#!/usr/bin/env python3
"""
FIX-30: Direct test of rectangle repositioning with manual shape creation
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data

print("=" * 70)
print("FIX-30: RECTANGLE REPOSITIONING TEST (MANUAL SHAPE)")
print("=" * 70)

# Create canvas and drawing state
h, w = 600, 800
ds = DrawingState(w, h)  # constructor signature is (w, h)

# Manually create a rectangle shape with rotated corners
print("\nCreating a manual rectangle shape with corners...")

# Create a rectangle at (200, 200) with corners (rotated 30 degrees)
# For simplicity, create a normal rectangle first
shape_data = create_shape_data(
    shape_type='rectangle',
    center_x=200,
    center_y=200,
    size=(100, 80),
    color=(0, 255, 0),
    thickness=2
)

# Manually add corner offsets (simulating a fitted rectangle with rotation)
# For a 100x80 rectangle centered at origin, corners would be at:
# (-50, -40), (50, -40), (50, 40), (-50, 40)
shape_data['corner_offsets'] = [
    (-50, -40),  # top-left
    (50, -40),   # top-right
    (50, 40),    # bottom-right
    (-50, 40),   # bottom-left
]

shape_id = ds.shape_tracker.add_shape(shape_data)
print(f"  Shape added: {shape_id}")
print(f"  Center: {shape_data['current_pos']}")
print(f"  Corners: {shape_data['corner_offsets']}")

# Draw the rectangle manually on canvas for reference
nx, ny = 200, 200
corners_screen = [(int(nx + ox), int(ny + oy)) for ox, oy in shape_data['corner_offsets']]
corner_pts = np.array(corners_screen, dtype=np.int32).reshape((-1, 1, 2))
cv2.polylines(ds.canvas, [corner_pts], isClosed=True,
              color=(0, 255, 0), thickness=2, lineType=cv2.LINE_AA)

print("\nBefore repositioning:")
print(f"  Canvas brightness: {np.mean(ds.canvas):.1f}")

# Extract original region
orig_region = ds.canvas[
    int(ny-60):int(ny+60),
    int(nx-60):int(nx+60)]
orig_brightness = np.mean(orig_region) if orig_region.size > 0 else 0
print(f"  Original position brightness: {orig_brightness:.1f}")

# Now move the shape
old_pos = (200, 200)
new_pos = (450, 350)

print(f"\nMoving from {old_pos} to {new_pos}...")

# Update shape position in tracker
shape = ds.shape_tracker.get_by_id(shape_id)
ds.shape_tracker.update_shape(shape_id, {'current_pos': new_pos})

#  Get refreshed shape
shape_updated = ds.shape_tracker.get_by_id(shape_id)

# Redraw at new position
ds.redraw_shape_at_position(shape_updated, old_pos)

print("\nAfter repositioning:")
print(f"  Canvas brightness: {np.mean(ds.canvas):.1f}")

# Check new region
new_region = ds.canvas[
    int(new_pos[1]-60):int(new_pos[1]+60),
    int(new_pos[0]-60):int(new_pos[0]+60)]
new_brightness = np.mean(new_region) if new_region.size > 0 else 0
print(f"  New position brightness: {new_brightness:.1f}")

#  Check old region
old_region_after = ds.canvas[
    int(old_pos[1]-60):int(old_pos[1]+60),
    int(old_pos[0]-60):int(old_pos[0]+60)]
old_brightness_after = np.mean(old_region_after) if old_region_after.size > 0 else 0
print(f"  Old position brightness (after): {old_brightness_after:.1f}")

print("\n" + "=" * 70)
print("RESULT")
print("=" * 70)

if new_brightness > 50 and old_brightness_after < 20:
    print("SUCCESS: Rectangle moved with corners!")
    print("  - Old position erased")
    print("  - New position has rectangle drawn from stored corner offsets")
    
    try:
        cv2.imwrite(r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing\FIX30_test.png', ds.canvas)
        print("\nCanvas saved to FIX30_test.png")
    except Exception as e:
        print(f"Could not save: {e}")
else:
    print("ISSUE with repositioning:")
    print(f"  New brightness: {new_brightness:.1f} (expected > 50)")
    print(f"  Old cleaned up: {old_brightness_after:.1f} (expected < 20)")
