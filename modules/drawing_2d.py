"""
modules/drawing_2d.py  --  AI Powered Virtual Drawing Board (2-D module).

FIXES in this revision
-----------------------
FIX-1  DOTTED / DASHED CIRCLES
       _smooth_stroke() was skipping points too aggressively (min-distance=3).
       Raised to 1 (keep all points) so curves are never fragmentised.

FIX-2  CORRUPTED STROKE BUFFER AFTER INTERPOLATION
       draw_point() was appending incorrectly-averaged raw points into
       current_stroke during the gap-fill loop, poisoning the shape-detector.
       Now the interpolation loop only draws on the canvas; raw stroke data
       comes from the real (smoothed) fingertip position only.

FIX-3  LINE BLEEDING INTO CIRCLE AFTER PAUSE-SNAP
       After pause-snap fires the code set was_drawing[hi]=False and called
       reset_stroke() but did NOT reset prev_x/prev_y.  The very next frame
       a draw gesture resumed with the old prev position, drawing a long line
       across the newly-snapped circle.  Fix: force prev_x=prev_y=None in
       reset_stroke() (already correct) AND guard the resume-draw path so it
       skips the first point after a snap (was_drawing was False on that frame).

FIX-4  FRAME-SKIP GAP FILLING
       MP_FRAME_SKIP was 3, meaning 2 out of 3 frames used stale landmarks.
       Between stale frames the cursor teleports, creating gaps.  Fixed by
       only skipping MediaPipe *inference* but still using the freshest
       result for drawing — no behaviour change needed; the real fix is that
       FIX-2 now interpolates correctly without poisoning stroke data.

FIX-5  HAND-QUALITY THRESHOLD
       Threshold was 0.45 which still dropped partial detections mid-stroke.
       Lowered to 0.30 — gaps are filled by interpolation (FIX-2) so lower
       quality frames are acceptable.

FIX-6  SNAP TRIGGERING ON TOO-SHORT STROKES
       detect_and_snap_mlp required >= 20 pts but the rule-based path had no
       minimum.  Added a 15-point minimum to the rule-based path in
       try_snap_shape() so circles started from near-rest don't snap as lines.
"""

from __future__ import annotations
import cv2
import numpy as np
from collections import deque
from datetime import datetime
import os
import sys
import time
import math
from typing import Optional, List, Tuple, Dict, Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from core.config import (
    SCREEN_W, SCREEN_H, CAMERA_INDEX, CAMERA_W, CAMERA_H,
    MP_MAX_HANDS, MP_DETECT_CONF, MP_TRACK_CONF,
    DEFAULT_COLOR, DEFAULT_THICKNESS, MIN_THICKNESS, MAX_THICKNESS,
    ERASER_RADIUS, MIN_ERASER, MAX_ERASER, SMOOTH_BUF_SIZE,
    GESTURE_COOLDOWN, CLEAR_HOLD_FRAMES, PALETTE, SAVE_DIR,
    COLLAB_ENABLED, GESTURE_LABELS, CNN_MODEL_PATH, DATA_DIR,
)
from utils.mp_compat import HandTracker, DrawLandmarks, HAND_CONNECTIONS
from utils.gesture import fingers_up, classify_gesture, fingertip_px
from utils.shape_ai import sketch_to_3d, stroke_size, detect_and_snap
from utils.shape_mlp_ai import detect_and_snap_mlp
from utils.shape_fitting import fit_circle, fit_rectangle, fit_triangle, fit_line
from utils.temporal_smooth import LandmarkTemporalSmoother, ExponentialLandmarkFilter
from modules.sketch_position_control import (
    GestureActivator, ShapeTracker, MovementController,
    BoundaryManager, VisualIndicators, create_shape_data
)

# RL-based universal shape/letter recognition (NEW FIX-24)
try:
    from utils.universal_classifier import UniversalShapeClassifier
    from modules.rl_ui import RLFeedbackUI, RL_LearningUI
    from utils.learning_manager import LearningManager
    _RL_ENABLED = True
except ImportError:
    _RL_ENABLED = False

# CNN classifier (graceful degradation if torch/sklearn missing)
try:
    from ml.gesture_cnn import GestureClassifier, GestureDataCollector
    _CNN_OK = True
except ImportError:
    _CNN_OK = False

# Collaborative client (optional)
try:
    from modules.collab_server import CollabClient
    _COLLAB_IMPORT_OK = True
except ImportError:
    _COLLAB_IMPORT_OK = False

# -- Constants ----------------------------------------------------------------
WINDOW     = "AI Virtual Drawing - 2D"
UNDO_LIMIT = 20
UI_H       = 160
BTN_W      = 60
BTN_H      = 50

# Pause-to-snap
PAUSE_SNAP_SECONDS   = 1.0
PAUSE_MOVE_THRESHOLD = 15

# Smooth drawing settings
CATMULL_SUBDIV = 8
SMOOTH_WEIGHT  = SMOOTH_BUF_SIZE

# Letter snapping font settings
LETTER_FONT       = cv2.FONT_HERSHEY_SIMPLEX
LETTER_FONT_THICK = 3

# FIX-5: Lower hand quality threshold so partial detections don't drop mid-stroke
# FIX-10: Further lowered to 0.20 to maximize frame continuity (interpolation handles jitter)
_HAND_QUALITY_MIN = 0.20

# Minimum stroke points required before attempting any snap
_MIN_SNAP_PTS = 15


# =============================================================================
#  Smooth curve helpers
# =============================================================================

