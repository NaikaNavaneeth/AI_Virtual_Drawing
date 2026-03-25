"""
utils/gesture.py  —  Gesture recognition utilities.

Provides rule-based primitives used both standalone and as fallback
for the CNN classifier.

  fingers_up()          - per-finger up/down state
  classify_gesture()    - named gesture (rule-based)
  is_open_palm()        - all fingers extended (robust, requires ALL fingers up + spread)
  pinch_distance()      - normalised thumb-index distance
  palm_center_px()      - pixel coord of palm centre
  inter_palm_distance() - pixel distance between two palms

FIXES vs original:
  - open_palm now requires ALL 5 fingers clearly extended AND spread wide.
    A compressed or slightly-open hand no longer triggers clearing.
  - Added palm_openness_score() for a more graded detection.
  - Higher spread threshold + per-finger extension depth check to avoid
    false positives from half-closed palms.
"""

from __future__ import annotations
import math
from typing import List, Tuple

# -- MediaPipe landmark indices -----------------------------------------------
WRIST  = 0
TIPS   = [4, 8, 12, 16, 20]
PIPS   = [3, 6, 10, 14, 18]
MCPS   = [2, 5, 9, 13, 17]   # metacarpophalangeal joints (knuckles)


# -- Helpers ------------------------------------------------------------------
def _dist2d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# -- Core: fingers_up ---------------------------------------------------------
def fingers_up(hand_landmarks, hand_label: str) -> List[bool]:
    """
    Returns [thumb, index, middle, ring, pinky] booleans.
    True = finger extended/up.
    Accounts for left/right hand mirror difference.
    """
    lm = hand_landmarks.landmark
    result: List[bool] = []

    # Thumb: compare x position relative to palm
    if hand_label == "Right":
        result.append(lm[4].x < lm[3].x)
    else:
        result.append(lm[4].x > lm[3].x)

    # Index -> Pinky: tip.y < pip.y means extended
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        result.append(lm[tip].y < lm[pip].y)

    return result


def _finger_extension_depth(lm, tip_idx: int, mcp_idx: int) -> float:
    """
    Returns how far the fingertip is above the MCP joint (knuckle) in
    normalised coordinates. Positive = extended, negative = curled under.
    This is MORE robust than just tip.y < pip.y because it measures
    how MUCH the finger is extended, not just marginally.
    """
    return lm[mcp_idx].y - lm[tip_idx].y   # positive when tip is above knuckle


