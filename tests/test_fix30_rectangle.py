#!/usr/bin/env python3
"""
FIX-30: Test rectangle repositioning with proper rectangle stroke
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 70)
print("RECTANGLE REPOSITIONING TEST - FIX-30")
print("=" * 70)

# Create canvas
h, w = 600, 800
ds = DrawingState(w, h)  # constructor signature is (w, h)

# Create a realistic rectangle stroke (like user would draw)
# Better rectangle: closed loop around the shape
print("\nCreating a more realistic rectangle stroke...")

# A 100x80 rectangle from (150, 150) to (250, 230)
stroke = []

# Top edge (left to right)
for x in range(150, 251, 5):
    stroke.append((x, 150))

# Right edge (top to bottom)  
for y in range(150, 231, 5):
    stroke.append((250, y))

# Bottom edge (right to left)
for x in range(250, 149, -5):
    stroke.append((x, 230))

# Left edge (bottom to top)
for y in range(230, 149, -5):
    stroke.append((150, y))

# Close the loop
stroke.append((150, 150))

print(f"  Stroke: {len(stroke)} points, forming closed rectangle")

# Add to drawing state
ds.current_stroke = stroke
ds._stroke_buf_for_smooth = stroke.copy()
ds.snap_active = True

print("\nBefore snapping:")
print(f"  Canvas brightness: {np.mean(ds.canvas):.1f}")
print(f"  Shapes in tracker: {len(ds.shape_tracker.shapes)}")

# Snap the stroke
ds.try_snap_shape(collab_client=None)

print("\nAfter snapping:")
print(f"  Canvas brightness: {np.mean(ds.canvas):.1f}")
print(f"  Shapes in tracker: {len(ds.shape_tracker.shapes)}")

if not ds.shape_tracker.shapes:
    print("  ❌ No shape was registered!")
    sys.exit(1)

shape = ds.shape_tracker.shapes[0]
print(f"\nShape registered:")
print(f"  Type: {shape['type']}")
print(f"  Center: {shape['current_pos']}")
print(f"  Size: {shape['size']}")
print(f"  Has corner_offsets: {'corner_offsets' in shape}")

if 'corner_offsets' in shape:
    print(f"  Corner offsets: {shape['corner_offsets']}")

initial_center = shape['current_pos']

# Try to grab and move
print("\nGrabbing shape...")
grabbed = ds.shape_tracker.get_nearest(initial_center[0], initial_center[1], radius=120)

if not grabbed:
    print("  ❌ Failed to grab!")
    sys.exit(1)

print(f"  ✓ Grabbed: {grabbed['type']}")

# Now move it
old_pos = initial_center  
new_pos = (450, 350)

print(f"\nMoving shape from {old_pos} to {new_pos}...")

# Update position
ds.shape_tracker.update_shape(grabbed['id'], {'current_pos': new_pos})

# Get updated shape
shape_updated = ds.shape_tracker.get_by_id(grabbed['id'])

print(f"Before redraw: canvas brightness = {np.mean(ds.canvas):.1f}")

# Redraw at new position
ds.redraw_shape_at_position(shape_updated, old_pos)

print(f"After redraw: canvas brightness = {np.mean(ds.canvas):.1f}")

# Check regions
old_region = ds.canvas[
    int(old_pos[1]-60):int(old_pos[1]+60),
    int(old_pos[0]-60):int(old_pos[0]+60)]
old_brightness = np.mean(old_region) if old_region.size > 0 else 0

new_region = ds.canvas[
    int(new_pos[1]-60):int(new_pos[1]+60),
    int(new_pos[0]-60):int(new_pos[0]+60)]
new_brightness = np.mean(new_region) if new_region.size > 0 else 0

print(f"\nResult:")
print(f"  Old position brightness: {old_brightness:.1f}")
print(f"  New position brightness: {new_brightness:.1f}")

print("\n" + "=" * 70)
if new_brightness > 50 and old_brightness < 20:
    print("✅ SUCCESS: Rectangle moved correctly!")
    print("   - Old shape erased")
    print("   - New shape visible")
    print("\nFIX-30 is working!")
    
    # Save result
    try:
        cv2.imwrite(r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing\FIX30_result.png', ds.canvas)
        print("   - Canvas saved to FIX30_result.png")
    except:
        pass
else:
    print("❌ ISSUE: Repositioning failed")
    print(f"   New brightness: {new_brightness:.1f} (expected > 50)")
    print(f"   Old brightness: {old_brightness:.1f} (expected < 20)")
