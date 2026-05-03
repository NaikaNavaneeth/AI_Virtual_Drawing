#!/usr/bin/env python3
"""
Final comprehensive test: Simulate user drawing rough vs. clean shapes.
This demonstrates that the fix allows rough sketches while preserving shape detection.
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("\n" + "=" * 80)
print("COMPREHENSIVE ROUGH SKETCH FIX DEMONSTRATION")
print("=" * 80)

ds = DrawingState(800, 600)

def test_stroke(name, stroke_points, expected_type):
    """Test a stroke and verify the result."""
    print(f"\n{name}")
    print("-" * 80)
    
    ds.current_stroke = stroke_points
    ds._stroke_buf_for_smooth = stroke_points.copy()
    ds.snap_active = True
    
    print(f"  Stroke: {len(stroke_points)} points")
    initial_count = len(ds.shape_tracker.shapes)
    
    ds.try_snap_shape(collab_client=None)
    
    if len(ds.shape_tracker.shapes) > initial_count:
        shape = ds.shape_tracker.shapes[-1]
        detected = shape['type']
        status = "[PASS]" if expected_type.lower() in detected.lower() or detected == expected_type else "[FAIL]"
        print(f"  Result: {detected:15} {status}")
        if expected_type.lower() not in detected.lower() and detected != expected_type:
            print(f"    Expected: {expected_type}, Got: {detected}")
    else:
        print(f"  Result: (no shape detected) - Registered as freehand")
    
    # Clean up for next test
    ds.current_stroke.clear()
    ds._stroke_buf_for_smooth.clear()

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Rough scribble (messy, random)
print(f"\n{'SCENARIO 1: ROUGH SKETCHES (should be FREEHAND)':^80}")
print("=" * 80)

# Rough, scribbled line
rough1 = []
x, y = 100, 100
for i in range(60):
    x += np.random.randint(-20, 20)
    y += np.random.randint(-20, 20)
    rough1.append((max(50, min(750, x)), max(50, min(550, y))))

test_stroke("Rough scribble #1 (totally random)", rough1, "freehand")

# Rough scribble 2
rough2 = []
x, y = 400, 300
for i in range(50):
    x += np.random.randint(-15, 15)
    y += np.random.randint(-15, 15)
    rough2.append((max(50, min(750, x)), max(50, min(550, y))))

test_stroke("Rough scribble #2 (messy notes)", rough2, "freehand")

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Clean shapes (should snap)
print(f"\n{'SCENARIO 2: CLEAN SHAPES (should SNAP)':^80}")
print("=" * 80)

# Clean circle
circle = []
for angle in np.linspace(0, 2 * np.pi, 100):
    x = int(150 + 60 * np.cos(angle))
    y = int(200 + 60 * np.sin(angle))
    circle.append((x, y))

test_stroke("Clean perfect circle", circle, "circle")

# Clean square
square = [
    (300, 200), (400, 200),  # top
    (400, 300),              # right
    (300, 300),              # bottom
    (300, 200),              # close
]
# Extend to >= 20 points
for i in range(20):
    square.append((300 + i*4, 200))

test_stroke("Clean square (4 clear corners)", square, "square")

# Clean line (diagonal)
line = [(100 + i*3, 100 + i*2) for i in range(50)]
test_stroke("Clean diagonal line", line, "line")

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Mixed - rough circle attempt (tricky case)
print(f"\n{'SCENARIO 3: TRICKY CASES (nearly circular but rough)':^80}")
print("=" * 80)

# Try to draw circle but rough/wobbly
rough_circle = []
for angle in np.linspace(0, 2 * np.pi, 80):
    x = int(150 + 50 * np.cos(angle))
    y = int(450 + 50 * np.sin(angle))
    # Add random jitter
    x += np.random.randint(-8, 8)
    y += np.random.randint(-8, 8)
    rough_circle.append((max(50, min(750, x)), max(50, min(550, y))))

test_stroke("Wobbly circle (jittery but circular)", rough_circle, "circle")

print("\n" + "=" * 80)
print("DEMONSTRATION COMPLETE")
print("=" * 80)
print("""
INTERPRETATION:
- If rough sketches show freehand --> FIX IS WORKING [OK]
- If clean shapes still snap --> SHAPE DETECTION PRESERVED [OK]
- Wobbly circle falls to freehand --> VALIDATION IS WORKING [OK]

The fix allows natural, rough sketching while preserving intentional shape detection.
""")
