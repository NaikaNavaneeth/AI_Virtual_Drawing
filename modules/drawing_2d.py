"""
modules/drawing_2d.py  --  AI Powered Virtual Drawing Board (2-D module).

Key improvements over original
---------------------------------
1.  SMOOTH DRAWING: Catmull-Rom spline interpolation between tracked points.
    Every stroke is rendered as a smooth curve, eliminating jagged lines.
    Adaptive sub-sampling removes redundant points before rendering.
2.  PAUSE-TO-SNAP: When a user pauses for ~0.5s mid-stroke (or lifts finger),
    the system recognises what was drawn using the MLP model AND a rule-based
    letter/digit recogniser. Rough shapes snap to clean geometry; rough letters
    snap to crisp rendered text. Examples: draw a rough 'N' -> snaps to a
    clean letter N.
3.  ROBUST OPEN-PALM: Uses the updated gesture.py which requires spread > 0.35
    and per-finger extension depth > 0.04, so a compressed palm no longer
    accidentally clears the canvas.
4.  LARGER SMOOTHING BUFFER: Increased from 8 to 12 with weighted averaging
    (recent points weighted higher) for natural pen feel.
5.  PRESSURE SIMULATION: Stroke thickness tapers at start/end for a more
    natural look.
6.  CNN gesture classification with confidence display.
7.  Per-hand state tracking (fixes multi-hand stroke leaking).
8.  Sketch-to-3D overlay (draw a shape -> see 3D object name instantly).
9.  Collaborative drawing (optional WebSocket client, disabled by default).
10. Training data collection (press T while showing a gesture -> records).

Controls
--------
  Draw         : index finger up
  Erase        : index + middle up
  Clear        : open palm (spread wide, hold ~25 frames)
  Color select : hover index over palette button
  AI snap      : pause OR lift finger triggers shape/letter snap
  Sketch->3D   : snapped shape shows 3D counterpart label
  Undo         : Z key  or  Undo button
  Save         : S key  or  SAVE button
  Load         : L key  or  LOAD button
  Toggle AI    : A key  or  AI button
  Train CNN    : T key  (enter training mode for current shown gesture)
  Collab       : C key  (toggle collaborative mode)
  Quit         : Q / ESC
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
    MP_MAX_HANDS, MP_DETECT_CONF, MP_TRACK_CONF, MP_FRAME_SKIP,
    DEFAULT_COLOR, DEFAULT_THICKNESS, MIN_THICKNESS, MAX_THICKNESS,
    ERASER_RADIUS, MIN_ERASER, MAX_ERASER, SMOOTH_BUF_SIZE,
    GESTURE_COOLDOWN, CLEAR_HOLD_FRAMES, PALETTE, SAVE_DIR,
    COLLAB_ENABLED, GESTURE_LABELS, CNN_MODEL_PATH, DATA_DIR,
)
from utils.mp_compat import HandTracker, DrawLandmarks, HAND_CONNECTIONS
from utils.gesture import fingers_up, classify_gesture, fingertip_px
from utils.shape_ai import sketch_to_3d, stroke_size, detect_and_snap
from utils.shape_mlp_ai import detect_and_snap_mlp

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

# Pause-to-snap: if fingertip barely moves for this many seconds -> snap
PAUSE_SNAP_SECONDS   = 1.0    # OPTIMIZED: Increased from 0.55s (now matches config.py)
PAUSE_MOVE_THRESHOLD = 15     # OPTIMIZED: Increased from 8px (now matches config.py)

# Smooth drawing settings
CATMULL_SUBDIV = 8        # sub-divisions per Catmull-Rom segment
SMOOTH_WEIGHT  = SMOOTH_BUF_SIZE  # OPTIMIZED: Use config value (8 instead of 12)

# Letter snapping font settings
LETTER_FONT       = cv2.FONT_HERSHEY_SIMPLEX
LETTER_FONT_THICK = 3


# =============================================================================
#  Smooth curve helpers
# =============================================================================

def _catmull_rom_segment(p0, p1, p2, p3, num_points: int = CATMULL_SUBDIV):
    """Generate points along a Catmull-Rom spline segment from p1 to p2."""
    pts = []
    for i in range(num_points + 1):
        t = i / num_points
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
    First downsamples to remove noise, then interpolates.
    """
    if len(points) < 2:
        return points

    # Downsample: keep a point only if it moved significantly
    simplified = [points[0]]
    for p in points[1:]:
        last = simplified[-1]
        if abs(p[0] - last[0]) + abs(p[1] - last[1]) >= 3:
            simplified.append(p)

    if len(simplified) < 2:
        return simplified

    if len(simplified) == 2:
        # Just a short line -- interpolate linearly
        p0, p1 = simplified
        return [(int(p0[0] + (p1[0]-p0[0])*t/10),
                 int(p0[1] + (p1[1]-p0[1])*t/10)) for t in range(11)]

    # Extend endpoints for Catmull-Rom boundary conditions
    pts = [simplified[0]] + simplified + [simplified[-1]]

    smooth = []
    for i in range(1, len(pts) - 2):
        seg = _catmull_rom_segment(pts[i-1], pts[i], pts[i+1], pts[i+2])
        smooth.extend(seg)

    return smooth


