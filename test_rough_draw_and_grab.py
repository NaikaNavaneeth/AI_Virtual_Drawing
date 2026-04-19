#!/usr/bin/env python3
"""
Test: Can rough shapes be drawn AND grabbed
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("=" * 80) 
print("TEST: Drawing rough sketch and grabbing it")
print("=" * 80)

ds = DrawingState(800, 600)

# Simulate drawing a rough sketch in real-time
print("\n[1] Simulating real-time drawing (using draw_point)...")
rough_path = []
x, y = 200, 200
for i in range(50):
    x_new = x + np.random.randint(-8, 8)
    y_new = y + np.random.randint(-8, 8)
    x_new = max(50, min(750, x_new))
    y_new = max(50, min(550, y_new))
   
    # Use draw_point like the real app does
    ds.draw_point(x_new, y_new)
    rough_path.append((x_new, y_new))
    x, y = x_new, y_new

print(f"  Drew {len(rough_path)} points")
print(f"  current_stroke now has: {len(ds.current_stroke)} points")
print(f"  _stroke_buf_for_smooth now has: {len(ds._stroke_buf_for_smooth)} points")

# Check canvas BEFORE snapping
print(f"\n[2] Canvas before snapping:")
non_zero_before = np.count_nonzero(ds.canvas)
print(f"  Non-zero pixels: {non_zero_before}")

# Snap the shape
print(f"\n[3] Calling try_snap_shape()...")
ds.try_snap_shape(collab_client=None)

# Check canvas AFTER snapping  
print(f"\n[4] Canvas after snapping:")
non_zero_after = np.count_nonzero(ds.canvas)
print(f"  Non-zero pixels: {non_zero_after}")

# Check tracker
print(f"\n[5] Shape tracker:")
print(f"  Shapes registered: {len(ds.shape_tracker.shapes)}")

if ds.shape_tracker.shapes:
    shape = ds.shape_tracker.shapes[0]
    print(f"  Shape type: {shape.get('type')}")
    print(f"  Shape center: {shape.get('center')}")
    print(f"  Shape size: {shape.get('size')}")
    
    # Try to grab it
    print(f"\n[6] Testing grab at hand position (210, 205)...")
    grabbed = ds.shape_tracker.get_nearest(210, 205, radius=120)
    
    if grabbed:
        print(f"  SUCCESS: Shape is grabbable!")
        print(f"    Found: {grabbed.get('type')} at {grabbed.get('center')}")
    else:
        print(f"  FAILED: Shape is NOT grabbable!")
    
    # Try to move it
    if grabbed:
        print(f"\n[7] Testing shape movement...")
        old_pos = grabbed['current_pos']
        new_pos = (400, 300)
        
        print(f"  Moving from {old_pos} to {new_pos}...")
        
        # Update position
        ds.shape_tracker.update_shape(grabbed['id'], {'current_pos': new_pos, 'center': new_pos})
        updated = ds.shape_tracker.get_by_id(grabbed['id'])
        
        try:
            # Redraw at new position
            ds.redraw_shape_at_position(updated, old_pos)
            print(f"  SUCCESS: Shape repositioned!")
            
            non_zero_after_move = np.count_nonzero(ds.canvas)
            print(f"  Canvas pixels after move: {non_zero_after_move}")
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()

else:
    print("  ERROR: No shape registered!")

print("\n" + "=" * 80)
