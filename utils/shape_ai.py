"""
utils/shape_ai.py  —  AI-assisted shape correction + Sketch-to-3D mapping.

detect_and_snap()  — classify a stroke and return a clean geometric version.
sketch_to_3d()     — map a 2D shape name to a 3D object descriptor.
"""

from __future__ import annotations
import math
import numpy as np
from typing import List, Optional, Tuple, Dict, Any

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import SKETCH_TO_3D

Point = Tuple[int, int]


# ── Geometry helpers ─────────────────────────────────────────────────────────

def _bounding_box(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _perimeter(pts):
    total = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        total += math.hypot(a[0] - b[0], a[1] - b[1])
    return total


def _area_shoelace(pts):
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def _circularity(pts):
    p = _perimeter(pts)
    if p < 1e-6:
        return 0.0
    a = _area_shoelace(pts)
    return (4 * math.pi * a) / (p * p)


def _aspect_ratio(pts):
    x0, y0, x1, y1 = _bounding_box(pts)
    w = max(x1 - x0, 1)
    h = max(y1 - y0, 1)
    return max(w, h) / min(w, h)


def _stroke_length(pts):
    total = 0.0
    for i in range(1, len(pts)):
        total += math.hypot(pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1])
    return total


def _straightness(pts):
    if len(pts) < 2:
        return 0.0
    end = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    length = _stroke_length(pts)
    if length < 1e-6:
        return 1.0
    return end / length


def _closure_ratio(pts):
    gap = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    p   = _perimeter(pts)
    if p < 1e-6:
        return 1.0
    return gap / p


# ── Sub-sampler ──────────────────────────────────────────────────────────────

def _subsample(pts, n: int = 64):
    if len(pts) <= n:
        return pts
    indices = np.linspace(0, len(pts) - 1, n, dtype=int)
    return [pts[i] for i in indices]


# ── Clean shape generators ───────────────────────────────────────────────────

def _make_circle(pts, n: int = 120):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = int(sum(xs) / len(xs))
    cy = int(sum(ys) / len(ys))
    r  = int(max(max(xs) - min(xs), max(ys) - min(ys)) / 2)
    r  = max(r, 10)
    return [(int(cx + r * math.cos(2 * math.pi * i / n)),
             int(cy + r * math.sin(2 * math.pi * i / n))) for i in range(n)]


def _make_rectangle(pts):
    x0, y0, x1, y1 = _bounding_box(pts)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _make_triangle(pts):
    x0, y0, x1, y1 = _bounding_box(pts)
    mid_x = (x0 + x1) // 2
    return [(mid_x, y0), (x1, y1), (x0, y1), (mid_x, y0)]


def _make_line(pts):
    return [pts[0], pts[-1]]


# ── RDP simplification ───────────────────────────────────────────────────────

def _rdp_simplify(pts, epsilon: float):
    if len(pts) < 3:
        return pts
    start, end = np.array(pts[0]), np.array(pts[-1])
    line_vec   = end - start
    line_len   = np.linalg.norm(line_vec)
    if line_len < 1e-9:
        return [pts[0], pts[-1]]
    line_unit = line_vec / line_len
    dists = []
    for p in pts[1:-1]:
        p_vec  = np.array(p) - start
        proj   = np.dot(p_vec, line_unit)
        proj_pt= start + proj * line_unit
        dists.append(np.linalg.norm(np.array(p) - proj_pt))

    max_idx = int(np.argmax(dists)) + 1
    if dists[max_idx - 1] > epsilon:
        left  = _rdp_simplify(pts[:max_idx + 1], epsilon)
        right = _rdp_simplify(pts[max_idx:], epsilon)
        return left[:-1] + right
    return [pts[0], pts[-1]]


# ── Public: detect_and_snap ──────────────────────────────────────────────────

def detect_and_snap(
    raw_pts: List[Point],
    min_points: int = 12,
    confidence_threshold: float = 0.55,
) -> Tuple[Optional[str], Optional[List[Point]]]:
    """
    Analyse raw_pts and attempt to classify + clean the shape.
    Returns (shape_name, clean_points) or (None, None).
    
    OPTIMIZED: Better thresholds to prevent rectangle→circle misclassification.
    KEY FIX: Circle threshold now 0.90+ (subsampling makes rectangles look circular).
    """
    if len(raw_pts) < min_points:
        return None, None

    sub  = _subsample(raw_pts, 64)
    circ = _circularity(sub)
    ar   = _aspect_ratio(sub)
    strt = _straightness(sub)
    clos = _closure_ratio(sub)

    # ── Line detection (straightness wins) ───────────────────────────────────
    if strt > 0.88:
        return "line", _make_line(raw_pts)

    # ── Try to detect corners (indicates rectangle) ──────────────────────────
    # RDP simplification will reduce a rectangle to 4 corners, a circle stays round
    simplified = _rdp_simplify(sub, epsilon=5)  # Tighter epsilon for corner detection
    corner_count = len(simplified)
    
    # If we have 4 corners (eps=5) or slightly more, likely a rectangle/square
    if 4 <= corner_count <= 6 and ar < 4.0 and clos < 0.30:
        return "square", _make_rectangle(raw_pts)

    # ── Circle detection (VERY strict threshold to avoid false positives) ────
    # After subsampling & considering actual metrics:
    # - Rectangles: circ ~0.79, Circle: circ ~0.99
    # - Only detect as circle if VERY circular
    if circ > 0.90 and clos < 0.15 and ar < 1.4:
        return "circle", _make_circle(raw_pts)

    # ── Triangle detection ───────────────────────────────────────────────────
    if 3 <= corner_count <= 4 and clos < 0.30:
        return "triangle", _make_triangle(raw_pts)

    return None, None


# ── Public: sketch_to_3d ─────────────────────────────────────────────────────

def sketch_to_3d(shape_name: str) -> Optional[Dict[str, Any]]:
    """
    Map a detected 2D shape to a 3D object descriptor.

    Returns a dict with keys:
        type    – "sphere" | "cube" | "pyramid" | "cylinder"
        label   – human-readable name
        color   – default OpenGL colour as (R, G, B) floats 0-1
        scale   – initial display scale

    Returns None if the shape has no mapping.
    """
    mapping: Dict[str, Dict[str, Any]] = {
        "circle": {
            "type":  "sphere",
            "label": "Sphere",
            "color": (0.3, 0.6, 1.0),
            "scale": 1.0,
        },
        "square": {
            "type":  "cube",
            "label": "Cube",
            "color": (1.0, 0.5, 0.2),
            "scale": 1.0,
        },
        "triangle": {
            "type":  "pyramid",
            "label": "Pyramid",
            "color": (0.4, 0.9, 0.4),
            "scale": 1.0,
        },
        "line": {
            "type":  "cylinder",
            "label": "Cylinder",
            "color": (0.9, 0.3, 0.7),
            "scale": 1.0,
        },
    }
    return mapping.get(shape_name)


# ── Bounding box centre (used for sketch-to-3D placement) ────────────────────

def stroke_center(pts: List[Point]) -> Tuple[int, int]:
    """Return the pixel centre of the bounding box of a stroke."""
    x0, y0, x1, y1 = _bounding_box(pts)
    return (x0 + x1) // 2, (y0 + y1) // 2


def stroke_size(pts: List[Point]) -> Tuple[int, int]:
    """Return (width, height) of the stroke's bounding box."""
    x0, y0, x1, y1 = _bounding_box(pts)
    return x1 - x0, y1 - y0
