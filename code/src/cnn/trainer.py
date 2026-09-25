"""
Módulo de treinamento e avaliação com rastreamento de métricas:
- Perda (CrossEntropyLoss)
- Acurácia de treino e teste por época
- Matriz de confusão e métricas detalhadas (Precision, Recall, F1)
"""

import time
import os
from typing import Dict, Any, Tuple
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np


def set_seed(seed: int = 42):
    """Garante reprodutibilidade total do experimento."""
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


def train_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device
) -> Tuple[float, float]:
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    for inputs, targets in dataloader:
        inputs, targets = inputs.to(device), targets.to(device)
        
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()
        
        running_loss += loss.item() * inputs.size(0)
        _, preds = torch.max(outputs, 1)
        correct += (preds == targets).sum().item()
        total += targets.size(0)
        
    epoch_loss = running_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc


@torch.no_grad()
def evaluate(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device
) -> Dict[str, Any]:
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_targets = []
    
    for inputs, targets in dataloader:
        inputs, targets = inputs.to(device), targets.to(device)
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        
        running_loss += loss.item() * inputs.size(0)
        _, preds = torch.max(outputs, 1)
        correct += (preds == targets).sum().item()
        total += targets.size(0)
        
        all_preds.extend(preds.cpu().numpy())
        all_targets.extend(targets.cpu().numpy())
        
    eval_loss = running_loss / total
    eval_acc = correct / total
    
    cm = confusion_matrix(all_targets, all_preds)
    report = classification_report(all_targets, all_preds, output_dict=True, zero_division=0)
    
    return {
        "loss": float(eval_loss),
        "accuracy": float(eval_acc),
        "confusion_matrix": cm.tolist(),
        "report": report,
        "predictions": all_preds,
        "targets": all_targets
    }


def train_model(
    model: nn.Module,
    train_loader: torch.utils.data.DataLoader,
    test_loader: torch.utils.data.DataLoader,
    num_epochs: int = 10,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    device: torch.device = None,
    checkpoint_path: str = None
) -> Dict[str, Any]:
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    
    history = {
        "train_loss": [],
        "train_acc": [],
        "val_loss": [],
        "val_acc": [],
        "epoch_times": []
    }
    
    print(f"Iniciando treinamento ({num_epochs} épocas) em {device}...")
    start_total = time.time()
    
    for epoch in range(1, num_epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        val_eval = evaluate(model, test_loader, criterion, device)
        scheduler.step()
        elapsed = time.time() - t0
        
        history["train_loss"].append(round(train_loss, 4))
        history["train_acc"].append(round(train_acc, 4))
        history["val_loss"].append(round(val_eval["loss"], 4))
        history["val_acc"].append(round(val_eval["accuracy"], 4))
        history["epoch_times"].append(round(elapsed, 2))
        
        print(f"Época [{epoch:02d}/{num_epochs:02d}] "
              f"Treino Loss: {train_loss:.4f} | Treino Acc: {train_acc*100:.2f}% | "
              f"Val Loss: {val_eval['loss']:.4f} | Val Acc: {val_eval['accuracy']*100:.2f}% "
              f"({elapsed:.1f}s)")
              
    total_time = time.time() - start_total
    
    # Avaliação final detalhada
    final_eval = evaluate(model, test_loader, criterion, device)
    
    result = {
        "history": history,
        "final_loss": final_eval["loss"],
        "final_accuracy": final_eval["accuracy"],
        "confusion_matrix": final_eval["confusion_matrix"],
        "report": final_eval["report"],
        "total_time_seconds": round(total_time, 2)
    }
    
    if checkpoint_path:
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        torch.save({
            "model_state_dict": model.state_dict(),
            "final_accuracy": final_eval["accuracy"],
            "history": history
        }, checkpoint_path)
        print(f"Checkpoint salvo com sucesso em: {checkpoint_path}")
        
    return result
