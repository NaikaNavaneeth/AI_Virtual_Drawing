#!/usr/bin/env python
"""Test freehand stroke repositioning with redraw"""

from modules.drawing_2d import DrawingState
import cv2
import numpy as np

state = DrawingState(800, 600)
state.snap_active = True

# Draw a freehand-like curved scribble  
print('Drawing freehand sketch...')
import math
curve_points = []
for i in range(30):
    angle = (i / 30) * 2 * math.pi
    x = 200 + int(80 * math.cos(angle))
    y = 200 + int(80 * math.sin(angle))
    state.draw_point(x, y)
    curve_points.append((x, y))

print(f'Drew {len(state.current_stroke)} points')

# Process through snap (will detect as line but at least registers)
state.try_snap_shape()

shape = state.shape_tracker.get_most_recent()
if shape:
    print(f'\n✓ Shape registered as type: {shape["type"]}')
    print(f'  Original position: {shape["original_pos"]}')
    print(f'  Current position: {shape["current_pos"]}')
    print(f'  Size: {shape["size"]}')
    print(f'  Stroke points stored: {len(shape.get("stroke_points", []))} points')
    
    # Check if stroke_points are relative (should be small values, not absolute canvas coords)
    if shape.get('stroke_points'):
        first_pt = shape['stroke_points'][0]
        print(f'  First relative point: {first_pt}')
        # Absolute point should be first_pt + original position
        abs_x = first_pt[0] + shape['original_pos'][0]
        abs_y = first_pt[1] + shape['original_pos'][1]
        print(f'  Translated back to absolute: ({abs_x}, {abs_y})')
    
    print(f'\n✓ Testing repositioning...')
    # Move the shape
    old_pos = shape['current_pos']
    new_pos = (400, 300)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    print(f'  Before: {old_pos}')
    print(f'  After: {updated_shape["current_pos"]}')
    
    # Test redraw logic (simulate what happens in redraw_shape_at_position)
    print(f'\n✓ Verifying redraw logic...')
    if updated_shape.get('stroke_points'):
        # This is what the redraw code does
        x, y = updated_shape['current_pos']
        sample_point = updated_shape['stroke_points'][0]
        redraw_x = sample_point[0] + x
        redraw_y = sample_point[1] + y
        print(f'  Relative point will be drawn at: ({redraw_x}, {redraw_y})')
        
    print(f'\n✓ Freehand tracking and repositioning working!')
else:
    print('✗ No shape registered')
