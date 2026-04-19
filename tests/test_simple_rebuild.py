#!/usr/bin/env python
"""Simple test to verify rebuild works with tracker state"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.drawing_2d import DrawingState
from modules.sketch_position_control import create_shape_data
import cv2
import numpy as np

state = DrawingState(800, 600)

# Create shape
shape_data = create_shape_data(
    shape_type="rectangle",
    center_x=150,
    center_y=150,
    size=(100, 80),
    color=(0, 255, 0)
)
state.shape_tracker.add_shape(shape_data)

# Draw it
cv2.rectangle(state.canvas,
             (100, 110),
             (200, 190),
             (0, 255, 0), 2)

shape = state.shape_tracker.get_by_id(shape_data['id'])
print(f"Initial: tracker has position {shape['current_pos']}")

# Update position (simulate movement)
state.shape_tracker.update_shape(shape_data['id'], {'current_pos': (400, 400)})

shape = state.shape_tracker.get_by_id(shape_data['id'])
print(f"After update: tracker has position {shape['current_pos']}")

# Redraw manually
old_pos = (150, 150)
shape_to_redraw = state.shape_tracker.get_by_id(shape_data['id'])
state.redraw_shape_at_position(shape_to_redraw, old_pos)

gray = cv2.cvtColor(state.canvas[350:450, 350:450], cv2.COLOR_BGR2GRAY)
print(f"After redraw: shape at (400,400)? {bool(np.any(gray > 10))}")

# Rebuild
state.rebuild_all_shapes_on_canvas()

gray = cv2.cvtColor(state.canvas[350:450, 350:450], cv2.COLOR_BGR2GRAY)
print(f"After rebuild: shape at (400,400)? {bool(np.any(gray > 10))}")

shape = state.shape_tracker.get_by_id(shape_data['id'])
print(f"After rebuild: tracker still has shape? {shape is not None}")
if shape:
    print(f"  Position: {shape['current_pos']}")
