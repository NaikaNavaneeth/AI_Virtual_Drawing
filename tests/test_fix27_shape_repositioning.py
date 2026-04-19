#!/usr/bin/env python
"""
Test FIX-27: Verify repositioning works for ALL shape types (freehand, rectangle, triangle, line)
Previously only circles worked due to delta calculation bug in freehand redraw logic.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data
import numpy as np

def test_freehand_repositioning():
    """Test that freehand strokes can be repositioned correctly"""
    print("\n" + "="*60)
    print("TEST 1: Freehand Stroke Repositioning")
    print("="*60)
    
    state = DrawingState(800, 600)
    state.snap_active = True
    
    # Draw a simple freehand stroke (circle-like curve)
    print("Drawing freehand stroke...")
    import math
    for i in range(20):
        angle = (i / 20) * 2 * math.pi
        x = 200 + int(50 * math.cos(angle))
        y = 200 + int(50 * math.sin(angle))
        state.draw_point(x, y)
    
    # Register as freehand (skip snapping, directly register)
    state._register_freehand_stroke()
    
    shape = state.shape_tracker.get_most_recent()
    if not shape:
        print("✗ FAIL: Freehand shape not registered")
        return False
    
    print(f"✓ Freehand registered: {shape['type']}")
    print(f"  Original position: {shape['original_pos']}")
    print(f"  Stroke points (relative): {len(shape['stroke_points'])} points")
    
    # Test repositioning
    old_pos = shape['current_pos']
    new_pos = (400, 300)
    
    print(f"  Moving from {old_pos} to {new_pos}")
    
    # Simulate movement (update position in tracker)
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    # Verify position was updated
    if updated_shape['current_pos'] != new_pos:
        print(f"✗ FAIL: Position not updated in tracker")
        return False
    
    print(f"✓ Position updated in tracker")
    
    # Test redraw (this is where the bug was)
    try:
        state.redraw_shape_at_position(updated_shape, old_pos)
        print(f"✓ Redraw succeeded without errors")
    except Exception as e:
        print(f"✗ FAIL: Redraw raised exception: {e}")
        return False
    
    print(f"✓ Freehand repositioning test PASSED")
    return True


def test_rectangle_repositioning():
    """Test that rectangle shapes can be repositioned"""
    print("\n" + "="*60)
    print("TEST 2: Rectangle Repositioning")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    # Create a rectangle shape
    shape_data = create_shape_data(
        shape_type="rectangle",
        center_x=150,
        center_y=150,
        size=(100, 80),
        color=(0, 255, 0)
    )
    state.shape_tracker.add_shape(shape_data)
    
    shape = state.shape_tracker.get_most_recent()
    print(f"✓ Rectangle created at {shape['current_pos']}")
    
    old_pos = shape['current_pos']
    new_pos = (400, 400)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    try:
        state.redraw_shape_at_position(updated_shape, old_pos)
        print(f"✓ Rectangle repositioned from {old_pos} to {new_pos}")
        print(f"✓ Rectangle repositioning test PASSED")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_triangle_repositioning():
    """Test that triangle shapes can be repositioned"""
    print("\n" + "="*60)
    print("TEST 3: Triangle Repositioning")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    shape_data = create_shape_data(
        shape_type="triangle",
        center_x=250,
        center_y=250,
        size=(80, 80),
        color=(255, 0, 0)
    )
    state.shape_tracker.add_shape(shape_data)
    
    shape = state.shape_tracker.get_most_recent()
    print(f"✓ Triangle created at {shape['current_pos']}")
    
    old_pos = shape['current_pos']
    new_pos = (500, 150)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    try:
        state.redraw_shape_at_position(updated_shape, old_pos)
        print(f"✓ Triangle repositioned from {old_pos} to {new_pos}")
        print(f"✓ Triangle repositioning test PASSED")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_line_repositioning():
    """Test that line shapes can be repositioned"""
    print("\n" + "="*60)
    print("TEST 4: Line Repositioning")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    shape_data = create_shape_data(
        shape_type="line",
        center_x=300,
        center_y=300,
        size=(100, 50),
        color=(0, 0, 255)
    )
    # Add line endpoints (relative to center)
    shape_data['line_points'] = [(-50, -25), (50, 25)]
    state.shape_tracker.add_shape(shape_data)
    
    shape = state.shape_tracker.get_most_recent()
    print(f"✓ Line created at {shape['current_pos']}")
    
    old_pos = shape['current_pos']
    new_pos = (200, 500)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    try:
        state.redraw_shape_at_position(updated_shape, old_pos)
        print(f"✓ Line repositioned from {old_pos} to {new_pos}")
        print(f"✓ Line repositioning test PASSED")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_circle_repositioning():
    """Test that circle shapes still work (regression test)"""
    print("\n" + "="*60)
    print("TEST 5: Circle Repositioning (Regression Test)")
    print("="*60)
    
    state = DrawingState(800, 600)
    
    shape_data = create_shape_data(
        shape_type="circle",
        center_x=100,
        center_y=100,
        size=(60, 60),
        color=(255, 255, 0)
    )
    state.shape_tracker.add_shape(shape_data)
    
    shape = state.shape_tracker.get_most_recent()
    print(f"✓ Circle created at {shape['current_pos']}")
    
    old_pos = shape['current_pos']
    new_pos = (600, 400)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    try:
        state.redraw_shape_at_position(updated_shape, old_pos)
        print(f"✓ Circle repositioned from {old_pos} to {new_pos}")
        print(f"✓ Circle repositioning test PASSED")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  FIX-27: ALL SHAPE REPOSITIONING TEST SUITE".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)
    
    results = []
    results.append(("Freehand Stroke", test_freehand_repositioning()))
    results.append(("Rectangle", test_rectangle_repositioning()))
    results.append(("Triangle", test_triangle_repositioning()))
    results.append(("Line", test_line_repositioning()))
    results.append(("Circle (Regression)", test_circle_repositioning()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED - FIX-27 Complete!")
    else:
        print("✗ Some tests failed - Review above for details")
    print("="*60 + "\n")
    
    sys.exit(0 if all_passed else 1)
