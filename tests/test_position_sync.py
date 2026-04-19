#!/usr/bin/env python
"""
Test to verify tracker position is correctly synchronized during move/rebuild cycle
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data
import numpy as np
import cv2

def test_position_sync():
    print("\n" + "="*70)
    print("TEST: Position Synchronization During Movement")
    print("="*70)
    
    state = DrawingState(800, 600)
    
    # Create and draw a shape
    print("\n1. Creating shape at (150, 150)...")
    shape_data = create_shape_data(
        shape_type="rectangle",
        center_x=150,
        center_y=150,
        size=(100, 80),
        color=(0, 255, 0)
    )
    state.shape_tracker.add_shape(shape_data)
    shape_id = shape_data['id']
    
    # Draw it
    cv2.rectangle(state.canvas,
                 (int(150 - 50), int(150 - 40)),
                 (int(150 + 50), int(150 + 40)),
                 (0, 255, 0), 2, lineType=cv2.LINE_AA)
    
    shape = state.shape_tracker.get_by_id(shape_id)
    print(f"   Tracker position: {shape['current_pos']}")
    
    # Simulate grabbing the shape
    print("\n2. Simulating grab...")
    grab_pos = shape['current_pos']
   state.movement_controller.start_move(shape_id, grab_pos[0], grab_pos[1], grab_pos)
    print(f"   Movement controller initialized")
    
    # Simulate moving hand in multiple steps
    print("\n3. Simulating hand movement...")
    hand_positions = [
        (200, 200),  # Hand moves
        (250, 250),
        (300, 300),
        (350, 350),
        (400, 400),  # Final position
    ]
    
    for i, hand_pos in enumerate(hand_positions):
        # Calculate new position (as movement controller does)
        new_pos = state.movement_controller.calculate_new_position(hand_pos[0], hand_pos[1])
        
        print(f"   Step {i+1}: Hand at {hand_pos} → Shape to {new_pos}")
        
        # Update tracker (as main loop does)
        state.shape_tracker.update_shape(shape_id, {'current_pos': new_pos})
        
        # Redraw (as main loop does)
        shape_updated = state.shape_tracker.get_by_id(shape_id)
        if i == 0:
            old_pos_for_draw = grab_pos
        else:
            old_pos_for_draw = hand_positions[i-1]
        
        # Actually store old position properly
        if i == 0:
            old_pos_for_draw = grab_pos
        else:
            # Get position from previous iteration
            shape_before = state.shape_tracker.get_by_id(shape_id)
            # This is tricky - we need to know the OLD position
            # In real code, it's passed from before the update
        
    # At end, check what tracker has
    final_shape = state.shape_tracker.get_by_id(shape_id)
    print(f"\n4. After movement:")
    print(f"   Tracker position: {final_shape['current_pos']}")
    
    # Now rebuild
    print(f"\n5. Calling rebuild...")
    state.rebuild_all_shapes_on_canvas()
    
    # Check if shape appears
    gray = cv2.cvtColor(state.canvas[350:450, 350:450], cv2.COLOR_BGR2GRAY)
    if np.any(gray > 10):
        print(f"   ✓ Shape at (400, 400): Found")
    else:
        print(f"   ✗ Shape at (400, 400): NOT FOUND")
        
        # Debug
        shape_in_tracker = state.shape_tracker.get_by_id(shape_id)
        if shape_in_tracker:
            print(f"   Shape in tracker: Yes")
            print(f"   Position in tracker: {shape_in_tracker['current_pos']}")
        else:
            print(f"   Shape in tracker: NO!!!")

if __name__ == "__main__":
    test_position_sync()
