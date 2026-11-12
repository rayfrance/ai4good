"""Observador da Luzia: hooks do Claude Code (PostToolUse e UserPromptSubmit).

Roda localmente, sem chamar o modelo, só nos repositórios autorizados (`private/observer.json`).

- PostToolUse (edição de arquivo ou `git commit`): se o conceito de uma skill com lacuna aparece no
  que o agente escreveu, é **luz refletida** (+10 lm). No modo ativo, a Luzia mostra um cartão com uma
  pergunta: 1 frase sua converte em **luz própria** (até +30 lm).
- UserPromptSubmit: se o conceito aparece no **seu prompt** (você dirigiu), é **luz própria** (+20 lm).
  Também oferece os feixes que você mandou do painel (fila).
- Um reconhecimento por skill por sessão; no máximo 40 lm passivos por skill por dia (regras em docs/luzia-ux.md).
- Grava só o evento mascarado (horário, skill, extensão, origem). Nunca o caminho, o código ou o texto do prompt.
- Modos: `ativo` (cartão no chat), `passivo` (só registra e credita), `sob_demanda` (não observa).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from luzia import jogo  # noqa: E402

PRIVATE = HERE / 'private'
STATE_FILE = HERE.parents[1] / 'outputs' / 'sem2' / 'career_state.json'
CFG = PRIVATE / 'observer.json'
LOG = PRIVATE / 'sessao.jsonl'
SEEN = PRIVATE / 'sessao_vistos.json'
CLI = 'cd /c/Repositorio/ai4good-sem2/code && python -m luzia.cli'

PALAVRAS_PADRAO = {
    'Domain-Driven Design (DDD)': ['Domain', 'Aggregate', 'ValueObject', 'Value Object', 'Entity', 'Repository', 'BoundedContext',
                                   'DomainEvent', 'agregado', 'objeto de valor', 'entidade', 'subdomínio', 'contexto delimitado', 'DDD'],
    'Arquitetura .NET / Clean Architecture': ['Interface', 'UseCase', 'Application', 'Infrastructure', 'DependencyInjection',
                                              'IServiceCollection', 'camada', 'injeção de dependência', 'desacopl', 'clean architecture'],
    'Testes e Qualidade / SQL': ['Test', 'xunit', 'Assert', 'Mock', 'Fact', 'teste', 'cobertura', 'SELECT', 'JOIN', 'índice'],
    'Back-end C# / .NET e Integrações': ['HttpClient', 'Controller', 'Integration', 'async Task', 'integração', 'endpoint', 'retry'],
    'Front-end (JS / Razor / React)': ['.cshtml', 'useState', 'fetch(', 'jQuery', 'componente', 'modal', 'razor'],
    'Programação Agêntica e Fluxo com IA': ['CLAUDE.md', 'AGENTS.md', '.claude', 'subagente', 'hook', 'skill', 'plan mode'],
}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def plano() -> dict:
    return read_json(STATE_FILE, {}).get('plano', {})


def lacunas(plan: dict) -> dict[str, dict]:
    """Skills com lacuna (nível < meta), com palavras-chave do plano + padrão em português."""
    out = {}
    for nome, v in jogo.niveis(plan).items():
        if v['nivel'] >= v['meta']:
            continue
        s = next((x for x in plan.get('skills', []) if x['nome'] == nome), {})
        out[nome] = {'palavras': list(dict.fromkeys((s.get('palavras_chave') or []) + PALAVRAS_PADRAO.get(nome, []))),
                     'nivel': v['nivel'], 'meta': v['meta']}
    return out or {k: {'palavras': p, 'nivel': None, 'meta': None} for k, p in PALAVRAS_PADRAO.items()}


def detectar(texto: str, gaps: dict) -> list[str]:
    achadas = []
    for skill, info in gaps.items():
        for w in info['palavras']:
            if w and len(w) >= 3 and re.search(r'(?<![A-Za-z])' + re.escape(w), texto, re.IGNORECASE):
                achadas.append(skill)
                break
    return achadas


def authorized(cwd: str, cfg: dict) -> bool:
    roots = cfg.get('autorizados') or []
    cwd_n = cwd.replace('\\', '/').lower()
    return any(cwd_n.startswith(r.replace('\\', '/').lower()) for r in roots)


def sessao_id(event: dict) -> str:
    return hashlib.sha256(event.get('session_id', '').encode()).hexdigest()[:8]


def novas_na_sessao(sid: str, chave: str, skills: list[str]) -> list[str]:
    vistos = read_json(SEEN, {})
    ja = set(vistos.get(f'{sid}:{chave}', []))
    novas = [s for s in skills if s not in ja]
    vistos[f'{sid}:{chave}'] = sorted(ja | set(skills))
    PRIVATE.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(vistos, ensure_ascii=False), encoding='utf-8')
    return novas


def registrar(sid: str, skill: str, ext: str, origem: str, modo: str, lm: int, luz: str, interveio: bool) -> None:
    with LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'quando': datetime.now().isoformat(timespec='seconds'), 'sessao': sid, 'skill': skill,
                            'extensao': ext, 'ferramenta': origem, 'modo': modo, 'lm': lm, 'luz': luz,
                            'interveio': interveio}, ensure_ascii=False) + '\n')


def saida(evento: str, contexto: str) -> None:
    print(json.dumps({'hookSpecificOutput': {'hookEventName': evento, 'additionalContext': contexto}}, ensure_ascii=True))


def ao_enviar_prompt(event: dict, cfg: dict) -> None:
    """UserPromptSubmit: luz própria quando você dirige o conceito; e a fila do painel."""
    sid, modo = sessao_id(event), cfg.get('modo', 'ativo')
    partes = []
    if modo != 'sob_demanda':
        plan = plano()
        gaps = lacunas(plan)
        for skill in novas_na_sessao(sid, 'prompt', detectar(event.get('prompt', ''), gaps)):
            lm = jogo.passivo(skill, 'prompt', sid)
            registrar(sid, skill, 'prompt', 'prompt', modo, lm, 'propria', modo == 'ativo' and lm > 0)
            if lm and modo == 'ativo':
                partes.append(f'[Luzia · luz própria] A pessoa DIRIGIU "{skill}" neste pedido (+{lm} lm de luz própria). '
                              f'Responda normalmente e, no FIM, em UMA linha: "✨ Luzia · {skill}: você dirigiu isto, +{lm} lm de luz própria."')
    fila = read_json(PRIVATE / 'fila.json', [])
    pend = [f for f in fila if sid not in f.get('oferecida_em', [])]
    if pend:
        item = pend[0]
        item.setdefault('oferecida_em', []).append(sid)
        (PRIVATE / 'fila.json').write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding='utf-8')
        partes.append(
            f'[Luzia · fila] A pessoa enviou do painel o feixe #{item["id"]} ("{item.get("titulo", "")}"). Responda primeiro ao '
            'que ela pediu. No FIM, em uma linha começando com "✨ Luzia:", lembre o feixe e use AskUserQuestion com '
            '"Abrir em sessão nova", "Fazer aqui" e "Depois". Sessão nova: rode '
            f'`{CLI} prompt {item["id"]} --onde "sessão nova"` e abra uma sessão/agente novo com esse texto pela ferramenta do seu '
            f'harness (se não houver, faça aqui). Fazer aqui: rode `{CLI} fazer {item["id"]} --onde aqui` e siga o roteiro.'
        )
    if partes:
        saida('UserPromptSubmit', '\n'.join(partes))


def ao_usar_ferramenta(event: dict, cfg: dict) -> None:
    """PostToolUse: luz refletida quando o agente aplica um conceito do seu plano."""
    modo = cfg.get('modo', 'ativo')
    if modo == 'sob_demanda':
        return
    tool, ti = event.get('tool_name', ''), event.get('tool_input') or {}
    if tool == 'Bash':
        cmd = ti.get('command', '')
        if 'git commit' not in cmd:
            return
        texto, ext = cmd, 'commit'
    else:
        caminho = ti.get('file_path', '')
        edits = ' '.join(e.get('new_string', '') for e in ti.get('edits', []) if isinstance(e, dict))
        texto = ' '.join([Path(caminho).name, ti.get('content', ''), ti.get('new_string', ''), edits])
        ext = Path(caminho).suffix.lower() or 'arquivo'
    plan = plano()
    gaps = lacunas(plan)
    sid = sessao_id(event)
    novas = novas_na_sessao(sid, 'agente', detectar(texto, gaps))
    if not novas:
        return
    for i, skill in enumerate(novas):
        lm = jogo.passivo(skill, 'refletida', sid)
        registrar(sid, skill, ext, tool, modo, lm, 'refletida', modo == 'ativo' and i == 0)
    if modo != 'ativo':
        return
    skill = novas[0]
    info = gaps.get(skill, {})
    nivel = f"você {info.get('nivel')} → meta {info.get('meta')}" if info.get('nivel') is not None else 'lacuna do plano'
    saida('PostToolUse', (
        f'[Luzia · luz refletida] O código que você (agente) acabou de escrever aplica "{skill}" ({nivel}). Isso rendeu '
        '+10 lm de luz REFLETIDA para a pessoa: quem aplicou foi o agente. Termine a tarefa normalmente. No FIM da resposta, '
        'mostre este cartão em no máximo 3 linhas:\n'
        f'✨ Luzia · {skill} reconhecido nesta mudança · +10 lm (luz refletida)\n'
        '<1 linha: onde o conceito aparece concretamente nesta mudança>\n'
        '▸ Em 1 frase: <pergunta concreta de líder técnico sobre o porquê desta decisão> · vira luz própria: até +30 lm\n'
        'Depois, use AskUserQuestion com "Responder agora" e "Guardar para depois". Responder: espere a frase, avalie pela '
        'rubrica 0-4 (0 não explicou, 1 descreveu o código, 2 explicou o porquê, 3 comparou com alternativa, 4 ligou ao '
        f'conceito e aos trade-offs), dê retorno em 1 linha e rode: {CLI} cartao --skill "{skill}" --pergunta "<a pergunta>" '
        f'--nota <0-4> --resumo "<1 linha, sem nomes da empresa>". Guardar: rode {CLI} cartao --skill "{skill}" '
        '--pergunta "<a pergunta>". Nunca cite nomes da empresa, clientes ou colegas.'
    ))


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    cfg = read_json(CFG, {'modo': 'ativo', 'autorizados': []})
    if not authorized(event.get('cwd', ''), cfg):
        return
    try:
        if event.get('hook_event_name') == 'UserPromptSubmit':
            ao_enviar_prompt(event, cfg)
        else:
            ao_usar_ferramenta(event, cfg)
    except Exception:
        return  # o observador nunca deve atrapalhar a sessão


if __name__ == '__main__':
    main()
