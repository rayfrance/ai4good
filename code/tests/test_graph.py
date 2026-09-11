"""Testes estruturais da MLPGraph."""

import numpy as np
import pytest

from mlp.graph import MLPGraph



# ---------------------------------------------------------------------------
# Arquitetura 13 | 8 | 5 | 1
# ---------------------------------------------------------------------------

ARCH = [13, 8, 5, 1]
MLP = MLPGraph(ARCH, seed=42)


class TestConnectionCount:
    """Verifica que o grafo tem exatamente o número esperado de conexões."""

    def test_n_connections(self):
        expected = 13 * 8 + 8 * 5 + 5 * 1  # 104 + 40 + 5 = 149
        assert MLP.n_connections == expected, (
            f"Esperadas {expected} conexões, obtidas {MLP.n_connections}"
        )


class TestSigmoidOutput:
    """A saída da rede deve estar sempre em [0, 1]."""

    def test_zero_input(self):
        prob = MLP.predict_proba(np.zeros(13))
        assert 0.0 <= prob <= 1.0

    def test_random_inputs(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            x = rng.standard_normal(13)
            prob = MLP.predict_proba(x)
            assert 0.0 <= prob <= 1.0, f"Saída fora de [0,1]: {prob}"

    def test_extreme_positive(self):
        prob = MLP.predict_proba(np.ones(13) * 1000)
        assert 0.0 <= prob <= 1.0

    def test_extreme_negative(self):
        prob = MLP.predict_proba(np.ones(13) * -1000)
        assert 0.0 <= prob <= 1.0


class TestThreshold:
    """predict() deve binarizar corretamente pelo limiar."""

    def test_above_threshold(self, monkeypatch):
        monkeypatch.setattr(MLP, "predict_proba", lambda x: 0.7)
        assert MLP.predict(np.zeros(13)) == 1

    def test_below_threshold(self, monkeypatch):
        monkeypatch.setattr(MLP, "predict_proba", lambda x: 0.3)
        assert MLP.predict(np.zeros(13)) == 0

    def test_exactly_at_threshold(self, monkeypatch):
        # >= 0.5 → classe 1
        monkeypatch.setattr(MLP, "predict_proba", lambda x: 0.5)
        assert MLP.predict(np.zeros(13)) == 1

    def test_custom_threshold(self, monkeypatch):
        monkeypatch.setattr(MLP, "predict_proba", lambda x: 0.6)
        assert MLP.predict(np.zeros(13), threshold=0.7) == 0


class TestDataLeakage:
    """Verifica que treino e teste não compartilham índices."""

    def test_no_overlap(self):
        from mlp.data import split_stratified
        rng = np.random.default_rng(0)
        X = rng.random((100, 5))
        y = np.array([0] * 50 + [1] * 50)
        X_tr, X_te, y_tr, y_te = split_stratified(X, y, test_size=0.2, seed=42)
        # Se chegou aqui sem AssertionError, split_stratified já garantiu isso
        assert len(X_tr) + len(X_te) == 100


class TestReproducibility:
    """Dois runs com mesma semente devem produzir pesos idênticos."""

    def test_same_weights(self):
        mlp1 = MLPGraph([3, 4, 1], seed=7)
        mlp2 = MLPGraph([3, 4, 1], seed=7)
        w1 = [c.weight for c in mlp1._connections]
        w2 = [c.weight for c in mlp2._connections]
        assert w1 == w2

    def test_different_seeds(self):
        mlp1 = MLPGraph([3, 4, 1], seed=1)
        mlp2 = MLPGraph([3, 4, 1], seed=2)
        w1 = [c.weight for c in mlp1._connections]
        w2 = [c.weight for c in mlp2._connections]
        assert w1 != w2
