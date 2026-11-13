"""Observador de foco da Luzia: hooks do Claude Code (PostToolUse, UserPromptSubmit e SessionStart).

Roda localmente, sem chamar o modelo, só nos repositórios autorizados (`private/observer.json`).

- PostToolUse (edição de arquivo ou `git commit`): se o conceito de um prisma (skill) com lacuna aparece no
  que o agente escreveu, é **luz refletida** (+10 lm). Em foco com lampejos (`ativo`), a Luzia mostra um lampejo com uma
  pergunta: 1 frase sua converte em **luz própria** (até +30 lm).
- UserPromptSubmit: se o conceito aparece no **seu prompt** (você dirigiu), é **luz própria** (+20 lm).
  Também oferece os avanços que você mandou do painel (fila).
- Um reconhecimento por prisma por sessão; no máximo 40 lm passivos por prisma por dia (regras em docs/luzia-ux.md).
- Grava só o evento mascarado (horário, prisma, extensão, origem). Nunca o caminho, o código ou o texto do prompt.
- Tudo vai para o banco (`lumen`, `sessao_evento`, `lampejo`) por `banco.gravar_ou_pendurar`, com espera curta: se o banco
  estiver ocupado, o evento fica em `pendentes.jsonl` e a próxima escrita o absorve. O hook nunca levanta nem trava a sessão.
- SessionStart: se há algo a retomar (avanço em andamento, nível pronto, fila), uma linha no fim da 1ª resposta.
- Modos do foco: `ativo` (em foco, com lampejos), `passivo` (em foco, em silêncio), `sob_demanda` (fora de foco).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from luzia import acoes, arquivos, banco, jogo, prismas, trajetoria  # noqa: E402

PRIVATE = arquivos.PRIVATE
CFG = PRIVATE / 'observer.json'
CLI = arquivos.CLI

AGENTES = ('claude-code', 'codex', 'cursor', 'antigravity', 'outro')
NOMES_FOCO = {
    'ativo': 'em foco',
    'passivo': 'em silêncio',
    'sob_demanda': 'fora de foco',
}

# Nomes compostos antigos (a migração e os prismas ainda não divididos usam) + as habilidades isoladas.
PALAVRAS_PADRAO = {
    'Domain-Driven Design (DDD)': ['Domain', 'Aggregate', 'ValueObject', 'Value Object', 'Entity', 'Repository', 'BoundedContext',
                                   'DomainEvent', 'agregado', 'objeto de valor', 'entidade', 'subdomínio', 'contexto delimitado', 'DDD'],
    'Arquitetura .NET / Clean Architecture': ['Interface', 'UseCase', 'Application', 'Infrastructure', 'DependencyInjection',
                                              'IServiceCollection', 'camada', 'injeção de dependência', 'desacopl', 'clean architecture'],
    'Testes e Qualidade / SQL': ['Test', 'xunit', 'Assert', 'Mock', 'Fact', 'teste', 'cobertura', 'SELECT', 'JOIN', 'índice'],
    'Back-end C# / .NET e Integrações': ['HttpClient', 'Controller', 'Integration', 'async Task', 'integração', 'endpoint', 'retry'],
    'Front-end (JS / Razor / React)': ['.cshtml', 'useState', 'fetch(', 'jQuery', 'componente', 'modal', 'razor'],
    'Programação Agêntica e Fluxo com IA': ['CLAUDE.md', 'AGENTS.md', '.claude', 'subagente', 'hook', 'skill', 'plan mode'],
    **prismas.PALAVRAS_PARTE,
}


def read_json(path: Path, default):
    return arquivos.ler_json(path, default)


def config() -> dict:
    return read_json(CFG, {'modo': 'ativo', 'autorizados': [], 'agente': 'claude-code'})


def definir_modo(modo: str) -> dict:
    cfg = config()
    cfg['modo'] = modo
    arquivos.gravar_json(CFG, cfg)
    return cfg




def plano() -> dict:
    return trajetoria.plano(banco.ESPERA_CURTA_MS)


def lacunas(plan: dict) -> dict[str, dict]:
    """Prismas (skills) com lacuna (nível < meta), com palavras do banco + do plano + padrão em português."""
    with trajetoria.abrir(banco.ESPERA_CURTA_MS) as con:
        niveis = jogo.niveis(plan, con)
        do_banco = {p['nome']: p['palavras'] for p in trajetoria.prismas(con)}
    out = {}
    for nome, v in niveis.items():
        if v['nivel'] >= v['meta']:
            continue
        s = next((x for x in plan.get('skills', []) if x['nome'] == nome), {})
        palavras = (do_banco.get(nome) or []) + (s.get('palavras_chave') or []) + PALAVRAS_PADRAO.get(nome, [])
        out[nome] = {'palavras': list(dict.fromkeys(str(w) for w in palavras if w)), 'nivel': v['nivel'], 'meta': v['meta']}
    return out or {k: {'palavras': p, 'nivel': None, 'meta': None} for k, p in PALAVRAS_PADRAO.items()
                   if not prismas.composto(k)}  # sem trajetória: só habilidades isoladas


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


# ------------------------------------------------------------------ foco sem hooks (comando `foco` da CLI)
LIMITE_DIFF = 200_000


def sessao_do_foco(cwd: str, sessao: str = '') -> str:
    """Id da sessão do `foco`: o informado, ou um id diário por pasta (um reconhecimento por prisma por dia e pasta)."""
    bruto = sessao or f"foco|{cwd.replace(chr(92), '/').lower()}|{date.today().isoformat()}"
    return sessao_id({'session_id': bruto})


def _git(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', cwd, *args], capture_output=True, timeout=20, encoding='utf-8', errors='replace')


def adicionado_nos_arquivos(caminhos: list[str], cwd: str) -> str:
    """Só as linhas **acrescentadas** pelo `git diff` dos caminhos (contra o HEAD; arquivo novo conta inteiro) + os nomes.

    O código é lido em memória e nunca gravado. Levanta RuntimeError com a mensagem para a pessoa se não for um repositório git.
    """
    try:
        dentro = _git(cwd, 'rev-parse', '--is-inside-work-tree')
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f'não consegui rodar o git ({type(e).__name__})') from e
    if dentro.returncode != 0:
        raise RuntimeError('esta pasta não é um repositório git: o foco lê as mudanças pelo git diff')
    partes = [_git(cwd, 'diff', 'HEAD', '--unified=0', '--no-color', '--', *caminhos).stdout
              or _git(cwd, 'diff', '--unified=0', '--no-color', '--', *caminhos).stdout]  # repositório sem commits: só o diff do índice
    novos = [c for c in _git(cwd, 'ls-files', '--others', '--exclude-standard', '--', *caminhos).stdout.splitlines() if c]
    for novo in novos:  # arquivo ainda fora do git: o diff contra o vazio é o arquivo todo
        partes.append(_git(cwd, 'diff', '--no-index', '--unified=0', '--no-color', '--', os.devnull, novo).stdout)
    linhas = [l[1:] for texto in partes for l in texto.splitlines() if l.startswith('+') and not l.startswith('+++')]
    nomes = [Path(c).name for c in caminhos]
    return ' '.join(nomes + linhas)[:LIMITE_DIFF]


def situacao_do_foco(cwd: str) -> tuple[str, str]:
    """('ok' | 'fora_de_foco' | 'nao_autorizado', modo): confira antes de ler qualquer código ou prompt."""
    cfg = config()
    modo = cfg.get('modo', 'ativo')
    if not authorized(cwd, cfg):
        return 'nao_autorizado', modo
    return ('fora_de_foco' if modo == 'sob_demanda' else 'ok'), modo


def foco(origem: str, texto: str, cwd: str, sessao: str = '', ext: str = '') -> dict:
    """O mesmo reconhecimento dos hooks para agentes sem hooks (Antigravity, Codex, Cursor).

    `origem`: 'prompt' (texto do pedido da pessoa) ou 'agente' (o que o agente escreveu). Nada do texto é gravado.
    Devolve `situacao`, `modo`, `achados` (de `reconhecer_em`) e `gaps`.
    """
    situacao, modo = situacao_do_foco(cwd)
    if situacao != 'ok':
        return {'situacao': situacao, 'modo': modo, 'achados': [], 'gaps': {}}
    gaps = lacunas(plano())
    achados = reconhecer_em(texto, origem, sessao_do_foco(cwd, sessao), modo, 'prompt' if origem == 'prompt' else ext or 'arquivo',
                            'foco', gaps)
    return {'situacao': 'ok', 'modo': modo, 'achados': achados, 'gaps': gaps}


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


RUBRICA_LAMPEJO = ('rubrica 0-4 (0 não explicou, 1 descreveu o código, 2 explicou o porquê, 3 comparou com alternativa, '
                   '4 ligou ao conceito e aos trade-offs)')


def reconhecer_em(texto: str, origem: str, sid: str, modo: str, ext: str, ferramenta: str, gaps: dict) -> list[dict]:
    """O reconhecimento do foco, uma só implementação (hooks e comando `foco`).

    `origem` é 'prompt' (a pessoa dirigiu o conceito: luz própria, +20) ou 'agente' (o agente aplicou: luz refletida, +10).
    Vale uma vez por prisma por sessão e por origem, dentro do teto de 40 lm passivos por prisma por dia. Só no modo `ativo`
    o primeiro reconhecimento da mudança com lúmens abre um lampejo. Devolve só o que rendeu lúmens, com o valor real:
    `skill`, `lm`, `luz`, `lampejo` (True se abriu), `provisorio` (True se o banco estava ocupado e o valor não foi confirmado).
    """
    tipo = 'prompt' if origem == 'prompt' else 'refletida'
    achados, abriu = [], False
    for skill in detectar(texto, gaps):
        quer = modo == 'ativo' and tipo == 'refletida' and not abriu  # só o primeiro vira luz própria, uma vez
        estado: dict = {}
        lm = jogo.reconhecer(sid, origem if tipo == 'prompt' else 'agente', skill, tipo, ext, ferramenta, modo,
                             interveio=quer or (tipo == 'prompt' and modo == 'ativo'), lampejo=quer, estado=estado)
        if not lm:  # None: este prisma já foi reconhecido na sessão; 0: teto do dia cheio (nada a mostrar)
            continue
        abriu = abriu or quer
        achados.append({'skill': skill, 'lm': lm, 'luz': 'propria' if tipo == 'prompt' else 'refletida',
                        'lampejo': quer, 'provisorio': bool(estado.get('provisorio'))})
    return achados


def nivel_txt(info: dict) -> str:
    return f"você {info.get('nivel')} → meta {info.get('meta')}" if info.get('nivel') is not None else 'lacuna da trajetória'


def cartao_refletida(skill: str, pergunta: str = '<a pergunta>', nivel: str = 'lacuna da trajetória', lm: int = 10,
                     provisorio: bool = False) -> str:
    if provisorio:  # banco ocupado: o valor e o lampejo ainda não foram confirmados, então não convida a responder
        return (f'[Luzia · em foco · luz refletida] O código que você (agente) acabou de escrever aplica o prisma {skill} ({nivel}). '
                f'Rendeu +{lm} lm de luz REFLETIDA para a pessoa, a confirmar (o banco estava ocupado; a Luzia confirma na próxima '
                'gravação). Termine a tarefa normalmente e, no FIM, em UMA linha, sem fazer perguntas: '
                f'"✦ Centelha da sessão · {prismas.nome_curto(skill)} · +{lm} lm refletida (a confirmar)"')
    return (
        f'[Luzia · em foco · luz refletida] O código que você (agente) acabou de escrever aplica o prisma {skill} ({nivel}). Isso rendeu '
        f'+{lm} lm de luz REFLETIDA para a pessoa: quem aplicou foi o agente. Termine a tarefa normalmente. No FIM da resposta, '
        'mostre esta centelha da sessão em no máximo 3 linhas:\n'
        f'✦ Centelha da sessão · {prismas.nome_curto(skill)} · +{lm} lm refletida\n'
        '<1 linha: onde o conceito aparece concretamente nesta mudança>\n'
        f'▸ Em 1 frase: {pergunta} (até +30 lm própria)\n'
        'Depois, use AskUserQuestion com "Responder agora" e "Guardar". Responder: espere a frase, avalie pela '
        f'{RUBRICA_LAMPEJO}, dê retorno em 1 linha e rode: {CLI} lampejo --skill "{skill}" --pergunta "<a pergunta>" '
        f'--nota <0-4> --resumo "<1 linha do que a pessoa explicou>". Guardar: rode {CLI} lampejo --skill "{skill}" '
        '--pergunta "<a pergunta>".'
    )


@sem_quebrar
def ao_enviar_prompt(event: dict, cfg: dict) -> None:
    """UserPromptSubmit: luz própria quando você dirige o conceito; e a fila do painel."""
    sid, modo = sessao_id(event), cfg.get('modo', 'ativo')
    partes = []
    if modo != 'sob_demanda':
        gaps = lacunas(plano())
        for r in reconhecer_em(event.get('prompt', ''), 'prompt', sid, modo, 'prompt', 'prompt', gaps):
            if modo == 'ativo':
                partes.append(f'[Luzia · em foco · luz própria] A pessoa DIRIGIU o prisma "{r["skill"]}" neste pedido (+{r["lm"]} lm de luz própria). '
                              f'Responda normalmente e, no FIM, em UMA linha: "✦ Luzia · {prismas.nome_curto(r["skill"])}: você dirigiu isto · +{r["lm"]} lm própria"')
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
            f'[Luzia · fila] A pessoa enviou do painel a centelha #{item["id"]} ("{item.get("titulo", "")}"). Responda primeiro ao '
            'que ela pediu. No FIM, em uma linha começando com "✦ Luzia:", lembre a centelha e use AskUserQuestion com '
            '"Abrir em sessão nova", "Fazer aqui" e "Depois". Sessão nova: rode '
            f'`{CLI} prompt {item["id"]} --onde "sessão nova"` e abra uma sessão/agente novo com esse texto pela ferramenta do seu '
            f'harness (se não houver, faça aqui). Fazer aqui: rode `{CLI} fazer {item["id"]} --onde aqui` e siga o roteiro.'
        )
    if partes:
        saida('UserPromptSubmit', '\n'.join(partes))


@sem_quebrar
def ao_usar_ferramenta(event: dict, cfg: dict) -> None:
    """PostToolUse: luz refletida quando o agente aplica um conceito da sua trajetória."""
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
    gaps = lacunas(plano())
    achados = reconhecer_em(texto, 'agente', sessao_id(event), modo, ext, tool, gaps)
    if modo != 'ativo' or not achados:
        return
    r = next((x for x in achados if x['lampejo']), achados[0])
    saida('PostToolUse', cartao_refletida(r['skill'], '<pergunta concreta de líder técnico sobre o porquê desta decisão>',
                                          nivel=nivel_txt(gaps.get(r['skill'], {})), lm=r['lm'], provisorio=r['provisorio']))


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
        partes.append(f"{', '.join(prontas)} pronto para subir de nível")
    if andamento:
        partes.append(f'centelha em andamento: "{andamento[0].get("titulo", "")}"')
    if fila:
        partes.append(f"{len(fila)} {'centelha' if len(fila) == 1 else 'centelhas'} na fila do painel")
    if partes:
        saida('SessionStart', f"[Luzia · em foco · início] {'; '.join(partes)}. Não interrompa o que a pessoa pedir. No FIM da sua "
                              'primeira resposta, em UMA linha: "✦ Luzia (em foco): <resumo curto disso> · /luzia:hoje para continuar."')


def main() -> None:
    try:  # o Claude Code envia UTF-8; o pipe do Windows usaria a página de código local e estragaria os acentos
        event = json.loads(sys.stdin.buffer.read().decode('utf-8', errors='replace'))
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
