#!/usr/bin/env python3
"""
Detailed trace to understand why rough sketches aren't being registered.
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 80)
print("DETAILED TRACE: Rough Sketch Registration and Grabbing")
print("=" * 80)

# Create DrawingState
ds = DrawingState(800, 600)

# Create a totally rough scribble (random points)
print("\n[STEP 1] Creating rough sketch...")
rough = []
x, y = 200, 200
for i in range(50):
    x += np.random.randint(-15, 15)
    y += np.random.randint(-15, 15)
    rough.append((max(50, min(750, x)), max(50, min(550, y))))

print(f"  Created {len(rough)} points")
print(f"  Sample: {rough[:3]}")

# Set up the stroke in DrawingState
print("\n[STEP 2] Setting up stroke in DrawingState...")
ds.current_stroke = rough
ds._stroke_buf_for_smooth = rough.copy()
ds.snap_active = True

print(f"  current_stroke: {len(ds.current_stroke)} points")
print(f"  _stroke_buf_for_smooth: {len(ds._stroke_buf_for_smooth)} points")
print(f"  snap_active: {ds.snap_active}")

# Check shape tracker BEFORE snapping
print("\n[STEP 3] Shape tracker state BEFORE snapping...")
print(f"  Shapes in tracker: {len(ds.shape_tracker.shapes)}")
print(f"  Shape IDs: {ds.shape_tracker.shape_ids}")

# Call try_snap_shape (this is where the registration happens)
print("\n[STEP 4] Calling try_snap_shape()...")
try:
    ds.try_snap_shape(collab_client=None)
    print("  try_snap_shape() completed successfully")
except Exception as e:
    print(f"  ERROR: try_snap_shape() raised: {e}")
    import traceback
    traceback.print_exc()

# Check shape tracker AFTER snapping
print("\n[STEP 5] Shape tracker state AFTER snapping...")
print(f"  Shapes in tracker: {len(ds.shape_tracker.shapes)}")
print(f"  Shape IDs: {ds.shape_tracker.shape_ids}")

if ds.shape_tracker.shapes:
    for idx, shape in enumerate(ds.shape_tracker.shapes):
        print(f"\n  Shape {idx}:")
        print(f"    ID: {shape.get('id')}")
        print(f"    Type: {shape.get('type')}")
        print(f"    Center: {shape.get('center')}")
        print(f"    Current Pos: {shape.get('current_pos')}")
        print(f"    Size: {shape.get('size')}")
        if shape.get('type') == 'freehand':
            print(f"    Stroke points (relative): {len(shape.get('stroke_points', []))} points")
else:
    print("  WARNING: No shapes registered!")

# Now test grabbing
print("\n[STEP 6] Testing GRAB at position (210, 205)...")
test_x, test_y = 210, 205

print(f"  Looking for shapes near ({test_x}, {test_y}) within 120px radius...")

grabbed = ds.shape_tracker.get_nearest(test_x, test_y, radius=120)

if grabbed:
    print(f"  SUCCESS: Found shape!")
    print(f"    ID: {grabbed.get('id')}")
    print(f"    Type: {grabbed.get('type')}")
    print(f"    Center: {grabbed.get('center')}")
    
    # Calculate distance
    cx, cy = grabbed.get('center', (0, 0))
    dist = ((cx - test_x) ** 2 + (cy - test_y) ** 2) ** 0.5
    print(f"    Distance: {dist:.1f}px")
else:
    print(f"  FAILED: No shape found!")
    print(f"  Debugging info:")
    
    for idx, shape in enumerate(ds.shape_tracker.shapes):
        cx, cy = shape.get('center', shape.get('current_pos', (0, 0)))
        dist = ((cx - test_x) ** 2 + (cy - test_y) ** 2) ** 0.5
        print(f"    Shape {idx} ({shape.get('type')}): center=({cx}, {cy}), distance={dist:.1f}px")
        
        # Check if it's within radius
        if dist <= 120:
            print(f"      -> This shape IS within 120px radius but wasn't returned!")
        else:
            print(f"      -> This shape is {dist - 120:.1f}px outside radius")

print("\n" + "=" * 80)
