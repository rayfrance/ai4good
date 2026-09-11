"""
Gradient checking numérico para o backpropagation da MLPGraph.

Verifica que o gradiente analítico (backprop) concorda com a
estimativa numérica por diferenças finitas (forward vs central).

Usa uma rede pequena (2 → 3 → 1) para tornar o teste rápido.
"""

import numpy as np
import pytest

from mlp.graph import MLPGraph
from mlp.losses import binary_cross_entropy


EPS = 1e-5          # perturbação numérica
TOLERANCE = 1e-4    # diferença máxima aceitável


def numerical_gradient_weights(mlp: MLPGraph, x: np.ndarray, y: float) -> list[float]:
    """
    Estima ∂L/∂w_i numericamente para cada peso.

    Usa diferença central: (L(w+ε) - L(w-ε)) / (2ε)
    """
    grads = []
    for conn in mlp._connections:
        original = conn.weight

        conn.weight = original + EPS
        loss_plus = binary_cross_entropy(
            np.array([mlp.forward(x)]), np.array([y])
        )

        conn.weight = original - EPS
        loss_minus = binary_cross_entropy(
            np.array([mlp.forward(x)]), np.array([y])
        )

        conn.weight = original  # restaura
        grads.append((loss_plus - loss_minus) / (2.0 * EPS))

    return grads


def analytical_gradient_weights(mlp: MLPGraph, x: np.ndarray, y: float, lr: float = 1.0) -> list[float]:
    """
    Obtém o gradiente analítico via backprop.

    Executa train_step com lr=1.0 e calcula a diferença de peso
    (Δw = w_antes - w_depois = lr * grad), o que dá diretamente o gradiente.
    """
    w_before = [c.weight for c in mlp._connections]
    mlp.train_step(x, y, learning_rate=lr)
    w_after = [c.weight for c in mlp._connections]

    # Restaura pesos originais
    for conn, w in zip(mlp._connections, w_before):
        conn.weight = w

    # Δw = lr * grad → grad = Δw / lr = w_before - w_after
    return [wb - wa for wb, wa in zip(w_before, w_after)]


class TestGradientChecking:
    """Compara gradiente analítico com estimativa numérica."""

    def setup_method(self):
        """Rede pequena e entrada fixa para cada teste."""
        self.mlp = MLPGraph([2, 3, 1], seed=42)
        rng = np.random.default_rng(99)
        self.x = rng.standard_normal(2)
        self.y = 1.0

    def test_gradients_close(self):
        numerical = numerical_gradient_weights(self.mlp, self.x, self.y)
        analytical = analytical_gradient_weights(self.mlp, self.x, self.y, lr=1.0)

        max_diff = max(abs(n - a) for n, a in zip(numerical, analytical))
        assert max_diff < TOLERANCE, (
            f"Gradient check falhou. Diferença máxima: {max_diff:.6f} "
            f"(tolerância: {TOLERANCE})"
        )

    def test_all_weights_checked(self):
        """Certifica que estamos verificando todos os pesos."""
        expected = 2 * 3 + 3 * 1  # 9
        assert self.mlp.n_connections == expected

    def test_gradients_not_all_zero(self):
        """Backprop não pode retornar gradientes todos nulos."""
        analytical = analytical_gradient_weights(self.mlp, self.x, self.y, lr=1.0)
        assert any(abs(g) > 1e-10 for g in analytical), \
            "Todos os gradientes são zero — backprop não está propagando."

    def test_gradient_check_class_zero(self):
        """Testa também com target=0."""
        mlp = MLPGraph([2, 3, 1], seed=13)
        x = np.array([0.5, -0.3])
        y = 0.0

        numerical = numerical_gradient_weights(mlp, x, y)
        analytical = analytical_gradient_weights(mlp, x, y, lr=1.0)

        max_diff = max(abs(n - a) for n, a in zip(numerical, analytical))
        assert max_diff < TOLERANCE, (
            f"Gradient check (y=0) falhou. Diferença máxima: {max_diff:.6f}"
        )
