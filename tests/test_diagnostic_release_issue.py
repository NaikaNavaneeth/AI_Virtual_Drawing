#!/usr/bin/env python
"""
Diagnostic test to reproduce the shape release issue:
- Draw a shape
- Move it to new position (simulating thumbs_up)
- Release it (simulating palm open → rebuild)
- Check if shape appears at new position
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data, MovementController
import numpy as np
import cv2

def canvas_has_pixels_at_position(canvas, x, y, radius=30):
    """Check if canvas has pixels around a position"""
    y1 = max(0, y - radius)
    y2 = min(canvas.shape[0], y + radius)
    x1 = max(0, x - radius)
    x2 = min(canvas.shape[1], x + radius)
    
    region = canvas[y1:y2, x1:x2]
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    return np.any(gray > 10)

def test_shape_movement_and_release():
    """Simulate: create → move → release → check result"""
    print("\n" + "="*70)
    print("DIAGNOSTIC TEST: Shape Movement and Release")
    print("="*70)
    
    state = DrawingState(800, 600)
    
    # Create a rectangle shape
    print("\n1. Creating rectangle shape at (150, 150)...")
    shape_data = create_shape_data(
        shape_type="rectangle",
        center_x=150,
        center_y=150,
        size=(100, 80),
        color=(0, 255, 0)
    )
    state.shape_tracker.add_shape(shape_data)
    shape_id = shape_data['id']
    
    # Draw initial shape on canvas
    shape = state.shape_tracker.get_by_id(shape_id)
    print(f"   ✓ Shape created: {shape['type']}")
    print(f"   ✓ Position in tracker: {shape['current_pos']}")
    
    # Verify it's on canvas
    if not canvas_has_pixels_at_position(state.canvas, 150, 150):
        print("   ✗ Warning: Shape not visible on canvas at creation point")
    else:
        print(f"   ✓ Shape visible at (150, 150)")
    
    # Simulate movement (what happens during thumbs_up)
    print("\n2. Simulating movement to (400, 400)...")
    old_pos = shape['current_pos']
    new_pos = (400, 400)
    
    # This is what happens during movement
    state.shape_tracker.update_shape(shape_id, {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape_id)
    
    print(f"   ✓ Position updated in tracker: {updated_shape['current_pos']}")
    
    # Call redraw (simulating continuous movement)
    state.redraw_shape_at_position(updated_shape, old_pos)
    print(f"   ✓ Called redraw_shape_at_position()")
    
    # Check canvas state after movement
    has_old = canvas_has_pixels_at_position(state.canvas, 150, 150)
    has_new = canvas_has_pixels_at_position(state.canvas, 400, 400)
    
    print(f"\n   After movement:")
    print(f"   - Old position (150,150): {'✓ cleared' if not has_old else '✗ still has pixels'}")
    print(f"   - New position (400,400): {'✓ has pixels' if has_new else '✗ no pixels'}")
    
    if not has_new:
        print("   ✗ ERROR: Shape not at new position after redraw!")
        return False
    
    # Now simulate release (palm open → rebuild)
    print("\n3. Simulating release (calling rebuild_all_shapes_on_canvas)...")
    
    # Get the shape state before rebuild
    shape_before_rebuild = state.shape_tracker.get_by_id(shape_id)
    print(f"   Shape position before rebuild: {shape_before_rebuild['current_pos']}")
    print(f"   Tracker has {len(state.shape_tracker.shapes)} shapes")
    
    # This is called when palm opens
    state.rebuild_all_shapes_on_canvas()
    print(f"   ✓ Called rebuild_all_shapes_on_canvas()")
    
    # Check canvas state after rebuild
    has_new_after = canvas_has_pixels_at_position(state.canvas, 400, 400)
    
    print(f"\n   After rebuild:")
    print(f"   - Position (400,400): {'✓ has pixels' if has_new_after else '✗ NO PIXELS - SHAPE DISAPPEARED!'}")
    
    if not has_new_after:
        print("\n   🔴 CRITICAL: Shape disappeared after rebuild!")
        print("   This matches the reported issue.")
        
        # Debug: Check what rebuild is actually drawing
        print("\n   DEBUG: Reconstructing rebuild logic manually...")
        state.canvas = np.zeros((state.h, state.w, 3), dtype=np.uint8)
        
        for s in state.shape_tracker.shapes:
            if not s:
                continue
            pos = s.get('current_pos', s.get('center', (0, 0)))
            w, h = s.get('size', (50, 50))
            stype = s.get('type', 'rectangle')
            color = s.get('color', state.color)
            thickness = s.get('thickness', state.thickness)
            nx, ny = int(pos[0]), int(pos[1])
            
            print(f"   Rebuilding {stype}:")
            print(f"     - Position in shape dict: {pos}")
            print(f"     - Drawing at: ({nx}, {ny})")
            
            if stype == "rectangle":
                cv2.rectangle(state.canvas,
                             (int(nx - w//2), int(ny - h//2)),
                             (int(nx + w//2), int(ny + h//2)),
                             color, thickness, lineType=cv2.LINE_AA)
                print(f"     - Drew rectangle")
        
        has_after_manual = canvas_has_pixels_at_position(state.canvas, 400, 400)
        print(f"\n   After manual rebuild: {'✓ has pixels' if has_after_manual else '✗ still missing'}")
        
        return False
    
    print("\n   ✓ Shape correctly repositioned after rebuild!")
    print("\n✅ TEST PASSED - Shape release working correctly")
    return True

def test_freehand_release():
    """Test freehand stroke release specifically"""
    print("\n" + "="*70)
    print("DIAGNOSTIC TEST: Freehand Stroke Release")
    print("="*70)
    
    state = DrawingState(800, 600)
    
    # Draw freehand
    print("\n1. Drawing freehand stroke...")
    import math
    for i in range(25):
        angle = (i / 25) * 2 * math.pi
        x = 150 + int(50 * math.cos(angle))
        y = 150 + int(50 * math.sin(angle))
        state.draw_point(x, y)
    
    state._register_freehand_stroke()
    shape = state.shape_tracker.get_most_recent()
    print(f"   ✓ Freehand registered at {shape['original_pos']}")
    
    # Move it
    print("\n2. Moving freehand to (450, 350)...")
    old_pos = shape['current_pos']
    new_pos = (450, 350)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    state.redraw_shape_at_position(updated_shape, old_pos)
    
    has_new = canvas_has_pixels_at_position(state.canvas, 450, 350)
    print(f"   ✓ Shape at new position: {has_new}")
    
    # Release
    print("\n3. Releasing (rebuild)...")
    state.rebuild_all_shapes_on_canvas()
    
    has_new_after = canvas_has_pixels_at_position(state.canvas, 450, 350)
    
    if not has_new_after:
        print("   ✗ FAILED: Freehand disappeared after rebuild!")
        return False
    
    print("   ✓ Freehand correctly at new position after rebuild")
    return True

if __name__ == "__main__":
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + " SHAPE RELEASE DIAGNOSTIC TEST ".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    test1 = test_shape_movement_and_release()
    test2 = test_freehand_release()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Rectangle release: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"Freehand release: {'✅ PASS' if test2 else '❌ FAIL'}")
    
    if test1 and test2:
        print("\n✅ All tests passed")
    else:
        print("\n❌ Some tests failed - issue reproduced")
    print("="*70 + "\n")
    
    sys.exit(0 if (test1 and test2) else 1)
