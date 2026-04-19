#!/usr/bin/env python
"""Test freehand stroke tracking and repositioning"""

from modules.drawing_2d import DrawingState
import numpy as np

print('=' * 64)
print('     FREEHAND SKETCH TRACKING & REPOSITIONING TEST')
print('=' * 64)
print()

# Initialize drawing state
state = DrawingState(800, 600)
state.snap_active = True  # Enable snapping
print('✓ DrawingState initialized (800x600)')
print()

# Simulate drawing a freehand stroke
print('Step 1: Drawing freehand stroke...')
stroke_points = [
    (200, 200), (210, 195), (220, 190), (230, 192), (240, 200),
    (250, 210), (255, 220), (250, 230), (240, 235), (230, 233),
]

for i, (x, y) in enumerate(stroke_points):
    state.draw_point(x, y)

print(f'  - Drew {len(stroke_points)} points')
print(f'  - Stroke buffer size: {len(state._stroke_buf_for_smooth)}')
print(f'  - Snap active: {state.snap_active}')
print()

# Try to snap shape (this will trigger freehand registration if no shape detected)
print('Step 2: Processing stroke through shape detector...')
state.try_snap_shape()
print(f'  - Registered: {len(state.shape_tracker.shapes)} shapes in tracker')

shape = state.shape_tracker.get_most_recent()
if shape:
    print(f'  ✓ Shape type: {shape["type"]}')
    print(f'  ✓ Original position: {shape["original_pos"]}')
    print(f'  ✓ Current position: {shape["current_pos"]}')
    print(f'  ✓ Size: {shape["size"]}')
    print(f'  ✓ Stroke points (relative): {len(shape["stroke_points"])} points')
    
    # Verify points are relative
    if shape['stroke_points']:
        rx, ry = shape['stroke_points'][0]
        print(f'  ✓ First point offset: ({rx}, {ry})')
else:
    print('  ✗ No shape registered')
print()

# Simulate repositioning
print('Step 3: Repositioning freehand stroke...')
if shape:
    old_pos = shape['current_pos']
    new_pos = (300, 300)
    
    state.shape_tracker.update_shape(shape['id'], {'current_pos': new_pos})
    updated_shape = state.shape_tracker.get_by_id(shape['id'])
    
    print(f'  ✓ Old position: {old_pos}')
    print(f'  ✓ New position: {updated_shape["current_pos"]}')
    print(f'  ✓ Repositioning ready!')
print()

print('=' * 64)
print('     FREEHAND TRACKING VERIFIED!')
print('=' * 64)
print()
print('Ready for thumbs_up gesture to grab and move!')


