"""
MLP Prática — Aplicação Streamlit
==================================
Execução:
    streamlit run code/scripts/mlp_streamlit.py

Mostra:
  - Arquitetura e hiperparâmetros configuráveis
  - Grafo DOT da MLP (arestas azuis/vermelhas por sinal do peso)
  - Curvas de loss e acurácia por época
  - Acurácia final no conjunto de teste
  - Inferência por amostra selecionada
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import streamlit as st

# ---------------------------------------------------------------------------
# Ajuste de path para importar o pacote src/mlp/
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[2]  # raiz do repositório
sys.path.insert(0, str(_ROOT / "code" / "src"))

from mlp.graph import MLPGraph
from mlp.data import load_heart, split_stratified, standardize

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DATA_PATH = _ROOT / "code" / "data" / "heart.csv"
FEATURE_NAMES = [
    "age", "sex", "cp", "trestbps", "chol",
    "fbs", "restecg", "thalach", "exang",
    "oldpeak", "slope", "ca", "thal",
]

# ---------------------------------------------------------------------------
# Helpers de visualização DOT
# ---------------------------------------------------------------------------

def _build_dot(state: dict, max_nodes_shown: int = 5) -> str:
    """
    Gera especificação DOT da MLP a partir do graph_state().

    Para redes com muitos neurônios por camada, mostra apenas os primeiros
    `max_nodes_shown` para manter o gráfico legível, com label de resumo.
    Arestas azuis = peso positivo; vermelhas = peso negativo.
    Espessura proporcional à magnitude normalizada.
    """
    lines = [
        'digraph MLP {',
        '  rankdir=LR;',
        '  node [shape=circle, width=0.4, fontsize=8];',
        '  edge [fontsize=6];',
        '  splines=line;',
        '  nodesep=0.3;',
    ]

    layers = state["layers"]
    connections = state["connections"]

    # Descobre quais nós serão mostrados (subconjunto por camada)
    visible_nodes: set[str] = set()
    for li, layer in enumerate(layers):
        neurons = layer["neurons"]
        shown = neurons[:max_nodes_shown]
        for n in shown:
            visible_nodes.add(n["id"])

        # Nó de resumo se camada for truncada
        if len(neurons) > max_nodes_shown:
            summary_id = f"L{li}_more"
            hidden_count = len(neurons) - max_nodes_shown
            lines.append(
                f'  {summary_id} [shape=plaintext, label="...+{hidden_count}"];'
            )

        # Subgraph para alinhar verticalmente
        lines.append(f'  subgraph cluster_L{li} {{')
        lines.append(f'    label="{layer["activation_type"]}";')
        lines.append('    style=invis;')
        for n in shown:
            act_str = f"{n['activation']:.3f}" if n["activation"] != 0.0 else ""
            label = f"{n['id']}\\n{act_str}" if act_str else n["id"]
            lines.append(f'    {n["id"]} [label="{label}"];')
        if len(neurons) > max_nodes_shown:
            summary_id = f"L{li}_more"
            lines.append(f'    {summary_id};')
        lines.append('  }')

    # Arestas — apenas entre nós visíveis
    for conn in connections:
        if conn["from_id"] not in visible_nodes or conn["to_id"] not in visible_nodes:
            continue
        color = conn["color"]
        pw = conn["penwidth"]
        w_label = f"{conn['weight']:.3f}"
        lines.append(
            f'  {conn["from_id"]} -> {conn["to_id"]} '
            f'[color={color}, penwidth={pw}, label="{w_label}"];'
        )

    lines.append('}')
    return '\n'.join(lines)


def _accuracy(mlp: MLPGraph, X: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> float:
    preds = np.array([mlp.predict(X[i], threshold) for i in range(len(X))])
    return float(np.mean(preds == y))


# ---------------------------------------------------------------------------
# Carregamento e pré-processamento (cacheados)
# ---------------------------------------------------------------------------

@st.cache_data
def load_and_split(seed: int):
    """Carrega heart.csv, divide e padroniza. Resultado cacheado."""
    X, y = load_heart(DATA_PATH)
    X_train, X_test, y_train, y_test = split_stratified(X, y, test_size=0.2, seed=seed)
    X_train_s, X_test_s, mean, std = standardize(X_train, X_test)
    return X_train_s, X_test_s, y_train, y_test, mean, std


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="MLP — Heart Disease",
        page_icon="🫀",
        layout="wide",
    )

    st.title("🫀 MLP do Zero — Heart Disease")
    st.caption(
        "MLP implementada manualmente como grafo (sem TensorFlow/PyTorch). "
        "Backpropagation via chain rule. Dataset: UCI Heart Disease (1025 amostras)."
    )

    # ------------------------------------------------------------------
    # Sidebar — configuração
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Configuração")

        st.subheader("Arquitetura")
        h1 = st.number_input("Neurônios camada oculta 1", min_value=1, max_value=64, value=8)
        h2 = st.number_input("Neurônios camada oculta 2", min_value=1, max_value=64, value=5)
        arch = [13, int(h1), int(h2), 1]
        st.info(f"Arquitetura: {' | '.join(str(a) for a in arch)}")

        st.subheader("Hiperparâmetros")
        lr = st.number_input("Learning rate", min_value=1e-4, max_value=1.0, value=0.01, format="%.4f")
        epochs = st.slider("Épocas", min_value=1, max_value=200, value=60)
        seed = st.number_input("Semente", min_value=0, max_value=9999, value=42)
        threshold = st.slider("Limiar de decisão", 0.0, 1.0, 0.5, 0.01)

        st.subheader("Visualização")
        max_nodes = st.slider("Nós visíveis por camada", 2, 13, 5)

        btn_train = st.button("🚀 Treinar", type="primary", use_container_width=True)
        btn_reset = st.button("🔄 Resetar", use_container_width=True)

    # ------------------------------------------------------------------
    # Estado da sessão
    # ------------------------------------------------------------------
    if "mlp" not in st.session_state or btn_reset:
        st.session_state.mlp = None
        st.session_state.history = None
        st.session_state.test_acc = None
        st.session_state.arch = arch
        st.session_state.mean = None
        st.session_state.std = None

    # Verifica dataset
    if not DATA_PATH.exists():
        st.error(
            f"Dataset não encontrado em `{DATA_PATH}`.\n\n"
            "Coloque `heart.csv` na pasta `code/data/`. "
            "Veja `code/data/README.md` para instruções de download."
        )
        st.stop()

    # Carrega dados
    try:
        X_train, X_test, y_train, y_test, mean, std = load_and_split(int(seed))
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

    # ------------------------------------------------------------------
    # Info estática do dataset
    # ------------------------------------------------------------------
    with st.expander("📊 Dados do dataset", expanded=False):
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Total de amostras", 1025)
        col_b.metric("Features", 13)
        col_c.metric("Treino (80%)", len(X_train))
        col_d.metric("Teste (20%)", len(X_test))

        st.caption(
            "Padronização Z-score calculada exclusivamente no treino. "
            "Mesmos µ e σ aplicados ao teste e às inferências."
        )

    # ------------------------------------------------------------------
    # Treinamento
    # ------------------------------------------------------------------
    if btn_train:
        mlp = MLPGraph(arch, seed=int(seed))

        loss_hist: list[float] = []
        acc_hist: list[float] = []

        progress_bar = st.progress(0, text="Iniciando treinamento…")
        epoch_text = st.empty()
        col_graph, col_curves = st.columns([1.2, 1])

        graph_placeholder = col_graph.empty()
        chart_placeholder = col_curves.empty()

        def epoch_callback(epoch: int, loss: float, acc: float):
            loss_hist.append(loss)
            acc_hist.append(acc)

            pct = epoch / epochs
            progress_bar.progress(pct, text=f"Época {epoch}/{epochs} — loss: {loss:.4f} — acc treino: {acc:.2%}")

            # Atualiza grafo a cada 5 épocas ou na última
            if epoch % 5 == 0 or epoch == epochs:
                state = mlp.graph_state()
                dot = _build_dot(state, max_nodes_shown=max_nodes)
                graph_placeholder.graphviz_chart(dot, use_container_width=True)

            # Atualiza curvas
            chart_data = {
                "Loss": loss_hist,
                "Acurácia Treino": acc_hist,
            }
            chart_placeholder.line_chart(chart_data)

        t0 = time.time()
        history = mlp.fit(
            X_train, y_train,
            learning_rate=float(lr),
            epochs=int(epochs),
            seed=int(seed),
            callback=epoch_callback,
        )
        elapsed = time.time() - t0

        progress_bar.progress(1.0, text=f"✅ Treinamento concluído em {elapsed:.1f}s")

        # Acurácia final no teste (medida UMA única vez)
        test_acc = _accuracy(mlp, X_test, y_test, threshold=float(threshold))

        # Persiste no estado da sessão
        st.session_state.mlp = mlp
        st.session_state.history = history
        st.session_state.test_acc = test_acc
        st.session_state.arch = arch
        st.session_state.mean = mean
        st.session_state.std = std

        st.success(f"🎯 Acurácia no conjunto de teste: **{test_acc:.2%}**")

    # ------------------------------------------------------------------
    # Exibição pós-treinamento (estado persistido)
    # ------------------------------------------------------------------
    if st.session_state.mlp is not None:
        mlp: MLPGraph = st.session_state.mlp
        history = st.session_state.history
        test_acc = st.session_state.test_acc
        mean_vals = st.session_state.mean
        std_vals = st.session_state.std

        st.divider()

        # Métricas de resumo
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Acurácia Teste", f"{test_acc:.2%}")
        col2.metric("Loss final (treino)", f"{history['loss_history'][-1]:.4f}")
        col3.metric("Acurácia treino final", f"{history['acc_history'][-1]:.2%}")
        col4.metric("Total de conexões", mlp.n_connections)

        # Grafo + curvas lado a lado
        col_g, col_c = st.columns([1.2, 1])

        with col_g:
            st.subheader("🕸️ Grafo da MLP")
            st.caption("🔵 Peso positivo · 🔴 Peso negativo · Espessura ∝ |peso|")
            state = mlp.graph_state()
            dot = _build_dot(state, max_nodes_shown=max_nodes)
            st.graphviz_chart(dot, use_container_width=True)

        with col_c:
            st.subheader("📈 Curvas de Treinamento")
            chart_data = {
                "Loss": history["loss_history"],
                "Acurácia Treino": history["acc_history"],
            }
            st.line_chart(chart_data)

        # ------------------------------------------------------------------
        # Inferência por amostra
        # ------------------------------------------------------------------
        st.divider()
        st.subheader("🔍 Inferência")

        sample_idx = st.slider(
            "Selecione uma amostra do conjunto de teste",
            min_value=0,
            max_value=len(X_test) - 1,
            value=0,
        )

        x_raw = X_test[sample_idx]          # já padronizado
        y_true = int(y_test[sample_idx])
        prob = mlp.predict_proba(x_raw)
        pred_class = int(prob >= float(threshold))

        col_inf1, col_inf2, col_inf3 = st.columns(3)
        col_inf1.metric("Probabilidade (classe 1)", f"{prob:.4f}")
        col_inf2.metric("Classe prevista", "🫀 Doença" if pred_class == 1 else "✅ Saudável")
        col_inf3.metric("Classe real", "🫀 Doença" if y_true == 1 else "✅ Saudável")

        if pred_class == y_true:
            st.success("✅ Previsão correta!")
        else:
            st.error("❌ Previsão incorreta.")

        # Valores da amostra selecionada
        with st.expander("Ver valores da amostra (padronizados)", expanded=False):
            import pandas as pd
            df_sample = pd.DataFrame(
                {"Feature": FEATURE_NAMES, "Valor (padronizado)": x_raw.round(4)}
            )
            st.dataframe(df_sample, use_container_width=True, hide_index=True)

        # ------------------------------------------------------------------
        # Detalhes dos pesos
        # ------------------------------------------------------------------
        with st.expander("🔢 Pesos das conexões (primeiras 30)", expanded=False):
            import pandas as pd
            conns = state["connections"][:30]
            df_w = pd.DataFrame([
                {"De": c["from_id"], "Para": c["to_id"], "Peso": round(c["weight"], 6)}
                for c in conns
            ])
            st.dataframe(df_w, use_container_width=True, hide_index=True)

    else:
        st.info("👈 Configure os hiperparâmetros na sidebar e clique em **Treinar**.")


if __name__ == "__main__":
    main()
