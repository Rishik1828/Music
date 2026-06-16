"""
train.py
--------
Trains the EmotionCNN from scratch on FER2013 using PyTorch.
Works natively on Windows with CUDA (Python 3.12 compatible).

Usage:
    python src/train.py

Output:
    models/emotion_model.pth   (best checkpoint — highest val accuracy)
    models/final_model.pth     (final epoch weights)
    models/training_history.png
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau

from preprocess import (
    get_pytorch_loaders,
    NUM_CLASSES,
    EMOTION_LABELS,
    PROJECT_ROOT,
)

# ── Paths ──────────────────────────────────────────────────────────────────────
MODELS_DIR       = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
BEST_MODEL_PATH  = str(MODELS_DIR / "emotion_model.pth")
FINAL_MODEL_PATH = str(MODELS_DIR / "final_model.pth")
PLOT_PATH        = str(MODELS_DIR / "training_history.png")


# ── Model Architecture ─────────────────────────────────────────────────────────
class EmotionCNN(nn.Module):
    """
    3-block CNN matching the spec exactly.

    Key fix: nn.Dropout (element-wise) — NOT nn.Dropout2d (drops entire channels).
    Keras Dropout(0.25) on a 4D tensor is element-wise, same as nn.Dropout.

    Input : (N, 1, 48, 48)
    Output: (N, 7)  raw logits
    """

    def __init__(self, num_classes: int = NUM_CLASSES):
        super().__init__()

        # ── Block 1: Conv64 × 2 → BN → ReLU → MaxPool → Dropout ──────────────
        self.block1 = nn.Sequential(
            nn.Conv2d(1,  64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),        # 48 → 24
            nn.Dropout(0.25),       # ← element-wise (was wrongly Dropout2d before)
        )

        # ── Block 2: Conv128 × 2 → BN → ReLU → MaxPool → Dropout ─────────────
        self.block2 = nn.Sequential(
            nn.Conv2d(64,  128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),        # 24 → 12
            nn.Dropout(0.25),
        )

        # ── Block 3: Conv256 → BN → ReLU → MaxPool → Dropout ─────────────────
        self.block3 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),        # 12 → 6
            nn.Dropout(0.25),
        )

        # ── Classifier head ───────────────────────────────────────────────────
        self.classifier = nn.Sequential(
            nn.Flatten(),                       # 256 × 6 × 6 = 9 216
            nn.Linear(256 * 6 * 6, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes),        # raw logits → CrossEntropyLoss
        )

        # He (Kaiming) initialisation for all Conv/Linear layers
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias,   0)
            elif isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        return self.classifier(x)


# ── Training helpers ───────────────────────────────────────────────────────────
def train_one_epoch(model, loader, criterion, optimizer, device, clip_grad=1.0):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for imgs, labels in loader:
        imgs, labels = imgs.to(device), labels.to(device)

        optimizer.zero_grad()
        logits = model(imgs)
        loss   = criterion(logits, labels)
        loss.backward()

        # Gradient clipping — prevents loss spikes from destabilising weights
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=clip_grad)

        optimizer.step()

        total_loss += loss.item() * imgs.size(0)
        correct    += (logits.argmax(1) == labels).sum().item()
        total      += imgs.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0

    for imgs, labels in loader:
        imgs, labels = imgs.to(device), labels.to(device)
        logits = model(imgs)
        loss   = criterion(logits, labels)

        total_loss += loss.item() * imgs.size(0)
        correct    += (logits.argmax(1) == labels).sum().item()
        total      += imgs.size(0)

    return total_loss / total, correct / total


def plot_history(train_accs, val_accs, train_losses, val_losses):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].plot(train_accs, label='Train Acc')
    axes[0].plot(val_accs,   label='Val Acc')
    axes[0].set_title('Accuracy over Epochs')
    axes[0].set_xlabel('Epoch'); axes[0].set_ylabel('Accuracy')
    axes[0].legend(); axes[0].grid(True)

    axes[1].plot(train_losses, label='Train Loss')
    axes[1].plot(val_losses,   label='Val Loss')
    axes[1].set_title('Loss over Epochs')
    axes[1].set_xlabel('Epoch'); axes[1].set_ylabel('Loss')
    axes[1].legend(); axes[1].grid(True)

    plt.tight_layout()
    plt.savefig(PLOT_PATH, dpi=150)
    print(f"[Train] Plot saved → {PLOT_PATH}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Emotion CNN Training  —  FER2013  (PyTorch)")
    print("=" * 60)
    print(f"[Train] PyTorch version : {torch.__version__}")

    # ── Device ────────────────────────────────────────────────────────────────
    if torch.cuda.is_available():
        device = torch.device("cuda")
        torch.backends.cudnn.benchmark = True   # optimise conv kernels for fixed input size
        print(f"[Train] GPU : {torch.cuda.get_device_name(0)} ✓")
    else:
        device = torch.device("cpu")
        print("[Train] No GPU — running on CPU.")

    # ── Data ──────────────────────────────────────────────────────────────────
    print("\n[Train] Loading data …")
    train_loader, val_loader, class_weights = get_pytorch_loaders()

    # Clip extreme class weights — disgust=9.4 causes gradient spikes
    MAX_WEIGHT = 4.0
    class_weights = torch.clamp(class_weights, max=MAX_WEIGHT)
    class_weights = class_weights.to(device)
    print(f"[Train] Class weights (capped at {MAX_WEIGHT}): {class_weights.tolist()}")

    # Quick data sanity check — print one batch shape
    sample_imgs, sample_labels = next(iter(train_loader))
    print(f"[Train] Sample batch — imgs: {sample_imgs.shape}, labels: {sample_labels.shape}")
    print(f"[Train] Pixel range  — min={sample_imgs.min():.3f}, max={sample_imgs.max():.3f}")
    print(f"[Train] Label dist   — {torch.bincount(sample_labels, minlength=NUM_CLASSES).tolist()}")

    # ── Model ─────────────────────────────────────────────────────────────────
    print("\n[Train] Building model …")
    model     = EmotionCNN(num_classes=NUM_CLASSES).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    # Lower LR (3e-4 instead of 1e-3) + weight decay for regularisation
    optimizer = optim.Adam(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5,
        patience=7, min_lr=1e-6, verbose=True,
    )

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[Train] Total parameters : {total_params:,}")
    print(f"[Train] Initial LR       : {optimizer.param_groups[0]['lr']}")

    # ── Training loop ─────────────────────────────────────────────────────────
    MAX_EPOCHS     = 100
    EARLY_STOP_PAT = 15
    best_val_acc   = 0.0
    no_improve     = 0

    train_accs, val_accs     = [], []
    train_losses, val_losses = [], []

    print(f"\n[Train] Starting — max {MAX_EPOCHS} epochs, "
          f"early stop patience={EARLY_STOP_PAT}\n")

    for epoch in range(1, MAX_EPOCHS + 1):
        t0 = time.time()

        tr_loss, tr_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device
        )
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step(vl_loss)

        elapsed = time.time() - t0
        current_lr = optimizer.param_groups[0]['lr']

        train_accs.append(tr_acc);    val_accs.append(vl_acc)
        train_losses.append(tr_loss); val_losses.append(vl_loss)

        print(f"Epoch {epoch:3d}/{MAX_EPOCHS}  "
              f"loss={tr_loss:.4f}  acc={tr_acc:.4f}  "
              f"val_loss={vl_loss:.4f}  val_acc={vl_acc:.4f}  "
              f"lr={current_lr:.2e}  ({elapsed:.0f}s)")

        # ModelCheckpoint
        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            torch.save({
                'epoch'      : epoch,
                'model_state': model.state_dict(),
                'val_acc'    : vl_acc,
                'class_map'  : EMOTION_LABELS,
            }, BEST_MODEL_PATH)
            print(f"  ✓ Best model saved  val_acc={vl_acc*100:.2f}%")
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= EARLY_STOP_PAT:
                print(f"\n[Train] Early stopping at epoch {epoch}.")
                break

    # Save final
    torch.save({
        'epoch'      : epoch,
        'model_state': model.state_dict(),
        'val_acc'    : vl_acc,
        'class_map'  : EMOTION_LABELS,
    }, FINAL_MODEL_PATH)

    print(f"\n{'='*60}")
    print(f"  Best val accuracy : {best_val_acc * 100:.2f}%")
    print(f"  Best model  → {BEST_MODEL_PATH}")
    print(f"  Final model → {FINAL_MODEL_PATH}")
    print(f"{'='*60}")

    plot_history(train_accs, val_accs, train_losses, val_losses)
    print("\n[Train] Done ✓")


if __name__ == "__main__":
    main()
