"""Observador da Luzia: hooks do Claude Code (PostToolUse e UserPromptSubmit).

Roda localmente, sem chamar o modelo, só nos repositórios autorizados (`private/observer.json`).

- PostToolUse (edição de arquivo ou `git commit`): se o conceito de uma skill com lacuna aparece no
  que o agente escreveu, é **luz refletida** (+10 lm). No modo ativo, a Luzia mostra um cartão com uma
  pergunta: 1 frase sua converte em **luz própria** (até +30 lm).
- UserPromptSubmit: se o conceito aparece no **seu prompt** (você dirigiu), é **luz própria** (+20 lm).
  Também oferece os feixes que você mandou do painel (fila).
- Um reconhecimento por skill por sessão; no máximo 40 lm passivos por skill por dia (regras em docs/luzia-ux.md).
- Grava só o evento mascarado (horário, skill, extensão, origem). Nunca o caminho, o código ou o texto do prompt.
- Tudo vai para o banco (`lumen`, `sessao_evento`, `lampejo`) por `banco.gravar_ou_pendurar`, com espera curta: se o banco
  estiver ocupado, o evento fica em `pendentes.jsonl` e a próxima escrita o absorve. O hook nunca levanta nem trava a sessão.
- SessionStart: se há algo a retomar (feixe em andamento, degrau pronto, fila), uma linha no fim da 1ª resposta.
- Modos: `ativo` (cartão no chat), `passivo` (só registra e credita), `sob_demanda` (não observa).
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from luzia import acoes, arquivos, banco, jogo, trajetoria  # noqa: E402

PRIVATE = arquivos.PRIVATE
CFG = PRIVATE / 'observer.json'
CLI = arquivos.CLI

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
    return arquivos.ler_json(path, default)


def plano() -> dict:
    return trajetoria.plano(banco.ESPERA_CURTA_MS)


def lacunas(plan: dict) -> dict[str, dict]:
    """Skills com lacuna (nível < meta), com palavras-chave do plano + padrão em português."""
    out = {}
    for nome, v in jogo.niveis(plan, espera_ms=banco.ESPERA_CURTA_MS).items():
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


def registrar(sid: str, skill: str, ext: str, origem: str, modo: str, lm: int, luz: str, interveio: bool) -> bool:
    """Evento mascarado da sessão no banco (ou em `pendentes.jsonl` se o banco estiver ocupado)."""
    return banco.gravar_ou_pendurar('sessao_evento', {'sessao': sid, 'prisma': skill, 'extensao': ext, 'ferramenta': origem,
                                                      'modo': modo, 'lm': lm, 'luz': luz, 'interveio': 1 if interveio else 0})


def saida(evento: str, contexto: str) -> None:
    print(json.dumps({'hookSpecificOutput': {'hookEventName': evento, 'additionalContext': contexto}}, ensure_ascii=True))


def sem_quebrar(funcao):
    """O observador nunca atrapalha a sessão: erro do banco ou de qualquer parte vira linha no erros.log (só o tipo)."""
    @functools.wraps(funcao)
    def protegida(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except Exception as e:
            arquivos.registrar_erro(f'observer {funcao.__name__}', e)
    return protegida


@sem_quebrar
def ao_enviar_prompt(event: dict, cfg: dict) -> None:
    """UserPromptSubmit: luz própria quando você dirige o conceito; e a fila do painel."""
    sid, modo = sessao_id(event), cfg.get('modo', 'ativo')
    partes = []
    if modo != 'sob_demanda':
        plan = plano()
        gaps = lacunas(plan)
        for skill in detectar(event.get('prompt', ''), gaps):
            lm = jogo.reconhecer(sid, 'prompt', skill, 'prompt', 'prompt', 'prompt', modo, modo == 'ativo')
            if lm and modo == 'ativo':
                partes.append(f'[Luzia · luz própria] A pessoa DIRIGIU "{skill}" neste pedido (+{lm} lm de luz própria). '
                              f'Responda normalmente e, no FIM, em UMA linha: "✦ Luzia · {skill}: você dirigiu isto, +{lm} lm de luz própria."')
    try:  # espera curta: o hook não pode travar a sessão; sem a fila, o resto do aviso sai igual
        pend = [f for f in acoes.fila(banco.ESPERA_CURTA_MS) if sid not in f.get('oferecida_em', [])]
    except Exception as e:
        arquivos.registrar_erro('observer fila', e)
        pend = []
    if pend:
        item = pend[0]
        try:
            acoes.marcar_oferecida(item['id'], sid, banco.ESPERA_CURTA_MS)
        except Exception as e:  # o aviso sai mesmo se o banco estiver ocupado; o erro fica registrado
            arquivos.registrar_erro('observer fila', e)
        partes.append(
            f'[Luzia · fila] A pessoa enviou do painel o feixe #{item["id"]} ("{item.get("titulo", "")}"). Responda primeiro ao '
            'que ela pediu. No FIM, em uma linha começando com "✦ Luzia:", lembre o feixe e use AskUserQuestion com '
            '"Abrir em sessão nova", "Fazer aqui" e "Depois". Sessão nova: rode '
            f'`{CLI} prompt {item["id"]} --onde "sessão nova"` e abra uma sessão/agente novo com esse texto pela ferramenta do seu '
            f'harness (se não houver, faça aqui). Fazer aqui: rode `{CLI} fazer {item["id"]} --onde aqui` e siga o roteiro.'
        )
    if partes:
        saida('UserPromptSubmit', '\n'.join(partes))


@sem_quebrar
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
    novas = []
    for skill in detectar(texto, gaps):
        primeira = modo == 'ativo' and not novas  # só o primeiro reconhecido abre lampejo (vira luz própria uma vez)
        if jogo.reconhecer(sid, 'agente', skill, 'refletida', ext, tool, modo, primeira, lampejo=primeira) is not None:
            novas.append(skill)
    if not novas or modo != 'ativo':
        return
    skill = novas[0]
    info = gaps.get(skill, {})
    nivel = f"você {info.get('nivel')} → meta {info.get('meta')}" if info.get('nivel') is not None else 'lacuna do plano'
    saida('PostToolUse', (
        f'[Luzia · luz refletida] O código que você (agente) acabou de escrever aplica "{skill}" ({nivel}). Isso rendeu '
        '+10 lm de luz REFLETIDA para a pessoa: quem aplicou foi o agente. Termine a tarefa normalmente. No FIM da resposta, '
        'mostre este cartão em no máximo 3 linhas:\n'
        f'✦ Luzia · {skill} reconhecido nesta mudança · +10 lm (luz refletida)\n'
        '<1 linha: onde o conceito aparece concretamente nesta mudança>\n'
        '▸ Em 1 frase: <pergunta concreta de líder técnico sobre o porquê desta decisão> · vira luz própria: até +30 lm\n'
        'Depois, use AskUserQuestion com "Responder agora" e "Guardar para depois". Responder: espere a frase, avalie pela '
        'rubrica 0-4 (0 não explicou, 1 descreveu o código, 2 explicou o porquê, 3 comparou com alternativa, 4 ligou ao '
        f'conceito e aos trade-offs), dê retorno em 1 linha e rode: {CLI} cartao --skill "{skill}" --pergunta "<a pergunta>" '
        f'--nota <0-4> --resumo "<1 linha, sem nomes da empresa>". Guardar: rode {CLI} cartao --skill "{skill}" '
        '--pergunta "<a pergunta>". Nunca cite nomes da empresa, clientes ou colegas.'
    ))


@sem_quebrar
def ao_iniciar_sessao(event: dict, cfg: dict) -> None:
    """SessionStart: lembra o que dá para retomar, sem interromper."""
    if cfg.get('modo', 'ativo') == 'sob_demanda':
        return
    plan = plano()
    if not plan:
        return
    andamento = jogo.em_andamento(banco.ESPERA_CURTA_MS)
    prontas = [s['nome'].split('(')[0].strip() for s in jogo.rota(plan, espera_ms=banco.ESPERA_CURTA_MS)['skills']
               if s['pronto'] and not s['na_meta']]
    try:
        fila = acoes.fila(banco.ESPERA_CURTA_MS)
    except Exception as e:
        arquivos.registrar_erro('observer fila', e)
        fila = []
    partes = []
    if prontas:
        partes.append(f"{', '.join(prontas)} pronta para subir de degrau")
    if andamento:
        partes.append(f'feixe em andamento: "{andamento[0].get("titulo", "")}"')
    if fila:
        partes.append(f'{len(fila)} feixe(s) na fila do painel')
    if partes:
        saida('SessionStart', f"[Luzia · início] {'; '.join(partes)}. Não interrompa o que a pessoa pedir. No FIM da sua "
                              'primeira resposta, em UMA linha: "✦ Luzia: <resumo curto disso> · /luzia:hoje para continuar."')


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
        elif event.get('hook_event_name') == 'SessionStart':
            ao_iniciar_sessao(event, cfg)
        else:
            ao_usar_ferramenta(event, cfg)
    except Exception as e:  # o observador nunca deve atrapalhar a sessão, mas o erro fica registrado
        arquivos.registrar_erro(f"observer {event.get('hook_event_name', '')}", e)


if __name__ == '__main__':
    main()
