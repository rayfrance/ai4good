"""CLI da Luzia (agnóstica de harness; no Claude Code é chamada pelos comandos /luzia:*).

O jogo (docs/luzia-ux.md): feixes valem lúmens; lúmens enchem os degraus de cada skill; os degraus formam a rota até Plena.
- `triage`, `next-level`/`rota`, `feedback-progress`, `feedback-skills-opportunities`, `acoes`, `fila`
- `fazer`/`prompt`/`revisitar <id>`, `registrar <id> --nota --resumo`, `descartar <id> --motivo`, `restaurar <id>`, `enviar <id>`
- `subir <skill>` (confirma um degrau pronto), `dossie`, `cartao` (observador), `career-map`, `modo`
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import acoes, arquivos, jogo, pipeline, planner, propriedade, triage
from .privacy import Redactor

PAINEL = 'http://localhost:8501'
MODOS = ('ativo', 'passivo', 'sob_demanda')
CLI = 'cd /c/Repositorio/ai4good-sem2/code && python -m luzia.cli'


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
    autoaval = pipeline.read_json(pipeline.AUTOAVAL, {})
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


# ------------------------------------------------------------------ apresentação
def bar(value, total: int = 5, width: int = 5) -> str:
    value = max(0, min(total, int(value or 0)))
    filled = round(value / total * width)
    return '█' * filled + '░' * (width - filled)


def footer(rec: dict, hits: dict | None = None) -> None:
    masked = sum((hits or {}).values())
    print(
        f"\n`⏱ {rec['tempo_total_s']} s · 🧠 {rec['pico_memoria_mib']} MiB · 🔤 {rec['tokens_entrada']}→{rec['tokens_saida']} tokens"
        f" · 🔒 {masked} itens mascarados · versão {rec['versao']}`"
    )


ESTADO_IC = {'conquistado': '✦', 'em_andamento': '◐', 'na_fila': '➤', 'sugerido': '○', 'descartado': '✕'}


def feixe_linha(f: dict) -> str:
    extra = f" · nota {f.get('nota')}/4 · +{f.get('lm_ganho')} lm" if f.get('estado') == 'conquistado' else ''
    tent = f" · tentativa {f.get('tentativas') + 1}" if f.get('tentativas') and f.get('estado') != 'conquistado' else ''
    return (f"{ESTADO_IC.get(f.get('estado'), '○')} `#{f['id']}` **{f.get('titulo', '')}** · {f.get('tipo', '')} · "
            f"{f.get('duracao_min', '?')} min · **{f.get('valor_lm', '?')} lm**{extra}{tent}")


def oferecer(lista: list[dict]) -> None:
    pend = [a for a in lista if a.get('estado') not in ('conquistado', 'descartado')][:3]
    if pend:
        print('\nLUZIA_ACOES=' + json.dumps([{'id': a['id'], 'titulo': a.get('titulo', ''), 'tipo': a.get('tipo', ''),
                                              'lm': a.get('valor_lm')} for a in pend], ensure_ascii=False))


def rota_texto(plan: dict) -> None:
    r = jogo.rota(plan)
    luz = '━' * round(20 * r['pct'] / 100)
    print(f"**Rota** Júnior 3 {luz}◉{'─' * (20 - len(luz))} Plena · **{r['degraus_feitos']} de {r['degraus_total']} degraus** · "
          f"{r['lm_total']} lm · {r['luz_propria']}% luz própria")
    for s in r['skills']:
        if s['na_meta']:
            print(f"   ✦ {s['nome']} · nível {s['nivel']} · na meta")
            continue
        pronto = ' · **pronto para subir**' if s['pronto'] else ''
        print(f"   {s['nome']} {s['nivel']} → {s['proximo']}  `{bar(min(s['lm'], s['limiar']), s['limiar'], 10)}` "
              f"{s['lm']}/{s['limiar']} lm · luz própria {s['luz_propria']}%{pronto}")


def propriedade_entregas(state: dict) -> list[dict]:
    plan = state.get('plano', {})
    commits = state_commits(state)
    evs = acoes.evidencias()
    return [{**t, **propriedade.entrega(t, commits, plan.get('p1_direcao_prompt'), evs)} for t in plan.get('tarefas_recentes', [])]


def print_entrega(e: dict, todas: list[dict]) -> None:
    idx = e['indice']
    print(f"\n📦 **{e['tarefa']}** — luz própria **{idx if idx is not None else '—'}%** · base {e['base']}")
    print('   ' + ' · '.join(f"{k} {d['nota']} ({d['tipo']})" if d else f'{k} — sem base' for k, d in e['dimensoes'].items()))
    for a in todas:
        if a.get('origem') == 'entrega' and a.get('entrega') == e['tarefa']:
            print(f'   {feixe_linha(a)}' + (f" → acende {a['dimensao']}" if a.get('dimensao') else ''))


def avisar_degraus(plan: dict) -> None:
    for s in jogo.rota(plan)['skills']:
        if s['pronto'] and not s['na_meta']:
            print(f"\n✦ **{s['nome']}** está pronta para subir para o nível {s['proximo']} "
                  f"({s['lm']} lm, {s['luz_propria']}% luz própria). Confirme: `{CLI} subir \"{s['nome']}\"`")


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
    cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {})
    cfg['modo'] = modo
    arquivos.gravar_json(pipeline.OBSERVER_CFG, cfg)


def roteiro(a: dict) -> None:
    print(f"## ✨ Luzia · feixe `#{a['id']}` · **{a.get('valor_lm')} lm**")
    print(f"**{a.get('titulo', '')}** · {a.get('tipo', '')} · {a.get('skill', '')} · {a.get('duracao_min', '?')} min")
    print('Vale: ' + ' + '.join(f"{c[0]} {c[2]} ({c[1]})" for c in a.get('conta', [])))
    if a.get('entrega'):
        print(f"📦 entrega: {a['entrega']}" + (f" · acende {a['dimensao']}" if a.get('dimensao') else ''))
    print(f"\n**Por quê:** {a.get('por_que', '')}")
    print(f"**Conceitos:** {', '.join(a.get('conceitos', []))}")
    print('**Como:**')
    for i, p in enumerate(a.get('como', []), 1):
        print(f'{i}. {p}')
    print(f"**Onde explorar no repositório:** {a.get('onde_explorar', '')}")
    print('\n---\nROTEIRO PARA O AGENTE (conduza como a Luzia, sem fazer o trabalho no lugar da pessoa):')
    print('1. Mostre o feixe acima de forma curta e visual, com o valor em lúmens.')
    print(f"2. Siga este pedido da pessoa: «{a.get('prompt', '')}»")
    print('3. Faça UMA pergunta por vez e espere a resposta. Se a ação pede explorar o repositório, mostre só 2 lugares.')
    print('4. Avalie a resposta final pela rubrica 0–4: ' + ' · '.join(f'{k} = {v}' for k, v in propriedade.RUBRICA.items())
          + '. Valor ganho: 4 = 100%, 3 = 75%, 2 = 50%, 0–1 = tente de novo.')
    print('5. Diga a nota e o porquê em uma linha, com um ponto forte e um próximo passo.')
    print(f'6. Registre: {CLI} registrar {a["id"]} --nota <0-4> --resumo "<1 linha do que a pessoa demonstrou, sem nomes da empresa>"')


# ------------------------------------------------------------------ main
COMANDOS = [
    'triage', 'next-level', 'rota', 'feedback-progress', 'feedback-skills-opportunities', 'acoes', 'fazer', 'prompt',
    'registrar', 'revisitar', 'descartar', 'restaurar', 'subir', 'dossie', 'cartao', 'fila', 'enviar', 'career-map', 'modo',
    'modelo',
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
    ap.add_argument('--pergunta', default='')
    ap.add_argument('--motivo', default='nao_faz_sentido', choices=list(jogo.MOTIVOS))
    ap.add_argument('--onde', default='', help='Onde o feixe foi aberto (ex.: "sessão nova", "aqui")')
    args = ap.parse_args()

    entrada_path = Path(args.entrada)
    rotulo = args.rotulo or f'cmd-{args.comando}'

    if args.comando == 'modo':
        if args.valor not in MODOS:
            print(f'Use: modo {"|".join(MODOS)}')
            return
        set_mode(args.valor)
        print(f'✨ Luzia agora está em modo **{args.valor}**.')
        return

    if args.comando == 'modelo':
        from . import modelo
        s = modelo.status()
        print('## ✨ Luzia · modelo')
        print(f"**{s['nome_provedor']}** · `{s['modelo']}`" + (f" · {s['base_url']}" if s.get('base_url') else ''))
        print(f"chave: {'configurada' if s['chave_configurada'] else 'FALTANDO'} · "
              f"SDK: {'instalado' if s['sdk_instalado'] else 'falta: pip install ' + s['pip']}")
        print('Troque em Ajustes > Modelo da Luzia, no painel (/luzia:career-map). A chave fica só no .env desta máquina.')
        if args.valor == 'testar':
            r = modelo.chamar('Responda só com o JSON {"ok": true}.', 'Responda só com JSON.')
            print(f"teste: {r['texto'].strip()[:60]} · {r['segundos']:.1f} s · {r['tokens_in']}→{r['tokens_out']} tokens · {r['provedor']}/{r['modelo']}")
            if r.get('aviso'):
                print(f"⚠️ {r['aviso']}")
        return

    if args.comando == 'career-map':
        import webbrowser
        if not panel_up():
            start_panel()
        print(f'## ✨ Luzia · painel aberto em {PAINEL}')
        try:
            webbrowser.open(PAINEL)
        except Exception:
            pass
        return

    if args.comando == 'triage':
        plan, rec, hits = execute_triage(entrada_path, rotulo=rotulo, save_state=not args.salvar_json)
        if args.salvar_json:
            Path(args.salvar_json).write_text(
                json.dumps({'plano': plan, 'custo': rec, 'hits': hits}, ensure_ascii=False, indent=2), encoding='utf-8',
            )
            return
        plan = pipeline.load_state().get('plano', {})
        print('## ✨ Luzia · triagem')
        print(f"📍 {plan['onde_esta']['resumo']}\n🎯 {plan['aonde_quer_chegar']['resumo']}\n")
        rota_texto(plan)
        primeiros = [a for a in acoes.todas(plan) if a['origem'] == 'rota']
        print('\n**Primeiros feixes:**')
        for a in primeiros[:3]:
            print(feixe_linha(a))
        oferecer(primeiros)
        footer(rec, hits)
        return

    if args.comando == 'feedback-progress':
        _, rec, hits = daily_call('progress', entrada_path, rotulo)
        state = pipeline.load_state()
        todas = acoes.todas(state.get('plano', {}))
        print('## ✨ Luzia · luz própria nas suas entregas')
        for e in propriedade_entregas(state):
            print_entrega(e, todas)
        print('\n_P1 inferido dos seus prompts · P2 calculado do commit · P3/P4 só com evidência registrada._')
        oferecer([a for a in todas if a['origem'] == 'entrega'])
        footer(rec, hits)
        return

    if args.comando == 'feedback-skills-opportunities':
        resp, rec, hits = daily_call('opportunities', entrada_path, rotulo)
        plan = pipeline.load_state().get('plano', {})
        sessao = [a for a in acoes.todas(plan) if a['origem'] == 'sessão']
        print('## ✨ Luzia · oportunidades nesta sessão')
        print(f"_{resp.get('resumo_sessao', '')}_\n")
        for a in sessao:
            print(feixe_linha(a))
            print(f"   ↳ {a.get('gatilho', '')}")
        oferecer(sessao)
        footer(rec, hits)
        return

    state = pipeline.load_state()
    plan = state.get('plano', {})
    if not plan:
        print('A Luzia ainda não fez a triagem. Rode /luzia:triage.')
        return

    if args.comando in ('next-level', 'rota'):
        todas = acoes.todas(plan)
        print('## ✨ Luzia · sua rota até Plena')
        rota_texto(plan)
        cfg = load_cfg(entrada_path) if entrada_path.exists() else {}
        rit = jogo.ritmo(plan, cfg.get('horizonte', ''))
        print(f"\n_Calibragem: para chegar em ~{rit['meses']} meses, uns **{rit['feixes_semana']} feixe{'s' if rit['feixes_semana'] > 1 else ''} por semana**. "
              'É só referência: o que move a rota é o que você conquista._')
        por_skill: dict[str, list] = {}
        for a in todas:
            if a['estado'] != 'conquistado':
                por_skill.setdefault(a.get('skill_plano') or a.get('skill', ''), []).append(a)
        for skill, lista in por_skill.items():
            print(f'\n**{skill}**')
            for a in lista[:3]:
                print(f'   {feixe_linha(a)}')
        avisar_degraus(plan)
        oferecer(todas)
        return

    if args.comando == 'acoes':
        lista = acoes.todas(plan, descartados=True)
        print('## ✨ Luzia · seus feixes')
        for estado, nome in (('em_andamento', 'Em andamento'), ('na_fila', 'Na fila'), ('sugerido', 'Sugeridos'),
                             ('conquistado', 'Conquistados'), ('descartado', 'Descartados')):
            grupo = [a for a in lista if a.get('estado') == estado]
            if grupo:
                print(f'\n**{nome}**')
                for a in grupo:
                    print(feixe_linha(a))
        oferecer(lista)
        return

    if args.comando == 'fila':
        lista = [a for a in (acoes.find(plan, f['id']) for f in acoes.fila()) if a]
        print('## ✨ Luzia · feixes que você mandou do painel')
        if not lista:
            print('Nenhum feixe na fila. Abra o painel (/luzia:career-map) e clique em "Enviar".')
        for a in lista:
            print(feixe_linha(a))
        oferecer(lista)
        return

    a = acoes.find(plan, args.valor) if args.valor else None

    if args.comando == 'enviar':
        if not a:
            print(f'Feixe {args.valor} não encontrado.')
            return
        if not jogo.enfileirar(a['id']):
            print(f"`#{a['id']}` não pode ir para a fila: já foi conquistado (e revisitado) ou está descartado.")
            return
        acoes.enfileirar(a['id'], a.get('titulo', ''))
        print(f"➤ `#{a['id']}` na fila: a Luzia oferece na próxima mensagem do seu agente.")
        return

    if args.comando in ('prompt', 'fazer', 'revisitar'):
        if not a:
            print(f'Feixe {args.valor} não encontrado. Rode /luzia:next-level para ver os feixes.')
            return
        if (args.comando == 'revisitar' or a.get('estado') == 'conquistado') and not jogo.pode_revisitar(a):
            print(f"`#{a['id']}` já foi conquistado. Só dá para revisitar uma vez um feixe com nota 2 ou 3.")
            return
        if not jogo.iniciar(a['id'], args.onde or ('revisita' if a.get('estado') == 'conquistado' else '')):
            print(f"`#{a['id']}` está descartado. Restaure antes: `{CLI} restaurar {a['id']}`")
            return
        acoes.desenfileirar(a['id'])
        acoes.registrar_evento(a['id'], 'iniciada', skill=a.get('skill'), origem=a.get('origem'))
        if args.comando == 'prompt':
            print(acoes.prompt_completo(a))
        else:
            roteiro(a)
        return

    if args.comando == 'registrar':
        if not a or args.nota is None:
            print('Use: registrar <id> --nota 0-4 --resumo "..."')
            return
        res = jogo.conquistar(a['id'], args.nota, args.resumo[:200], plan)
        if res.get('erro'):
            print(res['erro'])
            return
        if res.get('tente_de_novo'):
            print(f"◐ Nota {args.nota}/4 ({propriedade.RUBRICA[max(0, min(4, args.nota))]}): ainda não. "
                  f"O feixe `#{a['id']}` continua aberto para você tentar de novo. Sem perda: a próxima tentativa vale o mesmo.")
            return
        acoes.registrar_evento(a['id'], 'concluida', nota=args.nota, resumo=args.resumo[:200], skill=a.get('skill'),
                               entrega=a.get('entrega'), dimensao=a.get('dimensao'), origem=a.get('origem'))
        r = jogo.rota(plan)
        s = next((x for x in r['skills'] if x['nome'] == (a.get('skill_plano') or a.get('skill'))), None)
        print(f"✦ Feixe conquistado · `#{a['id']}` · nota {args.nota}/4 · **+{res['ganho']} lm**"
              + (f" · {s['nome']} {s['lm']}/{s['limiar']} lm" if s else '') + f" · rota {r['degraus_feitos']}/{r['degraus_total']} degraus")
        if res.get('pode_revisitar'):
            print(f"↺ Você pode revisitar uma vez para buscar o restante: `{CLI} revisitar {a['id']}`")
        if a.get('entrega'):
            for e in propriedade_entregas(pipeline.load_state()):
                if e['tarefa'] == a['entrega']:
                    print(f"📦 {e['tarefa']} — luz própria agora **{e['indice']}%** · base {e['base']}")
        avisar_degraus(plan)
        oferecer([x for x in acoes.todas(plan) if x['id'] != a['id']])
        return

    if args.comando == 'descartar':
        if not a:
            print(f'Feixe {args.valor} não encontrado.')
            return
        jogo.descartar(a['id'], args.motivo)
        acoes.desenfileirar(a['id'])
        print(f"✕ `#{a['id']}` descartado ({jogo.MOTIVOS[args.motivo]}). A Luzia leva isso em conta nas próximas sugestões. "
              f"Para trazer de volta: `{CLI} restaurar {a['id']}`")
        return

    if args.comando == 'restaurar':
        if not a:
            print(f'Feixe {args.valor} não encontrado.')
            return
        jogo.restaurar(a['id'])
        print(f"○ `#{a['id']}` voltou para os sugeridos.")
        return

    if args.comando == 'subir':
        skill = jogo.skill_de(args.valor or args.skill, plan)
        res = jogo.subir(skill, plan)
        if res.get('erro'):
            print(f'{skill}: {res["erro"]}.')
            return
        r = res['rota']
        print(f"✦ **{skill}** subiu para o nível {res['para']}. Rota: **{r['degraus_feitos']} de {r['degraus_total']} degraus**.")
        print('O próximo trecho acende: rode /luzia:next-level para ver os feixes do novo nível.')
        if res.get('marco'):
            print(f"🏁 Marco {res['marco']['n']} de 3 alcançado. Dossiê de evidências salvo em `{res['marco']['dossie']}`.")
        return

    if args.comando == 'dossie':
        caminho = jogo.dossie(plan)
        print(f'## ✨ Luzia · dossiê de evidências\nSalvo em `{caminho}` (local, fora do git).')
        print(caminho.read_text(encoding='utf-8'))
        return

    if args.comando == 'cartao':
        if not args.skill or not args.pergunta:
            print('Use: cartao --skill "..." --pergunta "..." [--nota 0-4 --resumo "..."]')
            return
        skill = jogo.skill_de(args.skill, plan)
        if args.nota is not None:
            res = jogo.converter(skill, args.nota, args.pergunta[:60])
            if res.get('erro'):
                print(f"◐ {res['erro']}.")
                return
            nota, lm = res['nota'], res['lm']
            acoes.registrar_evento(acoes.aid('cartao', args.pergunta), 'concluida', nota=nota, resumo=args.resumo[:200],
                                   skill=skill, origem='cartao')
            print(f"✦ Luz própria: nota {nota}/4 · **+{lm} lm** em {skill}" if lm else
                  f"◐ Nota {nota}/4: ainda luz refletida. Fica guardado para você tentar de novo.")
            if not lm:
                acoes.guardar(skill, args.pergunta)
            avisar_degraus(plan)
        else:
            jogo.usar_cartao(skill, 'guardado')
            f = acoes.guardar(skill, args.pergunta)
            print(f"➤ Guardado como feixe `#{f['id']}`: aparece no painel e em /luzia:fazer {f['id']}")
        return


if __name__ == '__main__':
    main()
