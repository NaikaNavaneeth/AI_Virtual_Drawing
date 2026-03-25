"""
ml/gesture_cnn.py  —  CNN-based Gesture Classifier

Architecture
------------
Multi-layer Perceptron (MLP) trained on MediaPipe 21-landmark vectors.
Each landmark is represented as (x, y, z) normalised to wrist-reference
coordinates, giving 63 input features.

The model is intentionally lightweight so it runs in real-time alongside
the webcam loop with no GPU required.

  Input  :  63 floats  (21 landmarks × 3 coordinates, wrist-relative)
  Hidden :  [256 → ReLU → Dropout(0.3)] → [128 → ReLU] → [64 → ReLU]
  Output :  NUM_GESTURE_CLASSES (softmax)

Why MLP not CNN?
  MediaPipe landmarks are already a structured, high-level feature vector.
  Spatial convolutions are most useful on raw pixel grids; a deep MLP is
  more appropriate (and faster) for ordered keypoint arrays.

Usage
-----
  from ml.gesture_cnn import GestureClassifier

  clf = GestureClassifier()
  clf.load()                            # load saved model
  label, confidence = clf.predict(lm)  # lm = mediapipe hand_landmarks

  # --- Training from collected data ---
  clf.train(X, y)   # numpy arrays
  clf.save()
"""

from __future__ import annotations

import os
import pickle
import math
import numpy as np
from typing import List, Tuple, Optional

# ── Try PyTorch (preferred) then sklearn MLP (fallback) ──────────────────────
_TORCH_OK = False
try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except (ImportError, OSError) as e:
    # OSError: handle DLL loading issues on Windows
    # ImportError: handle missing torch
    pass

_SKLEARN_OK = False
try:
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import LabelEncoder
    _SKLEARN_OK = True
except (ImportError, OSError):
    pass

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import (
    CNN_MODEL_PATH, CNN_INPUT_SIZE, CNN_HIDDEN_SIZES, CNN_DROPOUT,
    CNN_CONFIDENCE, CNN_FALLBACK, GESTURE_LABELS, NUM_GESTURE_CLASSES,
)
from utils.gesture import classify_gesture  # rule-based fallback


# ═══════════════════════════════════════════════════════════════════════
#  Preprocessing: landmarks → feature vector
# ═══════════════════════════════════════════════════════════════════════

def landmarks_to_vector(hand_landmarks) -> Optional[np.ndarray]:
    """
    Convert MediaPipe hand_landmarks to a normalised 63-float feature vector.

    Normalisation steps:
    1. Translate so that wrist (landmark 0) is at origin.
    2. Scale so that the maximum absolute coordinate = 1.0.

    This makes the vector scale- and position-invariant.
    
    OPTIMIZED: Validates landmarks for NaN/corruption before processing.
    """
    import math
    
    lm = hand_landmarks.landmark
    
    # OPTIMIZED: Validate landmarks (reject corrupted detections)
    for i, landmark in enumerate(lm):
        # Check for NaN or invalid values
        if math.isnan(landmark.x) or math.isnan(landmark.y) or math.isnan(landmark.z):
            return None  # Skip corrupted landmark
        # Check visibility (if available)
        if hasattr(landmark, 'visibility') and landmark.visibility < 0.3:
            return None  # Skip low-confidence landmarks
    
    pts = np.array([[l.x, l.y, l.z] for l in lm], dtype=np.float32)

    # Translate to wrist origin
    pts -= pts[0]

    # Scale normalisation
    max_val = np.max(np.abs(pts))
    if max_val > 1e-6:
        pts /= max_val
    else:
        return None  # Degenerate hand (all points at same position)

    return pts.flatten()   # shape (63,)


def batch_landmarks_to_vectors(landmarks_list) -> np.ndarray:
    """Convert a list of hand_landmark objects to a (N, 63) numpy array."""
    return np.stack([landmarks_to_vector(lm) for lm in landmarks_list])


# ═══════════════════════════════════════════════════════════════════════
#  PyTorch MLP model definition
# ═══════════════════════════════════════════════════════════════════════

