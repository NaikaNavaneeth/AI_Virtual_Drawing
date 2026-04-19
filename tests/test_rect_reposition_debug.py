#!/usr/bin/env python3
"""
Debug test: Simulate rectangle repositioning flow
Trace: snap -> register -> grab -> move -> redraw
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import ShapeTracker

print("=" * 70)
print("RECTANGLE REPOSITIONING DEBUG TEST")
print("=" * 70)

# Create canvas
h, w = 600, 800
ds = DrawingState(w, h)  # constructor signature is (w, h)

print("\n🔸 STEP 1: Create a rough rectangle stroke...")
# Simulate user drawing a rectangle from (150, 150) to (250, 250)
stroke = [
    (150, 150), (160, 150), (170, 150), (180, 150), (190, 150), (200, 150),
    (210, 150), (220, 150), (230, 150), (240, 150), (250, 150),
    (250, 160), (250, 170), (250, 180), (250, 190), (250, 200),
    (250, 210), (250, 220), (250, 230), (250, 240), (250, 250),
    (240, 250), (230, 250), (220, 250), (210, 250), (200, 250),
    (190, 250), (180, 250), (170, 250), (160, 250), (150, 250),
    (150, 240), (150, 230), (150, 220), (150, 210), (150, 200),
    (150, 190), (150, 180), (150, 170), (150, 160), (150, 150),
]

print(f"  Stroke: {len(stroke)} points from ({stroke[0]}) to approx ({stroke[-1]})")

# Add stroke to drawing state
ds.current_stroke = stroke
ds._stroke_buf_for_smooth = stroke.copy()
ds.snap_active = True

print("\n🔸 STEP 2: Snap the rectangle...")
print("  Before snapping:")
print(f"    Canvas brightness: {np.mean(ds.canvas):.1f}")
print(f"    Shapes in tracker: {len(ds.shape_tracker.shapes)}")

# Call snap
ds.try_snap_shape(collab_client=None)

print("  After snapping:")
print(f"    Canvas brightness: {np.mean(ds.canvas):.1f}")
print(f"    Shapes in tracker: {len(ds.shape_tracker.shapes)}")

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[0]
    print(f"\n  Shape registered:")
    print(f"    Type: {shape['type']}")
    print(f"    Center: {shape['current_pos']}")
    print(f"    Size: {shape['size']}")
    print(f"    Color: {shape['color']}")
    initial_center = shape['current_pos']
    initial_size = shape['size']
else:
    print("  ❌ No shape registered!")
    sys.exit(1)

print("\n🔸 STEP 3: Try to grab the rectangle...")
grabbed_shape = ds.shape_tracker.get_nearest(initial_center[0], initial_center[1], radius=120)
if grabbed_shape:
    print(f"  ✓ Grabbed: {grabbed_shape['type']} at {grabbed_shape['current_pos']}")
else:
    print(f"  ❌ Failed to grab shape!")
    sys.exit(1)

print("\n🔸 STEP 4: Move the shape (simulate hand movement)...")
old_pos = initial_center
new_pos = (400, 300)
print(f"  Moving from {old_pos} to {new_pos}")

# Update shape position in tracker
ds.shape_tracker.update_shape(grabbed_shape['id'], {'current_pos': new_pos})

# Redraw at new position
print(f"  Before redraw:")
print(f"    Canvas brightness: {np.mean(ds.canvas):.1f}")

ds.redraw_shape_at_position(grabbed_shape, old_pos)

print(f"  After redraw:")
print(f"    Canvas brightness: {np.mean(ds.canvas):.1f}")

# Check if shape appears at new position
new_region = ds.canvas[int(new_pos[1]-60):int(new_pos[1]+60), int(new_pos[0]-60):int(new_pos[0]+60)]
new_brightness = np.mean(new_region)
print(f"    Region around new position brightness: {new_brightness:.1f}")

# Check if old shape is erased
old_region = ds.canvas[int(old_pos[1]-60):int(old_pos[1]+60), int(old_pos[0]-60):int(old_pos[0]+60)]
old_brightness = np.mean(old_region)
print(f"    Region around old position brightness: {old_brightness:.1f}")

print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)

if new_brightness > 50 and old_brightness < 20:
    print("✅ SUCCESS: Rectangle moved correctly!")
    print("   - Old position erased")
    print("   - New position has shape")
elif new_brightness > 50 and old_brightness > 50:
    print("⚠️  ISSUE: Shape at both old and new positions!")
    print("   - Old position not erased properly")
elif new_brightness < 20 and old_brightness < 20:
    print("❌ ISSUE: Shape disappeared!")
    print("   - Both old and new positions are empty")
else:
    print("❓ UNCLEAR: Mixed results")
    print(f"   - Old brightness: {old_brightness:.1f}")
    print(f"   - New brightness: {new_brightness:.1f}")

# Try to save for visual inspection
try:
    cv2.imwrite(r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing\debug_repositioning.png', ds.canvas)
    print(f"\n💾 Canvas saved to debug_repositioning.png for visual inspection")
except Exception as e:
    print(f"\n❌ Failed to save: {e}")
