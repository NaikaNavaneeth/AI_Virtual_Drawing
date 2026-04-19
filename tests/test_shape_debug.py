"""
test_shape_detection_debug.py - Debug shape detection with actual metrics

Shows what detect_and_snap is actually calculating internally
"""

import sys
import os
import math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.shape_ai import _subsample, _circularity, _aspect_ratio, _closure_ratio, _straightness

print("=" * 80)
print("  Shape Detection - Debugging Metrics")
print("=" * 80)

# ==============================================================================
# TEST: Rectangle (imperfect)
# ==============================================================================
print("\n[DEBUG] Imperfect Rectangle")
print("-" * 80)

rect_pts = []
# Top edge (left to right, slightly wavy)
for x in range(50, 150):
    y = 50 + int(2 * math.sin(x / 10))
    rect_pts.append((x, y))
# Right edge (top to bottom)
for y in range(50, 150):
    x = 150 + int(2 * math.cos(y / 10))
    rect_pts.append((x, y))
# Bottom edge (right to left)
for x in range(150, 50, -1):
    y = 150 - int(2 * math.sin(x / 10))
    rect_pts.append((x, y))
# Left edge (bottom to top)
for y in range(150, 50, -1):
    x = 50 - int(2 * math.cos(y / 10))
    rect_pts.append((x, y))

# Subsample like the actual function does
sub = _subsample(rect_pts, 64)
circ = _circularity(sub)
ar = _aspect_ratio(rect_pts)
strt = _straightness(rect_pts)
clos = _closure_ratio(rect_pts)

print(f"  Total points: {len(rect_pts)}")
print(f"  Subsampled points: {len(sub)}")
print(f"  Metrics:")
print(f"    Circularity: {circ:.4f}")
print(f"    Aspect ratio: {ar:.2f}")
print(f"    Straightness: {strt:.4f}")
print(f"    Closure ratio: {clos:.4f}")
print()
print(f"  Detection Checks:")
print(f"    strt > 0.88? {strt > 0.88} → Line?")
print(f"    circ < 0.65 AND clos < 0.25 AND ar < 3.5? {circ < 0.65 and clos < 0.25 and ar < 3.5} → Rectangle!")
print(f"    circ > 0.70 AND clos < 0.20 AND ar < 1.5? {circ > 0.70 and clos < 0.20 and ar < 1.5} → Circle?")

# ==============================================================================
# TEST: Actual Circle
# ==============================================================================
print("\n[DEBUG] True Circle")
print("-" * 80)

circle_pts = []
for angle in np.linspace(0, 2 * np.pi, 100):
    x = 100 + int(50 * math.cos(angle))
    y = 100 + int(50 * math.sin(angle))
    circle_pts.append((x, y))

sub = _subsample(circle_pts, 64)
circ = _circularity(sub)
ar = _aspect_ratio(circle_pts)
strt = _straightness(circle_pts)
clos = _closure_ratio(circle_pts)

print(f"  Total points: {len(circle_pts)}")
print(f"  Subsampled points: {len(sub)}")
print(f"  Metrics:")
print(f"    Circularity: {circ:.4f}")
print(f"    Aspect ratio: {ar:.2f}")
print(f"    Straightness: {strt:.4f}")
print(f"    Closure ratio: {clos:.4f}")
print()
print(f"  Detection Checks:")
print(f"    strt > 0.88? {strt > 0.88} → Line?")
print(f"    circ < 0.65 AND clos < 0.25 AND ar < 3.5? {circ < 0.65 and clos < 0.25 and ar < 3.5} → Rectangle?")
print(f"    circ > 0.70 AND clos < 0.20 AND ar < 1.5? {circ > 0.70 and clos < 0.20 and ar < 1.5} → Circle!")
