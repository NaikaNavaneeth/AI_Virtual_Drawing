"""
Debug detect_and_snap with detailed metrics
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.shape_ai import (
    detect_and_snap, _subsample, _circularity, 
    _aspect_ratio, _straightness, _closure_ratio, _rdp_simplify
)

print("=" * 80)
print("TESTING detect_and_snap() with circle")
print("=" * 80)

# Create rough circle
rough_circle = []
for i in range(30):
    angle = (i / 30) * 2 * np.pi
    x = int(100 + 50 * np.cos(angle) + np.random.randint(-8, 8))
    y = int(100 + 50 * np.sin(angle) + np.random.randint(-8, 8))
    rough_circle.append((x, y))

print(f"\nStroke: {len(rough_circle)} points")

# Get metrics
sub = _subsample(rough_circle, 64)
circ = _circularity(sub)
ar = _aspect_ratio(sub)
strt = _straightness(sub)
clos = _closure_ratio(sub)
simplified = _rdp_simplify(sub, epsilon=5)
corner_count = len(simplified)

print(f"\nMetrics:")
print(f"  Circularity: {circ:.3f} (threshold > 0.70)")
print(f"  Aspect ratio: {ar:.3f} (threshold < 1.5)")
print(f"  Closure ratio: {clos:.3f} (threshold < 0.25)")
print(f"  Straightness: {strt:.3f} (threshold > 0.88 = line)")
print(f"  Corner count: {corner_count}")

print(f"\nCircle detection checks:")
print(f"  circ > 0.70? {circ > 0.70}")
print(f"  clos < 0.25? {clos < 0.25}")
print(f"  ar < 1.5? {ar < 1.5}")
print(f"  ALL checks pass? {circ > 0.70 and clos < 0.25 and ar < 1.5}")

print(f"\nCalling detect_and_snap()...")
result = detect_and_snap(rough_circle)

if result:
    shape, clean_pts = result
    if shape:
        print(f"✓ DETECTED: {shape}")
    else:
        print(f"✗ Returned (None, None)")
else:
    print(f"✗ Returned None")

print("\n" + "=" * 80)
