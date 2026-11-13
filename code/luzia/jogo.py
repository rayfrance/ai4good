"""Motor do jogo da Luzia: avanços (feixes), lúmens, níveis, lampejos, rota e dossiê.

Regras em `docs/luzia-ux.md`. Tudo mora no banco `private/luzia.db` (fora do git):
- avanços: estado em `avanco` e história em `avanco_evento`;
- lúmens: livro `lumen` (prisma, lm, luz própria ou refletida, fonte), só de acréscimo;
- níveis, base, data do último nível e subidas: `prisma` e `nivel_registro` (`trajetoria.py`);
- lampejos: tabela `lampejo` (cada um pode virar luz própria uma única vez, nas 24 h seguintes).
Os arquivos antigos só são lidos pela migração (`migrar.py`).
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import arquivos, banco, trajetoria

PRIVATE = arquivos.PRIVATE
DOSSIES = PRIVATE / 'dossies'

LIMIAR_DEGRAU = 150
MIN_PROPRIA = 0.40
MIN_FEIXES_DEGRAU = 1  # todo degrau precisa de ao menos um feixe avaliado pela rubrica (sem recompensa sem evidência)
MULT = {4: 1.0, 3: 0.75, 2: 0.5}
PASSIVO = {'refletida': 10, 'prompt': 20, 'conversao': 30}
TETO_PASSIVO_DIA = 40
VALIDADE_CARTAO_H = 24
MOTIVOS = {'nao_faz_sentido': 'não faz sentido para mim', 'ja_domino': 'já domino', 'agora_nao': 'agora não'}
ORDEM_ESTADO = {'em_andamento': 0, 'na_fila': 1, 'sugerido': 2, 'conquistado': 3, 'descartado': 4}
# Origem do feixe (nome antigo) → origem gravada na coluna do avanço (spec, seção 5); o nome antigo fica no conteúdo.
ORIGEM_COLUNA = {'rota': 'triagem', 'entrega': 'entrega', 'sessão': 'sessao', 'sessao': 'sessao',
                 'trecho': 'acender', 'guardada': 'lampejo'}
# O que o avanço guarda em colunas de estado; todo o resto do feixe vai inteiro em `conteudo_json`.
CAMPOS_ESTADO = {'id', 'status', 'estado', 'historico', 'nota', 'lm_ganho', 'tentativas', 'revisitas',
                 'revisita_aberta', 'valor_lm', 'conta', 'criado_em', 'skill_plano', 'entrega_id'}
COLUNAS_ESTADO = ('nota', 'lm_ganho', 'tentativas', 'revisitas', 'revisita_aberta')
COLUNAS_EVENTO = ('onde', 'nota', 'resumo', 'motivo')
ESTADO_ANTIGO = {'conquistado': 'feita', 'em_andamento': 'em andamento', 'na_fila': 'pendente',
                 'sugerido': 'pendente', 'descartado': 'descartada'}


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


# ------------------------------------------------------------------ níveis e skills
def niveis(plan: dict, con: sqlite3.Connection | None = None, espera_ms: int | None = None) -> dict[str, dict]:
    """Prismas ativos da trajetória (os do plano e os incluídos por pedido), com nível e meta lidos do banco.

    Quem já tem uma conexão a passa em `con` (a rota consulta tudo numa só); `espera_ms` encurta a espera do hook.
    """
    if con is None:
        with trajetoria.abrir(espera_ms) as nova:
            return niveis(plan, nova)
    todos = {p['nome']: p for p in trajetoria.prismas(con, incluir_arquivados=True)}
    declarados = trajetoria.declarados(con)
    out = {}
    for s in plan.get('skills', []):
        nome = s['nome']
        p = todos.get(nome)
        if p is not None and p['estado'] == 'arquivado':
            continue
        if p is not None:
            nivel, meta = p['nivel'], p['meta']
        else:  # skill nova do plano que o banco ainda não conhece
            nivel = s.get('autoavaliacao') if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
            meta = s.get('alvo', 5)
        out[nome] = {'nivel': int(nivel or 0), 'meta': int(meta), 'sugere': s.get('luzia_sugere'),
                     'declarado': nome in declarados}
    for nome, p in todos.items():
        if nome not in out and p['estado'] == 'ativo':
            out[nome] = {'nivel': p['nivel'], 'meta': p['meta'], 'sugere': None, 'declarado': nome in declarados}
    return out


def autoavaliacao() -> dict[str, int]:
    """Nível dos prismas que a pessoa declarou ou conquistou (o que antes ficava em autoavaliacao.json)."""
    with trajetoria.abrir() as con:
        return trajetoria.declarados(con)


def nomes_de_skills(plan: dict) -> list[str]:
    """Skills do plano e prismas incluídos por pedido (para casar nomes sem abrir o banco a cada feixe)."""
    nomes = [s['nome'] for s in plan.get('skills', [])]
    with trajetoria.abrir() as con:
        nomes += [p['nome'] for p in trajetoria.prismas(con) if p['nome'] not in nomes]
    return nomes


def skill_de(nome: str, plan: dict, nomes: list[str] | None = None) -> str:
    """Casa o nome de skill de um feixe com a skill do plano (tolerante a variações)."""
    if nomes is None:
        nomes = nomes_de_skills(plan)
    if nome in nomes:
        return nome
    base = (nome or '').lower()
    for n in nomes:
        chave = n.lower().split('(')[0].split('/')[0].strip()
        if chave and (chave in base or base in n.lower()):
            return n
    return nome


def valor(feixe: dict, plan: dict, nv: dict | None = None, nomes: list[str] | None = None) -> tuple[int, list[list]]:
    """Valor em lúmens por regra visível: esforço + lacuna + prioridade."""
    nv = niveis(plan) if nv is None else nv
    skill = skill_de(feixe.get('skill', ''), plan, nomes)
    info = nv.get(skill, {'nivel': 0, 'meta': 0})
    lacuna_niveis = max(0, info['meta'] - info['nivel'])
    esforco = max(5, min(30, int(feixe.get('duracao_min') or 10)))
    lacunas = sorted(((max(0, v['meta'] - v['nivel']), k) for k, v in nv.items()), reverse=True)
    top2 = {k for _, k in lacunas[:2]}
    prio = 0 if lacuna_niveis == 0 else (10 if skill in top2 else 5)
    conta = [['esforço', f"{esforco} min", esforco],
             ['lacuna', f"{info['nivel']} → {info['meta']}", 15 * lacuna_niveis],
             ['prioridade', 'uma das maiores lacunas' if prio == 10 else ('lacuna no plano' if prio else 'skill na meta'), prio]]
    total = max(10, min(100, sum(c[2] for c in conta)))
    return total, conta


# ------------------------------------------------------------------ avanços (estado em `avanco`, história em `avanco_evento`)
SQL_HISTORICO = "SELECT * FROM avanco_evento WHERE json_extract(extra_json, '$.fonte') = 'historico'"


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _conteudo(f: dict) -> dict:
    """O que o feixe tem além das colunas de estado (vai inteiro para `conteudo_json`)."""
    return {k: v for k, v in f.items() if k not in CAMPOS_ESTADO}


def _origem_coluna(origem):
    return ORIGEM_COLUNA.get(origem, origem) if isinstance(origem, str) else origem


def _colunas(f: dict) -> tuple:
    """Os campos de conteúdo do avanço (os que `sincronizar` pode mudar), para ver se algo mudou de fato."""
    return (f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _conteudo(f), f.get('duracao_min'),
            f.get('valor_lm'), f.get('conta'), _origem_coluna(f.get('origem')), f.get('dimensao'))


def _evento_de(r: sqlite3.Row) -> dict:
    """Linha de `avanco_evento` no formato do histórico antigo (`quando`, `evento`, e só os campos preenchidos)."""
    try:
        extra = json.loads(r['extra_json'] or '{}')
    except ValueError:
        extra = {}
    h = {'quando': r['quando'], 'evento': r['evento']}
    h.update({c: r[c] for c in COLUNAS_EVENTO if r[c] is not None})
    if isinstance(extra, dict):
        h.update({k: v for k, v in extra.items() if k != 'fonte'})
    return h


def _feixe(r: sqlite3.Row, historico: list[dict]) -> dict:
    """Linha de `avanco` no formato de feixe de sempre (as colunas mandam; o conteúdo traz o resto)."""
    try:
        f = json.loads(r['conteudo_json'] or '{}')
    except ValueError:
        f = {}
    if not isinstance(f, dict):
        f = {}
    f['id'] = r['id']
    for campo in ('titulo', 'tipo', 'dimensao', 'duracao_min'):
        if r[campo] is not None:
            f[campo] = r[campo]
        else:
            f.setdefault(campo, None)
    if 'origem' not in f:  # o nome antigo da origem (rota, sessão...) fica no conteúdo; a coluna usa o novo
        f['origem'] = r['origem']
    f.update(estado=r['estado'], valor_lm=r['valor_lm'], nota=r['nota'], lm_ganho=r['lm_ganho'],
             tentativas=r['tentativas'], revisitas=r['revisitas'], criado_em=r['criado_em'], skill_plano=r['prisma'],
             entrega_id=r['entrega_id'],
             conta=json.loads(r['conta_json']) if r['conta_json'] else None, historico=historico)
    if f.get('origem') == 'entrega' and r['entrega_id'] is None:
        # vem do que a IA montou na triagem, não do git: o título "da entrega" que ela inventou nunca aparece como entrega
        f.pop('entrega', None)
        f['da_triagem'] = True
    if r['revisita_aberta']:
        f['revisita_aberta'] = True
    else:
        f.pop('revisita_aberta', None)
    return f


def _historicos(con: sqlite3.Connection, fid: str | None = None) -> dict[str, list[dict]]:
    sql, args = (SQL_HISTORICO, ()) if fid is None else (SQL_HISTORICO + ' AND avanco_id = ?', (fid,))
    out: dict[str, list[dict]] = {}
    for r in con.execute(sql + ' ORDER BY id', args):
        out.setdefault(r['avanco_id'], []).append(_evento_de(r))
    return out


def _carregar(con: sqlite3.Connection, historico: bool = True) -> dict[str, dict]:
    hist = _historicos(con) if historico else {}
    return {r['id']: _feixe(r, hist.get(r['id'], [])) for r in con.execute('SELECT * FROM avanco ORDER BY rowid')}


ABERTOS = ('sugerido', 'na_fila', 'em_andamento')


def _ocultos(con: sqlite3.Connection) -> set[str]:
    """Prismas arquivados: os avanços ainda abertos deles não são oferecidos até o prisma ser reativado."""
    return {r['nome'] for r in con.execute("SELECT nome FROM prisma WHERE estado = 'arquivado'")}


def avancos(con: sqlite3.Connection, estado: str | None = None, prisma: str | None = None,
            tipo: str | None = None, historico: bool = True, arquivados: bool = False) -> list[dict]:
    """Avanços do banco, na ordem do catálogo (estado, depois maior valor). Os filtros se combinam (E).

    Os avanços abertos de prisma arquivado ficam de fora (os conquistados e descartados continuam: são história).
    """
    onde, args = [], []
    for coluna, valor_ in (('estado', estado), ('prisma', prisma), ('tipo', tipo)):
        if valor_ is not None:
            onde.append(f'{coluna} = ?')
            args.append(valor_)
    ordem = ' '.join(f"WHEN '{e}' THEN {n}" for e, n in ORDEM_ESTADO.items())
    sql = ('SELECT * FROM avanco' + (' WHERE ' + ' AND '.join(onde) if onde else '')
           + f' ORDER BY CASE estado {ordem} ELSE 9 END, -COALESCE(valor_lm, 0), rowid')
    hist = _historicos(con) if historico else {}
    ocultos = set() if arquivados else _ocultos(con)
    return [_feixe(r, hist.get(r['id'], [])) for r in con.execute(sql, args)
            if not (r['prisma'] in ocultos and r['estado'] in ABERTOS)]


def _um(fid: str, con: sqlite3.Connection | None = None) -> dict | None:
    if con is None:
        with trajetoria.abrir() as nova:
            return _um(fid, nova)
    r = con.execute('SELECT * FROM avanco WHERE id = ?', (fid,)).fetchone()
    return None if r is None else _feixe(r, _historicos(con, fid).get(fid, []))


def _inserir_avanco(con: sqlite3.Connection, f: dict) -> None:
    dur = f.get('duracao_min')
    con.execute(
        'INSERT OR IGNORE INTO avanco (id, prisma, tipo, titulo, conteudo_json, duracao_min, valor_lm, conta_json, origem,'
        ' entrega_id, dimensao, estado, nota, lm_ganho, tentativas, revisitas, revisita_aberta, criado_em)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (f['id'], f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _json(_conteudo(f)),
         dur if isinstance(dur, int) and not isinstance(dur, bool) else None, f.get('valor_lm'),
         _json(f['conta']) if f.get('conta') is not None else None, _origem_coluna(f.get('origem')), f.get('entrega_id'),
         f.get('dimensao'),
         f.get('estado') or 'sugerido', f.get('nota'), int(f.get('lm_ganho') or 0), int(f.get('tentativas') or 0),
         int(f.get('revisitas') or 0), 1 if f.get('revisita_aberta') else 0, f.get('criado_em') or agora()))


def _atualizar_conteudo(con: sqlite3.Connection, f: dict, antes: dict) -> None:
    """Grava só o que o sync mudou: o conteúdo é relido dentro da transação (um `resumo` gravado agora por
    `conquistar` não se perde) e recebe apenas as chaves que diferem do que o sync leu."""
    dur = f.get('duracao_min')
    atual = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (f['id'],)).fetchone()[0] or '{}')
    novo = _conteudo(f)
    atual.update({k: v for k, v in novo.items() if antes.get(k, object()) != v})
    for k in set(antes) - set(novo):
        atual.pop(k, None)
    con.execute(
        'UPDATE avanco SET prisma = ?, tipo = ?, titulo = ?, conteudo_json = ?, duracao_min = ?, valor_lm = ?,'
        ' conta_json = ?, origem = ?, dimensao = ? WHERE id = ?',
        (f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _json(atual),
         dur if isinstance(dur, int) and not isinstance(dur, bool) else None, f.get('valor_lm'),
         _json(f['conta']) if f.get('conta') is not None else None, _origem_coluna(f.get('origem')),
         f.get('dimensao'), f['id']))


def _atualizar_estado(con: sqlite3.Connection, fid: str, estado: str | None, campos: dict) -> None:
    """Muda o estado atual do avanço; campo sem coluna (ex.: `resumo`) vai para o conteúdo."""
    sets, args, extras = [], [], {}
    if estado:
        sets.append('estado = ?')
        args.append(estado)
    for k, v in campos.items():
        if k in COLUNAS_ESTADO:
            sets.append(f'{k} = ?')
            args.append(int(v) if k == 'revisita_aberta' else v)
        else:
            extras[k] = v
    if extras:
        atual = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (fid,)).fetchone()[0] or '{}')
        sets.append('conteudo_json = ?')
        args.append(_json({**atual, **extras}))
    if sets:
        con.execute(f'UPDATE avanco SET {", ".join(sets)} WHERE id = ?', (*args, fid))


def _evento(con: sqlite3.Connection, fid: str, evento: str, **campos) -> None:
    """Acrescenta ao livro um fato da história do avanço (`fonte` 'historico'; o que não tem coluna vai em extra)."""
    colunas = {c: campos.pop(c, None) for c in COLUNAS_EVENTO}
    con.execute('INSERT INTO avanco_evento (avanco_id, quando, evento, onde, nota, resumo, motivo, extra_json)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (fid, agora(), evento, colunas['onde'], colunas['nota'], colunas['resumo'], colunas['motivo'],
                 _json({'fonte': 'historico', **campos})))


# ------------------------------------------------------------------ catálogo de feixes
def sincronizar(plan: dict) -> dict[str, dict]:
    """Traz para o catálogo os feixes que a Luzia sugeriu, sem perder estados e histórico.

    Só insere avanços novos e atualiza o conteúdo (valor, conta, skill do plano...) do que mudou de fato:
    o painel lê a cada 4 s, então nada é regravado quando nada mudou.
    """
    from . import acoes
    nomes = nomes_de_skills(plan)
    nv = niveis(plan)
    with trajetoria.abrir() as con:
        cat = _carregar(con)
        antes = {fid: _colunas(f) for fid, f in cat.items()}
        novos: list[str] = []
        antigos = None  # eventos registrados antes do catálogo existir (lidos só se houver feixe novo)
        for f in acoes.derivadas(plan):
            fid = f['id']
            conteudo = {k: v for k, v in f.items() if k not in CAMPOS_ESTADO and k not in ('nota', 'resumo', 'quando')}
            atual = cat.get(fid)
            if atual is None:
                if antigos is None:
                    antigos = acoes.status_map(con)
                st = antigos.get(fid, {}).get('status')
                cat[fid] = {**conteudo, 'id': fid, 'estado': {'em andamento': 'em_andamento'}.get(st, 'sugerido'),
                            'criado_em': agora(), 'historico': [], 'tentativas': 0, 'lm_ganho': 0, 'revisitas': 0,
                            'nota': None}
                novos.append(fid)
            else:
                # título renomeado e prisma escolhido num pedido `dividir` (prisma_fixo) não voltam ao do plano
                atual.update({k: v for k, v in conteudo.items()
                              if not (k == 'titulo' and atual.get('renomeado'))
                              and not (k == 'skill' and atual.get('prisma_fixo'))})
        for f in cat.values():
            if f.get('estado') != 'conquistado':
                f['valor_lm'], f['conta'] = valor(f, plan, nv, nomes)
            f['skill_plano'] = f.get('prisma_fixo') or skill_de(f.get('skill', ''), plan, nomes)
        mudaram = [fid for fid, f in cat.items() if fid not in novos and _colunas(f) != antes[fid]]
        if novos or mudaram:
            with banco.transacao(con):
                for fid in novos:
                    _inserir_avanco(con, cat[fid])
                for fid in mudaram:
                    _atualizar_conteudo(con, cat[fid], antes[fid][3])
    return cat


def catalogo(plan: dict, descartados: bool = False) -> list[dict]:
    cat = sincronizar(plan)
    with trajetoria.abrir() as con:
        ocultos = _ocultos(con)
    lista = [f for f in cat.values() if (descartados or f.get('estado') != 'descartado')
             and not (f.get('skill_plano') in ocultos and f.get('estado') in ABERTOS)]
    for f in lista:
        f['status'] = ESTADO_ANTIGO.get(f.get('estado'), 'pendente')
    return sorted(lista, key=lambda f: (ORDEM_ESTADO.get(f.get('estado'), 9), -int(f.get('valor_lm') or 0)))


def _mudar(fid: str, estado: str | None, evento: str, campos: dict | None = None, **extra) -> dict | None:
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            if con.execute('SELECT 1 FROM avanco WHERE id = ?', (fid,)).fetchone() is None:
                return None
            _atualizar_estado(con, fid, estado, campos or {})
            _evento(con, fid, evento, **extra)
        return _um(fid, con)


def pode_revisitar(f: dict) -> bool:
    """Uma revisita, só para feixe conquistado com nota 2 ou 3."""
    return f.get('estado') == 'conquistado' and int(f.get('nota') or 0) in (2, 3) and not f.get('revisitas')


def enfileirar(fid: str):
    """Manda o feixe para a fila do agente. Um feixe conquistado continua conquistado (a fila abre a revisita)."""
    f = _um(fid)
    if not f or f.get('estado') == 'descartado':
        return None
    if f.get('estado') == 'conquistado':
        return _mudar(fid, None, 'revisita enviada ao agente') if pode_revisitar(f) else None
    return _mudar(fid, None if f.get('estado') == 'em_andamento' else 'na_fila', 'enviado ao agente')


def iniciar(fid: str, onde: str = ''):
    f = _um(fid)
    if not f or f.get('estado') == 'descartado':
        return None
    if f.get('estado') == 'conquistado':
        if not pode_revisitar(f):
            return None
        return _mudar(fid, None, 'revisita iniciada', {'revisita_aberta': True}, onde=onde)
    return _mudar(fid, 'em_andamento', 'iniciado', onde=onde)


def descartar(fid: str, motivo: str):
    return _mudar(fid, 'descartado', 'descartado', motivo=MOTIVOS.get(motivo, motivo))


def restaurar(fid: str):
    return _mudar(fid, 'sugerido', 'restaurado')


def motivos_descartados() -> list[dict]:
    with trajetoria.abrir() as con:
        return [{'titulo': f.get('titulo'), 'skill': f.get('skill'), 'motivo': (f.get('historico') or [{}])[-1].get('motivo')}
                for f in avancos(con, estado='descartado')]


def em_andamento(espera_ms: int | None = None) -> list[dict]:
    """Avanços em andamento (sem histórico), para a linha de status e o aviso de início de sessão."""
    with trajetoria.abrir(espera_ms) as con:
        return avancos(con, estado='em_andamento', historico=False)




# ------------------------------------------------------------------ lúmens (livro `lumen`, só de acréscimo)
def _lumen(con: sqlite3.Connection, skill: str, lm: int, luz: str, fonte: str, ref: str = '') -> dict:
    """Acrescenta um lúmen ao livro, dentro da transação de quem chama."""
    rec = {'quando': agora(), 'skill': skill, 'lm': int(lm), 'luz': luz, 'fonte': fonte, 'ref': ref}
    con.execute('INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, ?, ?, ?, ?)',
                (rec['quando'], skill, rec['lm'], luz, fonte, ref))
    return rec


def lancar(skill: str, lm: int, luz: str, fonte: str, ref: str = '') -> dict:
    with trajetoria.abrir() as con, banco.transacao(con):
        return _lumen(con, skill, lm, luz, fonte, ref)


def livro(desde: str | None = None, limite: int | None = None) -> list[dict]:
    """Lúmens na ordem em que entraram (quando, skill, lm, luz, fonte, ref). `desde`: data/hora mínima; `limite`: só os últimos."""
    sql = 'SELECT quando, prisma AS skill, lm, luz, fonte, ref FROM lumen'
    args: list = []
    if desde:
        sql += ' WHERE quando >= ?'
        args.append(desde)
    if limite:
        sql += ' ORDER BY id DESC LIMIT ?'
        args.append(int(limite))
    else:
        sql += ' ORDER BY id'
    with trajetoria.abrir() as con:
        linhas = [dict(r) for r in con.execute(sql, args)]
    return linhas[::-1] if limite else linhas


def conquistar(fid: str, nota: int, resumo: str, plan: dict) -> dict:
    """Aplica a rubrica: ganha lúmens, ou volta como 'tente de novo'. Permite uma revisita para notas 2-3.

    O lúmen e a mudança do avanço (estado, nota, evento) entram numa transação só: ou os dois, ou nenhum.
    """
    cat = sincronizar(plan)
    f = cat.get(fid)
    if not f:
        return {'erro': 'centelha não encontrada'}
    nota = max(0, min(4, int(nota)))
    skill = f.get('skill_plano') or f.get('skill', '')
    alvo = int(round(f['valor_lm'] * MULT.get(nota, 0)))
    # Quem já ganhou lúmens neste feixe só pode voltar a ganhar pela revisita (mesmo se o estado se perdeu).
    revisita = f.get('estado') == 'conquistado' or int(f.get('lm_ganho') or 0) > 0
    if revisita:
        if not pode_revisitar({**f, 'estado': 'conquistado'}):
            return {'erro': 'esta centelha já foi revisitada ou já tem nota máxima'}
        if not f.get('revisita_aberta'):
            return {'erro': f'abra a revisita antes de registrar (/luzia:fazer {fid})'}
    elif f.get('estado') != 'em_andamento':
        return {'erro': f'esta centelha ainda não foi iniciada: comece por /luzia:fazer {fid}'}
    if nota < 2:  # tente de novo: o feixe (ou a revisita) continua aberto e a próxima tentativa vale o mesmo
        with trajetoria.abrir() as con, banco.transacao(con):
            con.execute('UPDATE avanco SET tentativas = tentativas + 1 WHERE id = ?', (fid,))
            _evento(con, fid, 'tente de novo', nota=nota, resumo=resumo)
        return {'ganho': 0, 'tente_de_novo': True, 'feixe': _um(fid)}
    ganho = max(0, alvo - int(f.get('lm_ganho') or 0)) if revisita else alvo
    campos = {'nota': max(nota, int(f.get('nota') or 0)), 'lm_ganho': int(f.get('lm_ganho') or 0) + ganho, 'resumo': resumo}
    if revisita:
        campos.update(revisitas=1, revisita_aberta=False)
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            vivo = con.execute('SELECT estado, lm_ganho, revisitas, revisita_aberta FROM avanco WHERE id = ?', (fid,)).fetchone()
            visto = (f.get('estado'), int(f.get('lm_ganho') or 0), int(f.get('revisitas') or 0), 1 if f.get('revisita_aberta') else 0)
            if vivo is None or tuple(vivo) != visto:  # outro processo mexeu no avanço entre a leitura e a gravação
                return {'erro': 'esta centelha mudou enquanto você registrava: confira o estado e tente de novo'}
            if ganho:
                _lumen(con, skill, ganho, 'propria', 'feixe', fid)
            _atualizar_estado(con, fid, 'conquistado', campos)
            _evento(con, fid, 'revisitado' if revisita else 'conquistado', nota=nota, lm=ganho, resumo=resumo)
        f = _um(fid, con)
    return {'ganho': ganho, 'feixe': f, 'pode_revisitar': pode_revisitar(f)}


# Lúmens passivos que ESTE processo mandou para os pendentes (prisma, dia) e o banco ainda não viu: entram no teto do dia.
_PENDURADO: dict[tuple[str, str, str], int] = {}


def passivo(skill: str, tipo: str, sessao: str = '') -> int:
    """Reconhecimento no dia a dia: 'refletida' (o agente aplicou), 'prompt' (você dirigiu) ou 'conversao'.

    Caminho quente do hook: UMA tentativa curta (ESPERA_CURTA_MS) lê o teto do dia e grava o lúmen na mesma transação.
    Se o banco estiver ocupado, o evento vai para `pendentes.jsonl` com o valor cheio do tipo; linhas pendentes ainda
    não contam no teto (o excesso possível fica limitado pela regra de um reconhecimento por prisma por sessão).
    """
    cheio = PASSIVO[tipo]
    resultado = {'lm': cheio}
    dia = agora()[:10]
    marca = (str(banco.caminho()), skill, dia)  # por banco: nada vaza entre pastas privadas
    dados = {'prisma': skill, 'lm': cheio, 'luz': 'refletida' if tipo == 'refletida' else 'propria',
             'fonte': f'passivo-{tipo}', 'ref': sessao}

    def ja_hoje(con):
        return int(con.execute("SELECT COALESCE(SUM(lm), 0) FROM lumen WHERE prisma = ? AND fonte LIKE 'passivo%' "
                               'AND quando >= ?', (skill, dia)).fetchone()[0])

    def limitar(ja):
        return cheio if tipo == 'conversao' else min(cheio, max(0, TETO_PASSIVO_DIA - ja))

    if banco.ocupado():  # a escrita nem tenta; mas leitura não bloqueia no WAL: o teto continua valendo
        ja = _PENDURADO.get(marca, 0)
        try:
            with trajetoria.abrir(banco.ESPERA_CURTA_MS) as con:
                ja += ja_hoje(con)
        except Exception as e:
            arquivos.registrar_erro('jogo.passivo teto', e)
        lm = limitar(ja)
        if lm and not banco.gravar_ou_pendurar('lumen', {**dados, 'lm': lm}):
            _PENDURADO[marca] = _PENDURADO.get(marca, 0) + lm
        return lm

    def no_teto(con, d):
        ja = ja_hoje(con)  # a transação absorveu os pendentes antes: o que este processo pendurou já está no livro
        lm = limitar(ja)
        resultado['lm'] = lm
        return {**d, 'lm': lm} if lm else None

    if banco.gravar_ou_pendurar('lumen', dados, ajustar=no_teto):
        _PENDURADO.pop(marca, None)  # só depois do COMMIT: os pendentes deste processo já estão no livro
    else:
        _PENDURADO[marca] = _PENDURADO.get(marca, 0) + cheio  # foi para os pendentes com o valor cheio
    return resultado['lm']


def reconhecer(sessao: str, chave: str, skill: str, tipo: str, extensao: str = '', ferramenta: str = '',
               modo: str = '', interveio: bool = False, lampejo: bool = False, estado: dict | None = None) -> int | None:
    """Um reconhecimento do observador, inteiro e numa tentativa curta: uma vez por prisma por sessão e por origem
    (`chave`: 'prompt' ou 'agente'), lúmen passivo dentro do teto do dia, evento da sessão e, se pedido, lampejo.

    Devolve o lm ganho (0 se o teto já encheu) ou None se a sessão já tinha reconhecido este prisma. Se o banco estiver
    ocupado, o reconhecimento inteiro vai para os pendentes (nada se perde) e a função devolve o valor cheio do tipo,
    provisório: na absorção vale o primeiro que chegar e o teto do dia. Nunca levanta por causa do banco.
    `estado` (opcional) recebe `provisorio=True` quando o reconhecimento foi para os pendentes (valor e lampejo não confirmados).
    """
    dados = {'sessao': sessao, 'chave': chave, 'prisma': skill, 'lm': PASSIVO[tipo],
             'luz': 'refletida' if tipo == 'refletida' else 'propria', 'fonte': f'passivo-{tipo}', 'ref': sessao,
             'teto': None if tipo == 'conversao' else TETO_PASSIVO_DIA, 'extensao': extensao, 'ferramenta': ferramenta,
             'modo': modo, 'interveio': 1 if interveio else 0, 'lampejo': 1 if lampejo else 0}
    retorno: dict = {}
    if banco.gravar_ou_pendurar('reconhecimento', dados, retorno=retorno):
        return retorno.get('resultado')
    if estado is not None:
        estado['provisorio'] = True
    return PASSIVO[tipo]


# ------------------------------------------------------------------ lampejos (tabela `lampejo`)
def abrir_lampejo(skill: str, sessao: str = '') -> bool:
    """O observador mostrou um lampejo: ele pode virar luz própria uma única vez, nas próximas 24 h. Nunca levanta no banco ocupado."""
    return banco.gravar_ou_pendurar('lampejo', {'prisma': skill, 'sessao': sessao})


def _fechar_lampejo(con: sqlite3.Connection, skill: str, como: str) -> bool:
    """Fecha o lampejo aberto mais recente do prisma (dentro da transação de quem chama). False se não houver."""
    corte = (datetime.now() - timedelta(hours=VALIDADE_CARTAO_H)).isoformat(timespec='seconds')
    r = con.execute("SELECT id FROM lampejo WHERE prisma = ? AND estado = 'aberto' AND quando >= ? "
                    'ORDER BY quando DESC, id DESC LIMIT 1', (skill, corte)).fetchone()
    if r is None:
        return False
    con.execute('UPDATE lampejo SET estado = ?, usado_em = ? WHERE id = ?', (como, agora(), r['id']))
    return True


def usar_lampejo(skill: str, como: str) -> bool:
    """Fecha o lampejo aberto mais recente da skill ('convertido' ou 'guardado'). False se não houver."""
    with trajetoria.abrir() as con, banco.transacao(con):
        return _fechar_lampejo(con, skill, como)


def converter(skill: str, nota: int, ref: str = '') -> dict:
    """Resposta ao lampejo, avaliada pela rubrica: até +30 lm de luz própria, uma vez por lampejo.

    Fechar o lampejo e lançar o lúmen acontecem na mesma transação.
    """
    nota = max(0, min(4, int(nota)))
    lm = round(PASSIVO['conversao'] * MULT.get(nota, 0))
    with trajetoria.abrir() as con, banco.transacao(con):
        if not _fechar_lampejo(con, skill, 'convertido' if nota >= 2 else 'guardado'):
            return {'erro': 'não há centelha da sessão aberta para este prisma: a conversão vale uma vez por centelha'}
        if lm:
            _lumen(con, skill, lm, 'propria', 'passivo-conversao', ref)
    return {'lm': lm, 'nota': nota}


# ------------------------------------------------------------------ níveis e rota
SQL_PROGRESSO = """
    WITH ult AS (SELECT prisma, MAX(quando) AS desde FROM nivel_registro GROUP BY prisma)
    SELECT l.prisma, SUM(l.lm) AS lm, SUM(CASE WHEN l.luz = 'propria' THEN l.lm ELSE 0 END) AS propria,
           COUNT(DISTINCT CASE WHEN l.fonte = 'feixe' THEN l.ref END) AS feixes
    FROM lumen l LEFT JOIN ult ON ult.prisma = l.prisma
    WHERE l.quando > COALESCE(ult.desde, '')
    GROUP BY l.prisma"""


def _degraus(con: sqlite3.Connection | None = None, espera_ms: int | None = None) -> dict:
    """Base, data do último nível, lúmens desde então, subidas conquistadas e marcos do dossiê (uma foto do banco).

    Poucas consultas para todos os prismas de uma vez: a rota roda a cada atualização do painel.
    """
    if con is None:
        with trajetoria.abrir(espera_ms) as nova:
            return _degraus(nova)
    ativos = trajetoria.prismas(con)
    primeiro, ultimo, origem = {}, {}, {}
    for r in con.execute('SELECT prisma, quando, para, origem FROM nivel_registro ORDER BY quando, id'):
        primeiro.setdefault(r['prisma'], int(r['para']))
        ultimo[r['prisma']], origem[r['prisma']] = r['quando'], r['origem']
    progresso = {r['prisma']: (int(r['lm']), int(r['propria']), int(r['feixes'])) for r in con.execute(SQL_PROGRESSO)}
    return {'base': {p['nome']: primeiro.get(p['nome'], p['nivel']) for p in ativos},
            'desde': {p['nome']: ultimo.get(p['nome'], '') for p in ativos},
            'origem_do_nivel': origem,
            'progresso': progresso,
            'historico': trajetoria.historico_subidas(con),
            'marcos_dossie': trajetoria.perfil_ler(con, 'marcos_dossie', [])}


def garantir_base(plan: dict, con: sqlite3.Connection | None = None) -> dict:
    """A base da rota é o primeiro registro do livro de níveis; skill sem registro ainda parte do nível atual."""
    if con is None:
        with trajetoria.abrir() as nova:
            return garantir_base(plan, nova)
    d = _degraus(con)
    for nome, v in niveis(plan, con).items():
        d['base'].setdefault(nome, v['nivel'])
        d['desde'].setdefault(nome, '')
    return d


def progresso_skill(skill: str, d: dict | None = None) -> dict:
    """Progresso do prisma até o próximo nível: lúmens desde o último registro de nível (de qualquer origem)."""
    d = d or _degraus()
    total, propria, feixes = d.get('progresso', {}).get(skill, (0, 0, 0))
    share = (propria / total) if total else 0.0
    falta = []
    if total < LIMIAR_DEGRAU:
        falta.append(f'{LIMIAR_DEGRAU - total} lm')
    if share < MIN_PROPRIA:
        falta.append(f'luz própria ≥ {int(MIN_PROPRIA * 100)}% (agora {round(100 * share)}%)')
    if feixes < MIN_FEIXES_DEGRAU:
        falta.append('1 centelha acesa')
    return {'lm': total, 'propria': propria, 'refletida': total - propria, 'luz_propria': round(100 * share),
            'limiar': LIMIAR_DEGRAU, 'feixes': feixes, 'falta': falta, 'pronto': not falta}




def rota(plan: dict, con: sqlite3.Connection | None = None, espera_ms: int | None = None) -> dict:
    if con is None:
        with trajetoria.abrir(espera_ms) as nova:
            return rota(plan, nova)
    nv = niveis(plan, con)
    d = garantir_base(plan, con)
    skills, total, feitos = [], 0, 0
    for nome, v in nv.items():
        base = int(d['base'].get(nome, v['nivel']))
        falta_total = max(0, v['meta'] - base)
        feitos_s = max(0, min(falta_total, v['nivel'] - base))
        total += falta_total
        feitos += feitos_s
        p = progresso_skill(nome, d)
        skills.append({'nome': nome, 'nivel': v['nivel'], 'meta': v['meta'], 'proximo': min(v['meta'], v['nivel'] + 1),
                       'na_meta': v['nivel'] >= v['meta'], **p})
    lm_total, lm_propria = trajetoria.lumens_totais(con)
    marcos = [math.ceil(total * k / 3) for k in (1, 2, 3)] if total else []
    return {'niveis_total': total, 'niveis_feitos': feitos, 'degraus_total': total, 'degraus_feitos': feitos,
            'marcos': marcos, 'skills': skills,
            'lm_total': lm_total, 'luz_propria': round(100 * lm_propria / lm_total) if lm_total else 0,
            'pct': round(100 * feitos / total) if total else 100}


def subir(skill: str, plan: dict) -> dict:
    """Confirma um nível pronto: sobe o nível (registro `conquistado`), zera o progresso do prisma e checa marco.

    Só é chamada depois do sim da pessoa (CLI `subir` / botão do painel). Tudo numa transação (BEGIN IMMEDIATE):
    o nível e o progresso são relidos com a trava na mão, então dois "sim" ao mesmo tempo sobem um nível só.
    """
    marco_titulo = None
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            d = garantir_base(plan, con)
            nv = niveis(plan, con)
            if skill not in nv:
                return {'erro': 'skill não encontrada no seu plano'}
            if nv[skill]['nivel'] >= nv[skill]['meta']:
                return {'erro': 'esta skill já está na meta'}
            p = progresso_skill(skill, d)
            if not p['pronto']:
                recente = (datetime.now() - timedelta(seconds=30)).isoformat(timespec='seconds')
                if d['origem_do_nivel'].get(skill) == 'conquistado' and d['desde'].get(skill, '') >= recente:
                    return {'erro': 'já subiu: este nível acabou de ser confirmado'}
                return {'erro': 'ainda não: falta ' + ', '.join(p['falta'])}
            novo = min(nv[skill]['meta'], nv[skill]['nivel'] + 1)
            if con.execute('SELECT 1 FROM prisma WHERE nome = ?', (skill,)).fetchone() is None:
                return {'erro': 'skill não encontrada na sua trajetória'}
            trajetoria.acrescentar_subida(con, skill, nv[skill]['nivel'], novo, p['lm'], p['luz_propria'])
            r = rota(plan, con)
            marcos_feitos = list(d.get('marcos_dossie', []))
            for i, m in enumerate(r['marcos'], 1):
                if r['niveis_feitos'] >= m and i not in marcos_feitos:
                    marcos_feitos.append(i)
                    trajetoria.perfil_gravar(con, 'marcos_dossie', marcos_feitos)
                    marco_titulo = i
        marco = None if marco_titulo is None else {
            'n': marco_titulo, 'dossie': str(dossie(plan, f'marco {marco_titulo} de 3', con))}
    return {'skill': skill, 'para': novo, 'rota': r, 'marco': marco}


def ritmo(plan: dict, horizonte: str = '') -> dict:
    """Calibragem (não cronograma): feixes por semana para chegar no prazo que a pessoa imagina."""
    with trajetoria.abrir() as con:
        r = rota(plan, con)
        pend = [f for f in avancos(con, historico=False) if f.get('estado') in ('sugerido', 'na_fila')]
    faltam = sum(max(0, s['meta'] - s['nivel']) * LIMIAR_DEGRAU - (s['lm'] if not s['na_meta'] else 0) for s in r['skills'])
    meses = next((int(t) for t in str(horizonte).split() if t.isdigit()), 12)
    medio = (sum(int(f.get('valor_lm', 40)) for f in pend) / len(pend)) if pend else 40
    semanas = max(1.0, meses * 4.33)
    return {'lm_faltam': max(0, faltam), 'meses': meses, 'feixes_semana': max(1, math.ceil(faltam / (medio * semanas)))}


# ------------------------------------------------------------------ dossiê
TIPO_PEDIDO = {'incluir': 'incluir skill', 'arquivar': 'arquivar skill', 'reativar': 'reativar skill',
               'mudar_meta': 'mudar a meta de uma skill'}
SQL_PEDIDOS_ACEITOS = """
    SELECT p.tipo, p.prisma, p.motivo, p.criado_em, p.decidido_em, l.texto, l.modelo, l.criado_em AS leitura_em
    FROM pedido p LEFT JOIN leitura l ON l.id = p.leitura_id
    WHERE p.estado = 'aceito' ORDER BY COALESCE(p.decidido_em, p.criado_em), p.id"""


def dossie(plan: dict, titulo: str = 'agora', con: sqlite3.Connection | None = None) -> Path:
    """Dossiê de evidências em linguagem formal (skill, nível, ação): só níveis conquistados contam como evidência."""
    if con is None:
        with trajetoria.abrir() as nova:
            return dossie(plan, titulo, nova)
    r = rota(plan, con)
    conq = avancos(con, estado='conquistado')
    d = _degraus(con)
    pedidos = con.execute(SQL_PEDIDOS_ACEITOS).fetchall()
    linhas = [
        f'# Dossiê de evidências · {titulo} · {agora()[:10]}', '',
        f"Trajetória: **{r['niveis_feitos']} de {r['niveis_total']} níveis** até a meta · {r['lm_total']} pontos de evidência acumulados · "
        f"{r['luz_propria']}% de autoria própria.", '',
        '## Níveis conquistados',
    ]
    linhas += [f"- {h['quando'][:10]} · {h['skill']} → nível {h['para']} ({h['lm']} pontos de evidência no período, {h['luz_propria']}% de autoria própria)"
               for h in d['historico']] or ['- nenhum ainda']
    linhas += ['', '## Ações concluídas (evidência avaliada pela rubrica 0–4)']
    for f in sorted(conq, key=lambda x: (x.get('historico') or [{}])[-1].get('quando', '')):
        linhas.append(f"- **{f.get('titulo')}** · {f.get('skill_plano') or f.get('skill')} · nota {f.get('nota')}/4 · "
                      f"{f.get('lm_ganho')} pontos de evidência — {f.get('resumo', '')}")
    if not conq:
        linhas.append('- nenhuma ainda')
    linhas += ['', '## Pedidos de mudança aceitos']
    for p in pedidos:
        linha = f"- {(p['decidido_em'] or p['criado_em'])[:10]} · {TIPO_PEDIDO.get(p['tipo'], p['tipo'])} · {p['prisma']}"
        if p['motivo']:
            linha += f" — {p['motivo']}"
        linhas.append(linha)
        if p['texto'] and p['modelo']:
            linhas.append(f"  - Análise: {p['texto']} (com base em {p['modelo']}, {(p['leitura_em'] or '')[:10]})")
        elif p['texto']:
            linhas.append('  - Análise: leitura indisponível')
    if not pedidos:
        linhas.append('- nenhum')
    linhas += ['', '## Por skill']
    for s in r['skills']:
        declarado = ' · nível declarado pela pessoa' if d['origem_do_nivel'].get(s['nome']) == 'declarado' else ''
        linhas.append(f"- {s['nome']}: nível {s['nivel']} (meta {s['meta']}) · {s['lm']} pontos de evidência desde o último nível · "
                      f"{s['luz_propria']}% de autoria própria{declarado}")
    linhas += ['', '_Gerado localmente pela Luzia a partir das evidências registradas; não substitui a avaliação do seu líder._']
    DOSSIES.mkdir(parents=True, exist_ok=True)
    caminho = DOSSIES / f"dossie-{agora()[:10]}-{titulo.replace(' ', '-')}.md"
    caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    return caminho
