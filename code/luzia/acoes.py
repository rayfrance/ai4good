"""Ações executáveis da Luzia: ids estáveis, status, evidências e links que abrem o Claude Code.

Tudo mora no banco (`private/luzia.db`, fora do git): a fila do painel em `fila`, as evidências (eventos
'iniciada'/'concluida') em `avanco_evento` e as ações guardadas pelo observador (cartão "guardar para depois")
como avanços de origem 'lampejo'. Os arquivos antigos só são lidos pela migração.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from urllib.parse import quote

from . import arquivos, banco, trajetoria

PRIVATE = arquivos.PRIVATE


# ------------------------------------------------------------------ fila painel → harness
def _agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _lista(texto) -> list:
    try:
        valor = json.loads(texto or '[]')
    except ValueError:
        return []
    return valor if isinstance(valor, list) else []


def _abrir(espera_ms: int | None):
    """Conexão normal, ou com espera curta (hook: nunca fica preso mais que o orçamento dele)."""
    return trajetoria.abrir(espera_ms)


def fila(espera_ms: int | None = None) -> list[dict]:
    """Ações que a pessoa mandou do painel para o agente e ainda não começou."""
    with _abrir(espera_ms) as con:
        return [{'id': r['avanco_id'], 'titulo': r['titulo'], 'quando': r['quando'], 'oferecida_em': _lista(r['oferecida_json'])}
                for r in con.execute(
                    'SELECT f.* FROM fila f LEFT JOIN avanco a ON a.id = f.avanco_id '
                    'LEFT JOIN prisma p ON p.nome = a.prisma '  # avanço de prisma arquivado não é oferecido
                    "WHERE COALESCE(p.estado, 'ativo') = 'ativo' ORDER BY f.quando, f.rowid")]


def enfileirar(acao_id: str, titulo: str = '') -> None:
    with trajetoria.abrir() as con, banco.transacao(con):
        con.execute('DELETE FROM fila WHERE avanco_id = ?', (acao_id,))
        con.execute('INSERT INTO fila (avanco_id, titulo, quando, oferecida_json) VALUES (?, ?, ?, ?)',
                    (acao_id, titulo, _agora(), '[]'))


def desenfileirar(acao_id: str) -> None:
    with trajetoria.abrir() as con, banco.transacao(con):
        con.execute('DELETE FROM fila WHERE avanco_id = ?', (acao_id,))


def marcar_oferecida(acao_id: str, sessao: str, espera_ms: int | None = None) -> None:
    with _abrir(espera_ms) as con, banco.transacao(con):
        r = con.execute('SELECT oferecida_json FROM fila WHERE avanco_id = ?', (acao_id,)).fetchone()
        if r is None:
            return
        oferecidas = _lista(r['oferecida_json'])
        if sessao not in oferecidas:
            oferecidas.append(sessao)
            con.execute('UPDATE fila SET oferecida_json = ? WHERE avanco_id = ?',
                        (json.dumps(oferecidas, ensure_ascii=False), acao_id))


def aid(origem: str, titulo: str) -> str:
    return hashlib.sha1(f'{origem}|{titulo}'.encode('utf-8')).hexdigest()[:4]


# ------------------------------------------------------------------ eventos e evidências (livro `avanco_evento`)
COLUNAS_EVENTO = ('nota', 'resumo', 'onde', 'motivo')


def eventos() -> list[dict]:
    """Eventos de evidência ('iniciada', 'concluida'...) no formato antigo; a história do feixe fica de fora."""
    out = []
    with trajetoria.abrir() as con:
        for r in con.execute('SELECT * FROM avanco_evento ORDER BY id'):
            try:
                extra = json.loads(r['extra_json'] or '{}')
            except ValueError:
                extra = {}
            extra = extra if isinstance(extra, dict) else {}
            if extra.get('fonte') == 'historico':
                continue
            rec = {'quando': r['quando'], 'id': r['avanco_id'], 'evento': r['evento']}
            rec.update({c: r[c] for c in COLUNAS_EVENTO if r[c] is not None})
            rec.update({k: v for k, v in extra.items() if k != 'fonte'})
            out.append(rec)
    return out


def registrar_evento(acao_id: str, evento: str, **extra) -> dict:
    rec = {'quando': _agora(), 'id': acao_id, 'evento': evento, **extra}
    colunas = {c: extra.get(c) for c in COLUNAS_EVENTO}
    resto = {k: v for k, v in extra.items() if k not in COLUNAS_EVENTO}
    if colunas['nota'] is not None:
        colunas['nota'] = int(colunas['nota'])
    with trajetoria.abrir() as con, banco.transacao(con):
        con.execute('INSERT INTO avanco_evento (avanco_id, quando, evento, onde, nota, resumo, motivo, extra_json)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (acao_id, rec['quando'], evento, colunas['onde'], colunas['nota'], colunas['resumo'],
                     colunas['motivo'], json.dumps({'fonte': 'evidencias', **resto}, ensure_ascii=False)))
    return rec


def evidencias() -> list[dict]:
    """Ações concluídas com nota (as que contam para P3/P4): só os eventos 'concluida', nunca o histórico do feixe."""
    return [e for e in eventos() if e.get('evento') == 'concluida']


def status_map(con: sqlite3.Connection | None = None) -> dict[str, dict]:
    if con is None:
        with trajetoria.abrir() as nova:
            return status_map(nova)
    st: dict[str, dict] = {}
    for r in con.execute("SELECT avanco_id, quando, evento, nota, resumo FROM avanco_evento "
                         "WHERE evento IN ('iniciada', 'concluida') ORDER BY id"):
        cur = st.setdefault(r['avanco_id'], {'status': 'pendente'})
        if r['evento'] == 'iniciada' and cur['status'] != 'feita':
            cur['status'] = 'em andamento'
        elif r['evento'] == 'concluida':
            cur.update(status='feita', nota=r['nota'], resumo=r['resumo'] or '', quando=r['quando'])
    return st


def guardar(skill: str, pergunta: str, contexto: str = '') -> dict:
    acao = {
        'titulo': pergunta[:70],
        'tipo': 'explicar',
        'skill': skill,
        'dimensao': None,
        'por_que': contexto or f'Oportunidade de {skill} que a Luzia viu na sua sessão.',
        'conceitos': [skill],
        'como': ['Abra a mudança em que isto apareceu.', 'Responda à pergunta com suas palavras.'],
        'onde_explorar': 'A mudança da sessão em que a Luzia interveio.',
        'prompt': f'Luzia me deixou esta pergunta sobre {skill}: "{pergunta}". Me faça a pergunta, espere minha resposta e depois me dê retorno.',
        'duracao_min': 5,
        'origem': 'guardada',
        'guardada_em': datetime.now().isoformat(timespec='seconds'),
    }
    acao['id'] = aid('guardada', acao['titulo'])
    from . import jogo  # a ação guardada é um avanço de origem 'lampejo'; valor e skill do plano vêm do próximo sync
    with trajetoria.abrir() as con, banco.transacao(con):
        jogo._inserir_avanco(con, {**acao, 'skill_plano': skill, 'estado': 'sugerido', 'criado_em': _agora()})
    return acao


def todas(plan: dict, descartados: bool = False) -> list[dict]:
    """Feixes do catálogo persistente do jogo (estado, valor em lúmens, histórico)."""
    from . import jogo
    return jogo.catalogo(plan, descartados=descartados)


def derivadas(plan: dict) -> list[dict]:
    """Feixes que a Luzia sugeriu no plano atual (antes de entrar no catálogo)."""
    out: list[dict] = []
    for marco in plan.get('plano', []):
        for a in marco.get('acoes', []):
            out.append({**a, 'origem': 'rota', 'horizonte': marco.get('horizonte', ''),
                        'id': aid('rota', a.get('titulo', ''))})
    for t in plan.get('tarefas_recentes', []):
        for a in t.get('acoes', []):
            # o id continua o mesmo (estado e histórico), mas o título "da entrega" que a IA montou não é uma entrega
            out.append({**a, 'origem': 'entrega', 'da_triagem': True,
                        'id': aid('entrega', t.get('tarefa', '') + a.get('titulo', ''))})
    for op in plan.get('oportunidades_tarefa_atual', []):
        a = op.get('acao') or {}
        if a:
            out.append({**a, 'origem': 'sessão', 'gatilho': op.get('gatilho', ''),
                        'id': aid('sessao', a.get('titulo', ''))})
    for t in plan.get('trechos', []):  # feixes que acendem quando a skill sobe de degrau ou fica sem feixe aberto
        for a in t.get('acoes', []):
            out.append({**a, 'skill': t.get('skill') or a.get('skill', ''), 'dimensao': None, 'origem': 'trecho',
                        'horizonte': f"nível {t.get('para', '')}", 'id': aid('trecho', t.get('skill', '') + a.get('titulo', ''))})
    return out  # as ações guardadas já são avanços no banco: o catálogo as mantém


def find(plan: dict, acao_id: str) -> dict | None:
    acao_id = acao_id.lstrip('#').lower()
    return next((a for a in todas(plan, descartados=True) if a['id'] == acao_id), None)


def deep_link(acao_id: str, cwd: str) -> str:
    """Claude Code em terminal (claude-cli://): abre uma sessão com /luzia:fazer <id> pronto para Enter."""
    return f'claude-cli://open?cwd={quote(cwd, safe="")}&q={quote(f"/luzia:fazer {acao_id}", safe="")}'


RUBRICA_TXT = ('0 = não explicou · 1 = descreveu o que o código faz · 2 = explicou o porquê da decisão · '
               '3 = comparou com uma alternativa · 4 = ligou ao conceito e aos trade-offs')


def comando_registrar(acao_id: str) -> str:
    return (f'{arquivos.CLI} registrar {acao_id} '
            '--nota <0-4> --resumo "<1 linha do que a pessoa demonstrou>"')


def prompt_completo(a: dict) -> str:
    """Prompt autossuficiente: funciona colado em qualquer agente (Claude, Codex, Cursor, Antigravity...)."""
    como = '\n'.join(f'{i}. {p}' for i, p in enumerate(a.get('como', []), 1))
    return (
        f"Você vai agir como a Luzia, minha líder técnica de carreira, na ação #{a['id']}: "
        f"\"{a.get('titulo', '')}\" ({a.get('tipo', '')} · {a.get('skill', '')} · ~{a.get('duracao_min', '?')} min).\n"
        f"Por quê: {a.get('por_que', '')}\n"
        f"Conceitos: {', '.join(a.get('conceitos', []))}\n"
        f"Como:\n{como}\n"
        f"Onde explorar neste repositório: {a.get('onde_explorar', '')}\n\n"
        f"Meu pedido: {a.get('prompt', '')}\n\n"
        'Regras: faça UMA pergunta por vez e espere minha resposta; não faça o trabalho no meu lugar; '
        'se precisar mostrar código do repositório, mostre só o essencial.\n'
        f'No fim, avalie minha resposta pela rubrica 0-4 ({RUBRICA_TXT}), diga a nota com um ponto forte e '
        'um próximo passo, e registre a evidência rodando no terminal:\n'
        + comando_registrar(a['id'])
    )