def _catmull_rom_segment(p0, p1, p2, p3, num_points: int = CATMULL_SUBDIV):
    """Generate points along a Catmull-Rom spline segment from p1 to p2."""
    pts = []
    for i in range(num_points + 1):
        t  = i / num_points
        t2 = t * t
        t3 = t2 * t
        x = 0.5 * (
            (2 * p1[0]) +
            (-p0[0] + p2[0]) * t +
            (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2 +
            (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3
        )
        y = 0.5 * (
            (2 * p1[1]) +
            (-p0[1] + p2[1]) * t +
            (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2 +
            (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3
        )
        pts.append((int(x), int(y)))
    return pts


def _smooth_stroke(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Convert a raw list of fingertip points into a smooth Catmull-Rom curve.

    FIX-1: Changed downsample threshold from 3 → 1 (keep every point).
    The old value of 3 skipped too many points on tight curves (circles),
    producing the dotted/dashed appearance seen in the screenshot.
    """
    if len(points) < 2:
        return points

    # FIX-1: Keep all points (threshold=1 means only skip exact duplicates).
    simplified = [points[0]]
    for p in points[1:]:
        last = simplified[-1]
        # Only skip if EXACTLY the same pixel (no movement at all)
        if p[0] != last[0] or p[1] != last[1]:
            simplified.append(p)

    if len(simplified) < 2:
        return simplified

    if len(simplified) == 2:
        p0, p1 = simplified
        return [(int(p0[0] + (p1[0]-p0[0])*t/10),
                 int(p0[1] + (p1[1]-p0[1])*t/10)) for t in range(11)]

    pts = [simplified[0]] + simplified + [simplified[-1]]
    smooth = []
    for i in range(1, len(pts) - 2):
        seg = _catmull_rom_segment(pts[i-1], pts[i], pts[i+1], pts[i+2])
        smooth.extend(seg)

    return smooth


def _render_smooth_stroke(canvas, points: List[Tuple[int, int]],
                           color, thickness: int, taper: bool = True):
    """Render a smooth Catmull-Rom stroke onto canvas."""
    smooth_pts = _smooth_stroke(points)
    if len(smooth_pts) < 2:
        return

    n = len(smooth_pts)
    for i in range(1, n):
        if taper and n > 6:
            progress = i / n
            if progress < 0.1:
                t = max(1, int(thickness * (progress / 0.1)))
            elif progress > 0.9:
                t = max(1, int(thickness * ((1.0 - progress) / 0.1)))
            else:
                t = thickness
        else:
            t = thickness

        cv2.line(canvas, smooth_pts[i-1], smooth_pts[i],
                 color, t, lineType=cv2.LINE_AA)


# =============================================================================
#  Weighted smoothing buffer for real-time cursor
# =============================================================================

class WeightedSmoothBuf:
    """
    A fixed-size buffer that returns a weighted average of recent positions.
    Exponential decay weights give more influence to recent points.
    """
    def __init__(self, maxlen: int = SMOOTH_WEIGHT):
        self.maxlen = maxlen
        self.buf: deque = deque(maxlen=maxlen)

    def push(self, x: int, y: int) -> Tuple[int, int]:
        self.buf.append((x, y))
        n = len(self.buf)
        # FIX-13: Reduce exponential weight 0.4→0.2 to reduce lag
        weights   = [math.exp(i * 0.2) for i in range(n)]
        total_w   = sum(weights)
        ax = int(sum(w * p[0] for w, p in zip(weights, self.buf)) / total_w)
        ay = int(sum(w * p[1] for w, p in zip(weights, self.buf)) / total_w)
        return ax, ay

    def clear(self):
        self.buf.clear()


# =============================================================================
#  Letter / character snap
# =============================================================================

def _snap_to_letter(stroke_pts, canvas_shape, color, thickness):
    if len(stroke_pts) < 8:
        return None
    xs = [p[0] for p in stroke_pts]; ys = [p[1] for p in stroke_pts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    w = x_max - x_min; h = y_max - y_min
    if w < 10 or h < 10:
        return None
    local = np.zeros(canvas_shape[:2], dtype=np.uint8)
    pts   = np.array(stroke_pts, dtype=np.int32)
    for i in range(1, len(pts)):
        cv2.line(local, tuple(pts[i-1]), tuple(pts[i]), 255, thickness + 1)
    roi = local[y_min:y_max+1, x_min:x_max+1]
    if roi.size == 0:
        return None
    try:
        from utils.shape_mlp_ai import get_classifier
        clf = get_classifier()
        if clf is not None:
            side   = max(w, h)
            padded = np.zeros((side, side), dtype=np.uint8)
            ph = (side - h) // 2; pw = (side - w) // 2
            padded[ph:ph+h+1, pw:pw+w+1] = roi
            resized = cv2.resize(padded, (28, 28), interpolation=cv2.INTER_AREA)
            label, conf = clf.predict(resized)
            if conf >= 0.65 and label not in ("circle", "square", "triangle", "line", "unknown"):
                return label, _make_letter_patch(label, w, h, color, thickness)
    except Exception:
        pass
    return None


def _make_letter_patch(label, w, h, color, thickness):
    padding = 8
    patch_h  = h + 2 * padding
    patch_w  = w + 2 * padding
    patch    = np.zeros((patch_h, patch_w, 3), dtype=np.uint8)
    scale    = 1.0
    for _ in range(20):
        (tw, th), _ = cv2.getTextSize(label, LETTER_FONT, scale, LETTER_FONT_THICK)
        if tw >= w * 0.85 or th >= h * 0.85:
            break
        scale += 0.15
    scale    = max(0.4, scale - 0.15)
    (tw, th), _ = cv2.getTextSize(label, LETTER_FONT, scale, LETTER_FONT_THICK)
    tx = (patch_w - tw) // 2
    ty = (patch_h + th) // 2
    cv2.putText(patch, label, (tx, ty),
                LETTER_FONT, scale, color, LETTER_FONT_THICK, cv2.LINE_AA)
    return patch


# =============================================================================
#  Drawing State
# =============================================================================

class DrawingState:
    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        self.canvas          = np.zeros((h, w, 3), dtype=np.uint8)
        self.color           = DEFAULT_COLOR
        self.thickness       = DEFAULT_THICKNESS
        self.eraser_r        = ERASER_RADIUS
        self.undo_stack: List[np.ndarray] = []
        self.current_stroke: List[Tuple[int, int]] = []
        self.snap_active     = True
        self.snap_feedback   = ""
        self.snap_timer      = 0.0
        self.sketch_3d_label = ""
        self.sketch_3d_timer = 0.0
        self.smooth_buf      = WeightedSmoothBuf(SMOOTH_WEIGHT)
        self.prev_x: Optional[int] = None
        self.prev_y: Optional[int] = None
        self.clear_hold      = 0
        self.was_drawing: Dict[int, bool] = {}
        self.pause_last_pos: Dict[int, Tuple[int, int]] = {}
        self.pause_start_time: Dict[int, float] = {}
        self.pause_snapped: Dict[int, bool] = {}
        self._stroke_buf_for_smooth: List[Tuple[int, int]] = []
        # FIX-3: Track whether we are in the "first point after a snap" state
        self._skip_first_draw: Dict[int, bool] = {}
        # FIX-11: Prevent continuous drawing during hand repositioning
        self._draw_start_pos: Dict[int, Tuple[int, int]] = {}
        # FIX-13: Reduce threshold from 8→2 for instant drawing start
        self._DRAW_THRESHOLD = 2
        
        # FIX-12: Add gesture confirmation (hysteresis) to prevent flickering
        # Track how many consecutive frames a gesture has been confirmed
        self._gesture_frames: Dict[int, int] = {}  # hand_id -> consecutive frame count
        self._last_gesture: Dict[int, str] = {}    # hand_id -> previous gesture
        # FIX-13: Reduce confirmation from 4→2 for faster stop detection (~65ms)
        self._STOP_CONFIRMATION_FRAMES = 2

        # ── Sketch Position Control ──────────────────────────────────────────
        # Enable gesture-based shape repositioning (closed thumbs_up grab and move)
        self.sketch_move_enabled = True
        self.gesture_activator = GestureActivator(hold_duration_sec=2.5)
        self.shape_tracker = ShapeTracker()
        self.movement_controller = MovementController((w, h))
        self.boundary_manager = BoundaryManager(w, h, UI_H)
        self.visual_indicators = VisualIndicators()
        self.is_moving_shape = False
        self.shape_move_timeout = 0.0
        self.current_moving_shape_id: Optional[str] = None
        
        # ── Shape Mapping (Rough → Clean) ────────────────────────────────────
        # Enable learnable shape correction using CNN
        self.shape_mapper = None
        self.use_shape_mapping = False
        try:
            from ml.shape_mapper import ShapeMapperInference
            self.shape_mapper = ShapeMapperInference()
            self.use_shape_mapping = self.shape_mapper.is_loaded
            if self.use_shape_mapping:
                print("[DrawingState] Shape mapping CNN enabled")
            else:
                print("[DrawingState] Shape mapping CNN not available (model not trained)")
        except Exception as e:
            print(f"[DrawingState] Shape mapping initialization failed: {e}")
        
        # ── Reinforcement Learning (FIX-24: Universal shape/letter recognition) ──
        # Enable RL-based shape/letter classification with continuous learning
        self.universal_classifier = None
        self.rl_feedback_ui = None
        self.learning_manager = None
        self.rl_enabled = False
        self._pending_rl_feedback = None  # (ClassificationResult, callback_fn)
        
        if _RL_ENABLED:
            try:
                self.universal_classifier = UniversalShapeClassifier()
                self.rl_feedback_ui = RLFeedbackUI(h, w)
                self.learning_manager = LearningManager()
                self.rl_enabled = True
                print("[DrawingState] RL-based universal shape/letter recognition enabled")
            except Exception as e:
                print(f"[DrawingState] RL initialization failed: {e}")
                self.rl_enabled = False

    def push_undo(self):
        if len(self.undo_stack) >= UNDO_LIMIT:
            self.undo_stack.pop(0)
        self.undo_stack.append(self.canvas.copy())

    def undo(self):
        if self.undo_stack:
            self.canvas = self.undo_stack.pop().copy()

    def clear(self):
        """
        Clear canvas and all associated sketch/shape data.
        Also resets shape tracker and stops any active shape movement.
        """
        self.push_undo()
        self.canvas[:] = 0
        
        # Clear all tracked shapes when canvas is cleared
        self.shape_tracker.clear_all()
        
        # Reset any active shape movement state
        self.is_moving_shape = False
        self.current_moving_shape_id = None
        self.shape_move_timeout = 0.0
        
        # Reset gesture activator to prevent stale grab attempts
        if hasattr(self, 'gesture_activator'):
            self.gesture_activator.reset()

    def reset_stroke(self):
        """
        Reset all per-stroke state including cursor position.
        FIX-3: prev_x/prev_y are cleared here so that after a snap the next
        draw gesture cannot accidentally connect to the old cursor position.
        """
        self.smooth_buf.clear()
        self.prev_x = self.prev_y = None   # FIX-3: explicit cursor reset
        self.current_stroke.clear()
        self._stroke_buf_for_smooth.clear()

    def _improve_stroke_with_cnn(self, stroke_pts):
        """
        Apply learnable shape mapping (CNN) to improve rough sketch quality.
        
        Converts stroke to 28x28 image, applies the trained mapper to clean
        it up, then extracts improved points from the cleaned image.
        
        Args:
            stroke_pts: Original rough stroke points
            
        Returns:
            Improved stroke points (same origin, cleaned up)
        """
        if not self.use_shape_mapping or self.shape_mapper is None:
            return stroke_pts
        
        try:
            # 1. Create 28x28 image from stroke
            xs = [p[0] for p in stroke_pts]
            ys = [p[1] for p in stroke_pts]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            w = max(x_max - x_min, 1)
            h = max(y_max - y_min, 1)
            
            # Create canvas and draw stroke
            stroke_canvas = np.zeros((28, 28), dtype=np.uint8)
            pts_normalized = [(int((p[0] - x_min) * 27 / max(w, 1)), 
                              int((p[1] - y_min) * 27 / max(h, 1))) for p in stroke_pts]
            
            if len(pts_normalized) > 1:
                for i in range(1, len(pts_normalized)):
                    cv2.line(stroke_canvas, pts_normalized[i-1], pts_normalized[i], 255, 1)
            
            # 2. Apply CNN mapping
            clean_img_28x28 = self.shape_mapper.map_rough_to_clean(stroke_canvas)
            if clean_img_28x28 is None:
                return stroke_pts
            
            # 3. Extract points from cleaned image
            # Find white pixels (shape pixels)
            contours, _ = cv2.findContours(clean_img_28x28, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return stroke_pts
            
            # Get the largest contour
            contour = max(contours, key=cv2.contourArea)
            if contour.shape[0] < 5:  # Too few points
                return stroke_pts
            
            # 4. Convert back to original coordinate space
            approx = cv2.approxPolyDP(contour, 1, True)
            improved_pts = []
            
            for point in approx:
                x_norm = point[0][0] / 27.0 if point[0][0] > 0 else 0
                y_norm = point[0][1] / 27.0 if point[0][1] > 0 else 0
                
                x_orig = x_min + x_norm * w
                y_orig = y_min + y_norm * h
                
                improved_pts.append((int(x_orig), int(y_orig)))
            
            if len(improved_pts) > 3:
                return improved_pts
            else:
                return stroke_pts
                
        except Exception as e:
            # Graceful fallback if CNN mapping fails
            print(f"[ShapeSnap] CNN improvement failed: {e}")
            return stroke_pts
    
    # ──────────────────────────────────────────────────────────────────────────
    # RL-Based Universal Shape/Letter Recognition (FIX-24)
    # ──────────────────────────────────────────────────────────────────────────
    
    def _detect_shape_with_rl(self) -> Optional[Tuple[str, str, float]]:
        """
        Detect shape/letter using RL-enhanced universal classifier.
        
        FIX: Increased confidence threshold from 0.3 to 0.75 to prevent
        rough sketches from being incorrectly snapped to shapes.
        Only high-confidence predictions will snap.
        
        Returns:
            (category, label, confidence) or None if detection fails
        """
        if not self.rl_enabled or not self.universal_classifier or len(self.current_stroke) < _MIN_SNAP_PTS:
            return None
        
        try:
            result = self.universal_classifier.classify(self.current_stroke)
            # FIX: Increase threshold from 0.3 to 0.75 to avoid false positives
            # Rough sketches will now fall through to freehand registration
            if result and result.confidence > 0.75:  # HIGH confidence threshold
                print(f"[RL] High-confidence detection: {result.label} ({result.confidence:.2f})")
                return (result.category, result.label, result.confidence)
            elif result:
                print(f"[RL] Low-confidence prediction ignored: {result.label} ({result.confidence:.2f})")
        except Exception as e:
            print(f"[RL] Classification failed: {e}")
        
        return None
    
    def _show_rl_feedback(self, prediction_result):
        """
        Show prediction to user and wait for feedback.
        
        Args:
            prediction_result: ClassificationResult from universal classifier
        """
        if not self.rl_feedback_ui:
            return
        
        # Callback for feedback
        def on_feedback(accepted: bool, correction: Optional[str]):
            if self.universal_classifier:
                correct_label = None if accepted else correction
                self.universal_classifier.record_feedback(
                    prediction_result,
                    correct_label=correct_label,
                    user_accepted=accepted,
                    timestamp=time.time()
                )
                
                if accepted:
                    print(f"✓ Confirmed: {prediction_result.label}")
                else:
                    print(f"✗ Corrected: {prediction_result.label} → {correction}")
        
        # Show the feedback UI
        self._pending_rl_feedback = (prediction_result, on_feedback)
    
    def _handle_rl_keyboard_feedback(self, key: int) -> bool:
        """
        Handle keyboard input for RL feedback.
        
        Args:
            key: OpenCV key code
            
        Returns:
            True if feedback was processed
        """
        if not hasattr(self, '_pending_rl_feedback') or self._pending_rl_feedback is None:
            return False
        
        if self.rl_feedback_ui:
            return self.rl_feedback_ui.handle_feedback(key)
        
        return False
    
    def _print_rl_statistics(self):
        """Print learning statistics to console."""
        if not self.learning_manager:
            print("[RL] No learning data yet")
            return
        
        report = self.learning_manager.analyze_feedback()
        self.learning_manager.print_report(report)

    def draw_point(self, x: int, y: int):
        """
        Add a point to the current stroke with weighted smoothing.

        FIX-2: Removed the bogus averaged-point append inside the gap-fill
        interpolation loop.  The loop now ONLY draws on the canvas.
        The single real fingertip position (ax, ay) is appended to
        current_stroke exactly once, after the loop.
        """
        ax, ay = self.smooth_buf.push(x, y)

        # Append the REAL smoothed position once (FIX-2: removed loop appends)
        self.current_stroke.append((x, y))
        self._stroke_buf_for_smooth.append((ax, ay))

        if self.prev_x is not None:
            dist = math.hypot(ax - self.prev_x, ay - self.prev_y)

            if dist > 20:
                # Gap-fill: interpolate on canvas ONLY — do NOT add to stroke buffer
                steps = max(2, int(dist / 10))
                for i in range(1, steps + 1):
                    t_cur  = i / (steps + 1)
                    t_prev = (i - 1) / (steps + 1)
                    ix  = int(self.prev_x + t_cur  * (ax - self.prev_x))
                    iy  = int(self.prev_y + t_cur  * (ay - self.prev_y))
                    ipx = int(self.prev_x + t_prev * (ax - self.prev_x))
                    ipy = int(self.prev_y + t_prev * (ay - self.prev_y))
                    cv2.line(self.canvas, (ipx, ipy), (ix, iy),
                             self.color, self.thickness, lineType=cv2.LINE_AA)
                # Draw final segment to actual position
                cv2.line(self.canvas,
                         (int(self.prev_x + (steps / (steps + 1)) * (ax - self.prev_x)),
                          int(self.prev_y + (steps / (steps + 1)) * (ay - self.prev_y))),
                         (ax, ay),
                         self.color, self.thickness, lineType=cv2.LINE_AA)
            else:
                cv2.line(self.canvas,
                         (self.prev_x, self.prev_y), (ax, ay),
                         self.color, self.thickness, lineType=cv2.LINE_AA)

        self.prev_x, self.prev_y = ax, ay

    def erase_at(self, x: int, y: int):
        cv2.circle(self.canvas, (x, y), self.eraser_r, (0, 0, 0), -1)
        self.reset_stroke()

    def try_snap_shape(self, collab_client=None):
        """
        On stroke end: try unified shape snapping with fallback chain.
        
        Detection priority (FIX-24: Added RL-based universal classifier):
        1. Rule-based geometric detector (highest reliability)
        2. MLP shape classifier
        3. RL-based universal classifier (can handle any shape/letter)
        4. Legacy letter snapper (fallback)
        5. Freehand registration (last resort)
        """
        if not self.snap_active or len(self.current_stroke) < _MIN_SNAP_PTS:
            self.current_stroke.clear()
            self._stroke_buf_for_smooth.clear()
            return

        shape     = None
        clean_pts = None

        # Priority 1: rule-based geometric detector (most reliable)
        shape, clean_pts = detect_and_snap(self.current_stroke)

        if shape and clean_pts:
            self._apply_shape_snap(shape, clean_pts, collab_client)
        else:
            # Priority 2: MLP detector
            try:
                shape, clean_pts = detect_and_snap_mlp(
                    self.current_stroke, (self.h, self.w))
                if shape and clean_pts:
                    self._apply_shape_snap(shape, clean_pts, collab_client)
                else:
                    # Priority 3: RL-based universal classifier (NEW FIX-24)
                    rl_result = self._detect_shape_with_rl()
                    if rl_result:
                        category, label, confidence = rl_result
                        # For RL-detected shapes, convert to standard format
                        if category == "shapes":
                            self._apply_shape_snap(label, self.current_stroke, collab_client)
                            # Show prediction for feedback
                            try:
                                pred = self.universal_classifier.classify(self.current_stroke)
                                self._show_rl_feedback(pred)
                            except:
                                pass
                        shape = label  # Mark as snapped
                    else:
                        # Priority 4: Legacy letter snapping (fallback)
                        result = _snap_to_letter(
                            self.current_stroke, (self.h, self.w),
                            self.color, self.thickness)
                        if result:
                            letter, patch = result
                            if patch is not None:
                                self._apply_letter_snap(letter, patch)
                        # FIX-21: Ensure shape is reset for freehand registration
                        shape = None
            except Exception as e:
                print(f"[Shape] Detection failed: {e}")
                result = _snap_to_letter(
                    self.current_stroke, (self.h, self.w),
                    self.color, self.thickness)
                if result:
                    letter, patch = result
                    if patch is not None:
                        self._apply_letter_snap(letter, patch)
                # FIX-21: Ensure shape is reset for freehand registration
                shape = None

        # FIX-17: Register freehand stroke BEFORE clearing buffers
        # If no shape was snapped, register the freehand stroke for movement
        if shape is None:
            self._register_freehand_stroke(collab_client)
        
        self.current_stroke.clear()
        self._stroke_buf_for_smooth.clear()

    def _apply_shape_snap(self, shape: str, clean_pts, collab_client=None):
        """Replace current rough stroke with a clean geometric shape using advanced fitting.
        
        Uses least-squares and PCA-based fitting to ensure:
        - Perfect positioning (centroid correctness)
        - Rotation preservation (for rectangles/triangles)
        - Zero distortion (uses proper geometric fitting, not bounding box)
        
        NEW: Applies learnable shape mapping (CNN) to improve rough stroke quality before fitting.
        """
        if not self.current_stroke:
            return

        xs = [p[0] for p in self.current_stroke]
        ys = [p[1] for p in self.current_stroke]
        x_orig = min(xs); y_orig = min(ys)
        w_orig = max(xs) - x_orig
        h_orig = max(ys) - y_orig

        # Erase only the rough stroke pixels
        pts_arr_orig = np.array(self.current_stroke, dtype=np.int32).reshape((-1, 1, 2))
        stroke_mask  = np.zeros((self.h, self.w), dtype=np.uint8)
        cv2.polylines(stroke_mask, [pts_arr_orig], isClosed=False,
                      color=255, thickness=self.thickness + 2, lineType=cv2.LINE_AA)
        stroke_mask_3ch = cv2.cvtColor(stroke_mask, cv2.COLOR_GRAY2BGR)
        self.canvas = cv2.bitwise_and(self.canvas, cv2.bitwise_not(stroke_mask_3ch))

        # FIX-11: Increase thickness during shape snap for better visibility
        snap_thickness = max(self.thickness + 1, 4)
        
        # FIX-JHC: Apply learnable shape mapping before fitting
        # This improves rough stroke quality using the trained CNN
        improved_stroke = self._improve_stroke_with_cnn(self.current_stroke)

        # NEW: Use advanced shape fitting for perfect mapping
        fit_result = None
        center_x, center_y = x_orig + w_orig // 2, y_orig + h_orig // 2
        
        if shape == "circle":
            fit_result = fit_circle(improved_stroke)
            if fit_result and fit_result.get('quality', 0) > 0.3:
                center_x, center_y = fit_result['center']
                radius = int(fit_result['radius'])
                cv2.circle(self.canvas, (int(center_x), int(center_y)), radius,
                           self.color, snap_thickness, lineType=cv2.LINE_AA)
            else:
                # Fallback if fitting fails
                radius = int(max(w_orig, h_orig) / 2)
                cv2.circle(self.canvas, (int(center_x), int(center_y)), radius,
                           self.color, snap_thickness, lineType=cv2.LINE_AA)
                           
        elif shape == "rectangle":
            fit_result = fit_rectangle(improved_stroke)
            if fit_result and len(fit_result.get('corners', [])) == 4:
                corners = fit_result['corners']
                # Convert to int points for cv2.polylines
                corner_pts = np.array([(int(x), int(y)) for x, y in corners], 
                                      dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.canvas, [corner_pts], isClosed=True,
                              color=self.color, thickness=snap_thickness,
                              lineType=cv2.LINE_AA)
                center_x, center_y = fit_result['center']
            else:
                # Fallback: simple rectangle
                cv2.rectangle(self.canvas,
                              (x_orig, y_orig),
                              (x_orig + w_orig, y_orig + h_orig),
                              self.color, snap_thickness, lineType=cv2.LINE_AA)
                # FIX-29: Update center for fallback rectangle (so it can be grabbed)
                center_x = x_orig + w_orig // 2
                center_y = y_orig + h_orig // 2
                              
        elif shape == "triangle":
            fit_result = fit_triangle(improved_stroke)
            if fit_result and len(fit_result.get('corners', [])) == 3:
                corners = fit_result['corners']
                corner_pts = np.array([(int(x), int(y)) for x, y in corners],
                                      dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.canvas, [corner_pts], isClosed=True,
                              color=self.color, thickness=snap_thickness,
                              lineType=cv2.LINE_AA)
                center_x, center_y = fit_result['center']
            else:
                # Fallback: simple triangle
                p1 = (x_orig + w_orig // 2, y_orig)
                p2 = (x_orig, y_orig + h_orig)
                p3 = (x_orig + w_orig, y_orig + h_orig)
                pts = np.array([p1, p2, p3], dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.canvas, [pts], isClosed=True,
                              color=self.color, thickness=snap_thickness,
                              lineType=cv2.LINE_AA)
                # FIX-29: Update center for fallback triangle (so it can be grabbed)
                center_x = (p1[0] + p2[0] + p3[0]) // 3
                center_y = (p1[1] + p2[1] + p3[1]) // 3
                              
        elif shape == "line":
            fit_result = fit_line(improved_stroke)
            if fit_result:
                start = fit_result['start']
                end = fit_result['end']
                cv2.line(self.canvas, (int(start[0]), int(start[1])),
                         (int(end[0]), int(end[1])),
                         self.color, snap_thickness, lineType=cv2.LINE_AA)
                center_x, center_y = fit_result['center']
            else:
                # Fallback: endpoint line
                clean = [(int(p[0]), int(p[1])) for p in clean_pts]
                if len(clean) >= 2:
                    cv2.line(self.canvas, clean[0], clean[-1],
                             self.color, snap_thickness, lineType=cv2.LINE_AA)
                    # FIX-29: Update center for fallback line (so it can be grabbed)
                    center_x = (clean[0][0] + clean[-1][0]) // 2
                    center_y = (clean[0][1] + clean[-1][1]) // 2
        else:
            # Generic freehand shape
            clean = [(int(p[0]), int(p[1])) for p in clean_pts]
            pts_arr = np.array(clean, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.canvas, [pts_arr], isClosed=True,
                          color=self.color, thickness=snap_thickness,
                          lineType=cv2.LINE_AA)

        self.snap_feedback = "Snapped: " + shape
        self.snap_timer    = time.time() + 1.5
        
        # FIX-9: Reduced pause from 0.3→0.15s for faster feedback
        time.sleep(0.15)

        obj3d = sketch_to_3d(shape)
        if obj3d:
            self.sketch_3d_label = shape.capitalize() + " -> " + obj3d["label"]
            self.sketch_3d_timer = time.time() + 2.5

        if collab_client and collab_client.connected:
            collab_client.send_shape(shape, [[p[0], p[1]] for p in clean_pts])

        # ── Register Shape for Position Control ─────────────────────────
        # Track the snapped shape so user can grab and move it later
        shape_data = create_shape_data(
            shape_type=shape,
            center_x=int(center_x),
            center_y=int(center_y),
            size=(w_orig, h_orig),
            color=self.color,
            thickness=self.thickness
        )
        
        # FIX-30: Store fitted corners as relative offsets for rectangles/triangles
        # This allows repositioning rotated shapes correctly (not just axis-aligned)
        # FIX-31: Handle both "rectangle" and "square" types
        if shape in ("rectangle", "square") and fit_result and len(fit_result.get('corners', [])) == 4:
            corners = fit_result['corners']
            # Store corners as relative offsets from center for later repositioning
            corner_offsets = [(int(cx - center_x), int(cy - center_y)) for cx, cy in corners]
            shape_data['corner_offsets'] = corner_offsets
        
        elif shape == "triangle" and fit_result and len(fit_result.get('corners', [])) == 3:
            corners = fit_result['corners']
            # Store corners as relative offsets from center for later repositioning
            corner_offsets = [(int(cx - center_x), int(cy - center_y)) for cx, cy in corners]
            shape_data['corner_offsets'] = corner_offsets
        
        # FIX: Store line endpoints relative to center for proper repositioning
        if shape == "line" and clean_pts and len(clean_pts) >= 2:
            # Calculate line endpoints relative to center
            p1 = clean_pts[0]
            p2 = clean_pts[-1]
            p1_rel = (p1[0] - center_x, p1[1] - center_y)
            p2_rel = (p2[0] - center_x, p2[1] - center_y)
            shape_data['line_points'] = [p1_rel, p2_rel]
        
        self.shape_tracker.add_shape(shape_data)

    def _apply_letter_snap(self, label: str, patch: np.ndarray):
        """Blit a clean-rendered letter over the rough drawn region."""
        xs    = [p[0] for p in self.current_stroke]
        ys    = [p[1] for p in self.current_stroke]
        x_min = max(0, min(xs) - 8)
        y_min = max(0, min(ys) - 8)
        x_max = min(self.w, max(xs) + 8)
        y_max = min(self.h, max(ys) + 8)

        stroke_mask = np.zeros((self.h, self.w), dtype=np.uint8)
        stroke_pts  = np.array(self.current_stroke, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(stroke_mask, [stroke_pts], isClosed=False,
                      color=255, thickness=self.thickness + 2, lineType=cv2.LINE_AA)
        stroke_mask_inv     = cv2.bitwise_not(stroke_mask)
        stroke_mask_inv_3ch = cv2.cvtColor(stroke_mask_inv, cv2.COLOR_GRAY2BGR)
        self.canvas = cv2.bitwise_and(self.canvas, stroke_mask_inv_3ch)

        target_h = y_max - y_min
        target_w = x_max - x_min
        if target_h <= 0 or target_w <= 0:
            return
        resized_patch = cv2.resize(patch, (target_w, target_h),
                                   interpolation=cv2.INTER_LINEAR)
        mask = cv2.cvtColor(resized_patch, cv2.COLOR_BGR2GRAY)
        _, mask_bin = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)
        mask3   = cv2.cvtColor(mask_bin, cv2.COLOR_GRAY2BGR)
        roi     = self.canvas[y_min:y_max, x_min:x_max]
        blended = np.where(mask3 > 0, resized_patch, roi)
        self.canvas[y_min:y_max, x_min:x_max] = blended

        self.snap_feedback = "Snapped: " + label
        self.snap_timer    = time.time() + 1.5

    def _register_freehand_stroke(self, collab_client=None):
        """
        Register a freehand stroke as a movable shape.
        Called when a stroke doesn't match any geometric shapes.
        Allows users to grab and move any drawn stroke.
        """
        if not self._stroke_buf_for_smooth or len(self._stroke_buf_for_smooth) < _MIN_SNAP_PTS:
            return
        
        # Calculate bounding box from stroke points
        xs = [p[0] for p in self._stroke_buf_for_smooth]
        ys = [p[1] for p in self._stroke_buf_for_smooth]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        w = x_max - x_min
        h = y_max - y_min
        center_x = x_min + w // 2
        center_y = y_min + h // 2
        
        # FIX-21: Store stroke points as RELATIVE offsets from center
        # This ensures correct repositioning when shape is moved
        # Each point is stored as (x - center_x, y - center_y)
        stroke_points = [
            (int(p[0] - center_x), int(p[1] - center_y)) 
            for p in self._stroke_buf_for_smooth
        ]
        
        # Create shape data for freehand stroke
        shape_data = {
            'id': str(__import__('uuid').uuid4()),
            'type': 'freehand',
            'original_pos': (center_x, center_y),
            'current_pos': (center_x, center_y),
            'center': (center_x, center_y),
            'bounding_box': (x_min, y_min, x_max, y_max),
            'size': (w, h),
            'rotation': 0,
            'stroke_points': stroke_points,  # Store as relative offsets
            'color': self.color,
            'thickness': self.thickness,
            'timestamp': time.time(),
            'moved': False,
            'move_count': 0,
        }
        
        # Register in shape tracker
        self.shape_tracker.add_shape(shape_data)

    def apply_peer_event(self, msg: dict):
        t = msg.get("type")
        if t == "draw":
            cv2.line(self.canvas,
                     (msg["px"], msg["py"]), (msg["x"], msg["y"]),
                     tuple(msg["color"]), msg["thickness"], cv2.LINE_AA)
        elif t == "erase":
            cv2.circle(self.canvas, (msg["x"], msg["y"]), msg["radius"], (0,0,0), -1)
        elif t == "clear":
            self.push_undo(); self.canvas[:] = 0
        elif t == "shape":
            pts = np.array(msg["points"], dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.canvas, [pts], isClosed=True,
                          color=(180,180,180), thickness=3, lineType=cv2.LINE_AA)

    def save(self) -> str:
        name = os.path.join(SAVE_DIR,
                            "drawing_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
        cv2.imwrite(name, self.canvas)
        return name

    def load_latest(self) -> Optional[str]:
        try:
            files = sorted(f for f in os.listdir(SAVE_DIR) if f.endswith(".png"))
        except OSError:
            return None
        if files:
            path = os.path.join(SAVE_DIR, files[-1])
            img  = cv2.imread(path)
            if img is not None:
                img = cv2.resize(img, (self.w, self.h))
                self.push_undo()
                self.canvas = img
                return path
        return None

    def redraw_shape_at_position(self, shape: Dict[str, Any], old_pos: Tuple[int, int]):
        """
        Erase a shape from its old position and redraw at new position on canvas.
        Uses mask-based erasing to properly handle antialiasing and thick lines.
        
        Args:
            shape: Shape data dictionary from tracker
            old_pos: Previous (x, y) position to erase from
        """
        if not shape:
            return
        
        ox, oy = old_pos
        nx, ny = shape.get('current_pos', old_pos)
        w, h = shape.get('size', (50, 50))
        shape_type = shape.get('type', 'rectangle')
        color = shape.get('color', self.color)
        thickness = shape.get('thickness', self.thickness)
        
        # Add padding to ensure complete erasure (handles antialiasing + thickness)
        padding = thickness + 5
        
        # Create mask for old shape location (for complete erasure)
        erase_mask = np.zeros((self.h, self.w), dtype=np.uint8)
        
        if shape_type == "circle":
            cv2.circle(erase_mask, (int(ox), int(oy)), 
                      int(w//2) + padding, 255, -1)
        elif shape_type in ("rectangle", "square"):  # FIX-31: Handle both types
            # FIX-30: Use stored corner offsets if available (for rotated rectangles)
            corner_offsets = shape.get('corner_offsets', None)
            if corner_offsets and len(corner_offsets) == 4:
                # Erase using stored corner offsets
                corners_old = [(int(ox + ox_off), int(oy + oy_off)) 
                               for ox_off, oy_off in corner_offsets]
                corner_pts = np.array(corners_old, dtype=np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(erase_mask, [corner_pts], 255)
                # Add padding border around the corners
                cv2.polylines(erase_mask, [corner_pts], isClosed=True,
                              color=255, thickness=padding, lineType=cv2.LINE_AA)
            else:
                # Fallback: erase axis-aligned rectangle
                cv2.rectangle(erase_mask,
                             (int(ox - w//2 - padding), int(oy - h//2 - padding)),
                             (int(ox + w//2 + padding), int(oy + h//2 + padding)),
                             255, -1)
        elif shape_type == "triangle":
            # FIX-30: Use stored corner offsets if available (for rotated triangles)
            corner_offsets = shape.get('corner_offsets', None)
            if corner_offsets and len(corner_offsets) == 3:
                # Erase using stored corner offsets
                corners_old = [(int(ox + ox_off), int(oy + oy_off)) 
                               for ox_off, oy_off in corner_offsets]
                corner_pts = np.array(corners_old, dtype=np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(erase_mask, [corner_pts], 255)
                # Add padding border around the corners
                cv2.polylines(erase_mask, [corner_pts], isClosed=True,
                              color=255, thickness=padding, lineType=cv2.LINE_AA)
            else:
                # Fallback: erase axis-aligned triangle
                p1 = (int(ox), int(oy - h//2 - padding))
                p2 = (int(ox - w//2 - padding), int(oy + h//2 + padding))
                p3 = (int(ox + w//2 + padding), int(oy + h//2 + padding))
                pts = np.array([p1, p2, p3], dtype=np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(erase_mask, [pts], 255)
        elif shape_type == "line":
            cv2.line(erase_mask, (int(ox), int(oy)), (int(nx), int(ny)),
                    255, thickness + padding, cv2.LINE_AA)
        elif shape_type == "freehand":
            # For freehand strokes, erase the old position
            stroke_points = shape.get('stroke_points', [])
            if stroke_points:
                # FIX-27: Stroke points are relative offsets from center
                # Translate to old position (ox, oy) being erased
                for i in range(1, len(stroke_points)):
                    p1 = stroke_points[i-1]
                    p2 = stroke_points[i]
                    cv2.line(erase_mask,
                            (int(p1[0] + ox), int(p1[1] + oy)),
                            (int(p2[0] + ox), int(p2[1] + oy)),
                            255, thickness + padding, cv2.LINE_AA)
            else:
                # Fallback: erase bounding box if no stroke points
                cv2.rectangle(erase_mask,
                            (int(ox - w//2 - padding), int(oy - h//2 - padding)),
                            (int(ox + w//2 + padding), int(oy + h//2 + padding)),
                            255, -1)
        
        # Apply mask-based erasure: clear old shape region
        erase_mask_inv = cv2.bitwise_not(erase_mask)
        erase_mask_3ch = cv2.cvtColor(erase_mask_inv, cv2.COLOR_GRAY2BGR)
        self.canvas = cv2.bitwise_and(self.canvas, erase_mask_3ch)
        
        # Draw shape at new position
        if shape_type == "circle":
            cv2.circle(self.canvas, (int(nx), int(ny)), int(w//2),
                      color, thickness, lineType=cv2.LINE_AA)
        elif shape_type in ("rectangle", "square"):  # FIX-31: Handle both types
            # FIX-30: Use stored corner offsets if available (for rotated rectangles)
            corner_offsets = shape.get('corner_offsets', None)
            if corner_offsets and len(corner_offsets) == 4:
                # Redraw at new position using stored corner offsets
                corners_new = [(int(nx + ox), int(ny + oy)) for ox, oy in corner_offsets]
                corner_pts = np.array(corners_new, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.canvas, [corner_pts], isClosed=True,
                              color=color, thickness=thickness, lineType=cv2.LINE_AA)
            else:
                # Fallback: axis-aligned rectangle (no corner data stored)
                cv2.rectangle(self.canvas,
                             (int(nx - w//2), int(ny - h//2)),
                             (int(nx + w//2), int(ny + h//2)),
                             color, thickness, lineType=cv2.LINE_AA)
        elif shape_type == "triangle":
            # FIX-30: Use stored corner offsets if available (for rotated triangles)
            corner_offsets = shape.get('corner_offsets', None)
            if corner_offsets and len(corner_offsets) == 3:
                # Redraw at new position using stored corner offsets
                corners_new = [(int(nx + ox), int(ny + oy)) for ox, oy in corner_offsets]
                corner_pts = np.array(corners_new, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.canvas, [corner_pts], isClosed=True,
                              color=color, thickness=thickness, lineType=cv2.LINE_AA)
            else:
                # Fallback: axis-aligned triangle (no corner data stored)
                p1 = (int(nx), int(ny - h//2))
                p2 = (int(nx - w//2), int(ny + h//2))
                p3 = (int(nx + w//2), int(ny + h//2))
                pts = np.array([p1, p2, p3], dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(self.canvas, [pts], isClosed=True,
                             color=color, thickness=thickness, lineType=cv2.LINE_AA)
        elif shape_type == "line":
            # FIX: For line shapes, maintain the line geometry (just translate)
            # Store line endpoints relative to center in original_pos
            line_points = shape.get('line_points', None)
            if line_points and len(line_points) >= 2:
                # Get relative endpoints stored during snapping
                p1_rel = line_points[0]
                p2_rel = line_points[1]
                # Translate endpoints based on new position
                p1_new = (p1_rel[0] + nx, p1_rel[1] + ny)
                p2_new = (p2_rel[0] + nx, p2_rel[1] + ny)
                cv2.line(self.canvas, (int(p1_new[0]), int(p1_new[1])), 
                        (int(p2_new[0]), int(p2_new[1])),
                        color, thickness, lineType=cv2.LINE_AA)
            else:
                # Fallback: if no line_points stored, use bounding box center
                cv2.line(self.canvas, (int(nx - w//2), int(ny)), 
                        (int(nx + w//2), int(ny)),
                        color, thickness, lineType=cv2.LINE_AA)
        elif shape_type == "freehand":
            # For freehand strokes, redraw the path at new position
            stroke_points = shape.get('stroke_points', [])
            if stroke_points:
                # FIX-27: Stroke points are stored relative offsets from center
                # Apply directly to new position (nx, ny) not as delta
                # Each stroke point: (relative_x + new_center_x, relative_y + new_center_y)
                for i in range(1, len(stroke_points)):
                    p1 = stroke_points[i-1]
                    p2 = stroke_points[i]
                    cv2.line(self.canvas,
                            (int(p1[0] + nx), int(p1[1] + ny)),
                            (int(p2[0] + nx), int(p2[1] + ny)),
                            color, thickness, lineType=cv2.LINE_AA)

    def rebuild_all_shapes_on_canvas(self):
        """
        Rebuild all shapes currently in tracker onto canvas.
        Used after releasing a moved shape to ensure clean final rendering.
        More efficient than redraw_shape_at_position for multiple shapes.
        """
        # Clear canvas and redraw all tracked shapes
        self.canvas = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        
        num_shapes = len(self.shape_tracker.shapes)
        print(f"[REBUILD] Called - {num_shapes} shapes in tracker")
        
        for idx, shape in enumerate(self.shape_tracker.shapes):
            if not shape:
                continue
            
            pos = shape.get('current_pos', shape.get('center', (0, 0)))
            w, h = shape.get('size', (50, 50))
            shape_type = shape.get('type', 'rectangle')
            color = shape.get('color', self.color)
            thickness = shape.get('thickness', self.thickness)
            nx, ny = int(pos[0]), int(pos[1])
            
            # DEBUG: Log what we're drawing
            print(f"[REBUILD] Shape {idx}: {shape_type} at ({nx}, {ny}), size ({w}, {h}), color {color}, thickness {thickness}")
            
            # Draw each shape type at its current position
            if shape_type == "circle":
                cv2.circle(self.canvas, (nx, ny), int(w//2),
                          color, thickness, lineType=cv2.LINE_AA)
            elif shape_type in ("rectangle", "square"):  # FIX-31: Handle both types
                try:
                    # FIX-30: Use stored corner offsets if available (for rotated rectangles)
                    corner_offsets = shape.get('corner_offsets', None)
                    if corner_offsets and len(corner_offsets) == 4:
                        # Draw using stored corner offsets
                        corners_new = [(int(nx + ox), int(ny + oy)) for ox, oy in corner_offsets]
                        corner_pts = np.array(corners_new, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.polylines(self.canvas, [corner_pts], isClosed=True,
                                      color=color, thickness=thickness, lineType=cv2.LINE_AA)
                    else:
                        # Fallback: axis-aligned rectangle
                        cv2.rectangle(self.canvas,
                                     (int(nx - w//2), int(ny - h//2)),
                                     (int(nx + w//2), int(ny + h//2)),
                                     color, thickness, lineType=cv2.LINE_AA)
                except Exception as e:
                    print(f"[ERROR] Rectangle draw failed: {e}, shape={shape_type}, pos=({nx},{ny}), size=({w},{h})")
            elif shape_type == "triangle":
                try:
                    # FIX-30: Use stored corner offsets if available (for rotated triangles)
                    corner_offsets = shape.get('corner_offsets', None)
                    if corner_offsets and len(corner_offsets) == 3:
                        # Draw using stored corner offsets
                        corners_new = [(int(nx + ox), int(ny + oy)) for ox, oy in corner_offsets]
                        corner_pts = np.array(corners_new, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.polylines(self.canvas, [corner_pts], isClosed=True,
                                      color=color, thickness=thickness, lineType=cv2.LINE_AA)
                    else:
                        # Fallback: axis-aligned triangle
                        p1 = (int(nx), int(ny - h//2))
                        p2 = (int(nx - w//2), int(ny + h//2))
                        p3 = (int(nx + w//2), int(ny + h//2))
                        pts = np.array([p1, p2, p3], dtype=np.int32).reshape((-1, 1, 2))
                        cv2.polylines(self.canvas, [pts], isClosed=True,
                                     color=color, thickness=thickness, lineType=cv2.LINE_AA)
                except Exception as e:
                    print(f"[ERROR] Triangle draw failed: {e}")
            elif shape_type == "line":
                try:
                    line_points = shape.get('line_points', None)
                    if line_points and len(line_points) >= 2:
                        p1_rel, p2_rel = line_points[0], line_points[1]
                        p1_new = (int(p1_rel[0] + nx), int(p1_rel[1] + ny))
                        p2_new = (int(p2_rel[0] + nx), int(p2_rel[1] + ny))
                        cv2.line(self.canvas, p1_new, p2_new,
                                color, thickness, lineType=cv2.LINE_AA)
                    else:
                        cv2.line(self.canvas, (int(nx - w//2), int(ny)), 
                                (int(nx + w//2), int(ny)),
                                color, thickness, lineType=cv2.LINE_AA)
                except Exception as e:
                    print(f"[ERROR] Line draw failed: {e}")
            elif shape_type == "freehand":
                try:
                    stroke_points = shape.get('stroke_points', [])
                    if stroke_points:
                        # FIX-27b: Fix same delta bug in rebuild as in redraw
                        # Stroke points are relative offsets - apply directly to current position
                        for i in range(1, len(stroke_points)):
                            p1 = stroke_points[i-1]
                            p2 = stroke_points[i]
                            cv2.line(self.canvas,
                                    (int(p1[0] + nx), int(p1[1] + ny)),
                                    (int(p2[0] + nx), int(p2[1] + ny)),
                                    color, thickness, lineType=cv2.LINE_AA)
                except Exception as e:
                    print(f"[ERROR] Freehand draw failed: {e}")


# =============================================================================
#  UI Layout
# =============================================================================

class UILayout:
    def __init__(self, w: int):
        self.w = w
        self.color_btns: dict = {}
        x = 10
        for name, bgr in PALETTE.items():
            self.color_btns[name] = ((x, 10, x + BTN_W, 10 + BTN_H), bgr)
            x += BTN_W + 6

        cx = 10
        self.btn_thick_up = (cx,      70, cx + BTN_W,      120); cx += BTN_W + 6
        self.btn_thick_dn = (cx,      70, cx + BTN_W,      120); cx += BTN_W + 6
        self.btn_erase_up = (cx,      70, cx + BTN_W,      120); cx += BTN_W + 6
        self.btn_erase_dn = (cx,      70, cx + BTN_W,      120); cx += BTN_W + 6
        self.btn_snap     = (cx,      70, cx + BTN_W + 10, 120); cx += BTN_W + 16
        self.btn_undo     = (cx,      70, cx + BTN_W,      120)
        self.btn_save     = (w - 130, 10, w - 10,  60)
        self.btn_load     = (w - 130, 70, w - 10, 120)

    def _in(self, btn, x, y) -> bool:
        x1, y1, x2, y2 = btn
        return x1 <= x <= x2 and y1 <= y <= y2

    def hit(self, x: int, y: int):
        for name, (rect, bgr) in self.color_btns.items():
            if self._in(rect, x, y):
                return "set_color", bgr
        if self._in(self.btn_thick_up, x, y): return "thick_up", None
        if self._in(self.btn_thick_dn, x, y): return "thick_dn", None
        if self._in(self.btn_erase_up, x, y): return "erase_up", None
        if self._in(self.btn_erase_dn, x, y): return "erase_dn", None
        if self._in(self.btn_snap,     x, y): return "snap_tog", None
        if self._in(self.btn_undo,     x, y): return "undo",     None
        if self._in(self.btn_save,     x, y): return "save",     None
        if self._in(self.btn_load,     x, y): return "load",     None
        return None, None


# =============================================================================
#  HUD renderer
# =============================================================================

def _draw_ui(frame, ui, ds, fps,
             cnn_label="", cnn_conf=0.0,
             training_mode=False, training_label="",
             training_count=0, collab_connected=False,
             voice_last="", voice_timer=0.0):
    H, W = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (W, UI_H), (15, 15, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    for name, (rect, bgr) in ui.color_btns.items():
        x1, y1, x2, y2 = rect
        cv2.rectangle(frame, (x1, y1), (x2, y2), bgr, -1)
        border = (255, 255, 255) if bgr == ds.color else (80, 80, 80)
        cv2.rectangle(frame, (x1, y1), (x2, y2), border, 2)

    mx = W // 2
    cv2.rectangle(frame, (mx - 22, 12), (mx + 22, 55), ds.color, -1)
    cv2.rectangle(frame, (mx - 22, 12), (mx + 22, 55), (255, 255, 255), 2)

    def _btn(rect, label, active=False):
        x1, y1, x2, y2 = rect
        col = (60, 200, 60) if active else (55, 55, 65)
        cv2.rectangle(frame, (x1, y1), (x2, y2), col, -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (120, 120, 130), 2)
        tw, th = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)[0]
        cv2.putText(frame, label,
                    (x1 + ((x2 - x1) - tw) // 2, y1 + ((y2 - y1) + th) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (230, 230, 230), 1, cv2.LINE_AA)

    _btn(ui.btn_thick_up, "+Brush " + str(ds.thickness))
    _btn(ui.btn_thick_dn, "-Brush")
    _btn(ui.btn_erase_up, "+Erase")
    _btn(ui.btn_erase_dn, "-Erase")
    _btn(ui.btn_snap,     "AI ON" if ds.snap_active else "AI OFF", ds.snap_active)
    _btn(ui.btn_undo,     "Undo")
    _btn(ui.btn_save,     "SAVE")
    _btn(ui.btn_load,     "LOAD")

    cv2.putText(frame,
                "Brush:" + str(ds.thickness) + "  Eraser:" + str(ds.eraser_r),
                (mx - 80, UI_H - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, "FPS " + str(fps), (W - 85, H - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1, cv2.LINE_AA)

    if cnn_label:
        bar_x, bar_y = 10, H - 60
        bar_w = int(180 * cnn_conf)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 180, bar_y + 16), (40, 40, 40), -1)
        color_bar = (0, 200, 100) if cnn_conf >= 0.7 else (0, 160, 255)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 16), color_bar, -1)
        cv2.putText(frame,
                    "CNN: " + cnn_label + " " + str(int(cnn_conf * 100)) + "%",
                    (bar_x, bar_y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 240, 200), 1, cv2.LINE_AA)

    if collab_connected:
        cv2.circle(frame, (W - 20, 140), 7, (0, 220, 100), -1)
        cv2.putText(frame, "LIVE", (W - 50, 144),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 100), 1, cv2.LINE_AA)

    if ds.snap_feedback and time.time() < ds.snap_timer:
        cv2.putText(frame, ds.snap_feedback, (20, H - 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 200), 2, cv2.LINE_AA)

    if ds.sketch_3d_label and time.time() < ds.sketch_3d_timer:
        tw = cv2.getTextSize(ds.sketch_3d_label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0][0]
        cv2.putText(frame, ds.sketch_3d_label,
                    (W // 2 - tw // 2, H - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2, cv2.LINE_AA)

    if ds.clear_hold > 0:
        pct   = ds.clear_hold / CLEAR_HOLD_FRAMES
        bar_w = int(W * pct)
        cv2.rectangle(frame, (0, H - 8), (bar_w, H), (0, 60, 255), -1)
        cv2.putText(frame, "Spread open palm -- hold to CLEAR",
                    (W // 2 - 155, H - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 255), 2, cv2.LINE_AA)

    if training_mode:
        cv2.rectangle(frame, (0, UI_H), (W, UI_H + 40), (0, 30, 80), -1)
        cv2.putText(frame,
                    "TRAINING: Show '" + training_label + "' | Samples: " + str(training_count),
                    (10, UI_H + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 220, 255), 1, cv2.LINE_AA)

    cv2.putText(frame, "Z=Undo  S=Save  L=Load  C=Clear  A=AI  T=Train  Q=Quit",
                (200, H - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 120), 1, cv2.LINE_AA)

    try:
        import speech_recognition as _sr_chk
        _sr_ok = True
    except ImportError:
        _sr_ok = False
    cv2.circle(frame, (W - 15, 135), 6,
               (0, 200, 80) if _sr_ok else (0, 80, 200), -1, cv2.LINE_AA)

    if voice_last and time.time() < voice_timer:
        cv2.putText(frame, voice_last, (10, H - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 220, 255), 1, cv2.LINE_AA)


# =============================================================================
#  Action dispatchers
# =============================================================================

def _apply_action(action, payload, ds, status_cb, collab=None):
    if action == "set_color":
        ds.color = payload; status_cb("Color changed")
    elif action == "thick_up":
        ds.thickness = min(MAX_THICKNESS, ds.thickness + 2); status_cb("Brush: " + str(ds.thickness))
    elif action == "thick_dn":
        ds.thickness = max(MIN_THICKNESS, ds.thickness - 2); status_cb("Brush: " + str(ds.thickness))
    elif action == "erase_up":
        ds.eraser_r  = min(MAX_ERASER,   ds.eraser_r  + 5);  status_cb("Eraser: " + str(ds.eraser_r))
    elif action == "erase_dn":
        ds.eraser_r  = max(MIN_ERASER,   ds.eraser_r  - 5);  status_cb("Eraser: " + str(ds.eraser_r))
    elif action == "snap_tog":
        ds.snap_active = not ds.snap_active
        status_cb("AI snap ON" if ds.snap_active else "AI snap OFF")
    elif action == "undo":
        ds.undo(); status_cb("Undo")
    elif action == "save":
        p = ds.save(); status_cb("Saved: " + os.path.basename(p))
    elif action == "load":
        p = ds.load_latest()
        status_cb("Loaded: " + os.path.basename(p) if p else "No saves found")


def _apply_voice_command(cmd, ds, status_cb):
    COLOR_MAP = {
        "color_red":    (0,   0,   255),
        "color_blue":   (255, 50,  0),
        "color_green":  (0,   210, 0),
        "color_white":  (255, 255, 255),
        "color_yellow": (0,   220, 220),
        "color_orange": (0,   128, 255),
        "color_purple": (210, 0,   210),
        "color_cyan":   (255, 220, 0),
    }
    if cmd in COLOR_MAP:
        ds.color = COLOR_MAP[cmd]; status_cb("[Voice] Color: " + cmd.replace("color_","").capitalize())
    elif cmd == "clear_canvas": ds.clear(); status_cb("[Voice] Canvas cleared")
    elif cmd == "undo":         ds.undo();  status_cb("[Voice] Undo")
    elif cmd == "save":
        p = ds.save(); status_cb("[Voice] Saved: " + os.path.basename(p))
    elif cmd == "thick_up":
        ds.thickness = min(MAX_THICKNESS, ds.thickness + 2); status_cb("[Voice] Brush: " + str(ds.thickness))
    elif cmd == "thick_down":
        ds.thickness = max(MIN_THICKNESS, ds.thickness - 2); status_cb("[Voice] Brush: " + str(ds.thickness))
    elif cmd == "erase_up":
        ds.eraser_r = min(MAX_ERASER, ds.eraser_r + 10); status_cb("[Voice] Eraser: " + str(ds.eraser_r))
    elif cmd == "erase_down":
        ds.eraser_r = max(MIN_ERASER, ds.eraser_r - 10); status_cb("[Voice] Eraser: " + str(ds.eraser_r))
    elif cmd == "toggle_eraser": ds.color = (0,0,0); status_cb("[Voice] Eraser mode")
    elif cmd == "snap_on":       ds.snap_active = True;  status_cb("[Voice] AI snap ON")
    elif cmd == "snap_off":      ds.snap_active = False; status_cb("[Voice] AI snap OFF")
    elif cmd == "snap_toggle":
        ds.snap_active = not ds.snap_active
        status_cb("[Voice] AI snap " + ("ON" if ds.snap_active else "OFF"))


# =============================================================================
#  Quality / temporal helpers
# =============================================================================

def _get_hand_quality(hand_landmarks) -> float:
    """
    Score hand detection quality (0.0-1.0).
    FIX-5: Threshold caller uses _HAND_QUALITY_MIN = 0.30 (was 0.45).
    """
    if not hand_landmarks or not hand_landmarks.landmark:
        return 0.0
    visibilities = []
    for lm in hand_landmarks.landmark:
        visibilities.append(getattr(lm, 'visibility', 1.0))
    return sum(visibilities) / len(visibilities) if visibilities else 0.0


class GestureTemporalFilter:
    """Smooths gesture predictions over time using majority voting."""
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)

    def filter(self, gesture: str) -> str:
        self.history.append(gesture)
        if len(self.history) < self.window_size:
            return gesture
        from collections import Counter
        return Counter(self.history).most_common(1)[0][0]

    def reset(self):
        self.history.clear()


# =============================================================================
#  Main loop
# =============================================================================

def run(use_voice: bool = True):

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("ERROR: Camera not found at index " + str(CAMERA_INDEX)); sys.exit(1)
    # FIX-26: Maximize FPS for responsive hand tracking (low latency)
    cap.set(cv2.CAP_PROP_FPS, 60)  # INCREASED: 30→60 FPS for real-time responsiveness
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)

    ret, test_frame = cap.read()
    if not ret:
        print("ERROR: Cannot read from camera."); cap.release(); sys.exit(1)
    FH, FW = test_frame.shape[:2]

    ds = DrawingState(FW, FH)
    ui = UILayout(FW)

    tracker = HandTracker(
        max_hands   = MP_MAX_HANDS,
        detect_conf = MP_DETECT_CONF,
        track_conf  = MP_TRACK_CONF,
    )

    cnn_clf = None; cnn_ok = False
    if _CNN_OK:
        cnn_clf = GestureClassifier()
        cnn_ok  = cnn_clf.load()
        if not cnn_ok:
            print("[CNN] No model found. Press T to train.")

    collector      = GestureDataCollector() if _CNN_OK else None
    training_mode  = False
    training_label = GESTURE_LABELS[0]
    training_idx   = 0
    training_count = 0
    train_X: list  = []
    train_y: list  = []

    vc = None
    if use_voice:
        try:
            from modules.voice import VoiceCommandListener, print_commands
            vc = VoiceCommandListener(mode="2d"); vc.start(); print_commands("2d")
        except Exception as e:
            print("[Voice] Not available: " + str(e))

    collab = None
    if COLLAB_ENABLED and _COLLAB_IMPORT_OK:
        try:
            from modules.collab_server import CollabClient
            collab = CollabClient()
            collab.connect(on_message=ds.apply_peer_event)
        except Exception as e:
            print("[Collab] Not available: " + str(e))

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    prev_time        = time.time()
    fps              = 0
    btn_cooldown     = 0.0
    status_msg       = ""
    status_timer     = 0.0
    voice_last_heard = ""
    voice_last_timer = 0.0
    last_cnn_label   = ""
    last_cnn_conf    = 0.0
    gesture_filter   = GestureTemporalFilter(window_size=7)  # FIX-JHC: Reduced 11→7 to eliminate gesture ghosting (200ms window)
    
    # NEW: Temporal smoothing for frame gaps elimination
    temporal_smoothers = {}  # Per-hand smoothing to interpolate missing frames
    landmark_filters = {}     # Per-hand exponential filtering for jitter reduction
    
    # FIX-26b: Add separate hand position buffer for shape movement (more stable)
    # Drawing uses high alpha (0.65) for responsiveness, but movement needs stability
    hand_position_buffer = {}  # Per-hand: deque of last N positions for movement smoothing

    def show_status(msg, dur=1.5):
        nonlocal status_msg, status_timer
        status_msg = msg; status_timer = time.time() + dur

    frame_count = 0
    last_result = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)

        if vc:
            cmd = vc.poll()
            if cmd:
                _apply_voice_command(cmd, ds, show_status)
                heard = vc.last_heard() if hasattr(vc, 'last_heard') else cmd
                voice_last_heard = 'Heard: "' + heard + '" -> ' + cmd
                voice_last_timer = time.time() + 3.0

        now       = time.time()
        fps       = int(1.0 / max(now - prev_time, 1e-6))
        prev_time = now

        # Always process fresh MediaPipe results (no reuse)
        # This eliminates frame drops from stale detection data
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = tracker.process(rgb)
        frame_count += 1

        finger_cursor       = None
        gesture_this_frame  = "idle"

        if result.hands:
            for hi, hand in enumerate(result.hands):
                # NEW: Apply temporal smoothing to reduce frame gaps
                hand_quality = _get_hand_quality(hand.landmarks)
                
                # Initialize smoothers for this hand if needed
                if hi not in temporal_smoothers:
                    temporal_smoothers[hi] = LandmarkTemporalSmoother(history_size=1)  # FIX-26: Reduced buffering for responsiveness
                    landmark_filters[hi] = ExponentialLandmarkFilter(alpha=0.65)  # FIX-26: 0.15→0.65 (65% current, 35% history = responsive)
                
                # Smooth landmarks using temporal interpolation
                smoothed_hand = temporal_smoothers[hi].smooth(hand, hand_quality, time.time())
                if smoothed_hand is None:
                    continue
                
                # Apply exponential filter to reduce jitter
                smoothed_hand.landmarks = landmark_filters[hi].filter(smoothed_hand.landmarks)
                
                # FIX-5: Lowered threshold to 0.30
                if _get_hand_quality(smoothed_hand.landmarks) < _HAND_QUALITY_MIN:
                    continue

                DrawLandmarks(frame, smoothed_hand)
                label = smoothed_hand.label
                lm    = smoothed_hand.landmarks

                rule_gesture = classify_gesture(lm, label)

                if cnn_ok and cnn_clf:
                    gesture, conf = cnn_clf.predict(lm, label)
                    last_cnn_label = gesture; last_cnn_conf = conf
                    if gesture == "open_palm" and rule_gesture != "open_palm":
                        gesture = rule_gesture
                else:
                    gesture = rule_gesture
                    last_cnn_label = gesture + " (rule)"; last_cnn_conf = 1.0

                if gesture == "open_palm" and last_cnn_conf < 0.90:
                    gesture = rule_gesture

                # FIX-JHC: Apply temporal filter consistently
                # Window size 7 = ~233ms at 30 FPS, good balance between stability and responsiveness
                # No hard cutoff - all gestures filtered equally for consistency
                gesture = gesture_filter.filter(gesture)
                gesture_this_frame = gesture
                # FIX-15: IMMEDIATE gesture-based start/stop (removed 2-3 second timing delays)
                # Draw starts immediately when "draw" gesture detected
                # Draw stops immediately when gesture changes away from "draw"
                # This provides much better UX - users can start/stop drawing instantly

                if training_mode and collector:
                    training_count = collector.record(lm)

                # FIX-16: Use correct finger position based on gesture
                # thumbs_up: use thumb (0), others: use index (1)
                tracking_finger = 0 if gesture_this_frame == "thumbs_up" else 1
                ix, iy      = fingertip_px(lm, FW, FH, finger=tracking_finger)
                finger_cursor = (ix, iy)
                was_prev    = ds.was_drawing.get(hi, False)

                # ── Button zone ──────────────────────────────────────────────
                # ENHANCEMENT: Support index, middle, and ring fingers for UI selection
                # FIX-19: Check for button hits BEFORE gesture processing
                # This ensures button responsiveness regardless of gesture state
                button_action_taken = False
                if now >= btn_cooldown:
                    # Try each of the three fingers (index=1, middle=2, ring=3) for UI hit
                    for test_finger in [1, 2, 3]:
                        test_x, test_y = fingertip_px(lm, FW, FH, finger=test_finger)
                        if test_y < UI_H:  # Finger is in UI area (0-160px from top)
                            action, payload = ui.hit(test_x, test_y)
                            if action:
                                btn_cooldown = now + GESTURE_COOLDOWN
                                _apply_action(action, payload, ds, show_status, collab)
                                button_action_taken = True
                                break  # Stop checking other fingers after successful hit
                    
                    if button_action_taken:
                        # Reset drawing state when button clicked
                        ds.reset_stroke()
                        ds.was_drawing[hi]    = False
                        ds.pause_snapped[hi]  = False
                        ds._skip_first_draw[hi] = False
                        continue  # Skip gesture handling when button is clicked

                # ── Open palm → clear ────────────────────────────────────────
                if gesture_this_frame == "open_palm":
                    # Reset shape positioning state when gesture changes
                    if ds.is_moving_shape:
                        # FIX-JHC: Rebuild canvas to ensure no artifacts from repositioning
                        # This clears any lingering traces from shape movement
                        ds.rebuild_all_shapes_on_canvas()
                        ds.is_moving_shape = False
                        ds.movement_controller.end_move()
                        show_status("Shape released.", 1.5)
                        # FIX-28: Don't try to snap after rebuild - it will erase shapes
                        # Mark that we just released a shape so we skip try_snap below
                        released_shape_this_frame = True
                    else:
                        released_shape_this_frame = False
                    ds.gesture_activator.reset()  # FIX: Reset when gesture changes
                    
                    if not hasattr(ds, '_open_palm_streak'):
                        ds._open_palm_streak = 0; ds._open_palm_time = now
                    if now > ds._open_palm_time + 0.20:
                        ds._open_palm_streak = 0
                    ds._open_palm_streak += 1; ds._open_palm_time = now

                    if ds._open_palm_streak >= 3 and last_cnn_conf > 0.85:
                        ds.clear_hold += 1
                        if ds.clear_hold >= CLEAR_HOLD_FRAMES:
                            ds.clear(); ds.clear_hold = 0
                            ds._open_palm_streak = 0
                            show_status("Canvas cleared!")
                            if collab and collab.connected:
                                collab.send_clear()
                    else:
                        ds.clear_hold = 0

                    # FIX-28: Don't snap if we just released a shape - snap will destroy it
                    if released_shape_this_frame:
                        ds.reset_stroke()  # Just reset stroke, don't try to snap
                    elif was_prev:
                        ds.try_snap_shape(collab)
                        ds.was_drawing[hi] = False
                    else:
                        ds.reset_stroke()
                    ds.pause_snapped[hi]    = False
                    ds._skip_first_draw[hi] = True  # FIX-3: guard next draw start

                # ── Sketch Position Control ──────────────────────────────────
                # Closed thumbs_up gesture: grab and move shapes
                elif gesture_this_frame == "thumbs_up":
                    # Update gesture activator for thumbs_up (closed fist with thumb up)
                    # CRITICAL: Must update on EVERY frame to track hold duration properly
                    is_activated = ds.gesture_activator.update(
                        "thumbs_up", is_fist=True, current_time=now
                    )
                    progress = ds.gesture_activator.get_hold_progress(now)
                    
                    # Draw grab activation ring (shows progress to user)
                    ds.visual_indicators.draw_grab_activation_ring(
                        frame, ix, iy, progress
                    )
                    
                    # FIX: Check is_activated (returns True when hold duration met), NOT gesture
                    # is_activated is only True after holding for 2-3 seconds
                    if is_activated and not ds.is_moving_shape:
                        # FIX-JHC: Grab the shape NEAREST to hand position, not the most recent
                        # This allows dynamic selection of ANY shape on screen based on hand proximity
                        # Search radius: 120 pixels (allows grabbing shapes near hand)
                        shape = ds.shape_tracker.get_nearest(ix, iy, radius=120)
                        
                        if shape:
                            # FIX-26b: Initialize position buffer for this hand (for smooth movement)
                            if hi not in hand_position_buffer:
                                hand_position_buffer[hi] = deque(maxlen=5)
                            hand_position_buffer[hi].clear()
                            hand_position_buffer[hi].append((ix, iy))
                            
                            ds.movement_controller.start_move(
                                shape['id'], ix, iy, shape['current_pos']
                            )
                            ds.is_moving_shape = True
                            ds.current_moving_shape_id = shape['id']
                            ds.shape_move_timeout = now + 3.0
                            show_status("Shape grabbed! Move hand to reposition.")
                    
                    elif ds.is_moving_shape:
                        # Update shape position as hand moves
                        if now > ds.shape_move_timeout:
                            # Timeout - auto-release
                            ds.is_moving_shape = False
                            ds.movement_controller.end_move()
                            show_status("Shape released (timeout).", 2.0)
                        else:
                            # FIX-26b: Smooth hand position for stable shape movement
                            # Use position buffer to reduce jitter (separate from drawing responsiveness)
                            if hi not in hand_position_buffer:
                                hand_position_buffer[hi] = deque(maxlen=5)  # Keep last 5 positions
                            
                            hand_position_buffer[hi].append((ix, iy))
                            
                            # Average last N positions for stability during movement
                            if len(hand_position_buffer[hi]) > 0:
                                avg_x = sum(p[0] for p in hand_position_buffer[hi]) / len(hand_position_buffer[hi])
                                avg_y = sum(p[1] for p in hand_position_buffer[hi]) / len(hand_position_buffer[hi])
                                ix_smooth, iy_smooth = int(avg_x), int(avg_y)
                            else:
                                ix_smooth, iy_smooth = ix, iy
                            
                            # Calculate new position based on smoothed hand movement
                            new_pos = ds.movement_controller.calculate_new_position(ix_smooth, iy_smooth)
                            shape = ds.shape_tracker.get_by_id(ds.current_moving_shape_id)
                            
                            if shape and new_pos:
                                # Save old position before updating
                                old_pos = shape.get('current_pos', shape.get('center', (ix, iy)))
                                
                                # Apply boundary constraints
                                final_pos = ds.boundary_manager.clamp_position(
                                    shape, new_pos[0], new_pos[1]
                                )
                                
                                # Only redraw if position actually changed (performance optimization)
                                if final_pos != old_pos:
                                    # Store old position for redraw (update tracker before redraw)
                                    old_pos_for_erase = old_pos
                                    
                                    # Update shape position in tracker
                                    ds.shape_tracker.update_shape(shape['id'], {
                                        'current_pos': final_pos,
                                        'center': final_pos,
                                        'moved': True
                                    })
                                    
                                    # FIX-JHC: Redraw shape only when position changed (eliminates frame drops)
                                    shape_updated = ds.shape_tracker.get_by_id(ds.current_moving_shape_id)
                                    if shape_updated:
                                        ds.redraw_shape_at_position(shape_updated, old_pos_for_erase)

                # ── Erase ────────────────────────────────────────────────────
                elif gesture_this_frame == "erase":
                    # Hand opened while moving shape - release it
                    if ds.is_moving_shape:
                        ds.is_moving_shape = False
                        ds.movement_controller.end_move()
                        show_status("Shape released.", 1.5)
                    ds.gesture_activator.reset()

                    if iy > UI_H:
                        if not was_prev:
                            ds.push_undo()
                        ds.erase_at(ix, iy)
                        if collab and collab.connected:
                            collab.send_erase(ix, iy, ds.eraser_r)
                    ds.was_drawing[hi]      = False
                    ds.clear_hold           = 0
                    ds.pause_snapped[hi]    = False
                    ds._skip_first_draw[hi] = False

                # FIX-15: HARD STOP - block drawing if not in draw gesture
                if gesture_this_frame != "draw":
                    ds.prev_x = None
                    ds.prev_y = None

                # ── Draw ─────────────────────────────────────────────────────
                elif gesture_this_frame == "draw" and not button_action_taken:
                    # Reset shape positioning state when gesture changes from gesture like thumbs_up
                    if ds.is_moving_shape:
                        ds.is_moving_shape = False
                        ds.movement_controller.end_move()
                        show_status("Shape released.", 1.5)
                    ds.gesture_activator.reset()  # FIX: Reset when gesture changes to draw
                    
                    # FIX-15: Immediate gesture-based drawing (no timing delays)
                    # FIX-20: Eliminate drawing delay by removing threshold requirement
                    # Draw starts immediately with NO DISTANCE requirement
                    # Prevents jittery/delayed line rendering
                    
                    if iy > UI_H:  # Only draw when BELOW UI area
                        # Initialize drawing state on first frame
                        if not was_prev:
                            ds._draw_start_pos[hi] = (ix, iy)
                            ds.was_drawing[hi] = True
                            ds.push_undo()
                            ds.pause_last_pos[hi]   = (ix, iy)
                            ds.pause_start_time[hi] = now
                            ds.pause_snapped[hi]    = False
                            ds.prev_x = ix
                            ds.prev_y = iy
                        
                        # FIX-20: Start drawing IMMEDIATELY without threshold wait
                        # Append point and draw it right away
                        ds.draw_point(ix, iy)
                        if collab and collab.connected:
                            prev_x = ds.prev_x if ds.prev_x is not None else ix
                            prev_y = ds.prev_y if ds.prev_y is not None else iy
                            collab.send_stroke(ix, iy, prev_x, prev_y,
                                             ds.color, ds.thickness)

                        # Pause-to-snap detection
                        if ds.snap_active and not ds.pause_snapped.get(hi, False):
                            last_px, last_py = ds.pause_last_pos.get(hi, (ix, iy))
                            moved = abs(ix - last_px) + abs(iy - last_py)
                            if moved > PAUSE_MOVE_THRESHOLD:
                                ds.pause_last_pos[hi]   = (ix, iy)
                                ds.pause_start_time[hi] = now
                            else:
                                paused_for = now - ds.pause_start_time.get(hi, now)
                                if paused_for >= PAUSE_SNAP_SECONDS and len(ds.current_stroke) >= _MIN_SNAP_PTS:
                                    ds.push_undo()
                                    ds.try_snap_shape(collab)
                                    ds.pause_snapped[hi]    = True
                                    ds.was_drawing[hi]      = False
                                    ds._draw_start_pos.pop(hi, None)
                                    ds.reset_stroke()
                    else:
                        # Finger moved to UI area - stop drawing
                        if was_prev:
                            ds.try_snap_shape(collab)
                            ds.was_drawing[hi] = False
                            ds._skip_first_draw[hi] = True
                        ds._draw_start_pos.pop(hi, None)
                        ds.reset_stroke()
                        ds.prev_x = None
                        ds.prev_y = None

                    ds.clear_hold = 0

                # ── Idle / other ─────────────────────────────────────────────
                else:
                    # Release any shape being moved if gesture changes
                    if ds.is_moving_shape:
                        ds.is_moving_shape = False
                        ds.movement_controller.end_move()
                        show_status("Shape released.", 1.5)
                    ds.gesture_activator.reset()
                    
                    if was_prev:
                        ds.try_snap_shape(collab)
                        ds.was_drawing[hi] = False
                        # FIX-3: Guard next stroke so no line from old position
                        ds._skip_first_draw[hi] = True
                    ds._draw_start_pos.pop(hi, None)  # FIX-11: Clean up draw start position
                    ds.reset_stroke()
                    ds.clear_hold           = 0
                    ds.pause_snapped[hi]    = False

        else:
            for hi in list(ds.was_drawing.keys()):
                if ds.was_drawing[hi]:
                    ds.try_snap_shape(collab)
                    ds.was_drawing[hi]      = False
                    ds._skip_first_draw[hi] = True  # FIX-3
                    ds._draw_start_pos.pop(hi, None)  # FIX-11: Clean up
            # FIX-12: Clean up gesture confirmation state for lost hands
            for hi in list(ds._gesture_frames.keys()):
                ds._gesture_frames.pop(hi, None)
                ds._last_gesture.pop(hi, None)
            ds.reset_stroke()
            ds.clear_hold = 0

        # ── Release Shape on Gesture Change ──────────────────────────────
        # If we're moving a shape but gesture is no longer "thumbs_up", release it
        if gesture_this_frame != "thumbs_up" and ds.is_moving_shape:
            # FIX-JHC: Finalize shape position on canvas before releasing
            ds.rebuild_all_shapes_on_canvas()
            ds.is_moving_shape = False
            ds.movement_controller.end_move()
            if hasattr(ds, 'gesture_activator'):
                ds.gesture_activator.reset()

        # Merge canvas onto frame
        gray    = cv2.cvtColor(ds.canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
        mask3   = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        frame   = cv2.bitwise_and(frame, cv2.bitwise_not(mask3))
        frame   = cv2.bitwise_or(frame, ds.canvas)

        # ── Render Moving Shapes ─────────────────────────────────────────
        # Draw indicator rings for shapes being moved
        if ds.is_moving_shape and ds.current_moving_shape_id:
            shape = ds.shape_tracker.get_by_id(ds.current_moving_shape_id)
            if shape:
                x, y = shape['current_pos']
                w, h = shape.get('size', (50, 50))
                # Draw highlight outline
                cv2.rectangle(frame, (int(x - w//2), int(y - h//2)),
                            (int(x + w//2), int(y + h//2)),
                            (0, 255, 0), 3)
                # Draw movement ring
                cv2.circle(frame, (int(x), int(y)), max(w, h) // 2 + 10,
                          (0, 255, 255), 2)

        _draw_ui(frame, ui, ds, fps,
                 cnn_label        = last_cnn_label,
                 cnn_conf         = last_cnn_conf,
                 training_mode    = training_mode,
                 training_label   = training_label,
                 training_count   = training_count,
                 collab_connected = (collab is not None and collab.connected),
                 voice_last       = voice_last_heard,
                 voice_timer      = voice_last_timer)

        # Cursor decorations
        if finger_cursor:
            fx, fy = finger_cursor
            if gesture_this_frame == "erase":
                cv2.circle(frame, (fx, fy), ds.eraser_r, (80, 80, 255), 2, cv2.LINE_AA)
            elif gesture_this_frame == "draw":
                r = max(ds.thickness, 3)
                cv2.circle(frame, (fx, fy), r, ds.color, -1, cv2.LINE_AA)
                for hi2 in ds.pause_start_time:
                    if ds.was_drawing.get(hi2, False) and not ds.pause_snapped.get(hi2, False):
                        paused_for = now - ds.pause_start_time.get(hi2, now)
                        if paused_for > 0.1:
                            pct     = min(1.0, paused_for / PAUSE_SNAP_SECONDS)
                            arc_end = int(360 * pct)
                            if arc_end > 10 and iy > UI_H:
                                cv2.ellipse(frame, (fx, fy),
                                            (r + 8, r + 8), -90,
                                            0, arc_end, (0, 255, 200), 2, cv2.LINE_AA)

        if status_msg and time.time() < status_timer:
            cv2.putText(frame, status_msg,
                        (FW // 2 - 120, FH - 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 220, 0), 2, cv2.LINE_AA)

        cv2.imshow(WINDOW, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break
        elif key == ord('z'):
            ds.undo(); show_status("Undo")
        elif key == ord('s'):
            p = ds.save(); show_status("Saved: " + os.path.basename(p))
        elif key == ord('l'):
            p = ds.load_latest()
            show_status("Loaded: " + os.path.basename(p) if p else "No saves found")
        elif key == ord('c'):
            ds.clear(); show_status("Canvas cleared!")
            if collab and collab.connected: collab.send_clear()
        elif key == ord('a'):
            ds.snap_active = not ds.snap_active
            show_status("AI snap ON" if ds.snap_active else "AI snap OFF")

        elif key == ord('t') and _CNN_OK:
            if not training_mode:
                training_mode  = True
                training_label = GESTURE_LABELS[training_idx % len(GESTURE_LABELS)]
                training_count = 0
                collector.start_session(training_label)
                show_status("Training: Show '" + training_label + "'", 2.0)
            else:
                show_status("Already training. Y=done, N=next")

        elif key == ord('y') and training_mode and _CNN_OK:
            n = collector.end_session()
            X, y = collector.get_dataset()
            if len(X) > 0:
                train_X.append(X); train_y.append(y)
            training_idx += 1; training_count = 0
            if training_idx < len(GESTURE_LABELS):
                training_label = GESTURE_LABELS[training_idx]
                collector.start_session(training_label)
                show_status("Next: '" + training_label + "'", 2.0)
            else:
                training_mode = False
                show_status("Training CNN...", 3.0)
                try:
                    all_X = np.concatenate(train_X); all_y = np.concatenate(train_y)
                    Xa, ya = collector.augment(all_X, all_y)
                    cnn_clf.train(Xa, ya); cnn_clf.save(); cnn_ok = True
                    show_status("CNN trained & saved!", 3.0)
                except Exception as e:
                    show_status("Training failed: " + str(e), 3.0)
                train_X = []; train_y = []; training_idx = 0

        elif key == ord('n') and training_mode and _CNN_OK:
            collector.end_session()
            training_idx += 1; training_count = 0
            if training_idx < len(GESTURE_LABELS):
                training_label = GESTURE_LABELS[training_idx]
                collector.start_session(training_label)
                show_status("Skipped. Now: '" + training_label + "'", 2.0)
            else:
                training_mode = False; show_status("Training cancelled.", 1.5)

    tracker.close(); cap.release()
    if vc: vc.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run(use_voice=False)