"""
modules/rl_ui.py — Reinforcement learning feedback UI for shape/letter recognition.

Displays predictions and collects user feedback to improve accuracy over time.
"""

from __future__ import annotations
import cv2
import time
from typing import Optional, Callable
from utils.universal_classifier import ClassificationResult

class RLFeedbackUI:
    """
    Displays shape/letter prediction with feedback options.
    Allows user to confirm or correct predictions.
    """
    
    def __init__(self, canvas_h: int, canvas_w: int):
        """Initialize feedback UI."""
        self.canvas_h = canvas_h
        self.canvas_w = canvas_w
        
        self.show_feedback = False
        self.feedback_timer = 0.0
        self.feedback_timeout = 3.0  # seconds
        
        self.current_prediction: Optional[ClassificationResult] = None
        self.feedback_callback: Optional[Callable] = None
        
        # UI settings
        self.feedback_box_height = 80
        self.feedback_box_width = 400
        self.feedback_font = cv2.FONT_HERSHEY_SIMPLEX
        self.feedback_font_scale = 0.6
        self.feedback_font_color = (255, 255, 255)  # White
        self.feedback_font_thickness = 1
    
    def show_prediction(self, prediction: ClassificationResult, 
                       callback: Callable[[bool, Optional[str]], None]):
        """
        Display a prediction and wait for user feedback.
        
        Args:
            prediction: Classification result
            callback: Function to call with (accepted: bool, correction: str)
                     - accepted=True, correction=None → user confirmed
                     - accepted=False, correction="A" → user corrected it to "A"
        """
        self.current_prediction = prediction
        self.feedback_callback = callback
        self.show_feedback = True
        self.feedback_timer = time.time() + self.feedback_timeout
    
    def draw_feedback_ui(self, canvas):
        """
        Draw feedback UI on canvas.
        Shows:
        - Predicted label
        - Confidence percentage
        - Alternative predictions
        - Feedback option
        """
        if not self.show_feedback or self.current_prediction is None:
            return canvas
        
        # Check if feedback should disappear
        if time.time() > self.feedback_timer:
            self.show_feedback = False
            return canvas
        
        pred = self.current_prediction
        
        # Box position (top-left area)
        box_x = 20
        box_y = self.canvas_h - self.feedback_box_height - 20
        
        # Draw semi-transparent background
        overlay = canvas.copy()
        cv2.rectangle(overlay, (box_x, box_y), 
                     (box_x + self.feedback_box_width, box_y + self.feedback_box_height),
                     (0, 100, 200), -1)  # Dark blue background
        cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, canvas)
        
        # Draw border
        cv2.rectangle(canvas, (box_x, box_y),
                     (box_x + self.feedback_box_width, box_y + self.feedback_box_height),
                     (0, 200, 255), 2)  # Orange border
        
        # Main prediction text
        main_text = f"{pred.label.upper()} ({pred.confidence:.0%})"
        cv2.putText(canvas, main_text, (box_x + 10, box_y + 25),
                   self.feedback_font, self.feedback_font_scale,
                   self.feedback_font_color, self.feedback_font_thickness)
        
        # Confidence feedback
        if pred.confidence > 0.8:
            confidence_text = "✓ High confidence"
            confidence_color = (0, 255, 0)  # Green
        elif pred.confidence > 0.6:
            confidence_text = "⚠ Medium confidence"
            confidence_color = (0, 165, 255)  # Orange
        else:
            confidence_text = "? Low confidence"
            confidence_color = (0, 0, 255)  # Red
        
        cv2.putText(canvas, confidence_text, (box_x + 10, box_y + 50),
                   self.feedback_font, 0.5, confidence_color, 1)
        
        # Alternative predictions (if available)
        if pred.alternatives:
            alt_text = f"Alt: {', '.join(f'{l}({c:.0%})' for l, c in pred.alternatives[:2])}"
            cv2.putText(canvas, alt_text, (box_x + 10, box_y + 70),
                       self.feedback_font, 0.4, (200, 200, 200), 1)
        
        # Feedback hints
        hint_text = "[SPACE]✓ [E]Edit [?]Menu"
        cv2.putText(canvas, hint_text, (box_x + self.feedback_box_width - 180, box_y + 70),
                   self.feedback_font, 0.4, (150, 150, 255), 1)
        
        return canvas
    
    def handle_feedback(self, key: int) -> bool:
        """
        Handle user keyboard feedback.
        
        Args:
            key: OpenCV key code
            
        Returns:
            True if feedback was processed
        """
        if not self.show_feedback or self.current_prediction is None:
            return False
        
        # Space key: confirm prediction
        if key == ord(' '):
            self.show_feedback = False
            if self.feedback_callback:
                self.feedback_callback(accepted=True, correction=None)
            return True
        
        # E key: edit/correct prediction
        if key == ord('e') or key == ord('E'):
            self.show_feedback = False
            print("\n[CORRECTION MODE]")
            print(f"Original prediction: {self.current_prediction.label}")
            correction = input("What should it be? > ").strip().upper()
            if correction and self.feedback_callback:
                self.feedback_callback(accepted=False, correction=correction)
            return True
        
        # ? or H key: show menu
        if key == ord('?') or key == ord('h') or key == ord('H'):
            self._show_help_menu()
            return True
        
        # Escape: skip
        if key == 27:
            self.show_feedback = False
            return True
        
        return False
    
    def _show_help_menu(self):
        """Show help menu for feedback options."""
        print("\n" + "="*50)
        print("FEEDBACK MENU")
        print("="*50)
        print("[SPACE]  — Confirm prediction (yes, it's correct)")
        print("[E]      — Edit/correct the prediction")
        print("[?]      — Show this help menu")
        print("[ESC]    — Skip feedback (don't record)")
        print("="*50)