# -- Named gesture classifier (rule-based) ------------------------------------
def classify_gesture(hand_landmarks, hand_label: str) -> str:
    """
    Rule-based gesture classifier. Used as:
    1. Standalone when no CNN model is loaded.
    2. Fallback when CNN confidence < threshold.

    Returns a gesture name string.

    KEY FIX: open_palm now requires:
      (a) ALL 4 fingers clearly extended (not just marginally),
      (b) Thumb extended,
      (c) Thumb-to-pinky spread > 0.35 (was 0.25),
      (d) Average finger extension depth > 0.04 -- prevents a
          compressed/bent-finger hand from triggering clear.
    """
    lm  = hand_landmarks.landmark
    fup = fingers_up(hand_landmarks, hand_label)
    thumb, index, middle, ring, pinky = fup

    # -- Draw: only index finger up -------------------------------------------
    if index and not middle and not ring and not pinky:
        return "draw"

    # -- Erase: index + middle up ---------------------------------------------
    if index and middle and not ring and not pinky:
        return "erase"

    # -- Select: index + middle + ring up -------------------------------------
    if index and middle and ring and not pinky:
        return "select"

    # -- Open palm (CLEAR) -- robust multi-condition check --------------------
    # Condition 1: basic fingers_up says all fingers up
    if all(fup):
        thumb_tip = lm[4]
        pinky_tip = lm[20]

        # Condition 2: thumb-to-pinky spread (normalised coords)
        spread_dist = math.hypot(
            thumb_tip.x - pinky_tip.x,
            thumb_tip.y - pinky_tip.y
        )

        # Condition 3: EACH finger must be clearly extended above its knuckle
        # finger tip indices:  8, 12, 16, 20  |  MCP indices: 5, 9, 13, 17
        finger_pairs = [(8, 5), (12, 9), (16, 13), (20, 17)]
        depths = [_finger_extension_depth(lm, tip, mcp) for tip, mcp in finger_pairs]
        avg_depth = sum(depths) / len(depths)
        min_depth = min(depths)  # even the least extended finger must clear the bar

        palm_open = (
            spread_dist > 0.35      # fingers must be spread wide
            and avg_depth > 0.04    # fingers must be clearly extended on average
            and min_depth > -0.01   # no single finger can be curled behind knuckle
        )

        if palm_open:
            return "open_palm"

        # If all fup is True but conditions not met, fall through to idle
        # (prevents false clears from half-open hands)

    # -- Fist -----------------------------------------------------------------
    if not any(fup):
        return "fist"

    # -- Thumbs up ------------------------------------------------------------
    if thumb and not index and not middle and not ring and not pinky:
        return "thumbs_up"

    # -- Pinch: thumb and index tips close, others down -----------------------
    tip_thumb = (lm[4].x, lm[4].y)
    tip_index = (lm[8].x, lm[8].y)
    dist = _dist2d(tip_thumb, tip_index)
    if dist < 0.06 and not middle and not ring and not pinky:
        return "pinch"

    # -- OK sign: thumb-index ring, middle+ring+pinky extended ----------------
    if dist < 0.07 and middle and ring and pinky:
        return "ok"

    return "idle"


# -- Convenience predicates ---------------------------------------------------
def is_open_palm(hand_landmarks, hand_label: str) -> bool:
    return classify_gesture(hand_landmarks, hand_label) == "open_palm"


def palm_openness_score(hand_landmarks) -> float:
    """
    Returns a 0.0-1.0 score of how open the palm is.
    Useful for progress bars or debugging.
    """
    lm = hand_landmarks.landmark
    finger_pairs = [(8, 5), (12, 9), (16, 13), (20, 17)]
    depths = [_finger_extension_depth(lm, tip, mcp) for tip, mcp in finger_pairs]
    avg_depth = sum(depths) / len(depths)
    thumb_tip = lm[4]; pinky_tip = lm[20]
    spread = math.hypot(thumb_tip.x - pinky_tip.x, thumb_tip.y - pinky_tip.y)
    # Combine: normalise each component
    score = min(1.0, (avg_depth / 0.08) * 0.5 + (spread / 0.45) * 0.5)
    return max(0.0, score)


def pinch_distance(hand_landmarks) -> float:
    """Normalised (0-1) distance between thumb tip and index tip."""
    lm = hand_landmarks.landmark
    return math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)


def palm_center_px(hand_landmarks, w: int, h: int) -> Tuple[int, int]:
    """Pixel coordinates of palm centre (average of wrist + 4 MCP joints)."""
    lm  = hand_landmarks.landmark
    ids = [0, 5, 9, 13, 17]
    cx  = int(sum(lm[i].x for i in ids) / len(ids) * w)
    cy  = int(sum(lm[i].y for i in ids) / len(ids) * h)
    return cx, cy


def inter_palm_distance(lm_a, lm_b, w: int, h: int) -> float:
    """Pixel distance between two palm centres."""
    ax, ay = palm_center_px(lm_a, w, h)
    bx, by = palm_center_px(lm_b, w, h)
    return math.hypot(ax - bx, ay - by)


def fingertip_px(hand_landmarks, w: int, h: int, finger: int = 1) -> Tuple[int, int]:
    """
    Pixel coordinate of a fingertip.
    finger: 0=thumb, 1=index, 2=middle, 3=ring, 4=pinky
    """
    tip_ids = [4, 8, 12, 16, 20]
    lm = hand_landmarks.landmark
    t  = lm[tip_ids[finger]]
    return int(t.x * w), int(t.y * h)
