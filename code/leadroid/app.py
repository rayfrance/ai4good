"""Luzia · painel @career-map (aberto por /luzia:career-map).

Tudo o que aparece vem do estado salvo pela Luzia (saída do modelo, já anonimizada),
da autoavaliação da pessoa e dos eventos mascarados que o observador registrou na sessão.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leadroid import pipeline  # noqa: E402

st.set_page_config(page_title='Luzia · @career-map', page_icon='✨', layout='wide')

st.markdown(
    """
<style>
.stApp { background: radial-gradient(circle at 20% 0%, #1e1b4b 0%, #0b0b12 60%); color: #f4f4f5; }
[data-testid="stSidebar"] { background: #0f0f1a; }
.block-container { padding-top: 1.6rem; }
.lz-card { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.09); border-radius: 18px;
           padding: 18px 20px; height: 100%; }
.lz-kpi { font-size: 2.6rem; font-weight: 800; line-height: 1; }
.lz-sub { color: #a1a1aa; font-size: .85rem; margin-top: 6px; }
.lz-tag { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .78rem; margin: 2px 4px 2px 0;
          background: rgba(250,204,21,.12); color: #fde68a; border: 1px solid rgba(250,204,21,.25); }
.lz-tag.g { background: rgba(16,185,129,.12); color: #6ee7b7; border-color: rgba(16,185,129,.3); }
.lz-tag.b { background: rgba(59,130,246,.12); color: #93c5fd; border-color: rgba(59,130,246,.3); }
.lz-journey { display:flex; align-items:center; gap:12px; font-weight:700; font-size:1.05rem; }
.lz-track { flex:1; height:10px; border-radius:999px; background:rgba(255,255,255,.08); overflow:hidden; }
.lz-fill { height:100%; background: linear-gradient(90deg,#3b82f6,#a855f7,#facc15); }
.lz-feed { border-left: 3px solid #facc15; padding: 6px 12px; margin: 6px 0; background: rgba(255,255,255,.03);
           border-radius: 0 10px 10px 0; }
.lz-h { font-size: 1.05rem; font-weight: 700; margin-bottom: 6px; }
</style>
""",
    unsafe_allow_html=True,
)

esc = html.escape
state = pipeline.load_state()
plan = state.get('plano', {})
skills = plan.get('skills', [])
autoaval = pipeline.read_json(pipeline.AUTOAVAL, {})
obs_cfg = pipeline.read_json(pipeline.OBSERVER_CFG, {'modo': 'ativo', 'autorizados': []})


def last_run() -> dict:
    if not pipeline.RUNS.exists():
        return {}
    lines = [ln for ln in pipeline.RUNS.read_text(encoding='utf-8').splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else {}


def level(s: dict) -> int:
    v = autoaval.get(s['nome'], s.get('autoavaliacao'))
    return int(v if v is not None else s.get('luzia_sugere', s.get('atual', 0)))


# ------------------------------------------------------------------ barra lateral
st.sidebar.markdown('## ✨ Luzia')
st.sidebar.caption('sua líder técnica no agente')
MODOS = {'ativo': '🟢 Ativa + observando', 'passivo': '👀 Só observando', 'sob_demanda': '💬 Só quando chamada'}
atual_modo = obs_cfg.get('modo', 'ativo')
novo = st.sidebar.radio('Modo', list(MODOS), index=list(MODOS).index(atual_modo), format_func=MODOS.get)
if novo != atual_modo:
    obs_cfg['modo'] = novo
    pipeline.OBSERVER_CFG.parent.mkdir(parents=True, exist_ok=True)
    pipeline.OBSERVER_CFG.write_text(json.dumps(obs_cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    st.sidebar.success('Modo salvo — o observador já segue este modo.')

st.sidebar.divider()
st.sidebar.code('/luzia:feedback-skills-opportunities\n/luzia:feedback-progress\n/luzia:next-level\n/luzia:career-map\n/luzia:triage', language='text')
run = last_run()
if run:
    st.sidebar.divider()
    st.sidebar.caption(
        f"⏱ {run['tempo_total_s']} s · 🧠 {run['pico_memoria_mib']} MiB · 🔤 {run['tokens_entrada']}→{run['tokens_saida']}\n\n"
        f"`{run['rotulo']}` · versão `{run['versao']}` · {run['quando'][11:16]}"
    )

if not plan:
    st.warning('A Luzia ainda não fez a triagem. Rode /luzia:triage no Claude Code.')
    st.stop()

# ------------------------------------------------------------------ topo: a jornada
tarefas = plan.get('tarefas_recentes', [])
prop_media = round(sum(int(t.get('indice_propriedade', 0)) for t in tarefas) / len(tarefas)) if tarefas else 0
soma_atual = sum(level(s) for s in skills)
soma_alvo = sum(int(s.get('alvo', 5)) for s in skills) or 1
jornada = round(100 * soma_atual / soma_alvo)

c1, c2, c3 = st.columns([2.2, 1, 1])
with c1:
    st.markdown(
        f"""<div class="lz-card"><div class="lz-sub">sua jornada · 12 meses</div>
        <div class="lz-journey" style="margin-top:10px">💼 Júnior 3<div class="lz-track"><div class="lz-fill" style="width:{jornada}%"></div></div>🎯 Plena</div>
        <div class="lz-sub">{esc(plan.get('aonde_quer_chegar', {}).get('lacuna_principal', ''))}</div></div>""",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(f'<div class="lz-card"><div class="lz-kpi">{jornada}%</div><div class="lz-sub">do caminho até Plena</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="lz-card"><div class="lz-kpi">{prop_media}%</div><div class="lz-sub">propriedade intelectual média</div></div>', unsafe_allow_html=True)

st.write('')
t_map, t_live, t_prop, t_next = st.tabs(['🧭 Mapa', '⚡ Ao vivo', '🧠 Propriedade', '🗺️ Próximo nível'])

# ------------------------------------------------------------------ mapa de skills
with t_map:
    rows = []
    for s in skills:
        rows.append({
            'Skill': s['nome'], 'Você': level(s), 'Meta': int(s.get('alvo', 5)),
            'Luzia sugere': int(s.get('luzia_sugere', level(s))),
            'Evidência': s.get('evidencia', ''),
        })
    df = pd.DataFrame(rows)
    base = alt.Chart(df).encode(y=alt.Y('Skill:N', sort=None, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=13)))
    chart = (
        base.mark_rule(strokeWidth=6, opacity=.35, color='#a855f7').encode(x=alt.X('Você:Q', scale=alt.Scale(domain=[0, 5]), title='nível 0–5', axis=alt.Axis(tickCount=5)), x2='Meta:Q')
        + base.mark_circle(size=360, color='#3b82f6').encode(x='Você:Q', tooltip=['Skill', 'Você', 'Meta', 'Luzia sugere', 'Evidência'])
        + base.mark_circle(size=360, color='#10b981').encode(x='Meta:Q', tooltip=['Skill', 'Meta'])
        + base.mark_point(shape='diamond', size=120, color='#facc15', filled=True).encode(x='Luzia sugere:Q', tooltip=['Skill', 'Luzia sugere', 'Evidência'])
    ).properties(height=340).configure_view(stroke=None).configure_axis(gridColor='#27272a', labelColor='#d4d4d8', titleColor='#a1a1aa')
    st.altair_chart(chart, use_container_width=True)
    st.markdown('<span class="lz-tag b">● você</span><span class="lz-tag g">● meta Plena</span><span class="lz-tag">◆ Luzia sugere</span>', unsafe_allow_html=True)

    diag = plan.get('diagnostico_fontes', {})
    if diag:
        a, b = st.columns(2)
        a.markdown(f'<div class="lz-card"><div class="lz-h">📄 currículo × prática</div>{esc(diag.get("conflito_curriculo_vs_realidade", ""))}</div>', unsafe_allow_html=True)
        b.markdown(f'<div class="lz-card"><div class="lz-h">🤖 como você usa IA</div>{esc(diag.get("padrao_uso_ia_observado", ""))}</div>', unsafe_allow_html=True)

    with st.expander('🎚️ Ajustar minha autoavaliação'):
        cols = st.columns(3)
        novos = {}
        for i, s in enumerate(skills):
            with cols[i % 3]:
                novos[s['nome']] = st.slider(s['nome'], 0, 5, level(s), key=f"auto_{s['nome']}")
        if st.button('💾 Salvar autoavaliação', type='primary'):
            pipeline.AUTOAVAL.parent.mkdir(parents=True, exist_ok=True)
            pipeline.AUTOAVAL.write_text(json.dumps(novos, ensure_ascii=False, indent=2), encoding='utf-8')
            st.success('Salvo. A Luzia parte destes níveis.')
            st.rerun()

# ------------------------------------------------------------------ ao vivo (observador)
with t_live:
    @st.fragment(run_every='3s')
    def feed() -> None:
        evs = list(reversed(pipeline.session_events(40)))
        k1, k2, k3 = st.columns(3)
        k1.metric('eventos observados', len(evs))
        k2.metric('intervenções', sum(1 for e in evs if e.get('interveio')))
        k3.metric('modo', MODOS.get(pipeline.read_json(pipeline.OBSERVER_CFG, {}).get('modo', 'ativo'), '').split(' ', 1)[-1])
        if not evs:
            st.info('Trabalhe no Claude Code: quando uma skill do seu plano aparecer, ela surge aqui.')
            return
        cont = pd.Series([e['skill'] for e in evs]).value_counts().reset_index()
        cont.columns = ['Skill', 'vezes']
        st.altair_chart(
            alt.Chart(cont).mark_bar(cornerRadiusEnd=6, color='#facc15').encode(
                x=alt.X('vezes:Q', title=None, axis=alt.Axis(tickMinStep=1)), y=alt.Y('Skill:N', sort='-x', title=None, axis=alt.Axis(labelLimit=260)),
            ).properties(height=40 * len(cont) + 20).configure_view(stroke=None).configure_axis(gridColor='#27272a', labelColor='#d4d4d8'),
            use_container_width=True,
        )
        for e in evs[:8]:
            icon = '✨ interveio no chat' if e.get('interveio') else '👀 registrou'
            st.markdown(
                f"<div class='lz-feed'><b>{esc(e['skill'])}</b> · {esc(e.get('extensao', ''))} · {e['quando'][11:16]} · {icon}</div>",
                unsafe_allow_html=True,
            )

    feed()

# ------------------------------------------------------------------ propriedade intelectual
with t_prop:
    for i, t in enumerate(tarefas):
        base_idx = int(t.get('indice_propriedade', 0))
        passos = t.get('passos_para_100', [])
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**{esc(t['tarefa'])}**")
                st.markdown(''.join(f'<span class="lz-tag b">{esc(s)}</span>' for s in t.get('skills', [])), unsafe_allow_html=True)
                ganho = 0
                for j, p in enumerate(passos):
                    if st.checkbox(f"{p['passo']}  **+{p.get('ganho', 0)}%**", key=f'p_{i}_{j}'):
                        ganho += int(p.get('ganho', 0))
                total = min(100, base_idx + ganho)
                st.progress(total / 100, text=f'propriedade {total}%' + (' · 🟢 100%!' if total >= 100 else ''))
                if t.get('risco_debito_tecnico'):
                    st.caption(f"⚠️ {t['risco_debito_tecnico']}")
            with right:
                dims = pd.DataFrame({
                    'dim': ['P1 prompt', 'P2 commit', 'P3 conceito', 'P4 arquitetura'],
                    'v': [t.get('p1_direcao_prompt', 0), t.get('p2_coesao_commit', 0),
                          t.get('p3_aplicacao_conceitual', 0), t.get('p4_dominio_arquitetural', 0)],
                })
                st.altair_chart(
                    alt.Chart(dims).mark_bar(cornerRadiusEnd=4).encode(
                        x=alt.X('v:Q', scale=alt.Scale(domain=[0, 100]), title=None),
                        y=alt.Y('dim:N', sort=None, title=None),
                        color=alt.Color('v:Q', scale=alt.Scale(domain=[0, 100], range=['#ef4444', '#facc15', '#10b981']), legend=None),
                        tooltip=['dim', 'v'],
                    ).properties(height=140).configure_view(stroke=None).configure_axis(gridColor='#27272a', labelColor='#d4d4d8'),
                    use_container_width=True,
                )

# ------------------------------------------------------------------ próximo nível
with t_next:
    icons = {'90 dias': '🌱', '6 meses': '🚀', '12 meses': '🏆'}
    marcos = plan.get('plano', [])
    cols = st.columns(len(marcos) or 1)
    for col, m in zip(cols, marcos):
        passos_html = ''.join(f'<li>{esc(p)}</li>' for p in m.get('passos', []))
        col.markdown(
            f"""<div class="lz-card"><div class="lz-kpi">{icons.get(m['horizonte'], '📅')}</div>
            <div class="lz-h" style="margin-top:8px">{esc(m['horizonte'])} · {esc(m.get('titulo', ''))}</div>
            <ul>{passos_html}</ul>
            <span class="lz-tag">✨ {esc(m.get('como_a_luzia_age', ''))}</span><br>
            <span class="lz-tag g">🏁 {esc(m.get('sinal_de_progresso', ''))}</span></div>""",
            unsafe_allow_html=True,
        )
    st.write('')
    st.markdown(f"<div class='lz-card'>👉 <b>próximo passo:</b> {esc(plan.get('proximo_passo', ''))}</div>", unsafe_allow_html=True)
