"""
utils/shape_mlp_ai.py - Shape detection using the trained MLP model.
"""
import numpy as np
import cv2
from typing import List, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.drawing_mlp import DrawingMLP
from utils.shape_ai import _bounding_box, _make_circle, _make_rectangle, _make_triangle, _make_line

IMG_SIZE = 28
CONFIDENCE_THRESHOLD = 0.80

# --- Singleton Classifier Instance ---
_classifier = None

def get_classifier():
    """Initializes and returns the singleton MLP classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = DrawingMLP()
        if not _classifier.load():
            print("[ShapeMLP] WARNING: Could not load the drawing MLP model. Shape snapping will not work.")
            _classifier = None
    return _classifier

def _preprocess_stroke(stroke_points: List[Tuple[int, int]], canvas_shape: Tuple[int, int]) -> Optional[np.ndarray]:
    """
    Takes a list of points from a stroke, extracts the ROI, and preprocesses
    it into a 28x28 image suitable for the MLP model.
    """
    if not stroke_points:
        return None

    # 1. Find bounding box
    x_min, y_min, x_max, y_max = _bounding_box(stroke_points)
    w = x_max - x_min
    h = y_max - y_min
    
    # Ensure we have a valid bounding box with positive dimensions
    # Add 1 to convert from differences to inclusive ranges
    w = max(w, 1)
    h = max(h, 1)

    # 2. Create a temporary canvas for the stroke
    stroke_canvas = np.zeros(canvas_shape[:2], dtype=np.uint8)
    pts = np.array(stroke_points, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(stroke_canvas, [pts], isClosed=False, color=255, thickness=3) # Use a consistent thickness

    # 3. Extract ROI and add padding to make it square
    # Ensure we don't go out of bounds and clamp to valid indices
    y_max_clamped = min(y_max + 1, canvas_shape[0])
    x_max_clamped = min(x_max + 1, canvas_shape[1])
    roi = stroke_canvas[y_min:y_max_clamped, x_min:x_max_clamped]
    
    # Safety check: ensure roi is not empty
    if roi.size == 0:
        return None
    
    # Adjust w and h based on actual roi dimensions
    h_actual, w_actual = roi.shape
    if h_actual == 0 or w_actual == 0:
        return None
    
    side = max(w_actual, h_actual)
    padded = np.zeros((side, side), dtype=np.uint8)
    
    pad_w = (side - w_actual) // 2
    pad_h = (side - h_actual) // 2
    
    padded[pad_h:pad_h+h_actual, pad_w:pad_w+w_actual] = roi

    # 4. Resize to IMG_SIZE x IMG_SIZE
    resized = cv2.resize(padded, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)

    return resized


def detect_and_snap_mlp(
    raw_pts: List[Tuple[int, int]],
    canvas_shape: Tuple[int, int]
) -> Tuple[Optional[str], Optional[List[Tuple[int, int]]]]:
    """
    Uses the trained MLP to classify a stroke and return a clean version.
    OPTIMIZED: Enhanced validation to reject malformed strokes early.
    """
    clf = get_classifier()
    
    # OPTIMIZED: Stricter minimum point count (was 5, now 20)
    if not clf or len(raw_pts) < 20:
        return None, None
    
    # OPTIMIZED: Validate aspect ratio (reject extreme ratios)
    x_min, y_min, x_max, y_max = _bounding_box(raw_pts)
    w = max(x_max - x_min, 1)
    h = max(y_max - y_min, 1)
    aspect = w / h if h > 0 else 1.0
    
    # Reject extreme aspect ratios (too elongated or too thin)
    if aspect > 5.0 or aspect < 0.2:
        return None, None  # Stroke is degenerate (line-like)

    # 1. Preprocess the stroke into a 28x28 image
    processed_image = _preprocess_stroke(raw_pts, canvas_shape)
    if processed_image is None:
        return None, None
        
    # 2. Get prediction from the model
    shape, confidence = clf.predict(processed_image)
    
    print(f"[ShapeMLP] Detected: {shape} (Confidence: {confidence:.2f})") # Debug print

    # 3. If confident, generate the clean shape
    if confidence < CONFIDENCE_THRESHOLD:
        return None, None

    # Use the original rule-based shape generators
    if shape == "circle":
        return "circle", _make_circle(raw_pts)
    elif shape == "square":
        # The model was trained on squares, but the old code has rectangle.
        # Let's be explicit.
        return "rectangle", _make_rectangle(raw_pts)
    elif shape == "triangle":
        return "triangle", _make_triangle(raw_pts)
    elif shape == "line":
        return "line", _make_line(raw_pts)

    return None, None
