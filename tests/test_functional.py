#!/usr/bin/env python
"""Test that shape snapping works through the drawing state"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from modules.drawing_2d import DrawingState

print("\n" + "="*80)
print("FUNCTIONAL TEST: Shape Snapping via DrawingState")
print("="*80 + "\n")

# Create drawing state
ds = DrawingState(1280, 720)
ds.snap_active = True  # Enable snapping

# Test 1: Draw and snap a circle
print("Test 1: Circle snapping")
ds.current_stroke = []
for angle in range(0, 360, 10):
    rad = math.radians(angle)
    x = 150 + 35 * math.cos(rad)
    y = 120 + 35 * math.sin(rad)
    ds.current_stroke.append((int(x), int(y)))

print(f"  Created circle stroke with {len(ds.current_stroke)} points")
print(f"  Snap active: {ds.snap_active}")
print(f"  Current stroke length: {len(ds.current_stroke)}")

# Call try_snap_shape
ds.try_snap_shape(None)
print(f"  Shapes on canvas after snapping: {len(ds.shapes)}")
if ds.shapes:
    for shape in ds.shapes:
        print(f"    - {shape['type']}: {len(shape['pts'])} points")
    print(f"  ✅ Circle was snapped!")
else:
    print(f"  ❌ Circle was NOT snapped (treated as freehand or failed detection)")

# Test 2: Draw and snap a square
print("\nTest 2: Square snapping")
ds.shapes = []  # Clear
ds.current_stroke = []
square_points = [(100, 100), (150, 100), (150, 150), (100, 150), (100, 100)]
for i in range(len(square_points) - 1):
    p1 = square_points[i]
    p2 = square_points[i + 1]
    # Interpolate between points
    for t in [j/10.0 for j in range(11)]:
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + (p2[1] - p1[1]) * t
        ds.current_stroke.append((int(x), int(y)))

print(f"  Created square stroke with {len(ds.current_stroke)} points")

ds.try_snap_shape(None)
print(f"  Shapes on canvas after snapping: {len(ds.shapes)}")
if ds.shapes:
    for shape in ds.shapes:
        print(f"    - {shape['type']}: {len(shape['pts'])} points")
    print(f"  ✅ Square was snapped!")
else:
    print(f"  ❌ Square was NOT snapped")

# Test 3: Draw and snap a line
print("\nTest 3: Line snapping")
ds.shapes = []  # Clear
ds.current_stroke = []
for i in range(21):
    t = i / 20.0
    x = 100 + (100 * t)
    y = 100 + (50 * t)
    ds.current_stroke.append((int(x), int(y)))

print(f"  Created line stroke with {len(ds.current_stroke)} points")

ds.try_snap_shape(None)
print(f"  Shapes on canvas after snapping: {len(ds.shapes)}")
if ds.shapes:
    for shape in ds.shapes:
        print(f"    - {shape['type']}: {len(shape['pts'])} points")
    print(f"  ✅ Line was snapped!")
else:
    print(f"  ❌ Line was NOT snapped")

print("\n" + "="*80)
print("✅ Functional tests complete!")
print("="*80 + "\n")
