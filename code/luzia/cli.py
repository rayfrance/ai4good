"""CLI da Luzia (agnóstica de harness; no Claude Code é chamada pelos comandos /luzia:*).

O jogo (docs/luzia-ux.md): avanços valem lúmens; lúmens enchem os níveis de cada prisma (skill); os níveis formam a trajetória até a meta.
- `hoje`, `triage`, `trajetoria` (`next-level`/`rota`), `entregas` (`feedback-progress`), `entrega <id>`, `feedback-skills-opportunities`
- `avancos` (`acoes`), `fila`, `fazer`/`prompt`/`revisitar <id>`, `registrar <id> --nota --resumo`, `descartar <id> --motivo`, `restaurar <id>`, `enviar <id>`
- `subir <prisma>`, `nivel <prisma> <N>`, `acender <prisma>` (`trecho`), `pedido <subacao> ...`, `dossie`, `cartao`, `guardar`, `career-map`, `modo`, `modelo`
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import acoes, arquivos, entregas, jogo, leituras, modelo, observer, pedidos, pipeline, planner, propriedade, trajetoria, triage
from .privacy import Redactor

PAINEL = 'http://localhost:8501'
MODOS = ('ativo', 'passivo', 'sob_demanda')
CLI = arquivos.CLI


def _vocab_novo(texto: str) -> str:
    """Converte termos internos legados para o vocabulário novo nas mensagens visíveis."""
    out = str(texto)
    for velho, novo in (
        ('este feixe', 'este avanço'),
        ('conquistar 1 feixe desta skill', 'conquistar 1 avanço deste prisma'),
        ('Feixe', 'Avanço'),
        ('feixes', 'avanços'),
        ('feixe', 'avanço'),
        ('Degrau', 'Nível'),
        ('degraus', 'níveis'),
        ('degrau', 'nível'),
        ('cartões', 'lampejos'),
        ('cartão', 'lampejo'),
    ):
        out = out.replace(velho, novo)
    return out


def espectro_txt(nivel: int, total: int = 5) -> str:
    n = max(0, min(total, int(nivel or 0)))
    return '▰' * n + '▱' * (total - n)


# ------------------------------------------------------------------ entradas e redação
def load_cfg(entrada_path: Path) -> dict:
    return json.loads(entrada_path.read_text(encoding='utf-8'))


def make_redactor(cfg: dict) -> Redactor:
    repo = Path(cfg['repo']) if cfg.get('repo') else None
    colleagues = triage.repo_authors(repo) if repo and repo.exists() else []
    return Redactor.from_file(pipeline.PRIVATE / 'termos.txt', extra_colleagues=colleagues)


def recent_commits(cfg: dict, redactor: Redactor, limit: int = 15) -> list[dict]:
    out = []
    if cfg.get('repo') and cfg.get('author') and Path(cfg['repo']).exists():
        for c in triage.my_commits(Path(cfg['repo']), cfg['author'], limit):
            out.append({
                'data': c.date, 'mensagem': redactor.redact(c.subject), 'arquivos': c.files,
                'linhas': f'+{c.insertions}/-{c.deletions}', 'areas': c.areas,
            })
    return out


def skills_summary(plan: dict) -> list[dict]:
    autoaval = jogo.autoavaliacao()
    return [
        {'nome': s['nome'], 'nivel': autoaval.get(s['nome'], s.get('autoavaliacao') or s.get('luzia_sugere')),
         'alvo': s.get('alvo')}
        for s in plan.get('skills', [])
    ]


def state_commits(state: dict) -> list[dict]:
    plan = state.get('plano', {})
    return (plan.get('_commits_dia') or []) + ((state.get('payload_anonimizado') or {}).get('commits_recentes') or [])


# ------------------------------------------------------------------ chamadas ao modelo
def execute_triage(entrada_path: Path, rotulo: str = 'plugin-triage', save_state: bool = True) -> tuple[dict, dict, dict]:
    pipeline.load_env()
    cfg = load_cfg(entrada_path)
    t0 = time.perf_counter()
    redactor = make_redactor(cfg)

    inputs = dict(cfg)
    inputs['cv_text'] = triage.read_pdf(Path(cfg['cv_pdf'])) if cfg.get('cv_pdf') else ''
    inputs['linkedin_text'] = triage.read_pdf(Path(cfg['linkedin_pdf'])) if cfg.get('linkedin_pdf') else ''
    inputs['github_data'] = {}
    if cfg.get('github'):
        try:
            inputs['github_data'] = triage.github_profile(cfg['github'])
        except Exception:
            inputs['github_data'] = {}
    if cfg.get('incluir_historico_ia', True):
        inputs['ai_history'] = triage.shared_ai_history(vault_dir=Path(cfg.get('vault', r'C:\Repositorio\Cerebro_Rayane')))
    else:
        inputs['ai_history'] = {}

    payload = pipeline.build_payload(inputs, redactor)
    result, record = pipeline.run_plan(
        payload, prep_seconds=time.perf_counter() - t0, label=rotulo, hits=dict(redactor.hits),
        save_current_state=save_state,
    )
    return result.plan, record, dict(redactor.hits)


def daily_call(kind: str, entrada_path: Path, rotulo: str) -> tuple[dict, dict, dict]:
    """Chamada leve do dia a dia: plano salvo + memória viva (commits, sessão e evidências)."""
    pipeline.load_env()
    plan = pipeline.load_state().get('plano', {})
    cfg = load_cfg(entrada_path)
    t0 = time.perf_counter()
    redactor = make_redactor(cfg)
    payload = {
        'objetivo': plan.get('aonde_quer_chegar', {}),
        'skills': skills_summary(plan),
        'eventos_sessao': pipeline.session_events(),
        'evidencias_registradas': [
            {k: e.get(k) for k in ('entrega', 'dimensao', 'nota', 'skill')} for e in acoes.evidencias()
        ],
        'feixes_descartados_pela_pessoa': jogo.motivos_descartados(),
    }
    if kind == 'progress':
        payload['commits_recentes'] = recent_commits(cfg, redactor)
        schema, intro = planner.PROGRESS_SCHEMA, 'Plano salvo + commits recentes da pessoa (anonimizados por LGPD):'
    else:
        schema, intro = planner.OPPORTUNITIES_SCHEMA, 'Plano salvo + eventos mascarados da sessão atual no agente:'
    result, record = pipeline.run_plan(
        payload, prep_seconds=time.perf_counter() - t0, label=rotulo, hits=dict(redactor.hits),
        schema=schema, intro=intro,
    )
    if kind == 'progress':
        pipeline.update_state({'tarefas_recentes': result.plan.get('tarefas_recentes', []),
                               '_commits_dia': payload['commits_recentes']}, record)
    else:
        pipeline.update_state({'oportunidades_tarefa_atual': result.plan.get('oportunidades_tarefa_atual', [])}, record)
    return result.plan, record, dict(redactor.hits)


def gerar_trecho(skill: str, rotulo: str = 'cmd-trecho') -> dict:
    """Acende 3 avanços novos para um prisma (depois de subir um nível ou quando ele fica sem avanço aberto)."""
    pipeline.load_env()
    plan = pipeline.load_state().get('plano', {})
    skill = jogo.skill_de(skill, plan)
    nv = jogo.niveis(plan).get(skill)
    if not nv:
        return {'erro': 'prisma não encontrado na sua trajetória'}
    if nv['nivel'] >= nv['meta']:
        return {'erro': 'este prisma já está na meta'}
    t0 = time.perf_counter()
    s = next((x for x in plan.get('skills', []) if x['nome'] == skill), {})
    existentes = [f for f in acoes.todas(plan, descartados=True) if (f.get('skill_plano') or f.get('skill')) == skill]
    payload = {
        'objetivo': plan.get('aonde_quer_chegar', {}),
        'skill': {'nome': skill, 'nivel': nv['nivel'], 'para': nv['nivel'] + 1, 'meta': nv['meta'], 'evidencia': s.get('evidencia', '')},
        'feixes_existentes': [{'titulo': f.get('titulo'), 'estado': f.get('estado')} for f in existentes],
        'feixes_descartados_pela_pessoa': [m for m in jogo.motivos_descartados() if jogo.skill_de(m.get('skill') or '', plan) == skill],
    }
    result, record = pipeline.run_plan(payload, prep_seconds=time.perf_counter() - t0, label=rotulo,
                                       schema=planner.TRECHO_SCHEMA,
                                       intro='Trajetória salva da pessoa e o prisma que precisa de 3 novos avanços:')
    novas = [a for a in result.plan.get('acoes', []) if isinstance(a, dict) and a.get('titulo')][:3]
    if not novas:
        return {'erro': 'o modelo não devolveu avanços; tente de novo'}
    trechos = plan.get('trechos', []) + [{'skill': skill, 'para': nv['nivel'] + 1, 'quando': record['quando'], 'acoes': novas}]
    pipeline.update_state({'trechos': trechos}, record)
    plan = pipeline.load_state().get('plano', {})
    ids = {acoes.aid('trecho', skill + a.get('titulo', '')) for a in novas}
    gerados = [f for f in acoes.todas(plan) if f['id'] in ids]
    return {'skill': skill, 'prisma': skill, 'feixes': gerados, 'avancos': gerados, 'record': record}


gerar_acender = gerar_trecho


# ------------------------------------------------------------------ apresentação
def bar(value, total: int = 5, width: int = 5) -> str:
    value = max(0, min(total, int(value or 0)))
    filled = round(value / total * width)
    return '█' * filled + '░' * (width - filled)


def footer(rec: dict, hits: dict | None = None) -> None:
    masked = sum((hits or {}).values())
    print(
        f"\n`{rec['tempo_total_s']} s · {rec['pico_memoria_mib']} MiB · {rec['tokens_entrada']}→{rec['tokens_saida']} tokens"
        f" · {masked} itens mascarados · {rec.get('modelo', '')} · versão {rec['versao']}`"
    )


def curto(nome: str, n: int = 44) -> str:
    base = (nome or '').split('(')[0].strip()
    return base if len(base) <= n else base[: n - 1] + '…'


# ------------------------------------------------------------------ botões (protocolo para qualquer agente)
def botoes(itens: list[dict], pergunta: str = 'O que você quer fazer agora?') -> None:
    vistos, lista = set(), []
    for b in itens:
        if b and b['rodar'] not in vistos:
            vistos.add(b['rodar'])
            lista.append(b)
    if not lista:
        lista = [BT_PAINEL]
    print(f'\nLUZIA_CLI={CLI}')
    print(f'LUZIA_PERGUNTA={pergunta}')
    print('LUZIA_BOTOES=' + json.dumps(lista[:3], ensure_ascii=False))


def bt_feixe(f: dict, prefixo: str = '') -> dict:
    return {'rotulo': (prefixo + f.get('titulo', ''))[:48],
            'descricao': f"{f.get('tipo', '')} · Prisma {curto(f.get('skill_plano') or f.get('skill', ''))} · {f.get('duracao_min', '?')} min · {f.get('valor_lm')} lm",
            'rodar': f"fazer {f['id']}"}


bt_avanco = bt_feixe
BT_PAINEL = {'rotulo': 'Abrir o painel', 'descricao': 'trajetória, avanços e entregas no navegador', 'rodar': 'career-map'}
BT_TRAJETORIA = {'rotulo': 'Ver minha trajetória', 'descricao': 'prismas, níveis e lúmens até a meta', 'rodar': 'trajetoria'}


def proximos_botoes(plan: dict, excluir: set | tuple = ()) -> list[dict]:
    """O que faz sentido agora, em ordem: subir nível pronto, continuar, fila, revisitar, acender, próximo avanço."""
    r = jogo.rota(plan)
    lista = [f for f in acoes.todas(plan) if f['id'] not in excluir]
    fila_ids = [x['id'] for x in acoes.fila()]
    bts = [{'rotulo': f"Subir {curto(s['nome'])} para {s['proximo']}",
            'descricao': f"nível pronto: {s['lm']} lm, {s['luz_propria']}% luz própria · você confirma",
            'rodar': f'subir "{s["nome"]}"'} for s in r['skills'] if s['pronto'] and not s['na_meta']]
    bts += [bt_feixe(f, 'Continuar: ') for f in lista if f['estado'] == 'em_andamento'][:1]
    bts += [bt_feixe(f) for f in lista if f['id'] in fila_ids][:1]
    bts += [{'rotulo': f"Revisitar: {f.get('titulo', '')}"[:48],
             'descricao': f"buscar o restante: você levou {f.get('lm_ganho')} de {f.get('valor_lm')} lm",
             'rodar': f"fazer {f['id']}"} for f in lista if jogo.pode_revisitar(f)][:1]
    abertos = {f.get('skill_plano') or f.get('skill') for f in lista if f['estado'] in ('sugerido', 'na_fila', 'em_andamento')}
    bts += [{'rotulo': f"Acender avanços de {curto(s['nome'])}"[:48],
             'descricao': f"3 avanços novos para o nível {s['proximo']} (o modelo leva ~10 s)",
             'rodar': f'trecho "{s["nome"]}"'} for s in r['skills'] if not s['na_meta'] and s['nome'] not in abertos][:1]
    bts += [bt_feixe(f) for f in lista if f['estado'] == 'sugerido']
    return bts or [BT_PAINEL]


ESTADO_IC = {'conquistado': '✦', 'em_andamento': '◐', 'na_fila': '➤', 'sugerido': '○', 'descartado': '✕'}


def feixe_linha(f: dict) -> str:
    extra = f" · nota {f.get('nota')}/4 · +{f.get('lm_ganho')} lm" if f.get('estado') == 'conquistado' else ''
    tent = f" · tentativa {f.get('tentativas') + 1}" if f.get('tentativas') and f.get('estado') != 'conquistado' else ''
    sk = f.get('skill_plano') or f.get('skill', '')
    return (f"{ESTADO_IC.get(f.get('estado'), '○')} `#{f['id']}` **{f.get('titulo', '')}** · {f.get('tipo', '')} · "
            f"Prisma {curto(sk)} · {f.get('duracao_min', '?')} min · **{f.get('valor_lm', '?')} lm**{extra}{tent}")


def oferecer(lista: list[dict], pergunta: str = 'Qual avanço você quer fazer agora?') -> None:
    botoes([bt_feixe(a) for a in lista if a.get('estado') not in ('conquistado', 'descartado')] or [BT_PAINEL], pergunta)


def linha_rota(plan: dict, state: dict | None = None) -> dict:
    r = jogo.rota(plan)
    ini, fim = pipeline.rotulos(state or pipeline.load_state())
    luz = '━' * round(20 * r['pct'] / 100)
    print(f"**Trajetória** {ini} {luz}◉{'─' * (20 - len(luz))} {fim} · **{r['niveis_feitos']} de {r['niveis_total']} níveis** · "
          f"{r['lm_total']} lm · {r['luz_propria']}% luz própria")
    return r


def rota_texto(plan: dict, state: dict | None = None) -> None:
    r = linha_rota(plan, state)
    with trajetoria.abrir() as con:
        leit_map = {s['nome']: leituras.obter(con, 'prisma', s['nome']) for s in r['skills']}
    for idx, s in enumerate(r['skills']):
        rotulo_p = f"Prisma {s['nome']} (prisma (skill))" if idx == 0 else f"Prisma {s['nome']}"
        esp = espectro_txt(s['nivel'])
        if s['na_meta']:
            print(f"   ✦ {rotulo_p} · `{esp}` nível {s['nivel']}/{s['meta']} · na meta")
            continue
        pronto = ' · **nível pronto para subir**' if s['pronto'] else f" · falta: {_vocab_novo(', '.join(s['falta']))}"
        print(f"   {rotulo_p} · `{esp}` nível {s['nivel']} → meta {s['meta']}  `{bar(min(s['lm'], s['limiar']), s['limiar'], 10)}` "
              f"{s['lm']}/{s['limiar']} lm · luz própria {s['luz_propria']}%{pronto}")
        print('      ' + leitura_txt(leit_map.get(s['nome'])))


def propriedade_entregas(state: dict) -> list[dict]:
    plan = state.get('plano', {})
    commits = state_commits(state)
    evs = acoes.evidencias()
    return [{**t, **propriedade.entrega(t, commits, plan.get('p1_direcao_prompt'), evs)} for t in plan.get('tarefas_recentes', [])]


def print_entrega(e: dict, todas: list[dict]) -> None:
    idx = e['indice']
    print(f"\n▸ **{e['tarefa']}** · propriedade **{idx if idx is not None else '—'}%** · medida em {e['base']}")
    print('   ' + ' · '.join(f"{k} {d['nota']} ({d['tipo']})" if d else f'{k} sem base' for k, d in e['dimensoes'].items()))
    for a in todas:
        if a.get('origem') == 'entrega' and a.get('entrega') == e['tarefa']:
            print(f'   {feixe_linha(a)}' + (f" → acende {a['dimensao']}" if a.get('dimensao') else ''))


def base_resumo(alvo_tipo: str | None, base: dict | None) -> str:
    """Os fatos que fundamentaram uma leitura, em uma linha (o que vai depois de "com base em")."""
    b = base if isinstance(base, dict) else {}
    if alvo_tipo == 'prisma':
        lm = b.get('lumens') or {}
        return (f"nível {b.get('nivel', '?')}/{b.get('meta', '?')}, {lm.get('total', 0)} lm "
                f"({lm.get('propria', 0)} de luz própria), {len(b.get('avancos_conquistados') or [])} avanço(s) "
                f"conquistado(s) e {b.get('entregas_total', 0)} entrega(s) do prisma")
    if alvo_tipo == 'entrega':
        f = b.get('fatos') or {}
        return (f"{f.get('commits', 0)} commit(s), {f.get('arquivos', 0)} arquivo(s), {f.get('linhas', 0)} linhas e "
                f"{len(b.get('prismas') or [])} prisma(s) atravessado(s) da entrega")
    if alvo_tipo == 'pedido':
        return (f"o pedido ({b.get('tipo', '')} em Prisma {b.get('prisma', '')}) e a trajetória atual "
                f"({len(b.get('prismas_ativos') or [])} prisma(s) ativo(s))")
    return 'os fatos medidos pela Luzia'


def motivo_sem_leitura() -> str:
    return ('a Luzia ainda não tem base para uma leitura' if modelo.pronto()
            else 'leitura indisponível: configure o modelo (`modelo`, ou Ajustes no painel)')


def leitura_txt(leit: dict | None, base_txt: str | None = None, indisponivel: str = '') -> str:
    """Toda leitura de IA na tela: texto + "com base em" + modelo + data; sem leitura, diz por quê (nunca vazio)."""
    if leit and leit.get('texto') and leit.get('modelo'):
        base_txt = base_txt or base_resumo(leit.get('alvo_tipo'), leit.get('base'))
        venc = ' · a base mudou desde então' if leit.get('vencida') else ''
        return (f"_Leitura da Luzia · com base em: {base_txt} · {leit['modelo']} · "
                f"{str(leit.get('criado_em') or '')[:10]}{venc}:_ {leit['texto']}")
    return f"_Leitura da Luzia: {indisponivel or motivo_sem_leitura()}._"


NOME_DIMENSAO = {'P1': 'direção no prompt', 'P2': 'coesão da entrega', 'P3': 'aplicação conceitual',
                 'P4': 'domínio arquitetural'}
SEM_BASE_DIMENSAO = {'P1': 'sem base — a triagem ainda não leu seus prompts',
                     'P2': 'sem base — a entrega não tem commits medidos',
                     'P3': 'sem base — acende quando você explica o conceito num avanço desta entrega',
                     'P4': 'sem base — acende quando você defende a decisão num avanço desta entrega'}


def linhas_propriedade(prop: dict) -> list[str]:
    """P1–P4 de uma entrega com a base de cada nota (o mesmo que o painel mostra)."""
    indice = prop.get('indice')
    out = [f"- **Propriedade na entrega:** **{f'{indice}%' if indice is not None else '—'}** · "
           f"medida em {prop.get('base') or '0 de 4 dimensões'}"]
    for k in ('P1', 'P2', 'P3', 'P4'):
        d = (prop.get('dimensoes') or {}).get(k)
        if d:
            out.append(f"   - {k} · {NOME_DIMENSAO[k]}: **{d['nota']}** ({d.get('tipo', '')}) — {d.get('base', '')}")
        else:
            out.append(f"   - {k} · {NOME_DIMENSAO[k]}: {SEM_BASE_DIMENSAO[k]}")
    return out


def avisar_degraus(plan: dict) -> None:
    for s in jogo.rota(plan)['skills']:
        if s['pronto'] and not s['na_meta']:
            print(f"\n✦ **Prisma {s['nome']}** está pronto para subir para o nível {s['proximo']} "
                  f"({s['lm']} lm, {s['luz_propria']}% luz própria). Você decide quando.")


# ------------------------------------------------------------------ painel
def panel_up() -> bool:
    try:
        with urllib.request.urlopen(PAINEL + '/api/ping', timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start_panel() -> None:
    server = Path(__file__).resolve().parent / 'server.py'
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    subprocess.Popen(
        [sys.executable, str(server)], cwd=str(pipeline.ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=flags,
    )
    for _ in range(20):
        if panel_up():
            return
        time.sleep(0.3)


def set_mode(modo: str) -> None:
    observer.salvar_modo(modo)


def roteiro(a: dict) -> None:
    revisita = a.get('estado') == 'conquistado'
    print(f"## ✦ Luzia · {'revisita do ' if revisita else ''}avanço `#{a['id']}` · **{a.get('valor_lm')} lm**")
    print(f"**{a.get('titulo', '')}** · {a.get('tipo', '')} · Prisma {curto(a.get('skill_plano') or a.get('skill', ''))} · {a.get('duracao_min', '?')} min")
    if revisita:
        print(f"Você levou {a.get('lm_ganho')} de {a.get('valor_lm')} lm (nota {a.get('nota')}/4). Nesta revisita vale só a diferença.")
    else:
        print('Vale: ' + ' + '.join(f"{c[0]} {c[2]} ({c[1]})" for c in a.get('conta', [])))
    if a.get('entrega'):
        print(f"▸ entrega: {a['entrega']}" + (f" · acende {a['dimensao']}" if a.get('dimensao') else ''))
    print(f"\n**Por quê:** {a.get('por_que', '')}")
    print(f"**Conceitos:** {', '.join(a.get('conceitos', []))}")
    print('**Como:**')
    for i, p in enumerate(a.get('como', []), 1):
        print(f'{i}. {p}')
    print(f"**Onde explorar no repositório:** {a.get('onde_explorar', '')}")
    print('\n---\nROTEIRO PARA O AGENTE (conduza como a Luzia, sem fazer o trabalho no lugar da pessoa):')
    print('1. Mostre o avanço acima de forma curta e visual, com o valor em lúmens.')
    print(f"2. Siga este pedido da pessoa: «{a.get('prompt', '')}»")
    print('3. Faça UMA pergunta por vez e espere a resposta. Se a ação pede explorar o repositório, mostre só 2 lugares.')
    print('4. Avalie a resposta final pela rubrica 0–4: ' + ' · '.join(f'{k} = {v}' for k, v in propriedade.RUBRICA.items())
          + '. Valor ganho: 4 = 100%, 3 = 75%, 2 = 50%, 0–1 = tente de novo.')
    print('5. Diga a nota e o porquê em uma linha, com um ponto forte e um próximo passo.')
    print(f'6. Registre: {CLI} registrar {a["id"]} --nota <0-4> --resumo "<1 linha do que a pessoa demonstrou, sem nomes da empresa>"')
    print('7. A saída do registrar termina com LUZIA_BOTOES: ofereça esses botões como próxima ação.')


def hoje(plan: dict, state: dict) -> None:
    """Ponto de partida: onde você está agora e os próximos passos em botões."""
    print('## ✦ Luzia · hoje')
    r = linha_rota(plan, state)
    lista = acoes.todas(plan)
    hoje_lm = sum(x['lm'] for x in jogo.livro(desde=jogo.agora()[:10]))
    andamento = sum(1 for f in lista if f['estado'] == 'em_andamento')
    prontas = [curto(s['nome']) for s in r['skills'] if s['pronto'] and not s['na_meta']]
    partes = [f'+{hoje_lm} lm hoje']
    if andamento:
        partes.append(f"{andamento} avanço{'s' if andamento > 1 else ''} em andamento")
    if acoes.fila():
        partes.append(f'{len(acoes.fila())} na fila')
    if prontas:
        partes.append(f"{', '.join(prontas)} pronta{'s' if len(prontas) > 1 else ''} para subir de nível")
    print('Agora: ' + ' · '.join(partes))
    perto = sorted((s for s in r['skills'] if not s['na_meta'] and s['lm']), key=lambda s: (-s['lm'], s['nome']))[:3]
    if perto:
        print('Mais perto do próximo nível: ' + ' · '.join(
            f"Prisma {curto(s['nome'])} {s['lm']}/{s['limiar']} lm" + ('' if s['feixes'] else ' (falta 1 avanço)') for s in perto))
    else:
        print('Nenhum lúmen ainda: o primeiro avanço conquistado acende a trajetória.')
    botoes(proximos_botoes(plan) + [BT_PAINEL], 'Por onde seguimos?')


def _botoes_pedido(pid: int, p: dict) -> list[dict]:
    prop = p.get('proposta') or {}
    nv = prop.get('nivel_partida', 1)
    mt = prop.get('meta', 3)
    return [
        {'rotulo': f'Aceitar pedido #{pid}', 'descricao': f"aplicar mudança em Prisma {curto(p['prisma'], 24)}", 'rodar': f'pedido aceitar {pid}'},
        {'rotulo': f'Ajustar pedido #{pid}', 'descricao': f'rever proposta (nível {nv} → meta {mt})', 'rodar': f'pedido ajustar {pid} --nivel {nv} --meta {mt}'},
        {'rotulo': f'Recusar pedido #{pid}', 'descricao': 'arquivar pedido sem mudar a trajetória', 'rodar': f'pedido recusar {pid}'},
    ]


def _id_pedido(extras: list[str], sub: str) -> int:
    if not extras or not str(extras[0]).lstrip('#').isdigit():
        raise ValueError(f'informe o número do pedido: `pedido {sub} <número>`')
    return int(str(extras[0]).lstrip('#'))


def _print_proposta(p: dict) -> None:
    proposta = p.get('proposta') or {}
    if not proposta:
        return
    ganho = int(proposta.get('ganho_niveis') or 0)
    print(f"- **Proposta da Luzia:** nível **{proposta.get('nivel_partida')} → meta {proposta.get('meta')}/5**"
          f" · a trajetória {'ganha' if ganho >= 0 else 'perde'} {abs(ganho)} nível(is)")
    if p.get('tipo') in ('incluir', 'mudar_meta'):
        print('- **Análise do pedido:** ' + leitura_txt(p.get('leitura'), indisponivel=proposta.get('leitura_indisponivel', '')))
    for a in (proposta.get('acoes') or [])[:3]:
        print(f"  - Avanço inicial sugerido: **{a.get('titulo', '')}** ({a.get('tipo', '')})")


def cmd_pedido(args, restantes: list[str], plan: dict) -> None:
    """Pedido de mudança pelo chat; todo erro vira uma mensagem clara terminando em botões (nunca traceback)."""
    sub = (args.valor or (restantes[0] if restantes else '')).strip().lower()
    extras = restantes[1:] if args.valor and restantes and restantes[0] == args.valor else list(restantes)
    with trajetoria.abrir() as con:
        try:
            _pedido(con, sub, extras, args)
        except (ValueError, RuntimeError) as e:
            print(f'Não foi possível concluir o pedido: {e}.')
            abertos = [x for x in pedidos.listar(con)  # o pedido que já está aberto para este prisma, se for o caso
                       if x['estado'] in ('aberto', 'proposto') and str(e).endswith(f"prisma {x['prisma']}")]
            bts = _botoes_pedido(abertos[0]['id'], abertos[0]) if abertos else []
            botoes(bts + [BT_TRAJETORIA, BT_PAINEL], 'Como seguimos com a sua trajetória?')


def _pedido(con, sub: str, extras: list[str], args) -> None:
    if sub == 'abrir':
        if len(extras) < 2:
            print('Informe o tipo e o prisma: `pedido abrir <incluir|arquivar|reativar|mudar_meta> "<prisma>" --motivo "..."`')
            botoes([BT_TRAJETORIA, BT_PAINEL])
            return
        tipo, nome_prisma = extras[0], extras[1]
        motivo = args.motivo if args.motivo != 'nao_faz_sentido' else ''
        p = pedidos.abrir(con, tipo, nome_prisma, motivo)
        if tipo in ('incluir', 'mudar_meta'):
            p = pedidos.propor(con, p['id'], nivel=args.nivel, meta=args.meta)
        print(f"✦ **Pedido `#{p['id']}` aberto** · **{p['tipo']}** em **Prisma {p['prisma']}** (estado: **{p['estado']}**)")
        if p.get('motivo'):
            print(f"- **Motivo:** {p['motivo']}")
        _print_proposta(p)
        botoes(_botoes_pedido(p['id'], p), 'Como você quer decidir este pedido?')
        return

    if sub == 'ajustar':
        pid = _id_pedido(extras, sub)
        p = pedidos.propor(con, pid, nivel=args.nivel, meta=args.meta)
        print(f"✦ **Pedido `#{pid}` ajustado** · **Prisma {p['prisma']}** (estado: **{p['estado']}**)")
        _print_proposta(p)
        botoes(_botoes_pedido(pid, p), 'Aceitar esta nova proposta ou ajustar de novo?')
        return

    if sub == 'aceitar':
        pid = _id_pedido(extras, sub)
        p = pedidos.aceitar(con, pid)
        plan = pipeline.load_state().get('plano', {})
        print(f"★ **Pedido `#{pid}` aceito** — trajetória atualizada com **{p['tipo']}** em **Prisma {p['prisma']}**.")
        botoes([BT_TRAJETORIA, *proximos_botoes(plan)[:2]], 'Qual é o próximo passo na nova trajetória?')
        return

    if sub == 'recusar':
        pid = _id_pedido(extras, sub)
        pedidos.recusar(con, pid)
        print(f"Pedido `#{pid}` recusado — sua trajetória permanece inalterada.")
        botoes([BT_TRAJETORIA, BT_PAINEL])
        return

    lista = pedidos.listar(con)
    if not lista:
        print('Nenhum pedido de mudança registrado na sua trajetória.')
        botoes([BT_TRAJETORIA, BT_PAINEL])
        return
    print('## ✦ Luzia · pedidos de mudança da trajetória')
    bts: list[dict] = []
    for p in lista[:5]:
        print(f"- Pedido `#{p['id']}` · **{p['tipo']}** em **Prisma {p['prisma']}** — **{p['estado']}** ({p.get('motivo', '')})")
        if p['estado'] in ('aberto', 'proposto') and not bts:
            bts.extend(_botoes_pedido(p['id'], p))
    botoes(bts or [BT_TRAJETORIA, BT_PAINEL])


def cmd_entregas(args, state: dict, entrada_path: Path, rotulo: str) -> None:
    dias = args.ampliar if args.ampliar > 0 else 90
    plan = state.get('plano', {})
    jogo.sincronizar(plan)
    with trajetoria.abrir() as con:
        entregas.atualizar(con, dias=dias)
        lista = entregas.listar(con)
        leit_map = {str(e['id']): leituras.obter(con, 'entrega', str(e['id'])) for e in lista}

    if not lista and args.rotulo == 'feedback-progress':
        _, rec, hits = daily_call('progress', entrada_path, rotulo)
        state = pipeline.load_state()
        todas = acoes.todas(state.get('plano', {}))
        print('## ✦ Luzia · propriedade nas suas entregas')
        for e in propriedade_entregas(state):
            print_entrega(e, todas)
        print('\n_P1 inferido dos seus prompts (geral) · P2 calculado da entrega · P3/P4 só com evidência registrada._')
        footer(rec, hits)
        oferecer([a for a in todas if a['origem'] == 'entrega'], 'Qual lacuna você quer fechar agora?')
        return

    print('## ✦ Luzia · suas entregas e propriedade sobre o código')
    bts: list[dict] = []
    if lista:
        for e in lista[:10]:
            fatos = e.get('fatos', {})
            prismas_nomes = ', '.join(f"Prisma {p['prisma']}" for p in e.get('prismas', [])) or 'nenhum prisma mapeado'
            print(
                f"\n▸ **Entrega `#{e['id']}` · {e['titulo']}** ({e['fonte']})\n"
                f"   Fatos: {fatos.get('inicio', '')[:10]} a {fatos.get('fim', '')[:10]} "
                f"({fatos.get('duracao_dias', 1)}d) · {fatos.get('commits', 0)} commit(s) · "
                f"{fatos.get('arquivos', 0)} arquivo(s) · {fatos.get('linhas', 0)} linhas\n"
                f"   Prismas atravessados: {prismas_nomes}"
            )
            print('   ' + leitura_txt(leit_map.get(str(e['id']))))
            if len(bts) < 2:
                bts.append({'rotulo': f"Ver entrega #{e['id']}", 'descricao': curto(e['titulo'], 40), 'rodar': f"entrega {e['id']}"})
    else:
        todas = acoes.todas(plan)
        for e in propriedade_entregas(state):
            print_entrega(e, todas)
    bts.append({'rotulo': 'Ampliar janela (180 dias)', 'descricao': 'buscar entregas mais antigas no git', 'rodar': 'entregas --ampliar 180'})
    bts.append(BT_PAINEL)
    botoes(bts, 'Qual entrega você quer inspecionar?')


def cmd_entrega_detalhe(entrega_id: int, plan: dict) -> None:
    jogo.sincronizar(plan)
    with trajetoria.abrir() as con:
        det = entregas.detalhe(con, entrega_id)
    if not det:
        print(f'Entrega `#{entrega_id}` não encontrada.')
        botoes([{'rotulo': 'Ver entregas', 'descricao': 'listar entregas detectadas', 'rodar': 'entregas'}, BT_PAINEL])
        return
    fatos = det['fatos']
    print(f"## ✦ Luzia · Entrega `#{det['id']}` · {det['titulo']} ({det['fonte']})")
    print(f"- **Período:** {fatos['inicio'][:10]} a {fatos['fim'][:10]} ({fatos['duracao_dias']} dia(s))")
    print(f"- **Volume:** {fatos['commits']} commit(s) · {fatos['arquivos']} arquivo(s) · {fatos['linhas']} linhas · áreas: {', '.join(fatos['areas']) or 'n/d'}")
    if det['prismas']:
        print('- **Prismas atravessados:** ' + ', '.join(
            f"Prisma {p['prisma']} ({', '.join(p['termos'])})" for p in det['prismas']
        ))
    prop = det.get('propriedade') or {}
    for linha in linhas_propriedade(prop):
        print(linha)
    print('\n' + leitura_txt(det.get('leitura')))

    if det['avancos_feitos']:
        print('\n**Avanços feitos para esta entrega**')
        for a in det['avancos_feitos']:
            print(f'   {feixe_linha(a)}')
    if det['avancos_uteis']:
        print('\n**Avanços úteis abertos nos mesmos prismas**')
        for a in det['avancos_uteis']:
            print(f'   {feixe_linha(a)}')
    if det['lumens_ligados']:
        soma_lm = sum(int(l['lm']) for l in det['lumens_ligados'])
        print(f"\n**Lúmens ligados ({len(det['lumens_ligados'])} registro(s) · {soma_lm} lm)**")
        for l in det['lumens_ligados'][:5]:
            print(f"- {l['quando'][:10]} · Prisma {l['prisma']} · +{l['lm']} lm ({l['luz']} · {l['fonte']})")

    bts = [bt_feixe(a) for a in det['avancos_uteis'][:2]]
    bts.append({'rotulo': 'Voltar às entregas', 'descricao': 'ver lista de entregas', 'rodar': 'entregas'})
    bts.append(BT_PAINEL)
    botoes(bts, 'Quer praticar um avanço ligado a esta entrega?')


# ------------------------------------------------------------------ main
COMANDOS = [
    'hoje', 'triage', 'trajetoria', 'next-level', 'rota',
    'entregas', 'entrega', 'feedback-progress', 'feedback-skills-opportunities',
    'avancos', 'acoes', 'fazer', 'prompt', 'registrar', 'revisitar', 'descartar', 'restaurar',
    'subir', 'nivel', 'acender', 'trecho', 'pedido',
    'dossie', 'lampejo', 'cartao', 'guardar', 'fila', 'enviar', 'career-map', 'modo', 'modelo',
]


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Luzia CLI')
    ap.add_argument('comando', choices=COMANDOS)
    ap.add_argument('valor', nargs='?', default='')
    ap.add_argument('--entrada', default=str(pipeline.PRIVATE / 'entrada.json'))
    ap.add_argument('--rotulo', default='')
    ap.add_argument('--salvar-json', default='', help='Salva a resposta e o custo num JSON separado (não altera o estado)')
    ap.add_argument('--nota', type=int, default=None)
    ap.add_argument('--resumo', default='')
    ap.add_argument('--skill', default='')
    ap.add_argument('--prisma', default='')
    ap.add_argument('--estado', default='')
    ap.add_argument('--tipo', default='')
    ap.add_argument('--pergunta', default='')
    ap.add_argument('--motivo', default='nao_faz_sentido')
    ap.add_argument('--onde', default='', help='Onde o avanço foi aberto (ex.: "sessão nova", "aqui")')
    ap.add_argument('--acao', choices=['converter', 'guardar'], default='converter')
    ap.add_argument('--ampliar', type=int, default=0)
    ap.add_argument('--nivel', type=int, default=None)
    ap.add_argument('--meta', type=int, default=None)
    args, restantes = ap.parse_known_args()

    entrada_path = Path(args.entrada)
    rotulo = args.rotulo or f'cmd-{args.comando}'

    if args.comando == 'modo':
        bts_foco = [
            {'rotulo': 'Em foco, com lampejos', 'descricao': 'observa e mostra lampejos no chat', 'rodar': 'modo ativo'},
            {'rotulo': 'Em foco, em silêncio', 'descricao': 'soma lúmens sem interromper', 'rodar': 'modo passivo'},
            {'rotulo': 'Fora de foco', 'descricao': 'só responde quando chamada', 'rodar': 'modo sob_demanda'},
        ]
        if args.valor in MODOS:
            set_mode(args.valor)
            nome_foco = observer.NOMES_FOCO.get(args.valor, args.valor)
            print(f'✦ Foco da Luzia ajustado para **{nome_foco}** (`{args.valor}`).')
        else:
            cfg = observer.config()
            nome_foco = observer.NOMES_FOCO.get(cfg['modo'], cfg['modo'])
            print(f"✦ Foco atual da Luzia: **{nome_foco}** (`{cfg['modo']}`).")
        botoes(bts_foco, 'Qual foco da Luzia você prefere agora?')
        return

    if args.comando == 'modelo':
        s = modelo.status()
        print('## ✦ Luzia · modelo')
        print(f"**{s['nome_provedor']}** · `{s['modelo']}`" + (f" · {s['base_url']}" if s.get('base_url') else ''))
        print(f"chave: {'configurada' if s['chave_configurada'] else 'FALTANDO'} · "
              f"SDK: {'instalado' if s['sdk_instalado'] else 'falta: pip install ' + s['pip']}")
        print('Troque em Ajustes > Modelo da Luzia, no painel. A chave fica só no .env desta máquina.')
        if args.valor == 'testar':
            r = modelo.chamar('Responda só com o JSON {"ok": true}.', 'Responda só com JSON.')
            print(f"teste: {r['texto'].strip()[:60]} · {r['segundos']:.1f} s · {r['tokens_in']}→{r['tokens_out']} tokens · {r['provedor']}/{r['modelo']}")
            if r.get('aviso'):
                print(f"! {r['aviso']}")
        botoes([BT_TRAJETORIA, BT_PAINEL], 'O que você quer ver agora?')
        return

    if args.comando == 'career-map':
        import webbrowser
        if not panel_up():
            start_panel()
        print(f'## ✦ Luzia · painel aberto em {PAINEL}')
        try:
            webbrowser.open(PAINEL)
        except Exception:
            pass
        botoes([BT_TRAJETORIA, BT_PAINEL])
        return

    if args.comando == 'triage':
        plan, rec, hits = execute_triage(entrada_path, rotulo=rotulo, save_state=not args.salvar_json)
        if args.salvar_json:
            Path(args.salvar_json).write_text(
                json.dumps({'plano': plan, 'custo': rec, 'hits': hits}, ensure_ascii=False, indent=2), encoding='utf-8',
            )
            return
        state = pipeline.load_state()
        plan = state.get('plano', {})
        print('## ✦ Luzia · triagem')
        base_tri = 'sua entrada, currículo, commits e histórico autorizados (anonimizados)'
        for rotulo_tri, campo in (('Onde você está', 'onde_esta'), ('Aonde quer chegar', 'aonde_quer_chegar')):
            texto = (plan.get(campo) or {}).get('resumo', '')
            leit = {'texto': texto, 'modelo': rec.get('modelo'), 'criado_em': rec.get('quando')}
            print(f"{rotulo_tri}: {leitura_txt(leit, base_tri)}")
        print()
        rota_texto(plan, state)
        primeiros = [a for a in acoes.todas(plan) if a['origem'] == 'rota']
        print('\n**Primeiros avanços:**')
        for a in primeiros[:3]:
            print(feixe_linha(a))
        footer(rec, hits)
        botoes([{'rotulo': 'Ajustar meu nível no painel', 'descricao': 'a trajetória parte do nível que você declara',
                 'rodar': 'career-map'}] + [bt_feixe(a) for a in primeiros], 'Quer ajustar seu nível ou já começar?')
        return

    if args.comando == 'feedback-skills-opportunities':
        resp, rec, hits = daily_call('opportunities', entrada_path, rotulo)
        plan = pipeline.load_state().get('plano', {})
        sessao = [a for a in acoes.todas(plan) if a['origem'] == 'sessão']
        print('## ✦ Luzia · oportunidades nesta sessão')
        if resp.get('resumo_sessao'):
            print(leitura_txt({'texto': resp['resumo_sessao'], 'modelo': rec.get('modelo'), 'criado_em': rec.get('quando')},
                              f"{rec.get('eventos_sessao', 0)} evento(s) mascarado(s) da sessão e o seu plano") + '\n')
        for a in sessao:
            print(feixe_linha(a))
            print(f"   ↳ {a.get('gatilho', '')}")
        footer(rec, hits)
        oferecer(sessao, 'Quer aproveitar alguma agora?')
        return

    state = pipeline.load_state()
    plan = state.get('plano', {})
    if not plan:
        print('A Luzia ainda não fez a triagem. Rode /luzia:triage.')
        botoes([BT_PAINEL])
        return

    if args.comando in ('entregas', 'feedback-progress'):
        cmd_entregas(args, state, entrada_path, rotulo)
        return

    if args.comando == 'entrega':
        if not args.valor or not str(args.valor).isdigit():
            print('Informe o número da entrega: `entrega <id>`')
            botoes([{'rotulo': 'Ver entregas', 'descricao': 'listar entregas detectadas', 'rodar': 'entregas'}, BT_PAINEL])
            return
        cmd_entrega_detalhe(int(args.valor), plan)
        return

    if args.comando == 'pedido':
        cmd_pedido(args, restantes, plan)
        return

    if args.comando == 'nivel':
        alvo_prisma = args.valor or args.prisma or args.skill
        nv_arg = args.nivel if args.nivel is not None else (int(restantes[0]) if restantes and restantes[0].lstrip('-').isdigit() else None)
        if not alvo_prisma or nv_arg is None:
            print('Informe o prisma e o nível (0 a 5): `nivel "<prisma>" <0-5>`')
            botoes(proximos_botoes(plan))
            return
        skill = jogo.skill_de(alvo_prisma, plan)
        with trajetoria.abrir() as con:
            try:
                trajetoria.declarar_nivel(con, skill, int(nv_arg))
            except ValueError as e:
                print(_vocab_novo(str(e)))
                botoes(proximos_botoes(plan))
                return
        nv_int = int(nv_arg)
        print(f"✦ **Prisma {skill}** declarado no **nível {nv_int}** `{espectro_txt(nv_int)}` (ponto de partida registrado).")
        botoes(proximos_botoes(plan), 'Qual é o próximo passo na sua trajetória?')
        return

    if args.comando == 'hoje':
        hoje(plan, state)
        return

    if args.comando in ('trajetoria', 'next-level', 'rota'):
        todas = acoes.todas(plan)
        with trajetoria.abrir() as con:
            versoes = trajetoria.versoes(con)
            ver_atual = versoes[-1]['numero'] if versoes else 1
            ver_motivo = versoes[-1]['origem'] if versoes else 'triagem'
            arquivados = [p for p in trajetoria.prismas(con, incluir_arquivados=True) if p['estado'] == 'arquivado']
            lista_pedidos = pedidos.listar(con)
        print(f"## ✦ Luzia · sua trajetória até {pipeline.rotulos(state)[1]} · v{ver_atual} ({ver_motivo})")
        rota_texto(plan, state)
        cfg = load_cfg(entrada_path) if entrada_path.exists() else {}
        rit = jogo.ritmo(plan, cfg.get('horizonte', ''))
        print(f"\n_Calibragem: para chegar em ~{rit['meses']} meses, uns **{rit['feixes_semana']} avanço{'s' if rit['feixes_semana'] > 1 else ''} por semana**. "
              'É só referência: o que move a trajetória é o que você conquista._')
        por_skill: dict[str, list] = {}
        for a in todas:
            if a['estado'] != 'conquistado':
                por_skill.setdefault(a.get('skill_plano') or a.get('skill', ''), []).append(a)
        for skill, lista in por_skill.items():
            print(f'\n**Prisma {skill}**')
            for a in lista[:3]:
                print(f'   {feixe_linha(a)}')
        if arquivados:
            print('\n**Prismas arquivados (lúmens e histórico preservados)**')
            for p in arquivados:
                print(f"   - Prisma {p['nome']} · `{espectro_txt(p['nivel'])}` nível {p['nivel']}/{p['meta']}")
        if lista_pedidos:
            print('\n**Pedidos de mudança na trajetória**')
            for p in lista_pedidos[:5]:
                print(f"   - Pedido `#{p['id']}` · **{p['tipo']}** em **Prisma {p['prisma']}** — estado: **{p['estado']}**")
        avisar_degraus(plan)
        botoes(proximos_botoes(plan), 'Por onde seguimos?')
        return

    if args.comando in ('avancos', 'acoes'):
        jogo.sincronizar(plan)
        est_f = args.estado or None
        pri_raw = args.prisma or args.skill or (args.valor if args.valor else None)
        pri_f = jogo.skill_de(pri_raw, plan) if pri_raw else None
        tip_f = args.tipo or None
        with trajetoria.abrir() as con:
            lista = jogo.avancos(con, estado=est_f, prisma=pri_f, tipo=tip_f)
        filtros_txt = ', '.join(f'{k}={v}' for k, v in (('estado', est_f), ('prisma', pri_f), ('tipo', tip_f)) if v)
        print(f"## ✦ Luzia · seus avanços{f' ({filtros_txt})' if filtros_txt else ''}")
        if filtros_txt:
            if not lista:
                print('Nenhum avanço encontrado para este filtro.')
            for a in lista:
                print(feixe_linha(a))
        else:
            for estado, nome in (('em_andamento', 'Em andamento'), ('na_fila', 'Na fila'), ('sugerido', 'Sugeridos'),
                                 ('conquistado', 'Conquistados'), ('descartado', 'Descartados')):
                grupo = [a for a in lista if a.get('estado') == estado]
                if grupo:
                    print(f'\n**{nome}** ({len(grupo)})')
                    for a in grupo:
                        print(feixe_linha(a))
        bts = [bt_feixe(a) for a in lista if a.get('estado') in ('em_andamento', 'na_fila', 'sugerido')][:2]
        bts.append({'rotulo': 'Filtrar sugeridos', 'descricao': 'mostrar apenas avanços sugeridos', 'rodar': 'avancos --estado sugerido'})
        botoes(bts, 'Qual avanço agora?')
        return

    if args.comando == 'fila':
        lista = [a for a in (acoes.find(plan, f['id']) for f in acoes.fila()) if a]
        print('## ✦ Luzia · avanços que você mandou do painel')
        if not lista:
            print('Nenhum avanço na fila. No painel, clique em "Enviar para o agente" num avanço.')
        for a in lista:
            print(feixe_linha(a))
        botoes([bt_feixe(a) for a in lista] + ([BT_PAINEL] if not lista else []), 'Começamos qual?')
        return

    if args.comando in ('acender', 'trecho'):
        res = gerar_trecho(args.valor or args.prisma or args.skill, rotulo)
        if res.get('erro'):
            print(f"◐ {_vocab_novo(res['erro'])}.")
            botoes(proximos_botoes(plan))
            return
        print(f"## ✦ Luzia · 3 avanços novos acesos para Prisma {curto(res['skill'])}")
        for f in res['feixes']:
            print(feixe_linha(f))
        footer(res['record'])
        oferecer(res['feixes'], 'Qual avanço novo você quer fazer?')
        return

    if args.comando == 'guardar':
        skill = jogo.skill_de(args.valor or args.prisma or args.skill, plan)
        jogo.usar_lampejo(skill, 'guardado')
        f = acoes.guardar(skill, args.pergunta or f'Oportunidade observada em {skill}')
        print(f"➤ Guardado como avanço `#{f['id']}`: aparece no painel e em /luzia:hoje.")
        botoes([bt_feixe({**f, 'valor_lm': 30}), *proximos_botoes(plan)[:2]], 'Quer fazer este avanço agora?')
        return

    a = acoes.find(plan, args.valor) if args.valor else None

    if args.comando == 'enviar':
        if not a:
            print(f'Avanço {args.valor} não encontrado.')
            botoes(proximos_botoes(plan))
            return
        if not jogo.enfileirar(a['id']):
            print(f"`#{a['id']}` não pode ir para a fila: já foi conquistado (e revisitado) ou está descartado.")
            botoes(proximos_botoes(plan))
            return
        acoes.enfileirar(a['id'], a.get('titulo', ''))
        print(f"➤ `#{a['id']}` na fila: a Luzia oferece na próxima mensagem do seu agente.")
        botoes([bt_feixe(a), BT_PAINEL], 'Quer fazer este avanço agora?')
        return

    if args.comando in ('prompt', 'fazer', 'revisitar'):
        if not a:
            print(f'Avanço {args.valor} não encontrado.')
            botoes(proximos_botoes(plan))
            return
        if (args.comando == 'revisitar' or a.get('estado') == 'conquistado') and not jogo.pode_revisitar(a):
            print(f"`#{a['id']}` já foi conquistado. Só dá para revisitar uma vez um avanço com nota 2 ou 3.")
            botoes(proximos_botoes(plan, {a['id']}))
            return
        if not jogo.iniciar(a['id'], args.onde or ('revisita' if a.get('estado') == 'conquistado' else '')):
            print(f"`#{a['id']}` está descartado.")
            botoes([{'rotulo': 'Restaurar este avanço', 'descricao': 'volta para os sugeridos', 'rodar': f"restaurar {a['id']}"}])
            return
        acoes.desenfileirar(a['id'])
        acoes.registrar_evento(a['id'], 'iniciada', skill=a.get('skill'), origem=a.get('origem'))
        if args.comando == 'prompt':
            print(acoes.prompt_completo(a))
        else:
            roteiro(a)
            botoes([
                {'rotulo': 'Descartar este avanço', 'descricao': 'não faz sentido para a minha trajetória', 'rodar': f"descartar {a['id']} --motivo nao_faz_sentido"},
                {'rotulo': 'Já domino este tema', 'descricao': 'descartar por já dominar', 'rodar': f"descartar {a['id']} --motivo ja_domino"},
                BT_PAINEL,
            ], 'Responda à pergunta da Luzia no chat, ou escolha:')
        return

    if args.comando == 'registrar':
        if not a or args.nota is None:
            print('Use: registrar <id> --nota 0-4 --resumo "..."')
            botoes(proximos_botoes(plan))
            return
        res = jogo.conquistar(a['id'], args.nota, args.resumo[:200], plan)
        if res.get('erro'):
            print(f"◐ {_vocab_novo(res['erro'])}.")
            botoes(proximos_botoes(plan))
            return
        if res.get('tente_de_novo'):
            print(f"◐ Nota {args.nota}/4 ({propriedade.RUBRICA[max(0, min(4, args.nota))]}): ainda não. "
                  f"O avanço `#{a['id']}` continua aberto: tente de novo agora ou depois, vale o mesmo.")
            botoes([bt_feixe(a, 'Tentar de novo: '), *proximos_botoes(plan, {a['id']})[:2]])
            return
        acoes.registrar_evento(a['id'], 'concluida', nota=args.nota, resumo=args.resumo[:200], skill=a.get('skill'),
                               entrega=a.get('entrega'), dimensao=a.get('dimensao'), origem=a.get('origem'))
        r = jogo.rota(plan)
        s = next((x for x in r['skills'] if x['nome'] == (a.get('skill_plano') or a.get('skill'))), None)
        print(f"✦ Avanço conquistado · `#{a['id']}` · nota {args.nota}/4 · **+{res['ganho']} lm**"
              + (f" · Prisma {curto(s['nome'])} {s['lm']}/{s['limiar']} lm" if s else '') + f" · trajetória {r['niveis_feitos']}/{r['niveis_total']} níveis")
        if a.get('entrega'):
            for e in propriedade_entregas(pipeline.load_state()):
                if e['tarefa'] == a['entrega']:
                    print(f"▸ {e['tarefa']}: propriedade agora **{e['indice']}%** · medida em {e['base']}")
        avisar_degraus(plan)
        revisita = [{'rotulo': 'Revisitar agora', 'descricao': f"buscar o restante: {res['feixe']['lm_ganho']} de {res['feixe']['valor_lm']} lm",
                     'rodar': f"fazer {a['id']}"}] if res.get('pode_revisitar') else []
        botoes(proximos_botoes(plan, {a['id']})[:2] + revisita, 'E agora?')
        return

    if args.comando == 'descartar':
        if not a:
            print(f'Avanço {args.valor} não encontrado.')
            botoes(proximos_botoes(plan))
            return
        motivo_k = args.motivo if args.motivo in jogo.MOTIVOS else 'nao_faz_sentido'
        jogo.descartar(a['id'], motivo_k)
        acoes.desenfileirar(a['id'])
        print(f"✕ `#{a['id']}` descartado ({jogo.MOTIVOS[motivo_k]}). A Luzia leva isso em conta nas próximas sugestões.")
        botoes([{'rotulo': 'Desfazer', 'descricao': 'o avanço volta para os sugeridos', 'rodar': f"restaurar {a['id']}"}]
               + proximos_botoes(plan, {a['id']}))
        return

    if args.comando == 'restaurar':
        if not a:
            print(f'Avanço {args.valor} não encontrado.')
            botoes(proximos_botoes(plan))
            return
        jogo.restaurar(a['id'])
        print(f"○ `#{a['id']}` voltou para os sugeridos.")
        botoes([bt_feixe({**a, 'estado': 'sugerido'})])
        return

    if args.comando == 'subir':
        skill = jogo.skill_de(args.valor or args.prisma or args.skill, plan)
        res = jogo.subir(skill, plan)
        if res.get('erro'):
            print(f"◐ Prisma {curto(skill)}: {_vocab_novo(res['erro'])}.")
            botoes(proximos_botoes(plan))
            return
        r = res['rota']
        print(f"✦ **Prisma {skill}** subiu para o nível {res['para']}. Trajetória: **{r['niveis_feitos']} de {r['niveis_total']} níveis**.")
        if res.get('marco'):
            print(f"◆ Marco {res['marco']['n']} de 3 alcançado. Dossiê de evidências salvo em `{res['marco']['dossie']}` (local).")
        s = next((x for x in r['skills'] if x['nome'] == skill), {})
        prox = [] if s.get('na_meta') else [{'rotulo': f'Acender avanços de {curto(skill)}'[:48],
                                             'descricao': f"3 avanços para o nível {s.get('proximo')} (o modelo leva ~10 s)",
                                             'rodar': f'trecho "{skill}"'}]
        botoes(prox + proximos_botoes(plan), 'Acendemos os próximos avanços?')
        return

    if args.comando == 'dossie':
        caminho = jogo.dossie(plan)
        print(f'## ✦ Luzia · dossiê de evidências\nSalvo em `{caminho}` (local, fora do git).')
        print(caminho.read_text(encoding='utf-8'))
        botoes(proximos_botoes(plan)[:2] + [BT_PAINEL])
        return

    if args.comando in ('lampejo', 'cartao'):
        alvo_sk = args.valor or args.prisma or args.skill
        if not alvo_sk:
            print('Use: lampejo "<prisma>" [--acao guardar|converter] [--nota 0-4 --resumo "..."]')
            botoes(proximos_botoes(plan))
            return
        skill = jogo.skill_de(alvo_sk, plan)
        if args.acao == 'guardar' or (args.nota is None and args.pergunta):
            jogo.usar_lampejo(skill, 'guardado')
            f = acoes.guardar(skill, args.pergunta or f'Pergunta do lampejo sobre {skill}')
            print(f"➤ Lampejo guardado como avanço `#{f['id']}`: aparece no painel e em /luzia:hoje.")
            botoes([bt_feixe({**f, 'valor_lm': 30}), *proximos_botoes(plan)[:2]])
            return
        if args.nota is None:
            print('Informe `--nota 0-4` para converter o lampejo em luz própria.')
            botoes(proximos_botoes(plan))
            return
        res = jogo.converter(skill, args.nota, (args.pergunta or args.resumo or '')[:60])
        if res.get('erro'):
            print(f"◐ {_vocab_novo(res['erro'])}.")
            botoes(proximos_botoes(plan))
            return
        nota, lm = res['nota'], res['lm']
        acoes.registrar_evento(acoes.aid('cartao', args.pergunta or skill), 'concluida', nota=nota, resumo=args.resumo[:200],
                               skill=skill, origem='cartao')
        print(f"✦ Luz própria: nota {nota}/4 · **+{lm} lm** em Prisma {curto(skill)}" if lm else
              f"◐ Nota {nota}/4: ainda luz refletida. Virou um avanço guardado para você tentar com calma.")
        if not lm:
            acoes.guardar(skill, args.pergunta or f'Pergunta do lampejo sobre {skill}')
        avisar_degraus(plan)
        botoes([b for b in proximos_botoes(plan) if b['rodar'].startswith('subir')] or proximos_botoes(plan))
        return


if __name__ == '__main__':
    main()
