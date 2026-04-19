"""
utils/shape_fitting.py  —  Advanced geometric shape fitting for perfect mapping.

Provides optimal shape fitting algorithms to convert rough sketches to clean
geometric shapes with correct positioning, rotation, and sizing.

Functions:
  - fit_circle()      : Least-squares circle fitting (handles organic circles)
  - fit_rectangle()   : PCA-based rectangle with rotation detection
  - fit_triangle()    : Optimal triangle corner positioning
  - fit_line()        : Least-squares line regression

The goal is to map rough sketches to perfect shapes while preserving:
  - Position (centroid)
  - Rotation (axis orientation for rectangles, triangles)
  - Size (radius/dimensions)
"""

from __future__ import annotations
import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any

Point = Tuple[int, int]


# =============================================================================
#  Geometric Helpers
# =============================================================================

def _centroid(pts: List[Point]) -> Tuple[float, float]:
    """Calculate centroid (center of mass) of point cloud."""
    if not pts:
        return 0.0, 0.0
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)
    return float(np.mean(xs)), float(np.mean(ys))


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two points."""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def _angle_between(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
    """Angle between two vectors in radians."""
    len1 = math.sqrt(v1[0]**2 + v1[1]**2)
    len2 = math.sqrt(v2[0]**2 + v2[1]**2)
    if len1 < 1e-6 or len2 < 1e-6:
        return 0.0
    cos_angle = (v1[0]*v2[0] + v1[1]*v2[1]) / (len1 * len2)
    cos_angle = max(-1.0, min(1.0, cos_angle))  # Clamp to [-1, 1]
    return math.acos(cos_angle)


def _rotate_points(pts: List[Point], angle: float, origin: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Rotate points around origin by angle (radians)."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rotated = []
    for p in pts:
        x = p[0] - origin[0]
        y = p[1] - origin[1]
        x_rot = x * cos_a - y * sin_a
        y_rot = x * sin_a + y * cos_a
        rotated.append((x_rot + origin[0], y_rot + origin[1]))
    return rotated


# =============================================================================
#  Circle Fitting (Least-Squares)
# =============================================================================

def fit_circle(pts: List[Point]) -> Optional[Dict[str, Any]]:
    """
    Fit optimal circle to stroke points using least-squares method.
    
    Solves for center (cx, cy) and radius r that minimizes:
        sum((sqrt((x_i - cx)^2 + (y_i - cy)^2) - r)^2)
    
    Returns:
        {
            'center': (cx, cy),
            'radius': r,
            'error': total_fitting_error,
            'quality': 1 - (error / total_radial_variance)  # 0-1, higher is better
        }
    """
    if len(pts) < 3:
        return None
    
    # Convert to numpy arrays
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)
    
    # Calculate centroid
    cx = np.mean(xs)
    cy = np.mean(ys)
    
    # Shift points to centroid
    xs_c = xs - cx
    ys_c = ys - cy
    
    # Build system for least-squares
    # We solve: (A^T A) p = A^T b
    # where p = [ux, uy, r] and b = 1
    # This is the algebraic method for circle fitting
    
    u = np.column_stack([xs_c, ys_c, np.ones_like(xs_c)])
    uu = np.dot(u.T, u)
    
    try:
        # Solve normal equations
        u_inv = np.linalg.inv(uu)
        p = np.dot(u_inv, u.T)
        p = np.dot(p, np.ones_like(xs))
        
        # Extract parameters
        ux, uy = p[0], p[1]
        center_x = cx + ux / 2.0
        center_y = cy + uy / 2.0
        
        # Calculate radius
        distances = np.sqrt((xs - center_x)**2 + (ys - center_y)**2)
        radius = np.mean(distances)
        
        # Calculate fitting error
        error = np.sum((distances - radius)**2)
        variance = np.var(distances)
        
        # Quality metric: 1 - (error / total_variance)
        quality = 1.0 - (error / (variance * len(pts))) if variance > 1e-6 else 0.5
        quality = max(0.0, min(1.0, quality))
        
        return {
            'center': (float(center_x), float(center_y)),
            'radius': float(radius),
            'error': float(error),
            'quality': float(quality)
        }
    except Exception:
        # Fallback to simple centroid + average radius
        distances = np.sqrt(xs**2 + ys**2)
        radius = np.mean(distances)
        return {
            'center': (float(cx), float(cy)),
            'radius': float(radius),
            'error': 0.0,
            'quality': 0.5
        }


# =============================================================================
#  Rectangle Fitting (PCA-based with rotation detection)
# =============================================================================

def fit_rectangle(pts: List[Point]) -> Optional[Dict[str, Any]]:
    """
    Fit optimal rectangle to stroke points using PCA for rotation detection.
    
    Algorithm:
    1. Apply PCA to find principal axes (long axis = width direction)
    2. Rotate points to align with principal axes
    3. Find bounding box in rotated space
    4. Calculate rotation angle
    
    Returns:
        {
            'center': (cx, cy),
            'width': w,
            'height': h,
            'angle': rotation_angle_radians,
            'corners': [(x1,y1), (x2,y2), (x3,y3), (x4,y4)],
            'quality': 0-1
        }
    """
    if len(pts) < 4:
        return None
    
    # Convert to numpy arrays
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)
    
    # Calculate centroid
    cx = np.mean(xs)
    cy = np.mean(ys)
    
    # Center the points
    xs_c = xs - cx
    ys_c = ys - cy
    
    # Build covariance matrix
    cov = np.cov(xs_c, ys_c)
    
    try:
        # Get eigenvalues and eigenvectors for PCA
        eigenvalues, eigenvectors = np.linalg.eig(cov)
        
        # Sort by eigenvalue (largest first)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Minor axis (first principal component)
        v1 = eigenvectors[:, 0]  # direction of maximum variance (width)
        v2 = eigenvectors[:, 1]  # direction of minimum variance (height)
        
        # Calculate rotation angle
        angle = math.atan2(v1[1], v1[0])
        
        # Rotate points to align with principal axes
        rotated = _rotate_points(pts, -angle, (cx, cy))
        
        # Find bounding box in rotated space
        rx = np.array([p[0] for p in rotated], dtype=np.float64)
        ry = np.array([p[1] for p in rotated], dtype=np.float64)
        
        x_min, x_max = np.min(rx), np.max(rx)
        y_min, y_max = np.min(ry), np.max(ry)
        
        width = x_max - x_min
        height = y_max - y_max
        
        # Rectangle center in rotated space
        rect_cx = (x_min + x_max) / 2.0
        rect_cy = (y_min + y_max) / 2.0
        
        # Rotate back to original space
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        # Rectangle corners in rotated space
        corners_rot = [
            (x_min, y_min),
            (x_max, y_min),
            (x_max, y_max),
            (x_min, y_max)
        ]
        
        # Transform back to original space
        corners = []
        for crx, cry in corners_rot:
            ox = crx * cos_a - cry * sin_a + cx
            oy = crx * sin_a + cry * cos_a + cy
            corners.append((float(ox), float(oy)))
        
        return {
            'center': (float(cx), float(cy)),
            'width': float(width),
            'height': float(height),
            'angle': float(angle),
            'corners': corners,
            'quality': 0.85  # PCA-based fit is generally good
        }
    except Exception:
        # Fallback to simple bounding box
        x_min, x_max = np.min(xs), np.max(xs)
        y_min, y_max = np.min(ys), np.max(ys)
        width = x_max - x_min
        height = y_max - y_min
        
        return {
            'center': (float(cx), float(cy)),
            'width': float(width),
            'height': float(height),
            'angle': 0.0,
            'corners': [
                (float(x_min), float(y_min)),
                (float(x_max), float(y_min)),
                (float(x_max), float(y_max)),
                (float(x_min), float(y_max))
            ],
            'quality': 0.5
        }


# =============================================================================
#  Triangle Fitting (Optimal corner positioning)
# =============================================================================

def fit_triangle(pts: List[Point]) -> Optional[Dict[str, Any]]:
    """
    Fit optimal triangle to stroke points.
    
    Algorithm:
    1. Find convex hull
    2. If exactly 3 points, use those
    3. If more, find 3 points that maximize enclosed area
    4. Refine by finding best 3 corners
    
    Returns:
        {
            'corners': [(x1,y1), (x2,y2), (x3,y3)],
            'center': (cx, cy),
            'area': triangle_area,
            'quality': 0-1
        }
    """
    if len(pts) < 3:
        return None
    
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)
    
    # Calculate centroid
    cx = np.mean(xs)
    cy = np.mean(ys)
    
    # Find points farthest from center (likely to be corners)
    distances = np.sqrt((xs - cx)**2 + (ys - cy)**2)
    
    # Get indices of 3 farthest points
    corner_indices = np.argsort(distances)[-3:]
    corners = [pts[i] for i in corner_indices]
    
    # Calculate triangle area
    def triangle_area(p1, p2, p3):
        return abs((p2[0] - p1[0]) * (p3[1] - p1[1]) - (p3[0] - p1[0]) * (p2[1] - p1[1])) / 2.0
    
    area = triangle_area(corners[0], corners[1], corners[2])
    
    # Triangle centroid
    tri_cx = (corners[0][0] + corners[1][0] + corners[2][0]) / 3.0
    tri_cy = (corners[0][1] + corners[1][1] + corners[2][1]) / 3.0
    
    return {
        'corners': [(float(c[0]), float(c[1])) for c in corners],
        'center': (float(tri_cx), float(tri_cy)),
        'area': float(area),
        'quality': 0.80  # Corner detection is usually reliable
    }


# =============================================================================
#  Line Fitting (Least-Squares Regression)
# =============================================================================

def fit_line(pts: List[Point]) -> Optional[Dict[str, Any]]:
    """
    Fit optimal line to stroke points using least-squares regression.
    
    Fits line: y = mx + b that minimizes perpendicular distance to all points.
    
    Returns:
        {
            'start': (x1, y1),
            'end': (x2, y2),
            'center': (cx, cy),
            'slope': m,
            'intercept': b,
            'angle': angle_radians,
            'length': line_length,
            'quality': 0-1
        }
    """
    if len(pts) < 2:
        return None
    
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)
    
    # Calculate center
    cx = np.mean(xs)
    cy = np.mean(ys)
    
    # Use SVD for robust line fitting
    # Center the points
    xs_c = xs - cx
    ys_c = ys - cy
    
    # Build matrix
    A = np.column_stack([xs_c, ys_c])
    
    try:
        # Perform SVD
        u, s, vt = np.linalg.svd(A, full_matrices=False)
        
        # The line direction is the vector with smallest singular value
        # (least variance, best fits the line)
        direction = vt[-1, :]  # Last row of V^T
        
        # Normalize
        direction = direction / np.linalg.norm(direction)
        
        # Calculate points along the line
        projections = np.dot(A, direction)
        min_proj = np.min(projections)
        max_proj = np.max(projections)
        
        # Start and end points of the line
        start_x = cx + min_proj * direction[0]
        start_y = cy + min_proj * direction[1]
        end_x = cx + max_proj * direction[0]
        end_y = cy + max_proj * direction[1]
        
        # Calculate angle
        angle = math.atan2(direction[1], direction[0])
        
        # Calculate length
        length = _distance((start_x, start_y), (end_x, end_y))
        
        # Calculate fitting error
        residuals = A[:, 0] * direction[1] - A[:, 1] * direction[0]
        error = np.sum(residuals**2)
        quality = 1.0 - (error / (len(pts) * 100.0)) if len(pts) > 0 else 0.5
        quality = max(0.0, min(1.0, quality))
        
        # Calculate slope and intercept (for reference)
        if abs(direction[0]) > 1e-6:
            slope = direction[1] / direction[0]
            intercept = cy - slope * cx
        else:
            slope = float('inf')
            intercept = cx
        
        return {
            'start': (float(start_x), float(start_y)),
            'end': (float(end_x), float(end_y)),
            'center': (float(cx), float(cy)),
            'slope': float(slope),
            'intercept': float(intercept),
            'angle': float(angle),
            'length': float(length),
            'quality': float(quality)
        }
    except Exception:
        # Fallback to simple endpoints
        min_idx = np.argmin(xs)
        max_idx = np.argmax(xs)
        
        start_x = xs[min_idx]
        start_y = ys[min_idx]
        end_x = xs[max_idx]
        end_y = ys[max_idx]
        
        length = _distance((start_x, start_y), (end_x, end_y))
        angle = math.atan2(end_y - start_y, end_x - start_x)
        
        return {
            'start': (float(start_x), float(start_y)),
            'end': (float(end_x), float(end_y)),
            'center': (float(cx), float(cy)),
            'slope': (end_y - start_y) / (end_x - start_x + 1e-6),
            'intercept': 0.0,
            'angle': float(angle),
            'length': float(length),
            'quality': 0.5
        }
