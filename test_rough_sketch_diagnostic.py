#!/usr/bin/env python3
"""
Diagnose why rough sketches are not detecting properly
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 70)
print("ROUGH SKETCH DETECTION DIAGNOSTIC")
print("=" * 70)

# Create drawing state
ds = DrawingState(800, 600)

# Simulate a rough/scribbled sketch (not a perfect shape)
# This is what a user would actually draw
print("\nSimulating rough sketch...")

# Create a messy, scribbled stroke (like freehand)
rough_stroke = []

# Add some random-ish points to simulate rough drawing
import random
x, y = 200, 200
for i in range(50):  # 50 points = more than _MIN_SNAP_PTS (15)
    # Add some randomness to make it rough
    if i % 5 == 0:
        x += random.randint(-30, 30)
        y += random.randint(-30, 30)
    else:
        x += random.randint(-5, 5)
        y += random.randint(-5, 5)
    
    # Keep within bounds
    x = max(50, min(750, x))
    y = max(50, min(550, y))
    rough_stroke.append((x, y))

print(f"  Created rough stroke with {len(rough_stroke)} points")

# Add to drawing state
ds.current_stroke = rough_stroke
ds._stroke_buf_for_smooth = rough_stroke.copy()
ds.snap_active = True

print("\nBefore snapping:")
print(f"  Snap active: {ds.snap_active}")
print(f"  Stroke points: {len(ds.current_stroke)}")
print(f"  Shapes in tracker: {len(ds.shape_tracker.shapes)}")

# Try to snap
print("\nCalling try_snap_shape()...")
ds.try_snap_shape(collab_client=None)

print("\nAfter snapping:")
print(f"  Shapes in tracker: {len(ds.shape_tracker.shapes)}")

if ds.shape_tracker.shapes:
    for idx, shape in enumerate(ds.shape_tracker.shapes):
        print(f"  Shape {idx}: type='{shape['type']}', center={shape['current_pos']}, size={shape['size']}")
else:
    print("  NO SHAPES REGISTERED!")

print("\n" + "=" * 70)
if len(ds.shape_tracker.shapes) > 0:
    shape = ds.shape_tracker.shapes[0]
    print(f"SUCCESS: Rough sketch registered as '{shape['type']}'")
    if shape['type'] == 'freehand':
        print("  - Correctly identified as freehand sketch")
    else:
        print(f"  - WARNING: Registered as '{shape['type']}' instead of 'freehand'")
        print("  - This explains why rough sketches appear incorrect!")
else:
    print("ISSUE: Rough sketch not registered at all!")
    print("  - Check if stroke has enough points (need >= 15)")
    print("  - Check if snap_active is enabled")
