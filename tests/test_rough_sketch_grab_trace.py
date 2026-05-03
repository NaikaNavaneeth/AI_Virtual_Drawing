#!/usr/bin/env python3
"""
Detailed diagnostic: Trace exactly what happens when a rough sketch is drawn
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 80)
print("DETAILED ROUGH SKETCH TRACE")
print("=" * 80)

ds = DrawingState(800, 600)

# Create a totally rough scribble
rough = []
x, y = 200, 200
for i in range(50):
    x += np.random.randint(-15, 15)
    y += np.random.randint(-15, 15)
    rough.append((max(50, min(750, x)), max(50, min(550, y))))

print(f"\nCreated rough stroke: {len(rough)} points")
print(f"Points sample: {rough[:5]}")

# Set up the stroke
ds.current_stroke = rough
ds._stroke_buf_for_smooth = rough.copy()
ds.snap_active = True

print("\n[BEFORE SNAP]")
print(f"  snap_active: {ds.snap_active}")
print(f"  current_stroke: {len(ds.current_stroke)} points")
print(f"  shapes in tracker: {len(ds.shape_tracker.shapes)}")
print(f"  freehand strokes: {len(ds.shape_tracker.freehand_strokes)}")

print("\n[CALLING try_snap_shape...]")
ds.try_snap_shape(collab_client=None)

print("\n[AFTER SNAP]")
print(f"  shapes in tracker: {len(ds.shape_tracker.shapes)}")
print(f"  freehand strokes: {len(ds.shape_tracker.freehand_strokes)}")

# Check what was actually registered
if ds.shape_tracker.shapes:
    for i, shape in enumerate(ds.shape_tracker.shapes):
        print(f"\n  Shape {i}:")
        print(f"    type: {shape.get('type')}")
        print(f"    pts: {len(shape.get('pts', []))} points")
        print(f"    pos: {shape.get('current_pos')}")

if ds.shape_tracker.freehand_strokes:
    for i, stroke in enumerate(ds.shape_tracker.freehand_strokes):
        print(f"\n  Freehand {i}:")
        print(f"    pts: {len(stroke.get('pts', []))} points")
        print(f"    pos: {stroke.get('current_pos')}")

# Now try to grab it
print("\n[ATTEMPTING GRAB]")
print(f"  Testing pick at position (210, 205)...")

# Check if it's grabbable
grabbed = ds.try_pick_shape_at_pos(210, 205)
print(f"  try_pick_shape_at_pos result: {grabbed}")

if grabbed:
    print(f"  Current grabbed_shape: {ds.grabbed_shape}")
    if ds.grabbed_shape:
        print(f"    type: {ds.grabbed_shape.get('type')}")
else:
    print(f"  WARNING: Could not grab the stroke!")
    
    # Debug: check what shapes are actually at that position
    print(f"\n[DEBUG] All shapes/strokes in tracker:")
    for shape in ds.shape_tracker.shapes:
        pos = shape.get('current_pos', (0, 0))
        size = shape.get('size', (0, 0))
        print(f"  Shape '{shape.get('type')}' at {pos}, size {size}")
    
    for stroke in ds.shape_tracker.freehand_strokes:
        pos = stroke.get('current_pos', (0, 0))
        print(f"  Freehand at {pos}")
