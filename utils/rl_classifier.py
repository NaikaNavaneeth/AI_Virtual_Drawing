"""
utils/rl_classifier.py - Reinforcement Learning-based Universal Shape Classifier.

Tier 3: Learns from user corrections without retraining.
- Handles unlimited shape types
- Improves confidence scores based on feedback
- Personalizes to user's drawing style
- Non-breaking integration with existing Tiers 1 & 2
"""

from __future__ import annotations
import numpy as np
import cv2
from typing import Optional, Tuple, List, Dict
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
import time
from collections import defaultdict

Point = Tuple[int, int]

# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RLClassificationResult:
    """RL classification result with confidence"""
    category: str  # "shape", "letter", "number", "symbol"
    label: str
    confidence: float  # 0.0-1.0
    reason: str  # Why this classification
    alternatives: List[Tuple[str, float]]  # Top N alternatives

@dataclass
class UserFeedback:
    """User correction feedback for RL learning"""
    predicted_label: str
    actual_label: str
    confidence: float
    timestamp: float
    features: Dict[str, float]
    accepted: bool  # True if correct, False if user corrected


# ──────────────────────────────────────────────────────────────────────────────
# Feature Extraction (same as universal_classifier.py)
# ──────────────────────────────────────────────────────────────────────────────

class RLFeatureExtractor:
    """Extract features from strokes for RL-based classification"""
    
    @staticmethod
    def extract(pts: List[Point]) -> Dict[str, float]:
        """Extract geometric features from stroke"""
        if len(pts) < 3:
            return {}
        
        features = {
            'circularity': RLFeatureExtractor._circularity(pts),
            'aspect_ratio': RLFeatureExtractor._aspect_ratio(pts),
            'straightness': RLFeatureExtractor._straightness(pts),
            'closure_ratio': RLFeatureExtractor._closure_ratio(pts),
            'complexity': RLFeatureExtractor._complexity(pts),
            'num_corners': float(RLFeatureExtractor._count_corners(pts)),
            'stroke_length': float(RLFeatureExtractor._stroke_length(pts)),
            'stroke_density': RLFeatureExtractor._stroke_density(pts),
            'velocity_variance': RLFeatureExtractor._velocity_variance(pts),
            'direction_changes': float(RLFeatureExtractor._count_direction_changes(pts)),
        }
        
        return features
    
    @staticmethod
    def _circularity(pts):
        """How circular is the shape? 0=line, 1=perfect circle"""
        if len(pts) < 4:
            return 0.0
        pts_arr = np.array(pts, dtype=np.float32)
        perimeter = float(cv2.arcLength(pts_arr.reshape((-1, 1, 2)), False))
        area = float(cv2.contourArea(pts_arr.reshape((-1, 1, 2))))
        if perimeter < 1e-6:
            return 0.0
        return (4 * np.pi * area) / (perimeter ** 2)
    
    @staticmethod
    def _aspect_ratio(pts):
        """Width/height ratio (1=square, >1=wide, <1=tall)"""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        return max(w, h) / max(min(w, h), 1)
    
    @staticmethod
    def _straightness(pts):
        """How straight? 0=very curved, 1=straight line"""
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
        """How closed? 0=fully closed circle, 1=open line"""
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
        """Stroke complexity (0=simple line, 1=very complex)"""
        if len(pts) < 4:
            return 0.0
        curvatures = []
        for i in range(1, len(pts) - 1):
            v1 = np.array(pts[i]) - np.array(pts[i-1])
            v2 = np.array(pts[i+1]) - np.array(pts[i])
            mag1, mag2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if mag1 > 1e-6 and mag2 > 1e-6:
                cos_angle = np.clip(np.dot(v1, v2) / (mag1 * mag2), -1, 1)
                angle = np.arccos(cos_angle)
                curvatures.append(angle)
        if not curvatures:
            return 0.0
        threshold = np.mean(curvatures) + np.std(curvatures)
        return float(sum(1 for c in curvatures if c > threshold) / len(curvatures))
    
    @staticmethod
    def _count_corners(pts):
        """Count sharp corners"""
        if len(pts) < 3:
            return 0
        pts_arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
        try:
            approx = cv2.approxPolyDP(pts_arr, epsilon=5, closed=False)
            return len(approx)
        except:
            return 0
    
    @staticmethod
    def _stroke_length(pts):
        """Total stroke length"""
        if len(pts) < 2:
            return 0
        return sum(np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1]))
                  for i in range(1, len(pts)))
    
    @staticmethod
    def _stroke_density(pts):
        """Points per unit area"""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        area = w * h + 1
        return len(pts) / area
    
    @staticmethod
    def _velocity_variance(pts):
        """Variance in drawing speed"""
        if len(pts) < 2:
            return 0.0
        velocities = [np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1]))
                     for i in range(1, len(pts))]
        if not velocities:
            return 0.0
        return float(np.var(velocities))
    
    @staticmethod
    def _count_direction_changes(pts):
        """Count direction reversals"""
        if len(pts) < 3:
            return 0
        changes = 0
        for i in range(1, len(pts) - 1):
            v1 = np.array(pts[i]) - np.array(pts[i-1])
            v2 = np.array(pts[i+1]) - np.array(pts[i])
            dot = np.dot(v1, v2)
            if dot < 0:  # Direction changed
                changes += 1
        return changes


