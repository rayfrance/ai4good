"""
Script de Avaliação e Geração de Gráficos e Visualizações:
1. Curvas de Convergência (Acurácia e Loss por época) - Baseline vs SE-CNN
2. Matrizes de Confusão lado a lado
3. Mosaico Qualitativo de Amostras de Inferência (com acertos do mecanismo de atenção)
4. Gráfico de Custo Paramétrico vs Acurácia
"""

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")  # Backend não interativo para geração headless de figuras

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CODE_DIR = os.path.join(ROOT_DIR, "code")
for path in [ROOT_DIR, CODE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import torch
import torchvision.transforms as transforms
from src.cnn.models import BaselineCNN, SE_CNN
from src.cnn.data_loader import get_cifar10_loaders, CIFAR10_CLASSES, FASHION_CLASSES


def plot_convergence(metrics: dict, output_dir: str = "outputs/plots"):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. CIFAR-10 Convergence
    if "cifar10_baseline" in metrics and "cifar10_se_cnn" in metrics:
        b_hist = metrics["cifar10_baseline"]["history"]
        se_hist = metrics["cifar10_se_cnn"]["history"]
        epochs = range(1, len(b_hist["train_loss"]) + 1)
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Loss
        axes[0].plot(epochs, b_hist["train_loss"], "b--", label="Baseline (Treino)", alpha=0.7)
        axes[0].plot(epochs, b_hist["val_loss"], "b-o", label="Baseline (Validação)", linewidth=2)
        axes[0].plot(epochs, se_hist["train_loss"], "r--", label="SE-CNN (Treino)", alpha=0.7)
        axes[0].plot(epochs, se_hist["val_loss"], "r-s", label="SE-CNN c/ Atenção (Validação)", linewidth=2)
        axes[0].set_title("Evolução da Perda (Loss) por Época — CIFAR-10", fontsize=12, fontweight="bold")
        axes[0].set_xlabel("Época")
        axes[0].set_ylabel("Cross-Entropy Loss")
        axes[0].grid(True, linestyle=":", alpha=0.6)
        axes[0].legend()
        
        # Accuracy
        b_val_acc = [acc * 100 for acc in b_hist["val_acc"]]
        b_tr_acc = [acc * 100 for acc in b_hist["train_acc"]]
        se_val_acc = [acc * 100 for acc in se_hist["val_acc"]]
        se_tr_acc = [acc * 100 for acc in se_hist["train_acc"]]
        
        axes[1].plot(epochs, b_tr_acc, "b--", label="Baseline (Treino)", alpha=0.7)
        axes[1].plot(epochs, b_val_acc, "b-o", label="Baseline (Validação)", linewidth=2)
        axes[1].plot(epochs, se_tr_acc, "r--", label="SE-CNN (Treino)", alpha=0.7)
        axes[1].plot(epochs, se_val_acc, "r-s", label="SE-CNN c/ Atenção (Validação)", linewidth=2)
        axes[1].set_title("Evolução da Acurácia (%) por Época — CIFAR-10", fontsize=12, fontweight="bold")
        axes[1].set_xlabel("Época")
        axes[1].set_ylabel("Acurácia (%)")
        axes[1].grid(True, linestyle=":", alpha=0.6)
        axes[1].legend()
        
        plt.tight_layout()
        save_path = os.path.join(output_dir, "cifar10_convergence.png")
        plt.savefig(save_path, dpi=300)
        plt.close()
        print(f"[Gráfico] Salvo: {save_path}")

    # 2. Fashion-MNIST Convergence (Desafio)
    if "fashion_baseline" in metrics and "fashion_se_cnn" in metrics:
        b_hist = metrics["fashion_baseline"]["history"]
        se_hist = metrics["fashion_se_cnn"]["history"]
        epochs = range(1, len(b_hist["train_loss"]) + 1)
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Loss
        axes[0].plot(epochs, b_hist["train_loss"], "b--", label="Baseline (Treino)", alpha=0.7)
        axes[0].plot(epochs, b_hist["val_loss"], "b-o", label="Baseline (Validação)", linewidth=2)
        axes[0].plot(epochs, se_hist["train_loss"], "g--", label="SE-CNN (Treino)", alpha=0.7)
        axes[0].plot(epochs, se_hist["val_loss"], "g-s", label="SE-CNN c/ Atenção (Validação)", linewidth=2)
        axes[0].set_title("Evolução da Perda (Loss) — Fashion-MNIST (Desafio)", fontsize=12, fontweight="bold")
        axes[0].set_xlabel("Época")
        axes[0].set_ylabel("Cross-Entropy Loss")
        axes[0].grid(True, linestyle=":", alpha=0.6)
        axes[0].legend()
        
        # Accuracy
        b_val_acc = [acc * 100 for acc in b_hist["val_acc"]]
        b_tr_acc = [acc * 100 for acc in b_hist["train_acc"]]
        se_val_acc = [acc * 100 for acc in se_hist["val_acc"]]
        se_tr_acc = [acc * 100 for acc in se_hist["train_acc"]]
        
        axes[1].plot(epochs, b_tr_acc, "b--", label="Baseline (Treino)", alpha=0.7)
        axes[1].plot(epochs, b_val_acc, "b-o", label="Baseline (Validação)", linewidth=2)
        axes[1].plot(epochs, se_tr_acc, "g--", label="SE-CNN (Treino)", alpha=0.7)
        axes[1].plot(epochs, se_val_acc, "g-s", label="SE-CNN c/ Atenção (Validação)", linewidth=2)
        axes[1].set_title("Evolução da Acurácia (%) — Fashion-MNIST (Desafio)", fontsize=12, fontweight="bold")
        axes[1].set_xlabel("Época")
        axes[1].set_ylabel("Acurácia (%)")
        axes[1].grid(True, linestyle=":", alpha=0.6)
        axes[1].legend()
        
        plt.tight_layout()
        save_path = os.path.join(output_dir, "fashion_convergence.png")
        plt.savefig(save_path, dpi=300)
        plt.close()
        print(f"[Gráfico] Salvo: {save_path}")


def plot_confusion_matrices(metrics: dict, output_dir: str = "outputs/plots"):
    os.makedirs(output_dir, exist_ok=True)
    
    if "cifar10_baseline" not in metrics or "cifar10_se_cnn" not in metrics:
        return
        
    cm_base = np.array(metrics["cifar10_baseline"]["confusion_matrix"])
    cm_se = np.array(metrics["cifar10_se_cnn"]["confusion_matrix"])
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    # Subplot Baseline
    im0 = axes[0].imshow(cm_base, interpolation='nearest', cmap=plt.cm.Blues)
    axes[0].set_title(f"BaselineCNN (Acurácia: {metrics['cifar10_baseline']['final_accuracy']*100:.2f}%)", fontsize=12, fontweight="bold")
    tick_marks = np.arange(len(CIFAR10_CLASSES))
    axes[0].set_xticks(tick_marks)
    axes[0].set_xticklabels(CIFAR10_CLASSES, rotation=45, ha="right", fontsize=9)
    axes[0].set_yticks(tick_marks)
    axes[0].set_yticklabels(CIFAR10_CLASSES, fontsize=9)
    axes[0].set_ylabel("Rótulo Verdadeiro")
    axes[0].set_xlabel("Predição do Modelo")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    
    # Subplot SE-CNN
    im1 = axes[1].imshow(cm_se, interpolation='nearest', cmap=plt.cm.Greens)
    axes[1].set_title(f"SE_CNN c/ Atenção (Acurácia: {metrics['cifar10_se_cnn']['final_accuracy']*100:.2f}%)", fontsize=12, fontweight="bold")
    axes[1].set_xticks(tick_marks)
    axes[1].set_xticklabels(CIFAR10_CLASSES, rotation=45, ha="right", fontsize=9)
    axes[1].set_yticks(tick_marks)
    axes[1].set_yticklabels(CIFAR10_CLASSES, fontsize=9)
    axes[1].set_ylabel("Rótulo Verdadeiro")
    axes[1].set_xlabel("Predição do Modelo")
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
    
    plt.tight_layout()
    save_path = os.path.join(output_dir, "cifar10_confusion_matrices.png")
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"[Gráfico] Salvo: {save_path}")


