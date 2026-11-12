"""Ações executáveis da Luzia: ids estáveis, status, evidências e links que abrem o Claude Code.

As evidências ficam em `private/evidencias.jsonl` (fora do git). Ações guardadas pelo observador
(cartão "guardar para depois") ficam em `private/acoes_guardadas.json`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

PRIVATE = Path(__file__).resolve().parent / 'private'
EVID = PRIVATE / 'evidencias.jsonl'
SALVAS = PRIVATE / 'acoes_guardadas.json'
FILA = PRIVATE / 'fila.json'


# ------------------------------------------------------------------ fila painel → harness
def fila() -> list[dict]:
    """Ações que a pessoa mandou do painel para o agente e ainda não começou."""
    return _read_json(FILA, [])


def enfileirar(acao_id: str, titulo: str = '') -> None:
    itens = [f for f in fila() if f['id'] != acao_id]
    itens.append({'id': acao_id, 'titulo': titulo, 'quando': datetime.now().isoformat(timespec='seconds'), 'oferecida_em': []})
    PRIVATE.mkdir(parents=True, exist_ok=True)
    FILA.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding='utf-8')


def desenfileirar(acao_id: str) -> None:
    if FILA.exists():
        FILA.write_text(json.dumps([f for f in fila() if f['id'] != acao_id], ensure_ascii=False, indent=2), encoding='utf-8')


def marcar_oferecida(acao_id: str, sessao: str) -> None:
    itens = fila()
    for f in itens:
        if f['id'] == acao_id and sessao not in f['oferecida_em']:
            f['oferecida_em'].append(sessao)
    FILA.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding='utf-8')


def aid(origem: str, titulo: str) -> str:
    return hashlib.sha1(f'{origem}|{titulo}'.encode('utf-8')).hexdigest()[:4]


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def eventos() -> list[dict]:
    if not EVID.exists():
        return []
    out = []
    for line in EVID.read_text(encoding='utf-8').splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def registrar_evento(acao_id: str, evento: str, **extra) -> dict:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    rec = {'quando': datetime.now().isoformat(timespec='seconds'), 'id': acao_id, 'evento': evento, **extra}
    with EVID.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def evidencias() -> list[dict]:
    """Ações concluídas com nota (as que contam para P3/P4)."""
    return [e for e in eventos() if e.get('evento') == 'concluida']


def status_map() -> dict[str, dict]:
    st: dict[str, dict] = {}
    for e in eventos():
        cur = st.setdefault(e['id'], {'status': 'pendente'})
        if e['evento'] == 'iniciada' and cur['status'] != 'feita':
            cur['status'] = 'em andamento'
        elif e['evento'] == 'concluida':
            cur.update(status='feita', nota=e.get('nota'), resumo=e.get('resumo', ''), quando=e['quando'])
    return st


def guardar(skill: str, pergunta: str, contexto: str = '') -> dict:
    salvas = _read_json(SALVAS, [])
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
    if not any(a['id'] == acao['id'] for a in salvas):
        salvas.append(acao)
        PRIVATE.mkdir(parents=True, exist_ok=True)
        SALVAS.write_text(json.dumps(salvas, ensure_ascii=False, indent=2), encoding='utf-8')
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
            out.append({**a, 'origem': 'entrega', 'entrega': t.get('tarefa', ''),
                        'id': aid('entrega', t.get('tarefa', '') + a.get('titulo', ''))})
    for op in plan.get('oportunidades_tarefa_atual', []):
        a = op.get('acao') or {}
        if a:
            out.append({**a, 'origem': 'sessão', 'gatilho': op.get('gatilho', ''),
                        'id': aid('sessao', a.get('titulo', ''))})
    out.extend(_read_json(SALVAS, []))
    return out


def find(plan: dict, acao_id: str) -> dict | None:
    acao_id = acao_id.lstrip('#').lower()
    return next((a for a in todas(plan, descartados=True) if a['id'] == acao_id), None)


def deep_link(acao_id: str, cwd: str) -> str:
    """Claude Code em terminal (claude-cli://): abre uma sessão com /luzia:fazer <id> pronto para Enter."""
    return f'claude-cli://open?cwd={quote(cwd, safe="")}&q={quote(f"/luzia:fazer {acao_id}", safe="")}'


CODE_DIR = Path(__file__).resolve().parents[1]
RUBRICA_TXT = ('0 = não explicou · 1 = descreveu o que o código faz · 2 = explicou o porquê da decisão · '
               '3 = comparou com uma alternativa · 4 = ligou ao conceito e aos trade-offs')


def comando_registrar(acao_id: str) -> str:
    return (f'cd "{CODE_DIR.as_posix()}" && python -m luzia.cli registrar {acao_id} '
            '--nota <0-4> --resumo "<1 linha do que a pessoa demonstrou, sem nomes da empresa>"')


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
