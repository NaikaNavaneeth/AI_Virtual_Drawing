"""
utils/learning_manager.py — Manages model retraining and continuous improvement from feedback.

Analyzes collected feedback and:
- Identifies problematic categories
- Optimizes confidence thresholds
- Suggests model improvements
- Generates performance reports
"""

from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import time

@dataclass
class LearningReport:
    """Report on model performance and learning progress."""
    timestamp: float
    total_predictions: int
    overall_accuracy: float
    best_performing_labels: List[Tuple[str, float]]  # [(label, accuracy), ...]
    worst_performing_labels: List[Tuple[str, float]]
    recommended_threshold_adjustments: Dict[str, float]
    improvement_suggestions: List[str]
    estimated_improvement: float  # Expected accuracy gain from suggestions


class LearningManager:
    """
    Manages continuous learning from user feedback.
    Analyzes patterns and optimizes model performance.
    """
    
    def __init__(self):
        """Initialize learning manager."""
        self.feedback_log: List[Dict] = []
        self.learning_history: List[LearningReport] = []
        self._load_feedback()
    
    def analyze_feedback(self) -> LearningReport:
        """
        Analyze collected feedback and generate learning report.
        
        Returns:
            LearningReport with statistics and recommendations
        """
        self._load_feedback()
        
        if not self.feedback_log:
            return LearningReport(
                timestamp=time.time(),
                total_predictions=0,
                overall_accuracy=0.5,
                best_performing_labels=[],
                worst_performing_labels=[],
                recommended_threshold_adjustments={},
                improvement_suggestions=["Start drawing and confirming/correcting to begin learning"],
                estimated_improvement=0.0
            )
        
        # Calculate per-label statistics
        label_stats = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'confidences': []})
        
        for feedback in self.feedback_log:
            pred_label = feedback.get('predicted_label', 'unknown')
            user_accepted = feedback.get('user_accepted', False)
            pred_conf = feedback.get('predicted_confidence', 0.5)
            
            stats = label_stats[pred_label]
            if user_accepted:
                stats['correct'] += 1
            else:
                stats['incorrect'] += 1
            stats['confidences'].append(pred_conf)
        
        # Calculate per-label accuracy
        accuracies = {}
        for label, stat in label_stats.items():
            total = stat['correct'] + stat['incorrect']
            if total > 0:
                accuracies[label] = stat['correct'] / total
        
        # Overall statistics
        total_correct = sum(s['correct'] for s in label_stats.values())
        total_predictions = len(self.feedback_log)
        overall_accuracy = total_correct / total_predictions if total_predictions > 0 else 0.5
        
        # Best and worst performing
        sorted_labels = sorted(accuracies.items(), key=lambda x: x[1], reverse=True)
        best_performing = sorted_labels[:5]
        worst_performing = sorted_labels[-5:] if len(sorted_labels) > 5 else []
        
        # Generate recommendations
        recommendations = self._generate_recommendations(label_stats, accuracies)
        threshold_adjustments = self._suggest_threshold_adjustments(label_stats, accuracies)
        
        # Estimate improvement
        estimated_improvement = self._estimate_improvement(accuracies, recommendations)
        
        report = LearningReport(
            timestamp=time.time(),
            total_predictions=total_predictions,
            overall_accuracy=overall_accuracy,
            best_performing_labels=best_performing,
            worst_performing_labels=worst_performing,
            recommended_threshold_adjustments=threshold_adjustments,
            improvement_suggestions=recommendations,
            estimated_improvement=estimated_improvement
        )
        
        self.learning_history.append(report)
        return report
    
    def _generate_recommendations(self, label_stats: Dict, 
                                 accuracies: Dict[str, float]) -> List[str]:
        """Generate improvement suggestions based on analysis."""
        recommendations = []
        
        # Find labels that need improvement
        poor_labels = [l for l, acc in accuracies.items() if acc < 0.7]
        if poor_labels:
            recommendations.append(
                f"Focus on {', '.join(poor_labels[:3])} — they have low accuracy (<70%)"
            )
        
        # Identify overconfident predictions
        for label, stats in label_stats.items():
            if stats['incorrect'] > 0:
                avg_conf_when_wrong = np.mean([c for i, c in enumerate(stats['confidences']) 
                                               if i < stats['incorrect']])
                if avg_conf_when_wrong > 0.7:
                    recommendations.append(
                        f"'{label}' is overconfident when wrong — reduce confidence threshold"
                    )
        
        # Suggest data collection areas
        underrepresented = [l for l, acc in accuracies.items() 
                           if label_stats[l]['correct'] + label_stats[l]['incorrect'] < 5]
        if underrepresented:
            recommendations.append(
                f"Need more examples of: {', '.join(underrepresented[:3])}"
            )
        
        # Encourage continued learning
        if len(self.feedback_log) < 50:
            recommendations.append(
                "Collect more feedback to improve accuracy (target: 50+ predictions)"
            )
        
        if not recommendations:
            recommendations.append("Model is performing well! Continue monitoring for anomalies.")
        
        return recommendations
    
    def _suggest_threshold_adjustments(self, label_stats: Dict, 
                                      accuracies: Dict[str, float]) -> Dict[str, float]:
        """Suggest confidence threshold adjustments per label."""
        adjustments = {}
        
        for label, stats in label_stats.items():
            if stats['correct'] + stats['incorrect'] < 3:
                continue  # Not enough data
            
            # Calculate correct and incorrect confidences
            n_total = stats['correct'] + stats['incorrect']
            correct_conf = np.mean(stats['confidences'][:stats['correct']]) \
                          if stats['correct'] > 0 else 0.5
            incorrect_conf = np.mean(stats['confidences'][stats['correct']:]) \
                           if stats['incorrect'] > 0 else 0.5
            
            # If many wrong predictions were made confidently, lower threshold
            if stats['incorrect'] > 0 and incorrect_conf > 0.7:
                adjustments[label] = -0.10
            # If wrong predictions tend to come with lower confidence, we can trust it more
            elif stats['incorrect'] > 0 and incorrect_conf < 0.5:
                adjustments[label] = 0.05
        
        return adjustments
    
    def _estimate_improvement(self, accuracies: Dict[str, float], 
                             recommendations: List[str]) -> float:
        """Estimate potential accuracy improvement from recommendations."""
        current_avg = np.mean(list(accuracies.values())) if accuracies else 0.5
        
        # Each recommendation could improve accuracy by up to 2-5%
        potential_gain = len(recommendations) * 0.02
        
        # Cap at realistic improvement
        return min(potential_gain, 0.15)  # Max 15% improvement
    
    def _load_feedback(self):
        """Load feedback logs from disk."""
        feedback_file = Path("assets") / "feedback" / "all_feedback.jsonl"
        
        self.feedback_log = []
        if feedback_file.exists():
            try:
                with open(feedback_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            feedback = json.loads(line)
                            self.feedback_log.append(feedback)
            except Exception as e:
                print(f"Warning: Could not load feedback: {e}")
    
    def generate_report_text(self, report: LearningReport) -> str:
        """Generate human-readable report from LearningReport."""
        lines = [
            "",
            "╔════════════════════════════════════════════╗",
            "║     REINFORCEMENT LEARNING REPORT          ║",
            "╚════════════════════════════════════════════╝",
            "",
            f"Analysis Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.timestamp))}",
            f"Total Predictions Analyzed: {report.total_predictions}",
            f"Overall Accuracy: {report.overall_accuracy:.1%}",
            ""
        ]
        
        if report.best_performing_labels:
            lines.append("🟢 BEST PERFORMING:")
            for label, acc in report.best_performing_labels:
                lines.append(f"   ✓ {label:15s} — {acc:.1%} accuracy")
            lines.append("")
        
        if report.worst_performing_labels:
            lines.append("🔴 NEEDS IMPROVEMENT:")
            for label, acc in report.worst_performing_labels:
                lines.append(f"   ✗ {label:15s} — {acc:.1%} accuracy")
            lines.append("")
        
        if report.improvement_suggestions:
            lines.append("💡 RECOMMENDATIONS:")
            for i, suggestion in enumerate(report.improvement_suggestions, 1):
                lines.append(f"   {i}. {suggestion}")
            lines.append("")
        
        if report.recommended_threshold_adjustments:
            lines.append("⚙️  THRESHOLD ADJUSTMENTS:")
            for label, adjustment in report.recommended_threshold_adjustments.items():
                arrow = "↑" if adjustment > 0 else "↓"
                lines.append(f"   {arrow} {label:15s} {adjustment:+.2f}")
            lines.append("")
        
        lines.append(f"📈 Estimated Improvement Potential: {report.estimated_improvement:.1%}")
        lines.append("")
        
        return "\n".join(lines)
    
    def print_report(self, report: LearningReport):
        """Print report to console."""
        print(self.generate_report_text(report))
    
    def get_improvement_trajectory(self) -> Dict[str, Any]:
        """
        Get historical improvement trajectory.
        
        Returns:
            Dict with accuracy over time
        """
        if not self.learning_history:
            return {'timestamps': [], 'accuracies': [], 'trend': 'insufficient_data'}
        
        timestamps = [r.timestamp for r in self.learning_history]
        accuracies = [r.overall_accuracy for r in self.learning_history]
        
        # Calculate trend
        if len(accuracies) > 1:
            recent_improvement = accuracies[-1] - accuracies[0]
            if recent_improvement > 0.05:
                trend = 'improving'
            elif recent_improvement < -0.05:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'timestamps': timestamps,
            'accuracies': accuracies,
            'trend': trend,
            'current_accuracy': accuracies[-1] if accuracies else 0.5,
            'initial_accuracy': accuracies[0] if accuracies else 0.5,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Continuous Learning Loop (for periodic retraining)
# ─────────────────────────────────────────────────────────────────────────────

class ContinuousLearningScheduler:
    """
    Handles periodic analysis and learning updates.
    Can be run in background thread to improve models over time.
    """
    
    def __init__(self, check_interval: float = 300.0):
        """
        Initialize scheduler.
        
        Args:
            check_interval: Seconds between learning analyses (default: 5 min)
        """
        self.manager = LearningManager()
        self.check_interval = check_interval
        self.last_check = 0.0
        self.should_run = True
    
    def check_and_learn(self) -> bool:
        """
        Check if it's time to run learning analysis.
        Returns True if analysis was performed.
        """
        now = time.time()
        if now - self.last_check >= self.check_interval:
            self.last_check = now
            report = self.manager.analyze_feedback()
            self.manager.print_report(report)
            return True
        return False
    
    def force_analysis(self):
        """Force immediate analysis (useful for manual trigger)."""
        report = self.manager.analyze_feedback()
        self.manager.print_report(report)


if __name__ == "__main__":
    # Test the learning manager
    manager = LearningManager()
    
    # Check if we have feedback
    if not manager.feedback_log:
        print("No feedback collected yet. Start by running the drawing application.")
    else:
        report = manager.analyze_feedback()
        manager.print_report(report)