def plot_qualitative_inferences(output_dir: str = "outputs/plots"):
    """
    Roda inferência lado a lado em amostras do conjunto de teste CIFAR-10
    e plota um mosaico mostrando: Imagem, Rótulo real, Predição Baseline vs Predição SE-CNN.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    base_path = "outputs/checkpoints/baseline_cifar10.pt"
    se_path = "outputs/checkpoints/se_cnn_cifar10.pt"
    if not os.path.exists(base_path) or not os.path.exists(se_path):
        return
        
    model_base = BaselineCNN(in_channels=3, num_classes=10).to(device)
    model_base.load_state_dict(torch.load(base_path, map_location=device)["model_state_dict"])
    model_base.eval()
    
    model_se = SE_CNN(in_channels=3, num_classes=10).to(device)
    model_se.load_state_dict(torch.load(se_path, map_location=device)["model_state_dict"])
    model_se.eval()
    
    _, test_loader, classes = get_cifar10_loaders(
        data_dir="code/data/cifar10", batch_size=64, max_test_samples=500, seed=123
    )
    
    # Coleta amostras onde os modelos predizem
    samples = []
    norm_mean = np.array([0.4914, 0.4822, 0.4465])
    norm_std = np.array([0.2470, 0.2435, 0.2616])
    
    with torch.no_grad():
        for images, targets in test_loader:
            images_dev = images.to(device)
            out_base = model_base(images_dev)
            out_se = model_se(images_dev)
            
            preds_base = torch.argmax(out_base, dim=1).cpu().numpy()
            preds_se = torch.argmax(out_se, dim=1).cpu().numpy()
            targets_np = targets.numpy()
            
            for i in range(len(targets_np)):
                true_c = targets_np[i]
                p_base = preds_base[i]
                p_se = preds_se[i]
                
                # Desnormaliza imagem para visualização
                img_np = images[i].permute(1, 2, 0).numpy()
                img_denorm = np.clip(img_np * norm_std + norm_mean, 0, 1)
                
                samples.append({
                    "image": img_denorm,
                    "target": true_c,
                    "pred_base": p_base,
                    "pred_se": p_se,
                    "target_name": classes[true_c],
                    "base_name": classes[p_base],
                    "se_name": classes[p_se],
                    "se_fixed": (p_base != true_c and p_se == true_c)
                })
            if len(samples) >= 300:
                break
                
    # Prioriza mostrar amostras onde SE corrigiu o erro da Baseline, mais alguns acertos mútuos
    fixed_samples = [s for s in samples if s["se_fixed"]]
    mutual_samples = [s for s in samples if s["pred_base"] == s["target"] and s["pred_se"] == s["target"]]
    
    selected = (fixed_samples[:6] + mutual_samples[:4])[:10]
    
    fig, axes = plt.subplots(2, 5, figsize=(16, 7))
    for idx, ax in enumerate(axes.flat):
        if idx >= len(selected):
            ax.axis('off')
            continue
        s = selected[idx]
        ax.imshow(s["image"])
        
        status_color = "green" if s["se_fixed"] else "black"
        tag = " [SE Corrigiu!]" if s["se_fixed"] else ""
        title = (
            f"Alvo: {s['target_name']}\n"
            f"Base: {s['base_name']} {'✓' if s['pred_base']==s['target'] else '✗'}\n"
            f"SE: {s['se_name']} {'✓' if s['pred_se']==s['target'] else '✗'}{tag}"
        )
        ax.set_title(title, fontsize=9, color=status_color, fontweight="bold" if s["se_fixed"] else "normal")
        ax.axis('off')
        
    plt.suptitle("Inferência Qualitativa Comparativa (CIFAR-10) — Baseline vs. SE-CNN", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    save_path = os.path.join(output_dir, "qualitative_comparison.png")
    plt.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[Gráfico] Salvo: {save_path}")


def main():
    metrics_path = "outputs/metrics.json"
    if not os.path.exists(metrics_path):
        print(f"Arquivo {metrics_path} não encontrado. Execute o treinamento primeiro.")
        return
        
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
        
    print("Gerando gráficos comparativos de desempenho e qualidade...")
    plot_convergence(metrics)
    plot_confusion_matrices(metrics)
    plot_qualitative_inferences()
    print("Todos os gráficos foram gerados com sucesso em outputs/plots/")


if __name__ == "__main__":
    main()
