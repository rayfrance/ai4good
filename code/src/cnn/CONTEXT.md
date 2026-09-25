# code/src/cnn/ — Experimento de Arquitetura CNN

> Leia este arquivo antes de criar ou modificar qualquer coisa nesta pasta.

## O que é este módulo

Implementação em PyTorch de duas arquiteturas de redes neurais convolucionais para
classificação de imagens, com o objetivo de avaliar o impacto da introdução de
mecanismos de atenção de canais (Squeeze-and-Excitation) na capacidade discriminativa
da rede.

## Artigo base

**Título:** "Evaluating CNN Architectures Using Attention Mechanisms: Convolutional
Block Attention Module, Squeeze, and Excitation for Image Classification on CIFAR10
Dataset"
**Autores:** Abhisek Ganguly, A. Usha Ruby, George Chellin Chandran J.
**Data:** Agosto de 2023
**DOI:** 10.13140/RG.2.2.33649.66408
**Anotação de leitura:** `papers/notes/ganguly2023-attention-cnn-cifar10.md`

## Arquiteturas implementadas

| Modelo | Descrição | Arquivo |
|---|---|---|
| `BaselineCNN` | CNN de 3 estágios convolucionais com BatchNorm, ReLU, MaxPool e Dropout | `models.py` |
| `SE_CNN` | Mesma CNN com blocos Squeeze-and-Excitation (SEBlock) após cada estágio | `models.py` |
| `SEBlock` | Módulo de atenção de canais: GAP → Linear(C/r) → ReLU → Linear(C) → Sigmoid | `models.py` |

## Datasets suportados

| Dataset | Resolução | Canais | Classes | Loader |
|---|---|---|---|---|
| CIFAR-10 | 32×32 | 3 (RGB) | 10 | `data_loader.get_cifar10_loaders()` |
| Fashion-MNIST | 28×28 | 1 (Grayscale) | 10 | `data_loader.get_fashion_mnist_loaders()` |

## Organização dos arquivos

```
code/src/cnn/
├── CONTEXT.md       ← este arquivo
├── __init__.py      ← exports dos modelos e utilitários
├── models.py        ← BaselineCNN, SE_CNN, SEBlock, count_parameters
├── data_loader.py   ← carregamento e normalização dos datasets
└── trainer.py       ← laço de treino, avaliação e salvamento de checkpoints
```

## Scripts relacionados

- `code/scripts/train_experiments.py` — treina as 4 combinações (2 modelos × 2 datasets)
- `code/scripts/evaluate_and_plot.py` — gera gráficos de convergência e matrizes de confusão
- `code/scripts/cnn_streamlit.py` — app interativo para inferência ao vivo
- `code/tests/test_cnn_models.py` — testes unitários das arquiteturas

## Resultados

Os checkpoints (.pt) e métricas (metrics.json) são salvos em `outputs/`.
Os gráficos de convergência e matrizes de confusão ficam em `outputs/plots/`.
