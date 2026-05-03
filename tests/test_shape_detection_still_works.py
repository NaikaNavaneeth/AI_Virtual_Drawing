#!/usr/bin/env python3
"""
Test that clean shape detection still works after the rough sketch fix.
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 70)
print("SHAPE DETECTION VERIFICATION")
print("=" * 70)

ds = DrawingState(800, 600)

# Test 1: Clean circle
print("\n[Test 1] Clean Circle Detection")
print("-" * 70)

# Draw a proper circle
circle_center = (200, 200)
radius = 80
circle_stroke = []
for angle in np.linspace(0, 2 * np.pi, 120):
    x = int(circle_center[0] + radius * np.cos(angle))
    y = int(circle_center[1] + radius * np.sin(angle))
    circle_stroke.append((x, y))

ds.current_stroke = circle_stroke
ds._stroke_buf_for_smooth = circle_stroke.copy()
ds.snap_active = True

print(f"Circle stroke: {len(circle_stroke)} points")
ds.try_snap_shape(collab_client=None)

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[-1]
    print(f"✓ Detected: {shape['type']}")
    if shape['type'] in ['circle', 'polygon']:
        print("  PASS: Circle recognized")
    else:
        print(f"  FAIL: Got {shape['type']} instead")
else:
    print("✗ No shape detected")

# Clear
ds.shape_tracker.shapes.clear()
ds.current_stroke.clear()
ds._stroke_buf_for_smooth.clear()

# Test 2: Clean Square
print("\n[Test 2] Clean Square Detection")
print("-" * 70)

square_stroke = [
    (150, 150), (250, 150), # Top edge
    (250, 250),              # top-right to bottom-right
    (150, 250),              # bottom edge
    (150, 150),              # close shape
] + [(150 + i*2, 150) for i in range(50)]  # Make it longer

ds.current_stroke = square_stroke
ds._stroke_buf_for_smooth = square_stroke.copy()
ds.snap_active = True

print(f"Square stroke: {len(square_stroke)} points")
ds.try_snap_shape(collab_client=None)

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[-1]
    print(f"✓ Detected: {shape['type']}")
    if shape['type'] in ['square', 'rectangle', 'polygon']:
        print("  PASS: Square-like shape recognized")
    else:
        print(f"  FAIL: Got {shape['type']} instead")
else:
    print("✗ No shape detected")

# Clear
ds.shape_tracker.shapes.clear()
ds.current_stroke.clear()
ds._stroke_buf_for_smooth.clear()

# Test 3: Clean Line
print("\n[Test 3] Clean Line Detection")
print("-" * 70)

line_stroke = [(100 + i*2, 300 + i) for i in range(75)]

ds.current_stroke = line_stroke
ds._stroke_buf_for_smooth = line_stroke.copy()
ds.snap_active = True

print(f"Line stroke: {len(line_stroke)} points")
ds.try_snap_shape(collab_client=None)

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[-1]
    print(f"✓ Detected: {shape['type']}")
    if shape['type'] in ['line', 'polygon']:
        print("  PASS: Line recognized")
    else:
        print(f"  FAIL: Got {shape['type']} instead")
else:
    print("✗ No shape detected")

print("\n" + "=" * 70)
print("SUMMARY: All clean shapes should still be detected")
print("=" * 70)
