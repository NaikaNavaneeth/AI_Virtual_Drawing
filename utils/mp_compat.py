"""
utils/mp_compat.py  —  MediaPipe compatibility shim.

MediaPipe 0.10.x on Python 3.11/3.12 removed the classic
`mp.solutions` namespace and replaced it with the Tasks API.

This module provides a single import surface that works with BOTH:
  • Old API  (mediapipe 0.9.x / 0.10.x with solutions present)
  • New API  (mediapipe 0.10.x Tasks API — hand_landmarker.task required)

Usage (replaces all direct mediapipe imports in the project):
    from utils.mp_compat import HandTracker, DrawLandmarks, HAND_CONNECTIONS

    tracker = HandTracker(max_hands=2, detect_conf=0.75, track_conf=0.70)
    result  = tracker.process(rgb_frame)   # → CompatResult

    for hand in result.hands:
        label     = hand.label          # "Left" or "Right"
        landmarks = hand.landmarks      # list of 21 objects with .x .y .z
        DrawLandmarks(frame, hand)      # draws skeleton on frame

    lm = result.hands[0].landmarks
    tip = lm[8]                         # index finger tip
    x_px = int(tip.x * frame_width)
    y_px = int(tip.y * frame_height)
"""

from __future__ import annotations
import sys as _sys, os as _os
_MP_COMPAT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _MP_COMPAT_ROOT not in _sys.path:
    _sys.path.insert(0, _MP_COMPAT_ROOT)
import os
import sys
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

# ── Hand skeleton connections (21-landmark standard, same for both APIs) ──────
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),         # thumb
    (0,5),(5,6),(6,7),(7,8),         # index
    (0,9),(9,10),(10,11),(11,12),    # middle
    (0,13),(13,14),(14,15),(15,16),  # ring
    (0,17),(17,18),(18,19),(19,20),  # pinky
    (5,9),(9,13),(13,17),            # palm
]

# ── Drawing spec colours ──────────────────────────────────────────────────────
_LANDMARK_COLOR    = (0, 200, 255)   # cyan dots
_CONNECTION_COLOR  = (255, 150, 0)   # orange lines


# ═══════════════════════════════════════════════════════════════════════════════
#  Shared data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Landmark:
    """Single normalised landmark with .x .y .z (all 0-1 range)."""
    x: float
    y: float
    z: float = 0.0

    # Extra visibility/presence fields (kept for compatibility if any code accesses them)
    visibility: float = 1.0
    presence:   float = 1.0


class LandmarkList:
    """
    Wraps a list of Landmark objects.
    Supports both iteration and .landmark[i] access
    (the old API used .landmark attribute, not direct indexing).
    """
    def __init__(self, landmarks: List[Landmark]):
        self.landmark = landmarks      # old-API style: lm.landmark[8]

    def __iter__(self):
        return iter(self.landmark)

    def __len__(self):
        return len(self.landmark)

    def __getitem__(self, idx):
        return self.landmark[idx]


@dataclass
class HandResult:
    """Single detected hand — label + landmarks."""
    label:     str           # "Left" or "Right"
    score:     float         # detection confidence
    landmarks: LandmarkList  # 21 landmarks


@dataclass
class CompatResult:
    """
    Result returned by HandTracker.process().
    Mimics the shape of mp.solutions.hands result for backward compatibility.
    """
    hands: List[HandResult]

    # ── Old-API attributes kept for any code that uses them directly ──────────
    @property
    def multi_hand_landmarks(self):
        """Returns list of LandmarkList objects (old API style)."""
        if not self.hands:
            return None
        return [h.landmarks for h in self.hands]

    @property
    def multi_handedness(self):
        """Returns fake handedness objects with .classification[0].label."""
        if not self.hands:
            return None
        return [_FakeHandedness(h.label, h.score) for h in self.hands]


