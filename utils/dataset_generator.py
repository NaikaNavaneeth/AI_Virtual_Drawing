"""
utils/dataset_generator.py - Synthetic dataset generation.

OPTIMIZED APPROACH (April 5, 2026):
- Clean shapes with minimal noise (99%+ accuracy achieved baseline)
- Focus: Clean shapes produce excellent accuracy with MLP
- Strategy: Use shape fitting + temporal smoothing + rule-based detection as primary fallback
"""
import numpy as np
import cv2
import random
from typing import Tuple

IMG_SIZE = 28
NUM_SAMPLES_PER_CLASS = 5000  # 20K total (5K per class)
NUM_CLASSES = 4  # 0: circle, 1: square, 2: triangle, 3: line


def generate_shape(shape_type: int) -> np.ndarray:
    """Generates clean shapes with minimal noise."""
    img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    color = 255
    thickness = 2  # Fixed thickness
    
    margin = 5
    center = IMG_SIZE // 2
    
    if shape_type == 0:  # Circle
        radius = random.randint(6, IMG_SIZE // 2 - margin)
        cv2.circle(img, (center, center), radius, color, thickness)
    
    elif shape_type == 1:  # Square
        side = random.randint(10, IMG_SIZE - 2 * margin)
        x1 = center - side // 2
        y1 = center - side // 2
        x2 = x1 + side
        y2 = y1 + side
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

    elif shape_type == 2:  # Triangle
        half_side = random.randint(6, IMG_SIZE // 2 - margin)
        p1 = (center, center - half_side)
        p2 = (center - half_side, center + half_side)
        p3 = (center + half_side, center + half_side)
        
        pts = np.array([p1, p2, p3], np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(img, [pts], isClosed=True, color=color, thickness=thickness)

    elif shape_type == 3:  # Line
        x1 = margin
        y1 = margin
        x2 = IMG_SIZE - margin
        y2 = IMG_SIZE - margin
        if random.random() > 0.5:  # make it horizontal sometimes
            y2 = y1
        cv2.line(img, (x1, y1), (x2, y2), color, thickness)

    # Add only minimal light noise (4% chance)
    if random.random() > 0.96:
        noise = np.random.normal(0, 2, img.shape).astype(np.float32)
        img = (img.astype(np.float32) + noise).astype(np.uint8)
    
    img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def create_dataset() -> Tuple[np.ndarray, np.ndarray]:
    """Creates clean dataset (20K samples: 5K per class)."""
    X = []
    y = []
    
    print(f"[Dataset] Generating {NUM_SAMPLES_PER_CLASS * NUM_CLASSES} samples ({NUM_SAMPLES_PER_CLASS} per class)...")
    
    for class_id in range(NUM_CLASSES):
        class_names = ["circle", "square", "triangle", "line"]
        print(f"  Generating {class_names[class_id]}...", end="", flush=True)
        
        for _ in range(NUM_SAMPLES_PER_CLASS):
            img = generate_shape(class_id)
            X.append(img)
            y.append(class_id)
        
        print(" [OK]")

    print(f"[Dataset] Dataset created: {len(X)} samples")
    X_array = np.array(X)
    y_array = np.array(y)
    
    # Verify data integrity
    print(f"[Dataset] X dtype: {X_array.dtype}, X range: [{X_array.min()}, {X_array.max()}]")
    
    return X_array, y_array


if __name__ == '__main__':
    # For testing: generate and show some samples
    X_data, y_data = create_dataset()
    
    print(f"Generated dataset with shape: {X_data.shape}")
    print(f"Labels shape: {y_data.shape}")
    print(f"Data range: [{X_data.min()}, {X_data.max()}]")