class _MLP(nn.Module if _TORCH_OK else object):
    """
    Lightweight MLP gesture classifier.
    Input: 63 normalised landmark coordinates.
    Output: softmax over NUM_GESTURE_CLASSES.
    """
    def __init__(self, input_size=63, hidden_sizes=None, num_classes=9, dropout=0.3):
        if _TORCH_OK:
            super().__init__()
        if hidden_sizes is None:
            hidden_sizes = [256, 128, 64]

        if _TORCH_OK:
            layers = []
            prev = input_size
            for h in hidden_sizes:
                layers += [
                    nn.Linear(prev, h),
                    nn.BatchNorm1d(h),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
                prev = h
            layers.append(nn.Linear(prev, num_classes))
            self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


# ═══════════════════════════════════════════════════════════════════════
#  Main classifier class
# ═══════════════════════════════════════════════════════════════════════

class GestureClassifier:
    """
    Unified gesture classifier.
    Uses PyTorch MLP if available, else sklearn MLPClassifier, else
    falls back to the rule-based heuristic classifier.
    """

    def __init__(self):
        self._backend: str = "none"
        self._model    = None
        self._encoder  = None   # label encoder (sklearn path)
        self.loaded    = False

    # ── Public: load ────────────────────────────────────────────────────
    def load(self) -> bool:
        """Load a previously saved model. Returns True on success."""
        if not os.path.exists(CNN_MODEL_PATH):
            return False
        try:
            with open(CNN_MODEL_PATH, "rb") as f:
                data = pickle.load(f)

            if data.get("backend") == "torch" and _TORCH_OK:
                model = _MLP(
                    input_size   = CNN_INPUT_SIZE,
                    hidden_sizes = CNN_HIDDEN_SIZES,
                    num_classes  = NUM_GESTURE_CLASSES,
                    dropout      = CNN_DROPOUT,
                )
                model.load_state_dict(data["state_dict"])
                model.eval()
                self._model   = model
                self._backend = "torch"

            elif data.get("backend") == "sklearn" and _SKLEARN_OK:
                self._model   = data["model"]
                self._encoder = data["encoder"]
                self._backend = "sklearn"

            else:
                return False

            self.loaded = True
            print(f"[GestureClassifier] Loaded model ({self._backend})")
            return True

        except Exception as e:
            print(f"[GestureClassifier] Load failed: {e}")
            return False

    # ── Public: train ───────────────────────────────────────────────────
    def train(self, X: np.ndarray, y: np.ndarray,
              epochs: int = 60, lr: float = 1e-3) -> float:
        """
        Train the model.
        X : (N, 63) float32  — landmark feature vectors
        y : (N,)    int      — class indices (0..NUM_GESTURE_CLASSES-1)
        Returns final training accuracy.
        """
        if _TORCH_OK:
            return self._train_torch(X, y, epochs, lr)
        elif _SKLEARN_OK:
            return self._train_sklearn(X, y)
        else:
            raise RuntimeError("Neither PyTorch nor scikit-learn is available.")

    def _train_torch(self, X, y, epochs=60, lr=1e-3) -> float:
        import torch, torch.nn as nn
        from torch.utils.data import TensorDataset, DataLoader

        model = _MLP(CNN_INPUT_SIZE, CNN_HIDDEN_SIZES, NUM_GESTURE_CLASSES, CNN_DROPOUT)
        opt   = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        criterion = nn.CrossEntropyLoss()

        Xt = torch.tensor(X, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        ds = TensorDataset(Xt, yt)
        dl = DataLoader(ds, batch_size=32, shuffle=True)

        model.train()
        for epoch in range(epochs):
            total_loss = 0.0
            for xb, yb in dl:
                opt.zero_grad()
                loss = criterion(model(xb), yb)
                loss.backward()
                opt.step()
                total_loss += loss.item()
            sched.step()
            if (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{epochs}  loss={total_loss/len(dl):.4f}")

        # Accuracy
        model.eval()
        with torch.no_grad():
            preds = model(Xt).argmax(dim=1).numpy()
        acc = float((preds == y).mean())

        self._model   = model
        self._backend = "torch"
        self.loaded   = True
        print(f"[GestureClassifier] Torch training done. Accuracy: {acc:.3f}")
        return acc

    def _train_sklearn(self, X, y) -> float:
        le  = LabelEncoder()
        y_e = le.fit_transform(y)
        clf = MLPClassifier(
            hidden_layer_sizes=tuple(CNN_HIDDEN_SIZES),
            activation="relu",
            max_iter=300,
            random_state=42,
            early_stopping=True,
        )
        clf.fit(X, y_e)
        acc = clf.score(X, y_e)

        self._model   = clf
        self._encoder = le
        self._backend = "sklearn"
        self.loaded   = True
        print(f"[GestureClassifier] sklearn training done. Accuracy: {acc:.3f}")
        return acc

    # ── Public: save ────────────────────────────────────────────────────
    def save(self):
        """Persist the model to disk."""
        os.makedirs(os.path.dirname(CNN_MODEL_PATH), exist_ok=True)
        if self._backend == "torch":
            data = {
                "backend":     "torch",
                "state_dict":  self._model.state_dict(),
                "labels":      GESTURE_LABELS,
            }
        elif self._backend == "sklearn":
            data = {
                "backend": "sklearn",
                "model":   self._model,
                "encoder": self._encoder,
                "labels":  GESTURE_LABELS,
            }
        else:
            raise RuntimeError("No model to save.")

        with open(CNN_MODEL_PATH, "wb") as f:
            pickle.dump(data, f)
        print(f"[GestureClassifier] Model saved to {CNN_MODEL_PATH}")

    # ── Public: predict ─────────────────────────────────────────────────
    def predict(self, hand_landmarks, hand_label: str = "Right") -> Tuple[str, float]:
        """
        Predict gesture for a single hand.
        Returns (gesture_name, confidence).
        Falls back to rule-based classifier if CNN confidence < threshold.
        """
        if not self.loaded:
            # No CNN loaded — use rule-based directly
            return classify_gesture(hand_landmarks, hand_label), 0.0

        vec = landmarks_to_vector(hand_landmarks)
        if vec is None:
            # Invalid/corrupted landmarks (NaN/degenerate/low-visibility) —
            # fall back to rule-based so real-time inference doesn't crash.
            rule_label = classify_gesture(hand_landmarks, hand_label)
            return rule_label, 1.0

        try:
            if self._backend == "torch":
                label, conf = self._predict_torch(vec)
            else:
                label, conf = self._predict_sklearn(vec)
        except Exception as e:
            print(f"[GestureClassifier] predict error: {e}")
            return classify_gesture(hand_landmarks, hand_label), 0.0

        # Fall back to rule-based if confidence is low
        if CNN_FALLBACK and conf < CNN_CONFIDENCE:
            rule_label = classify_gesture(hand_landmarks, hand_label)
            return rule_label, conf

        return label, conf

    def _predict_torch(self, vec: np.ndarray) -> Tuple[str, float]:
        import torch, torch.nn.functional as F
        with torch.no_grad():
            x     = torch.tensor(vec, dtype=torch.float32).unsqueeze(0)
            logit = self._model(x)
            prob  = F.softmax(logit, dim=1).squeeze().numpy()
        idx  = int(np.argmax(prob))
        return GESTURE_LABELS[idx], float(prob[idx])

    def _predict_sklearn(self, vec: np.ndarray) -> Tuple[str, float]:
        prob = self._model.predict_proba([vec])[0]
        idx  = int(np.argmax(prob))
        # sklearn stores classes in encoder order
        label = GESTURE_LABELS[self._encoder.inverse_transform([idx])[0]]
        return label, float(prob[idx])


# ═══════════════════════════════════════════════════════════════════════
#  Dataset collection helper
# ═══════════════════════════════════════════════════════════════════════

class GestureDataCollector:
    """
    Interactive tool to collect training samples.

    Usage:
        collector = GestureDataCollector()
        collector.start_session("draw")   # label to record
        collector.record(hand_landmarks)  # call this in your frame loop
        collector.end_session()           # finalize samples
        X, y = collector.get_dataset()
        collector.save_dataset("assets/gesture_data/dataset.npz")
    """

    def __init__(self):
        self._X: List[np.ndarray] = []
        self._y: List[int]        = []
        self._current_label: int  = -1
        self._session_count: int  = 0

    def start_session(self, label: str):
        if label not in GESTURE_LABELS:
            raise ValueError(f"Unknown label '{label}'. Choose from {GESTURE_LABELS}")
        self._current_label  = GESTURE_LABELS.index(label)
        self._session_count  = 0

    def record(self, hand_landmarks) -> int:
        """Record one sample. Returns number of samples recorded this session."""
        if self._current_label < 0:
            raise RuntimeError("Call start_session() first.")
        vec = landmarks_to_vector(hand_landmarks)
        if vec is None:
            # Skip invalid samples (prevents training-set corruption).
            return self._session_count

        self._X.append(vec)
        self._y.append(self._current_label)
        self._session_count += 1
        return self._session_count

    def end_session(self) -> int:
        count = self._session_count
        self._current_label  = -1
        self._session_count  = 0
        return count

    def get_dataset(self) -> Tuple[np.ndarray, np.ndarray]:
        return np.array(self._X, dtype=np.float32), np.array(self._y, dtype=np.int64)

    def save_dataset(self, path: str):
        X, y = self.get_dataset()
        np.savez(path, X=X, y=y)
        print(f"[GestureDataCollector] Saved {len(y)} samples to {path}")

    @staticmethod
    def load_dataset(path: str) -> Tuple[np.ndarray, np.ndarray]:
        data = np.load(path)
        return data["X"], data["y"]

    def augment(self, X: np.ndarray, y: np.ndarray,
                noise_std: float = 0.01, n_copies: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """
        Light augmentation: add Gaussian noise to each sample n_copies times.
        This prevents over-fitting when the collected dataset is small.
        """
        def _renormalize(vecs: np.ndarray) -> np.ndarray:
            # Mirror landmarks_to_vector() normalization: max absolute coordinate = 1.
            mx = np.max(np.abs(vecs), axis=1, keepdims=True)
            mx = np.where(mx > 1e-9, mx, 1.0).astype(np.float32)
            return (vecs / mx).astype(np.float32)

        extras_X, extras_y = [], []
        for _ in range(n_copies):
            noise = np.random.normal(0, noise_std, X.shape).astype(np.float32)
            aug = X + noise
            aug = _renormalize(aug)
            extras_X.append(aug)
            extras_y.append(y)

        X_aug = np.concatenate([_renormalize(X)] + extras_X, axis=0)
        y_aug = np.concatenate([y] + extras_y, axis=0)
        shuffle = np.random.permutation(len(y_aug))
        return X_aug[shuffle], y_aug[shuffle]


# ═══════════════════════════════════════════════════════════════════════
#  Convenience: generate synthetic training data for bootstrap
# ═══════════════════════════════════════════════════════════════════════

def generate_synthetic_samples(n_per_class: int = 200,
                                noise: float = 0.04) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic landmark vectors for each gesture class.
    Uses idealised finger-position prototypes + Gaussian noise.
    OPTIMIZED: Added hand rotations, perspective transforms, and scale variations.
    Allows the CNN to be bootstrapped without any real capture session.
    """
    rng = np.random.default_rng(42)

    # Prototypical (normalised) finger extension patterns.
    # Layout: [wrist, thumb_cmc, thumb_mcp, thumb_ip, thumb_tip,
    #          idx_mcp..tip, mid_mcp..tip, ring_mcp..tip, pinky_mcp..tip]
    # We use a simplified hand silhouette with realistic proportions.

    def _hand(fingers_up: List[bool]) -> np.ndarray:
        """
        Create a 63-float vector from a boolean list [thumb, idx, mid, ring, pinky].
        Each segment is a small 3D offset from the previous joint.
        """
        pts = np.zeros((21, 3), dtype=np.float32)
        # Wrist at origin; palm root joints across x
        palm_x  = [0.00, 0.05, 0.12, 0.19, 0.26]
        palm_y  = [0.00, -0.08, -0.10, -0.10, -0.09]
        # Finger segment lengths (thumb shorter)
        seg_len = [
            [0.06, 0.04, 0.03],  # thumb
            [0.10, 0.07, 0.05],  # index
            [0.10, 0.08, 0.06],  # middle
            [0.09, 0.07, 0.05],  # ring
            [0.07, 0.05, 0.04],  # pinky
        ]
        joint_start = [1, 5, 9, 13, 17]  # MCP of each finger
        for fi, (up, segs) in enumerate(zip(fingers_up, seg_len)):
            bx, by = palm_x[fi], palm_y[fi]
            pts[joint_start[fi]] = [bx, by, 0.0]
            for si, sl in enumerate(segs):
                ji = joint_start[fi] + si + 1
                if up:
                    pts[ji] = pts[ji - 1] + [0, -sl, 0]  # finger extends upward
                else:
                    pts[ji] = pts[ji - 1] + [sl * 0.3, sl * 0.5, 0]  # curl
        # Normalise
        mx = np.max(np.abs(pts)) + 1e-9
        pts /= mx
        return pts.flatten()
    
    def _augment_sample(vec: np.ndarray, rng) -> np.ndarray:
        """
        OPTIMIZED: Apply realistic augmentations to a 63-vector.
        - Hand rotation (±20° in image plane)
        - 3D perspective (viewing angle variation)
        - Scale variation (±30%)
        """
        pts = vec.reshape(21, 3)
        
        # 1. Rotation in x-y plane (±20°)
        angle = rng.uniform(-20, 20) * np.pi / 180
        c, s = np.cos(angle), np.sin(angle)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float32)
        pts = pts @ R.T
        
        # 2. Perspective variation (tilt in 3D) - scale z slightly
        perspective = rng.uniform(0.8, 1.2)
        pts[:, 2] *= perspective
        
        # 3. Scale variation (±30%)
        scale = rng.uniform(0.7, 1.3)
        pts *= scale
        
        # Renormalise
        mx = np.max(np.abs(pts)) + 1e-9
        pts /= mx
        
        return pts.flatten().astype(np.float32)

    # Map gesture classes to finger extension patterns
    patterns = {
        "draw":      [False, True,  False, False, False],
        "erase":     [False, True,  True,  False, False],
        "select":    [False, True,  True,  True,  False],
        "open_palm": [True,  True,  True,  True,  True],
        # Make each class distinct. In particular, pinch must differ from fist.
        "fist":      [False, False, False, False, False],
        "thumbs_up": [True,  False, False, False, False],
        # "pinch" is special: we will later force thumb tip & index tip proximity.
        "pinch":     [True,  True,  False, False, False],
        # "ok" is special: we force thumb tip close to index tip while other fingers are up.
        "ok":        [False, True,  True,  True,  True],
        "idle":      [True,  True,  False, True,  True],
    }

    X_list, y_list = [], []
    for label, pat in patterns.items():
        proto = _hand(pat).reshape(21, 3)

        # Gesture-specific landmark shaping so classes become learnable from 63-d vectors.
        if label == "pinch":
            # Bring thumb tip (4) close to index tip (8); keep other fingers curled by pat.
            thumb_tip = proto[4].copy()
            index_tip = proto[8].copy()
            mid = (thumb_tip + index_tip) / 2.0
            # Pull both tips toward midpoint to make them close regardless of initial hand pose.
            proto[4] = mid + (thumb_tip - mid) * 0.15
            proto[8] = mid + (index_tip - mid) * 0.15
        elif label == "ok":
            # Force thumb tip close to index tip, while keeping middle/ring/pinky extended via pat.
            thumb_tip = proto[4].copy()
            index_tip = proto[8].copy()
            mid = (thumb_tip + index_tip) / 2.0
            proto[4] = mid + (thumb_tip - mid) * 0.12
            proto[8] = mid + (index_tip - mid) * 0.12

        proto = proto.flatten()
        cls   = GESTURE_LABELS.index(label)
        for _ in range(n_per_class):
            # OPTIMIZED: Generate base sample with noise
            sample = proto + rng.normal(0, noise, 63).astype(np.float32)
            # Renormalise (keeps inference compatibility)
            mx = np.max(np.abs(sample)) + 1e-9
            sample /= mx
            
            # OPTIMIZED: Apply augmentations (rotation, perspective, scale)
            sample = _augment_sample(sample, rng)
            
            X_list.append(sample)
            y_list.append(cls)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    shuffle = rng.permutation(len(y))
    return X[shuffle], y[shuffle]


# ═══════════════════════════════════════════════════════════════════════
#  CLI: train on synthetic data and save a bootstrap model
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Gesture CNN Trainer ===")
    print(f"Backend: {'PyTorch' if _TORCH_OK else 'sklearn' if _SKLEARN_OK else 'NONE'}")

    print("\nGenerating synthetic training data ...")
    X, y = generate_synthetic_samples(n_per_class=300)
    print(f"  Total samples: {len(y)}")

    # Augment
    collector = GestureDataCollector()
    X_aug, y_aug = collector.augment(X, y, n_copies=2)
    print(f"  After augmentation: {len(y_aug)}")

    print("\nTraining model ...")
    clf = GestureClassifier()
    acc = clf.train(X_aug, y_aug)
    print(f"\nFinal accuracy on training data: {acc:.1%}")

    clf.save()
    print(f"\nModel saved. Ready for use in the drawing platform.")
    print("To improve accuracy, capture real hand data using the 'T' key in 2D mode.")