class _FakeHandedness:
    """Mimics mediapipe's handedness protobuf so old code works unchanged."""
    def __init__(self, label: str, score: float):
        self.classification = [_FakeClassification(label, score)]


class _FakeClassification:
    def __init__(self, label: str, score: float):
        self.label = label
        self.score = score


# ═══════════════════════════════════════════════════════════════════════════════
#  Backend: Old API  (mp.solutions.hands)
# ═══════════════════════════════════════════════════════════════════════════════

class _OldAPIBackend:
    def __init__(self, max_hands: int, detect_conf: float, track_conf: float):
        import mediapipe as mp
        self._hands = mp.solutions.hands.Hands(
            max_num_hands            = max_hands,
            min_detection_confidence = detect_conf,
            min_tracking_confidence  = track_conf,
        )

    def process(self, rgb: np.ndarray) -> CompatResult:
        raw = self._hands.process(rgb)
        hands: List[HandResult] = []
        if raw.multi_hand_landmarks:
            for i, lm_proto in enumerate(raw.multi_hand_landmarks):
                label = raw.multi_handedness[i].classification[0].label
                score = raw.multi_handedness[i].classification[0].score
                lms   = [Landmark(l.x, l.y, l.z) for l in lm_proto.landmark]
                hands.append(HandResult(label=label, score=score,
                                        landmarks=LandmarkList(lms)))
        return CompatResult(hands=hands)

    def close(self):
        self._hands.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Backend: New Tasks API  (mediapipe 0.10.x)
# ═══════════════════════════════════════════════════════════════════════════════

_MODEL_FILENAME = "hand_landmarker.task"
_MODEL_URL      = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)


