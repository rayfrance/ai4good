"""Migração única dos JSON antigos de `private/` para o banco (`luzia.db`), sem perder nem duplicar nada.

`banco.garantir` chama `migrar(con)` uma única vez, já dentro de uma transação `BEGIN EXCLUSIVE`: aí esta função só
executa comandos na conexão recebida (não abre, não confirma, não desfaz). Chamada solta (testes, conferência),
abre a própria transação exclusiva. Um erro inesperado desfaz tudo: nenhuma linha migrada e nenhuma marca.

Dado antigo fora do formato nunca derruba a migração: o registro ruim é pulado (ou o valor ruim vira nulo) e o
aviso vai para `meta('migracao').avisos` (só arquivo, campo e tipo, nunca o conteúdo); o original fica no backup.
Só valores simples (texto, número, nulo) vão para colunas; listas e objetos vão para as colunas `*_json`.

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

import hashlib
import json
import re
import shutil
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

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
# Onde guardar um valor que não cabe na coluna (lista ou objeto): no JSON da própria linha, quando ela tem um.
SOBRA = {'avanco': 'conteudo_json', 'avanco_evento': 'extra_json'}
# Colunas NOT NULL de texto: um valor que não cabe vira '' (como um campo ausente no arquivo antigo).
TEXTO_OBRIGATORIO = {'lumen': ('quando', 'prisma', 'fonte', 'ref'), 'lampejo': ('prisma', 'quando'),
                     'avanco': ('criado_em',), 'avanco_evento': ('quando', 'evento'), 'fila': ('quando',),
                     'sessao_evento': ('quando',), 'nivel_registro': ('quando',), 'trajetoria_versao': ('criada_em',)}
# Formato inesperado num registro: pula o registro e avisa. Erros do banco (trava, disco) não estão aqui: esses sobem.
# ProgrammingError/InterfaceError também não: são defeito do código e precisam falhar alto, nunca virar aviso.
RUINS = (TypeError, ValueError, KeyError, AttributeError, IndexError, OverflowError, sqlite3.IntegrityError)
INT_MAX = 2 ** 63 - 1


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def versao() -> str:
    """Hash do código desta migração: `banco.garantir` só tenta de novo uma migração que falhou se ele mudar."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


# ------------------------------------------------------------------ valores fora do formato
def _escalar(valor) -> bool:
    return valor is None or isinstance(valor, (str, int, float))


