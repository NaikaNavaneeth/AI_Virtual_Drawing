"""
ml/train_drawing_mlp_extended.py - Train MLP for 30 shape types (A-Z + 0-9).
Extended from original 4-shape trainer to support letters and numbers.

Training 30 shape classes:
- Geometric: circle, square, triangle, line, pentagon, hexagon (6)
- Letters: A-Z (26 uppercase + 26 lowercase = 52, but we'll use uppercase) (26)
- Numbers: 0-9 (10)
Total: 30 unique labels

Training data: ~30,000 synthetic samples (1000 per class)
"""

import numpy as np
import cv2
import os
import joblib
from sklearn.neural_network import MLPClassifier
from pathlib import Path
import random

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

SHAPE_TYPES_30 = [
    # Geometric shapes (6)
    'circle', 'square', 'triangle', 'line', 'pentagon', 'hexagon',
    
    # Letters A-Z (26)
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 
    'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
    'U', 'V', 'W', 'X', 'Y', 'Z'
]

IMG_SIZE = 28
SAMPLES_PER_CLASS = 1000  # 1000 samples per shape
TOTAL_SAMPLES = len(SHAPE_TYPES_30) * SAMPLES_PER_CLASS

OUTPUT_MODEL = os.path.join(os.path.dirname(__file__), "drawing_mlp_30.pkl")

print(f"[Training] Extended MLP for {len(SHAPE_TYPES_30)} shapes")
print(f"[Training] Total samples: {TOTAL_SAMPLES}")
print(f"[Training] Model output: {OUTPUT_MODEL}")

# ──────────────────────────────────────────────────────────────────────────────
# Synthetic Data Generation
# ──────────────────────────────────────────────────────────────────────────────

def _generate_circle(img, cx, cy, radius, thickness):
    """Draw circle on image"""
    cv2.circle(img, (cx, cy), radius, 255, thickness, cv2.LINE_AA)

def _generate_square(img, cx, cy, size, thickness):
    """Draw square on image"""
    half = size // 2
    pts = np.array([
        [cx - half, cy - half],
        [cx + half, cy - half],
        [cx + half, cy + half],
        [cx - half, cy + half]
    ], dtype=np.int32)
    cv2.polylines(img, [pts], True, 255, thickness, cv2.LINE_AA)