def _get_model_path() -> str:
    """
    Return the path to hand_landmarker.task, downloading it on first run.
    Cached in ~/.cache/mediapipe/ so future runs are instant.
    """
    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "mediapipe")
    os.makedirs(cache_dir, exist_ok=True)
    model_path = os.path.join(cache_dir, _MODEL_FILENAME)

    if os.path.exists(model_path) and os.path.getsize(model_path) > 100_000:
        return model_path

    # Need to download
    print(f"[MediaPipe] Downloading {_MODEL_FILENAME} (~34 MB, one-time) ...")
    print(f"[MediaPipe] Source: {_MODEL_URL}")
    print(f"[MediaPipe] Cache:  {model_path}")

    try:
        import urllib.request

        def _progress(count, block_size, total_size):
            pct = int(count * block_size * 100 / max(total_size, 1))
            bar = "#" * (pct // 4)
            print(f"\r  [{bar:<25}] {pct:3d}%", end="", flush=True)

        urllib.request.urlretrieve(_MODEL_URL, model_path, _progress)
        print()  # newline after progress bar
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        print(f"[MediaPipe] Download complete: {size_mb:.1f} MB")
        return model_path

    except Exception as e:
        # Clean up partial file
        if os.path.exists(model_path):
            os.remove(model_path)
        raise RuntimeError(
            f"\n[MediaPipe] Could not download hand_landmarker.task: {e}\n"
            f"\nPlease download it manually from:\n  {_MODEL_URL}\n"
            f"and place it at:\n  {model_path}\n"
        ) from e


class _NewAPIBackend:
    def __init__(self, max_hands: int, detect_conf: float, track_conf: float):
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            HandLandmarker, HandLandmarkerOptions, RunningMode
        )

        model_path = _get_model_path()
        options    = HandLandmarkerOptions(
            base_options               = BaseOptions(model_asset_path=model_path),
            running_mode               = RunningMode.VIDEO,
            num_hands                  = max_hands,
            min_hand_detection_confidence = detect_conf,
            min_hand_presence_confidence  = detect_conf,
            min_tracking_confidence    = track_conf,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._timestamp  = 0

        # Store connections for drawing
        from mediapipe.tasks.python.vision.hand_landmarker import HandLandmarksConnections
        self._connections = HandLandmarksConnections.HAND_CONNECTIONS

    def process(self, rgb: np.ndarray) -> CompatResult:
        from mediapipe.tasks.python.vision.core.image import Image
        from mediapipe.tasks.python.vision.core.image import ImageFormat

        self._timestamp += 33   # ~30 fps in ms
        mp_image = Image(image_format=ImageFormat.SRGB, data=rgb)
        raw = self._landmarker.detect_for_video(mp_image, self._timestamp)

        hands: List[HandResult] = []
        if raw.hand_landmarks:
            for i, lm_list in enumerate(raw.hand_landmarks):
                # handedness: Category with .category_name = "Left"/"Right"
                if raw.handedness and i < len(raw.handedness):
                    cat   = raw.handedness[i][0]
                    label = cat.display_name or cat.category_name or "Right"
                    # Tasks API flips Left/Right vs old API — normalise here
                    label = "Left" if label == "Right" else "Right"
                    score = cat.score or 1.0
                else:
                    label, score = "Right", 1.0

                lms = [Landmark(l.x, l.y, l.z) for l in lm_list]
                hands.append(HandResult(label=label, score=score,
                                        landmarks=LandmarkList(lms)))
        return CompatResult(hands=hands)

    def close(self):
        self._landmarker.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Public: HandTracker
# ═══════════════════════════════════════════════════════════════════════════════

class HandTracker:
    """
    Unified hand tracker — picks the correct backend automatically.

    Example
    -------
        tracker = HandTracker(max_hands=2, detect_conf=0.75, track_conf=0.70)
        while True:
            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = tracker.process(rgb)
            for hand in result.hands:
                ...
        tracker.close()
    """

    def __init__(self,
                 max_hands:   int   = 2,
                 detect_conf: float = 0.75,
                 track_conf:  float = 0.70):

        self._backend_name = "unknown"

        # Try old API first
        try:
            import mediapipe as mp
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
                self._backend = _OldAPIBackend(max_hands, detect_conf, track_conf)
                self._backend_name = "solutions (classic)"
                print("[MediaPipe] Using classic solutions API")
                return
        except Exception as e:
            print(f"[MediaPipe] Classic API unavailable: {e}")

        # Fall back to new Tasks API
        try:
            self._backend = _NewAPIBackend(max_hands, detect_conf, track_conf)
            self._backend_name = "Tasks API (0.10.x)"
            print("[MediaPipe] Using Tasks API")
        except Exception as e:
            raise RuntimeError(
                f"\n[MediaPipe] Both APIs failed.\n"
                f"Tasks API error: {e}\n\n"
                f"Try: pip install \"mediapipe>=0.10.13\" and ensure internet access\n"
                f"for the one-time model download (~34 MB)."
            ) from e

    def process(self, rgb_frame: np.ndarray) -> CompatResult:
        """Process one RGB frame. Returns CompatResult."""
        return self._backend.process(rgb_frame)

    def close(self):
        """Release resources."""
        self._backend.close()

    @property
    def backend(self) -> str:
        return self._backend_name


# ═══════════════════════════════════════════════════════════════════════════════
#  Public: DrawLandmarks
# ═══════════════════════════════════════════════════════════════════════════════

def DrawLandmarks(frame: np.ndarray, hand: HandResult,
                  dot_color=_LANDMARK_COLOR, line_color=_CONNECTION_COLOR,
                  dot_radius: int = 3, line_thickness: int = 2):
    """
    Draw hand skeleton on a BGR frame in-place.
    Works identically regardless of which backend is in use.
    """
    H, W = frame.shape[:2]
    lm = hand.landmarks.landmark

    # Draw connections first (under dots)
    for a, b in HAND_CONNECTIONS:
        ax, ay = int(lm[a].x * W), int(lm[a].y * H)
        bx, by = int(lm[b].x * W), int(lm[b].y * H)
        cv2.line(frame, (ax, ay), (bx, by), line_color, line_thickness, cv2.LINE_AA)

    # Draw landmark dots on top
    for l in lm:
        px, py = int(l.x * W), int(l.y * H)
        cv2.circle(frame, (px, py), dot_radius, dot_color, -1, cv2.LINE_AA)


# ═══════════════════════════════════════════════════════════════════════════════
#  Backward-compat: mp.solutions-style objects exposed at module level
# ═══════════════════════════════════════════════════════════════════════════════
# These let existing code that still does:
#   mp_hands = mp.solutions.hands
#   mp_draw  = mp.solutions.drawing_utils
# work if it imports from here instead.

class _HandsSolutionsShim:
    """Shim that looks like mp.solutions.hands to old code."""
    HAND_CONNECTIONS = HAND_CONNECTIONS

    class Hands:
        """Drop-in replacement for mp.solutions.hands.Hands()."""
        def __init__(self, max_num_hands=2,
                     min_detection_confidence=0.75,
                     min_tracking_confidence=0.70):
            self._tracker = HandTracker(max_num_hands,
                                        min_detection_confidence,
                                        min_tracking_confidence)

        def process(self, rgb: np.ndarray):
            return self._tracker.process(rgb)

        def close(self):
            self._tracker.close()


class _DrawingUtilsShim:
    """Shim that looks like mp.solutions.drawing_utils to old code."""

    class DrawingSpec:
        def __init__(self, color=(0,200,255), thickness=2, circle_radius=3):
            self.color         = color
            self.thickness     = thickness
            self.circle_radius = circle_radius

    @staticmethod
    def draw_landmarks(frame, hand_landmarks,
                       connections=None,
                       landmark_drawing_spec=None,
                       connection_drawing_spec=None):
        """
        Mimics mp.solutions.drawing_utils.draw_landmarks().
        hand_landmarks can be either LandmarkList (CompatResult style)
        or a HandResult object.
        """
        # Normalise: accept both LandmarkList and HandResult
        if isinstance(hand_landmarks, HandResult):
            lm_list = hand_landmarks.landmarks.landmark
        elif isinstance(hand_landmarks, LandmarkList):
            lm_list = hand_landmarks.landmark
        else:
            lm_list = hand_landmarks.landmark  # raw old-API proto

        # Extract drawing specs
        dot_r   = 3
        dot_c   = _LANDMARK_COLOR
        line_c  = _CONNECTION_COLOR
        line_t  = 2

        if landmark_drawing_spec and hasattr(landmark_drawing_spec, "circle_radius"):
            dot_r = landmark_drawing_spec.circle_radius
            dot_c = landmark_drawing_spec.color
        if connection_drawing_spec and hasattr(connection_drawing_spec, "thickness"):
            line_t = connection_drawing_spec.thickness
            line_c = connection_drawing_spec.color

        H, W = frame.shape[:2]
        _conns = connections or HAND_CONNECTIONS

        # Normalise connections — Tasks API uses Connection objects, old API uses tuples
        conn_pairs = []
        for c in _conns:
            if hasattr(c, "start"):
                conn_pairs.append((c.start, c.end))
            elif isinstance(c, (tuple, list)):
                conn_pairs.append((c[0], c[1]))

        for a, b in conn_pairs:
            ax, ay = int(lm_list[a].x * W), int(lm_list[a].y * H)
            bx, by = int(lm_list[b].x * W), int(lm_list[b].y * H)
            cv2.line(frame, (ax, ay), (bx, by), line_c, line_t, cv2.LINE_AA)

        for l in lm_list:
            px, py = int(l.x * W), int(l.y * H)
            cv2.circle(frame, (px, py), dot_r, dot_c, -1, cv2.LINE_AA)


# Module-level shim objects for drop-in compatibility
mp_hands_shim = _HandsSolutionsShim()
mp_draw_shim  = _DrawingUtilsShim()