#!/usr/bin/env python3
"""
Comprehensive diagnostic: Check if rough sketches are truly grabbable in real scenarios
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import ShapeTracker

print("=" * 80)
print("COMPREHENSIVE ROUGH SKETCH GRABBABILITY DIAGNOSTIC")
print("=" * 80)

# Scenario 1: Exact simulation of user drawing behavior
print("\n[SCENARIO 1] Simulating exact user behavior...")
ds = DrawingState(800, 600)

# User draws a rough rectangle (like in the screenshot)
print("  Drawing rough rectangle...")
rough_rect = []
for x in range(150, 300, 10):
    for y in range(150, 250, 10):
        if abs(x - 150) < 5 or abs(x - 300) < 5 or abs(y - 150) < 5 or abs(y - 250) < 5:
            # Add some jitter to make it rough
            jx = x + np.random.randint(-8, 8)
            jy = y + np.random.randint(-8, 8)
            ds.draw_point(jx, jy)
            rough_rect.append((jx, jy))

print(f"    Drew {len(ds.current_stroke)} raw points")
print(f"    Smoothed points: {len(ds._stroke_buf_for_smooth)}")

# Snap it
print("  Calling try_snap_shape()...")
ds.try_snap_shape()

# Check result
print(f"\n  RESULT:")
print(f"    Shapes in tracker: {len(ds.shape_tracker.shapes)}")

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[0]
    print(f"    Shape type: {shape['type']}")
    print(f"    Shape center: {shape['current_pos']}")
    print(f"    Shape size: {shape['size']}")
    print(f"    Shape ID: {shape['id']}")
    
    # NOW test grabbing
    print(f"\n  Testing GRAB simulation...")
    
    # Simulate hand at shape center
    hand_x, hand_y = shape['current_pos']
    print(f"    Hand at ({hand_x}, {hand_y})")
    
    # Trigger grab gesture
    found = ds.shape_tracker.get_nearest(hand_x, hand_y, radius=120)
    
    if found:
        print(f"    FOUND by get_nearest(): YES")
        print(f"      Found ID: {found['id']}")
        print(f"      Correct shape: {found['id'] == shape['id']}")
    else:
        print(f"    FOUND by get_nearest(): NO")
        print(f"    DEBUG: Checking distance calculation...")
        for s in ds.shape_tracker.shapes:
            cx, cy = s.get('center', s.get('current_pos', (0, 0)))
            dist = ((cx - hand_x) ** 2 + (cy - hand_y) ** 2) ** 0.5
            print(f"      Shape at ({cx}, {cy}): distance={dist:.1f}px")
else:
    print("    No shape registered!")

# Scenario 2: Check if the issue is in how shapes are drawn/stored
print("\n[SCENARIO 2] Manual shape creation and grab test...")

ds2 = DrawingState(800, 600)

# Manually create a freehand shape
shape_data = {
    'id': 'test-freehand-1',
    'type': 'freehand',
    'original_pos': (250, 250),
    'current_pos': (250, 250),
    'center': (250, 250),
    'bounding_box': (200, 200, 300, 300),
    'size': (100, 100),
    'rotation': 0,
    'stroke_points': [(i, i) for i in range(-50, 50)],
    'color': (0, 255, 0),
    'thickness': 2,
    'timestamp': 0,
    'moved': False,
    'move_count': 0,
}

ds2.shape_tracker.add_shape(shape_data)
print(f"  Manually added freehand shape at (250, 250)")
print(f"  Shapes in tracker: {len(ds2.shape_tracker.shapes)}")

# Try to grab it
found = ds2.shape_tracker.get_nearest(250, 250, radius=120)
if found:
    print(f"  Can grab manually-created shape: YES")
else:
    print(f"  Can grab manually-created shape: NO")

# Scenario 3: Check tracker state in detail
print("\n[SCENARIO 3] Shape tracker internal state check...")

print(f"  Tracker.shapes list: {len(ds.shape_tracker.shapes)} items")
print(f"  Tracker.shape_ids map: {ds.shape_tracker.shape_ids}")
print(f"  Tracker.creation_order: {ds.shape_tracker.creation_order}")

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[0]
    print(f"\n  Shape[0] details:")
    for key in ['id', 'type', 'center', 'current_pos', 'moved', 'timestamp']:
        print(f"    {key}: {shape.get(key, 'MISSING')}")

print("\n" + "=" * 80)