def _generate_triangle(img, cx, cy, size, thickness):
    """Draw triangle on image"""
    h = int(size * 0.866)
    pts = np.array([
        [cx, cy - h // 2],
        [cx - size // 2, cy + h // 2],
        [cx + size // 2, cy + h // 2]
    ], dtype=np.int32)
    cv2.polylines(img, [pts], True, 255, thickness, cv2.LINE_AA)

def _generate_line(img, cx, cy, length, thickness):
    """Draw line on image"""
    cv2.line(img, (cx - length // 2, cy), (cx + length // 2, cy), 255, thickness, cv2.LINE_AA)

def _generate_pentagon(img, cx, cy, radius, thickness):
    """Draw pentagon on image"""
    pts = []
    for i in range(5):
        angle = 2 * np.pi * i / 5 - np.pi / 2
        x = int(cx + radius * np.cos(angle))
        y = int(cy + radius * np.sin(angle))
        pts.append([x, y])
    pts = np.array(pts, dtype=np.int32)
    cv2.polylines(img, [pts], True, 255, thickness, cv2.LINE_AA)

def _generate_hexagon(img, cx, cy, radius, thickness):
    """Draw hexagon on image"""
    pts = []
    for i in range(6):
        angle = 2 * np.pi * i / 6
        x = int(cx + radius * np.cos(angle))
        y = int(cy + radius * np.sin(angle))
        pts.append([x, y])
    pts = np.array(pts, dtype=np.int32)
    cv2.polylines(img, [pts], True, 255, thickness, cv2.LINE_AA)

def _generate_letter(img, letter, cx, cy, size, thickness):
    """Draw letter on image using OpenCV text"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = size / 20.0
    text_size = cv2.getTextSize(letter, font, font_scale, thickness)[0]
    x = cx - text_size[0] // 2
    y = cy + text_size[1] // 2
    cv2.putText(img, letter, (x, y), font, font_scale, 255, thickness, cv2.LINE_AA)

def _generate_number(img, num_str, cx, cy, size, thickness):
    """Draw number on image using OpenCV text"""
    _generate_letter(img, num_str, cx, cy, size, thickness)

def _add_noise(img, noise_type='gaussian'):
    """Add noise to image for robustness"""
    if noise_type == 'gaussian':
        noise = np.random.normal(0, 5, img.shape)
        img = np.clip(img + noise, 0, 255)
    elif noise_type == 'salt_pepper':
        s_p_ratio = 0.5
        num_salt = np.random.poisson(img.size * 0.01)
        coords = [np.random.randint(0, i, num_salt) for i in img.shape]
        img[tuple(coords)] = 255
        num_pepper = np.random.poisson(img.size * 0.01)
        coords = [np.random.randint(0, i, num_pepper) for i in img.shape]
        img[tuple(coords)] = 0
    
    return img.astype(np.uint8)

def _generate_synthetic_shape(shape_type):
    """Generate a single synthetic training sample"""
    img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    base_size = IMG_SIZE // 3
    
    # Random variations
    thickness = random.randint(1, 3)
    scale_factor = random.uniform(0.7, 1.3)
    noise_type = random.choice(['gaussian', 'salt_pepper', None])
    
    size = int(base_size * scale_factor)
    
    # Generate based on shape type
    if shape_type == 'circle':
        _generate_circle(img, cx, cy, size // 2, thickness)
    elif shape_type == 'square':
        _generate_square(img, cx, cy, size, thickness)
    elif shape_type == 'triangle':
        _generate_triangle(img, cx, cy, size, thickness)
    elif shape_type == 'line':
        _generate_line(img, cx, cy, size, thickness)
    elif shape_type == 'pentagon':
        _generate_pentagon(img, cx, cy, size // 2, thickness)
    elif shape_type == 'hexagon':
        _generate_hexagon(img, cx, cy, size // 2, thickness)
    elif len(shape_type) == 1 and shape_type.isalpha():
        # Letter
        _generate_letter(img, shape_type, cx, cy, size, thickness)
    elif len(shape_type) == 1 and shape_type.isdigit():
        # Number
        _generate_number(img, shape_type, cx, cy, size, thickness)
    
    # Add noise
    if noise_type:
        img = _add_noise(img, noise_type)
    
    # Normalize to 0-1
    img = img.astype(np.float32) / 255.0
    
    return img

# ──────────────────────────────────────────────────────────────────────────────
# Training
# ──────────────────────────────────────────────────────────────────────────────

def train_extended_mlp():
    """Train MLP classifier on 30 shape types"""
    
    print("\n[Training] Generating synthetic dataset...")
    
    X = []
    y = []
    
    # Generate samples for each shape type
    for shape_idx, shape_type in enumerate(SHAPE_TYPES_30):
        print(f"  [{shape_idx + 1}/{len(SHAPE_TYPES_30)}] Generating {SAMPLES_PER_CLASS} samples for '{shape_type}'...")
        
        for _ in range(SAMPLES_PER_CLASS):
            img = _generate_synthetic_shape(shape_type)
            img_flat = img.flatten()  # Flatten to 784 features
            
            X.append(img_flat)
            y.append(shape_idx)
    
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int32)
    
    print(f"\n[Training] Dataset shape: {X.shape}")
    print(f"[Training] Labels shape: {y.shape}")
    print(f"[Training] Building MLP classifier...")
    
    # Create MLP with expanded output layer
    mlp = MLPClassifier(
        hidden_layer_sizes=(512, 256, 128),  # Same architecture
        activation='relu',
        solver='adam',
        learning_rate='adaptive',
        learning_rate_init=0.001,
        batch_size=32,
        max_iter=100,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=10,
        random_state=42,
        verbose=True
    )
    
    print("\n[Training] Training MLP (this may take 5-10 minutes)...")
    mlp.fit(X, y)
    
    # Evaluate
    print("\n[Training] Training complete!")
    train_score = mlp.score(X, y)
    print(f"[Training] Training accuracy: {train_score:.4f}")
    
    # Save model
    print(f"\n[Training] Saving model to {OUTPUT_MODEL}...")
    joblib.dump(mlp, OUTPUT_MODEL)
    print("[Training] ✓ Model saved successfully!")
    
    return mlp

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("="*80)
    print("Extended MLP Training (4 shapes → 30 shapes)")
    print("="*80)
    
    train_extended_mlp()
    
    print("\n" + "="*80)
    print("✓ Training Complete!")
    print("="*80)