class RL_LearningUI:
    """Shows learning statistics and improvement metrics."""
    
    def __init__(self):
        """Initialize statistics UI."""
        self.stats_display = {}
    
    def update_stats(self, classifier) -> str:
        """
        Generate a statistics display string.
        
        Args:
            classifier: UniversalShapeClassifier instance
            
        Returns:
            Formatted statistics string
        """
        if not classifier.success_counts and not classifier.error_counts:
            return "No learning data yet. Start by confirming or correcting predictions!\n"
        
        # Calculate overall accuracy
        total_successes = sum(classifier.success_counts.values())
        total_errors = sum(classifier.error_counts.values())
        total = total_successes + total_errors
        
        if total == 0:
            return "No predictions made yet.\n"
        
        overall_accuracy = total_successes / total
        
        stats = f"""
╔════════════════════════════════════════╗
║   REINFORCEMENT LEARNING STATISTICS    ║
╚════════════════════════════════════════╝

Overall Accuracy: {overall_accuracy:.1%} ({total_successes}/{total} correct)
Total Predictions: {total}

Top 5 Most Confident Predictions:
"""
        
        # Get top predictions by RL adjustment
        sorted_preds = sorted(
            classifier.rl_adjustments.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]
        
        for key, adjustment in sorted_preds:
            cat_label = key.split(':')
            if len(cat_label) == 2:
                label = cat_label[1]
            else:
                label = key
            
            hist = classifier.get_confidence_history(label)
            arrow = "↑" if adjustment > 0 else "↓"
            stats += f"\n  {arrow} {label:10s} — Acc: {hist['accuracy']:.0%} | Adj: {adjustment:+.2f}"
        
        stats += "\n\nLearning Progress:\n"
        stats += "System learns from your feedback and adjusts predictions.\n"
        stats += "More corrections = faster learning!\n"
        
        return stats
    
    def display_stats(self, classifier):
        """Print statistics to console."""
        print(self.update_stats(classifier))


if __name__ == "__main__":
    # Test UI
    feedback_ui = RLFeedbackUI(600, 800)
    
    from utils.universal_classifier import ClassificationResult
    
    # Mock prediction
    mock_pred = ClassificationResult(
        category="shapes",
        label="circle",
        confidence=0.92,
        alternatives=[("ellipse", 0.06), ("polygon", 0.02)]
    )
    
    def mock_callback(accepted, correction):
        print(f"Feedback: accepted={accepted}, correction={correction}")
    
    feedback_ui.show_prediction(mock_pred, mock_callback)
    print("Feedback UI initialized successfully")
