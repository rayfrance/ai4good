"""CLI e motor dos comandos do plugin LuzIA para Claude Code, Cursor, Codex e Antigravity.

Comandos disponíveis (invocados pelos slash commands `/LuzIA:*` ou `@*`):
- `python -m leadroid.cli triage`
- `python -m leadroid.cli feedback-skills-opportunities`
- `python -m leadroid.cli feedback-progress`
- `python -m leadroid.cli next-level`
- `python -m leadroid.cli career-map`
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from . import pipeline, triage
from .privacy import Redactor


def execute_triage(entrada_path: Path, rotulo: str = 'plugin-triage', save_state: bool = True) -> tuple[dict, dict, dict]:
    pipeline.load_env()
    cfg = json.loads(entrada_path.read_text(encoding='utf-8'))
    t0 = time.perf_counter()
    repo = Path(cfg['repo']) if cfg.get('repo') else None
    colleagues = triage.repo_authors(repo) if repo and repo.exists() else []
    redactor = Redactor.from_file(pipeline.PRIVATE / 'termos.txt', extra_colleagues=colleagues)

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
        payload,
        prep_seconds=prep_s,
        label=rotulo,
        hits=dict(redactor.hits),
        save_current_state=save_state,
    )
    return result.plan, record, dict(redactor.hits)


def load_or_run_state(entrada_path: Path, rotulo: str) -> tuple[dict, dict, dict]:
    if pipeline.STATE_FILE.exists():
        st = json.loads(pipeline.STATE_FILE.read_text(encoding='utf-8'))
        return st['plano'], st['custo_ultima_execucao'], st.get('anonimizacao_hits', {})
    return execute_triage(entrada_path, rotulo=rotulo, save_state=True)


def print_cost_footer(rec: dict, hits: dict) -> None:
    masked = ', '.join(f'{k}×{v}' for k, v in hits.items()) or 'nenhum'
    print('\n---')
    print(
        f"**[LuzIA · Telemetria da Execução]** versão `{rec['versao']}` · modelo `{rec['modelo']}`\n"
        f"- **Tempo total:** `{rec['tempo_total_s']} s` (preparo local `{rec['tempo_preparo_s']} s` + LLM `{rec['tempo_modelo_s']} s`) vs. `~13,0 s` estimados no `flx.md`\n"
        f"- **Pico de memória (RSS):** `{rec['pico_memoria_mib']} MiB` vs. `~300 MiB` estimados no `flx.md`\n"
        f"- **Tokens:** `{rec['tokens_entrada']}` entrada / `{rec['tokens_saida']}` saída (`{rec['commits']}` commits + `{rec.get('notas_vault', 0)}` notas do vault + `{rec.get('sessoes_ia', 0)}` sessões IA)\n"
        f"- **Anonimização LGPD local:** {masked} (nenhum código/diff saiu da máquina)\n"
        f"- **Máquina:** {rec['maquina']}"
    )


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Plugin LuzIA CLI')
    ap.add_argument(
        'comando',
        choices=[
            'triage',
            'feedback-skills-opportunities',
            'feedback-progress',
            'next-level',
            'career-map',
        ],
    )
    ap.add_argument('--entrada', default=str(pipeline.PRIVATE / 'entrada.json'))
    ap.add_argument('--rotulo', default='')
    ap.add_argument('--forcar', action='store_true', help='Reexecuta o modelo mesmo se já houver estado salvo')
    ap.add_argument('--salvar-json', default='', help='Salva o plano e o custo num arquivo JSON separado')
    args = ap.parse_args()

    entrada_path = Path(args.entrada)
    rotulo = args.rotulo or f'cmd-{args.comando}'

    if args.comando == 'triage' or args.forcar:
        plan, rec, hits = execute_triage(entrada_path, rotulo=rotulo, save_state=(not args.salvar_json))
        if args.salvar_json:
            Path(args.salvar_json).write_text(
                json.dumps({'plano': plan, 'custo': rec, 'hits': hits}, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
    else:
        plan, rec, hits = load_or_run_state(entrada_path, rotulo=rotulo)

    if args.comando == 'triage':
        print('## ✨ LuzIA · Triagem e Plano de Carreira (`@triage`)')
        print(f"**Onde você está:** {plan['onde_esta']['resumo']}")
        print(f"**Aonde quer chegar:** {plan['aonde_quer_chegar']['resumo']}")
        print(f"**Lacuna principal:** {plan['aonde_quer_chegar']['lacuna_principal']}\n")
        diag = plan.get('diagnostico_fontes') or {}
        if diag.get('conflito_curriculo_vs_realidade'):
            print(f"**Calibração Currículo × Realidade:** {diag['conflito_curriculo_vs_realidade']}")
        if diag.get('padrao_uso_ia_observado'):
            print(f"**Padrão de uso de IA observado:** {diag['padrao_uso_ia_observado']}\n")
        print('### Mapa de Skills (Atual × Alvo Pleno)')
        for s in plan['skills']:
            print(f"- **{s['nome']}**: `{s['atual']}/5` → `{s['alvo']}/5` (*fonte: {s['fonte']}* — {s['evidencia']})")
        print(f"\n**Próximo passo imediato:** {plan['proximo_passo']}")
        print_cost_footer(rec, hits)

    elif args.comando == 'feedback-skills-opportunities':
        print('## ✨ LuzIA · Oportunidades de Prática na Tarefa (`@feedback-skills-opportunities`)')
        for op in plan.get('oportunidades_tarefa_atual', []):
            print(f"- **Skill alvo:** `{op['skill_alvo']}`")
            print(f"  - *Como praticar com o agente:* {op['como_praticar_com_agente']}")
            print(f"  - *Para não delegar no escuro:* {op['evitar_delegacao_cega']}")
        print_cost_footer(rec, hits)

    elif args.comando == 'feedback-progress':
        print('## ✨ LuzIA · Progresso e Propriedade Intelectual (`@feedback-progress`)')
        for t in plan.get('tarefas_recentes', []):
            print(f"- **{t['tarefa']}** — Propriedade: `{t['propriedade']}` ({', '.join(t.get('skills', []))})")
            print(f"  - *Diagnóstico:* {t['por_que']}")
            print(f"  - *Pergunta da LuzIA técnico:* **{t['pergunta_do_lider']}**")
        print_cost_footer(rec, hits)

    elif args.comando == 'next-level':
        print('## ✨ LuzIA · Rota para o Próximo Nível (`@next-level`)')
        print(f"**Lacuna principal (Jr 3 → Pleno):** {plan['aonde_quer_chegar']['lacuna_principal']}\n")
        for p in plan.get('plano', []):
            print(f"- **{p['horizonte']}**: {p['acao']}")
            print(f"  - *Uso educado da IA:* {p['uso_educado_da_ia']}")
            print(f"  - *Sinal de progresso:* {p['sinal_de_progresso']}")
        print(f"\n**Próximo passo:** {plan['proximo_passo']}")
        print_cost_footer(rec, hits)

    elif args.comando == 'career-map':
        import webbrowser
        print('## ✨ LuzIA · Painel Visual (`@career-map`)')
        print(f"Estado sincronizado em `{pipeline.STATE_FILE}`.")
        print('Abrindo o painel visual do LuzIA no navegador: http://localhost:8501')
        try:
            webbrowser.open('http://localhost:8501')
        except Exception:
            pass
        print_cost_footer(rec, hits)


if __name__ == '__main__':
    main()