# ──────────────────────────────────────────────────────────────────────────────
# RL-Based Classifier
# ──────────────────────────────────────────────────────────────────────────────

class RLShapeClassifier:
    """
    Tier 3 RL Classifier: Learns shapes from user feedback.
    
    - No retraining needed for new shapes
    - Adapts confidence scores based on corrections
    - Personalizes to user's drawing style
    - Maintains learning state in persistent storage
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize RL classifier with optional persistent storage"""
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "assets", "rl_knowledge.json"
        )
        
        # Shape knowledge base: {label: {features, confidence, feedback_count}}
        self.shape_knowledge = defaultdict(lambda: {
            'feature_mean': {},
            'feature_variance': {},
            'confidence': 0.5,  # Start at neutral
            'feedback_count': 0,
            'correct_count': 0,
            'last_updated': time.time(),
        })
        
        # Feedback history for debugging
        self.feedback_history = []
        
        # Load persisted knowledge if available
        self.load_knowledge()
    
    def classify(self, stroke_pts: List[Point], return_alternatives: bool = True
                ) -> Optional[RLClassificationResult]:
        """
        Classify a stroke using learned knowledge.
        
        Args:
            stroke_pts: Stroke points
            return_alternatives: Include top 3 alternatives
        
        Returns:
            RLClassificationResult or None if low confidence
        """
        if len(stroke_pts) < 3:
            return None
        
        # Extract features from stroke
        features = RLFeatureExtractor.extract(stroke_pts)
        if not features:
            return None
        
        # Score against all known shapes
        scores = {}
        for label, knowledge in self.shape_knowledge.items():
            score = self._compute_similarity(features, label, knowledge)
            scores[label] = score
        
        if not scores:
            return None
        
        # Find best match
        best_label = max(scores, key=scores.get)
        best_score = scores[best_label]
        
        # Get confidence from learned knowledge
        base_confidence = self.shape_knowledge[best_label]['confidence']
        final_confidence = (best_score + base_confidence) / 2.0
        
        # Determine category
        category = self._determine_category(best_label)
        
        # Alternatives
        alternatives = []
        if return_alternatives:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            for label, score in sorted_scores[1:4]:  # Top 3 alternatives
                alt_conf = self.shape_knowledge[label]['confidence']
                alternatives.append((label, (score + alt_conf) / 2.0))
        
        return RLClassificationResult(
            category=category,
            label=best_label,
            confidence=final_confidence,
            reason=f"Feature similarity: {best_score:.2f}, Learned confidence: {base_confidence:.2f}",
            alternatives=alternatives
        )
    
    def learn_from_feedback(self, predicted_label: str, actual_label: str, 
                           features: Dict[str, float], was_correct: bool):
        """
        Learn from user feedback (correction or confirmation).
        
        Args:
            predicted_label: What system predicted
            actual_label: What user confirmed it was
            features: Extracted features from stroke
            was_correct: True if prediction was correct, False if corrected
        """
        feedback = UserFeedback(
            predicted_label=predicted_label,
            actual_label=actual_label,
            confidence=self.shape_knowledge[predicted_label]['confidence'],
            timestamp=time.time(),
            features=features,
            accepted=was_correct
        )
        self.feedback_history.append(feedback)
        
        # Update knowledge base
        knowledge = self.shape_knowledge[actual_label]
        
        # Update confidence
        if was_correct:
            # Increase confidence if prediction was correct
            knowledge['correct_count'] += 1
            knowledge['confidence'] = min(
                1.0, 
                knowledge['confidence'] + 0.05
            )
        else:
            # Decrease confidence if prediction was wrong
            knowledge['confidence'] = max(
                0.3,
                knowledge['confidence'] - 0.1
            )
        
        knowledge['feedback_count'] += 1
        knowledge['last_updated'] = time.time()
        
        # Update feature statistics
        for feature_name, value in features.items():
            if feature_name not in knowledge['feature_mean']:
                knowledge['feature_mean'][feature_name] = value
                knowledge['feature_variance'][feature_name] = 0.0
            else:
                # Running mean and variance
                prev_mean = knowledge['feature_mean'][feature_name]
                n = knowledge['feedback_count']
                
                # Welford's algorithm for online variance
                new_mean = prev_mean + (value - prev_mean) / n
                new_var = (knowledge['feature_variance'][feature_name] + 
                          (value - prev_mean) * (value - new_mean))
                
                knowledge['feature_mean'][feature_name] = new_mean
                knowledge['feature_variance'][feature_name] = new_var / n if n > 1 else 0.0
        
        # Persist after each feedback
        self.save_knowledge()
        
        print(f"[RLClassifier] Learned: {predicted_label} → {actual_label} "
              f"(confidence: {knowledge['confidence']:.2f})")
    
    def _compute_similarity(self, features: Dict[str, float], label: str, 
                           knowledge: Dict) -> float:
        """Compute similarity between stroke features and learned shape"""
        if not knowledge['feature_mean']:
            return 0.5  # No prior knowledge
        
        similarity = 0.0
        count = 0
        
        for feature_name, value in features.items():
            if feature_name not in knowledge['feature_mean']:
                continue
            
            expected = knowledge['feature_mean'][feature_name]
            variance = max(knowledge['feature_variance'][feature_name], 0.01)
            
            # Gaussian-like similarity (higher closer to mean)
            diff = abs(value - expected)
            sim = np.exp(-(diff ** 2) / (2 * variance + 1e-6))
            
            similarity += sim
            count += 1
        
        return similarity / count if count > 0 else 0.5
    
    def _determine_category(self, label: str) -> str:
        """Determine category of shape label"""
        if label in ['circle', 'square', 'triangle', 'line', 'pentagon', 'hexagon']:
            return 'shape'
        elif len(label) == 1 and label.isalpha():
            return 'letter'
        elif len(label) == 1 and label.isdigit():
            return 'number'
        else:
            return 'symbol'
    
    def save_knowledge(self):
        """Persist learned knowledge to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Convert to serializable format
            data = {
                'shapes': {},
                'feedback_count': len(self.feedback_history),
                'last_updated': time.time()
            }
            
            for label, knowledge in self.shape_knowledge.items():
                data['shapes'][label] = {
                    'feature_mean': knowledge['feature_mean'],
                    'feature_variance': knowledge['feature_variance'],
                    'confidence': knowledge['confidence'],
                    'feedback_count': knowledge['feedback_count'],
                    'correct_count': knowledge['correct_count'],
                    'last_updated': knowledge['last_updated']
                }
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"[RLClassifier] Saved knowledge to {self.storage_path}")
        except Exception as e:
            print(f"[RLClassifier] Error saving knowledge: {e}")
    
    def load_knowledge(self):
        """Load persisted knowledge from storage"""
        try:
            if not os.path.exists(self.storage_path):
                print(f"[RLClassifier] No prior knowledge found, starting fresh")
                return
            
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            for label, knowledge in data.get('shapes', {}).items():
                self.shape_knowledge[label] = knowledge
            
            print(f"[RLClassifier] Loaded knowledge for {len(self.shape_knowledge)} shapes")
        except Exception as e:
            print(f"[RLClassifier] Error loading knowledge: {e}")
    
    def add_known_shape(self, label: str, typical_features: Dict[str, float],
                       initial_confidence: float = 0.7):
        """
        Pre-register a shape (for Tier 2 learned shapes).
        Used to initialize RL classifier with MLP knowledge.
        """
        self.shape_knowledge[label] = {
            'feature_mean': typical_features.copy(),
            'feature_variance': {k: 0.05 for k in typical_features},  # Small initial variance
            'confidence': initial_confidence,
            'feedback_count': 1,  # Already has knowledge
            'correct_count': 1,
            'last_updated': time.time()
        }
        print(f"[RLClassifier] Registered shape: {label}")
    
    def get_stats(self) -> Dict:
        """Get classifier statistics"""
        return {
            'known_shapes': len(self.shape_knowledge),
            'total_feedback': len(self.feedback_history),
            'shapes': {
                label: {
                    'confidence': knowledge['confidence'],
                    'feedback_count': knowledge['feedback_count'],
                    'accuracy': (knowledge['correct_count'] / knowledge['feedback_count'] 
                                if knowledge['feedback_count'] > 0 else 0.0)
                }
                for label, knowledge in self.shape_knowledge.items()
            }
        }


# ──────────────────────────────────────────────────────────────────────────────
# Global Instance
# ──────────────────────────────────────────────────────────────────────────────

_rl_classifier = None

def get_rl_classifier() -> RLShapeClassifier:
    """Get or create singleton RL classifier"""
    global _rl_classifier
    if _rl_classifier is None:
        _rl_classifier = RLShapeClassifier()
    return _rl_classifier
