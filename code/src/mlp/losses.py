"""Função de perda Binary Cross-Entropy e sua derivada."""

import numpy as np


def binary_cross_entropy(y_pred: np.ndarray, y_true: np.ndarray, eps: float = 1e-12) -> float:
    """
    BCE = -[ y * log(ŷ) + (1-y) * log(1-ŷ) ]

    Args:
        y_pred: saída da rede, shape (n,) ou escalar, valores em (0, 1)
        y_true: rótulos binários, shape (n,) ou escalar
        eps: clamp para evitar log(0)

    Returns:
        Perda média escalar.
    """
    y_pred = np.clip(y_pred, eps, 1.0 - eps)
    return -float(np.mean(y_true * np.log(y_pred) + (1.0 - y_true) * np.log(1.0 - y_pred)))


def binary_cross_entropy_prime(y_pred: np.ndarray, y_true: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """
    Gradiente da BCE em relação a ŷ (antes de combinar com sigmoid_prime).

    dL/dŷ = -(y/ŷ) + (1-y)/(1-ŷ)

    Quando combinado com sigmoid na saída:
        dL/dz = dL/dŷ * dŷ/dz = ŷ - y  (simplificação elegante)
    """
    y_pred = np.clip(y_pred, eps, 1.0 - eps)
    return -(y_true / y_pred) + (1.0 - y_true) / (1.0 - y_pred)
