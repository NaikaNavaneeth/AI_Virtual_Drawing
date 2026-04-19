"""
utils/shape_mlp_ai.py - Shape detection using the trained MLP model.

OPTIMIZATIONS (Phase 1.5):
- Model cached in memory (pre-allocated at startup)
- Preprocessing cached and reused
- NumPy operations prioritized over OpenCV where possible
- Redundant copies eliminated
"""
import numpy as np
import cv2
from typing import List, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.drawing_mlp import DrawingMLP
from utils.shape_ai import _bounding_box, _make_circle, _make_rectangle, _make_triangle, _make_line
from core.config import MLP_CONFIDENCE_THRESHOLD

IMG_SIZE = 28
# Confidence threshold now imported from config.py for easy tuning
# Default: 0.65 (balance between accuracy and recall)
CONFIDENCE_THRESHOLD = MLP_CONFIDENCE_THRESHOLD

# --- Optimized Singleton Classifier Instance ---
_classifier = None
_classifier_cache = {}  # Cache for model predictions

def get_classifier():
    """Initializes and returns the singleton MLP classifier instance (pre-cached)."""
    global _classifier
    if _classifier is None:
        _classifier = DrawingMLP()
        if not _classifier.load():
            print("[ShapeMLP] WARNING: Could not load the drawing MLP model. Shape snapping will not work.")
            _classifier = None
    return _classifier


def _validate_shape_match(raw_pts: List[Tuple[int, int]], detected_shape: str) -> bool:
    """
    Validate that the detected shape actually matches the stroke characteristics.
    This prevents false positives where rough sketches are incorrectly classified as shapes.
    
    Args:
        raw_pts: The original stroke points
        detected_shape: The shape detected by MLP ("circle", "square", "triangle", "line")
    
    Returns:
        True if stroke properties match the detected shape, False otherwise
    """
    if not raw_pts or len(raw_pts) < 10:
        return False
    
    pts_array = np.array(raw_pts, dtype=np.float32)
    
    # CIRCLE validation: Check if the stroke forms a closed loop
    if detected_shape == "circle":
        # Calculate distance from first to last point
        start = pts_array[0]
        end = pts_array[-1]
        closure = np.linalg.norm(end - start)
        
        # For a circle, start and end should be close (closure distance < 25% of bbox diagonal)
        x_min, y_min = pts_array.min(axis=0)
        x_max, y_max = pts_array.max(axis=0)
        bbox_diag = np.sqrt((x_max - x_min) ** 2 + (y_max - y_min) ** 2)
        
        closure_ratio = closure / bbox_diag if bbox_diag > 0 else 1.0
        if closure_ratio > 0.35:  # Too open, not a circle
            return False
        
        return True
    
    # TRIANGLE validation: Check for ~3 corners/direction changes
    elif detected_shape == "triangle":
        # Calculate direction changes (angles) at each point
        if len(pts_array) < 5:
            return False
        
        # Compute angles between consecutive segments
        corners = 0
        threshold_angle = 30  # degrees
        
        for i in range(1, len(pts_array) - 1):
            v1 = pts_array[i] - pts_array[i-1]
            v2 = pts_array[i+1] - pts_array[i]
            
            len1 = np.linalg.norm(v1)
            len2 = np.linalg.norm(v2)
            
            if len1 > 1 and len2 > 1:
                cos_angle = np.dot(v1, v2) / (len1 * len2)
                cos_angle = np.clip(cos_angle, -1, 1)
                angle_rad = np.arccos(cos_angle)
                angle_deg = np.degrees(angle_rad)
                
                # Sharp turn = corner
                if angle_deg < (180 - threshold_angle):
                    corners += 1
        
        # Triangles should have 3 distinct corners
        # Allow 2-4 corners for rough sketches
        return 2 <= corners <= 4
    
    # SQUARE validation: Check for ~4 corners and rectangular aspect
    elif detected_shape == "square":
        if len(pts_array) < 5:
            return False
        
        # Count corners (similar to triangle logic)
        corners = 0
        threshold_angle = 30  # degrees
        
        for i in range(1, len(pts_array) - 1):
            v1 = pts_array[i] - pts_array[i-1]
            v2 = pts_array[i+1] - pts_array[i]
            
            len1 = np.linalg.norm(v1)
            len2 = np.linalg.norm(v2)
            
            if len1 > 1 and len2 > 1:
                cos_angle = np.dot(v1, v2) / (len1 * len2)
                cos_angle = np.clip(cos_angle, -1, 1)
                angle_rad = np.arccos(cos_angle)
                angle_deg = np.degrees(angle_rad)
                
                if angle_deg < (180 - threshold_angle):
                    corners += 1
        
        # Squares should have 4 corners
        if not (3 <= corners <= 5):
            return False
        
        # Also check aspect ratio (should be roughly square-like)
        x_min, y_min = pts_array.min(axis=0)
        x_max, y_max = pts_array.max(axis=0)
        w = x_max - x_min
        h = y_max - y_min
        aspect = w / h if h > 0 else 1.0
        
        # Aspect ratio should be between 0.6 and 1.67 (allows some rectangles)
        if aspect < 0.6 or aspect > 1.67:
            return False
        
        return True
    
    # LINE validation: Check if points are roughly collinear
    elif detected_shape == "line":
        if len(pts_array) < 3:
            return False
        
        # Use least-squares to fit a line, check residuals
        # If most points are close to the line, it's a valid line
        A = np.vstack([pts_array[:, 0], np.ones(len(pts_array))]).T
        try:
            m, c = np.linalg.lstsq(A, pts_array[:, 1], rcond=None)[0]
        except:
            return False
        
        # Calculate distances from points to fitted line
        line_y = m * pts_array[:, 0] + c
        distances = np.abs(pts_array[:, 1] - line_y)
        
        # At least 70% of points should be close to the line (within 10 units)
        close_points = np.sum(distances < 10)
        linearity = close_points / len(pts_array)
        
        return linearity >= 0.7
    
    return False


