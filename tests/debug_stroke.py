#!/usr/bin/env python
"""Debug stroke validation"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

valid_stroke = [
    (100, 100), (110, 105), (120, 115), (130, 130),
    (135, 150), (130, 170), (110, 185), (90, 190),
    (70, 185), (50, 170), (45, 150), (50, 130),
    (70, 115), (90, 105), (100, 100)
]

xs = [p[0] for p in valid_stroke]
ys = [p[1] for p in valid_stroke]
x_spread = max(xs) - min(xs)
y_spread = max(ys) - min(ys)
bbox_area = x_spread * y_spread

print(f"Stroke points: {len(valid_stroke)}")
print(f"X spread: {x_spread} (min: {min(xs)}, max: {max(xs)})")
print(f"Y spread: {y_spread} (min: {min(ys)}, max: {max(ys)})")
print(f"BBox area: {bbox_area} (need > 400)")

# Calculate distances
distances = []
for i in range(1, len(valid_stroke)):
    dx = valid_stroke[i][0] - valid_stroke[i-1][0]
    dy = valid_stroke[i][1] - valid_stroke[i-1][1]
    dist = math.hypot(dx, dy)
    distances.append(dist)

avg_dist = sum(distances) / len(distances) if distances else 0
max_dist = max(distances) if distances else 0
print(f"Avg distance: {avg_dist:.2f} (need < 15)")
print(f"Max distance: {max_dist:.2f} (need < 40)")

large_gaps = sum(1 for d in distances if d > 20)
print(f"Large gaps (>20): {large_gaps} (max allowed: {len(distances) * 0.2:.1f})")
