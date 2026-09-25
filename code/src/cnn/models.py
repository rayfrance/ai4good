"""
Definição das Arquiteturas Neurais:
- BaselineCNN: Rede convolucional profunda padrão com BatchNorm e Dropout.
- SE_CNN: Rede convolucional com mecanismos de atenção Squeeze-and-Excitation (SEBlock).

Referência:
Ganguly, Ruby, & Chandran (2023). "Evaluating CNN Architectures Using Attention Mechanisms:
Convolutional Block Attention Module, Squeeze, and Excitation for Image Classification on CIFAR10 Dataset".
"""

import torch
import torch.nn as nn


class SEBlock(nn.Module):
    """
    Bloco Squeeze-and-Excitation (SE) para atenção de canais.
    
    1. Squeeze: Global Average Pooling agrega informações espaciais globais [B, C, H, W] -> [B, C, 1, 1].
    2. Excitation: Gargalo de duas camadas lineares com ativação ReLU e Sigmoid para modelar
       a interdependência não-linear e não-mutuamente exclusiva entre os canais.
    3. Scale: Recalibra os canais de entrada multiplicando pelo peso de atenção [0, 1].
    """
    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        bottleneck_dim = max(channels // reduction, 4)
        self.squeeze = nn.AdaptiveAvgPool2d(1)
        self.excitation = nn.Sequential(
            nn.Linear(channels, bottleneck_dim, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(bottleneck_dim, channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.shape
        # Squeeze: [B, C, 1, 1] -> [B, C]
        s = self.squeeze(x).view(b, c)
        # Excitation: [B, C] -> [B, C, 1, 1]
        e = self.excitation(s).view(b, c, 1, 1)
        # Scale: recalibra os canais da feature map
        return x * e


class BaselineCNN(nn.Module):
    """
    Arquitetura CNN Convolucional Padrão (Sem atenção).
    Consiste em 3 estágios convolucionais com Batch Normalization, ReLU, MaxPool e Dropout,
    seguidos de um classificador fully connected.
    """
    def __init__(self, in_channels: int = 3, num_classes: int = 10):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes
        
        # Estágio 1: [B, in_channels, H, W] -> [B, 32, H/2, W/2]
        self.stage1 = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout2d(0.2)
        )
        
        # Estágio 2: [B, 32, H/2, W/2] -> [B, 64, H/4, W/4]
        self.stage2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout2d(0.3)
        )
        
        # Estágio 3: [B, 64, H/4, W/4] -> [B, 128, H/8, W/8]
        self.stage3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout2d(0.3)
        )
        
        # Pooling adaptativo para garantir tamanho fixo independente do dataset (32x32 ou 28x28)
        self.adaptive_pool = nn.AdaptiveAvgPool2d((4, 4))
        
        # Classificador Linear
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.stage1(x)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.adaptive_pool(out)
        logits = self.classifier(out)
        return logits


class SE_CNN(nn.Module):
    """
    Arquitetura CNN com Mecanismo de Atenção Squeeze-and-Excitation (SEBlock).
    Adiciona blocos SE após os blocos convolucionais para permitir que a rede
    recalibre adaptativamente as importâncias dos canais de características.
    """
    def __init__(self, in_channels: int = 3, num_classes: int = 10, reduction: int = 16):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes
        self.reduction = reduction
        
        # Estágio 1 com SE
        self.conv1_1 = nn.Conv2d(in_channels, 32, kernel_size=3, padding=1, bias=False)
        self.bn1_1 = nn.BatchNorm2d(32)
        self.conv1_2 = nn.Conv2d(32, 32, kernel_size=3, padding=1, bias=False)
        self.bn1_2 = nn.BatchNorm2d(32)
        self.relu = nn.ReLU(inplace=True)
        self.se1 = SEBlock(32, reduction=reduction)
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.drop1 = nn.Dropout2d(0.2)
        
        # Estágio 2 com SE
        self.conv2_1 = nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False)
        self.bn2_1 = nn.BatchNorm2d(64)
        self.conv2_2 = nn.Conv2d(64, 64, kernel_size=3, padding=1, bias=False)
        self.bn2_2 = nn.BatchNorm2d(64)
        self.se2 = SEBlock(64, reduction=reduction)
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.drop2 = nn.Dropout2d(0.3)
        
        # Estágio 3 com SE
        self.conv3_1 = nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False)
        self.bn3_1 = nn.BatchNorm2d(128)
        self.se3 = SEBlock(128, reduction=reduction)
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.drop3 = nn.Dropout2d(0.3)
        
        # Pooling adaptativo
        self.adaptive_pool = nn.AdaptiveAvgPool2d((4, 4))
        
        # Classificador
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Estágio 1
        x = self.relu(self.bn1_1(self.conv1_1(x)))
        x = self.relu(self.bn1_2(self.conv1_2(x)))
        x = self.se1(x)  # Atenção SE
        x = self.pool1(x)
        x = self.drop1(x)
        
        # Estágio 2
        x = self.relu(self.bn2_1(self.conv2_1(x)))
        x = self.relu(self.bn2_2(self.conv2_2(x)))
        x = self.se2(x)  # Atenção SE
        x = self.pool2(x)
        x = self.drop2(x)
        
        # Estágio 3
        x = self.relu(self.bn3_1(self.conv3_1(x)))
        x = self.se3(x)  # Atenção SE
        x = self.pool3(x)
        x = self.drop3(x)
        
        # Saída
        x = self.adaptive_pool(x)
        logits = self.classifier(x)
        return logits


def count_parameters(model: nn.Module) -> int:
    """Retorna a contagem de parâmetros treináveis do modelo."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