def _preprocess_stroke(stroke_points: List[Tuple[int, int]], canvas_shape: Tuple[int, int]) -> Optional[np.ndarray]:
    """
    OPTIMIZED: Takes stroke points, extracts ROI, preprocesses to 28x28.
    
    Optimizations:
    - Minimal array copying
    - Use numpy operations where efficient
    - Single-pass padding and resize
    """
    if not stroke_points:
        return None

    # 1. Find bounding box (numpy-based for speed)
    stroke_array = np.array(stroke_points, dtype=np.int32)
    x_min, y_min = stroke_array.min(axis=0)
    x_max, y_max = stroke_array.max(axis=0)
    
    w = max(x_max - x_min, 1)
    h = max(y_max - y_min, 1)

    # 2. Optimized: Create stroke canvas only for the ROI region
    # (smaller memory footprint than full canvas)
    roi_h = h + 2
    roi_w = w + 2
    stroke_canvas = np.zeros((roi_h, roi_w), dtype=np.uint8)
    
    # Translate points to ROI coordinates
    pts_roi = stroke_array - np.array([x_min - 1, y_min - 1])
    pts_roi = pts_roi.reshape((-1, 1, 2))
    cv2.polylines(stroke_canvas, [pts_roi], isClosed=False, color=255, thickness=2)

    # 3. Optimize: Make square with single np.pad call (vs manual loop)
    side = max(roi_h, roi_w)
    pad_h = (side - roi_h) // 2
    pad_w = (side - roi_w) // 2
    
    padded = np.pad(stroke_canvas, ((pad_h, side - roi_h - pad_h), (pad_w, side - roi_w - pad_w)), 
                     mode='constant', constant_values=0)

    # 4. Resize to IMG_SIZE (INTER_AREA for downsampling is already optimal)
    resized = cv2.resize(padded, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)

    return resized


def detect_and_snap_mlp(
    raw_pts: List[Tuple[int, int]],
    canvas_shape: Tuple[int, int] = (640, 480),
    return_confidence: bool = False
) -> Tuple[Optional[str], Optional[List[Tuple[int, int]]], float]:
    """
    Uses the trained MLP to classify a stroke and return a clean version.
    OPTIMIZED: Enhanced validation to reject malformed strokes early.
    
    Args:
        raw_pts: Stroke points
        canvas_shape: Canvas dimensions (default assumes standard size)
        return_confidence: If True, always return (shape, pts, confidence)
    
    Returns:
        If return_confidence=False: (shape, pts)
        If return_confidence=True: (shape, pts, confidence)
    """
    clf = get_classifier()
    
    # OPTIMIZED: Stricter minimum point count (was 5, now 20)
    if not clf or len(raw_pts) < 20:
        result = (None, None)
        if return_confidence:
            return (None, None, 0.0)
        return result
    
    # OPTIMIZED: Validate aspect ratio (reject extreme ratios)
    x_min, y_min, x_max, y_max = _bounding_box(raw_pts)
    w = max(x_max - x_min, 1)
    h = max(y_max - y_min, 1)
    aspect = w / h if h > 0 else 1.0
    
    # Reject extreme aspect ratios (too elongated or too thin)
    if aspect > 5.0 or aspect < 0.2:
        if return_confidence:
            return (None, None, 0.0)
        return (None, None)

    # 1. Preprocess the stroke into a 28x28 image
    processed_image = _preprocess_stroke(raw_pts, canvas_shape)
    if processed_image is None:
        if return_confidence:
            return (None, None, 0.0)
        return (None, None)
        
    # 2. Get prediction from the model
    shape, confidence = clf.predict(processed_image)
    
    print(f"[ShapeMLP] Detected: {shape} (Confidence: {confidence:.2f})") # Debug print

    # 3. Check confidence threshold
    if confidence < CONFIDENCE_THRESHOLD:
        if return_confidence:
            return (None, None, confidence)
        return (None, None)

    # 4. VALIDATE shape match (new fix for rough sketches)
    # Check if the detected shape actually matches the stroke properties
    if not _validate_shape_match(raw_pts, shape):
        print(f"[ShapeMLP] Shape validation FAILED for {shape} - treating as freehand")
        if return_confidence:
            return (None, None, confidence)
        return (None, None)
    
    print(f"[ShapeMLP] Shape validation PASSED for {shape}")

    # Use the original rule-based shape generators
    clean_shape = None
    if shape == "circle":
        clean_shape = "circle"
        clean_pts = _make_circle(raw_pts)
    elif shape == "square":
        # The model was trained on squares
        clean_shape = "square"
        clean_pts = _make_rectangle(raw_pts)
    elif shape == "triangle":
        clean_shape = "triangle"
        clean_pts = _make_triangle(raw_pts)
    elif shape == "line":
        clean_shape = "line"
        clean_pts = _make_line(raw_pts)
    else:
        if return_confidence:
            return (None, None, confidence)
        return (None, None)

    if return_confidence:
        return (clean_shape, clean_pts, confidence)
    return (clean_shape, clean_pts)
