"""
train_gesture_cnn.py  —  Standalone CNN training script.

Trains a gesture classifier on synthetic data (bootstrap) and saves it
so the drawing platform can load it immediately.

For better real-world accuracy, collect real hand data using the T key
in the 2D drawing module, then re-run this script with --real flag.

Usage
-----
    python train_gesture_cnn.py                 # synthetic bootstrap
    python train_gesture_cnn.py --real          # train on collected .npz files
    python train_gesture_cnn.py --eval          # evaluate saved model
"""

import argparse
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml.gesture_cnn import (
    GestureClassifier,
    GestureDataCollector,
    generate_synthetic_samples,
)
from core.config import DATA_DIR, GESTURE_LABELS, CNN_MODEL_PATH


def train_synthetic(epochs: int = 150):
    print("=" * 55)
    print("  Gesture CNN — Synthetic Bootstrap Training")
    print("=" * 55)

    print(f"\nGenerating {300 * len(GESTURE_LABELS)} synthetic samples ...")
    X, y = generate_synthetic_samples(n_per_class=300)

    collector = GestureDataCollector()
    X_aug, y_aug = collector.augment(X, y, n_copies=3)
    print(f"After augmentation: {len(y_aug)} samples")

    print("\nClass distribution:")
    for i, label in enumerate(GESTURE_LABELS):
        count = int((y_aug == i).sum())
        print(f"  {label:12s}: {count}")

    print(f"\nTraining ({epochs} epochs) ...")
    clf = GestureClassifier()
    acc = clf.train(X_aug, y_aug, epochs=epochs)
    clf.save()

    print(f"\n  Training accuracy : {acc:.1%}")
    print(f"  Model saved to    : {CNN_MODEL_PATH}")
    print("\nReady!  Run `python main.py 2d` to use it.")


def train_real():
    """Train on .npz files collected via the T key in 2D mode."""
    print("=" * 55)
    print("  Gesture CNN — Real Data Training")
    print("=" * 55)

    npz_files = [
        os.path.join(DATA_DIR, f)
        for f in os.listdir(DATA_DIR)
        if f.endswith(".npz")
    ]

    if not npz_files:
        print(f"\nNo .npz files found in {DATA_DIR}")
        print("Collect real data using the T key in 2D drawing mode first.")
        sys.exit(1)

    all_X, all_y = [], []
    for path in npz_files:
        X, y = GestureDataCollector.load_dataset(path)
        all_X.append(X)
        all_y.append(y)
        print(f"  Loaded: {os.path.basename(path)} — {len(y)} samples")

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y, axis=0)

    # Mix with synthetic to prevent overfitting
    X_syn, y_syn = generate_synthetic_samples(n_per_class=50)
    X = np.concatenate([X, X_syn], axis=0)
    y = np.concatenate([y, y_syn], axis=0)

    collector = GestureDataCollector()
    X_aug, y_aug = collector.augment(X, y, n_copies=2)
    print(f"\nTotal samples after augmentation: {len(y_aug)}")

    clf = GestureClassifier()
    acc = clf.train(X_aug, y_aug, epochs=100)
    clf.save()
    print(f"\n  Training accuracy : {acc:.1%}")


def evaluate():
    """Quick evaluation of the saved model on held-out synthetic data."""
    print("=" * 55)
    print("  Gesture CNN — Evaluation")
    print("=" * 55)

    clf = GestureClassifier()
    if not clf.load():
        print("No model found. Run training first.")
        sys.exit(1)

    X, y = generate_synthetic_samples(n_per_class=100, noise=0.05)
    correct = 0
    for xi, yi in zip(X, y):
        # Wrap numpy array in a mock hand_landmarks object for the classifier
        class _MockLM:
            class landmark:
                pass
        # Use direct sklearn/torch prediction (bypass landmark_to_vector by
        # calling the internal predict method directly on the vector)
        if clf._backend == "torch":
            import torch, torch.nn.functional as F
            with torch.no_grad():
                t     = torch.tensor(xi, dtype=torch.float32).unsqueeze(0)
                prob  = F.softmax(clf._model(t), dim=1).squeeze().numpy()
            pred = int(np.argmax(prob))
        else:
            pred_raw = clf._model.predict([xi])[0]
            pred     = int(clf._encoder.inverse_transform([pred_raw])[0])
        if pred == yi:
            correct += 1

    acc = correct / len(y)
    print(f"\n  Test accuracy: {acc:.1%}  ({correct}/{len(y)} correct)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gesture CNN trainer")
    parser.add_argument("--real",   action="store_true", help="Train on real collected data")
    parser.add_argument("--eval",   action="store_true", help="Evaluate saved model")
    parser.add_argument("--epochs", type=int, default=150)
    args = parser.parse_args()

    if args.eval:
        evaluate()
    elif args.real:
        train_real()
    else:
        train_synthetic(epochs=args.epochs)
