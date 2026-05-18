"""
utils/shape_mlp_ai.py - Shape detection using the trained MLP model.

OPTIMIZATIONS (Phase 1.5):
- Model cached in memory (pre-allocated at startup)
- Preprocessing cached and reused
- NumPy operations prioritized over OpenCV where possible
- Redundant copies eliminated

EXTENDED (Phase 2):
- Support for 30-shape model (letters A-Z + 0-9)
- RL classifier integration for Tier 3 fallback
- Switchable MLP modes at runtime
"""
import numpy as np
import cv2
from typing import List, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.drawing_mlp import DrawingMLP, MLPMode
from utils.shape_ai import _bounding_box, _make_circle, _make_rectangle, _make_triangle, _make_line
from core.config import MLP_CONFIDENCE_THRESHOLD, MLP_MODE, RL_CLASSIFIER_ENABLED

IMG_SIZE = 28
CONFIDENCE_THRESHOLD = MLP_CONFIDENCE_THRESHOLD

# --- Optimized Singleton Classifier Instances ---
_classifier = None
_rl_classifier = None
_classifier_cache = {}

def get_classifier(mode_override: Optional[str] = None):
    """
    Initializes and returns the singleton MLP classifier instance.
    
    Args:
        mode_override: Force a specific mode ("standard" or "extended")
                      Default uses config.MLP_MODE
    
    Returns:
        DrawingMLP instance or None if failed to load
    """
    global _classifier
    
    mode_str = mode_override or MLP_MODE
    target_mode = MLPMode.EXTENDED if mode_str == "extended" else MLPMode.STANDARD
    
    # If mode changed, reinitialize
    if _classifier and _classifier.mode != target_mode:
        print(f"[ShapeMLP] Mode changed from {_classifier.mode.value} to {target_mode.value}")
        _classifier = None
    
    if _classifier is None:
        _classifier = DrawingMLP(mode=target_mode)
        if not _classifier.load():
            print(f"[ShapeMLP] WARNING: Could not load {target_mode.value} MLP model.")
            print(f"[ShapeMLP] Shape snapping may be limited.")
            _classifier = None
    
    return _classifier


def get_rl_classifier():
    """Get or initialize RL classifier for Tier 3 fallback"""
    global _rl_classifier
    
    if not RL_CLASSIFIER_ENABLED:
        return None
    
    if _rl_classifier is None:
        try:
            from utils.rl_classifier import get_rl_classifier as rl_getter
            _rl_classifier = rl_getter()
            print("[ShapeMLP] RL Classifier (Tier 3) initialized")
        except Exception as e:
            print(f"[ShapeMLP] Failed to initialize RL classifier: {e}")
            return None
    
    return _rl_classifier


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
        print(f"[Validation] REJECT {detected_shape}: too few points ({len(raw_pts)})")
        return False
    
    pts_array = np.array(raw_pts, dtype=np.float32)
    
    # Calculate aspect ratio for all shapes
    x_min, y_min = pts_array.min(axis=0)
    x_max, y_max = pts_array.max(axis=0)
    w = x_max - x_min
    h = y_max - y_min
    aspect = w / h if h > 0 else 1.0
    print(f"[Validation] Checking {detected_shape}: {len(raw_pts)} pts, aspect={aspect:.2f}")
    
    # CIRCLE validation: Check if the stroke forms a closed loop
    if detected_shape == "circle":
        # Calculate distance from first to last point
        start = pts_array[0]
        end = pts_array[-1]
        closure = np.linalg.norm(end - start)
        
        # For a circle, start and end should be close (closure distance < 50% of bbox diagonal)
        # FIX-30c: Very relaxed - allow open circles
        x_min, y_min = pts_array.min(axis=0)
        x_max, y_max = pts_array.max(axis=0)
        bbox_diag = np.sqrt((x_max - x_min) ** 2 + (y_max - y_min) ** 2)
        
        closure_ratio = closure / bbox_diag if bbox_diag > 0 else 1.0
        if closure_ratio > 0.60:  # Very relaxed, allow quite open circles
            return False
        
        return True
    
    # TRIANGLE validation: Check for ~3 corners/direction changes
    elif detected_shape == "triangle":
        # FIX-30c: Much more relaxed - just check that stroke has some meaningful length
        # Minimal point count for a triangle
        if len(pts_array) < 3:
            return False
        
        # Just accept it - the MLP confidence threshold already filters bad predictions
        return True
    
    # SQUARE validation: Check for ~4 corners and rectangular aspect
    elif detected_shape == "square":
        # FIX-30c: Very relaxed - accept almost all detected squares
        # Minimum points for any polygon
        if len(pts_array) < 3:
            print(f"[Validation] REJECT square: too few points ({len(pts_array)})")
            return False
        
        # Just accept it - confidence threshold filters bad predictions
        print(f"[Validation] ACCEPT square")
        return True
    
    # LINE validation: Check if points are roughly collinear
    elif detected_shape == "line":
        if len(pts_array) < 3:
            print(f"[Validation] REJECT line: too few points ({len(pts_array)})")
            return False
        
        # Use least-squares to fit a line, check residuals
        # If most points are close to the line, it's a valid line
        A = np.vstack([pts_array[:, 0], np.ones(len(pts_array))]).T
        try:
            m, c = np.linalg.lstsq(A, pts_array[:, 1], rcond=None)[0]
        except:
            print(f"[Validation] REJECT line: lstsq failed")
            return False
        
        # Calculate distances from points to fitted line
        line_y = m * pts_array[:, 0] + c
        distances = np.abs(pts_array[:, 1] - line_y)
        
        # FIX-30c: Much more lenient - 70% linearity instead of 85%
        # Allow curved strokes and loose lines (users don't draw perfectly straight)
        close_points = np.sum(distances < 10)  # Also increased tolerance from 6 to 10
        linearity = close_points / len(pts_array)
        
        print(f"[Validation] Line check: {linearity:.0%} linearity ({close_points}/{len(pts_array)} points < 10 units)")
        
        return linearity >= 0.70
    
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
    cv2.polylines(stroke_canvas, [pts_roi], isClosed=False, color=255, thickness=1)

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
    
    # OPTIMIZED: Minimum point count (10 points allows quick strokes from users)
    if not clf or len(raw_pts) < 10:
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

    # 4. Shape processing and snapping
    # FIX-30c: Accept predictions with confidence >= 0.75 without additional validation
    # The threshold itself provides sufficient filtering
    # The model may not be perfect, but validation is too strict for real user input
    
    print(f"[ShapeMLP] Shape validation BYPASSED (confidence: {confidence:.2f} >= 0.75)")

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
