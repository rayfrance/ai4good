"""Funções de ativação e suas derivadas."""

import numpy as np


def relu(z: np.ndarray) -> np.ndarray:
    """Rectified Linear Unit: max(0, z)."""
    return np.maximum(0.0, z)


def relu_prime(z: np.ndarray) -> np.ndarray:
    """Derivada do ReLU: 1 se z > 0, 0 caso contrário."""
    return (z > 0).astype(float)


def sigmoid(z: np.ndarray) -> np.ndarray:
    """Sigmoid estável numericamente: 1 / (1 + e^{-z})."""
    # clip para evitar overflow em exp
    z_clipped = np.clip(z, -500, 500)
    return 1.0 / (1.0 + np.exp(-z_clipped))


def sigmoid_prime(z: np.ndarray) -> np.ndarray:
    """Derivada do sigmoid: σ(z) * (1 − σ(z))."""
    s = sigmoid(z)
    return s * (1.0 - s)
