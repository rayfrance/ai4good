"""Observador de sessão da Luzia (hooks do Claude Code, 100% local, sem chamar modelo).

Pega eventos de `SessionStart`, `UserPromptSubmit` e `PostToolUse` via stdin (JSON),
verifica se o repositório está autorizado, cruza o texto com as lacunas da trajetória
e devolve contexto curto para o Claude agir como a Luzia, dentro do foco escolhido:
- `ativo` ("em foco, com lampejos"): avisa quando o agente usa um conceito da lacuna (luz refletida +10 lm) ou quando a pessoa dirige (+20 lm).
- `passivo` ("em foco, em silêncio"): só registra lúmens e eventos no banco; não injeta lampejo no meio da sessão.
- `sob_demanda` ("fora de foco"): não observa; a Luzia só fala quando chamada por `/luzia:...`.

LGPD: nunca guarda o código nem o prompt bruto — só horário, prisma, extensão e modo.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import acoes, arquivos, banco, jogo, trajetoria

PRIVATE = arquivos.PRIVATE
CFG = PRIVATE / 'observer.json'
CONFIG = CFG

MODOS_VALIDOS = ('ativo', 'passivo', 'sob_demanda')
NOMES_FOCO = {
    'ativo': 'em foco, com lampejos',
    'passivo': 'em foco, em silêncio',
    'sob_demanda': 'fora de foco',
}

# Vocabulário técnico por prisma (usado quando o plano ainda não trouxe `palavras_chave`).
PALAVRAS_PADRAO: dict[str, list[str]] = {
    'ddd': ['aggregate', 'agregado', 'bounded context', 'value object', 'domain event', 'domain service', 'invariante', 'entidade de domínio'],
    'clean architecture': ['usecase', 'use case', 'application layer', 'domain layer', 'infrastructure', 'repository', 'injeção de dependência', 'inversion'],
    'arquitetura': ['clean architecture', 'camada', 'desacopl', 'interface', 'solid', ' controller', 'service', 'handler', 'dto'],
    'teste': ['xunit', 'nunit', 'mstest', '[fact]', '[theory]', 'moq', 'fluentassertions', 'assert.', 'mock', 'unit test', 'caso de borda'],
    'sql': ['select ', 'join ', 'group by', 'index ', 'migration', 'linq', 'ef core', 'dbcontext', 'query', 'transação'],
    'c#': ['async ', 'await ', 'ienumerable', 'iqueryable', ' cancellationtoken', 'middleware', 'httpclient', ' backgroundservice'],
    '.net': ['asp.net', 'program.cs', 'startup.cs', 'servicecollection', 'addscoped', 'addtransient', 'addsingleton'],
    'front': ['react', 'usestate', 'useeffect', 'component', 'razor', '.cshtml', 'fetch(', 'addeventlistener', ' viewmodel'],
}

PERGUNTAS_PADRAO: dict[str, str] = {
    'ddd': 'Qual regra de negócio aqui pertence ao domínio e ficaria protegida mesmo se a tela ou o banco mudassem?',
    'arquitetura': 'Se a regra principal desta mudança trocar amanhã, você mexe em um lugar só ou em mais de uma camada?',
    'teste': 'Qual caso de borda desta mudança quebraria em produção se ninguém testar agora?',
    'sql': 'Esta consulta ou mudança de dados continua rápida e inteira se o volume crescer dez vezes?',
    'c#': 'Se a chamada externa desta mudança falhar ou demorar, o que acontece com o fluxo principal?',
    'front': 'A regra que está nesta tela mora só aqui ou ficou dividida com o back-end?',
}


def config() -> dict:
    cfg = arquivos.ler_json(CONFIG, {})
    modo = cfg.get('modo', 'ativo')
    return {
        'modo': modo if modo in MODOS_VALIDOS else 'ativo',
        'autorizados': [str(Path(p).resolve()) for p in cfg.get('autorizados', [])],
    }


def salvar_modo(modo: str, autorizados: list[str] | None = None) -> dict:
    if modo not in MODOS_VALIDOS:
        raise ValueError(f'modo inválido: {modo}')
    atual = config()
    novo = {'modo': modo, 'autorizados': autorizados if autorizados is not None else atual['autorizados']}
    arquivos.gravar_json(CONFIG, novo)
    return novo


def autorizado(cwd: str, cfg: dict) -> bool:
    if not cwd or not cfg.get('autorizados'):
        return False
    try:
        atual = Path(cwd).resolve()
    except OSError:
        return False
    for base in cfg['autorizados']:
        try:
            b = Path(base).resolve()
            if atual == b or b in atual.parents:
                return True
        except OSError:
            continue
    return False


def plano() -> dict:
    return trajetoria.plano(banco.ESPERA_CURTA_MS)


def _chave_padrao(nome_skill: str) -> str:
    s = nome_skill.lower()
    for k in ('ddd', 'clean architecture', 'arquitetura', 'teste', 'sql', 'c#', '.net', 'front'):
        if k in s:
            return 'arquitetura' if k == 'clean architecture' else ('c#' if k == '.net' else k)
    return ''


def lacunas(plan: dict) -> dict[str, dict]:
    """Prismas ativos com nível < meta (os que merecem atenção do observador)."""
    out: dict[str, dict] = {}
    nv = jogo.niveis(plan, espera_ms=banco.ESPERA_CURTA_MS)
    palavras_plano = {s.get('nome', ''): list(s.get('palavras_chave') or []) for s in plan.get('skills', [])}
    palavras_banco: dict[str, list[str]] = {}
    try:
        with trajetoria.abrir(banco.ESPERA_CURTA_MS) as con:
            for p in trajetoria.prismas(con):
                palavras_banco[p['nome']] = list(p.get('palavras') or [])
    except Exception as e:
        arquivos.registrar_erro('observer.lacunas prismas', e)
    for nome, info in nv.items():
        atual, meta = info['nivel'], info['meta']
        if atual >= meta:
            continue
        chave = _chave_padrao(nome)
        palavras = list(palavras_plano.get(nome) or []) + list(palavras_banco.get(nome) or []) + PALAVRAS_PADRAO.get(chave, [])
        seen: set[str] = set()
        limpas = [p.lower() for p in palavras if p and not (p.lower() in seen or seen.add(p.lower()))]
        if limpas:
            out[nome] = {
                'nivel': atual,
                'meta': meta,
                'palavras': limpas,
                'pergunta': PERGUNTAS_PADRAO.get(chave, f'Por que esta decisão em {nome} foi feita assim e qual seria a alternativa?'),
            }
    return out


def detectar(texto: str, lac: dict[str, dict]) -> tuple[str, dict, str] | None:
    """Devolve (nome_prisma, info, termo_encontrado) para a primeira lacuna que aparece no texto."""
    t = texto.lower()
    for nome, info in lac.items():
        for p in info['palavras']:
            padrao = r'(?<![\w])' + re.escape(p.strip()) + r'(?![\w])'
            if re.search(padrao, t):
                return nome, info, p.strip()
    return None


def saida_hook(evento: str, contexto: str) -> None:
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': evento,
            'additionalContext': contexto,
        }
    }, ensure_ascii=False))


def ao_iniciar_sessao(evento: dict, cfg: dict) -> None:
    if cfg['modo'] == 'sob_demanda':
        return
    plan = plano()
    lac = lacunas(plan)
    resumo = ', '.join(f"Prisma {n} ({v['nivel']}→{v['meta']})" for n, v in list(lac.items())[:3])
    partes = []
    if resumo:
        partes.append(f"Luzia ({NOMES_FOCO.get(cfg['modo'], 'em foco')}): prismas (skills) em desenvolvimento nesta trajetória: {resumo}.")
    try:
        with trajetoria.abrir(banco.ESPERA_CURTA_MS) as con:
            r = jogo.rota(plan, con)
            andamento = jogo.avancos(con, estado='em_andamento', historico=False)
            pendentes = acoes.fila(banco.ESPERA_CURTA_MS)
        prontos = [s['nome'] for s in r['skills'] if s['pronto'] and not s['na_meta']]
    except Exception as e:
        arquivos.registrar_erro('observer.ao_iniciar_sessao', e)
        andamento, prontos, pendentes = [], [], []
    if prontos:
        partes.append(f"Nível pronto para confirmar em Prisma {prontos[0]} (o nível só muda com o sim da pessoa em /luzia:hoje).")
    if andamento:
        partes.append(f"Avanço em andamento: #{andamento[0]['id']} \"{andamento[0].get('titulo', '')}\".")
    if pendentes:
        nomes = ', '.join(f"#{x['id']} \"{x.get('titulo', '')}\"" for x in pendentes[:2])
        partes.append(f"A pessoa enviou do painel para fazer aqui: {nomes}.")
    if len(partes) > 1:
        partes.append(
            '[Luzia · início] Na sua PRIMEIRA resposta desta sessão, depois de responder ao que a pessoa pediu, '
            'acrescente UMA linha curta lembrando o que está aberto e sugerindo `/luzia:hoje`.'
        )
    if partes:
        saida_hook('SessionStart', ' '.join(partes))


def ao_enviar_prompt(evento: dict, cfg: dict) -> None:
    if cfg['modo'] == 'sob_demanda':
        return
    sessao = str(evento.get('session_id', 'sem-sessao'))
    partes: list[str] = []

    try:
        nao_oferecidas = [x for x in acoes.fila(banco.ESPERA_CURTA_MS) if sessao not in x.get('oferecida_em', [])]
    except Exception as e:
        arquivos.registrar_erro('observer.ao_enviar_prompt fila', e)
        nao_oferecidas = []
    if nao_oferecidas:
        f = nao_oferecidas[0]
        try:
            acoes.marcar_oferecida(f['id'], sessao, banco.ESPERA_CURTA_MS)
        except Exception as e:
            arquivos.registrar_erro('observer.ao_enviar_prompt marcar_oferecida', e)
        partes.append(
            f"[Luzia · fila] A pessoa clicou no painel em \"Fazer no Claude Code\" para o avanço #{f['id']} "
            f"\"{f.get('titulo', '')}\". Depois de responder ao que ela escreveu agora, ofereça em botões "
            f"(AskUserQuestion): \"Abrir em sessão nova\" (recomendado), \"Fazer aqui\" ou \"Depois\". "
            f"Se ela escolher fazer, siga `/luzia:fazer {f['id']}`."
        )

    prompt = str(evento.get('prompt', ''))
    achado = detectar(prompt, lacunas(plano())) if len(prompt) >= 12 else None
    if achado:
        nome, info, _ = achado
        lm = jogo.reconhecer(sessao, 'prompt', nome, 'prompt', modo=cfg['modo'])
        if lm is not None and cfg['modo'] == 'ativo' and lm > 0:
            partes.append(
                f"[Luzia · luz própria +{lm} lm] A pessoa trouxe **{nome}** no próprio prompt "
                f"(Prisma {nome}, nível {info['nivel']}→{info['meta']}). Reconheça em uma linha curta no fim da resposta."
            )
    if partes:
        saida_hook('UserPromptSubmit', ' '.join(partes))


def _texto_ferramenta(nome_ferramenta: str, entrada: dict) -> tuple[str, str]:
    """Extrai o texto analisável e a extensão do arquivo, sem guardar caminho."""
    if nome_ferramenta in ('Write', 'Edit', 'MultiEdit'):
        caminho = str(entrada.get('file_path') or entrada.get('path') or '')
        ext = Path(caminho).suffix.lower() if caminho else ''
        partes = [
            str(entrada.get('content', '')),
            str(entrada.get('new_string', '')),
            ' '.join(str(e.get('new_string', '')) for e in entrada.get('edits', []) if isinstance(e, dict)),
        ]
        return ' '.join(partes), ext
    if nome_ferramenta == 'Bash':
        cmd = str(entrada.get('command', ''))
        if 'git commit' in cmd:
            return cmd, '.git-commit'
    return '', ''


def cartao_refletida(skill: str, pergunta: str, lm: int = 10) -> str:
    """Lampejo compacto de 3 linhas + ações pelo CLI da Luzia."""
    cli = arquivos.CLI
    sk = skill.replace('"', '')
    pg = pergunta.replace('"', "'")
    return (
        f"[Luzia · luz refletida +{lm} lm em Prisma {skill}] Você acabou de aplicar este prisma pela pessoa. "
        'Termine a tarefa normalmente e, no fim da resposta, mostre este lampejo de 3 linhas:\n'
        f'> **✦ Lampejo da Luzia · Prisma {skill}** (+{lm} lm de luz refletida · responda e ganhe até +30 lm de luz própria)\n'
        f'> _{pergunta}_\n'
        '> Responda em 1–2 linhas agora, ou diga **guardar** para virar um avanço seu.\n'
        'Em seguida, ofereça em botões (AskUserQuestion): "Responder agora" e "Guardar para depois". '
        f'Se ela responder agora, avalie pela rubrica 0–4 ({acoes.RUBRICA_TXT}) e rode '
        f'`{cli} lampejo "{sk}" --acao converter --nota <0-4>` (vale uma única vez por lampejo). '
        f'Se ela escolher guardar, rode `{cli} guardar "{sk}" --pergunta "{pg}"`.'
    )


def ao_usar_ferramenta(evento: dict, cfg: dict) -> None:
    if cfg['modo'] == 'sob_demanda':
        return
    ferramenta = str(evento.get('tool_name', ''))
    entrada = evento.get('tool_input') or {}
    if not isinstance(entrada, dict):
        return
    texto, ext = _texto_ferramenta(ferramenta, entrada)
    if len(texto) < 20:
        return
    achado = detectar(texto, lacunas(plano()))
    if not achado:
        return
    nome, info, _ = achado
    sessao = str(evento.get('session_id', 'sem-sessao'))
    interveio = cfg['modo'] == 'ativo'
    lm = jogo.reconhecer(sessao, 'agente', nome, 'refletida', extensao=ext, ferramenta=ferramenta,
                         modo=cfg['modo'], interveio=interveio, lampejo=interveio)
    if lm is not None and interveio:
        saida_hook('PostToolUse', cartao_refletida(nome, info['pergunta'], lm=lm))


def main() -> None:
    try:
        cru = sys.stdin.read()
        evento = json.loads(cru) if cru.strip() else {}
    except json.JSONDecodeError:
        return
    cfg = config()
    cwd = str(evento.get('cwd') or '')
    if not autorizado(cwd, cfg):
        return
    nome_ev = str(evento.get('hook_event_name', ''))
    if nome_ev == 'SessionStart':
        ao_iniciar_sessao(evento, cfg)
    elif nome_ev == 'UserPromptSubmit':
        ao_enviar_prompt(evento, cfg)
    elif nome_ev == 'PostToolUse':
        ao_usar_ferramenta(evento, cfg)


if __name__ == '__main__':
    main()
