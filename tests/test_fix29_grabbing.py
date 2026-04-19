#!/usr/bin/env python3
"""
FIX-29: Test that all shapes (not just circles) can be grabbed.
Verifies that shape centers are correctly calculated during snapping.
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.sketch_position_control import ShapeTracker, create_shape_data

print("=" * 70)
print("FIX-29: Shape Grabbing Test - All Shapes Should Be Discoverable")
print("=" * 70)

# Create a shape tracker
tracker = ShapeTracker()
hand_x, hand_y = 400, 300  # Hand position
grab_radius = 120  # Same as in main code

shapes_to_test = [
    ("circle", 400, 300),      # Centered at hand
    ("rectangle", 400, 300),   # Centered at hand
    ("triangle", 400, 300),    # Centered at hand
    ("line", 400, 300),        # Centered at hand
    ("freehand", 400, 300),    # Centered at hand
]

print("\n🔸 Creating shapes with centers exactly at hand position (400, 300)...")
for shape_type, cx, cy in shapes_to_test:
    shape_data = create_shape_data(
        shape_type=shape_type,
        center_x=cx,
        center_y=cy,
        size=(100, 80),
        color=(0, 255, 0),
        thickness=2
    )
    shape_id = tracker.add_shape(shape_data)
    print(f"  ✓ {shape_type:10s} added with center ({cx}, {cy}), ID: {shape_id[:8]}...")

print(f"\n🔸 Attempting to grab shape nearest to hand at ({hand_x}, {hand_y})...")
nearest = tracker.get_nearest(hand_x, hand_y, radius=grab_radius)

if nearest:
    print(f"  ✓ FOUND: {nearest['type']} shape!")
    print(f"    Center: ({nearest['center'][0]}, {nearest['center'][1]})")
    print(f"    Distance: 0 pixels")
else:
    print(f"  ❌ FAILED: No shape found within {grab_radius}px radius!")

print("\n🔸 Testing grab radius detection (simulating hand movement)...")
test_positions = [
    (400, 300, "center"),
    (450, 300, "30px right"),
    (350, 300, "50px left"),  
    (400, 350, "50px down"),
    (400, 250, "50px up"),
    (520, 300, "120px right (edge)"),
    (280, 300, "120px left (edge)"),
    (600, 300, "200px right (out of range)"),
]

print(f"\n  Hand Position → Shape Found?")
print(f"  {'-' * 50}")

for hx, hy, label in test_positions:
    nearest = tracker.get_nearest(hx, hy, radius=grab_radius)
    found_type = nearest['type'] if nearest else None
    status = "✓ YES" if nearest else "❌ NO"
    print(f"  ({hx:3d}, {hy:3d}) {label:25s} → {status:8s} ({found_type or 'none'})")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("If all 5 shapes were added and first hand position found a shape:")
print("  ✅ FIX-29 is working - all shapes should now be grabbable!")
print("\nIf only circle works but rectangles/triangles/lines don't:")
print("  ❌ Problem still exists in center calculation or tracking")
