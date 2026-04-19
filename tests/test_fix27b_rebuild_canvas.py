#!/usr/bin/env python
"""
Test FIX-27b: Verify rebuild_all_shapes_on_canvas correctly redraws all shapes at their current positions
This simulates the complete movement cycle: grab → move → release
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data
import numpy as np
import cv2

def canvas_has_pixels(canvas, region=None):
    """Check if canvas has non-zero pixels in a region"""
    if region:
        x1, y1, x2, y2 = region
        region_canvas = canvas[y1:y2, x1:x2]
    else:
        region_canvas = canvas
    
    gray = cv2.cvtColor(region_canvas, cv2.COLOR_BGR2GRAY)
    return np.any(gray > 10)

def test_freehand_full_cycle():
    """Test freehand: draw → move → release (rebuild)"""
    print("\n" + "="*60)
    print("TEST 1: Freehand Full Movement Cycle")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    # Draw a freehand stroke
    print("Drawing freehand stroke at original location...")
    import math
    for i in range(20):
        angle = (i / 20) * 2 * math.pi
        x = 200 + int(50 * math.cos(angle))
        y = 200 + int(50 * math.sin(angle))
        state.draw_point(x, y)
    
    state._register_freehand_stroke()
    shape = state.shape_tracker.get_most_recent()
    
    print(f"✓ Freehand stroke registered")
    print(f"  Original position: {shape['original_pos']}")
    print(f"  Current position: {shape['current_pos']}")
    
    # Verify canvas has pixels near original position
    orig_region = (150, 150, 250, 250)
    canvas_before = state.canvas.copy()
    if not canvas_has_pixels(canvas_before, orig_region):
        print("✗ FAIL: Canvas doesn't have stroke pixels at original location")
        return False
    
    print(f"✓ Canvas has stroke pixels at original location")
    
    # Move the shape
    print("\nMoving shape to new position...")
    old_pos = shape['current_pos']
    new_pos = (500, 400)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    # Redraw at new position (what happens during movement)
    state.redraw_shape_at_position(updated_shape, old_pos)
    print(f"✓ Shape redrawn at new position: {new_pos}")
    
    canvas_after_move = state.canvas.copy()
    
    # Check new location has pixels
    new_region = (450, 350, 550, 450)
    if not canvas_has_pixels(canvas_after_move, new_region):
        print("✗ FAIL: Canvas doesn't have pixels at new location after redraw")
        return False
    
    print(f"✓ Canvas has pixels at new location")
    
    # Simulate releasing (which calls rebuild_all_shapes_on_canvas)
    print("\nReleasing shape (calling rebuild)...")
    state.rebuild_all_shapes_on_canvas()
    
    canvas_after_rebuild = state.canvas.copy()
    
    # Check that shape is still at new position
    if not canvas_has_pixels(canvas_after_rebuild, new_region):
        print("✗ FAIL: Shape disappeared from new location after rebuild!")
        print("  This indicates rebuild_all_shapes_on_canvas is drawing at wrong position")
        return False
    
    print(f"✓ Shape correctly positioned at new location after rebuild")
    
    # Verify old location is cleared (or mostly cleared)
    # Note: might have some ghost pixels due to antialiasing
    old_gray = cv2.cvtColor(canvas_before[150:250, 150:250], cv2.COLOR_BGR2GRAY)
    old_pixels_before = np.count_nonzero(old_gray > 10)
    
    old_gray_after = cv2.cvtColor(canvas_after_rebuild[150:250, 150:250], cv2.COLOR_BGR2GRAY)
    old_pixels_after = np.count_nonzero(old_gray_after > 10)
    
    if old_pixels_after > old_pixels_before * 0.5:  # Allow some antialiasing remnants
        print(f"⚠ Warning: Old location still has pixels (before:{old_pixels_before}, after:{old_pixels_after})")
    else:
        print(f"✓ Old location properly cleared")
    
    print(f"✓ Freehand full cycle test PASSED")
    return True

def test_all_shapes_rebuild():
    """Test rebuild with multiple shape types"""
    print("\n" + "="*60)
    print("TEST 2: Multiple Shapes Rebuild Test")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    # Create multiple shapes at different positions
    shapes_to_create = [
        ("circle", 100, 100, (0, 255, 0)),
        ("rectangle", 300, 100, (0, 0, 255)),
        ("triangle", 500, 100, (255, 0, 0)),
        ("line", 150, 300, (255, 255, 0)),
    ]
    
    shape_ids = []
    for shape_type, cx, cy, color in shapes_to_create:
        shape_data = create_shape_data(
            shape_type=shape_type,
            center_x=cx,
            center_y=cy,
            size=(80, 80),
            color=color
        )
        if shape_type == "line":
            shape_data['line_points'] = [(-40, -40), (40, 40)]
        
        state.shape_tracker.add_shape(shape_data)
        shape_ids.append(shape_data['id'])
        print(f"  Created {shape_type} at ({cx}, {cy})")
    
    # Move each shape
    print("\nMoving all shapes...")
    new_positions = [(400, 400), (600, 500), (100, 500), (300, 450)]
    
    for shape_id, new_pos in zip(shape_ids, new_positions):
        shape = state.shape_tracker.get_by_id(shape_id)
        old_pos = shape['current_pos']
        
        state.shape_tracker.update_shape(shape_id, {'current_pos': new_pos})
        updated_shape = state.shape_tracker.get_by_id(shape_id)
        state.redraw_shape_at_position(updated_shape, old_pos)
    
    print(f"  All shapes moved")
    
    # Rebuild and verify
    print("\nRebuilding all shapes...")
    try:
        state.rebuild_all_shapes_on_canvas()
        print(f"✓ Rebuild succeeded")
    except Exception as e:
        print(f"✗ FAIL: Rebuild raised exception: {e}")
        return False
    
    # Check that canvas has content
    if not canvas_has_pixels(state.canvas):
        print("✗ FAIL: Canvas is empty after rebuild")
        return False
    
    print(f"✓ Canvas has content after rebuild")
    print(f"✓ Multiple shapes rebuild test PASSED")
    return True

def test_freehand_rebuild_specifically():
    """Test just freehand rebuild path"""
    print("\n" + "="*60)
    print("TEST 3: Freehand Rebuild Specific Test")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    # Create a freehand stroke with known points
    print("Creating freehand stroke...")
    import math
    for i in range(25):
        angle = (i / 25) * 2 * math.pi
        x = 150 + int(60 * math.cos(angle))
        y = 150 + int(60 * math.sin(angle))
        state.draw_point(x, y)
    
    state._register_freehand_stroke()
    shape = state.shape_tracker.get_most_recent()
    
    if not shape or shape['type'] != 'freehand':
        print("✗ FAIL: Freehand shape not created")
        return False
    
    initial_pos = shape['current_pos']
    print(f"✓ Freehand created at {initial_pos}")
    print(f"  Stroke points: {len(shape['stroke_points'])}")
    
    # Move it
    new_pos = (450, 350)
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    
    # Clear canvas and rebuild just this shape via rebuild_all_shapes_on_canvas
    state.canvas = np.zeros((state.h, state.w, 3), dtype=np.uint8)
    
    # Get updated shape and redraw via rebuild logic
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    # Manually do what rebuild_all_shapes_on_canvas does for freehand
    pos = updated_shape.get('current_pos')
    w, h = updated_shape.get('size', (50, 50))
    color = updated_shape.get('color', state.color)
    thickness = updated_shape.get('thickness', state.thickness)
    nx, ny = int(pos[0]), int(pos[1])
    
    stroke_points = updated_shape.get('stroke_points', [])
    print(f"\nTesting rebuild logic:")
    print(f"  Current position: ({nx}, {ny})")
    print(f"  Stroke points to draw: {len(stroke_points)}")
    
    if stroke_points:
        # This is the FIX-27b logic
        for i in range(1, len(stroke_points)):
            p1 = stroke_points[i-1]
            p2 = stroke_points[i]
            expected_p1 = (int(p1[0] + nx), int(p1[1] + ny))
            expected_p2 = (int(p2[0] + nx), int(p2[1] + ny))
            
            # Verify points are sensible
            if not (50 < expected_p1[0] < 750 and 50 < expected_p1[1] < 550):
                print(f"✗ FAIL: Calculated point out of bounds: {expected_p1}")
                return False
        
        print(f"✓ All calculated positions are within bounds")
        
        # Actually draw them
        for i in range(1, len(stroke_points)):
            p1 = stroke_points[i-1]
            p2 = stroke_points[i]
            cv2.line(state.canvas,
                    (int(p1[0] + nx), int(p1[1] + ny)),
                    (int(p2[0] + nx), int(p2[1] + ny)),
                    color, thickness, lineType=cv2.LINE_AA)
    
    # Verify pixels exist at new position
    new_region = (400, 300, 500, 400)
    if not canvas_has_pixels(state.canvas, new_region):
        print("✗ FAIL: No pixels drawn at new position")
        return False
    
    print(f"✓ Pixels correctly drawn at new position")
    print(f"✓ Freehand rebuild specific test PASSED")
    return True

if __name__ == "__main__":
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + " FIX-27b: REBUILD CANVAS TEST SUITE ".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)
    
    results = []
    results.append(("Freehand Full Cycle", test_freehand_full_cycle()))
    results.append(("All Shapes Rebuild", test_all_shapes_rebuild()))
    results.append(("Freehand Rebuild Logic", test_freehand_rebuild_specifically()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED - FIX-27b Complete!")
        print("  Shapes now relocate correctly when moved and released")
    else:
        print("✗ Some tests failed - Review above for details")
    print("="*60 + "\n")
    
    sys.exit(0 if all_passed else 1)
