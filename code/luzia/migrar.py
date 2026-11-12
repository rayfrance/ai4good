"""Migração única dos JSON antigos de `private/` para o banco (`luzia.db`), sem perder nem duplicar nada.

`banco.garantir` chama `migrar(con)` uma única vez, já dentro de uma transação `BEGIN EXCLUSIVE`: aí esta função só
executa comandos na conexão recebida (não abre, não confirma, não desfaz). Chamada solta (testes, conferência),
abre a própria transação exclusiva. Qualquer erro desfaz tudo: nenhuma linha migrada e nenhuma marca.

Antes de ler, os originais são copiados para `private/migracao-AAAAMMDD/`; nada é apagado nem alterado.
Rodar de novo não duplica: a marca `meta('migracao')`, gravada aqui no fim, encerra a função sem tocar no banco
(`banco.garantir` confere `meta('migrado_em')` por conta própria).

De → para (formatos antigos de jogo.py, acoes.py, observer.py e pipeline.py):
- `career_state.json` → `perfil` ('plano' inteiro, 'rotulos', 'estado_legado' com o resto do arquivo),
  `prisma` (nível de `autoavaliacao.json` ou do plano, meta = `alvo`, palavras = `palavras_chave` + padrão do observador)
  e `trajetoria_versao` nº 1 (origem 'triagem');
- `autoavaliacao.json` → nível atual do prisma e `perfil('autoavaliacao')`;
- `feixes.json` → `avanco` (+ `historico` → `avanco_evento`); `acoes_guardadas.json` → `avanco` origem 'lampejo';
- `evidencias.jsonl` → `avanco_evento` (eventos 'iniciada'/'concluida', mesmo com id fora do catálogo);
- `lumens.jsonl` → `lumen`; `cartoes.json` → `lampejo`; `fila.json` → `fila`; `sessao.jsonl` → `sessao_evento`;
- `degraus.json` → `nivel_registro` (base = 1 registro 'migrado', cada subida do histórico = 'conquistado',
  nível declarado depois = 'declarado'), `desde` → `prisma.ultimo_nivel_em`, `marcos_dossie` → `perfil`.

As regras antigas usadas aqui (nível de `jogo.niveis`, nome de `jogo.skill_de`, rótulos de `pipeline.rotulos`)
estão copiadas de propósito: a migração lê o formato antigo e não pode mudar quando aqueles módulos passarem ao banco.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import arquivos, banco

ARQUIVOS = ('feixes.json', 'lumens.jsonl', 'degraus.json', 'autoavaliacao.json', 'cartoes.json', 'evidencias.jsonl',
            'fila.json', 'acoes_guardadas.json', 'sessao.jsonl', 'career_state.json')
TABELAS = ('perfil', 'prisma', 'trajetoria_versao', 'avanco', 'avanco_evento', 'lumen', 'nivel_registro', 'lampejo',
           'fila', 'sessao_evento')
# Origem antiga do feixe → origem do avanço (spec, seção 5). Uma origem desconhecida fica como veio.
ORIGEM_AVANCO = {'rota': 'triagem', 'entrega': 'entrega', 'sessão': 'sessao', 'sessao': 'sessao',
                 'trecho': 'acender', 'guardada': 'lampejo'}
# Campos do feixe que viram colunas de estado do avanço; todo o resto vai inteiro para `conteudo_json`.
ESTADO_FEIXE = {'id', 'status', 'estado', 'historico', 'nota', 'lm_ganho', 'tentativas', 'revisitas',
                'revisita_aberta', 'valor_lm', 'conta', 'criado_em'}
COLUNAS_EVENTO = ('quando', 'evento', 'onde', 'nota', 'resumo', 'motivo')
ESTADOS_LAMPEJO = ('aberto', 'convertido', 'guardado')


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


# ------------------------------------------------------------------ leitura do formato antigo
def _ler_json(path: Path, padrao, avisos: list[str]):
    """Como `arquivos.ler_json` (ilegível = padrão), mas sem efeitos colaterais: a cópia fiel está no backup."""
    if not path.exists():
        return padrao
    try:
        dados = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        avisos.append(f'{path.name}: ilegível ({type(e).__name__}); ficou só no backup')
        return padrao
    if not isinstance(dados, type(padrao)):
        avisos.append(f'{path.name}: formato inesperado ({type(dados).__name__}); ficou só no backup')
        return padrao
    return dados


def _ler_jsonl(path: Path, avisos: list[str]) -> list[dict]:
    """Como `jogo.livro` e `acoes.eventos`: linha que não é um objeto JSON fica de fora (e é contada).

    Lê bytes e decodifica linha a linha: uma gravação interrompida no meio de um caractere acentuado
    (`ensure_ascii=False`) estraga só aquela linha, nunca o arquivo inteiro.
    """
    if not path.exists():
        return []
    try:
        bruto = path.read_bytes()
    except OSError as e:
        avisos.append(f'{path.name}: ilegível ({type(e).__name__}); ficou só no backup')
        return []
    out, ruins = [], 0
    for linha in bruto.splitlines():
        if not linha.strip():
            continue
        try:
            rec = json.loads(linha.decode('utf-8'))
        except ValueError:  # inclui UnicodeDecodeError
            ruins += 1
            continue
        if isinstance(rec, dict):
            out.append(rec)
        else:
            ruins += 1
    if ruins:
        avisos.append(f'{path.name}: {ruins} linha(s) ilegível(is) ignorada(s), como o jogo já fazia')
    return out


def _int(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _luz(valor, avisos: list[str]) -> str:
    """Regra de `jogo.rota`: só 'propria' conta como luz própria; o resto é refletida (avisando se não era 'refletida')."""
    if valor == 'propria':
        return 'propria'
    if valor != 'refletida':
        avisos.append(f'lúmen com luz desconhecida {valor!r} contado como refletida')
    return 'refletida'


def _lumens(pasta: Path, avisos: list[str]) -> list[dict]:
    out = []
    for r in _ler_jsonl(pasta / 'lumens.jsonl', avisos):
        lm = _int(r.get('lm'))
        if lm is None:  # jogo.rota somaria r['lm'] e quebraria: fica só no backup
            avisos.append(f"lúmen sem valor numérico em {r.get('quando')!r} ignorado")
            continue
        out.append({'quando': r.get('quando') or '', 'prisma': r.get('skill') or '', 'lm': lm,
                    'luz': _luz(r.get('luz'), avisos), 'fonte': r.get('fonte') or '', 'ref': r.get('ref') or ''})
    return out


def _niveis_legado(plan: dict, auto: dict) -> dict[str, int]:
    """O nível atual de cada skill do plano, pela regra de `jogo.niveis`."""
    out = {}
    for s in plan.get('skills', []):
        nivel = auto.get(s['nome'])
        if nivel is None:
            nivel = s.get('autoavaliacao') if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
        out[s['nome']] = int(nivel or 0)
    return out


def _prisma_de(nome: str, plan: dict) -> str:
    """O nome da skill do plano que casa com o nome gravado no feixe (regra de `jogo.skill_de`)."""
    nomes = [s['nome'] for s in plan.get('skills', [])]
    if nome in nomes:
        return nome
    base = (nome or '').lower()
    for n in nomes:
        chave = n.lower().split('(')[0].split('/')[0].strip()
        if chave and (chave in base or base in n.lower()):
            return n
    return nome


def _rotulos(state: dict) -> dict[str, str]:
    """Nomes curtos de onde a pessoa está e aonde quer chegar (regra de `pipeline.rotulos`)."""
    plan = state.get('plano', {})
    tri = (state.get('payload_anonimizado') or {}).get('triagem', {})
    out = {}
    for campo, declarado, padrao in (('onde_esta', 'nivel_atual_declarado', 'hoje'),
                                     ('aonde_quer_chegar', 'objetivo_declarado', 'meta')):
        curto = (plan.get(campo) or {}).get('nivel_curto')
        if not curto:
            m = re.search(r'(J[úu]nior|Plen[oa]|S[êe]nior|Especialista|Tech Lead)(?:\s+n[íi]vel)?\s*(\d)?',
                          tri.get(declarado, ''), re.I)
            curto = ' '.join(x for x in m.groups() if x).strip() if m else padrao
        out[campo] = curto[:1].upper() + curto[1:]
    return out


def _status_antigo(evidencias: list[dict]) -> dict[str, str]:
    """Estado de cada id pelos eventos de evidência (regra de `acoes.status_map`)."""
    st: dict[str, str] = {}
    for e in evidencias:
        if 'id' not in e:
            continue
        atual = st.setdefault(e['id'], 'pendente')
        if e.get('evento') == 'iniciada' and atual != 'feita':
            st[e['id']] = 'em andamento'
        elif e.get('evento') == 'concluida':
            st[e['id']] = 'feita'
    return st


def _avancos_legado(pasta: Path, avisos: list[str]) -> list[dict]:
    """Os feixes do catálogo e as ações guardadas que ainda não tinham entrado nele (como `jogo.sincronizar` faria)."""
    cat = _ler_json(pasta / 'feixes.json', {}, avisos)
    out = [{**f, 'id': f.get('id') or fid} for fid, f in cat.items() if isinstance(f, dict)]
    ids = {f['id'] for f in out}
    status = _status_antigo(_ler_jsonl(pasta / 'evidencias.jsonl', []))
    for a in _ler_json(pasta / 'acoes_guardadas.json', [], avisos):
        if isinstance(a, dict) and a.get('id') and a['id'] not in ids:
            ids.add(a['id'])
            out.append({**a, 'estado': 'em_andamento' if status.get(a['id']) == 'em andamento' else 'sugerido',
                        'criado_em': a.get('guardada_em') or ''})
    return out


def _carregar(pasta: Path) -> dict:
    avisos: list[str] = []
    state = _ler_json(pasta / 'career_state.json', {}, avisos)
    d = {
        'avisos': avisos,
        'state': state,
        'plan': state.get('plano') or {},
        'auto': _ler_json(pasta / 'autoavaliacao.json', {}, avisos),
        'degraus': _ler_json(pasta / 'degraus.json', {}, avisos),
        'avancos': _avancos_legado(pasta, avisos),
        'evidencias': _ler_jsonl(pasta / 'evidencias.jsonl', avisos),
        'lumens': _lumens(pasta, avisos),
        'cartoes': _ler_json(pasta / 'cartoes.json', [], avisos),
        'fila': _ler_json(pasta / 'fila.json', [], avisos),
        'sessao': _ler_jsonl(pasta / 'sessao.jsonl', avisos),
    }
    d['inicio'] = _inicio(d)
    return d


def _inicio(d: dict) -> str:
    """Um segundo antes do dado antigo mais velho: a data do registro 'migrado' (nível de partida).

    O progresso de nível conta os lúmens depois do último registro; com a base antes de tudo, nenhum lúmen antigo
    deixa de contar (no jogo antigo, quem nunca subiu contava o livro inteiro).
    """
    datas = [r['quando'] for r in d['lumens']]
    for f in d['avancos']:
        datas += [f.get('criado_em')] + [h.get('quando') for h in f.get('historico') or [] if isinstance(h, dict)]
    datas += [h.get('quando') for h in d['degraus'].get('historico', []) if isinstance(h, dict)]
    datas += list((d['degraus'].get('desde') or {}).values())
    for fonte in ('evidencias', 'cartoes', 'fila', 'sessao'):
        datas += [x.get('quando') for x in d[fonte] if isinstance(x, dict)]
    datas.append(d['state'].get('atualizado_em'))
    validas = []
    for t in datas:
        try:
            validas.append(datetime.fromisoformat(str(t)).replace(tzinfo=None))  # o jogo grava hora local sem fuso
        except ValueError:
            continue
    if not validas:
        return agora()
    return (min(validas) - timedelta(seconds=1)).isoformat(timespec='seconds')


# ------------------------------------------------------------------ cópia dos originais
def _copiar_originais(pasta: Path) -> Path | None:
    """Copia os arquivos antigos para `migracao-AAAAMMDD/` (a pasta pode já existir de uma tentativa anterior).

    Uma cópia já feita nunca é sobrescrita: se o original mudou desde então, a nova cópia ganha a hora no nome.
    """
    presentes = [pasta / n for n in ARQUIVOS if (pasta / n).is_file()]
    if not presentes:
        return None
    destino = pasta / f'migracao-{datetime.now():%Y%m%d}'
    destino.mkdir(parents=True, exist_ok=True)
    for origem in presentes:
        alvo = destino / origem.name
        if alvo.exists():
            if alvo.read_bytes() == origem.read_bytes():
                continue
            alvo = destino / f'{origem.name}.{datetime.now():%H%M%S%f}'
        shutil.copy2(origem, alvo)
    return destino


# ------------------------------------------------------------------ gravação
def _inserir(con: sqlite3.Connection, tabela: str, linha: dict, cont: dict, chave: bool = False) -> None:
    """INSERT simples (livros e eventos) ou, em tabela com chave natural, `ON CONFLICT DO NOTHING`."""
    colunas = ', '.join(linha)
    marcas = ', '.join('?' for _ in linha)
    sql = f'INSERT INTO {tabela} ({colunas}) VALUES ({marcas})' + (' ON CONFLICT DO NOTHING' if chave else '')
    cont[tabela] += con.execute(sql, tuple(linha.values())).rowcount


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _perfil(con, d: dict, cont: dict) -> None:
    state, auto, degraus = d['state'], d['auto'], d['degraus']
    valores = {}
    if 'plano' in state:
        valores['plano'] = state['plano']
        valores['rotulos'] = _rotulos(state)
    resto = {k: v for k, v in state.items() if k != 'plano'}
    if resto:
        valores['estado_legado'] = resto  # payload anonimizado, custo e fontes da última triagem
    if auto:
        valores['autoavaliacao'] = auto  # inclui skills que não estão no plano
    if 'marcos_dossie' in degraus:
        valores['marcos_dossie'] = degraus['marcos_dossie']
    for chave, valor in valores.items():
        _inserir(con, 'perfil', {'chave': chave, 'valor_json': _json(valor)}, cont, chave=True)


def _prismas(con, d: dict, cont: dict) -> None:
    from .observer import PALAVRAS_PADRAO  # import tardio: o observador importa o jogo
    plan, desde = d['plan'], d['degraus'].get('desde') or {}
    niveis = _niveis_legado(plan, d['auto'])
    foto = []
    for s in plan.get('skills', []):
        nome = s['nome']
        meta = _int(s.get('alvo', 5))
        meta = 5 if meta is None else meta
        palavras = list(dict.fromkeys((s.get('palavras_chave') or []) + PALAVRAS_PADRAO.get(nome, [])))
        _inserir(con, 'prisma', {'nome': nome, 'palavras_json': _json(palavras), 'nivel': niveis[nome], 'meta': meta,
                                 'estado': 'ativo', 'origem': 'triagem', 'ultimo_nivel_em': desde.get(nome) or None,
                                 'criado_em': None}, cont, chave=True)
        foto.append({'nome': nome, 'nivel': niveis[nome], 'meta': meta, 'estado': 'ativo', 'origem': 'triagem',
                     'palavras': palavras})
    if foto:
        _inserir(con, 'trajetoria_versao', {'numero': 1, 'criada_em': d['state'].get('atualizado_em') or agora(),
                                            'origem': 'triagem', 'pedido_id': None,
                                            'foto_json': _json({'prismas': foto})}, cont, chave=True)


def _evento(avanco_id: str, h: dict, fonte: str, omitir: tuple = ()) -> dict:
    """`fonte` separa o histórico do feixe ('historico') das evidências P3/P4 ('evidencias'): a mesma conquista
    aparece nos dois, e quem lê o livro não pode contá-la duas vezes."""
    extra = {'fonte': fonte, **{k: v for k, v in h.items() if k not in COLUNAS_EVENTO and k not in omitir}}
    return {'avanco_id': avanco_id, 'quando': h.get('quando') or '', 'evento': h.get('evento') or '',
            'onde': h.get('onde'), 'nota': _int(h.get('nota')), 'resumo': h.get('resumo'), 'motivo': h.get('motivo'),
            'extra_json': _json(extra)}


def _avancos(con, d: dict, cont: dict) -> None:
    plan = d['plan']
    for f in d['avancos']:
        origem = f.get('origem')
        conta = f.get('conta')
        _inserir(con, 'avanco', {
            'id': f['id'], 'prisma': f.get('skill_plano') or _prisma_de(f.get('skill', ''), plan) or None,
            'tipo': f.get('tipo'), 'titulo': f.get('titulo'),
            'conteudo_json': _json({k: v for k, v in f.items() if k not in ESTADO_FEIXE}),
            'duracao_min': _int(f.get('duracao_min')), 'valor_lm': _int(f.get('valor_lm')),
            'conta_json': _json(conta) if conta is not None else None,
            'origem': ORIGEM_AVANCO.get(origem, origem), 'entrega_id': None, 'dimensao': f.get('dimensao'),
            'estado': f.get('estado') or 'sugerido', 'nota': _int(f.get('nota')),
            'lm_ganho': _int(f.get('lm_ganho')) or 0, 'tentativas': _int(f.get('tentativas')) or 0,
            'revisitas': _int(f.get('revisitas')) or 0, 'revisita_aberta': 1 if f.get('revisita_aberta') else 0,
            'criado_em': f.get('criado_em') or '',
        }, cont, chave=True)
        for h in f.get('historico') or []:
            if isinstance(h, dict):
                _inserir(con, 'avanco_evento', _evento(f['id'], h, 'historico'), cont)
    for e in d['evidencias']:  # eventos P3/P4 de acoes.py; o id pode não estar no catálogo (cartão)
        if e.get('id'):
            _inserir(con, 'avanco_evento', _evento(str(e['id']), e, 'evidencias', omitir=('id',)), cont)


def _lumens_grava(con, d: dict, cont: dict) -> None:
    for r in d['lumens']:
        _inserir(con, 'lumen', r, cont)


def _niveis(con, d: dict, cont: dict) -> None:
    """Livro de níveis: base 'migrado', subidas 'conquistado' e nível declarado depois 'declarado'."""
    degraus = d['degraus']
    base = degraus.get('base') or {}
    historico = [h for h in degraus.get('historico') or [] if isinstance(h, dict) and h.get('skill')]
    atuais = {k: _int(v) for k, v in d['auto'].items()}
    atuais.update(_niveis_legado(d['plan'], d['auto']))
    nomes = list(dict.fromkeys([s['nome'] for s in d['plan'].get('skills', [])] + list(base)
                               + [h['skill'] for h in historico]))
    for nome in nomes:
        atual = atuais.get(nome)
        anterior, quando = None, d['inicio']
        partida = _int(base[nome]) if nome in base else atual
        if partida is not None:
            _inserir(con, 'nivel_registro', {'prisma': nome, 'de': None, 'para': partida, 'quando': quando,
                                             'origem': 'migrado', 'lm': None, 'luz_propria': None}, cont)
            anterior = partida
        for h in sorted((h for h in historico if h['skill'] == nome), key=lambda h: str(h.get('quando') or '')):
            para = _int(h.get('para'))
            if para is None:
                d['avisos'].append(f'subida de nível sem destino em {h.get("quando")!r} ficou só no backup')
                continue
            # jogo.subir sempre sobe um nível (nivel + 1): se o anterior não é para − 1, a pessoa declarou um nível
            # no painel entre as subidas. Essa declaração (sem data) entra antes, na data do registro anterior.
            if anterior is not None and anterior != para - 1:
                _inserir(con, 'nivel_registro', {'prisma': nome, 'de': anterior, 'para': para - 1, 'quando': quando,
                                                 'origem': 'declarado', 'lm': None, 'luz_propria': None}, cont)
            quando = h.get('quando') or quando
            # luz_propria: percentual 0–100, como jogo.progresso_skill sempre gravou.
            _inserir(con, 'nivel_registro', {'prisma': nome, 'de': para - 1, 'para': para, 'quando': quando,
                                             'origem': 'conquistado', 'lm': _int(h.get('lm')),
                                             'luz_propria': h.get('luz_propria')}, cont)
            anterior = para
        if atual is not None and anterior is not None and atual != anterior:
            # Declarado no painel depois da última subida, sem data: fica na data do registro anterior, para não
            # zerar o progresso que o jogo antigo continuava contando.
            _inserir(con, 'nivel_registro', {'prisma': nome, 'de': anterior, 'para': atual, 'quando': quando,
                                             'origem': 'declarado', 'lm': None, 'luz_propria': None}, cont)


def _lampejos(con, d: dict, cont: dict) -> None:
    for c in d['cartoes']:
        if not isinstance(c, dict):
            continue
        estado = c.get('estado') or 'aberto'
        if estado not in ESTADOS_LAMPEJO:
            d['avisos'].append(f'cartão com estado {estado!r} migrado como guardado')
            estado = 'guardado'
        _inserir(con, 'lampejo', {'prisma': c.get('skill') or '', 'sessao': c.get('sessao'),
                                  'quando': c.get('quando') or '', 'estado': estado, 'usado_em': c.get('usado_em')}, cont)


def _fila(con, d: dict, cont: dict) -> None:
    for item in d['fila']:
        if isinstance(item, dict) and item.get('id'):
            _inserir(con, 'fila', {'avanco_id': item['id'], 'titulo': item.get('titulo'), 'quando': item.get('quando') or '',
                                   'oferecida_json': _json(item.get('oferecida_em') or [])}, cont, chave=True)


def _sessao(con, d: dict, cont: dict) -> None:
    for e in d['sessao']:
        interveio = e.get('interveio')
        _inserir(con, 'sessao_evento', {'quando': e.get('quando') or '', 'sessao': e.get('sessao'), 'prisma': e.get('skill'),
                                        'extensao': e.get('extensao'), 'ferramenta': e.get('ferramenta'),
                                        'modo': e.get('modo'), 'lm': _int(e.get('lm')), 'luz': e.get('luz'),
                                        'interveio': None if interveio is None else int(bool(interveio))}, cont)


# ------------------------------------------------------------------ entrada
def _ja_migrado(con: sqlite3.Connection) -> bool:
    """Só a marca desta migração conta (`banco.garantir` confere `migrado_em` por conta própria)."""
    return con.execute("SELECT 1 FROM meta WHERE chave = 'migracao'").fetchone() is not None


def migrar(con: sqlite3.Connection, pasta: Path | None = None) -> dict:
    """Importa os JSON antigos de `pasta` (padrão: `arquivos.PRIVATE`) e devolve as linhas inseridas por tabela."""
    if con.in_transaction:  # chamada por banco.garantir, dentro do BEGIN EXCLUSIVE dele
        return _migrar(con, pasta)
    with banco.transacao(con, 'EXCLUSIVE'):
        return _migrar(con, pasta)


def _migrar(con: sqlite3.Connection, pasta: Path | None) -> dict:
    cont = {t: 0 for t in TABELAS}
    if _ja_migrado(con):
        return cont
    pasta = Path(pasta) if pasta is not None else Path(arquivos.PRIVATE)
    copia = _copiar_originais(pasta)  # antes de ler qualquer coisa
    d = _carregar(pasta)
    _perfil(con, d, cont)
    _prismas(con, d, cont)
    _avancos(con, d, cont)
    _lumens_grava(con, d, cont)
    _niveis(con, d, cont)
    _lampejos(con, d, cont)
    _fila(con, d, cont)
    _sessao(con, d, cont)
    con.execute("INSERT INTO meta (chave, valor) VALUES ('migracao', ?)",
                (_json({'em': agora(), 'copia': copia.name if copia else None, 'contagens': cont,
                        'avisos': d['avisos']}),))
    return cont


# ------------------------------------------------------------------ conferência (antes × depois)
def _bruto_json(path: Path, padrao):
    try:
        dados = json.loads(path.read_bytes().decode('utf-8'))
    except (OSError, ValueError):
        return padrao
    return dados if isinstance(dados, type(padrao)) else padrao


def _bruto_jsonl(path: Path) -> list[dict]:
    try:
        linhas = path.read_bytes().splitlines()
    except OSError:
        return []
    out = []
    for linha in linhas:
        try:
            rec = json.loads(linha.decode('utf-8'))
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def totais_json(pasta: Path) -> dict:
    """Totais lidos direto dos arquivos antigos, pelas regras do jogo antigo.

    Não usa os leitores nem as normalizações da migração: é a conferência independente do que ela gravou.
    """
    pasta = Path(pasta)
    lumens = []
    for r in _bruto_jsonl(pasta / 'lumens.jsonl'):  # jogo.livro + soma de jogo.rota
        try:
            lumens.append((int(r['lm']), r.get('luz')))
        except (KeyError, TypeError, ValueError):
            continue
    cat = _bruto_json(pasta / 'feixes.json', {})
    estados = Counter(f.get('estado') or 'sugerido' for f in cat.values() if isinstance(f, dict))
    iniciadas, concluidas = set(), set()  # acoes.status_map → jogo.sincronizar, para as guardadas fora do catálogo
    for e in _bruto_jsonl(pasta / 'evidencias.jsonl'):
        if e.get('evento') == 'iniciada':
            iniciadas.add(e.get('id'))
        elif e.get('evento') == 'concluida':
            concluidas.add(e.get('id'))
    vistas = set(cat)
    for a in _bruto_json(pasta / 'acoes_guardadas.json', []):
        if isinstance(a, dict) and a.get('id') and a['id'] not in vistas:
            vistas.add(a['id'])
            estados['em_andamento' if a['id'] in iniciadas - concluidas else 'sugerido'] += 1
    plano = _bruto_json(pasta / 'career_state.json', {}).get('plano') or {}
    auto = _bruto_json(pasta / 'autoavaliacao.json', {})
    niveis = {}
    for s in plano.get('skills', []):  # jogo.niveis
        nivel = auto.get(s['nome'])
        if nivel is None:
            nivel = s['autoavaliacao'] if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
        niveis[s['nome']] = int(nivel or 0)
    return {
        'lumens_total': sum(lm for lm, _ in lumens),
        'lumens_propria': sum(lm for lm, luz in lumens if luz == 'propria'),
        'avancos_por_estado': dict(estados),
        'niveis': niveis,
    }


def totais_banco(con: sqlite3.Connection) -> dict:
    """Os mesmos totais, lidos do banco; o nível de cada prisma vem do livro (último registro por quando, id)."""
    total, propria = con.execute(
        "SELECT COALESCE(SUM(lm), 0), COALESCE(SUM(CASE WHEN luz = 'propria' THEN lm END), 0) FROM lumen").fetchone()
    niveis = con.execute('SELECT p.nome, (SELECT r.para FROM nivel_registro r WHERE r.prisma = p.nome '
                         'ORDER BY r.quando DESC, r.id DESC LIMIT 1) FROM prisma p')
    return {
        'lumens_total': total,
        'lumens_propria': propria,
        'avancos_por_estado': {e: n for e, n in con.execute('SELECT estado, COUNT(*) FROM avanco GROUP BY estado')},
        'niveis': {n: v for n, v in niveis},
    }
