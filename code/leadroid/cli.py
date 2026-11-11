"""CLI da Luzia, chamado pelos comandos /luzia:* do Claude Code.

- `triage`: triagem completa (feita uma vez; o estado fica salvo).
- `feedback-progress`: propriedade intelectual nas entregas recentes (chama o modelo).
- `feedback-skills-opportunities`: oportunidades da sessão atual (chama o modelo).
- `next-level`: rota 90 dias / 6 meses / 12 meses do plano salvo.
- `career-map`: abre o painel visual (sobe o Streamlit se precisar).
- `modo ativo|passivo|sob_demanda`: como a Luzia observa a sessão.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import pipeline, planner, triage
from .privacy import Redactor

PAINEL = 'http://localhost:8501'
MODOS = ('ativo', 'passivo', 'sob_demanda')


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
        {
            'nome': s['nome'],
            'autoavaliacao': autoaval.get(s['nome'], s.get('autoavaliacao')),
            'alvo': s.get('alvo'),
        }
        for s in plan.get('skills', [])
    ]


def execute_triage(entrada_path: Path, rotulo: str = 'plugin-triage', save_state: bool = True) -> tuple[dict, dict, dict]:
    pipeline.load_env()
    cfg = json.loads(entrada_path.read_text(encoding='utf-8'))
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
        vault = Path(cfg.get('vault', r'C:\Repositorio\Cerebro_Rayane'))
        inputs['ai_history'] = triage.shared_ai_history(vault_dir=vault)
    else:
        inputs['ai_history'] = {}

    payload = pipeline.build_payload(inputs, redactor)
    prep_s = time.perf_counter() - t0
    result, record = pipeline.run_plan(
        payload, prep_seconds=prep_s, label=rotulo, hits=dict(redactor.hits), save_current_state=save_state,
    )
    return result.plan, record, dict(redactor.hits)


def daily_call(kind: str, entrada_path: Path, rotulo: str) -> tuple[dict, dict, dict]:
    """Chamada leve do dia a dia: usa o plano salvo + memória viva (commits e sessão)."""
    pipeline.load_env()
    state = pipeline.load_state()
    plan = state.get('plano', {})
    cfg = json.loads(entrada_path.read_text(encoding='utf-8'))
    t0 = time.perf_counter()
    redactor = make_redactor(cfg)
    payload = {
        'objetivo': plan.get('aonde_quer_chegar', {}),
        'skills': skills_summary(plan),
        'eventos_sessao': pipeline.session_events(),
    }
    if kind == 'progress':
        payload['commits_recentes'] = recent_commits(cfg, redactor)
        schema, intro = planner.PROGRESS_SCHEMA, 'Plano salvo + commits recentes da pessoa (anonimizados por LGPD):'
    else:
        schema, intro = planner.OPPORTUNITIES_SCHEMA, 'Plano salvo + eventos mascarados da sessão atual no agente:'
    prep_s = time.perf_counter() - t0
    result, record = pipeline.run_plan(
        payload, prep_seconds=prep_s, label=rotulo, hits=dict(redactor.hits), schema=schema, intro=intro,
    )
    key = 'tarefas_recentes' if kind == 'progress' else 'oportunidades_tarefa_atual'
    pipeline.update_state({key: result.plan.get(key, [])}, record)
    return result.plan, record, dict(redactor.hits)


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


def panel_up() -> bool:
    try:
        urllib.request.urlopen(PAINEL, timeout=2)
        return True
    except Exception:
        return False


def start_panel() -> None:
    app = Path(__file__).resolve().parent / 'app.py'
    flags = 0
    if sys.platform == 'win32':
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', str(app), '--server.headless', 'true', '--server.port', '8501'],
        cwd=str(pipeline.ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, creationflags=flags,
    )
    for _ in range(30):
        if panel_up():
            return
        time.sleep(0.5)


def set_mode(modo: str) -> None:
    cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {})
    cfg['modo'] = modo
    pipeline.OBSERVER_CFG.parent.mkdir(parents=True, exist_ok=True)
    pipeline.OBSERVER_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Luzia CLI')
    ap.add_argument('comando', choices=[
        'triage', 'feedback-skills-opportunities', 'feedback-progress', 'next-level', 'career-map', 'modo',
    ])
    ap.add_argument('valor', nargs='?', default='')
    ap.add_argument('--entrada', default=str(pipeline.PRIVATE / 'entrada.json'))
    ap.add_argument('--rotulo', default='')
    ap.add_argument('--salvar-json', default='', help='Salva a resposta e o custo num JSON separado (não altera o estado)')
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

    if args.comando == 'triage':
        plan, rec, hits = execute_triage(entrada_path, rotulo=rotulo, save_state=not args.salvar_json)
        if args.salvar_json:
            Path(args.salvar_json).write_text(
                json.dumps({'plano': plan, 'custo': rec, 'hits': hits}, ensure_ascii=False, indent=2), encoding='utf-8',
            )
        print('## ✨ Luzia · triagem')
        print(f"📍 {plan['onde_esta']['resumo']}\n🎯 {plan['aonde_quer_chegar']['resumo']}\n")
        for s in plan.get('skills', []):
            auto = s.get('autoavaliacao')
            print(f"`{bar(auto if auto is not None else s.get('luzia_sugere'))}` **{s['nome']}** "
                  f"{auto if auto is not None else '–'} → {s['alvo']}  · Luzia sugere {s.get('luzia_sugere')}")
        print(f"\n👉 {plan.get('proximo_passo', '')}")
        footer(rec, hits)
        return

    if args.comando == 'feedback-progress':
        plan, rec, hits = daily_call('progress', entrada_path, rotulo)
        print('## ✨ Luzia · propriedade intelectual')
        print(f"_{plan.get('resumo_progresso', '')}_\n")
        for t in plan.get('tarefas_recentes', []):
            idx = int(t.get('indice_propriedade', 0))
            print(f"`{bar(idx, 100, 10)}` **{idx}%** · {t['tarefa']}")
            for p in t.get('passos_para_100', []):
                print(f"   ☐ {p['passo']} **(+{p.get('ganho', 0)}%)**")
        footer(rec, hits)
        return

    if args.comando == 'feedback-skills-opportunities':
        plan, rec, hits = daily_call('opportunities', entrada_path, rotulo)
        print('## ✨ Luzia · oportunidades nesta sessão')
        print(f"_{plan.get('resumo_sessao', '')}_\n")
        for op in plan.get('oportunidades_tarefa_atual', []):
            print(f"🎯 **{op['skill_alvo']}** — {op.get('alerta', '')}")
            print(f"   🤝 {op.get('como_praticar_com_agente', '')}")
        footer(rec, hits)
        return

    state = pipeline.load_state()
    plan = state.get('plano', {})
    rec = state.get('custo_ultima_execucao', {})

    if args.comando == 'next-level':
        print('## ✨ Luzia · próximo nível')
        print(f"🎯 {plan.get('aonde_quer_chegar', {}).get('lacuna_principal', '')}\n")
        for p in plan.get('plano', []):
            print(f"📅 **{p['horizonte']}** · {p.get('titulo', '')}")
            for passo in p.get('passos', []):
                print(f"   ▸ {passo}")
            print(f"   🏁 {p.get('sinal_de_progresso', '')}")
        print(f"\n_Plano da triagem de {state.get('atualizado_em', '?')}._")
        return

    if args.comando == 'career-map':
        import webbrowser
        if not panel_up():
            print('Subindo o painel…')
            start_panel()
        print(f'## ✨ Luzia · painel aberto em {PAINEL}')
        try:
            webbrowser.open(PAINEL)
        except Exception:
            pass


if __name__ == '__main__':
    main()
