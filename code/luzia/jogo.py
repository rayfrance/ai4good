"""Motor do jogo da Luzia: feixes, lúmens, degraus, rota e dossiê.

Regras em `docs/luzia-ux.md`. Tudo fica em `private/` (fora do git):
- avanços (os feixes): estado em `avanco` e história em `avanco_evento`, no banco;
- `lumens.jsonl`: livro de lúmens (skill, lm, luz própria ou refletida, fonte);
- níveis, base, data do último nível e subidas: banco (`trajetoria.py`: `prisma` e `nivel_registro`);
- `cartoes.json`: cartões que o observador mostrou (cada um pode virar luz própria uma vez).
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import arquivos, banco, trajetoria

PRIVATE = arquivos.PRIVATE
FEIXES = PRIVATE / 'feixes.json'  # só o caminho antigo: a migração lê, nada mais grava aqui
LUMENS = PRIVATE / 'lumens.jsonl'
DEGRAUS = PRIVATE / 'degraus.json'
AUTOAVAL = PRIVATE / 'autoavaliacao.json'
CARTOES = PRIVATE / 'cartoes.json'
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
                 'revisita_aberta', 'valor_lm', 'conta', 'criado_em', 'skill_plano'}
COLUNAS_ESTADO = ('nota', 'lm_ganho', 'tentativas', 'revisitas', 'revisita_aberta')
COLUNAS_EVENTO = ('onde', 'nota', 'resumo', 'motivo')
ESTADO_ANTIGO = {'conquistado': 'feita', 'em_andamento': 'em andamento', 'na_fila': 'pendente',
                 'sugerido': 'pendente', 'descartado': 'descartada'}


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _ler(path: Path, padrao):
    return arquivos.ler_json(path, padrao)


def _gravar(path: Path, dados) -> None:
    arquivos.gravar_json(path, dados)


# ------------------------------------------------------------------ níveis e skills
def niveis(plan: dict) -> dict[str, dict]:
    """Prismas ativos da trajetória (os do plano e os incluídos por pedido), com nível e meta lidos do banco."""
    with trajetoria.abrir() as con:
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
             conta=json.loads(r['conta_json']) if r['conta_json'] else None, historico=historico)
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


def avancos(con: sqlite3.Connection, estado: str | None = None, prisma: str | None = None,
            tipo: str | None = None, historico: bool = True) -> list[dict]:
    """Avanços do banco, na ordem do catálogo (estado, depois maior valor). Os filtros se combinam (E)."""
    onde, args = [], []
    for coluna, valor_ in (('estado', estado), ('prisma', prisma), ('tipo', tipo)):
        if valor_ is not None:
            onde.append(f'{coluna} = ?')
            args.append(valor_)
    ordem = ' '.join(f"WHEN '{e}' THEN {n}" for e, n in ORDEM_ESTADO.items())
    sql = ('SELECT * FROM avanco' + (' WHERE ' + ' AND '.join(onde) if onde else '')
           + f' ORDER BY CASE estado {ordem} ELSE 9 END, -COALESCE(valor_lm, 0), rowid')
    hist = _historicos(con) if historico else {}
    return [_feixe(r, hist.get(r['id'], [])) for r in con.execute(sql, args)]


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
        ' dimensao, estado, nota, lm_ganho, tentativas, revisitas, revisita_aberta, criado_em)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (f['id'], f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _json(_conteudo(f)),
         dur if isinstance(dur, int) and not isinstance(dur, bool) else None, f.get('valor_lm'),
         _json(f['conta']) if f.get('conta') is not None else None, _origem_coluna(f.get('origem')), f.get('dimensao'),
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
                atual.update({k: v for k, v in conteudo.items() if k != 'titulo' or not atual.get('renomeado')})
        for f in cat.values():
            if f.get('estado') != 'conquistado':
                f['valor_lm'], f['conta'] = valor(f, plan, nv, nomes)
            f['skill_plano'] = skill_de(f.get('skill', ''), plan, nomes)
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
    lista = [f for f in cat.values() if descartados or f.get('estado') != 'descartado']
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


def em_andamento() -> list[dict]:
    """Avanços em andamento (sem histórico), para a linha de status e o aviso de início de sessão."""
    with trajetoria.abrir() as con:
        return avancos(con, estado='em_andamento', historico=False)


# ------------------------------------------------------------------ lúmens
def lancar(skill: str, lm: int, luz: str, fonte: str, ref: str = '') -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    rec = {'quando': agora(), 'skill': skill, 'lm': int(lm), 'luz': luz, 'fonte': fonte, 'ref': ref}
    with LUMENS.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def livro() -> list[dict]:
    if not LUMENS.exists():
        return []
    out = []
    for linha in LUMENS.read_text(encoding='utf-8').splitlines():
        try:
            out.append(json.loads(linha))
        except Exception:
            continue
    return out


def conquistar(fid: str, nota: int, resumo: str, plan: dict) -> dict:
    """Aplica a rubrica: ganha lúmens, ou volta como 'tente de novo'. Permite uma revisita para notas 2-3."""
    cat = sincronizar(plan)
    f = cat.get(fid)
    if not f:
        return {'erro': 'feixe não encontrado'}
    nota = max(0, min(4, int(nota)))
    skill = f.get('skill_plano') or f.get('skill', '')
    alvo = int(round(f['valor_lm'] * MULT.get(nota, 0)))
    # Quem já ganhou lúmens neste feixe só pode voltar a ganhar pela revisita (mesmo se o estado se perdeu).
    revisita = f.get('estado') == 'conquistado' or int(f.get('lm_ganho') or 0) > 0
    if revisita:
        if not pode_revisitar({**f, 'estado': 'conquistado'}):
            return {'erro': 'este feixe já foi revisitado ou já tem nota máxima'}
        if not f.get('revisita_aberta'):
            return {'erro': f'abra a revisita antes de registrar (/luzia:fazer {fid})'}
    elif f.get('estado') != 'em_andamento':
        return {'erro': f'este feixe ainda não foi iniciado: comece por /luzia:fazer {fid}'}
    if nota < 2:  # tente de novo: o feixe (ou a revisita) continua aberto e a próxima tentativa vale o mesmo
        with trajetoria.abrir() as con, banco.transacao(con):
            con.execute('UPDATE avanco SET tentativas = tentativas + 1 WHERE id = ?', (fid,))
            _evento(con, fid, 'tente de novo', nota=nota, resumo=resumo)
        return {'ganho': 0, 'tente_de_novo': True, 'feixe': _um(fid)}
    ganho = max(0, alvo - int(f.get('lm_ganho') or 0)) if revisita else alvo
    if ganho:
        lancar(skill, ganho, 'propria', 'feixe', fid)
    campos = {'nota': max(nota, int(f.get('nota') or 0)), 'lm_ganho': int(f.get('lm_ganho') or 0) + ganho, 'resumo': resumo}
    if revisita:
        campos.update(revisitas=1, revisita_aberta=False)
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            _atualizar_estado(con, fid, 'conquistado', campos)
            _evento(con, fid, 'revisitado' if revisita else 'conquistado', nota=nota, lm=ganho, resumo=resumo)
        f = _um(fid, con)
    return {'ganho': ganho, 'feixe': f, 'pode_revisitar': pode_revisitar(f)}


def passivo(skill: str, tipo: str, sessao: str = '') -> int:
    """Reconhecimento no dia a dia: 'refletida' (o agente aplicou), 'prompt' (você dirigiu) ou 'conversao'."""
    hoje = agora()[:10]
    ja = sum(r['lm'] for r in livro() if r['skill'] == skill and r['fonte'].startswith('passivo') and r['quando'][:10] == hoje)
    if tipo != 'conversao' and ja >= TETO_PASSIVO_DIA:
        return 0
    lm = PASSIVO[tipo] if tipo != 'conversao' else PASSIVO['conversao']
    lm = min(lm, max(0, TETO_PASSIVO_DIA - ja)) if tipo != 'conversao' else lm
    if lm:
        lancar(skill, lm, 'refletida' if tipo == 'refletida' else 'propria', f'passivo-{tipo}', sessao)
    return lm


def abrir_cartao(skill: str, sessao: str = '') -> None:
    """O observador mostrou um cartão: ele pode virar luz própria uma única vez, nas próximas 24 h."""
    corte = (datetime.now() - timedelta(days=7)).isoformat(timespec='seconds')
    cartoes = [c for c in _ler(CARTOES, []) if c.get('quando', '') >= corte]
    cartoes.append({'skill': skill, 'sessao': sessao, 'quando': agora(), 'estado': 'aberto'})
    _gravar(CARTOES, cartoes)


def usar_cartao(skill: str, como: str) -> bool:
    """Fecha o cartão aberto mais recente da skill ('convertido' ou 'guardado'). False se não houver."""
    cartoes = _ler(CARTOES, [])
    corte = (datetime.now() - timedelta(hours=VALIDADE_CARTAO_H)).isoformat(timespec='seconds')
    for c in reversed(cartoes):
        if c.get('skill') == skill and c.get('estado') == 'aberto' and c.get('quando', '') >= corte:
            c.update(estado=como, usado_em=agora())
            _gravar(CARTOES, cartoes)
            return True
    return False


def converter(skill: str, nota: int, ref: str = '') -> dict:
    """Resposta ao cartão do observador, avaliada pela rubrica: até +30 lm de luz própria, uma vez por cartão."""
    nota = max(0, min(4, int(nota)))
    if not usar_cartao(skill, 'convertido' if nota >= 2 else 'guardado'):
        return {'erro': 'não há cartão aberto da Luzia para esta skill: a conversão vale uma vez por cartão'}
    lm = round(PASSIVO['conversao'] * MULT.get(nota, 0))
    if lm:
        lancar(skill, lm, 'propria', 'passivo-conversao', ref)
    return {'lm': lm, 'nota': nota}


# ------------------------------------------------------------------ degraus e rota
def _degraus() -> dict:
    """Base, data do último nível, subidas conquistadas e marcos do dossiê (lidos do banco, no formato antigo)."""
    with trajetoria.abrir() as con:
        ativos = trajetoria.prismas(con)
        return {'base': {p['nome']: trajetoria.base_de(con, p) for p in ativos},
                'desde': {p['nome']: trajetoria.desde(con, p['nome']) for p in ativos},
                'historico': trajetoria.historico_subidas(con),
                'marcos_dossie': trajetoria.perfil_ler(con, 'marcos_dossie', [])}


def garantir_base(plan: dict) -> dict:
    """A base da rota é o primeiro registro do livro de níveis; skill sem registro ainda parte do nível atual."""
    d = _degraus()
    for nome, v in niveis(plan).items():
        d['base'].setdefault(nome, v['nivel'])
        d['desde'].setdefault(nome, '')
    return d


def progresso_skill(skill: str, d: dict | None = None) -> dict:
    d = d or _degraus()
    desde = d.get('desde', {}).get(skill, '')
    regs = [r for r in livro() if r['skill'] == skill and r['quando'] > desde]
    total = sum(r['lm'] for r in regs)
    propria = sum(r['lm'] for r in regs if r['luz'] == 'propria')
    share = (propria / total) if total else 0.0
    feixes = len({r.get('ref') for r in regs if r.get('fonte') == 'feixe'})
    falta = []
    if total < LIMIAR_DEGRAU:
        falta.append(f'{LIMIAR_DEGRAU - total} lm')
    if share < MIN_PROPRIA:
        falta.append(f'luz própria em {int(MIN_PROPRIA * 100)}% (agora {round(100 * share)}%)')
    if feixes < MIN_FEIXES_DEGRAU:
        falta.append('conquistar 1 feixe desta skill')
    return {'lm': total, 'propria': propria, 'refletida': total - propria, 'luz_propria': round(100 * share),
            'limiar': LIMIAR_DEGRAU, 'feixes': feixes, 'falta': falta, 'pronto': not falta}


def rota(plan: dict) -> dict:
    d = garantir_base(plan)
    nv = niveis(plan)
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
    lm_total = sum(r['lm'] for r in livro())
    lm_propria = sum(r['lm'] for r in livro() if r['luz'] == 'propria')
    marcos = [math.ceil(total * k / 3) for k in (1, 2, 3)] if total else []
    return {'niveis_total': total, 'niveis_feitos': feitos, 'degraus_total': total, 'degraus_feitos': feitos,
            'marcos': marcos, 'skills': skills,
            'lm_total': lm_total, 'luz_propria': round(100 * lm_propria / lm_total) if lm_total else 0,
            'pct': round(100 * feitos / total) if total else 100}


def subir(skill: str, plan: dict) -> dict:
    """Confirma um degrau pronto: sobe o nível declarado, zera o progresso da skill e checa marco."""
    d = garantir_base(plan)
    nv = niveis(plan)
    if skill not in nv:
        return {'erro': 'skill não encontrada no seu plano'}
    if nv[skill]['nivel'] >= nv[skill]['meta']:
        return {'erro': 'esta skill já está na meta'}
    p = progresso_skill(skill, d)
    if not p['pronto']:
        return {'erro': 'ainda não: falta ' + ', '.join(p['falta'])}
    novo = min(nv[skill]['meta'], nv[skill]['nivel'] + 1)
    with trajetoria.abrir() as con:
        if con.execute('SELECT 1 FROM prisma WHERE nome = ?', (skill,)).fetchone() is None:
            return {'erro': 'skill não encontrada na sua trajetória'}
        trajetoria.registrar_subida(con, skill, novo, p['lm'], p['luz_propria'])
    r = rota(plan)
    marco = None
    marcos_feitos = list(d.get('marcos_dossie', []))
    for i, m in enumerate(r['marcos'], 1):
        if r['niveis_feitos'] >= m and i not in marcos_feitos:
            marcos_feitos.append(i)
            with trajetoria.abrir() as con, trajetoria.banco.transacao(con):
                trajetoria.perfil_gravar(con, 'marcos_dossie', marcos_feitos)
            marco = {'n': i, 'dossie': str(dossie(plan, f'marco {i} de 3'))}
    return {'skill': skill, 'para': novo, 'rota': r, 'marco': marco}


def ritmo(plan: dict, horizonte: str = '') -> dict:
    """Calibragem (não cronograma): feixes por semana para chegar no prazo que a pessoa imagina."""
    r = rota(plan)
    faltam = sum(max(0, s['meta'] - s['nivel']) * LIMIAR_DEGRAU - (s['lm'] if not s['na_meta'] else 0) for s in r['skills'])
    meses = next((int(t) for t in str(horizonte).split() if t.isdigit()), 12)
    with trajetoria.abrir() as con:
        pend = [f for f in avancos(con, historico=False) if f.get('estado') in ('sugerido', 'na_fila')]
    medio = (sum(int(f.get('valor_lm', 40)) for f in pend) / len(pend)) if pend else 40
    semanas = max(1.0, meses * 4.33)
    return {'lm_faltam': max(0, faltam), 'meses': meses, 'feixes_semana': max(1, math.ceil(faltam / (medio * semanas)))}


# ------------------------------------------------------------------ dossiê
def dossie(plan: dict, titulo: str = 'agora') -> Path:
    r = rota(plan)
    with trajetoria.abrir() as con:
        conq = avancos(con, estado='conquistado')
    d = _degraus()
    linhas = [
        f'# Dossiê de evidências · {titulo} · {agora()[:10]}', '',
        f"Rota: **{r['degraus_feitos']} de {r['degraus_total']} degraus** até Plena · {r['lm_total']} lm · {r['luz_propria']}% de luz própria.", '',
        '## Degraus subidos',
    ]
    linhas += [f"- {h['quando'][:10]} · {h['skill']} → {h['para']} ({h['lm']} lm, {h['luz_propria']}% luz própria)" for h in d['historico']] or ['- nenhum ainda']
    linhas += ['', '## Feixes conquistados (evidência avaliada pela rubrica 0–4)']
    for f in sorted(conq, key=lambda x: (x.get('historico') or [{}])[-1].get('quando', '')):
        linhas.append(f"- **{f.get('titulo')}** · {f.get('skill_plano') or f.get('skill')} · nota {f.get('nota')}/4 · {f.get('lm_ganho')} lm — {f.get('resumo', '')}")
    if not conq:
        linhas.append('- nenhum ainda')
    linhas += ['', '## Por skill']
    for s in r['skills']:
        linhas.append(f"- {s['nome']}: nível {s['nivel']} (meta {s['meta']}) · {s['lm']} lm desde o último degrau · {s['luz_propria']}% luz própria")
    linhas += ['', '_Gerado localmente pela Luzia a partir das evidências registradas; não substitui a avaliação do seu líder._']
    DOSSIES.mkdir(parents=True, exist_ok=True)
    caminho = DOSSIES / f"dossie-{agora()[:10]}-{titulo.replace(' ', '-')}.md"
    caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    return caminho
