#!/usr/bin/env python
"""Debug MLP preprocessing to see what the model actually receives"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from utils.shape_mlp_ai import _preprocess_stroke
from ml.drawing_mlp import DrawingMLP, MLPMode

# Test strokes
test_strokes = {
    "circle": [
        (150, 100), (160, 98), (170, 100), (177, 110), (180, 120),
        (177, 130), (170, 140), (160, 142), (150, 140), (143, 130),
        (140, 120), (143, 110), (150, 100)
    ],
    "square": [
        (100, 100), (150, 100), (150, 150), (100, 150), (100, 100)
    ],
    "triangle": [
        (100, 150), (150, 100), (200, 150), (100, 150)
    ],
    "line": [
        (100, 100), (120, 115), (140, 130), (160, 145), (180, 160)
    ],
}

print("Testing MLP preprocessing and model predictions:\n")

# Load the model
clf = DrawingMLP(mode=MLPMode.STANDARD)
clf.load()

canvas_shape = (720, 1280)

for name, stroke in test_strokes.items():
    print(f"Shape: {name}")
    print(f"  Points: {len(stroke)} points, coordinates range: {min(p[0] for p in stroke)}-{max(p[0] for p in stroke)}, {min(p[1] for p in stroke)}-{max(p[1] for p in stroke)}")
    
    # Preprocess
    img_28x28 = _preprocess_stroke(stroke, canvas_shape)
    if img_28x28 is None:
        print("  ERROR: Preprocessing failed\n")
        continue
    
    # Get stats
    nonzero = np.count_nonzero(img_28x28)
    print(f"  Preprocessed: 28x28 image, {nonzero} non-zero pixels, intensity range: {img_28x28.min()}-{img_28x28.max()}")
    
    # Show a simple ASCII visualization
    print(f"  Visual (. = empty, # = filled):")
    for row in img_28x28:
        line = ""
        for val in row:
            if val > 127:
                line += "#"
            elif val > 0:
                line += "~"
            else:
                line += "."
        print(f"    {line}")
    
    # Get prediction
    pred_label, pred_conf = clf.predict(img_28x28)
    all_probs = clf.predict_all_probs(img_28x28)
    
    print(f"  Prediction: {pred_label} (confidence: {pred_conf:.3f})")
    print(f"  All probabilities:")
    for label, prob in all_probs.items():
        print(f"    {label:10} {prob:.3f}")
    
    print()
