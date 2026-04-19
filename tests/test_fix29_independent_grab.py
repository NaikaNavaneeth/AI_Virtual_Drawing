#!/usr/bin/env python3
"""
FIX-29: Test that all shapes with correct centers can be grabbed.
Places each shape at different positions to verify independent grabbing.
"""

import sys
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.sketch_position_control import ShapeTracker, create_shape_data

print("=" * 70)
print("FIX-29: Independent Shape Grabbing Test")
print("=" * 70)

# Create a shape tracker
tracker = ShapeTracker()
grab_radius = 120

# Place each shape at different positions
shapes_with_positions = [
    ("circle", 200, 200),      
    ("rectangle", 400, 200),   
    ("triangle", 600, 200),    
    ("line", 200, 400),        
    ("freehand", 400, 400),    
]

print("\n🔸 Creating shapes at different positions...")
for shape_type, cx, cy in shapes_with_positions:
    shape_data = create_shape_data(
        shape_type=shape_type,
        center_x=cx,
        center_y=cy,
        size=(80, 60),
        color=(0, 255, 0),
        thickness=2
    )
    shape_id = tracker.add_shape(shape_data)
    print(f"  ✓ {shape_type:10s} at ({cx:3d}, {cy:3d}), ID: {shape_id[:8]}...")

print(f"\n🔸 Testing grab-by-proximity for each shape...")
print(f"  (Moving hand to each shape's position)\n")

test_results = []
for shape_type, cx, cy in shapes_with_positions:
    # Simulate hand moving to this shape's position
    nearest = tracker.get_nearest(cx, cy, radius=grab_radius)
    
    if nearest:
        correct = nearest['type'] == shape_type
        status = "✓ CORRECT" if correct else "❌ WRONG"
        print(f"  Hand at ({cx:3d}, {cy:3d}) → Grabbed: {nearest['type']:10s} {status}")
        test_results.append((shape_type, correct))
    else:
        print(f"  Hand at ({cx:3d}, {cy:3d}) → ❌ NO SHAPE FOUND!")
        test_results.append((shape_type, False))

print("\n" + "=" * 70)
print("FIX-29 VALIDATION")
print("=" * 70)

all_pass = all(result for _, result in test_results)

if all_pass:
    print("✅ SUCCESS: All shapes are now grabable!")
    print("\nBefore FIX-29:")
    print("  ❌ Only circles could be grabbed")
    print("  ❌ Rectangles couldn't be found (wrong center)")
    print("  ❌ Triangles couldn't be found (wrong center)")
    print("  ❌ Lines couldn't be found (wrong center)")
    print("  ❌ Freehand couldn't be found (wrong center)")
    print("\nAfter FIX-29:")
    print("  ✅ All shapes have correct center positions")
    print("  ✅ All shapes can be grabbed independently")
    print("  ✅ Gesture repositioning should now work for all shapes!")
else:
    print("❌ FAILED: Some shapes still can't be grabbed")
    for shape_type, passed in test_results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"  {shape_type:10s}: {status}")
