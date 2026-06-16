"""
preprocess.py
-------------
Data loaders (PyTorch) for FER2013 + single-face preprocessing for inference.

Training  : get_pytorch_loaders() → returns (train_loader, val_loader, class_weights)
Inference : preprocess_face(face_bgr) → torch.Tensor (1,1,48,48)
"""

import numpy as np
from pathlib import Path
from sklearn.utils.class_weight import compute_class_weight

import torch
from torchvision import datasets, transforms

# ── Constants ──────────────────────────────────────────────────────────────────
IMG_SIZE    = 48
BATCH_SIZE  = 64
NUM_CLASSES = 7

EMOTION_LABELS = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAIN_DIR    = PROJECT_ROOT / "Dataset" / "train"
TEST_DIR     = PROJECT_ROOT / "Dataset" / "test"


# ── Augmentation transforms ────────────────────────────────────────────────────
TRAIN_TRANSFORM = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.RandomAffine(degrees=0, translate=(0.1, 0.1), scale=(0.9, 1.1)),
    transforms.ColorJitter(brightness=0.2),
    transforms.ToTensor(),               # → [0, 1] float32, shape (1, 48, 48)
])

VAL_TRANSFORM = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
])


# ── Data loaders ───────────────────────────────────────────────────────────────
def get_pytorch_loaders(batch_size: int = BATCH_SIZE):
    """
    Returns (train_loader, val_loader, class_weight_tensor).
    class_weight_tensor is a float32 GPU/CPU tensor of shape (NUM_CLASSES,).
    """
    train_ds = datasets.ImageFolder(str(TRAIN_DIR), transform=TRAIN_TRANSFORM)
    val_ds   = datasets.ImageFolder(str(TEST_DIR),  transform=VAL_TRANSFORM)

    train_loader = torch.utils.data.DataLoader(
        train_ds,
        batch_size  = batch_size,
        shuffle     = True,
        num_workers = 0,          # 0 = main process (safe on Windows)
        pin_memory  = torch.cuda.is_available(),
    )
    val_loader = torch.utils.data.DataLoader(
        val_ds,
        batch_size  = batch_size,
        shuffle     = False,
        num_workers = 0,
        pin_memory  = torch.cuda.is_available(),
    )

    # ── Class weights ──────────────────────────────────────────────────────────
    labels         = np.array(train_ds.targets)
    unique_classes = np.unique(labels)
    weights        = compute_class_weight('balanced', classes=unique_classes, y=labels)
    weight_tensor  = torch.tensor(weights, dtype=torch.float32)

    # Display
    inv_map = {v: k for k, v in train_ds.class_to_idx.items()}
    print("[Preprocess] Class weights:")
    for idx, w in enumerate(weights):
        print(f"  {inv_map.get(idx, idx):10s}: {w:.4f}")
    print(f"[Preprocess] Class index map: {train_ds.class_to_idx}")

    return train_loader, val_loader, weight_tensor


# ── Single-image preprocessing for inference ───────────────────────────────────
def preprocess_face(face_bgr: np.ndarray) -> torch.Tensor:
    """
    Converts a BGR face crop (OpenCV) → PyTorch tensor (1, 1, 48, 48) float32.

    Parameters
    ----------
    face_bgr : np.ndarray   Shape (H, W, 3)

    Returns
    -------
    torch.Tensor   Shape (1, 1, 48, 48), values in [0, 1]
    """
    import cv2
    gray       = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    resized    = cv2.resize(gray, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
    normalized = resized.astype(np.float32) / 255.0
    tensor     = torch.tensor(normalized).unsqueeze(0).unsqueeze(0)  # (1,1,48,48)
    return tensor


# ── Quick self-test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import torch
    print(f"[Preprocess] PyTorch version : {torch.__version__}")
    print(f"[Preprocess] CUDA available  : {torch.cuda.is_available()}")
    print(f"[Preprocess] TRAIN_DIR       : {TRAIN_DIR}")

    if not TRAIN_DIR.exists():
        print("[Preprocess] ERROR: TRAIN_DIR not found.")
    else:
        train_l, val_l, cw = get_pytorch_loaders()
        print(f"[Preprocess] Train batches : {len(train_l)}")
        print(f"[Preprocess] Val batches   : {len(val_l)}")
        print(f"[Preprocess] Class weights : {cw}")
