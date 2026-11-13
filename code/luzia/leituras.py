"""Leituras da Luzia com base visível, modelo e data (Tarefa 10).

Toda leitura de IA guarda os fatos usados (`base_json`), o hash desses fatos (`base_hash`),
o modelo e a data (`criado_em`). Só regenera quando o hash da base muda ou sob pedido, e
renova todas as leituras vencidas numa única chamada em lote (tudo ou nada na transação).
Sem modelo, sem chave ou sem internet: devolve 0 e nada é gravado.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime

from . import arquivos, banco, entregas, jogo, pipeline, planner, trajetoria


def _agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _texto(texto) -> str:
    """Texto real (a base aparece na tela de quem entrou); o envio ao modelo mascara conforme `mascarar_modelo`."""
    return str(texto or '').strip()


def _base_prisma(con: sqlite3.Connection, nome: str) -> dict:
    todos = {p['nome']: p for p in trajetoria.prismas(con, incluir_arquivados=True)}
    p = todos.get(nome, {'nome': nome, 'nivel': 0, 'meta': 5, 'estado': 'ativo'})
    plano = trajetoria.perfil_ler(con, 'plano') or {}
    skill_tri = next((s for s in plano.get('skills', []) if s.get('nome') == nome), {})
    diag = plano.get('diagnostico_fontes') or {}

    entregas_rows = con.execute(
        'SELECT e.id, e.titulo, e.commits, e.arquivos, e.linhas, ep.termos_json '
        'FROM entrega_prisma ep JOIN entrega e ON e.id = ep.entrega_id '
        'WHERE ep.prisma = ? ORDER BY e.fim DESC, e.id DESC',
        (nome,),
    ).fetchall()
    termos_set: dict[str, None] = {}
    entregas_resumo = []
    for r in entregas_rows:
        try:
            ts = json.loads(r['termos_json'] or '[]')
        except ValueError:
            ts = []
        for t in ts:
            termos_set[str(t)] = None
        entregas_resumo.append({
            'titulo': _texto(r['titulo']),
            'commits': int(r['commits'] or 0),
            'arquivos': int(r['arquivos'] or 0),
            'linhas': int(r['linhas'] or 0),
        })

    avs = jogo.avancos(con, prisma=nome, historico=False)
    conquistados = [
        {'titulo': _texto(a.get('titulo')), 'tipo': a.get('tipo'),
         'nota': a.get('nota'), 'lm_ganho': int(a.get('lm_ganho') or 0)}
        for a in avs if a.get('estado') == 'conquistado'
    ]
    abertos = sum(1 for a in avs if a.get('estado') in ('sugerido', 'na_fila', 'em_andamento'))

    lm_propria, lm_refletida = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN luz = 'propria' THEN lm END), 0), "
        "COALESCE(SUM(CASE WHEN luz = 'refletida' THEN lm END), 0) "
        'FROM lumen WHERE prisma = ?',
        (nome,),
    ).fetchone()
    lm_propria, lm_refletida = int(lm_propria or 0), int(lm_refletida or 0)

    ev_dirigido, ev_agente = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN ferramenta = 'prompt' THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN ferramenta != 'prompt' THEN 1 ELSE 0 END), 0) "
        'FROM sessao_evento WHERE prisma = ?',
        (nome,),
    ).fetchone()
    lm_dir_cnt, lm_ag_cnt = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN luz = 'propria' THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN luz = 'refletida' THEN 1 ELSE 0 END), 0) "
        'FROM lumen WHERE prisma = ?',
        (nome,),
    ).fetchone()
    dirigido = int(ev_dirigido or 0) + int(lm_dir_cnt or 0)
    pelo_agente = int(ev_agente or 0) + int(lm_ag_cnt or 0)
    total_interacoes = dirigido + pelo_agente
    pct_dirigido = round(100 * dirigido / total_interacoes) if total_interacoes else None

    return {
        'prisma': nome,
        'nivel': int(p.get('nivel') or 0),
        'meta': int(p.get('meta') if p.get('meta') is not None else 5),
        'estado': p.get('estado', 'ativo'),
        'entregas_total': len(entregas_rows),
        'commits_total': sum(int(r['commits'] or 0) for r in entregas_rows),
        'termos_detectados': list(termos_set),
        'entregas': entregas_resumo[:5],
        'avancos_conquistados': conquistados,
        'avancos_abertos': abertos,
        'lumens': {'propria': lm_propria, 'refletida': lm_refletida, 'total': lm_propria + lm_refletida},
        'uso_ia': {'dirigido': dirigido, 'pelo_agente': pelo_agente, 'pct_dirigido': pct_dirigido},
        'triagem': {
            'evidencia': _texto(skill_tri.get('evidencia')),
            'curriculo_vs_pratica': _texto(diag.get('conflito_curriculo_vs_realidade')),
        },
    }


def _base_entrega(con: sqlite3.Connection, entrega_id: str, det: dict | None = None) -> dict:
    try:
        eid = int(entrega_id)
    except ValueError:
        return {'entrega_id': str(entrega_id)}
    det = det if det is not None else entregas.detalhe(con, eid, incluir_leitura=False)
    if det is None:
        return {'entrega_id': str(entrega_id)}
    lm_ligados = det.get('lumens_ligados') or []
    lm_prop = sum(int(l['lm']) for l in lm_ligados if l.get('luz') == 'propria')
    lm_refl = sum(int(l['lm']) for l in lm_ligados if l.get('luz') == 'refletida')
    prop = det.get('propriedade') or {}
    dims = prop.get('dimensoes') or {}
    return {
        'entrega_id': eid,
        'titulo': _texto(det.get('titulo')),
        'fatos': det.get('fatos') or {},
        'prismas': [{'prisma': p['nome'], 'termos': p['termos']} for p in (det.get('prismas') or [])],
        'avancos_feitos': [
            {'titulo': _texto(a.get('titulo')), 'estado': a.get('estado'),
             'nota': a.get('nota'), 'dimensao': a.get('dimensao')}
            for a in (det.get('avancos_feitos') or [])
        ],
        'lumens_ligados': {'propria': lm_prop, 'refletida': lm_refl, 'total': lm_prop + lm_refl},
        'propriedade': {
            'indice': prop.get('indice'),
            'base': prop.get('base'),
            'dimensoes': {k: (v.get('nota') if isinstance(v, dict) else None) for k, v in dims.items()},
        },
    }


def _base_pedido(con: sqlite3.Connection, pedido_id: str) -> dict:
    try:
        pid = int(pedido_id)
    except ValueError:
        pid = -1
    r = con.execute('SELECT * FROM pedido WHERE id = ?', (pid,)).fetchone()
    resumo = trajetoria.resumo(con)
    ativos = [{'nome': p['nome'], 'nivel': p['nivel'], 'meta': p['meta']} for p in trajetoria.prismas(con)]
    if r is None:
        return {'pedido_id': str(pedido_id), 'trajetoria': resumo, 'prismas_ativos': ativos}
    return {
        'pedido_id': int(r['id']),
        'tipo': r['tipo'],
        'prisma': r['prisma'],
        'motivo': _texto(r['motivo']),
        'trajetoria': resumo,
        'prismas_ativos': ativos,
    }


def base(con: sqlite3.Connection, alvo_tipo: str, alvo_id: str, det: dict | None = None) -> dict:
    """Fatos determinísticos que fundamentam a leitura de um prisma, entrega ou pedido (reais: aparecem na tela de quem
    entrou; o envio ao modelo mascara conforme o interruptor `mascarar_modelo`, em `pipeline.run_plan`).

    `det` (entrega): o detalhe já calculado por quem chama (sem leitura), para não calculá-lo duas vezes.
    """
    alvo_id = str(alvo_id)
    if alvo_tipo == 'prisma':
        return _base_prisma(con, alvo_id)
    if alvo_tipo == 'entrega':
        return _base_entrega(con, alvo_id, det)
    if alvo_tipo == 'pedido':
        return _base_pedido(con, alvo_id)
    raise ValueError(f'tipo de alvo desconhecido para leitura: {alvo_tipo!r}')


def hash_base(dados_base: dict) -> str:
    """SHA-256 canônico (JSON com chaves ordenadas) da base de fatos."""
    canonico = json.dumps(dados_base, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()


def obter(con: sqlite3.Connection, alvo_tipo: str, alvo_id: str, atual: dict | None = None) -> dict | None:
    """Leitura mais recente gravada para (alvo_tipo, alvo_id), indicando se está vencida.

    `atual`: a base de fatos de agora, se quem chama já a calculou (senão ela é calculada aqui).
    """
    alvo_id = str(alvo_id)
    r = con.execute(
        'SELECT id, texto, base_json, base_hash, modelo, criado_em FROM leitura '
        'WHERE alvo_tipo = ? AND alvo_id = ? ORDER BY id DESC LIMIT 1',
        (alvo_tipo, alvo_id),
    ).fetchone()
    if r is None:
        return None
    try:
        base_salva = json.loads(r['base_json'] or '{}')
    except ValueError:
        base_salva = {}
    atual_hash = hash_base(atual if atual is not None else base(con, alvo_tipo, alvo_id))
    return {
        'id': int(r['id']),
        'alvo_tipo': alvo_tipo,
        'alvo_id': alvo_id,
        'texto': r['texto'],
        'base': base_salva,
        'base_hash': r['base_hash'],
        'modelo': r['modelo'],
        'criado_em': r['criado_em'],
        'vencida': r['base_hash'] != atual_hash,
    }


ENTREGAS_RELEVANTES = 10  # no chat; o painel mostra 15
LOTES_AUTOMATICOS = 2     # rodada automática do painel: no máximo 2 lotes


def vencidas(con: sqlite3.Connection, entregas_max: int | None = None) -> list[tuple[str, str]]:
    """Alvos ('prisma'|'entrega', id) sem leitura ou cujo hash da base mudou.

    Prismas ativos mais as `entregas_max` entregas mais recentes (todas, se None): é o conjunto "relevante" que a tela mostra.
    """
    candidatos: list[tuple[str, str]] = [('prisma', p['nome']) for p in trajetoria.prismas(con)]
    limite = '' if entregas_max is None else f' LIMIT {int(entregas_max)}'
    candidatos += [('entrega', str(r['id'])) for r in
                   con.execute(f'SELECT id FROM entrega ORDER BY fim DESC, id DESC{limite}')]
    out: list[tuple[str, str]] = []
    for tipo, aid in candidatos:
        r = con.execute(
            'SELECT base_hash FROM leitura WHERE alvo_tipo = ? AND alvo_id = ? ORDER BY id DESC LIMIT 1',
            (tipo, aid),
        ).fetchone()
        if r is None or r['base_hash'] != hash_base(base(con, tipo, aid)):
            out.append((tipo, aid))
    return out


TAMANHO_LOTE = 8  # alvos por chamada: um banco grande não vira um prompt gigante


def gerar(con: sqlite3.Connection, alvos: list[tuple[str, str]] | None = None) -> int:
    """Gera as leituras em lotes de até 8 alvos por chamada ao modelo; cada lote é gravado inteiro ou não é gravado.

    Devolve quantas leituras entraram (um lote que falhou ou veio incompleto não grava nada, e os outros seguem).
    """
    lista = list(dict.fromkeys(alvos if alvos is not None else vencidas(con)))
    return sum(_gerar_lote(con, lista[i:i + TAMANHO_LOTE]) for i in range(0, len(lista), TAMANHO_LOTE))


def _gerar_lote(con: sqlite3.Connection, lista: list[tuple[str, str]]) -> int:
    """Uma chamada ao modelo para estes alvos; grava todas as leituras ou nenhuma, numa transação."""
    if not lista:
        return 0
    itens = []
    for tipo, aid in lista:
        aid_s = str(aid)
        b = base(con, tipo, aid_s)
        itens.append({
            'alvo': f'{tipo}:{aid_s}',
            'alvo_tipo': tipo,
            'alvo_id': aid_s,
            'base': b,
            'base_hash': hash_base(b),
        })

    payload = {
        'alvos': [
            {'alvo': it['alvo'], 'tipo': it['alvo_tipo'], 'id': it['alvo_id'], 'fatos': it['base']}
            for it in itens
        ],
    }
    t0 = time.perf_counter()
    try:
        res, rec = pipeline.run_plan(
            payload,
            prep_seconds=time.perf_counter() - t0,
            label='leituras-lote',
            save_current_state=False,
            schema=planner.LEITURAS_SCHEMA,
            intro='Fatos medidos localmente pela Luzia para gerar leituras com base:',
        )
    except Exception as e:
        arquivos.registrar_erro('leituras.gerar', e)
        return 0

    brutas = (res.plan or {}).get('leituras') if isinstance(res.plan, dict) else None
    if not isinstance(brutas, list):
        return 0

    por_chave: dict[str, str] = {}
    for item in brutas:
        if isinstance(item, dict) and isinstance(item.get('alvo'), str) and isinstance(item.get('texto'), str):
            txt = item['texto'].strip()
            if txt:
                por_chave[item['alvo']] = txt

    prontas: list[tuple[dict, str]] = []
    for it in itens:
        txt = por_chave.get(it['alvo']) or por_chave.get(it['alvo_id'])
        if not txt:
            return 0  # lote incompleto: grava todas ou nenhuma
        prontas.append((it, txt))

    modelo_nome = (rec or {}).get('modelo') or getattr(res, 'model', '') or 'desconhecido'
    quando = (rec or {}).get('quando') or _agora()
    with banco.transacao(con):
        for it, txt in prontas:
            con.execute(
                'INSERT INTO leitura (alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (it['alvo_tipo'], it['alvo_id'], txt, json.dumps(it['base'], ensure_ascii=False, sort_keys=True),
                 it['base_hash'], modelo_nome, quando),
            )
    return len(prontas)
