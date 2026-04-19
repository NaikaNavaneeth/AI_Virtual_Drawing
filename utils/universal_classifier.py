"""
utils/universal_classifier.py — Universal shape and letter recognition with RL.

Handles:
- Geometric shapes (circle, rectangle, triangle, line)
- Letters (A-Z, a-z)
- Numbers (0-9)
- Novel shapes and symbols
- Learns from user feedback via reinforcement learning
"""

from __future__ import annotations
import numpy as np
import cv2
from typing import List, Tuple, Optional, Dict, Any
import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict

Point = Tuple[int, int]

# ──────────────────────────────────────────────────────────────────────────────
# Configuration and Data Structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Result of shape/letter classification."""
    category: str  # "shape", "letter", "number", "symbol"
    label: str     # "circle", "A", "5", etc.
    confidence: float  # 0.0-1.0
    alternatives: List[Tuple[str, float]] = field(default_factory=list)  # [(label, conf), ...]
    features: Dict[str, float] = field(default_factory=dict)  # Diagnostic features
    rl_adjusted: bool = False  # Whether RL adjusted the confidence

@dataclass
class FeedbackRecord:
    """User feedback on a classification."""
    predicted_label: str
    predicted_confidence: float
    correct_label: Optional[str]  # What user said it actually was
    user_accepted: bool  # True if user confirmed, False if corrected
    stroke_features: Dict[str, float]
    timestamp: float


# ──────────────────────────────────────────────────────────────────────────────
# Feature Extraction
# ──────────────────────────────────────────────────────────────────────────────

class FeatureExtractor:
    """Extract features from strokes to assist classification."""
    
    @staticmethod
    def extract(pts: List[Point]) -> Dict[str, float]:
        """Extract geometric and topological features from stroke."""
        if len(pts) < 3:
            return {}
        
        pts_arr = np.array(pts, dtype=np.float32)
        
        features = {
            # Shape properties
            'circularity': FeatureExtractor._circularity(pts),
            'aspect_ratio': FeatureExtractor._aspect_ratio(pts),
            'straightness': FeatureExtractor._straightness(pts),
            'closure_ratio': FeatureExtractor._closure_ratio(pts),
            'complexity': FeatureExtractor._complexity(pts),
            
            # Topological properties
            'num_corners': float(FeatureExtractor._count_corners(pts)),
            'stroke_length': float(FeatureExtractor._stroke_length(pts)),
            'stroke_density': FeatureExtractor._stroke_density(pts),
            
            # Writing style
            'velocity_variance': FeatureExtractor._velocity_variance(pts),
            'direction_changes': float(FeatureExtractor._count_direction_changes(pts)),
        }
        
        return features
    
    @staticmethod
    def _circularity(pts):
        """How circular is the shape? 0=line, 1=circle"""
        if len(pts) < 4:
            return 0.0
        pts = np.array(pts, dtype=np.float32)
        perimeter = float(cv2.arcLength(pts.reshape((-1, 1, 2)), False))
        area = float(cv2.contourArea(pts.reshape((-1, 1, 2))))
        if perimeter < 1e-6:
            return 0.0
        return (4 * np.pi * area) / (perimeter ** 2)
    
    @staticmethod
    def _aspect_ratio(pts):
        """Width/height ratio of bounding box"""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        return max(w, h) / max(min(w, h), 1)
    
    @staticmethod
    def _straightness(pts):
        """How straight is the overall stroke? 0=curved, 1=straight"""
        if len(pts) < 2:
            return 0.0
        direct = np.linalg.norm(np.array(pts[-1]) - np.array(pts[0]))
        actual = sum(np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1])) 
                    for i in range(1, len(pts)))
        if actual < 1e-6:
            return 1.0
        return float(direct / actual)
    
    @staticmethod
    def _closure_ratio(pts):
        """How closed is the shape? 0=closed, 1=open"""
        if len(pts) < 2:
            return 1.0
        gap = np.linalg.norm(np.array(pts[-1]) - np.array(pts[0]))
        perimeter = sum(np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1]))
                       for i in range(1, len(pts)))
        if perimeter < 1e-6:
            return 1.0
        return float(gap / perimeter)
    
    @staticmethod
    def _complexity(pts):
        """Stroke complexity (0-1, higher = more complex)"""
        if len(pts) < 4:
            return 0.0
        # Complexity = number of high-derivative points / total points
        curvatures = []
        for i in range(1, len(pts) - 1):
            v1 = np.array(pts[i]) - np.array(pts[i-1])
            v2 = np.array(pts[i+1]) - np.array(pts[i])
            angle = np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6), -1, 1))
            curvatures.append(angle)
        threshold = np.mean(curvatures) + np.std(curvatures)
        return float(sum(1 for c in curvatures if c > threshold) / len(curvatures))
    
    @staticmethod
    def _count_corners(pts):
        """Count number of sharp corners"""
        if len(pts) < 3:
            return 0
        pts_arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
        approx = cv2.approxPolyDP(pts_arr, epsilon=5, closed=False)
        return len(approx)
    
    @staticmethod
    def _stroke_length(pts):
        """Total stroke length"""
        return sum(np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1]))
                  for i in range(1, len(pts)))
    
    @staticmethod
    def _stroke_density(pts):
        """Points per unit area (density)"""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        area = w * h + 1
        return len(pts) / area
    
    @staticmethod
    def _velocity_variance(pts):
        """Variance in stroke velocity"""
        if len(pts) < 2:
            return 0.0
        velocities = [np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1]))
                     for i in range(1, len(pts))]
        if not velocities:
            return 0.0
        return float(np.var(velocities))
    
    @staticmethod
    def _count_direction_changes(pts):
        """Number of significant direction changes"""
        if len(pts) < 3:
            return 0
        changes = 0
        for i in range(1, len(pts) - 1):
            v1 = np.array(pts[i]) - np.array(pts[i-1])
            v2 = np.array(pts[i+1]) - np.array(pts[i])
            dot = np.dot(v1, v2)
            if dot < 0:  # Direction changed (angle > 90°)
                changes += 1
        return changes


