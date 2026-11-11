"""Observador passivo da Luzia: hook PostToolUse do Claude Code.

Roda a cada edição de arquivo (Edit/Write/MultiEdit) ou `git commit` (Bash), localmente,
sem chamar o modelo. Compara o que entrou na sessão com as palavras-chave das skills
que ainda têm lacuna no plano de carreira.

- Grava em `private/sessao.jsonl` só o evento mascarado: horário, skill, extensão e
  ferramenta. Nunca grava nome de arquivo, caminho ou código.
- Modo `ativo`: na 1ª detecção de cada skill por sessão, intervém com uma linha no chat.
- Modo `passivo`: só registra (o evento aparece no painel).
- Modo `sob_demanda`: não faz nada.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIVATE = HERE / 'private'
STATE_FILE = HERE.parents[1] / 'outputs' / 'sem2' / 'career_state.json'
CFG = PRIVATE / 'observer.json'
LOG = PRIVATE / 'sessao.jsonl'
SEEN = PRIVATE / 'sessao_vistos.json'

DEFAULT_KEYWORDS = {
    'Domain-Driven Design (DDD)': ['Domain', 'Aggregate', 'ValueObject', 'Entity', 'Repository', 'BoundedContext', 'DomainEvent'],
    'Arquitetura .NET / Clean Architecture': ['Interface', 'Service', 'UseCase', 'Application', 'Infrastructure', 'DependencyInjection', 'IServiceCollection'],
    'Testes e Qualidade / SQL': ['Test', 'xunit', 'Assert', 'Mock', 'Fact', 'SELECT', 'JOIN'],
    'Back-end C# / .NET e Integrações': ['HttpClient', 'Controller', 'Integration', 'Api', 'async Task'],
    'Front-end (JS / Razor / React)': ['.cshtml', '.js', 'useState', 'fetch(', 'jQuery'],
    'Programação Agêntica e Fluxo com IA': ['CLAUDE.md', 'AGENTS.md', '.claude', 'prompt', 'skill'],
}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def gap_keywords() -> dict[str, list[str]]:
    """Palavras-chave das skills com lacuna (autoavaliação < alvo), vindas do plano salvo."""
    plan = read_json(STATE_FILE, {}).get('plano', {})
    autoaval = read_json(PRIVATE / 'autoavaliacao.json', {})
    out = {}
    for s in plan.get('skills', []):
        nome = s.get('nome', '')
        atual = autoaval.get(nome, s.get('autoavaliacao', s.get('luzia_sugere', s.get('atual', 0)))) or 0
        if int(atual) >= int(s.get('alvo', 5)):
            continue
        out[nome] = s.get('palavras_chave') or DEFAULT_KEYWORDS.get(nome, [])
    return out or DEFAULT_KEYWORDS


def authorized(cwd: str, cfg: dict) -> bool:
    roots = cfg.get('autorizados') or []
    cwd_n = cwd.replace('\\', '/').lower()
    return any(cwd_n.startswith(r.replace('\\', '/').lower()) for r in roots)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    cfg = read_json(CFG, {'modo': 'ativo', 'autorizados': []})
    modo = cfg.get('modo', 'ativo')
    if modo == 'sob_demanda' or not authorized(event.get('cwd', ''), cfg):
        return

    tool = event.get('tool_name', '')
    ti = event.get('tool_input') or {}
    if tool == 'Bash':
        cmd = ti.get('command', '')
        if 'git commit' not in cmd:
            return
        haystack, ext = cmd, 'commit'
    else:
        path = ti.get('file_path', '')
        edits = ' '.join(e.get('new_string', '') for e in ti.get('edits', []) if isinstance(e, dict))
        haystack = ' '.join([Path(path).name, ti.get('content', ''), ti.get('new_string', ''), edits])
        ext = Path(path).suffix.lower() or 'arquivo'

    found = []
    for skill, words in gap_keywords().items():
        for w in words:
            if w and re.search(re.escape(w), haystack, re.IGNORECASE):
                found.append(skill)
                break
    if not found:
        return

    sid = hashlib.sha256(event.get('session_id', '').encode()).hexdigest()[:8]
    seen = read_json(SEEN, {})
    already = set(seen.get(sid, []))
    novas = [s for s in found if s not in already]
    intervir = modo == 'ativo' and bool(novas)

    PRIVATE.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec='seconds')
    with LOG.open('a', encoding='utf-8') as f:
        for s in found:
            f.write(json.dumps({
                'quando': now, 'sessao': sid, 'skill': s, 'extensao': ext, 'ferramenta': tool,
                'modo': modo, 'interveio': intervir and s in novas,
            }, ensure_ascii=False) + '\n')
    seen[sid] = sorted(already | set(found))
    SEEN.write_text(json.dumps(seen, ensure_ascii=False), encoding='utf-8')

    if intervir:
        skill = novas[0]
        msg = f'✨ Luzia: esta tarefa toca em {skill}, uma lacuna do seu plano. Quer ver a teoria aplicada aqui?'
        print(json.dumps({
            'systemMessage': msg,
            'hookSpecificOutput': {
                'hookEventName': 'PostToolUse',
                'additionalContext': (
                    f'[Luzia · observador] A edição atual exercita "{skill}", lacuna do plano de carreira da pessoa. '
                    'Ao final da sua resposta, diga em UMA linha, começando com "✨ Luzia:", como esse conceito se '
                    'aplica a esta mudança e ofereça /luzia:feedback-skills-opportunities. Não interrompa a tarefa.'
                ),
            },
        }, ensure_ascii=False))


if __name__ == '__main__':
    main()
