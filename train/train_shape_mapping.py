"""
train/train_shape_mapping.py

Train a CNN to map rough sketches → clean geometric shapes.
This solves the sketch normalization problem using supervised learning.

APPROACH:
- Generate synthetic (rough, clean) pairs
- Train CNN with encoder-decoder architecture
- Use MSE loss to learn pixel-wise shape reconstruction
- Supports all 4 shape types (circle, square, triangle, line)

USAGE:
    python train_shape_mapping.py

OUTPUT:
    ml/shape_mapping_model.pth (~5-10MB with full dataset)
"""
import os
import sys
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import random

# Set random seeds for reproducibility
np.random.seed(42)
torch.manual_seed(42)
random.seed(42)

IMG_SIZE = 28
NUM_SAMPLES_PER_CLASS = 2000  # 8K total
NUM_CLASSES = 4  # circle, square, triangle, line
CLASS_NAMES = ["circle", "square", "triangle", "line"]
AUGMENTATION_FACTOR = 4  # Each clean shape → 4 rough variants

# Model save path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(_PROJECT_ROOT, "ml", "shape_mapping_model.pth")


class ShapeMapper(nn.Module):
    """
    Encoder-Decoder CNN to map rough sketches to clean shapes.
    
    Architecture:
    - Encoder: 3 conv layers with pooling (extract features from rough sketch)
    - Bottleneck: 64 channels (compact representation)
    - Decoder: 3 deconv layers (reconstruct clean shape)
    """
    def __init__(self):
        super(ShapeMapper, self).__init__()
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # 28 → 14
            
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # 14 → 7
            
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
        )
        
        # Decoder (mirror of encoder)
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(64, 32, kernel_size=4, stride=2, padding=1),  # 7 → 14
            nn.ReLU(inplace=True),
            
            nn.ConvTranspose2d(32, 16, kernel_size=4, stride=2, padding=1),  # 14 → 28
            nn.ReLU(inplace=True),
            
            nn.Conv2d(16, 1, kernel_size=3, stride=1, padding=1),
            nn.Sigmoid()  # Output in [0, 1]
        )
    
    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


