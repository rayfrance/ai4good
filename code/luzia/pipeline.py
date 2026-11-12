"""Pipeline ponta a ponta e medição de custo de uma execução do plugin Luzia."""

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

from . import arquivos, banco, planner, trajetoria, triage
from .privacy import Redactor

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = arquivos.PRIVATE
RUNS = ROOT / 'outputs' / 'sem2' / 'runs.jsonl'
STATE_FILE = arquivos.ESTADO  # privado (fora do git); outputs/sem2 guarda só a foto do seminário
AUTOAVAL = PRIVATE / 'autoavaliacao.json'
OBSERVER_CFG = PRIVATE / 'observer.json'
SESSION_LOG = PRIVATE / 'sessao.jsonl'


def read_json(path: Path, default):
    return arquivos.ler_json(path, default)


def load_state() -> dict:
    """Estado vivo da carreira: o plano e o resto da última triagem moram no `perfil` do banco."""
    return trajetoria.estado()


def rotulos(state: dict) -> tuple[str, str]:
    """Nomes curtos de onde a pessoa está e aonde quer chegar (ex.: 'Júnior 3' → 'Plena'), do perfil."""
    with trajetoria.abrir() as con:
        guardados = trajetoria.perfil_ler(con, 'rotulos')
    if isinstance(guardados, dict) and guardados.get('onde_esta') and guardados.get('aonde_quer_chegar'):
        return guardados['onde_esta'], guardados['aonde_quer_chegar']
    return _rotulos_de(state)


def _rotulos_de(state: dict) -> tuple[str, str]:
    import re
    plan = state.get('plano', {})
    tri = (state.get('payload_anonimizado') or {}).get('triagem', {})
    out = []
    for campo, declarado, padrao in (('onde_esta', 'nivel_atual_declarado', 'hoje'), ('aonde_quer_chegar', 'objetivo_declarado', 'meta')):
        curto = (plan.get(campo) or {}).get('nivel_curto')
        if not curto:
            m = re.search(r'(J[úu]nior|Plen[oa]|S[êe]nior|Especialista|Tech Lead)(?:\s+n[íi]vel)?\s*(\d)?', tri.get(declarado, ''), re.I)
            curto = ' '.join(x for x in m.groups() if x).strip() if m else padrao
        out.append(curto[:1].upper() + curto[1:])
    return out[0], out[1]


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
    """Carrega as chaves dos provedores do .env (fora do git)."""
    from . import modelo
    modelo.carregar_env()


def version() -> str:
    try:
        sha = subprocess.run(
            ['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', '-C', str(ROOT), 'status', '--porcelain', '--', 'code/luzia'],
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

    autoaval = trajetoria_autoavaliacao() if inputs.get('usar_autoavaliacao', True) else {}

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


def trajetoria_autoavaliacao() -> dict:
    with trajetoria.abrir() as con:
        return trajetoria.declarados(con)


def log_run(record: dict) -> None:
    """Custo de uma chamada: vai para `chamada_modelo` e segue em `outputs/sem2/runs.jsonl` (sem dado pessoal)."""
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    with RUNS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    with trajetoria.abrir() as con, banco.transacao(con):
        con.execute('INSERT INTO chamada_modelo (quando, rotulo, modelo, segundos, tokens_in, tokens_out, registro_json) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (record.get('quando') or datetime.now().isoformat(timespec='seconds'), record.get('rotulo'),
                     record.get('modelo'), record.get('tempo_modelo_s'), record.get('tokens_entrada'),
                     record.get('tokens_saida'), json.dumps(record, ensure_ascii=False)))


def _gravar_estado(state: dict) -> None:
    """Plano e demais campos do estado no `perfil`, mais rótulos; skills novas viram prismas (as conhecidas ficam como estão)."""
    plano = state.get('plano') or {}
    with trajetoria.abrir() as con, banco.transacao(con):
        trajetoria.perfil_gravar(con, 'plano', plano)
        trajetoria.perfil_gravar(con, 'estado_legado', {k: v for k, v in state.items() if k != 'plano'})
        trajetoria.perfil_gravar(con, 'rotulos', dict(zip(('onde_esta', 'aonde_quer_chegar'), _rotulos_de(state))))
        if trajetoria.sincronizar_prismas(con, plano.get('skills', [])):
            trajetoria.acrescentar_versao(con, 'triagem', None)


def save_state(payload: dict, plan: dict, record: dict, hits: dict) -> None:
    anterior = load_state().get('plano', {})
    for chave in ('tarefas_recentes', 'oportunidades_tarefa_atual', '_commits_dia'):
        if chave not in plan and chave in anterior:
            plan[chave] = anterior[chave]
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
    _gravar_estado(state)


def update_state(fields: dict, record: dict) -> None:
    """Atualiza só os campos do dia a dia no estado salvo (a triagem continua valendo)."""
    state = load_state()
    if not state:
        return
    state.setdefault('plano', {}).update(fields)
    state['atualizado_em'] = record['quando']
    state['custo_ultima_execucao'] = record
    with trajetoria.abrir() as con, banco.transacao(con):
        trajetoria.perfil_gravar(con, 'plano', state['plano'])
        trajetoria.perfil_gravar(con, 'estado_legado', {k: v for k, v in state.items() if k != 'plano'})


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
