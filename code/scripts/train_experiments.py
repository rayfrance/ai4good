"""
Script de Treinamento Comparativo:
1. BaselineCNN vs SE_CNN no CIFAR-10 (Dataset Principal)
2. BaselineCNN vs SE_CNN no Fashion-MNIST (Desafio +0.5 VA1)

Salva checkpoints em outputs/checkpoints/ e métricas consolidadas em outputs/metrics.json.
"""

import os
import sys
import json
import argparse
import time

# Adiciona raiz e pasta 'code' ao PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CODE_DIR = os.path.join(ROOT_DIR, "code")
for path in [ROOT_DIR, CODE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import torch
from src.cnn.models import BaselineCNN, SE_CNN, count_parameters
from src.cnn.data_loader import get_cifar10_loaders, get_fashion_mnist_loaders
from src.cnn.trainer import train_model, set_seed


def run_experiment(
    epochs: int = 10,
    batch_size: int = 128,
    lr: float = 1e-3,
    max_train_samples: int = 20000,
    max_test_samples: int = 4000,
    run_fashion: bool = True
):
    set_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== INICIANDO EXPERIMENTO DE ARQUITETURAS NEURAIS (Dispositivo: {device}) ===")
    
    os.makedirs("outputs/checkpoints", exist_ok=True)
    os.makedirs("outputs/plots", exist_ok=True)
    
    all_results = {}
    
    # -------------------------------------------------------------------------
    # 1. CIFAR-10 (Dataset Principal)
    # -------------------------------------------------------------------------
    print("\n" + "="*70)
    print("ETAPA 1: Carregando CIFAR-10 (Imagens 32x32 RGB, 10 classes)")
    print("="*70)
    cifar_train, cifar_test, cifar_classes = get_cifar10_loaders(
        data_dir="code/data/cifar10",
        batch_size=batch_size,
        max_train_samples=max_train_samples,
        max_test_samples=max_test_samples,
        seed=42
    )
    print(f"Treino CIFAR-10: {len(cifar_train.dataset)} amostras | Teste: {len(cifar_test.dataset)} amostras")
    
    # Baseline CNN no CIFAR-10
    print("\n--- Treinando BaselineCNN (CIFAR-10) ---")
    base_cifar = BaselineCNN(in_channels=3, num_classes=10)
    params_base_cifar = count_parameters(base_cifar)
    print(f"Parâmetros treináveis BaselineCNN: {params_base_cifar:,}")
    
    res_base_cifar = train_model(
        model=base_cifar,
        train_loader=cifar_train,
        test_loader=cifar_test,
        num_epochs=epochs,
        lr=lr,
        device=device,
        checkpoint_path="outputs/checkpoints/baseline_cifar10.pt"
    )
    res_base_cifar["parameters"] = params_base_cifar
    all_results["cifar10_baseline"] = res_base_cifar
    
    # SE-CNN no CIFAR-10
    print("\n--- Treinando SE_CNN com Atenção Squeeze-and-Excitation (CIFAR-10) ---")
    se_cifar = SE_CNN(in_channels=3, num_classes=10, reduction=16)
    params_se_cifar = count_parameters(se_cifar)
    print(f"Parâmetros treináveis SE_CNN: {params_se_cifar:,} (+{((params_se_cifar - params_base_cifar)/params_base_cifar)*100:.2f}%)")
    
    res_se_cifar = train_model(
        model=se_cifar,
        train_loader=cifar_train,
        test_loader=cifar_test,
        num_epochs=epochs,
        lr=lr,
        device=device,
        checkpoint_path="outputs/checkpoints/se_cnn_cifar10.pt"
    )
    res_se_cifar["parameters"] = params_se_cifar
    all_results["cifar10_se_cnn"] = res_se_cifar
    
    # -------------------------------------------------------------------------
    # 2. Fashion-MNIST (Desafio +0.5 VA1)
    # -------------------------------------------------------------------------
    if run_fashion:
        print("\n" + "="*70)
        print("ETAPA 2: Carregando Fashion-MNIST (Desafio - Imagens 28x28 Grayscale, 10 classes)")
        print("="*70)
        fashion_train, fashion_test, fashion_classes = get_fashion_mnist_loaders(
            data_dir="code/data/fashion_mnist",
            batch_size=batch_size,
            max_train_samples=max_train_samples,
            max_test_samples=max_test_samples,
            seed=42
        )
        print(f"Treino Fashion-MNIST: {len(fashion_train.dataset)} amostras | Teste: {len(fashion_test.dataset)} amostras")
        
        # Baseline CNN no Fashion-MNIST
        print("\n--- Treinando BaselineCNN (Fashion-MNIST) ---")
        base_fash = BaselineCNN(in_channels=1, num_classes=10)
        params_base_fash = count_parameters(base_fash)
        res_base_fash = train_model(
            model=base_fash,
            train_loader=fashion_train,
            test_loader=fashion_test,
            num_epochs=max(epochs // 2, 5),
            lr=lr,
            device=device,
            checkpoint_path="outputs/checkpoints/baseline_fashion.pt"
        )
        res_base_fash["parameters"] = params_base_fash
        all_results["fashion_baseline"] = res_base_fash
        
        # SE-CNN no Fashion-MNIST
        print("\n--- Treinando SE_CNN (Fashion-MNIST) ---")
        se_fash = SE_CNN(in_channels=1, num_classes=10, reduction=16)
        params_se_fash = count_parameters(se_fash)
        res_se_fash = train_model(
            model=se_fash,
            train_loader=fashion_train,
            test_loader=fashion_test,
            num_epochs=max(epochs // 2, 5),
            lr=lr,
            device=device,
            checkpoint_path="outputs/checkpoints/se_cnn_fashion.pt"
        )
        res_se_fash["parameters"] = params_se_fash
        all_results["fashion_se_cnn"] = res_se_fash
        
    # Salva métricas em JSON
    metrics_path = "outputs/metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[OK] Todas as métricas consolidadas foram salvas em {metrics_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Treinamento comparativo de arquiteturas CNN.")
    parser.add_argument("--epochs", type=int, default=8, help="Número de épocas de treino.")
    parser.add_argument("--batch-size", type=int, default=128, help="Tamanho do lote.")
    parser.add_argument("--lr", type=float, default=1e-3, help="Taxa de aprendizado inicial.")
    parser.add_argument("--max-train", type=int, default=15000, help="Máximo de amostras de treino por dataset.")
    parser.add_argument("--max-test", type=int, default=3000, help="Máximo de amostras de teste por dataset.")
    parser.add_argument("--no-fashion", action="store_true", help="Desativa o segundo dataset Fashion-MNIST.")
    
    args = parser.parse_args()
    run_experiment(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        max_train_samples=args.max_train,
        max_test_samples=args.max_test,
        run_fashion=not args.no_fashion
    )
