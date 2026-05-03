#!/usr/bin/env python3
"""
Detailed pixel tracking to see if rough sketch canvas updates work
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

ds = DrawingState(800, 600)

# Draw a simple rough sketch
print("Creating rough sketch...")
x, y = 200, 200
for i in range(20):
    x += np.random.randint(-5, 5)
    y += np.random.randint(-5, 5)
    ds.draw_point(max(50, min(750, x)), max(50, min(550, y)))

canvas_drawn = ds.canvas.copy()
pixels_drawn = np.count_nonzero(canvas_drawn)
print(f"After drawing: {pixels_drawn} pixels")

# Find which pixels are non-zero
drawn_coords = np.where(np.any(canvas_drawn > 0, axis=2))
print(f"  Rough sketch region: y=[{drawn_coords[0].min()}, {drawn_coords[0].max()}], x=[{drawn_coords[1].min()}, {drawn_coords[1].max()}]")

# Snap the shape
print("\nSnapping...")
ds.try_snap_shape()

canvas_after_snap = ds.canvas.copy()
pixels_after_snap = np.count_nonzero(canvas_after_snap)
print(f"After snap: {pixels_after_snap} pixels")

shape = ds.shape_tracker.shapes[0] if ds.shape_tracker.shapes else None
if not shape:
    print("ERROR: No shape registered!")
    sys.exit(1)

print(f"Shape: type={shape['type']}, center={shape['current_pos']}, size={shape['size']}")

# Now try to move it
old_pos = shape['current_pos']
new_pos = (500, 350)

print(f"\nMoving shape from {old_pos} to {new_pos}...")

# Update tracker
ds.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos, 'center': new_pos})
updated_shape = ds.shape_tracker.get_by_id(shape['id'])

# Redraw
print("Calling redraw_shape_at_position()...")
ds.redraw_shape_at_position(updated_shape, old_pos)

canvas_after_move = ds.canvas.copy()
pixels_after_move = np.count_nonzero(canvas_after_move)
print(f"After redraw: {pixels_after_move} pixels")

# Analyze what happened
print(f"\nCanvas pixel analysis:")
print(f"  Before move: {pixels_after_snap}")
print(f"  After move:  {pixels_after_move}")
print(f"  Difference:  {pixels_after_move - pixels_after_snap}")

# Find non-zero regions
non_zero_after = np.where(np.any(canvas_after_move > 0, axis=2))
if len(non_zero_after[0]) > 0:
    print(f"  New pixels region: y=[{non_zero_after[0].min()}, {non_zero_after[0].max()}], x=[{non_zero_after[1].min()}, {non_zero_after[1].max()}]")
else:
    print(f"  ERROR: No pixels on canvas after move!")

# Check if old position was erased
old_region_y_min = max(0, old_pos[1] - 50)
old_region_y_max = min(600, old_pos[1] + 50)
old_region_x_min = max(0, old_pos[0] - 50)
old_region_x_max = min(800, old_pos[0] + 50)

old_region = canvas_after_move[old_region_y_min:old_region_y_max, old_region_x_min:old_region_x_max]
pixels_in_old_region = np.count_nonzero(old_region)

print(f"\nOld position region check:")
print(f"  Region: x=[{old_region_x_min}, {old_region_x_max}], y=[{old_region_y_min}, {old_region_y_max}]")
print(f"  Pixels in old region: {pixels_in_old_region}")
if pixels_in_old_region > 0:
    print(f"  WARNING: Old sketch NOT properly erased!")

print("\n" + "=" * 80)