def _int(valor) -> int | None:
    if isinstance(valor, bool):
        return int(valor)
    try:
        n = int(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if -INT_MAX <= n <= INT_MAX else None


def _texto(valor) -> str | None:
    """Texto (ou None); número vira texto; lista ou objeto vira None."""
    if valor is None or isinstance(valor, str):
        return valor
    if isinstance(valor, (int, float)):
        return str(valor)
    return None


def _so_dicts(valor, onde: str, avisos: list[str]) -> list[dict]:
    """A lista de objetos de um arquivo antigo; o que não é objeto fica de fora (e é contado)."""
    if not isinstance(valor, list):
        if valor not in (None, {}, []):
            avisos.append(f'{onde}: esperava uma lista ({type(valor).__name__}); ficou só no backup')
        return []
    bons = [x for x in valor if isinstance(x, dict)]
    if len(bons) != len(valor):
        avisos.append(f'{onde}: {len(valor) - len(bons)} item(ns) fora do formato ignorado(s)')
    return bons


def _so_dict(valor, onde: str, avisos: list[str]) -> dict:
    if isinstance(valor, dict):
        return valor
    if valor not in (None, [], {}):
        avisos.append(f'{onde}: esperava um objeto ({type(valor).__name__}); ficou só no backup')
    return {}


@contextmanager
def _registro(d: dict, onde: str) -> Iterator[None]:
    """Um registro antigo de formato inesperado é pulado com aviso; o resto da migração segue."""
    try:
        yield
    except RUINS as e:
        d['avisos'].append(f'{onde}: registro fora do formato ({type(e).__name__}) ficou só no backup')


# ------------------------------------------------------------------ leitura do formato antigo
def _ler_json(path: Path, padrao, avisos: list[str]):
    """Como `arquivos.ler_json` (ilegível = padrão), mas sem efeitos colaterais: a cópia fiel está no backup."""
    if not path.exists():
        return padrao
    try:
        dados = json.loads(path.read_bytes().decode('utf-8'))
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


def _luz(valor, avisos: list[str]) -> str:
    """Regra de `jogo.rota`: só 'propria' conta como luz própria; o resto é refletida (avisando se não era 'refletida')."""
    if valor == 'propria':
        return 'propria'
    if valor != 'refletida':
        avisos.append(f'lúmen com luz desconhecida ({type(valor).__name__}) contado como refletida')
    return 'refletida'


def _lumens(pasta: Path, avisos: list[str]) -> list[dict]:
    out = []
    for r in _ler_jsonl(pasta / 'lumens.jsonl', avisos):
        lm = _int(r.get('lm'))
        if lm is None:  # jogo.rota somaria r['lm'] e quebraria: fica só no backup
            avisos.append('lumens.jsonl: lúmen sem valor numérico ignorado')
            continue
        out.append({'quando': r.get('quando') or '', 'prisma': r.get('skill') or '', 'lm': lm,
                    'luz': _luz(r.get('luz'), avisos), 'fonte': r.get('fonte') or '', 'ref': r.get('ref') or ''})
    return out


def _skills(plan: dict, avisos: list[str]) -> list[dict]:
    """As skills do plano com nome de texto; as outras ficam só no perfil('plano') e no backup."""
    skills = _so_dicts(plan.get('skills', []), 'career_state.json plano.skills', avisos)
    bons = [s for s in skills if isinstance(s.get('nome'), str) and s['nome'].strip()]
    if len(bons) != len(skills):
        avisos.append(f'career_state.json plano.skills: {len(skills) - len(bons)} skill(s) sem nome ignorada(s)')
    return bons


def _niveis_legado(skills: list[dict], auto: dict, avisos: list[str] | None = None) -> dict[str, int]:
    """O nível atual de cada skill do plano, pela regra de `jogo.niveis` (valor declarado que não é número: ignorado)."""
    out = {}
    for s in skills:
        nivel = _int(auto.get(s['nome'])) if auto.get(s['nome']) is not None else None
        if nivel is None and auto.get(s['nome']) is not None and avisos is not None:
            avisos.append('autoavaliacao.json: nível declarado que não é número ignorado (vale o do plano)')
        if nivel is None:
            nivel = s.get('autoavaliacao') if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
        out[s['nome']] = _int(nivel or 0) or 0
    return out


def _prisma_de(nome, skills: list[dict]) -> str | None:
    """O nome da skill do plano que casa com o nome gravado no feixe (regra de `jogo.skill_de`)."""
    if not isinstance(nome, str):
        return None
    nomes = [s['nome'] for s in skills]
    if nome in nomes:
        return nome
    base = nome.lower()
    for n in nomes:
        chave = n.lower().split('(')[0].split('/')[0].strip()
        if chave and (chave in base or base in n.lower()):
            return n
    return nome


def _rotulos(state: dict, plan: dict) -> dict[str, str]:
    """Nomes curtos de onde a pessoa está e aonde quer chegar (regra de `pipeline.rotulos`)."""
    payload = state.get('payload_anonimizado')
    tri = payload.get('triagem') if isinstance(payload, dict) else None
    tri = tri if isinstance(tri, dict) else {}
    out = {}
    for campo, declarado, padrao in (('onde_esta', 'nivel_atual_declarado', 'hoje'),
                                     ('aonde_quer_chegar', 'objetivo_declarado', 'meta')):
        bloco = plan.get(campo)
        curto = bloco.get('nivel_curto') if isinstance(bloco, dict) else None
        if not isinstance(curto, str) or not curto:
            texto = tri.get(declarado, '')
            m = re.search(r'(J[úu]nior|Plen[oa]|S[êe]nior|Especialista|Tech Lead)(?:\s+n[íi]vel)?\s*(\d)?',
                          texto if isinstance(texto, str) else '', re.I)
            curto = ' '.join(x for x in m.groups() if x).strip() if m else padrao
        out[campo] = curto[:1].upper() + curto[1:]
    return out


def _id(valor) -> str | None:
    """Id de feixe ou evento: texto (número vira texto); lista ou objeto não serve."""
    if isinstance(valor, bool):
        return None
    texto = _texto(valor)
    return texto if texto else None


def _status_antigo(evidencias: list[dict]) -> dict[str, str]:
    """Estado de cada id pelos eventos de evidência (regra de `acoes.status_map`)."""
    st: dict[str, str] = {}
    for e in evidencias:
        eid = _id(e.get('id'))
        if eid is None:
            continue
        atual = st.setdefault(eid, 'pendente')
        if e.get('evento') == 'iniciada' and atual != 'feita':
            st[eid] = 'em andamento'
        elif e.get('evento') == 'concluida':
            st[eid] = 'feita'
    return st


def _avancos_legado(pasta: Path, avisos: list[str]) -> list[dict]:
    """Os feixes do catálogo e as ações guardadas que ainda não tinham entrado nele (como `jogo.sincronizar` faria)."""
    cat = _ler_json(pasta / 'feixes.json', {}, avisos)
    out, ids, ruins = [], set(), 0
    for fid, f in cat.items():
        if not isinstance(f, dict):
            ruins += 1
            continue
        fid = _id(f.get('id')) or fid
        if fid in ids:
            ruins += 1
            continue
        ids.add(fid)
        out.append({**f, 'id': fid})
    status = _status_antigo(_ler_jsonl(pasta / 'evidencias.jsonl', []))
    for a in _so_dicts(_ler_json(pasta / 'acoes_guardadas.json', [], avisos), 'acoes_guardadas.json', avisos):
        aid = _id(a.get('id'))
        if aid is None:
            ruins += 1
        elif aid not in ids:
            ids.add(aid)
            out.append({**a, 'id': aid, 'estado': 'em_andamento' if status.get(aid) == 'em andamento' else 'sugerido',
                        'criado_em': a.get('guardada_em') or ''})
    if ruins:
        avisos.append(f'feixes.json/acoes_guardadas.json: {ruins} feixe(s) fora do formato ou repetido(s) ignorado(s)')
    return out


def _carregar(pasta: Path) -> dict:
    """Lê os arquivos antigos e já devolve cada parte no tipo esperado (o resto fica só no backup)."""
    avisos: list[str] = []
    state = _ler_json(pasta / 'career_state.json', {}, avisos)
    plan = _so_dict(state.get('plano'), 'career_state.json plano', avisos)
    degraus = _ler_json(pasta / 'degraus.json', {}, avisos)
    d = {
        'avisos': avisos,
        'state': state,
        'plan': plan,
        'skills': _skills(plan, avisos),
        'auto': _ler_json(pasta / 'autoavaliacao.json', {}, avisos),
        'degraus': degraus,
        'base': _so_dict(degraus.get('base'), 'degraus.json base', avisos),
        'desde': _so_dict(degraus.get('desde'), 'degraus.json desde', avisos),
        'subidas': [h for h in _so_dicts(degraus.get('historico', []), 'degraus.json historico', avisos)],
        'avancos': _avancos_legado(pasta, avisos),
        'evidencias': _ler_jsonl(pasta / 'evidencias.jsonl', avisos),
        'lumens': _lumens(pasta, avisos),
        'cartoes': _so_dicts(_ler_json(pasta / 'cartoes.json', [], avisos), 'cartoes.json', avisos),
        'fila': _so_dicts(_ler_json(pasta / 'fila.json', [], avisos), 'fila.json', avisos),
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
        historico = f.get('historico') if isinstance(f.get('historico'), list) else []
        datas += [f.get('criado_em')] + [h.get('quando') for h in historico if isinstance(h, dict)]
    datas += [h.get('quando') for h in d['subidas']] + list(d['desde'].values())
    for fonte in ('evidencias', 'cartoes', 'fila', 'sessao'):
        datas += [x.get('quando') for x in d[fonte]]
    datas.append(d['state'].get('atualizado_em'))
    validas = []
    for t in datas:
        if not isinstance(t, str):
            continue
        try:
            validas.append(datetime.fromisoformat(t).replace(tzinfo=None))  # o jogo grava hora local sem fuso
        except ValueError:
            continue
    if not validas:
        return agora()
    menor = min(validas)
    return (menor - timedelta(seconds=1) if menor > datetime.min + timedelta(seconds=1) else menor).isoformat(
        timespec='seconds')


# ------------------------------------------------------------------ cópia dos originais
def _copiar_originais(pasta: Path) -> Path | None:
    """Copia os arquivos antigos para `migracao-AAAAMMDD/` (uma pasta por dia; pode já existir de uma tentativa).

    Uma cópia já feita nunca é sobrescrita nem repetida: igual em bytes, fica como está; se o original mudou desde
    então, a nova versão ganha a hora no nome.
    """
    presentes = [pasta / n for n in ARQUIVOS if (pasta / n).is_file()]
    if not presentes:
        return None
    destino = pasta / f'migracao-{datetime.now():%Y%m%d}'
    destino.mkdir(parents=True, exist_ok=True)
    for origem in presentes:
        conteudo = origem.read_bytes()
        copias = [destino / origem.name, *destino.glob(f'{origem.name}.*')]
        if any(c.is_file() and c.read_bytes() == conteudo for c in copias):
            continue
        alvo = destino / origem.name
        if alvo.exists():
            alvo = destino / f'{origem.name}.{datetime.now():%H%M%S%f}'
        shutil.copy2(origem, alvo)
    return destino


# ------------------------------------------------------------------ gravação
def _inserir(con: sqlite3.Connection, tabela: str, linha: dict, cont: dict, d: dict, chave: bool = False) -> None:
    """INSERT simples (livros e eventos) ou, em tabela com chave natural, `ON CONFLICT DO NOTHING`.

    Só valores simples vão para as colunas: lista ou objeto vira nulo (ou '' numa coluna de texto obrigatória),
    com aviso, e o valor original vai para o JSON da linha quando ela tem um (`SOBRA`).
    """
    linha = dict(linha)
    fora = {c: v for c, v in linha.items() if not _escalar(v)}
    if fora:
        d['avisos'].append(f'{tabela}: {", ".join(sorted(fora))} fora do formato virou nulo (original no backup)')
        for c in fora:
            linha[c] = None
        coluna = SOBRA.get(tabela)
        if coluna and coluna not in fora:
            atual = json.loads(linha[coluna]) if isinstance(linha.get(coluna), str) else {}
            linha[coluna] = _json({**atual, '_fora_do_formato': fora})
    for c in TEXTO_OBRIGATORIO.get(tabela, ()):
        if c in linha and linha[c] is None:
            linha[c] = ''
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
        valores['rotulos'] = _rotulos(state, d['plan'])
    resto = {k: v for k, v in state.items() if k != 'plano'}
    if resto:
        valores['estado_legado'] = resto  # payload anonimizado, custo e fontes da última triagem
    if auto:
        valores['autoavaliacao'] = auto  # inclui skills que não estão no plano
    if 'marcos_dossie' in degraus:
        valores['marcos_dossie'] = degraus['marcos_dossie']
    for chave, valor in valores.items():
        with _registro(d, f'perfil {chave}'):
            _inserir(con, 'perfil', {'chave': chave, 'valor_json': _json(valor)}, cont, d, chave=True)


def _palavras(s: dict, padrao: list[str], avisos: list[str]) -> list[str]:
    bruto = s.get('palavras_chave')
    if isinstance(bruto, str):
        bruto = [bruto]
    elif not isinstance(bruto, list):
        if bruto is not None:
            avisos.append('career_state.json: palavras_chave fora do formato ignoradas')
        bruto = []
    proprias = [p for p in bruto if isinstance(p, str)]
    if len(proprias) != len(bruto):
        avisos.append('career_state.json: palavra-chave que não é texto ignorada')
    return list(dict.fromkeys(proprias + list(padrao)))


def _prismas(con, d: dict, cont: dict) -> None:
    from .observer import PALAVRAS_PADRAO  # import tardio: o observador importa o jogo
    niveis = _niveis_legado(d['skills'], d['auto'], d['avisos'])
    foto = []
    for s in d['skills']:
        nome = s['nome']
        with _registro(d, 'career_state.json skill'):
            meta = _int(s.get('alvo', 5))
            meta = 5 if meta is None else meta
            palavras = _palavras(s, PALAVRAS_PADRAO.get(nome, []), d['avisos'])
            _inserir(con, 'prisma', {'nome': nome, 'palavras_json': _json(palavras), 'nivel': niveis[nome], 'meta': meta,
                                     'estado': 'ativo', 'origem': 'triagem',
                                     'ultimo_nivel_em': d['desde'].get(nome) or None, 'criado_em': None}, cont, d,
                     chave=True)
            foto.append({'nome': nome, 'nivel': niveis[nome], 'meta': meta, 'estado': 'ativo', 'origem': 'triagem',
                         'palavras': palavras})
    if foto:
        with _registro(d, 'trajetoria_versao'):
            _inserir(con, 'trajetoria_versao', {'numero': 1, 'criada_em': _texto(d['state'].get('atualizado_em')) or agora(),
                                                'origem': 'triagem', 'pedido_id': None,
                                                'foto_json': _json({'prismas': foto})}, cont, d, chave=True)


def _evento(avanco_id: str, h: dict, fonte: str, omitir: tuple = ()) -> dict:
    """`fonte` separa o histórico do feixe ('historico') das evidências P3/P4 ('evidencias'): a mesma conquista
    aparece nos dois, e quem lê o livro não pode contá-la duas vezes."""
    extra = {'fonte': fonte, **{k: v for k, v in h.items() if k not in COLUNAS_EVENTO and k not in omitir}}
    return {'avanco_id': avanco_id, 'quando': h.get('quando') or '', 'evento': h.get('evento') or '',
            'onde': h.get('onde'), 'nota': _int(h.get('nota')), 'resumo': h.get('resumo'), 'motivo': h.get('motivo'),
            'extra_json': _json(extra)}


def _avancos(con, d: dict, cont: dict) -> None:
    for f in d['avancos']:
        with _registro(d, 'feixes.json feixe'):
            origem = f.get('origem')
            conta = f.get('conta')
            estado = f.get('estado') if isinstance(f.get('estado'), str) and f.get('estado') else 'sugerido'
            _inserir(con, 'avanco', {
                'id': f['id'], 'prisma': f.get('skill_plano') or _prisma_de(f.get('skill', ''), d['skills']) or None,
                'tipo': f.get('tipo'), 'titulo': f.get('titulo'),
                'conteudo_json': _json({k: v for k, v in f.items() if k not in ESTADO_FEIXE}),
                'duracao_min': _int(f.get('duracao_min')), 'valor_lm': _int(f.get('valor_lm')),
                'conta_json': _json(conta) if conta is not None else None,
                'origem': ORIGEM_AVANCO.get(origem, origem) if isinstance(origem, str) else origem,
                'entrega_id': None, 'dimensao': f.get('dimensao'), 'estado': estado, 'nota': _int(f.get('nota')),
                'lm_ganho': _int(f.get('lm_ganho')) or 0, 'tentativas': _int(f.get('tentativas')) or 0,
                'revisitas': _int(f.get('revisitas')) or 0, 'revisita_aberta': 1 if f.get('revisita_aberta') else 0,
                'criado_em': f.get('criado_em') or '',
            }, cont, d, chave=True)
        historico = f.get('historico')
        if historico is not None and not isinstance(historico, list):
            d['avisos'].append('feixes.json: histórico fora do formato ficou só no backup')
            historico = []
        for h in historico or []:
            if isinstance(h, dict):
                with _registro(d, 'feixes.json histórico'):
                    _inserir(con, 'avanco_evento', _evento(f['id'], h, 'historico'), cont, d)
    for e in d['evidencias']:  # eventos P3/P4 de acoes.py; o id pode não estar no catálogo (cartão)
        eid = _id(e.get('id'))
        if eid is None:
            d['avisos'].append('evidencias.jsonl: evento sem id ignorado')
            continue
        with _registro(d, 'evidencias.jsonl'):
            _inserir(con, 'avanco_evento', _evento(eid, e, 'evidencias', omitir=('id',)), cont, d)


def _lumens_grava(con, d: dict, cont: dict) -> None:
    for r in d['lumens']:
        with _registro(d, 'lumens.jsonl'):
            _inserir(con, 'lumen', r, cont, d)


def _niveis(con, d: dict, cont: dict) -> None:
    """Livro de níveis: base 'migrado', subidas 'conquistado' e nível declarado depois 'declarado'."""
    base = d['base']
    subidas = [h for h in d['subidas'] if isinstance(h.get('skill'), str) and h['skill']]
    if len(subidas) != len(d['subidas']):
        d['avisos'].append('degraus.json: subida sem skill ficou só no backup')
    atuais = {k: _int(v) for k, v in d['auto'].items()}
    atuais.update(_niveis_legado(d['skills'], d['auto']))
    nomes = list(dict.fromkeys([s['nome'] for s in d['skills']] + list(base) + [h['skill'] for h in subidas]))
    for nome in nomes:
        with _registro(d, 'degraus.json'):
            _niveis_de(con, d, cont, nome, atuais.get(nome), subidas)


def _niveis_de(con, d: dict, cont: dict, nome: str, atual: int | None, subidas: list[dict]) -> None:
    anterior, quando = None, d['inicio']
    if nome in d['base']:
        partida = _int(d['base'][nome])
        if partida is None:
            d['avisos'].append('degraus.json: base que não é número ignorada')
            partida = atual
    else:
        partida = atual
    if partida is not None:
        _inserir(con, 'nivel_registro', {'prisma': nome, 'de': None, 'para': partida, 'quando': quando,
                                         'origem': 'migrado', 'lm': None, 'luz_propria': None}, cont, d)
        anterior = partida
    for h in sorted((h for h in subidas if h['skill'] == nome), key=lambda h: str(h.get('quando') or '')):
        para = _int(h.get('para'))
        if para is None:
            d['avisos'].append('degraus.json: subida de nível sem destino ficou só no backup')
            continue
        # jogo.subir sempre sobe um nível (nivel + 1): se o anterior não é para − 1, a pessoa declarou um nível
        # no painel entre as subidas. Essa declaração (sem data) entra antes, na data do registro anterior.
        if anterior is not None and anterior != para - 1:
            _inserir(con, 'nivel_registro', {'prisma': nome, 'de': anterior, 'para': para - 1, 'quando': quando,
                                             'origem': 'declarado', 'lm': None, 'luz_propria': None}, cont, d)
        quando = _texto(h.get('quando')) or quando
        luz = h.get('luz_propria')
        # luz_propria: percentual 0–100, como jogo.progresso_skill sempre gravou.
        _inserir(con, 'nivel_registro', {'prisma': nome, 'de': para - 1, 'para': para, 'quando': quando,
                                         'origem': 'conquistado', 'lm': _int(h.get('lm')),
                                         'luz_propria': luz if isinstance(luz, (int, float)) else None}, cont, d)
        anterior = para
    if atual is not None and anterior is not None and atual != anterior:
        # Declarado no painel depois da última subida, sem data: fica na data do registro anterior, para não
        # zerar o progresso que o jogo antigo continuava contando.
        _inserir(con, 'nivel_registro', {'prisma': nome, 'de': anterior, 'para': atual, 'quando': quando,
                                         'origem': 'declarado', 'lm': None, 'luz_propria': None}, cont, d)


def _lampejos(con, d: dict, cont: dict) -> None:
    for c in d['cartoes']:
        with _registro(d, 'cartoes.json'):
            estado = c.get('estado') or 'aberto'
            if estado not in ESTADOS_LAMPEJO:
                d['avisos'].append('cartoes.json: cartão com estado desconhecido migrado como guardado')
                estado = 'guardado'
            _inserir(con, 'lampejo', {'prisma': c.get('skill') or '', 'sessao': c.get('sessao'),
                                      'quando': c.get('quando') or '', 'estado': estado,
                                      'usado_em': c.get('usado_em')}, cont, d)


def _fila(con, d: dict, cont: dict) -> None:
    for item in d['fila']:
        fid = _id(item.get('id'))
        if fid is None:
            d['avisos'].append('fila.json: item sem id ignorado')
            continue
        with _registro(d, 'fila.json'):
            oferecida = item.get('oferecida_em') or []
            _inserir(con, 'fila', {'avanco_id': fid, 'titulo': item.get('titulo'), 'quando': item.get('quando') or '',
                                   'oferecida_json': _json(oferecida if isinstance(oferecida, list) else [oferecida])},
                     cont, d, chave=True)


def _sessao(con, d: dict, cont: dict) -> None:
    for e in d['sessao']:
        with _registro(d, 'sessao.jsonl'):
            interveio = e.get('interveio')
            _inserir(con, 'sessao_evento', {'quando': e.get('quando') or '', 'sessao': e.get('sessao'),
                                            'prisma': e.get('skill'), 'extensao': e.get('extensao'),
                                            'ferramenta': e.get('ferramenta'), 'modo': e.get('modo'),
                                            'lm': _int(e.get('lm')), 'luz': e.get('luz'),
                                            'interveio': None if interveio is None else int(bool(interveio))}, cont, d)


# ------------------------------------------------------------------ entrada
def _ja_migrado(con: sqlite3.Connection) -> bool:
    """Só a marca desta migração conta (`banco.garantir` confere `migrado_em` por conta própria)."""
    return con.execute("SELECT 1 FROM meta WHERE chave = 'migracao'").fetchone() is not None


def migrar(con: sqlite3.Connection, pasta: Path | None = None) -> dict:
    """Importa os JSON antigos de `pasta` (padrão: `arquivos.PRIVATE`) e devolve as linhas inseridas por tabela."""
    if con.in_transaction:  # chamada por banco.garantir, dentro do BEGIN EXCLUSIVE dele
        return _migrar(con, pasta)
    with banco.transacao(con, 'EXCLUSIVE', absorver=False):
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
                (_json({'em': agora(), 'versao': versao(), 'copia': copia.name if copia else None,
                        'contagens': cont, 'avisos': d['avisos']}),))
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


def _bruto_int(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError, OverflowError):
        return None


def totais_json(pasta: Path) -> dict:
    """Totais lidos direto dos arquivos antigos, pelas regras do jogo antigo.

    Não usa os leitores nem as normalizações da migração: é a conferência independente do que ela gravou.
    Onde o jogo antigo quebraria (valor que não é número), o registro fica de fora, como na migração.
    """
    pasta = Path(pasta)
    lumens = []
    for r in _bruto_jsonl(pasta / 'lumens.jsonl'):  # jogo.livro + soma de jogo.rota
        lm = _bruto_int(r.get('lm'))
        if lm is not None:
            lumens.append((lm, r.get('luz')))
    cat = _bruto_json(pasta / 'feixes.json', {})
    feixes = [f for f in cat.values() if isinstance(f, dict)]
    estados = Counter(f['estado'] if isinstance(f.get('estado'), str) and f['estado'] else 'sugerido' for f in feixes)
    iniciadas, concluidas = set(), set()  # acoes.status_map → jogo.sincronizar, para as guardadas fora do catálogo
    for e in _bruto_jsonl(pasta / 'evidencias.jsonl'):
        if not isinstance(e.get('id'), (str, int)):
            continue
        if e.get('evento') == 'iniciada':
            iniciadas.add(str(e['id']))
        elif e.get('evento') == 'concluida':
            concluidas.add(str(e['id']))
    vistas = set(cat) | {f['id'] for f in feixes if isinstance(f.get('id'), str)}
    for a in _bruto_json(pasta / 'acoes_guardadas.json', []):
        if isinstance(a, dict) and isinstance(a.get('id'), str) and a['id'] and a['id'] not in vistas:
            vistas.add(a['id'])
            estados['em_andamento' if a['id'] in iniciadas - concluidas else 'sugerido'] += 1
    plano = _bruto_json(pasta / 'career_state.json', {}).get('plano')
    plano = plano if isinstance(plano, dict) else {}
    auto = _bruto_json(pasta / 'autoavaliacao.json', {})
    skills = plano.get('skills') if isinstance(plano.get('skills'), list) else []
    niveis = {}
    for s in skills:  # jogo.niveis
        if not isinstance(s, dict) or not isinstance(s.get('nome'), str) or not s['nome'].strip():
            continue
        nivel = _bruto_int(auto.get(s['nome']))
        if nivel is None:
            nivel = s['autoavaliacao'] if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
        niveis[s['nome']] = _bruto_int(nivel or 0) or 0
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