# ──────────────────────────────────────────────────────────────────────────────
# Universal Classifier
# ──────────────────────────────────────────────────────────────────────────────

class UniversalShapeClassifier:
    """
    Unified classifier for shapes, letters, numbers, and symbols.
    Learns from user feedback via reinforcement learning.
    """
    
    def __init__(self):
        """Initialize classifier and load RL models."""
        self.feature_extractor = FeatureExtractor()
        
        # Category definitions
        self.categories = {
            'shapes': ['circle', 'rectangle', 'triangle', 'line', 'ellipse', 'polygon'],
            'letters': ([chr(i) for i in range(ord('A'), ord('Z')+1)] +
                       [chr(i) for i in range(ord('a'), ord('z')+1)]),
            'numbers': [str(i) for i in range(10)],
            'symbols': ['+', '-', '*', '/', '=', '!', '?', '@', '#', '$'],
        }
        
        # RL confidence adjustments (learned from feedback)
        # Maps (category, label) → confidence boost/penalty
        self.rl_adjustments: Dict[str, float] = {}
        self.error_counts: Dict[str, int] = {}  # Track errors per label
        self.success_counts: Dict[str, int] = {}  # Track successes per label
        
        self._load_rl_model()
    
    def classify(self, pts: List[Point]) -> ClassificationResult:
        """
        Classify a stroke as a shape, letter, number, or symbol.
        Uses ensemble of detectors + RL-learned confidence adjustments.
        """
        if len(pts) < 3:
            return ClassificationResult("unknown", "scribble", 0.1)
        
        features = self.feature_extractor.extract(pts)
        
        # Try each detector in order
        result = self._try_geometric_shapes(pts, features)
        if result is None:
            result = self._try_letters(pts, features)
        if result is None:
            result = self._try_numbers(pts, features)
        if result is None:
            result = self._try_symbols(pts, features)
        if result is None:
            result = self._try_novel_shapes(pts, features)
        
        if result is None:
            result = ClassificationResult("unknown", "unknown", 0.0)
        
        # Apply RL adjustments to confidence
        adjustment_key = f"{result.category}:{result.label}"
        if adjustment_key in self.rl_adjustments:
            adjustment = self.rl_adjustments[adjustment_key]
            result.confidence = np.clip(result.confidence + adjustment, 0.0, 1.0)
            result.rl_adjusted = True
        
        result.features = features
        return result
    
    def _try_geometric_shapes(self, pts: List[Point], features: Dict) -> Optional[ClassificationResult]:
        """Try to detect geometric shapes."""
        circ = features.get('circularity', 0)
        ar = features.get('aspect_ratio', 2)
        strt = features.get('straightness', 0)
        clos = features.get('closure_ratio', 1)
        corners = features.get('num_corners', 0)
        
        # Line
        if strt > 0.85:
            return ClassificationResult('shapes', 'line', min(0.95, strt))
        
        # Circle (very circular, closed)
        if circ > 0.85 and clos < 0.2 and ar < 1.5:
            return ClassificationResult('shapes', 'circle', min(0.95, circ))
        
        # Rectangle (4 corners, moderate aspect ratio)
        if 3.5 <= corners <= 5 and ar < 4.0 and clos < 0.3:
            return ClassificationResult('shapes', 'rectangle', 0.85)
        
        # Triangle (3-4 corners)
        if 2.5 <= corners <= 4 and clos < 0.3:
            return ClassificationResult('shapes', 'triangle', 0.80)
        
        # Ellipse (circular but open)
        if 0.75 < circ < 0.90 and clos < 0.4:
            return ClassificationResult('shapes', 'ellipse', 0.75)
        
        # Polygon (many corners)
        if corners > 5:
            return ClassificationResult('shapes', 'polygon', 0.70)
        
        return None
    
    def _try_letters(self, pts: List[Point], features: Dict) -> Optional[ClassificationResult]:
        """Try to detect letters. Placeholder for character recognition."""
        # TODO: Integrate with trained CNN for handwriting recognition
        # For now, return None to allow fallback
        return None
    
    def _try_numbers(self, pts: List[Point], features: Dict) -> Optional[ClassificationResult]:
        """Try to detect numbers. Placeholder for digit recognition."""
        # TODO: Integrate with trained CNN for digit recognition
        return None
    
    def _try_symbols(self, pts: List[Point], features: Dict) -> Optional[ClassificationResult]:
        """Try to detect symbols."""
        strt = features.get('straightness', 0)
        circ = features.get('circularity', 0)
        
        # Plus sign: multiple perpendicular lines
        if strt > 0.8:
            return ClassificationResult('symbols', '+', 0.6)
        
        # These are basic heuristics; real implementation would use ML
        return None
    
    def _try_novel_shapes(self, pts: List[Point], features: Dict) -> Optional[ClassificationResult]:
        """Try to recognize novel shapes from user training."""
        # TODO: Use k-NN or other method to match against previously learned shapes
        return None
    
    def record_feedback(self, prediction: ClassificationResult, 
                       correct_label: Optional[str], user_accepted: bool,
                       timestamp: float):
        """
        Record user feedback to improve future predictions.
        
        Args:
            prediction: Original prediction
            correct_label: What it actually should be (if different)
            user_accepted: True if user approved, False if they corrected it
            timestamp: When feedback was given
        """
        feedback = FeedbackRecord(
            predicted_label=prediction.label,
            predicted_confidence=prediction.confidence,
            correct_label=correct_label if not user_accepted else prediction.label,
            user_accepted=user_accepted,
            stroke_features=prediction.features,
            timestamp=timestamp
        )
        
        # Update error/success counts
        pred_key = f"{prediction.category}:{prediction.label}"
        if user_accepted:
            self.success_counts[pred_key] = self.success_counts.get(pred_key, 0) + 1
        else:
            self.error_counts[pred_key] = self.error_counts.get(pred_key, 0) + 1
        
        # Adjust RL confidence based on feedback
        if not user_accepted:
            # Wrong prediction - decrease confidence for this label
            adjustment = -0.10  # Penalty
            self.rl_adjustments[pred_key] = self.rl_adjustments.get(pred_key, 0) + adjustment
        else:
            # Correct prediction - increase confidence
            adjustment = 0.05  # Reward
            self.rl_adjustments[pred_key] = self.rl_adjustments.get(pred_key, 0) + adjustment
        
        # Cap adjustments to reasonable range
        self.rl_adjustments[pred_key] = np.clip(self.rl_adjustments[pred_key], -0.4, 0.4)
        
        # Save feedback for later analysis
        self._save_feedback(feedback)
        self._save_rl_model()
    
    def _save_feedback(self, feedback: FeedbackRecord):
        """Save feedback record to disk for analysis."""
        feedback_dir = Path("assets") / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        
        feedback_file = feedback_dir / "all_feedback.jsonl"
        with open(feedback_file, 'a') as f:
            f.write(json.dumps(asdict(feedback)) + '\n')
    
    def _save_rl_model(self):
        """Save RL adjustments to disk."""
        model_dir = Path("assets")
        model_dir.mkdir(parents=True, exist_ok=True)
        
        rl_file = model_dir / "rl_adjustments.json"
        data = {
            'adjustments': self.rl_adjustments,
            'error_counts': self.error_counts,
            'success_counts': self.success_counts,
        }
        with open(rl_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_rl_model(self):
        """Load saved RL adjustments."""
        rl_file = Path("assets") / "rl_adjustments.json"
        if rl_file.exists():
            try:
                with open(rl_file, 'r') as f:
                    data = json.load(f)
                    self.rl_adjustments = data.get('adjustments', {})
                    self.error_counts = data.get('error_counts', {})
                    self.success_counts = data.get('success_counts', {})
            except Exception as e:
                print(f"Warning: Could not load RL model: {e}")
    
    def get_confidence_history(self, label: str) -> Dict[str, Any]:
        """Get performance statistics for a label."""
        key = f"shapes:{label}"  # Most common case
        errors = self.error_counts.get(key, 0)
        successes = self.success_counts.get(key, 0)
        total = errors + successes
        accuracy = successes / total if total > 0 else 0.5
        rl_adj = self.rl_adjustments.get(key, 0.0)
        
        return {
            'label': label,
            'total_predictions': total,
            'accuracy': accuracy,
            'error_count': errors,
            'success_count': successes,
            'rl_adjustment': rl_adj,
        }


if __name__ == "__main__":
    # Test the classifier
    classifier = UniversalShapeClassifier()
    
    # Mock a circular stroke
    circle = [(100 + 50*np.cos(a), 100 + 50*np.sin(a)) 
              for a in np.linspace(0, 2*np.pi, 80)]
    
    result = classifier.classify(circle)
    print(f"Classification: {result.label} ({result.confidence:.2%})")
    print(f"Category: {result.category}")
    print(f"Features: {result.features}")
