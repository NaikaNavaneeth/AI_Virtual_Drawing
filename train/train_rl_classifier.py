#!/usr/bin/env python3
"""
train_rl_classifier.py — Train the RL-based universal classifier using three-stage learning.

Usage:
    python train_rl_classifier.py              # Run all three stages
    python train_rl_classifier.py --stage 1    # Stage 1 only
    python train_rl_classifier.py --stage 2    # Stage 1 + 2
    python train_rl_classifier.py --external-dataset mnist  # With MNIST data
"""

import sys
import argparse
from pathlib import Path

# Add parent directory (ai_drawing root) to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.model_training import ModelTrainer


def main():
    """Main training entry point."""
    parser = argparse.ArgumentParser(
        description="Train RL-based universal shape classifier with three-stage pipeline"
    )
    parser.add_argument('--stage', type=int, default=3, choices=[1, 2, 3],
                       help="Training stage to execute (default: all 3)")
    parser.add_argument('--external-dataset', type=str, default='synthetic',
                       help="External dataset to use in Stage 2 (default: none)")
    parser.add_argument('--dataset-path', type=str, default=None,
                       help="Path to custom dataset file")
    parser.add_argument('--verbose', action='store_true',
                       help="Print detailed training information")
    parser.add_argument('--skip-rl', action='store_true',
                       help="Skip Stage 3 (RL) activation")
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("RL CLASSIFIER TRAINING PIPELINE")
    print("="*70)
    
    trainer = ModelTrainer()
    
    # Stage 1: Synthetic data
    if args.stage >= 1:
        if not trainer.train_stage_1_on_synthetic():
            print("\n✗ Stage 1 failed")
            return False
    
    # Stage 2: External data
    if args.stage >= 2:
        if not trainer.train_stage_2_on_external(args.external_dataset):
            print("\n✗ Stage 2 failed")
            return False
    
    # Stage 3: RL activation
    if args.stage >= 3 and not args.skip_rl:
        if not trainer.activate_stage_3_rl():
            print("\n✗ Stage 3 failed")
            return False
    
    # Print summary
    trainer.print_training_summary()
    
    print("\n" + "="*70)
    print("✓ TRAINING COMPLETE")
    print("="*70)
    
    print("""
Next steps:
  1. Run the drawing application
  2. Start drawing shapes and letters
  3. System will use trained model as baseline
  4. Your feedback improves it further in real-time!

Files created:
  • assets/datasets/synthetic_train.pkl - Training data
  • assets/datasets/synthetic_val.pkl - Validation data
  • assets/datasets/metadata.json - Dataset metadata
  • assets/checkpoints/ - Model checkpoints
  • assets/rl_adjustments.json - RL weights (updated as you use it)
  • assets/feedback/ - User feedback log
    """)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
