"""Pré-processamento do dataset Heart Disease."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np


def load_heart(path: str | Path) -> Tuple[np.ndarray, np.ndarray]:
    """
    Carrega o CSV do Heart Disease e retorna (X, y).

    O CSV deve ter 14 colunas com cabeçalho. A última coluna é o alvo binário.

    Args:
        path: Caminho para heart.csv

    Returns:
        X: float64 array de shape (n_samples, 13)
        y: float64 array de shape (n_samples,), valores 0 ou 1
    """
    data = np.genfromtxt(path, delimiter=",", skip_header=1, dtype=np.float64)
    X = data[:, :-1]   # 13 features
    y = data[:, -1]    # alvo binário
    return X, y


def deduplicate(X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Remove linhas duplicadas de X (mantém a primeira ocorrência).

    O dataset Kaggle johnsmith88/heart-disease-dataset possui 723 duplicatas
    em 1025 registros. Sem deduplicação, amostras idênticas caem em treino
    e teste, inflando artificialmente a acurácia para 100%.

    Args:
        X: features, shape (n, d)
        y: rótulos, shape (n,)

    Returns:
        X_unique, y_unique sem linhas repetidas
    """
    _, idx = np.unique(X, axis=0, return_index=True)
    idx_sorted = np.sort(idx)  # mantém ordem original
    return X[idx_sorted], y[idx_sorted]


def split_stratified(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Divisão estratificada por classe sem usar sklearn.

    Preserva a proporção de cada classe em treino e teste.
    Garante que os índices não se sobrepõem.

    Args:
        X: features
        y: rótulos binários
        test_size: fração para teste (default 0.2)
        seed: semente para reprodutibilidade

    Returns:
        X_train, X_test, y_train, y_test
    """
    rng = np.random.default_rng(seed)

    classes, counts = np.unique(y, return_counts=True)
    train_idx_list: list[np.ndarray] = []
    test_idx_list: list[np.ndarray] = []

    for cls in classes:
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        n_test = max(1, int(len(idx) * test_size))
        test_idx_list.append(idx[:n_test])
        train_idx_list.append(idx[n_test:])

    train_idx = np.concatenate(train_idx_list)
    test_idx = np.concatenate(test_idx_list)

    # Garantia de integridade
    assert len(set(train_idx.tolist()) & set(test_idx.tolist())) == 0, \
        "Vazamento: índices de treino e teste se sobrepõem!"

    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


def standardize(
    X_train: np.ndarray,
    X_test: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Padronização Z-score.

    µ e σ são calculados exclusivamente no treino e reutilizados no teste.
    Colunas com σ = 0 recebem σ = 1 para evitar divisão por zero.

    Returns:
        X_train_std, X_test_std, mean, std
    """
    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std[std == 0] = 1.0

    X_train_std = (X_train - mean) / std
    X_test_std = (X_test - mean) / std

    return X_train_std, X_test_std, mean, std
