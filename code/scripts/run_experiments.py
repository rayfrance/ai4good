"""
run_experiments.py — Executa variações de hiperparâmetros para o relatório.

Gera:
- outputs/experiments.csv  → tabela de resultados
- outputs/mlp_graph_before.png → grafo antes do treinamento
- outputs/mlp_graph_after.png  → grafo depois do treinamento
"""

import sys
import csv
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "src"))

from mlp.data import load_heart, deduplicate, split_stratified, standardize
from mlp.graph import MLPGraph


def draw_mlp(mlp, title="", figsize=(7.5, 5.5)):
    """Desenha o grafo da MLP com camadas alinhadas verticalmente."""
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)

    layer_sizes = mlp.layer_sizes
    max_nodes = max(layer_sizes)
    positions = {}

    for li, size in enumerate(layer_sizes):
        y_coords = np.linspace(max_nodes - 1, 0, size) if size > 1 else [(max_nodes - 1) / 2.0]
        for ni, y_pos in enumerate(y_coords):
            positions[f"L{li}N{ni}"] = (li * 2.6, y_pos)

    state = mlp.graph_state()
    weights = [abs(c["weight"]) for c in state["connections"]]
    max_w = max(weights) if weights else 1.0

    for conn in state["connections"]:
        if conn["from_id"] in positions and conn["to_id"] in positions:
            x1, y1 = positions[conn["from_id"]]
            x2, y2 = positions[conn["to_id"]]
            w = conn["weight"]
            color = "#1f77b4" if w >= 0 else "#d62728"
            norm_w = abs(w) / max_w
            lw = 0.4 + 2.6 * norm_w
            alpha = min(0.9, 0.2 + 0.7 * norm_w)
            ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, alpha=alpha, zorder=1)

    for nid, (x, y_pos) in positions.items():
        circle = plt.Circle((x, y_pos), 0.22, facecolor="#f8f9fa", edgecolor="#2c3e50", linewidth=1.3, zorder=2)
        ax.add_patch(circle)

    layer_names = [f"Entrada ({layer_sizes[0]})"] + [
        f"Oculta {i} ({s})" for i, s in enumerate(layer_sizes[1:-1], 1)
    ] + [f"Saida ({layer_sizes[-1]})"]

    for li, name in enumerate(layer_names):
        ax.text(li * 2.6, max_nodes + 0.3, name, ha="center", va="bottom", fontsize=9, fontweight="bold", color="#2c3e50")

    ax.set_xlim(-0.7, (len(layer_sizes) - 1) * 2.6 + 0.7)
    ax.set_ylim(-0.7, max_nodes + 0.9)
    plt.tight_layout()
    return fig


def run_experiment(X_tr, X_te, y_tr, y_te, arch, lr, epochs, seed=42, label=""):
    """Treina e avalia uma configuração, retorna dict de métricas."""
    mlp = MLPGraph(arch, seed=seed)

    t0 = time.time()
    history = mlp.fit(X_tr, y_tr, learning_rate=lr, epochs=epochs, seed=seed)
    elapsed = time.time() - t0

    preds = np.array([mlp.predict(X_te[i]) for i in range(len(X_te))])
    test_acc = float(np.mean(preds == y_te))

    tp = int(np.sum((preds == 1) & (y_te == 1)))
    fp = int(np.sum((preds == 1) & (y_te == 0)))
    fn = int(np.sum((preds == 0) & (y_te == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    train_acc = history["acc_history"][-1]
    loss_final = history["loss_history"][-1]

    return {
        "label": label,
        "arch": " | ".join(str(a) for a in arch),
        "lr": lr,
        "epochs": epochs,
        "test_acc": round(test_acc, 4),
        "train_acc": round(train_acc, 4),
        "loss_final": round(loss_final, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "time_s": round(elapsed, 2),
        "n_connections": mlp.n_connections,
    }, mlp


def main():
    data_path = ROOT / "code" / "data" / "heart.csv"
    out_dir = ROOT / "outputs"
    out_dir.mkdir(exist_ok=True)

    X, y = load_heart(str(data_path))
    X, y = deduplicate(X, y)
    X_tr, X_te, y_tr, y_te = split_stratified(X, y, test_size=0.2, seed=42)
    X_tr_s, X_te_s, mean, std = standardize(X_tr, X_te)

    print(f"Dataset: {len(X)} unicas | Treino: {len(X_tr)} | Teste: {len(X_te)}")

    # --- Grafo ANTES do treino ---
    mlp_before = MLPGraph([13, 8, 5, 1], seed=42)
    fig = draw_mlp(mlp_before, title="Antes do Treinamento (pesos iniciais Xavier)")
    fig.savefig(out_dir / "mlp_graph_before.png", bbox_inches="tight", dpi=300, facecolor="white")
    plt.close(fig)
    print("Gerado: outputs/mlp_graph_before.png")

    # --- Experimentos ---
    experiments = [
        {"arch": [13, 8, 5, 1], "lr": 0.01,  "epochs": 60,  "label": "Baseline"},
        {"arch": [13, 4, 1],    "lr": 0.01,  "epochs": 60,  "label": "Rede menor (1 oculta)"},
        {"arch": [13, 16, 8, 1],"lr": 0.01,  "epochs": 60,  "label": "Rede maior"},
        {"arch": [13, 8, 5, 1], "lr": 0.05,  "epochs": 60,  "label": "LR alta (0.05)"},
        {"arch": [13, 8, 5, 1], "lr": 0.001, "epochs": 60,  "label": "LR baixa (0.001)"},
        {"arch": [13, 8, 5, 1], "lr": 0.01,  "epochs": 200, "label": "200 epocas"},
    ]

    results = []
    baseline_mlp = None
    for exp in experiments:
        print(f"\nRodando: {exp['label']}...")
        res, mlp = run_experiment(
            X_tr_s, X_te_s, y_tr, y_te,
            arch=exp["arch"], lr=exp["lr"], epochs=exp["epochs"],
            label=exp["label"],
        )
        results.append(res)
        if exp["label"] == "Baseline":
            baseline_mlp = mlp
        print(f"  Test acc: {res['test_acc']:.4f} | Train acc: {res['train_acc']:.4f} | "
              f"Loss: {res['loss_final']:.4f} | F1: {res['f1']:.4f} | {res['time_s']}s")

    # --- Grafo DEPOIS do treino (baseline) ---
    fig = draw_mlp(baseline_mlp, title="Apos Treinamento (60 epocas, LR=0.01)")
    fig.savefig(out_dir / "mlp_graph_after.png", bbox_inches="tight", dpi=300, facecolor="white")
    plt.close(fig)
    print("\nGerado: outputs/mlp_graph_after.png")

    # --- CSV ---
    csv_path = out_dir / "experiments.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Gerado: {csv_path}")

    # --- Tabela formatada ---
    print("\n" + "=" * 80)
    print("TABELA DE RESULTADOS")
    print("=" * 80)
    header = f"{'Experimento':<25} {'Arq.':<15} {'LR':<7} {'Ep.':<5} {'Acc Test':<10} {'Acc Train':<10} {'Loss':<8} {'F1':<8} {'P':<8} {'R':<8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['label']:<25} {r['arch']:<15} {r['lr']:<7} {r['epochs']:<5} "
              f"{r['test_acc']:<10} {r['train_acc']:<10} {r['loss_final']:<8} "
              f"{r['f1']:<8} {r['precision']:<8} {r['recall']:<8}")


if __name__ == "__main__":
    main()
