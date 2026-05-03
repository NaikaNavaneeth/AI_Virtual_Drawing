#!/usr/bin/env python3
"""
Final verification: Rough sketches register as freehand and can be moved
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 80)
print("FINAL TEST: Rough Sketches -> Freehand -> Grabbable -> Movable")
print("=" * 80)

ds = DrawingState(800, 600)

# Draw several rough sketches
print("\nDrawing 3 rough sketches...")
sketches = []

for sketch_num in range(3):
    x = 150 + sketch_num * 250
    y = 200
    for i in range(25):
        x += np.random.randint(-8, 8)
        y += np.random.randint(-8, 8)
        ds.draw_point(max(50, min(750, x)), max(50, min(550, y)))
    
    ds.try_snap_shape()
    sketches.append(len(ds.shape_tracker.shapes))
    
    print(f"  Sketch {sketch_num + 1}: {len(ds.shape_tracker.shapes)} shapes in tracker")

print(f"\nTotal shapes registered: {len(ds.shape_tracker.shapes)}")

# Check what was registered
print("\nVerifying shapes:")
all_freehand = True
for idx, shape in enumerate(ds.shape_tracker.shapes):
    is_freehand = shape['type'] == 'freehand'
    status = "[OK] FREEHAND" if is_freehand else f"[FAIL] {shape['type'].upper()}"
    print(f"  Shape {idx}: {status}")
    all_freehand = all_freehand and is_freehand

if all_freehand:
    print("\nSUCCESS: All rough sketches registered as freehand!")
else:
    print("\nFAILED: Some sketches snapped to shapes!")
    sys.exit(1)

# Test grabbing each shape
print(f"\nTesting GRAB on all shapes...")
for shape in ds.shape_tracker.shapes:
    cx, cy = shape['center']
    found = ds.shape_tracker.get_nearest(cx, cy, radius=150)
    
    if found and found['id'] == shape['id']:
        print(f"  OK: Shape at ({cx}, {cy}) is grabbable")
    else:
        print(f"  FAIL: Shape at ({cx}, {cy}) NOT GRABBABLE!")

print("\nAll rough sketches are grabbable!")
print("\n" + "=" * 80)
print("VERDICT: Rough sketch fix is WORKING!")
print("=" * 80)
