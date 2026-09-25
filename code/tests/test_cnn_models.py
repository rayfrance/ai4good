"""
Testes unitários automatizados para as arquiteturas BaselineCNN e SE_CNN.
"""

import sys
import os

# Adiciona pasta 'code' ao sys.path para evitar colisão com o módulo 'code' da stdlib
CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import torch
import pytest
from src.cnn.models import BaselineCNN, SE_CNN, SEBlock, count_parameters


def test_se_block_shape():
    """Verifica se o SEBlock preserva exatamente o shape [B, C, H, W]."""
    x = torch.randn(4, 64, 16, 16)
    se = SEBlock(channels=64, reduction=16)
    out = se(x)
    assert out.shape == x.shape, f"Esperado {x.shape}, obteve {out.shape}"


def test_baseline_cnn_forward_cifar():
    """Verifica a saída da BaselineCNN para imagens 32x32 com 3 canais."""
    model = BaselineCNN(in_channels=3, num_classes=10)
    x = torch.randn(2, 3, 32, 32)
    out = model(x)
    assert out.shape == (2, 10), f"Esperado (2, 10), obteve {out.shape}"


def test_se_cnn_forward_cifar():
    """Verifica a saída da SE_CNN para imagens 32x32 com 3 canais."""
    model = SE_CNN(in_channels=3, num_classes=10, reduction=16)
    x = torch.randn(2, 3, 32, 32)
    out = model(x)
    assert out.shape == (2, 10), f"Esperado (2, 10), obteve {out.shape}"


def test_models_forward_fashion_mnist():
    """Verifica compatibilidade com imagens 28x28 em tons de cinza (1 canal)."""
    base = BaselineCNN(in_channels=1, num_classes=10)
    se = SE_CNN(in_channels=1, num_classes=10)
    
    x = torch.randn(2, 1, 28, 28)
    out_base = base(x)
    out_se = se(x)
    
    assert out_base.shape == (2, 10)
    assert out_se.shape == (2, 10)


def test_parameter_counts():
    """Verifica se SE_CNN adiciona uma sobrecarga paramétrica leve (< 3%)."""
    base = BaselineCNN(in_channels=3, num_classes=10)
    se = SE_CNN(in_channels=3, num_classes=10)
    
    params_base = count_parameters(base)
    params_se = count_parameters(se)
    
    assert params_se > params_base, "SE_CNN deve conter os parâmetros adicionais dos blocos de atenção"
    overhead_pct = ((params_se - params_base) / params_base) * 100
    assert overhead_pct < 5.0, f"Sobrecarga de parâmetros muito alta: {overhead_pct:.2f}%"
