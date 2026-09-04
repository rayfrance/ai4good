"""
MLPGraph — MLP construída do zero como grafo explícito.

Componentes
-----------
Neuron      : nó do grafo (id, bias, pre-ativação z, ativação a, delta)
Connection  : aresta do grafo (from_id, to_id, weight)
Layer       : grupo de neurônios com mesmo tipo de ativação
MLPGraph    : rede completa; orquestra forward pass e backpropagation
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .activations import relu, relu_prime, sigmoid, sigmoid_prime
from .losses import binary_cross_entropy


# ---------------------------------------------------------------------------
# Estruturas do grafo
# ---------------------------------------------------------------------------


@dataclass
class Neuron:
    """Nó do grafo da MLP."""

    neuron_id: str          # ex.: "L1N0"
    bias: float = 0.0
    z: float = 0.0          # pré-ativação (net input)
    activation: float = 0.0  # pós-ativação
    delta: float = 0.0      # gradiente local (backprop)


@dataclass
class Connection:
    """Aresta do grafo — conecta dois neurônios com um peso."""

    from_id: str
    to_id: str
    weight: float


@dataclass
class Layer:
    """Camada da MLP com tipo de ativação."""

    neurons: List[Neuron]
    activation_type: str  # "relu" | "sigmoid" | "input"


# ---------------------------------------------------------------------------
# MLPGraph
# ---------------------------------------------------------------------------


class MLPGraph:
    """
    MLP totalmente conectada representada como grafo.

    Parâmetros
    ----------
    layer_sizes : sequência de tamanhos (ex.: [13, 8, 5, 1])
    hidden_activation : "relu" (default)
    seed : semente para reprodutibilidade dos pesos iniciais

    Exemplo
    -------
    >>> mlp = MLPGraph([13, 8, 5, 1], seed=42)
    >>> prob = mlp.predict_proba(np.zeros(13))
    >>> 0.0 <= prob <= 1.0
    True
    """

    def __init__(
        self,
        layer_sizes: List[int],
        hidden_activation: str = "relu",
        seed: int = 42,
    ) -> None:
        if len(layer_sizes) < 2:
            raise ValueError("A rede precisa de pelo menos 2 camadas (entrada e saída).")

        self.layer_sizes = layer_sizes
        self.hidden_activation = hidden_activation
        self.seed = seed

        # Índice rápido: id → Neuron
        self._neurons: Dict[str, Neuron] = {}
        # Lista de conexões (uma por peso)
        self._connections: List[Connection] = []
        # Camadas em ordem
        self.layers: List[Layer] = []

        self._build(seed)

    # ------------------------------------------------------------------
    # Construção do grafo
    # ------------------------------------------------------------------

    def _neuron_id(self, layer_idx: int, neuron_idx: int) -> str:
        return f"L{layer_idx}N{neuron_idx}"

    def _build(self, seed: int) -> None:
        """Cria neurônios, conexões e inicializa pesos (Xavier/Glorot)."""
        rng = np.random.default_rng(seed)

        # --- Neurônios ---
        for li, size in enumerate(self.layer_sizes):
            if li == 0:
                act_type = "input"
            elif li == len(self.layer_sizes) - 1:
                act_type = "sigmoid"
            else:
                act_type = self.hidden_activation

            neurons: List[Neuron] = []
            for ni in range(size):
                nid = self._neuron_id(li, ni)
                n = Neuron(neuron_id=nid)
                neurons.append(n)
                self._neurons[nid] = n

            self.layers.append(Layer(neurons=neurons, activation_type=act_type))

        # --- Conexões com pesos Xavier ---
        for li in range(len(self.layer_sizes) - 1):
            fan_in = self.layer_sizes[li]
            fan_out = self.layer_sizes[li + 1]
            limit = math.sqrt(6.0 / (fan_in + fan_out))

            for from_n in self.layers[li].neurons:
                for to_n in self.layers[li + 1].neurons:
                    w = float(rng.uniform(-limit, limit))
                    conn = Connection(from_id=from_n.neuron_id, to_id=to_n.neuron_id, weight=w)
                    self._connections.append(conn)

    # ------------------------------------------------------------------
    # Lookup rápido
    # ------------------------------------------------------------------

    def _incoming(self, neuron_id: str) -> List[Connection]:
        """Retorna todas as conexões que chegam a `neuron_id`."""
        return [c for c in self._connections if c.to_id == neuron_id]

    def _outgoing(self, neuron_id: str) -> List[Connection]:
        """Retorna todas as conexões que saem de `neuron_id`."""
        return [c for c in self._connections if c.from_id == neuron_id]

    # ------------------------------------------------------------------
    # Ativação por tipo
    # ------------------------------------------------------------------

    @staticmethod
    def _activate(z: float, act_type: str) -> float:
        arr = np.array([z])
        if act_type == "relu":
            return float(relu(arr)[0])
        if act_type == "sigmoid":
            return float(sigmoid(arr)[0])
        return z  # input: identidade

    @staticmethod
    def _activate_prime(z: float, act_type: str) -> float:
        arr = np.array([z])
        if act_type == "relu":
            return float(relu_prime(arr)[0])
        if act_type == "sigmoid":
            return float(sigmoid_prime(arr)[0])
        return 1.0

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def forward(self, inputs: np.ndarray, trace: bool = False) -> float:
        """
        Propaga `inputs` pela rede e retorna a saída sigmoid da última camada.

        Args:
            inputs : array de shape (n_features,)
            trace  : se True, registra z e activation em cada neurônio

        Returns:
            Valor escalar ∈ (0, 1)
        """
        if len(inputs) != self.layer_sizes[0]:
            raise ValueError(
                f"Esperados {self.layer_sizes[0]} features, recebidos {len(inputs)}."
            )

        # Camada de entrada: ativação = valor do feature
        for ni, neuron in enumerate(self.layers[0].neurons):
            neuron.z = float(inputs[ni])
            neuron.activation = float(inputs[ni])

        # Camadas ocultas e saída
        for li in range(1, len(self.layers)):
            layer = self.layers[li]
            for neuron in layer.neurons:
                incoming = self._incoming(neuron.neuron_id)
                z = neuron.bias
                for conn in incoming:
                    z += conn.weight * self._neurons[conn.from_id].activation
                neuron.z = z
                neuron.activation = self._activate(z, layer.activation_type)

        output_neuron = self.layers[-1].neurons[0]
        return output_neuron.activation

    # ------------------------------------------------------------------
    # Backpropagation
    # ------------------------------------------------------------------

    def train_step(
        self,
        inputs: np.ndarray,
        target: float,
        learning_rate: float,
    ) -> float:
        """
        Executa um passo de gradiente descendente em uma única amostra.

        1. Forward pass
        2. Calcula deltas (camada de saída → ocultas)
        3. Atualiza pesos e biases

        Args:
            inputs       : array (n_features,)
            target       : rótulo binário 0 ou 1
            learning_rate: taxa de aprendizado η

        Returns:
            loss BCE escalar para esta amostra
        """
        y_hat = self.forward(inputs)
        loss = binary_cross_entropy(np.array([y_hat]), np.array([target]))

        # --- Camada de saída ---
        # dL/dz = ŷ - y  (BCE + sigmoid simplificados)
        out_neuron = self.layers[-1].neurons[0]
        out_neuron.delta = y_hat - target

        # --- Camadas ocultas (de trás para frente) ---
        for li in range(len(self.layers) - 2, 0, -1):
            layer = self.layers[li]
            for neuron in layer.neurons:
                # Soma dos gradientes vindos da próxima camada
                grad_sum = sum(
                    conn.weight * self._neurons[conn.to_id].delta
                    for conn in self._outgoing(neuron.neuron_id)
                )
                neuron.delta = grad_sum * self._activate_prime(neuron.z, layer.activation_type)

        # --- Atualização de pesos e biases ---
        for conn in self._connections:
            from_activation = self._neurons[conn.from_id].activation
            to_delta = self._neurons[conn.to_id].delta
            conn.weight -= learning_rate * to_delta * from_activation

        for li in range(1, len(self.layers)):
            for neuron in self.layers[li].neurons:
                neuron.bias -= learning_rate * neuron.delta

        return loss

    # ------------------------------------------------------------------
    # Inferência
    # ------------------------------------------------------------------

    def predict_proba(self, inputs: np.ndarray) -> float:
        """Retorna probabilidade escalar ∈ [0, 1]."""
        return self.forward(inputs)

    def predict(self, inputs: np.ndarray, threshold: float = 0.5) -> int:
        """Retorna classe binária (0 ou 1) pelo limiar."""
        return int(self.predict_proba(inputs) >= threshold)

    # ------------------------------------------------------------------
    # Estado do grafo (para a interface)
    # ------------------------------------------------------------------

    def graph_state(self) -> Dict:
        """
        Serializa o estado atual da rede para a camada de visualização.

        Returns:
            dict com:
              - "layers": lista de camadas, cada uma com lista de neurônios
              - "connections": lista de dicts {from_id, to_id, weight, color, penwidth}
        """
        # Normaliza pesos para escala visual
        all_weights = [abs(c.weight) for c in self._connections]
        max_w = max(all_weights) if all_weights else 1.0
        max_w = max(max_w, 1e-8)

        connections_out = []
        for conn in self._connections:
            normalized = abs(conn.weight) / max_w
            penwidth = 0.5 + 4.0 * normalized
            color = "blue" if conn.weight >= 0 else "red"
            connections_out.append({
                "from_id": conn.from_id,
                "to_id": conn.to_id,
                "weight": conn.weight,
                "color": color,
                "penwidth": round(penwidth, 2),
            })

        layers_out = []
        for layer in self.layers:
            neurons_out = []
            for n in layer.neurons:
                neurons_out.append({
                    "id": n.neuron_id,
                    "bias": round(n.bias, 4),
                    "activation": round(n.activation, 4),
                })
            layers_out.append({
                "activation_type": layer.activation_type,
                "neurons": neurons_out,
            })

        return {"layers": layers_out, "connections": connections_out}

    # ------------------------------------------------------------------
    # Treinamento completo
    # ------------------------------------------------------------------

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        learning_rate: float = 0.01,
        epochs: int = 60,
        seed: int = 42,
        callback=None,
    ) -> Dict:
        """
        Treina a rede por `epochs` épocas com SGD puro.

        O conjunto de treino é embaralhado a cada época com `seed` reproduzível.
        O teste NÃO entra neste método — acurácia de teste deve ser calculada
        externamente depois do fit.

        Args:
            X_train      : features de treino, shape (n, 13)
            y_train      : rótulos de treino, shape (n,)
            learning_rate: taxa de aprendizado
            epochs       : número de épocas
            seed         : semente de embaralhamento
            callback     : função opcional callback(epoch, loss, acc) para Streamlit

        Returns:
            dict com listas "loss_history" e "acc_history"
        """
        rng = np.random.default_rng(seed)
        n = len(X_train)
        loss_history = []
        acc_history = []

        for epoch in range(epochs):
            order = rng.permutation(n)
            epoch_loss = 0.0

            for i in order:
                loss = self.train_step(X_train[i], float(y_train[i]), learning_rate)
                epoch_loss += loss

            avg_loss = epoch_loss / n

            # Acurácia no treino (avaliação rápida)
            preds = np.array([self.predict(X_train[j]) for j in range(n)])
            acc = float(np.mean(preds == y_train))

            # Verifica NaN/Inf
            if not math.isfinite(avg_loss):
                raise RuntimeError(f"Loss NaN/Inf na época {epoch + 1}. Verifique a taxa de aprendizado.")

            loss_history.append(avg_loss)
            acc_history.append(acc)

            if callback is not None:
                callback(epoch + 1, avg_loss, acc)

        return {"loss_history": loss_history, "acc_history": acc_history}

    # ------------------------------------------------------------------
    # Propriedades utilitárias
    # ------------------------------------------------------------------

    @property
    def n_connections(self) -> int:
        """Número total de pesos na rede."""
        return len(self._connections)

    def __repr__(self) -> str:
        arch = " | ".join(str(s) for s in self.layer_sizes)
        return (
            f"MLPGraph(arch=[{arch}], "
            f"hidden={self.hidden_activation}, "
            f"connections={self.n_connections})"
        )
