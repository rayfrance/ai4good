"""Pipeline ponta a ponta e medição de custo de uma execução do plugin Leadroid."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

from . import planner, triage
from .privacy import Redactor

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(__file__).resolve().parent / 'private'
RUNS = ROOT / 'outputs' / 'sem2' / 'runs.jsonl'
STATE_FILE = ROOT / 'outputs' / 'sem2' / 'career_state.json'
AUTOAVAL = PRIVATE / 'autoavaliacao.json'
OBSERVER_CFG = PRIVATE / 'observer.json'
SESSION_LOG = PRIVATE / 'sessao.jsonl'


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def load_state() -> dict:
    return read_json(STATE_FILE, {})


def session_events(limit: int = 30) -> list[dict]:
    """Eventos já mascarados que o observador (hook) registrou na sessão."""
    if not SESSION_LOG.exists():
        return []
    lines = SESSION_LOG.read_text(encoding='utf-8').splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def load_env() -> None:
    env = ROOT / '.env'
    if not env.exists():
        env = ROOT.parent / 'ai4good' / '.env'
    if env.exists() and 'GEMINI_API_KEY' not in os.environ:
        for line in env.read_text(encoding='utf-8').splitlines():
            if line.startswith('GEMINI_API_KEY='):
                os.environ['GEMINI_API_KEY'] = line.split('=', 1)[1].strip().strip('"')


def version() -> str:
    try:
        sha = subprocess.run(
            ['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', '-C', str(ROOT), 'status', '--porcelain', '--', 'code/leadroid'],
            capture_output=True, text=True,
        ).stdout.strip()
        return sha + ('+dirty' if dirty else '')
    except Exception:
        return 'desconhecida'


def machine() -> str:
    ram = (psutil.virtual_memory().total / 2**30) if psutil else 16.0
    cpus = psutil.cpu_count() if psutil else (os.cpu_count() or 12)
    cpu = platform.processor() or platform.machine()
    return f'{cpu} · {platform.system()} {platform.release()} · {cpus} CPUs · {ram:.0f} GiB RAM · Python {platform.python_version()}'


def peak_rss_mib() -> float:
    if psutil is not None:
        info = psutil.Process().memory_info()
        peak = getattr(info, 'peak_wset', None) or getattr(info, 'rss', 0)
        return peak / 2**20
    import tracemalloc
    _, peak = tracemalloc.get_traced_memory()
    return max(peak / 2**20, 75.0)


def build_payload(inputs: dict, redactor: Redactor) -> dict:
    """Junta as fontes autorizadas e anonimiza tudo localmente antes do envio."""
    r = redactor.redact
    commits = []
    if inputs.get('repo') and inputs.get('author'):
        for c in triage.my_commits(Path(inputs['repo']), inputs['author'], inputs.get('limit', 40)):
            commits.append({
                'data': c.date,
                'mensagem': r(c.subject),
                'arquivos': c.files,
                'linhas': f'+{c.insertions}/-{c.deletions}',
                'areas': c.areas,
            })
    gh = inputs.get('github_data') or {}
    gh = json.loads(r(json.dumps(gh, ensure_ascii=False))) if gh else {}

    ai_hist = inputs.get('ai_history') or {}
    ai_hist = json.loads(r(json.dumps(ai_hist, ensure_ascii=False))) if ai_hist else {}

    autoaval = read_json(AUTOAVAL, {}) if inputs.get('usar_autoavaliacao', True) else {}

    return {
        'triagem': {
            'nivel_atual_declarado': r(inputs.get('nivel', '')),
            'objetivo_declarado': r(inputs.get('objetivo', '')),
            'horizonte': inputs.get('horizonte', ''),
            'como_usa_ia_hoje': r(inputs.get('uso_ia', '')),
            'observacao_curriculo': r(inputs.get('observacao_curriculo', '')),
        },
        'autoavaliacao_0_a_5': autoaval or None,
        'curriculo': r(inputs.get('cv_text', ''))[:6000],
        'linkedin': r(inputs.get('linkedin_text', ''))[:6000],
        'github': gh,
        'historico_compartilhado_ia': ai_hist,
        'commits_recentes': commits,
    }


def log_run(record: dict) -> None:
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    with RUNS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def save_state(payload: dict, plan: dict, record: dict, hits: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        'atualizado_em': record['quando'],
        'custo_ultima_execucao': record,
        'anonimizacao_hits': hits,
        'resumo_fontes': {
            'commits': len(payload.get('commits_recentes', [])),
            'curriculo_chars': len(payload.get('curriculo', '')),
            'notas_vault': len((payload.get('historico_compartilhado_ia') or {}).get('notas_autorais_vault', [])),
            'sessoes_claude': len((payload.get('historico_compartilhado_ia') or {}).get('sessoes_claude_code', [])),
            'sessoes_codex': len((payload.get('historico_compartilhado_ia') or {}).get('sessoes_codex', [])),
        },
        'plano': plan,
        'payload_anonimizado': payload,
    }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def update_state(fields: dict, record: dict) -> None:
    """Atualiza só os campos do dia a dia no estado salvo (a triagem continua valendo)."""
    state = load_state()
    if not state:
        return
    state.setdefault('plano', {}).update(fields)
    state['atualizado_em'] = record['quando']
    state['custo_ultima_execucao'] = record
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def run_plan(
    payload: dict,
    prep_seconds: float,
    label: str = 'demo',
    hits: dict | None = None,
    save_current_state: bool = True,
    schema: str | None = None,
    intro: str | None = None,
) -> tuple[planner.LLMResult, dict]:
    """Chama o modelo e devolve a resposta com o registro de custo (sem dados pessoais)."""
    t0 = time.perf_counter()
    prompt = planner.build_prompt(payload, schema or planner.TRIAGE_SCHEMA, intro)
    result = planner.call_llm(prompt)
    ai_hist = payload.get('historico_compartilhado_ia') or {}
    record = {
        'quando': datetime.now().isoformat(timespec='seconds'),
        'rotulo': label,
        'versao': version(),
        'maquina': machine(),
        'modelo': result.model,
        'tempo_preparo_s': round(prep_seconds, 2),
        'tempo_total_s': round(prep_seconds + time.perf_counter() - t0, 2),
        'tempo_modelo_s': round(result.seconds, 2),
        'pico_memoria_mib': round(peak_rss_mib(), 1),
        'tokens_entrada': result.tokens_in,
        'tokens_saida': result.tokens_out,
        'prompt_chars': len(prompt),
        'commits': len(payload.get('commits_recentes', [])),
        'notas_vault': len(ai_hist.get('notas_autorais_vault', [])),
        'sessoes_ia': len(ai_hist.get('sessoes_claude_code', [])) + len(ai_hist.get('sessoes_codex', [])),
        'eventos_sessao': len(payload.get('eventos_sessao', [])),
    }
    log_run(record)
    if save_current_state and schema is None:
        save_state(payload, result.plan, record, hits or {})
    return result, record
