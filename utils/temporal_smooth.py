"""
utils/temporal_smooth.py  —  Temporal smoothing for hand tracking landmarks.

Eliminates frame gaps caused by low quality detections or brief detection losses
by interpolating landmark positions based on previous valid frames.
"""

from __future__ import annotations
import math
from typing import List, Optional, Tuple
from collections import deque
from utils.mp_compat import HandResult, Landmark, LandmarkList


class LandmarkTemporalSmoother:
    """
    Smooths hand landmarks across frames using temporal interpolation.
    
    Keeps history of last 2 valid frames and performs linear interpolation
    if a frame has low quality detections or missing landmarks.
    """
    
    def __init__(self, history_size: int = 2):
        """Initialize smoother with history buffer size."""
        self.history_size = history_size
        self.history: deque = deque(maxlen=history_size)  # Store (landmarks, hand_label, timestamp)
        self.frame_count = 0
    
    def smooth(self, current_hand: Optional[HandResult], quality: float, 
               timestamp: float = 0.0) -> Optional[HandResult]:
        """
        Smooth current hand landmarks using temporal history.
        
        Args:
            current_hand: Current frame's detected hand (may be low quality or None)
            quality: Quality score 0-1 for current detection
            timestamp: Frame timestamp for interpolation
            
        Returns:
            Smoothed HandResult with potentially interpolated landmarks
        """
        self.frame_count += 1
        
        if current_hand is None:
            # Try to interpolate if we have history
            if len(self.history) >= 2:
                return self._interpolate_missing()
            return None
        
        # If quality is acceptable, store in history
        if quality > 0.25:  # Threshold slightly below minimum acceptable
            self.history.append({
                'hand': current_hand,
                'quality': quality,
                'timestamp': timestamp
            })
            return current_hand
        
        # Low quality: try temporal interpolation
        if len(self.history) >= 2:
            smoothed = self._interpolate_low_quality(current_hand)
            return smoothed
        else:
            # Not enough history, store what we have
            self.history.append({
                'hand': current_hand,
                'quality': quality,
                'timestamp': timestamp
            })
            return current_hand
    
    def _interpolate_missing(self) -> Optional[HandResult]:
        """Interpolate landmarks when detection failed entirely."""
        if len(self.history) < 2:
            return None
        
        hist_list = list(self.history)
        prev_hand = hist_list[-2]['hand']
        prev_prev_hand = hist_list[-1]['hand'] if len(hist_list) >= 3 else hist_list[-1]['hand']
        
        return self._interpolate_hands(prev_prev_hand, prev_hand, alpha=1.0)
    
    def _interpolate_low_quality(self, current_hand: HandResult) -> HandResult:
        """Blend current low-quality detection with temporal history."""
        if len(self.history) < 1:
            return current_hand
        
        prev_hand = list(self.history)[-1]['hand']
        
        # Blend: 70% previous, 30% current low-quality detection
        # This reduces jitter while keeping current detection in the loop
        blended = self._interpolate_hands(prev_hand, current_hand, alpha=0.3)
        
        # Still add current to history to maintain continuity
        return blended
    
    def _interpolate_hands(self, hand1: HandResult, hand2: HandResult, 
                           alpha: float) -> HandResult:
        """
        Linear interpolation between two hand detections.
        
        Args:
            hand1: First hand (weight 1-alpha)
            hand2: Second hand (weight alpha)
            alpha: Blend factor 0-1
        """
        # Interpolate landmarks
        new_landmarks = []
        
        for i in range(21):  # 21 landmarks in hand
            lm1 = hand1.landmarks[i]
            lm2 = hand2.landmarks[i]
            
            x = lm1.x * (1 - alpha) + lm2.x * alpha
            y = lm1.y * (1 - alpha) + lm2.y * alpha
            z = lm1.z * (1 - alpha) + lm2.z * alpha
            
            new_landmarks.append(Landmark(x=x, y=y, z=z))
        
        # Create interpolated hand result
        interpolated_hand = HandResult(
            label=hand1.label,
            score=(hand1.score * (1 - alpha) + hand2.score * alpha),
            landmarks=LandmarkList(new_landmarks)
        )
        
        return interpolated_hand
    
    def reset(self):
        """Reset history (call on explicit user action like clear)."""
        self.history.clear()
        self.frame_count = 0


class ExponentialLandmarkFilter:
    """
    Applies exponential moving average to landmark positions.
    
    Reduces jitter while maintaining responsiveness by exponentially
    weighted averaging of current and previous position.
    """
    
    def __init__(self, alpha: float = 0.2):
        """
        Initialize filter.
        
        Args:
            alpha: Smoothing factor 0-1. Higher = more responsive.
                  0.2 = 80% history, 20% current (smooth)
        """
        self.alpha = alpha
        self.prev_landmarks = None
    
    def filter(self, landmarks: Optional[LandmarkList]) -> Optional[LandmarkList]:
        """Apply exponential filter to landmarks."""
        if landmarks is None:
            return None
        
        if self.prev_landmarks is None:
            self.prev_landmarks = landmarks
            return landmarks
        
        # Apply exponential moving average
        filtered = []
        for i in range(len(landmarks)):
            curr = landmarks[i]
            prev = self.prev_landmarks[i]
            
            x = prev.x * (1 - self.alpha) + curr.x * self.alpha
            y = prev.y * (1 - self.alpha) + curr.y * self.alpha
            z = prev.z * (1 - self.alpha) + curr.z * self.alpha
            
            filtered.append(Landmark(x=x, y=y, z=z))
        
        result = LandmarkList(filtered)
        self.prev_landmarks = result
        return result
    
    def reset(self):
        """Reset filter state."""
        self.prev_landmarks = None
