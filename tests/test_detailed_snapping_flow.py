#!/usr/bin/env python
"""
Detailed diagnostic to trace shape through complete lifecycle
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data
import numpy as np
import cv2

def print_shape_info(label, state, shape_id):
    """Print detailed info about a shape"""
    shape = state.shape_tracker.get_by_id(shape_id)
    if not shape:
        print(f"{label}: Shape NOT in tracker!")
        return
    
    print(f"{label}:")
    print(f"  ID: {shape['id']}")
    print(f"  Type: {shape['type']}")
    print(f"  Center/Pos: {shape.get('center')}")
    print(f"  Current_pos: {shape.get('current_pos')}")
    print(f"  Original_pos: {shape.get('original_pos')}")
    print(f"  Size: {shape.get('size')}")
    print(f"  Color: {shape.get('color')}")
    print(f"  Thickness: {shape.get('thickness')}")
    print(f"  Moved: {shape.get('moved')}")

def test_complete_snapping_flow():
    """Test snapping instead of manual creation"""
    print("\n" + "="*70)
    print("TEST: Complete Snapping Flow (like real app)")
    print("="*70)
    
    state = DrawingState(800, 600)
    
    # Simulate snapping a rectangle by manually calling the snap logic
    print("\n1. Simulating '   rectangle' snap...")
    
    # First, "draw" a rectangle shape
    # Manually prepare as if try_snap_shape called _apply_shape_snap
    center_x, center_y = 150, 150
    w_orig, h_orig = 100, 80
    
    # Draw the snapped rectangle on canvas (like _apply_shape_snap does)
    snap_thickness = 2
    cv2.rectangle(state.canvas,
                 (int(center_x - w_orig//2), int(center_y - h_orig//2)),
                 (int(center_x + w_orig//2), int(center_y + h_orig//2)),
                 state.color, snap_thickness, lineType=cv2.LINE_AA)
    
    # Create shape data (like try_snap_shape does)
    shape_data = create_shape_data(
        shape_type="rectangle",
        center_x=center_x,
        center_y=center_y,
        size=(w_orig, h_orig),
        color=state.color,
        thickness=state.thickness
    )
    
    # Add to tracker (like try_snap_shape does)
    state.shape_tracker.add_shape(shape_data)
    
    shape_id = shape_data['id']
    print(f"   ✓ Shape snapped and added to tracker")
    print_shape_info("   After snap", state, shape_id)
    
    # Check canvas
    gray = cv2.cvtColor(state.canvas[100:200, 100:200], cv2.COLOR_BGR2GRAY)
    if np.any(gray > 10):
        print(f"   ✓ Shape visible on canvas at snap location")
    else:
        print(f"   ✗ Shape NOT visible on canvas!")
    
    # Now move it (like in main loop during thumbs_up)
    print("\n2. Moving to (400, 400)...")
    old_pos = shape_data['current_pos']
    new_pos = (400, 400)
    
    # Update tracker
    state.shape_tracker.update_shape(shape_id, {'current_pos': new_pos})
    print(f"   ✓ Updated tracker with new position")
    
    # Call redraw
    shape_to_redraw = state.shape_tracker.get_by_id(shape_id)
    state.redraw_shape_at_position(shape_to_redraw, old_pos)
    print(f"   ✓ Called redraw_shape_at_position()")
    
    # Check canvas
    gray_old = cv2.cvtColor(state.canvas[100:200, 100:200], cv2.COLOR_BGR2GRAY)
    gray_new = cv2.cvtColor(state.canvas[350:450, 350:450], cv2.COLOR_BGR2GRAY)
    
    print(f"   Old position cleared: {not np.any(gray_old > 10)}")
    print(f"   New position has pixels: {np.any(gray_new > 10)}")
    
    if not np.any(gray_new > 10):
        print("   ✗ Shape not at new position!")
        return False
    
    # Now release (palm opens → rebuild)
    print("\n3. Releasing (rebuild_all_shapes_on_canvas)...")
    
    print_shape_info("   Before rebuild", state, shape_id)
    
    # Check tracker still has shape
    tracker_shapes = state.shape_tracker.get_all_shapes()
    print(f"   Shapes in tracker: {len(tracker_shapes)}")
    for i, s in enumerate(tracker_shapes):
        if s:
            print(f"     [{i}] {s['type']} at {s.get('current_pos')}")
    
    # Call rebuild
    print(f"   Calling rebuild...")
    state.rebuild_all_shapes_on_canvas()
    
    print_shape_info("   After rebuild", state, shape_id)
    
    # Check if shape is still in tracker
    shape_check = state.shape_tracker.get_by_id(shape_id)
    if not shape_check:
        print("   ✗ Shape DISAPPEARED from tracker!")
        return False
    
    # Check if shape is on canvas
    gray_after = cv2.cvtColor(state.canvas[350:450, 350:450], cv2.COLOR_BGR2GRAY)
    if not np.any(gray_after > 10):
        print("   ✗ Shape NOT on canvas after rebuild!")
        print("\n   DEBUG: Checking rebuild logic...")
        
        # Manual check
        pos = shape_check.get('current_pos')
        nx, ny = int(pos[0]), int(pos[1])
        w, h = shape_check.get('size', (50, 50))
        color = shape_check.get('color')
        thickness = shape_check.get('thickness')
        
        print(f"   Shape rect would be drawn at:")
        print(f"     Position: ({nx}, {ny})")
        print(f"     Corner 1: ({int(nx - w//2)}, {int(ny - h//2)})")
        print(f"     Corner 2: ({int(nx + w//2)}, {int(ny + h//2)})")
        print(f"     Color: {color}")
        print(f"     Thickness: {thickness}")
        
        return False
    
    print("   ✓ Shape correctly at new position after rebuild!")
    print("\n✅ Complete snapping flow test PASSED")
    return True

if __name__ == "__main__":
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + " DETAILED SHAPE LIFECYCLE DIAGNOSTIC ".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    result = test_complete_snapping_flow()
    
    print("\n" + "="*70)
    if result:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED - Issue reproduced")
    print("="*70 + "\n")
    
    sys.exit(0 if result else 1)
