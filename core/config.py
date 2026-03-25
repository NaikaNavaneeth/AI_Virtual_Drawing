"""
config.py  —  Central configuration for the AI Virtual Drawing Platform.
All tuneable constants live here so every module stays in sync.
"""

import os
import platform

# ─────────────────────────────────────────────
# Screen resolution (platform-aware)
# ─────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720

if platform.system() == "Windows":
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        SCREEN_W = user32.GetSystemMetrics(0)
        SCREEN_H = user32.GetSystemMetrics(1)
    except Exception:
        pass
elif platform.system() == "Linux":
    try:
        import subprocess
        out = subprocess.check_output(["xrandr", "--current"], text=True)
        for line in out.splitlines():
            if "* " in line:
                parts = line.split()[0].split("x")
                SCREEN_W, SCREEN_H = int(parts[0]), int(parts[1])
                break
    except Exception:
        pass

# ─────────────────────────────────────────────
# Camera
# ─────────────────────────────────────────────
CAMERA_INDEX = 0
CAMERA_W     = SCREEN_W
CAMERA_H     = SCREEN_H

# ─────────────────────────────────────────────
# MediaPipe hand tracking
# ─────────────────────────────────────────────
MP_MAX_HANDS   = 2
MP_DETECT_CONF = 0.65  # FURTHER RELAXED: 0.70→0.65 to catch more frames
MP_TRACK_CONF  = 0.60  # FURTHER RELAXED: 0.65→0.60 for continuous tracking
                        # Frame skipping caused temporal misalignment between hand tracking 
                        # and stroke collection, creating visible gaps. Maintaining ~1 FPS 
                        # reduction is acceptable for drawing accuracy.

# ─────────────────────────────────────────────
# Drawing defaults
# ─────────────────────────────────────────────
DEFAULT_COLOR     = (255, 80, 0)
DEFAULT_THICKNESS = 5
MIN_THICKNESS     = 1
MAX_THICKNESS     = 30
ERASER_RADIUS     = 40
MIN_ERASER        = 10
MAX_ERASER        = 100

SMOOTH_BUF_SIZE   = 16  # FIX-10: Increased 8→16 for maximum smoothing and frame continuity

# ─────────────────────────────────────────────
# Gesture timing / debounce
# ─────────────────────────────────────────────
GESTURE_COOLDOWN  = 0.55
CLEAR_HOLD_FRAMES = 25

# OPTIMIZED: Pause-to-snap thresholds (fixes shape cutoff at corners)
PAUSE_SNAP_SECONDS = 1.0        # Increased from 0.55s
PAUSE_MOVE_THRESHOLD = 15        # Increased from 8px

# ─────────────────────────────────────────────
# Color palette (BGR)
# ─────────────────────────────────────────────
PALETTE = {
    "Orange": (0,   128, 255),
    "Red":    (0,   0,   255),
    "Green":  (0,   210, 0),
    "Blue":   (255, 50,  0),
    "Yellow": (0,   220, 220),
    "White":  (255, 255, 255),
    "Purple": (210, 0,   210),
    "Cyan":   (255, 220, 0),
}

# ─────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR  = os.path.join(BASE_DIR, "assets", "saved_drawings")
DATA_DIR  = os.path.join(BASE_DIR, "assets", "gesture_data")
MODEL_DIR_ML = os.path.join(BASE_DIR, "ml")
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# 3-D module
# ─────────────────────────────────────────────
MODEL_3D_W     = 960
MODEL_3D_H     = 720
ROT_GAIN       = 0.35
SCALE_GAIN     = 0.002
MIN_SCALE      = 0.3
MAX_SCALE      = 4.0
TRANSLATE_GAIN = 0.004

# ─────────────────────────────────────────────
# AI shape-correction
# ─────────────────────────────────────────────
MIN_STROKE_POINTS = 12
SHAPE_SCORE_MIN   = 0.55

# ─────────────────────────────────────────────
# CNN Gesture model
# ─────────────────────────────────────────────
CNN_MODEL_PATH    = os.path.join(MODEL_DIR_ML, "gesture_cnn.pkl")
CNN_INPUT_SIZE    = 63          # 21 landmarks × 3 (x,y,z), normalized
CNN_HIDDEN_SIZES  = [256, 128, 64]
CNN_DROPOUT       = 0.3
CNN_CONFIDENCE    = 0.85        # OPTIMIZED: Increased from 0.70 for stricter gesture recognition
CNN_FALLBACK      = True        # fall back to rule-based if confidence < threshold

# Gesture label map (shared between training and inference)
GESTURE_LABELS = [
    "draw",       # 0 - index only
    "erase",      # 1 - index + middle
    "select",     # 2 - index + middle + ring
    "open_palm",  # 3 - all five
    "fist",       # 4 - all closed
    "thumbs_up",  # 5 - thumb only
    "pinch",      # 6 - thumb + index close
    "ok",         # 7 - ok ring
    "idle",       # 8 - other
]
NUM_GESTURE_CLASSES = len(GESTURE_LABELS)

# ─────────────────────────────────────────────
# Sketch-to-3D mapping
# ─────────────────────────────────────────────
SKETCH_TO_3D = {
    "circle":    "sphere",
    "rectangle": "cube",
    "triangle":  "pyramid",
    "line":      "cylinder",
}

# ─────────────────────────────────────────────
# Collaborative drawing (WebSocket)
# ─────────────────────────────────────────────
COLLAB_HOST    = "localhost"
COLLAB_PORT    = 8765
COLLAB_ENABLED = False      # set True to enable; requires websockets package

# ─────────────────────────────────────────────
# Voice command keywords
# ─────────────────────────────────────────────
VOICE_COMMANDS = {
    "clear":   "clear_canvas",
    "red":     "color_red",
    "blue":    "color_blue",
    "green":   "color_green",
    "white":   "color_white",
    "yellow":  "color_yellow",
    "orange":  "color_orange",
    "undo":    "undo",
    "save":    "save",
    "eraser":  "toggle_eraser",
    "thicker": "thick_up",
    "thinner": "thick_down",
    "sphere":  "sketch_to_3d",
    "cube":    "sketch_to_3d",
}