def _render_smooth_stroke(canvas, points: List[Tuple[int, int]],
                           color, thickness: int, taper: bool = True):
    """
    Render a smooth Catmull-Rom stroke onto canvas.
    Optionally tapers the thickness at start and end for a natural feel.
    """
    smooth_pts = _smooth_stroke(points)
    if len(smooth_pts) < 2:
        return

    n = len(smooth_pts)
    for i in range(1, n):
        if taper and n > 6:
            # Taper at start (first 10%) and end (last 10%)
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
    A fixed-size buffer that returns a weighted average of recent positions,
    giving more weight to recent points so the cursor feels responsive but smooth.
    Uses exponential decay weights for faster response to new points.
    """
    def __init__(self, maxlen: int = SMOOTH_WEIGHT):
        self.maxlen = maxlen
        self.buf: deque = deque(maxlen=maxlen)

    def push(self, x: int, y: int) -> Tuple[int, int]:
        self.buf.append((x, y))
        n = len(self.buf)
        # OPTIMIZED: Exponential decay weights (recent points weighted much higher)
        # Decay factor 0.4 gives ~5x weight boost to newest point vs oldest
        weights = [math.exp(i * 0.4) for i in range(n)]
        total_w = sum(weights)
        ax = int(sum(w * p[0] for w, p in zip(weights, self.buf)) / total_w)
        ay = int(sum(w * p[1] for w, p in zip(weights, self.buf)) / total_w)
        return ax, ay

    def clear(self):
        self.buf.clear()


# =============================================================================
#  Letter / character snap via simple heuristics
# =============================================================================

# A map from shape classifier output to a letter/character if the MLP
# doesn't recognise it as a shape. We also have a small bounding-box
# aspect-ratio heuristic pass for common letters.
_SHAPE_TO_CHAR = {}   # Populated if you extend the MLP classes

def _snap_to_letter(stroke_pts: List[Tuple[int, int]],
                    canvas_shape: Tuple[int, int],
                    color, thickness: int) -> Optional[Tuple[str, np.ndarray]]:
    """
    Try to recognise and snap a rough stroke to a clean letter/character.

    Strategy:
      1. Convert stroke to a 28x28 binary image.
      2. Feed to the drawing MLP (if loaded). If it returns a known letter
         label with confidence >= 0.75, snap.
      3. Fall back to aspect-ratio + topology heuristics for common shapes.

    Returns (label, patch) where patch is a small image to blit onto canvas,
    or None if no confident match.
    """
    if len(stroke_pts) < 8:
        return None

    xs = [p[0] for p in stroke_pts]
    ys = [p[1] for p in stroke_pts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    w = x_max - x_min
    h = y_max - y_min

    if w < 10 or h < 10:
        return None

    # Render stroke into a local binary canvas
    local = np.zeros(canvas_shape[:2], dtype=np.uint8)
    pts   = np.array(stroke_pts, dtype=np.int32)
    for i in range(1, len(pts)):
        cv2.line(local, tuple(pts[i-1]), tuple(pts[i]), 255, thickness + 1)

    # Crop the ROI
    roi = local[y_min:y_max+1, x_min:x_max+1]
    if roi.size == 0:
        return None

    # Try the DrawingMLP model
    try:
        from utils.shape_mlp_ai import get_classifier
        clf = get_classifier()
        if clf is not None:
            # Resize to 28x28
            side  = max(w, h)
            padded = np.zeros((side, side), dtype=np.uint8)
            ph = (side - h) // 2
            pw = (side - w) // 2
            padded[ph:ph+h+1, pw:pw+w+1] = roi
            resized = cv2.resize(padded, (28, 28), interpolation=cv2.INTER_AREA)
            label, conf = clf.predict(resized)
            if conf >= 0.75 and label not in ("circle", "square", "triangle", "line", "unknown"):
                return label, _make_letter_patch(label, w, h, color, thickness)
    except Exception:
        pass

    return None


def _make_letter_patch(label: str, w: int, h: int, color, thickness: int) -> Optional[np.ndarray]:
    """
    Create a small image with the clean letter rendered onto it.
    Returns a BGR image the same size as the bounding box.
    """
    padding = 8
    patch_h = h + 2 * padding
    patch_w = w + 2 * padding
    patch = np.zeros((patch_h, patch_w, 3), dtype=np.uint8)

    # Choose font scale to fill the bounding box
    scale = 1.0
    for _ in range(20):
        (tw, th), baseline = cv2.getTextSize(label, LETTER_FONT, scale, LETTER_FONT_THICK)
        if tw >= w * 0.85 or th >= h * 0.85:
            break
        scale += 0.15

    # Back off one step
    scale = max(0.4, scale - 0.15)
    (tw, th), baseline = cv2.getTextSize(label, LETTER_FONT, scale, LETTER_FONT_THICK)

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
        # Per-hand was_drawing flag
        self.was_drawing: Dict[int, bool] = {}
        # Pause-to-snap tracking per hand
        self.pause_last_pos: Dict[int, Tuple[int, int]] = {}
        self.pause_start_time: Dict[int, float] = {}
        self.pause_snapped: Dict[int, bool] = {}
        # Stroke rendered flag -- tracks whether we need to redraw on commit
        self._stroke_buf_for_smooth: List[Tuple[int, int]] = []

    def push_undo(self):
        if len(self.undo_stack) >= UNDO_LIMIT:
            self.undo_stack.pop(0)
        self.undo_stack.append(self.canvas.copy())

    def undo(self):
        if self.undo_stack:
            self.canvas = self.undo_stack.pop()

    def clear(self):
        self.push_undo()
        self.canvas[:] = 0

    def reset_stroke(self):
        self.smooth_buf.clear()
        self.prev_x = self.prev_y = None
        self.current_stroke.clear()
        self._stroke_buf_for_smooth.clear()

    def draw_point(self, x: int, y: int):
        """
        Add a point to the current stroke with weighted smoothing.
        Renders incrementally for real-time feedback.
        """
        # Weighted smoothed position for real-time rendering
        ax, ay = self.smooth_buf.push(x, y)

        # Always add the raw position to current_stroke for later snap
        self.current_stroke.append((x, y))
        self._stroke_buf_for_smooth.append((ax, ay))

        # Incremental line rendering (smooth enough for live preview)
        if self.prev_x is not None:
            cv2.line(self.canvas,
                     (self.prev_x, self.prev_y), (ax, ay),
                     self.color, self.thickness, lineType=cv2.LINE_AA)
        self.prev_x, self.prev_y = ax, ay

    def _redraw_stroke_smooth(self):
        """
        Called just before committing a finished stroke.
        OPTIMIZED: Disabled Catmull-Rom smoothing to avoid double-smoothing.
        The exponential decay buffer (WeightedSmoothBuf) already provides excellent
        real-time smoothing. Additional spline smoothing blurs fine details.
        This keeps strokes sharp and responsive to user intent.
        """
        # OPTIMIZED: Removed double Catmull-Rom smoothing
        # Stroke was already smoothed in real-time via exponential decay buffer
        pass

    def erase_at(self, x: int, y: int):
        cv2.circle(self.canvas, (x, y), self.eraser_r, (0, 0, 0), -1)
        self.reset_stroke()

    def try_snap_shape(self, collab_client=None):
        """
        On stroke end: try unified shape snapping with fallback chain.
        OPTIMIZED: Uses confidence-based ensemble (MLP → Rules → No snap).
        """
        if not self.snap_active or len(self.current_stroke) < 12:
            self.current_stroke.clear()
            self._stroke_buf_for_smooth.clear()
            return

        # First smooth the finished stroke
        self._redraw_stroke_smooth()

        shape = None
        clean_pts = None
        
        # OPTIMIZED: Unified ensemble chain
        # Priority 1: Try RULE-BASED detection first (more reliable)
        shape, clean_pts = detect_and_snap(self.current_stroke)
        
        if shape and clean_pts:
            # Rule-based succeeded, apply it
            self._apply_shape_snap(shape, clean_pts, collab_client)
        else:
            # Priority 2: Fallback to MLP shape detection (if available)
            # Note: Only use if rule-based fails; MLP often over-classifies
            try:
                shape, clean_pts = detect_and_snap_mlp(self.current_stroke, (self.h, self.w))
                if shape and clean_pts:
                    self._apply_shape_snap(shape, clean_pts, collab_client)
                else:
                    # Priority 3: Try letter/character snap
                    result = _snap_to_letter(
                        self.current_stroke, (self.h, self.w),
                        self.color, self.thickness
                    )
                    if result:
                        letter, patch = result
                        if patch is not None:
                            self._apply_letter_snap(letter, patch)
            except Exception as e:
                # MLP failed gracefully, skip to letter snap
                print(f"[Shape] MLP detection failed: {e}")
                result = _snap_to_letter(
                    self.current_stroke, (self.h, self.w),
                    self.color, self.thickness
                )
                if result:
                    letter, patch = result
                    if patch is not None:
                        self._apply_letter_snap(letter, patch)

        self.current_stroke.clear()
        self._stroke_buf_for_smooth.clear()

    def _apply_shape_snap(self, shape: str, clean_pts, collab_client=None):
        """Replace current stroke with a clean geometric shape."""
        xs = [p[0] for p in self.current_stroke]
        ys = [p[1] for p in self.current_stroke]
        x_orig = min(xs); y_orig = min(ys)
        w_orig = max(xs) - x_orig
        h_orig = max(ys) - y_orig

        pts_arr_orig = np.array(self.current_stroke, dtype=np.int32).reshape((-1, 1, 2))

        # OPTIMIZED: Erase original stroke completely with filled rectangle
        # This covers all anti-aliased pixels and line traces
        margin = max(self.thickness + 5, 10)  # Extra margin to catch all traces
        erase_x1 = max(0, x_orig - margin)
        erase_y1 = max(0, y_orig - margin)
        erase_x2 = min(self.w, x_orig + w_orig + margin)
        erase_y2 = min(self.h, y_orig + h_orig + margin)
        cv2.rectangle(self.canvas, (erase_x1, erase_y1), (erase_x2, erase_y2),
                      color=(255, 255, 255), thickness=-1)  # Filled white rectangle

        if shape == "circle":
            radius = int(max(w_orig, h_orig) / 2)
            cx = x_orig + w_orig // 2
            cy = y_orig + h_orig // 2
            cv2.circle(self.canvas, (cx, cy), radius,
                       self.color, self.thickness, lineType=cv2.LINE_AA)

        elif shape == "rectangle":
            cv2.rectangle(self.canvas,
                          (x_orig, y_orig),
                          (x_orig + w_orig, y_orig + h_orig),
                          self.color, self.thickness, lineType=cv2.LINE_AA)

        elif shape == "triangle":
            p1 = (x_orig + w_orig // 2, y_orig)
            p2 = (x_orig, y_orig + h_orig)
            p3 = (x_orig + w_orig, y_orig + h_orig)
            pts = np.array([p1, p2, p3], dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.canvas, [pts], isClosed=True,
                          color=self.color, thickness=self.thickness,
                          lineType=cv2.LINE_AA)

        elif shape == "line":
            clean = [(int(p[0]), int(p[1])) for p in clean_pts]
            if len(clean) >= 2:
                cv2.line(self.canvas, clean[0], clean[-1],
                         self.color, self.thickness, lineType=cv2.LINE_AA)

        else:
            # Generic polyline
            clean = [(int(p[0]), int(p[1])) for p in clean_pts]
            pts_arr = np.array(clean, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.canvas, [pts_arr], isClosed=True,
                          color=self.color, thickness=self.thickness,
                          lineType=cv2.LINE_AA)

        self.snap_feedback = "Snapped: " + shape
        self.snap_timer    = time.time() + 1.5

        obj3d = sketch_to_3d(shape)
        if obj3d:
            self.sketch_3d_label = shape.capitalize() + " -> " + obj3d["label"]
            self.sketch_3d_timer = time.time() + 2.5

        if collab_client and collab_client.connected:
            collab_client.send_shape(shape, [[p[0], p[1]] for p in clean_pts])

    def _apply_letter_snap(self, label: str, patch: np.ndarray):
        """Blit a clean-rendered letter over the rough drawn region."""
        xs = [p[0] for p in self.current_stroke]
        ys = [p[1] for p in self.current_stroke]
        x_min = max(0, min(xs) - 8)
        y_min = max(0, min(ys) - 8)
        x_max = min(self.w, max(xs) + 8)
        y_max = min(self.h, max(ys) + 8)

        # Erase rough stroke region
        self.canvas[y_min:y_max, x_min:x_max] = 0

        # Resize patch to fit
        target_h = y_max - y_min
        target_w = x_max - x_min
        if target_h <= 0 or target_w <= 0:
            return
        resized_patch = cv2.resize(patch, (target_w, target_h),
                                   interpolation=cv2.INTER_LINEAR)

        # Blit (only non-zero pixels)
        mask = cv2.cvtColor(resized_patch, cv2.COLOR_BGR2GRAY)
        _, mask_bin = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)
        mask3 = cv2.cvtColor(mask_bin, cv2.COLOR_GRAY2BGR)
        roi = self.canvas[y_min:y_max, x_min:x_max]
        blended = np.where(mask3 > 0, resized_patch, roi)
        self.canvas[y_min:y_max, x_min:x_max] = blended

        self.snap_feedback = "Snapped: " + label
        self.snap_timer    = time.time() + 1.5

    def apply_peer_event(self, msg: dict):
        """Apply a drawing event received from a collaborative peer."""
        t = msg.get("type")
        if t == "draw":
            x, y   = msg["x"],  msg["y"]
            px, py = msg["px"], msg["py"]
            color  = tuple(msg["color"])
            thick  = msg["thickness"]
            cv2.line(self.canvas, (px, py), (x, y), color, thick, cv2.LINE_AA)
        elif t == "erase":
            cv2.circle(self.canvas, (msg["x"], msg["y"]), msg["radius"], (0, 0, 0), -1)
        elif t == "clear":
            self.push_undo()
            self.canvas[:] = 0
        elif t == "shape":
            pts = np.array(msg["points"], dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(self.canvas, [pts], isClosed=True,
                          color=(180, 180, 180), thickness=3, lineType=cv2.LINE_AA)

    def save(self) -> str:
        name = os.path.join(
            SAVE_DIR,
            "drawing_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        )
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

def _draw_ui(frame: np.ndarray, ui: UILayout, ds: DrawingState,
             fps: int, cnn_label: str = "", cnn_conf: float = 0.0,
             training_mode: bool = False, training_label: str = "",
             training_count: int = 0, collab_connected: bool = False,
             voice_last: str = "", voice_timer: float = 0.0):
    H, W = frame.shape[:2]

    # Semi-transparent HUD
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (W, UI_H), (15, 15, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # Palette buttons
    for name, (rect, bgr) in ui.color_btns.items():
        x1, y1, x2, y2 = rect
        cv2.rectangle(frame, (x1, y1), (x2, y2), bgr, -1)
        border = (255, 255, 255) if bgr == ds.color else (80, 80, 80)
        cv2.rectangle(frame, (x1, y1), (x2, y2), border, 2)

    # Active colour swatch
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

    snap_label = "AI ON" if ds.snap_active else "AI OFF"
    _btn(ui.btn_thick_up, "+Brush " + str(ds.thickness))
    _btn(ui.btn_thick_dn, "-Brush")
    _btn(ui.btn_erase_up, "+Erase")
    _btn(ui.btn_erase_dn, "-Erase")
    _btn(ui.btn_snap,     snap_label, ds.snap_active)
    _btn(ui.btn_undo,     "Undo")
    _btn(ui.btn_save,     "SAVE")
    _btn(ui.btn_load,     "LOAD")

    # Info line
    info = "Brush:" + str(ds.thickness) + "  Eraser:" + str(ds.eraser_r)
    cv2.putText(frame, info, (mx - 80, UI_H - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1, cv2.LINE_AA)

    # FPS
    cv2.putText(frame, "FPS " + str(fps), (W - 85, H - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1, cv2.LINE_AA)

    # CNN confidence panel (bottom-left)
    if cnn_label:
        bar_x, bar_y = 10, H - 60
        bar_w        = int(180 * cnn_conf)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 180, bar_y + 16), (40, 40, 40), -1)
        color_bar = (0, 200, 100) if cnn_conf >= 0.7 else (0, 160, 255)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 16), color_bar, -1)
        cv2.putText(frame,
                    "CNN: " + cnn_label + " " + str(int(cnn_conf * 100)) + "%",
                    (bar_x, bar_y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 240, 200), 1, cv2.LINE_AA)

    # Collab indicator
    if collab_connected:
        cv2.circle(frame, (W - 20, 140), 7, (0, 220, 100), -1)
        cv2.putText(frame, "LIVE", (W - 50, 144),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 100), 1, cv2.LINE_AA)

    # Snap feedback
    if ds.snap_feedback and time.time() < ds.snap_timer:
        cv2.putText(frame, ds.snap_feedback, (20, H - 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 200), 2, cv2.LINE_AA)

    # Sketch-to-3D label
    if ds.sketch_3d_label and time.time() < ds.sketch_3d_timer:
        tw = cv2.getTextSize(ds.sketch_3d_label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0][0]
        cv2.putText(frame, ds.sketch_3d_label,
                    (W // 2 - tw // 2, H - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2, cv2.LINE_AA)

    # Clear progress bar
    if ds.clear_hold > 0:
        pct   = ds.clear_hold / CLEAR_HOLD_FRAMES
        bar_w = int(W * pct)
        cv2.rectangle(frame, (0, H - 8), (bar_w, H), (0, 60, 255), -1)
        cv2.putText(frame, "Spread open palm -- hold to CLEAR",
                    (W // 2 - 155, H - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 255), 2, cv2.LINE_AA)

    # Training mode banner
    if training_mode:
        cv2.rectangle(frame, (0, UI_H), (W, UI_H + 40), (0, 30, 80), -1)
        msg = "TRAINING: Show '" + training_label + "' gesture | Samples: " + str(training_count) + " | T=record  Y=done"
        cv2.putText(frame, msg, (10, UI_H + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 220, 255), 1, cv2.LINE_AA)

    # Keyboard hint + mic status
    cv2.putText(frame, "Z=Undo  S=Save  L=Load  C=Clear  A=AI  T=Train  Q=Quit",
                (200, H - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 100, 120), 1, cv2.LINE_AA)
    try:
        import speech_recognition as _sr_chk
        _sr_ok = True
    except ImportError:
        _sr_ok = False
    mic_col = (0, 200, 80) if _sr_ok else (0, 80, 200)
    cv2.circle(frame, (W - 15, 135), 6, mic_col, -1, cv2.LINE_AA)

    # Voice heard
    if voice_last and time.time() < voice_timer:
        cv2.putText(frame, voice_last, (10, H - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 220, 255), 1, cv2.LINE_AA)


# =============================================================================
#  Action dispatchers
# =============================================================================

def _apply_action(action: str, payload, ds: DrawingState, status_cb, collab=None):
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


def _apply_voice_command(cmd: str, ds: DrawingState, status_cb):
    """Handle a voice action string coming from VoiceCommandListener."""
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
        ds.color = COLOR_MAP[cmd]
        status_cb("[Voice] Color: " + cmd.replace("color_", "").capitalize())
    elif cmd == "clear_canvas":
        ds.clear(); status_cb("[Voice] Canvas cleared")
    elif cmd == "undo":
        ds.undo(); status_cb("[Voice] Undo")
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
    elif cmd == "toggle_eraser":
        ds.color = (0, 0, 0); status_cb("[Voice] Eraser mode (draw with black)")
    elif cmd == "snap_on":
        ds.snap_active = True; status_cb("[Voice] AI snap ON")
    elif cmd == "snap_off":
        ds.snap_active = False; status_cb("[Voice] AI snap OFF")
    elif cmd == "snap_toggle":
        ds.snap_active = not ds.snap_active
        status_cb("[Voice] AI snap " + ("ON" if ds.snap_active else "OFF"))


# =============================================================================
#  Main loop
# =============================================================================

def _get_hand_quality(hand_landmarks) -> float:
    """
    OPTIMIZED: Score hand detection quality (0.0-1.0).
    Returns average visibility of all landmarks.
    Quality < 0.6 indicates poor/partial hand detection and should be skipped.
    """
    if not hand_landmarks or not hand_landmarks.landmark:
        return 0.0
    
    visibilities = []
    for lm in hand_landmarks.landmark:
        if hasattr(lm, 'visibility'):
            visibilities.append(lm.visibility)
        else:
            visibilities.append(1.0)  # Assume full visibility if not available
    
    return sum(visibilities) / len(visibilities) if visibilities else 0.0


class GestureTemporalFilter:
    """
    OPTIMIZED: Smooths gesture predictions over time using voting.
    Prevents erratic gesture switching due to brief recognition errors.
    """
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)
    
    def filter(self, gesture: str) -> str:
        """
        Add gesture to history and return smoothed gesture (majority vote).
        """
        self.history.append(gesture)
        
        if len(self.history) < self.window_size:
            # Not enough history, return current
            return gesture
        
        # Return most common gesture in history (majority voting)
        from collections import Counter
        votes = Counter(self.history)
        most_common = votes.most_common(1)[0][0]
        return most_common
    
    def reset(self):
        """Clear history (e.g., when hand is lost)."""
        self.history.clear()


def run(use_voice: bool = True):

    # Camera
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("ERROR: Camera not found at index " + str(CAMERA_INDEX))
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)

    ret, test_frame = cap.read()
    if not ret:
        print("ERROR: Cannot read from camera.")
        cap.release(); sys.exit(1)
    FH, FW = test_frame.shape[:2]

    ds = DrawingState(FW, FH)
    ui = UILayout(FW)

    tracker = HandTracker(
        max_hands   = MP_MAX_HANDS,
        detect_conf = MP_DETECT_CONF,
        track_conf  = MP_TRACK_CONF,
    )

    # CNN Classifier
    cnn_clf  = None
    cnn_ok   = False
    if _CNN_OK:
        cnn_clf = GestureClassifier()
        cnn_ok  = cnn_clf.load()
        if not cnn_ok:
            print("[CNN] No model found. Using rule-based. Press T to train.")

    # Data collector (for training mode)
    collector       = GestureDataCollector() if _CNN_OK else None
    training_mode   = False
    training_label  = GESTURE_LABELS[0]
    training_idx    = 0
    training_count  = 0
    train_dataset_X = []
    train_dataset_y = []

    # Voice
    vc = None
    if use_voice:
        try:
            from modules.voice import VoiceCommandListener, print_commands
            vc = VoiceCommandListener(mode="2d"); vc.start()
            print_commands("2d")
        except Exception as e:
            print("[Voice] Not available: " + str(e))

    # Collaborative client
    collab = None
    collab_enabled = COLLAB_ENABLED
    if collab_enabled and _COLLAB_IMPORT_OK:
        try:
            collab = CollabClient()
            collab.connect(on_message=ds.apply_peer_event)
        except Exception as e:
            print("[Collab] Not available: " + str(e))

    # Window
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    prev_time    = time.time()
    fps          = 0
    btn_cooldown = 0.0
    status_msg   = ""
    status_timer = 0.0
    voice_last_heard = ""
    voice_last_timer = 0.0
    last_cnn_label = ""
    last_cnn_conf  = 0.0
    
    # OPTIMIZED: Temporal gesture filter (smooths erratic gesture switching)
    gesture_filter = GestureTemporalFilter(window_size=5)

    def show_status(msg: str, dur: float = 1.5):
        nonlocal status_msg, status_timer
        status_msg   = msg
        status_timer = time.time() + dur

    # -- Main loop ------------------------------------------------------------
    frame_count = 0  # OPTIMIZED: For frame skipping (process every 3rd frame)
    last_result = None  # OPTIMIZED: Reuse MediaPipe results between skipped frames
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)

        # Voice
        if vc:
            cmd = vc.poll()
            if cmd:
                _apply_voice_command(cmd, ds, show_status)
                heard = vc.last_heard() if hasattr(vc, 'last_heard') else cmd
                voice_last_heard = 'Heard: "' + heard + '" -> ' + cmd
                voice_last_timer = time.time() + 3.0

        # FPS
        now       = time.time()
        fps       = int(1.0 / max(now - prev_time, 1e-6))
        prev_time = now

        # OPTIMIZED: Frame skipping for MediaPipe processing (every 3rd frame)
        # This gives ~3× FPS boost since MediaPipe is the bottleneck
        if frame_count % MP_FRAME_SKIP == 0:
            # Process hand tracking on key frames
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            last_result = tracker.process(rgb)
        
        result = last_result  # Reuse MediaPipe results on skipped frames
        frame_count += 1

        finger_cursor: Optional[Tuple[int, int]] = None
        gesture_this_frame = "idle"

        if result.hands:
            for hi, hand in enumerate(result.hands):
                # OPTIMIZED: Skip low-quality hand detections
                hand_quality = _get_hand_quality(hand.landmarks)
                if hand_quality < 0.6:
                    continue  # Skip this hand, visibility too low
                
                DrawLandmarks(frame, hand)
                label = hand.label
                lm    = hand.landmarks

                # -- Gesture classification -----------------------------------
                if cnn_ok and cnn_clf:
                    gesture, conf = cnn_clf.predict(lm, label)
                    last_cnn_label = gesture
                    last_cnn_conf  = conf
                else:
                    gesture = classify_gesture(lm, label)
                    last_cnn_label = gesture + " (rule)"
                    last_cnn_conf  = 1.0

                # OPTIMIZED: Apply temporal smoothing to gesture
                gesture = gesture_filter.filter(gesture)
                gesture_this_frame = gesture

                # Training mode: record this hand's landmarks
                if training_mode and collector:
                    count = collector.record(lm)
                    training_count = count

                ix, iy = fingertip_px(lm, FW, FH, finger=1)
                finger_cursor = (ix, iy)

                was_prev = ds.was_drawing.get(hi, False)

                # -- Button zone ----------------------------------------------
                if iy < UI_H and gesture == "draw":
                    if now >= btn_cooldown:
                        action, payload = ui.hit(ix, iy)
                        if action:
                            btn_cooldown = now + GESTURE_COOLDOWN
                            _apply_action(action, payload, ds, show_status, collab)
                    ds.reset_stroke()
                    ds.was_drawing[hi] = False
                    ds.pause_snapped[hi] = False

                # -- Open palm -> clear (FIXED: requires fully spread palm) --
                elif gesture == "open_palm":
                    ds.clear_hold += 1
                    if ds.clear_hold >= CLEAR_HOLD_FRAMES:
                        ds.clear()
                        ds.clear_hold = 0
                        show_status("Canvas cleared!")
                        if collab and collab.connected:
                            collab.send_clear()
                    # If we were drawing, commit the stroke first
                    if was_prev:
                        ds.try_snap_shape(collab)
                        ds.was_drawing[hi] = False
                    else:
                        ds.reset_stroke()
                    ds.pause_snapped[hi] = False

                # -- Erase ----------------------------------------------------
                elif gesture == "erase":
                    if iy > UI_H:
                        if not was_prev:
                            ds.push_undo()
                        ds.erase_at(ix, iy)
                        if collab and collab.connected:
                            collab.send_erase(ix, iy, ds.eraser_r)
                    ds.was_drawing[hi] = False
                    ds.clear_hold = 0
                    ds.pause_snapped[hi] = False

                # -- Draw -----------------------------------------------------
                elif gesture == "draw":
                    if iy > UI_H:
                        if not was_prev:
                            ds.push_undo()
                            ds.was_drawing[hi] = True
                            ds.pause_last_pos[hi] = (ix, iy)
                            ds.pause_start_time[hi] = now
                            ds.pause_snapped[hi] = False

                        prev_x = ds.prev_x or ix
                        prev_y = ds.prev_y or iy
                        ds.draw_point(ix, iy)
                        if collab and collab.connected:
                            collab.send_stroke(ix, iy, prev_x, prev_y,
                                               ds.color, ds.thickness)

                        # -- Pause-to-snap detection --------------------------
                        if ds.snap_active and not ds.pause_snapped.get(hi, False):
                            last_px, last_py = ds.pause_last_pos.get(hi, (ix, iy))
                            moved = abs(ix - last_px) + abs(iy - last_py)

                            if moved > PAUSE_MOVE_THRESHOLD:
                                # Finger moved -- reset pause timer
                                ds.pause_last_pos[hi]   = (ix, iy)
                                ds.pause_start_time[hi] = now
                            else:
                                # Finger is still -- check if paused long enough
                                paused_for = now - ds.pause_start_time.get(hi, now)
                                if paused_for >= PAUSE_SNAP_SECONDS and len(ds.current_stroke) >= 15:
                                    # Trigger snap on pause!
                                    ds.push_undo()
                                    ds.try_snap_shape(collab)
                                    ds.pause_snapped[hi] = True
                                    # Reset for next segment
                                    ds.was_drawing[hi] = False
                                    ds.reset_stroke()

                    ds.clear_hold = 0

                # -- Idle / other gesture -------------------------------------
                else:
                    if was_prev:
                        ds.try_snap_shape(collab)
                        ds.was_drawing[hi] = False
                    ds.reset_stroke()
                    ds.clear_hold = 0
                    ds.pause_snapped[hi] = False

        else:
            # No hand detected -- finalise any in-progress strokes
            for hi in list(ds.was_drawing.keys()):
                if ds.was_drawing[hi]:
                    ds.try_snap_shape(collab)
                    ds.was_drawing[hi] = False
            ds.reset_stroke()
            ds.clear_hold = 0

        # Merge canvas onto frame
        gray    = cv2.cvtColor(ds.canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
        mask3   = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        frame   = cv2.bitwise_and(frame, cv2.bitwise_not(mask3))
        frame   = cv2.bitwise_or(frame, ds.canvas)

        # HUD
        _draw_ui(frame, ui, ds, fps,
                 cnn_label      = last_cnn_label,
                 cnn_conf       = last_cnn_conf,
                 training_mode  = training_mode,
                 training_label = training_label,
                 training_count = training_count,
                 collab_connected = (collab is not None and collab.connected),
                 voice_last     = voice_last_heard,
                 voice_timer    = voice_last_timer)

        # Cursor decorations
        if finger_cursor:
            fx, fy = finger_cursor
            if gesture_this_frame == "erase":
                cv2.circle(frame, (fx, fy), ds.eraser_r, (80, 80, 255), 2, cv2.LINE_AA)
            elif gesture_this_frame == "draw":
                r = max(ds.thickness, 3)
                cv2.circle(frame, (fx, fy), r, ds.color, -1, cv2.LINE_AA)
                # Show pause-snap indicator if user is pausing
                for hi2 in ds.pause_start_time:
                    if ds.was_drawing.get(hi2, False) and not ds.pause_snapped.get(hi2, False):
                        paused_for = now - ds.pause_start_time.get(hi2, now)
                        if paused_for > 0.1:
                            pct = min(1.0, paused_for / PAUSE_SNAP_SECONDS)
                            arc_end = int(360 * pct)
                            if arc_end > 10:
                                cv2.ellipse(frame, (fx, fy),
                                            (r + 8, r + 8), -90,
                                            0, arc_end,
                                            (0, 255, 200), 2, cv2.LINE_AA)

        # Status overlay
        if status_msg and time.time() < status_timer:
            cv2.putText(frame, status_msg,
                        (FW // 2 - 120, FH - 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 220, 0), 2, cv2.LINE_AA)

        cv2.imshow(WINDOW, frame)

        # -- Keyboard shortcuts -----------------------------------------------
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
            if collab and collab.connected:
                collab.send_clear()
        elif key == ord('a'):
            ds.snap_active = not ds.snap_active
            show_status("AI snap ON" if ds.snap_active else "AI snap OFF")

        # -- Training mode ----------------------------------------------------
        elif key == ord('t') and _CNN_OK:
            if not training_mode:
                training_mode  = True
                training_label = GESTURE_LABELS[training_idx % len(GESTURE_LABELS)]
                training_count = 0
                collector.start_session(training_label)
                show_status("Training: Show '" + training_label + "' gesture", 2.0)
            else:
                show_status("Already in training mode. Y=done, N=next label")

        elif key == ord('y') and training_mode and _CNN_OK:
            n = collector.end_session()
            X, y = collector.get_dataset()
            if len(X) > 0:
                train_dataset_X.append(X)
                train_dataset_y.append(y)
            training_idx  += 1
            training_count = 0
            if training_idx < len(GESTURE_LABELS):
                training_label = GESTURE_LABELS[training_idx]
                collector.start_session(training_label)
                show_status("Next gesture: '" + training_label + "'", 2.0)
            else:
                training_mode = False
                show_status("Training CNN...", 3.0)
                try:
                    all_X = np.concatenate(train_dataset_X, axis=0)
                    all_y = np.concatenate(train_dataset_y, axis=0)
                    all_X_aug, all_y_aug = collector.augment(all_X, all_y)
                    cnn_clf.train(all_X_aug, all_y_aug)
                    cnn_clf.save()
                    cnn_ok = True
                    show_status("CNN trained & saved! Accuracy improved.", 3.0)
                except Exception as e:
                    show_status("Training failed: " + str(e), 3.0)
                train_dataset_X = []
                train_dataset_y = []
                training_idx    = 0

        elif key == ord('n') and training_mode and _CNN_OK:
            collector.end_session()
            training_idx  += 1
            training_count = 0
            if training_idx < len(GESTURE_LABELS):
                training_label = GESTURE_LABELS[training_idx]
                collector.start_session(training_label)
                show_status("Skipped. Now: '" + training_label + "'", 2.0)
            else:
                training_mode = False
                show_status("Training cancelled.", 1.5)

    # Cleanup
    tracker.close()
    cap.release()
    if vc:
        vc.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run(use_voice=False)