def generate_clean_shape(shape_type: int) -> np.ndarray:
    """Generate a perfect clean shape (target)."""
    img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    color = 255
    thickness = 2
    margin = 3
    center = IMG_SIZE // 2
    
    if shape_type == 0:  # Circle
        radius = random.randint(7, IMG_SIZE // 2 - margin)
        cv2.circle(img, (center, center), radius, color, thickness)
    elif shape_type == 1:  # Square
        side = random.randint(10, IMG_SIZE - 2 * margin)
        x1 = center - side // 2
        y1 = center - side // 2
        cv2.rectangle(img, (x1, y1), (x1 + side, y1 + side), color, thickness)
    elif shape_type == 2:  # Triangle
        half_side = random.randint(7, IMG_SIZE // 2 - margin)
        p1 = (center, center - half_side)
        p2 = (center - half_side, center + half_side)
        p3 = (center + half_side, center + half_side)
        pts = np.array([p1, p2, p3], np.int32).reshape((-1, 1, 2))
        cv2.polylines(img, [pts], isClosed=True, color=color, thickness=thickness)
    elif shape_type == 3:  # Line
        x1 = margin
        y1 = margin
        x2 = IMG_SIZE - margin
        y2 = IMG_SIZE - margin
        if random.random() > 0.5:
            y2 = y1
        cv2.line(img, (x1, y1), (x2, y2), color, thickness)
    
    return img


def corrupt_sketch(clean_img: np.ndarray) -> np.ndarray:
    """
    Corrupt a clean shape to simulate user's rough drawing.
    
    Corruption types:
    1. Gaussian noise (jitter)
    2. Random point dropout (gaps)
    3. Stroke wobble (±4px random offset)
    4. Line thickness variation
    """
    rough = clean_img.copy().astype(np.float32) / 255.0
    
    # 1. Random gaussian noise (±0.1)
    noise = np.random.normal(0, 0.08, rough.shape)
    rough = rough + noise
    
    # 2. Create gaps by dropout (8-15% of pixels)
    mask = np.random.random(rough.shape) > 0.10
    rough = rough * mask
    
    # 3. Stroke wobble - add small random offsets
    for _ in range(2):
        rough = np.roll(rough, np.random.randint(-2, 3), axis=0)
        rough = np.roll(rough, np.random.randint(-2, 3), axis=1)
    
    # 4. Clip to [0, 1]
    rough = np.clip(rough, 0, 1)
    
    return rough


class RoughCleanPairDataset(Dataset):
    """Dataset of (rough_sketch, clean_shape) pairs for training."""
    
    def __init__(self, rough_imgs, clean_imgs):
        self.rough = torch.FloatTensor(rough_imgs).unsqueeze(1)  # Add channel dim
        self.clean = torch.FloatTensor(clean_imgs).unsqueeze(1)
        
    def __len__(self):
        return len(self.rough)
    
    def __getitem__(self, idx):
        return self.rough[idx], self.clean[idx]


def create_training_data():
    """Generate (rough, clean) pairs for all shape types."""
    print("[Dataset] Generating training pairs...")
    
    all_rough = []
    all_clean = []
    
    for class_id in range(NUM_CLASSES):
        class_name = CLASS_NAMES[class_id]
        print(f"  Generating {class_name}...", end="", flush=True)
        
        for sample_idx in range(NUM_SAMPLES_PER_CLASS):
            # Generate clean shape
            clean = generate_clean_shape(class_id).astype(np.float32) / 255.0
            
            # Create multiple corrupted versions (augmentation)
            for aug in range(AUGMENTATION_FACTOR):
                rough = corrupt_sketch(clean)
                all_rough.append(rough)
                all_clean.append(clean)
        
        print(f" [{NUM_SAMPLES_PER_CLASS * AUGMENTATION_FACTOR} pairs]")
    
    all_rough = np.array(all_rough)
    all_clean = np.array(all_clean)
    
    print(f"[Dataset] Total pairs: {len(all_rough)}")
    print(f"           Rough shape: {all_rough.shape}, Clean shape: {all_clean.shape}")
    
    return all_rough, all_clean


def train_shape_mapper():
    """Train the shape mapping CNN."""
    
    # 1. Create dataset
    rough, clean = create_training_data()
    
    # 2. Split into train/val/test
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        rough, clean, test_size=0.2, random_state=42
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.15, random_state=42
    )
    
    print(f"\n[Split] Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    
    # 3. Create datasets and dataloaders
    train_dataset = RoughCleanPairDataset(X_train, y_train)
    val_dataset = RoughCleanPairDataset(X_val, y_val)
    test_dataset = RoughCleanPairDataset(X_test, y_test)
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)
    test_loader = DataLoader(test_dataset, batch_size=32)
    
    # 4. Initialize model, optimizer, loss
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n[Device] Using: {device}")
    
    model = ShapeMapper().to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=3, verbose=True
    )
    
    # 5. Training loop
    num_epochs = 20
    best_val_loss = float('inf')
    
    print(f"\n[Training] Starting {num_epochs} epochs...")
    
    for epoch in range(num_epochs):
        # Train
        model.train()
        train_loss = 0.0
        for rough_batch, clean_batch in train_loader:
            rough_batch = rough_batch.to(device)
            clean_batch = clean_batch.to(device)
            
            optimizer.zero_grad()
            output = model(rough_batch)
            loss = criterion(output, clean_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # Validate
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for rough_batch, clean_batch in val_loader:
                rough_batch = rough_batch.to(device)
                clean_batch = clean_batch.to(device)
                output = model(rough_batch)
                loss = criterion(output, clean_batch)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        
        # Learning rate scheduling
        scheduler.step(val_loss)
        
        print(f"Epoch {epoch+1:2d}/{num_epochs} | "
              f"Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f}")
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"           ✓ Model saved (val_loss: {val_loss:.6f})")
    
    # 6. Test on held-out data
    print(f"\n[Evaluation] Testing on held-out data...")
    model.eval()
    test_loss = 0.0
    with torch.no_grad():
        for rough_batch, clean_batch in test_loader:
            rough_batch = rough_batch.to(device)
            clean_batch = clean_batch.to(device)
            output = model(rough_batch)
            loss = criterion(output, clean_batch)
            test_loss += loss.item()
    
    test_loss /= len(test_loader)
    print(f"Test MSE Loss: {test_loss:.6f}")
    print(f"\n[Success] Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    train_shape_mapper()
