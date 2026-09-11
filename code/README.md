# MLP — Heart Disease Classifier

Experimento da disciplina **Tópicos Avançados em Inteligência Artificial** (UFRPE).

Implementa uma **Multi-Layer Perceptron do zero**, representada internamente como grafo
de nós e arestas. Sem uso de TensorFlow, PyTorch ou MLP pronta do scikit-learn.

---

## 📐 Arquitetura

```
Input (13)  →  Oculta 1 (8) [ReLU]  →  Oculta 2 (5) [ReLU]  →  Saída (1) [Sigmoid]
```

| Camada | Neurônios | Ativação | Entradas |
|---|---|---|---|
| Entrada | 13 | — | 13 features do Heart Disease |
| Oculta 1 | 8 | ReLU | 13 |
| Oculta 2 | 5 | ReLU | 8 |
| Saída | 1 | Sigmoid | 5 |

**Total de pesos:** 13×8 + 8×5 + 5×1 = **149 conexões**

---

## 🗂️ Organização dos arquivos

```
code/
├── data/
│   ├── heart.csv          # Dataset (não versionado — ver README interno)
│   └── README.md          # Descrição das colunas e instruções de download
├── src/
│   └── mlp/
│       ├── __init__.py
│       ├── graph.py        # Neuron, Connection, Layer, MLPGraph
│       ├── activations.py  # relu, sigmoid e derivadas
│       ├── losses.py       # binary_cross_entropy
│       └── data.py         # load_heart, split_stratified, standardize
├── scripts/
│   └── mlp_streamlit.py   # Aplicação Streamlit
├── tests/
│   ├── test_graph.py       # Conexões, sigmoid, limiar, leakage, reprodutibilidade
│   └── test_gradient.py    # Gradient checking numérico
└── requirements.txt
```

---

## ⚙️ Instalação

```bash
# A partir da raiz do repositório
pip install -r code/requirements.txt
```

**Dependências:**
- `numpy` — álgebra matricial
- `streamlit` — interface interativa
- `graphviz` (Python) — renderização DOT no Streamlit
- `pytest` — testes automatizados

---

## 🚀 Execução

```bash
# Interface Streamlit
streamlit run code/scripts/mlp_streamlit.py

# Testes
python -m pytest code/tests/ -v

# Verificação do workspace
python tools/workspace_check.py
```

---

## 📊 Divisão dos dados

O dataset Kaggle `johnsmith88/heart-disease-dataset` contém 1.025 registros,
porém apenas **302 são únicos** (723 duplicatas com labels consistentes).
A deduplicação é aplicada **antes** do split para evitar acurácia inflada.

| Conjunto | Registros | Proporção | Método |
|---|---|---|---|
| Treino | ~243 | 80% | Estratificado por `target`, semente 42 |
| Teste | ~59 | 20% | Estratificado por `target`, semente 42 |

- **Padronização:** µ e σ calculados exclusivamente no treino. O teste nunca influencia a normalização.
- **Embaralhamento:** apenas o conjunto de treino é reembaralhado a cada época.
- **Acurácia final:** medida uma única vez no conjunto de teste, após todo o treinamento.

---

## 📏 Métricas

| Métrica | Definição |
|---|---|
| **Loss (BCE)** | Binary Cross-Entropy: −[y·log(ŷ) + (1−y)·log(1−ŷ)] |
| **Acurácia** | Proporção de previsões corretas: Σ(ŷ == y) / n |
| **Probabilidade** | Saída da sigmoid: ∈ [0, 1] |
| **Classe prevista** | 1 se prob ≥ 0.5, senão 0 |

---

## 🔬 Como o backpropagation funciona

1. **Forward pass:** ativações propagam da entrada à saída camada por camada
2. **Gradiente da saída:** δ = ŷ − y (simplificação BCE + sigmoid)
3. **Gradiente das ocultas:** δ = (Σ w·δ_próxima) · relu'(z)
4. **Atualização:** w ← w − η·δ·a (peso menos learning_rate × gradiente × ativação anterior)

---

## 🧪 Validação

- **Structural tests:** 149 conexões, saída ∈ [0,1], limiar, sem leakage, reprodutibilidade
- **Gradient checking:** diferenças centrais com ε=1e-5 numa rede 2→3→1, tolerância 1e-4

---

## 👩‍💻 Autora

Rayane France — Licenciatura em Computação, UFRPE  
Disciplina: Tópicos Avançados em Inteligência Artificial
