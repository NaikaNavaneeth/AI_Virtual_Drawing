#!/usr/bin/env python3
"""
FIX-31: Test that shapes detected as "square" can be repositioned
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data

print("=" * 70)
print("FIX-31: SQUARE REPOSITIONING TEST")
print("=" * 70)

# Create drawing state
ds = DrawingState(800, 600)

# Manually create a square shape (with corner offsets, like detection would register)
print("\nCreating square shapes like the detector would...")

shapes_to_test = [
    ("square", 300, 200),
    ("square", 500, 300),
    ("rectangle", 400, 400),
]

shape_ids = []
for shape_type, cx, cy in shapes_to_test:
    shape_data = create_shape_data(
        shape_type=shape_type,
        center_x=cx,
        center_y=cy,
        size=(100, 80),
        color=(255, 80, 0),
        thickness=2
    )
    
    # Add corner offsets (simulating fitted corners)
    if shape_type in ("square", "rectangle"):
        shape_data['corner_offsets'] = [
            (-50, -40),  # top-left
            (50, -40),   # top-right
            (50, 40),    # bottom-right
            (-50, 40),   # bottom-left
        ]
    
    shape_id = ds.shape_tracker.add_shape(shape_data)
    shape_ids.append(shape_id)
    print(f"  Added {shape_type} at ({cx}, {cy}), ID: {shape_id[:8]}...")

print(f"\n{len(shape_ids)} shapes registered in tracker")

# Draw initial shapes on canvas
for i, (shape_type, cx, cy) in enumerate(shapes_to_test):
    shape = ds.shape_tracker.shapes[i]
    if 'corner_offsets' in shape:
        corners = [(int(cx + ox), int(cy + oy)) for ox, oy in shape['corner_offsets']]
        import cv2
        corner_pts = np.array(corners, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(ds.canvas, [corner_pts], isClosed=True,
                      color=(255, 80, 0), thickness=2, lineType=cv2.LINE_AA)

print("\nBefore repositioning:")
print(f"  Canvas brightness: {np.mean(ds.canvas):.1f}")

# Test repositioning each shape
print("\nRepositioning shapes...")
for idx, new_pos in enumerate([(200, 250), (600, 450), (300, 500)]):
    old_pos = shapes_to_test[idx][1:3]
    shape = ds.shape_tracker.get_by_id(shape_ids[idx])
    shape_type = shape['type']
    
    print(f"\n  {shape_type}: {old_pos} -> {new_pos}")
    
    # Update position
    ds.shape_tracker.update_shape(shape_ids[idx], {'current_pos': new_pos})
    shape_updated = ds.shape_tracker.get_by_id(shape_ids[idx])
    
    # Get brightness before
    region_before = ds.canvas[
        int(new_pos[1]-50):int(new_pos[1]+50),
        int(new_pos[0]-50):int(new_pos[0]+50)]
    brightness_before = np.mean(region_before) if region_before.size > 0 else 0
    
    # Redraw
    ds.redraw_shape_at_position(shape_updated, old_pos)
    
    # Get brightness after
    region_after = ds.canvas[
        int(new_pos[1]-50):int(new_pos[1]+50),
        int(new_pos[0]-50):int(new_pos[0]+50)]
    brightness_after = np.mean(region_after) if region_after.size > 0 else 0
    
    print(f"    Brightness before: {brightness_before:.1f}, after: {brightness_after:.1f}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("If shapes appear at new positions with brightness > 50:")
print("  FIX-31 is working - squares and rectangles can be repositioned!")
print("\nCanvas brightness:", np.mean(ds.canvas))

try:
    import cv2
    cv2.imwrite(r"c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing\FIX31_test.png", ds.canvas)
    print("Result saved to FIX31_test.png")
except:
    pass
