#!/usr/bin/env python
"""
Test shape detection with realistic strokes that have many interpolated points
(mimicking actual user drawing with frequent sampling)
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def interpolate_points(p1, p2, steps=5):
    """Interpolate between two points"""
    x1, y1 = p1
    x2, y2 = p2
    result = []
    for i in range(steps):
        t = i / steps
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        result.append((int(x), int(y)))
    return result

# Create realistic test strokes with many interpolated points
test_strokes = {
    "circle_realistic": [],  # Will be filled below
    "square_realistic": [],
    "triangle_realistic": [],
    "line_realistic": [],
}

# Circle: sample points along circumference
circle_center = (150, 120)
circle_radius = 35
for angle in range(0, 360, 10):
    rad = math.radians(angle)
    x = circle_center[0] + circle_radius * math.cos(rad)
    y = circle_center[1] + circle_radius * math.sin(rad)
    test_strokes["circle_realistic"].append((int(x), int(y)))

# Square: draw 4 sides with interpolated points
square_corners = [(100, 100), (150, 100), (150, 150), (100, 150), (100, 100)]
for i in range(len(square_corners) - 1):
    p1 = square_corners[i]
    p2 = square_corners[i + 1]
    points = interpolate_points(p1, p2, steps=10)
    test_strokes["square_realistic"].extend(points)

# Triangle: draw 3 sides with interpolated points
triangle_corners = [(100, 150), (200, 100), (150, 150), (100, 150)]
for i in range(len(triangle_corners) - 1):
    p1 = triangle_corners[i]
    p2 = triangle_corners[i + 1]
    points = interpolate_points(p1, p2, steps=10)
    test_strokes["triangle_realistic"].extend(points)

# Line: interpolate along diagonal
line_start = (100, 100)
line_end = (200, 150)
test_strokes["line_realistic"] = interpolate_points(line_start, line_end, steps=20)

print("\n" + "="*80)
print("SHAPE DETECTION TEST WITH REALISTIC STROKES")
print("="*80 + "\n")

from modules.drawing_2d import DrawingState
from utils.shape_ai import detect_and_snap
from utils.shape_mlp_ai import detect_and_snap_mlp

ds = DrawingState(1280, 720)

print("STEP 1: Check Stroke Properties")
print("-" * 80)

for name, stroke in test_strokes.items():
    is_valid = ds._is_valid_shape_stroke(stroke)
    status = "✅ VALID" if is_valid else "❌ INVALID"
    print(f"{name:20} → {status} ({len(stroke)} points)")

print("\n" + "="*80)
print("STEP 2: Test Tier 1 (Rule-Based)")
print("-" * 80)

for name, stroke in test_strokes.items():
    if ds._is_valid_shape_stroke(stroke):
        shape, pts = detect_and_snap(stroke)
        if shape:
            print(f"{name:20} → ✅ {shape}")
        else:
            print(f"{name:20} → ❌ Not detected")
    else:
        print(f"{name:20} → ⏸️  Blocked by validation")

print("\n" + "="*80)
print("STEP 3: Test Tier 2 (MLP)")
print("-" * 80)

for name, stroke in test_strokes.items():
    if ds._is_valid_shape_stroke(stroke):
        try:
            shape, pts = detect_and_snap_mlp(stroke, (720, 1280))
            if shape:
                print(f"{name:20} → ✅ {shape}")
            else:
                print(f"{name:20} → ⚠️  Low confidence/rejected")
        except Exception as e:
            print(f"{name:20} → ❌ Error: {str(e)[:40]}")
    else:
        print(f"{name:20} → ⏸️  Blocked by validation")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80 + "\n")

print("✅ Test complete. Summary:")
print("   - Circle: Should detect as circle")
print("   - Square: Should detect as square")
print("   - Triangle: Should detect as triangle")
print("   - Line: Should detect as line")
print("\nNote: MLP may misclassify some shapes due to model accuracy.")
print("Tier 1 (rule-based) should work well for geometric shapes.")
print()
