#!/usr/bin/env python
"""
Comprehensive shape detection test - diagnose exact issue
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("\n" + "="*80)
print("COMPREHENSIVE SHAPE DETECTION TEST")
print("="*80 + "\n")

# Create realistic test strokes
test_strokes = {
    "circle_perfect": [
        (150, 100), (160, 98), (170, 100), (177, 110), (180, 120),
        (177, 130), (170, 140), (160, 142), (150, 140), (143, 130),
        (140, 120), (143, 110), (150, 100)
    ],
    "square_perfect": [
        (100, 100), (150, 100), (150, 150), (100, 150), (100, 100)
    ],
    "triangle_perfect": [
        (100, 150), (150, 100), (200, 150), (100, 150)
    ],
    "line_perfect": [
        (100, 100), (120, 115), (140, 130), (160, 145), (180, 160)
    ],
}

from modules.drawing_2d import DrawingState
from utils.shape_ai import detect_and_snap
from utils.shape_mlp_ai import detect_and_snap_mlp

ds = DrawingState(1280, 720)

print("STEP 1: Check Stroke Validation")
print("-" * 80)

for name, stroke in test_strokes.items():
    is_valid = ds._is_valid_shape_stroke(stroke)
    print(f"{name:20} → {'✅ VALID' if is_valid else '❌ INVALID'}")
    
    if not is_valid:
        xs = [p[0] for p in stroke]
        ys = [p[1] for p in stroke]
        x_sp = max(xs) - min(xs)
        y_sp = max(ys) - min(ys)
        print(f"  → X spread: {x_sp}, Y spread: {y_sp}, Area: {x_sp*y_sp}")

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
            print(f"{name:20} → ❌ Error: {str(e)[:30]}")
    else:
        print(f"{name:20} → ⏸️  Blocked by validation")

print("\n" + "="*80)
print("STEP 4: Analyze Validation Thresholds")
print("-" * 80)

print("\nCurrent validation requirements:")
print("  ✓ Min spread: 20 pixels (X or Y)")
print("  ✓ Avg distance: < 25 pixels")
print("  ✓ Max distance: < 50 pixels")
print("  ✓ Large gaps: < 30% of points")
print("  ✓ Min bbox area: 400 pixels²")
print("  ✓ Max aspect ratio: 15:1")

print("\nTest stroke metrics:")
for name, stroke in test_strokes.items():
    xs = [p[0] for p in stroke]
    ys = [p[1] for p in stroke]
    x_sp = max(xs) - min(xs)
    y_sp = max(ys) - min(ys)
    area = x_sp * y_sp
    
    distances = []
    for i in range(1, len(stroke)):
        dx = stroke[i][0] - stroke[i-1][0]
        dy = stroke[i][1] - stroke[i-1][1]
        dist = math.hypot(dx, dy)
        distances.append(dist)
    
    avg_dist = sum(distances) / len(distances) if distances else 0
    max_dist = max(distances) if distances else 0
    
    print(f"\n{name}:")
    print(f"  X spread: {x_sp} {'✓' if x_sp >= 20 else '✗'}")
    print(f"  Y spread: {y_sp} {'✓' if y_sp >= 20 else '✗'}")
    print(f"  Area: {area} {'✓' if area >= 400 else '✗'}")
    print(f"  Avg dist: {avg_dist:.1f} {'✓' if avg_dist < 25 else '✗'}")
    print(f"  Max dist: {max_dist:.1f} {'✓' if max_dist < 50 else '✗'}")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80 + "\n")

# Check validation
valid_count = sum(1 for name, stroke in test_strokes.items() if ds._is_valid_shape_stroke(stroke))

if valid_count == len(test_strokes):
    print("✅ All test strokes pass validation")
    print("✅ Issue is likely in Tier 1 or Tier 2 detection, not validation")
elif valid_count > 0:
    print(f"⚠️  Only {valid_count}/{len(test_strokes)} strokes pass validation")
    print("⚠️  Validation thresholds may be too strict")
else:
    print("❌ NO strokes pass validation!")
    print("❌ Validation thresholds are definitely too strict")

print("\n" + "="*80 + "\n")
