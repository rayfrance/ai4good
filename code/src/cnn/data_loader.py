"""
Módulo de carregamento e pré-processamento dos datasets:
- CIFAR-10 (Dataset principal - 3 canais RGB, 32x32)
- Fashion-MNIST (Dataset do desafio - 1 canal Grayscale, 28x28)
"""

import os
import torch
from torch.utils.data import DataLoader, Subset
import torchvision
import torchvision.transforms as transforms

CIFAR10_CLASSES = [
    "airplane", "automobile", "bird", "cat", "deer",
    "dog", "frog", "horse", "ship", "truck"
]

FASHION_CLASSES = [
    "T-shirt/top", "Trouser", "Pullover", "Dress", "Coat",
    "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"
]


def get_cifar10_loaders(
    data_dir: str = "code/data/cifar10",
    batch_size: int = 128,
    num_workers: int = 0,
    max_train_samples: int = None,
    max_test_samples: int = None,
    seed: int = 42
):
    """
    Carrega CIFAR-10 com transformações de data augmentation leve no treino
    e normalização padrão do benchmark.
    """
    os.makedirs(data_dir, exist_ok=True)
    
    # Normalização CIFAR-10 padrão
    norm_mean = (0.4914, 0.4822, 0.4465)
    norm_std = (0.2470, 0.2435, 0.2616)
    
    train_transform = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(norm_mean, norm_std)
    ])
    
    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(norm_mean, norm_std)
    ])
    
    train_dataset = torchvision.datasets.CIFAR10(
        root=data_dir, train=True, download=True, transform=train_transform
    )
    test_dataset = torchvision.datasets.CIFAR10(
        root=data_dir, train=False, download=True, transform=test_transform
    )
    
    if max_train_samples is not None and max_train_samples < len(train_dataset):
        g = torch.Generator().manual_seed(seed)
        indices = torch.randperm(len(train_dataset), generator=g)[:max_train_samples]
        train_dataset = Subset(train_dataset, indices)
        
    if max_test_samples is not None and max_test_samples < len(test_dataset):
        g = torch.Generator().manual_seed(seed)
        indices = torch.randperm(len(test_dataset), generator=g)[:max_test_samples]
        test_dataset = Subset(test_dataset, indices)
        
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    
    return train_loader, test_loader, CIFAR10_CLASSES


def get_fashion_mnist_loaders(
    data_dir: str = "code/data/fashion_mnist",
    batch_size: int = 128,
    num_workers: int = 0,
    max_train_samples: int = None,
    max_test_samples: int = None,
    seed: int = 42
):
    """
    Carrega Fashion-MNIST (1 canal, 28x28) para o desafio de 2º dataset.
    """
    os.makedirs(data_dir, exist_ok=True)
    
    norm_mean = (0.2860,)
    norm_std = (0.3530,)
    
    train_transform = transforms.Compose([
        transforms.RandomCrop(28, padding=2),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(norm_mean, norm_std)
    ])
    
    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(norm_mean, norm_std)
    ])
    
    train_dataset = torchvision.datasets.FashionMNIST(
        root=data_dir, train=True, download=True, transform=train_transform
    )
    test_dataset = torchvision.datasets.FashionMNIST(
        root=data_dir, train=False, download=True, transform=test_transform
    )
    
    if max_train_samples is not None and max_train_samples < len(train_dataset):
        g = torch.Generator().manual_seed(seed)
        indices = torch.randperm(len(train_dataset), generator=g)[:max_train_samples]
        train_dataset = Subset(train_dataset, indices)
        
    if max_test_samples is not None and max_test_samples < len(test_dataset):
        g = torch.Generator().manual_seed(seed)
        indices = torch.randperm(len(test_dataset), generator=g)[:max_test_samples]
        test_dataset = Subset(test_dataset, indices)
        
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    
    return train_loader, test_loader, FASHION_CLASSES
