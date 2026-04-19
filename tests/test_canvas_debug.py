#!/usr/bin/env python3
"""
Debug test: Check canvas properties and drawing
"""

import sys
import numpy as np
import cv2
sys.path.insert(0, r'c:\Users\naika\Downloads\AI_Virtual_Drawing\ai_drawing')

from modules.drawing_2d import DrawingState

print("Canvas Debug Test")
print("=" * 60)

h, w = 600, 800
ds = DrawingState(w, h)  # constructor signature is (w, h)

print(f"Canvas shape: {ds.canvas.shape}")
print(f"Canvas dtype: {ds.canvas.dtype}")
print(f"Canvas initial brightness: {np.mean(ds.canvas):.1f}")

# Manually draw a rectangle using cv2
# Using BGR format: blue=(255,0,0), green=(0,255,0), red=(0,0,255)
corners = [(100, 100), (200, 100), (200, 200), (100, 200)]
corner_pts = np.array(corners, dtype=np.int32).reshape((-1, 1, 2))

print(f"\nDrawing rectangle with green color (0, 255, 0) using cv2.polylines")
cv2.polylines(ds.canvas, [corner_pts], isClosed=True,
              color=(0, 255, 0), thickness=2, lineType=cv2.LINE_AA)

print(f"After drawing, canvas brightness: {np.mean(ds.canvas):.1f}")

# Check the specific region
region = ds.canvas[80:220, 80:220]
print(f"Region brightness: {np.mean(region):.1f}")

# Check a specific corner pixel
print(f"\nPixel at (100, 100): {ds.canvas[100, 100]}")
print(f"Pixel at (150, 100): {ds.canvas[100, 150]}")
print(f"Pixel at (150, 150): {ds.canvas[150, 150]}")

# Try drawing with white instead
white_corners = [(300, 300), (400, 300), (400, 400), (300, 400)]
white_pts = np.array(white_corners, dtype=np.int32).reshape((-1, 1, 2))

print(f"\nDrawing rectangle with white color (255, 255, 255) using cv2.polylines")
cv2.polylines(ds.canvas, [white_pts], isClosed=True,
              color=(255, 255, 255), thickness=2, lineType=cv2.LINE_AA)

print(f"After drawing white, canvas brightness: {np.mean(ds.canvas):.1f}")

# Check the white region
region = ds.canvas[280:420, 280:420]
print(f"White region brightness: {np.mean(region):.1f}")

print(f"\nPixel at (300, 300): {ds.canvas[300, 300]}")
print(f"Pixel at (350, 300): {ds.canvas[300, 350]}")
print(f"Pixel at (350, 350): {ds.canvas[350, 350]}")
