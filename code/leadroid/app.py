"""Luzia · Painel Visual @career-map (aberto pelo comando /luzia:career-map no Harness).

A Luzia é uma líder técnica e mentora instalada como plugin no harness do agente
(Claude Code, Cursor, Codex, Antigravity):
- Atua de forma passiva (monitorando a sessão em background) e ativa (intervindo
  quando conceitos do seu plano aparecem na tarefa ou via comandos /luzia:*).
- Guia a pessoa desenvolvedora para alcançar 100% de Propriedade Intelectual e
  reduzir o débito técnico ao programar com IA.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leadroid import pipeline  # noqa: E402

st.set_page_config(page_title='Luzia · @career-map', page_icon='✨', layout='wide')
pipeline.load_env()

ss = st.session_state
if 'loaded_state' not in ss and pipeline.STATE_FILE.exists():
    try:
        saved = json.loads(pipeline.STATE_FILE.read_text(encoding='utf-8'))
        ss.payload = saved.get('payload_anonimizado', {})
        ss.hits = saved.get('anonimizacao_hits', {})
        ss.plan = saved.get('plano', {})
        ss.record = saved.get('custo_ultima_execucao', {})
        ss.loaded_state = True
    except Exception:
        pass

plan = ss.get('plan') or {}
rec = ss.get('record') or {}

# ------------------------------------------------------------------ Sidebar: A Luzia no Harness
st.sidebar.title('✨ Luzia')
st.sidebar.caption('Sua líder técnica e mentora no harness do agente — iluminando sua carreira e preservando sua propriedade intelectual.')

st.sidebar.markdown('### 🔌 Como a Luzia roda')
modo_operacao = st.sidebar.radio(
    'Modo de atuação no Harness (Claude Code / Cursor / Codex / Antigravity):',
    [
        '🟢 Ativo + Passivo (Observa a sessão e intervém ao detectar conceitos do plano)',
        '👀 Passivo (Apenas monitora em background e atualiza este painel)',
        '💬 Sob demanda (Só responde quando chamada via /luzia:* no chat)',
    ],
    index=0,
)

tem_memoria_harness = st.sidebar.toggle(
    'Memória do Harness conectada (Claude + Codex)',
    value=True,
    help='Se desmarcado (usuária nova sem histórico), a Luzia parte exclusivamente da sua autoavaliação nos sliders.',
)

st.sidebar.divider()
st.sidebar.markdown('**Skills & Comandos no Agente:**')
st.sidebar.code(
    '/luzia:triage\n'
    '/luzia:career-map\n'
    '/luzia:feedback-skills-opportunities\n'
    '/luzia:feedback-progress\n'
    '/luzia:next-level',
    language='text',
)

st.sidebar.divider()
st.sidebar.markdown('**⚡ Telemetria do Motor (`exp.md`):**')
st.sidebar.caption(
    f"• Tempo medido: **{rec.get('tempo_total_s', 9.39)} s** *(média 9,85 s vs. 13 s no flx)*\n"
    f"• Memória RSS: **{rec.get('pico_memoria_mib', 82.1)} MiB CLI / 186 MiB UI** *(vs. 300 MiB no flx)*\n"
    f"• Tokens: **{rec.get('tokens_entrada', 10171)} in → {rec.get('tokens_saida', 2426)} out**\n"
    f"• LGPD local ativa · commit `{pipeline.version()}`"
)

# ------------------------------------------------------------------ Cabeçalho do Perfil
c_head1, c_head2, c_head3 = st.columns([2, 2, 1])
c_head1.markdown('### 👤 Momento Atual Declarado\n**Dev Fullstack Júnior 3** *(C#/.NET, MVC, JS, SQL)*')
c_head2.markdown('### 🎯 Meta de Carreira (12 meses)\n**Desenvolvedora Plena** *(DDD, Arquitetura, IA Agêntica)*')
c_head3.metric('Propriedade Média', '62%', 'Meta: 100% nas entregas')

# ------------------------------------------------------------------ 4 Abas do Produto Luzia
t_map, t_obs, t_prop, t_plan = st.tabs([
    '🧭 1 · @career-map (Triagem & Autoavaliação)',
    '⚡ 2 · Na Sessão (@feedback-skills-opportunities)',
    '🧠 3 · Rumo a 100% de Propriedade (@feedback-progress)',
    '🗺️ 4 · Próximo Nível (@next-level · 90d / 6m / 12m)',
])

# ================================================================== ABA 1: @career-map
with t_map:
    st.caption(
        '✨ **Como a Luzia faz a triagem:** currículos (adaptados para vagas) e notas paradas no Obsidian nunca são tratados '
        'como verdade absoluta. A Luzia extrai as habilidades e **pergunta a você sua autoavaliação**, cruzando com a **memória viva do seu harness**.'
    )

    col_cal, col_chart = st.columns([1, 2])
    with col_cal:
        with st.container(border=True):
            st.markdown('##### 🎚️ Sua Autoavaliação (0 a 5)')
            st.caption('Você define seu ponto de partida real em cada habilidade:')
            skills_list = plan.get('skills', [])
            user_levels = {}
            for s in skills_list:
                nome = s['nome']
                default_val = 3 if ('DDD' in nome or 'Arquitetura' in nome) else int(s['atual'])
                user_levels[nome] = st.slider(
                    f"{nome} (Alvo Pleno: {s['alvo']}/5)",
                    0, 5, default_val,
                    key=f"sl_{nome}",
                )

    with col_chart:
        with st.container(border=True):
            st.markdown('##### 📊 Seu Mapa de Carreira: Nível Atual × Meta Plena (12 meses)')
            chart_rows = []
            for s in skills_list:
                nome = s['nome']
                atual_val = user_levels.get(nome, s['atual'])
                chart_rows.append({'Skill': nome, 'Referência': '1 · Seu Nível Atual', 'Nível': atual_val})
                chart_rows.append({'Skill': nome, 'Referência': '2 · Meta Plena (12m)', 'Nível': s['alvo']})
            df_c = pd.DataFrame(chart_rows)
            chart = (
                alt.Chart(df_c)
                .mark_bar(cornerRadiusEnd=4, size=16)
                .encode(
                    y=alt.Y('Skill:N', title=None, sort=None),
                    x=alt.X('Nível:Q', scale=alt.Scale(domain=[0, 5]), title='Nível (0 a 5)'),
                    color=alt.Color(
                        'Referência:N',
                        scale=alt.Scale(
                            domain=['1 · Seu Nível Atual', '2 · Meta Plena (12m)'],
                            range=['#3b82f6', '#10b981'],
                        ),
                        legend=alt.Legend(orient='top', title=None),
                    ),
                    yOffset='Referência:N',
                    tooltip=['Skill', 'Referência', 'Nível'],
                )
                .properties(height=310)
            )
            st.altair_chart(chart, width='stretch')

            if tem_memoria_harness:
                st.info(
                    '✨ **Calibração da Luzia:** Se a Luzia olhasse só o currículo de vaga, diria que seu Back-end já é `4/5`; '
                    'se olhasse só uma nota antiga do Obsidian (`ddd-cap-01.md`), rebaixaria seu DDD para `1/5`. '
                    'Por isso a Luzia parte da **sua autoavaliação** e acompanha sua evolução real nas sessões do harness.'
                )
            else:
                st.warning(
                    '👤 **Usuária nova sem histórico no harness:** A Luzia montou o mapa a partir da sua autoavaliação '
                    'e passará a aprender com as suas próximas sessões no agente.'
                )

# ================================================================== ABA 2: MONITORAMENTO NA SESSÃO
with t_obs:
    st.caption(
        'Enquanto você programa no Claude Code / Cursor / Antigravity, a skill passiva da Luzia detecta quando um '
        'conceito que falta para você virar Plena aparece na tarefa atual e te guia na hora.'
    )
    ops = plan.get('oportunidades_tarefa_atual', [])
    cols_op = st.columns(len(ops) if ops else 1)
    for col, op in zip(cols_op, ops):
        with col:
            with st.container(border=True):
                st.markdown(f"#### 🎯 {op['skill_alvo'].split('·')[0].strip()}")
                st.caption(f"📍 **{op.get('gatilho_detectado', '')}**")
                st.info(f"✨ **A Luzia avisa no chat:** *\"{op.get('alerta_do_observador', '')}\"*")
                st.markdown(f"**🤝 Como conduzir o agente agora:**\n{op.get('como_praticar_com_agente', '')}")
                with st.expander('📚 Ver teoria na prática e como zerar débito técnico'):
                    st.write(op.get('teoria_na_pratica', ''))
                    st.warning(op.get('evitar_delegacao_cega', ''))

# ================================================================== ABA 3: RUMO A 100% DE PROPRIEDADE INTELECTUAL
with t_prop:
    st.caption(
        '✨ **O objetivo da Luzia não é dar uma nota de prova, e sim te guiar até 100% de Propriedade Intelectual sobre o que você constrói com IA.** '
        'Ela observa **P1** (Direção no Prompt), **P2** (Coesão do Commit), **P3** (Aplicação Conceitual) e **P4** (Domínio Arquitetural) e mostra exatamente o que fazer para chegar aos 100%.'
    )

    guias_100 = [
        [
            'Revisar o contrato do helper de descrição dos enums com a camada de domínio (+8%)',
            'Adicionar 1 teste rápido em XUnit garantindo que todos os valores do enum da Jev possuem descrição válida (+8%)',
        ],
        [
            'Separar a regra de cálculo de status no Controller/Service C#, deixando o JavaScript apenas exibir o estado (+20%)',
            'Pedir ao Claude Code para gerar um diagrama curto do fluxo entre o alerta de atraso e o filtro de regime (+18%)',
        ],
        [
            'Extrair a interface `IClassificadorAnexo` no domínio para isolar os 12 arquivos da integração Jev (+25%)',
            'Pedir ao agente para listar os 3 cenários de falha da API Jev e revisar o tratamento de exceção linha a linha (+20%)',
            'Fracionar o próximo PR semelhante em commits menores (1º contrato, 2º cliente HTTP, 3º tela) (+20%)',
        ],
        [
            'Unificar o template HTML de agulhamento em um componente compartilhado para não duplicar entre Web e API (+32%)',
            'Garantir com o agente que uma falha no envio de e-mail não interrompa a transação principal do pedido (+30%)',
        ],
    ]

    for i, t in enumerate(plan.get('tarefas_recentes', [])[:3]):
        base_score = int(t.get('indice_propriedade', 50))
        passos_guia = guias_100[i] if i < len(guias_100) else ['Revisar decisões arquiteturais com a Luzia (+30%)']

        with st.container(border=True):
            # Calcula o ganho conforme a usuária conclui as orientações da Luzia
            concluidos = 0
            st.markdown(f"#### `{t['tarefa']}`")
            st.caption(f"Diagnóstico da Luzia: {t['por_que']} · **Débito técnico:** {t.get('risco_debito_tecnico', '')}")

            st.markdown('**✨ Guia da Luzia para você alcançar 100% de Propriedade Intelectual nesta entrega:**')
            for j, passo_txt in enumerate(passos_guia):
                if st.checkbox(passo_txt, key=f'chk_{i}_{j}'):
                    concluidos += 1

            ganho = int((100 - base_score) * (concluidos / len(passos_guia)))
            score_atual = min(100, base_score + ganho)

            c_bar, c_metric = st.columns([4, 1])
            c_bar.progress(score_atual / 100.0, text=f'Propriedade Intelectual sobre a entrega: {score_atual}% (inicial: {base_score}%)')
            status_lbl = '🟢 100% Dominada!' if score_atual == 100 else ('🟢 Alta' if score_atual >= 80 else '🟡 Em evolução')
            c_metric.metric('Propriedade', f'{score_atual}%', f'+{ganho}% com guia' if ganho else status_lbl)

# ================================================================== ABA 4: PLANO DE CARREIRA 90D / 6M / 12M
with t_plan:
    st.caption(
        'A Luzia usa este planejamento de 90 dias, 6 meses e 12 meses para monitorar suas sessões no harness, '
        'defender a execução do seu plano e incentivar você a praticar o que falta para chegar a Plena.'
    )
    marcos = plan.get('plano', [])
    cols_m = st.columns(len(marcos) if marcos else 3)
    for col, item in zip(cols_m, marcos):
        with col:
            with st.container(border=True):
                st.markdown(f"### 📅 {item['horizonte']}")
                st.caption(item.get('titulo', ''))
                st.markdown('**Instruções para as próximas tarefas:**')
                for p in item.get('passos_detalhados', [item['acao']]):
                    st.markdown(f'- {p}')
                st.info(f"✨ **Como a Luzia age no Harness:** {item.get('intervencao_leadroid_no_harness', '')}")
                st.success(f"🏁 **Sinal de progresso:** {item['sinal_de_progresso']}")
