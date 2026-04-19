#!/usr/bin/env python3
"""
Debug: Why aren't rough sketch shapes being DRAWN to the canvas?
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

ds = DrawingState(800, 600)

# Create rough sketch
print("Creating rough sketch...")
x, y = 200, 200
for i in range(30):
    x += np.random.randint(-10, 10)
    y += np.random.randint(-10, 10)
    ds.draw_point(max(50, min(750, x)), max(50, min(550, y)))

print(f"Drew stroke with {len(ds.current_stroke)} points")

# Check canvas before snap
canvas_before = ds.canvas.copy()
non_zero_before = np.count_nonzero(canvas_before)
print(f"Canvas before snap: {non_zero_before} pixels")

# Snap it
print("\nSnapping...")
ds.try_snap_shape()

# Check canvas after snap
canvas_after = ds.canvas.copy()
non_zero_after = np.count_nonzero(canvas_after)
print(f"Canvas after snap: {non_zero_after} pixels")

if len(ds.shape_tracker.shapes) == 0:
    print("ERROR: No shape registered!")
    sys.exit(1)

shape = ds.shape_tracker.shapes[0]
print(f"\nRegistered shape:")
print(f"  Type: {shape['type']}")
print(f"  Center: {shape['current_pos']}")
print(f"  Size: {shape['size']}")

if shape['type'] == 'freehand':
    stroke_points = shape.get('stroke_points', [])
    print(f"  Stroke relative points: {len(stroke_points)}")
    
    if stroke_points:
        print(f"    Sample point offsets: {stroke_points[:3]}")
        
        # Manually check what should be drawn
        cx, cy = shape['current_pos']
        print(f"\n  When drawn at ({cx}, {cy}), these pixels should be set:")
        
        sample_drawn = []
        for i in range(min(3, len(stroke_points)-1)):
            p1 = stroke_points[i]
            p2 = stroke_points[i+1]
            abs_p1 = (int(p1[0] + cx), int(p1[1] + cy))
            abs_p2 = (int(p2[0] + cx), int(p2[1] + cy))
            sample_drawn.append((abs_p1, abs_p2))
            print(f"    Line from {abs_p1} to {abs_p2}")
        
        # Check if those pixels are actually set in canvas
        print(f"\n  Checking if pixels are actually on canvas...")
        for (p1, p2) in sample_drawn:
            # Check if endpoints are on canvas
            x1, y1 = p1
            x2, y2 = p2
            
            if 0 <= x1 < 800 and 0 <= y1 < 600:
                pixel1 = canvas_after[y1, x1]
                is_set1 = np.any(pixel1 > 0)
                print(f"    {p1}: {pixel1} {'SET' if is_set1 else 'NOT SET'}")
            else:
                print(f"    {p1}: OUT OF BOUNDS")
            
            if 0 <= x2 < 800 and 0 <= y2 < 600:
                pixel2 = canvas_after[y2, x2]
                is_set2 = np.any(pixel2 > 0)
                print(f"    {p2}: {pixel2} {'SET' if is_set2 else 'NOT SET'}")
            else:
                print(f"    {p2}: OUT OF BOUNDS")

else:
    print(f"ERROR: Shape is type '{shape['type']}', expected 'freehand'")

print("\n" + "=" * 80)
print("SUMMARY: If pixels are NOT SET, the canvas drawing is broken!")
print("         If pixels ARE SET, reshape is broken but drawing works")
print("=" * 80)
