#!/usr/bin/env python
"""Debug freehand stroke buffer"""

from modules.drawing_2d import DrawingState

state = DrawingState(800, 600)
state.snap_active = True

# Draw a curved scribble (not a line or geometric shape)
print('Drawing curved scribble...')
import math
for i in range(50):
    angle = (i / 50) * 4 * math.pi
    x = 300 + int(100 * math.cos(angle + i*0.1))
    y = 300 + int(100 * math.sin(angle + i*0.1))
    state.draw_point(x, y)

print(f'current_stroke: {len(state.current_stroke)} points')
print(f'_stroke_buf_for_smooth: {len(state._stroke_buf_for_smooth)} points')

# Now try to register
print(f'\nCalling try_snap_shape()...')
state.try_snap_shape()

print(f'\nAfter try_snap_shape():')
print(f'Shapes in tracker: {len(state.shape_tracker.shapes)}')

if state.shape_tracker.shapes:
    shape = state.shape_tracker.get_most_recent()
    print(f'Shape type: {shape["type"]}')
    print(f'Shape original_pos: {shape["original_pos"]}')
    print(f'Shape size: {shape["size"]}')
else:
    print('No shape registered!')

