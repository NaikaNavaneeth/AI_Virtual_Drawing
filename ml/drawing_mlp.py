"""
ml/drawing_mlp.py - scikit-learn MLP model for shape/drawing recognition.

Supports:
- Mode 1 (Default): 4 shapes (circle, square, triangle, line)
- Mode 2 (Extended): 30 shapes (geometric + letters A-Z)

Can be switched at runtime or configured in core/config.py
"""
import numpy as np
import os
import joblib
from sklearn.neural_network import MLPClassifier
from enum import Enum

class MLPMode(Enum):
    """Model configuration modes"""
    STANDARD = "standard"  # 4 shapes
    EXTENDED = "extended"  # 30 shapes

MODEL_PATH_STANDARD = os.path.join(os.path.dirname(__file__), "drawing_mlp.pkl")
MODEL_PATH_EXTENDED = os.path.join(os.path.dirname(__file__), "drawing_mlp_30.pkl")

LABELS_STANDARD = ['circle', 'square', 'triangle', 'line']
LABELS_EXTENDED = [
    # Geometric shapes (6)
    'circle', 'square', 'triangle', 'line', 'pentagon', 'hexagon',
    
    # Letters A-Z (26)
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
    'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
    'U', 'V', 'W', 'X', 'Y', 'Z'
]

class DrawingMLP:
    def __init__(self, mode: MLPMode = MLPMode.STANDARD, model_path=None):
        """
        Initialize Drawing MLP classifier.
        
        Args:
            mode: MLPMode.STANDARD (4 shapes) or MLPMode.EXTENDED (30 shapes)
            model_path: Optional custom model path override
        """
        self.mode = mode
        
        # Determine model path and labels based on mode
        if mode == MLPMode.EXTENDED:
            self.model_path = model_path or MODEL_PATH_EXTENDED
            self.labels = LABELS_EXTENDED
            self.num_classes = 30
        else:
            self.model_path = model_path or MODEL_PATH_STANDARD
            self.labels = LABELS_STANDARD
            self.num_classes = 4
        
        self.model = None
        
        print(f"[DrawingMLP] Initialized in {mode.value} mode ({self.num_classes} shapes)")

    def load(self):
        """Load model from disk"""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                print(f"[DrawingMLP] Loaded {self.mode.value} model from {self.model_path}")
                print(f"[DrawingMLP] Model supports {len(self.labels)} shape classes: {self.labels[:5]}...")
                return True
            except Exception as e:
                print(f"[DrawingMLP] Error loading model: {e}")
                self.model = None
                return False
        
        print(f"[DrawingMLP] Model file not found: {self.model_path}")
        print(f"[DrawingMLP] To train, run: python ml/train_drawing_mlp.py (for 4 shapes)")
        print(f"[DrawingMLP] Or: python ml/train_drawing_mlp_extended.py (for 30 shapes)")
        return False

    def predict(self, image):
        """
        Predict the shape from a single image patch.
        The image should be a preprocessed 28x28 numpy array.
        
        Returns:
            (label_string, confidence_score)
        """
        if self.model is None:
            return "Model not loaded", 0.0

        try:
            # Ensure correct shape
            if image.shape != (28, 28):
                print(f"[DrawingMLP] WARNING: Image shape {image.shape}, expected (28, 28)")
            
            # Flatten the image and normalize to 0-1 range (model was trained on normalized data)
            image_flat = image.reshape(1, -1).astype(np.float32)
            image_flat = image_flat / 255.0  # Normalize to match training
            
            # Predict
            probabilities = self.model.predict_proba(image_flat)
            prediction = self.model.predict(image_flat)
            
            label = self.labels[prediction[0]]
            confidence = float(np.max(probabilities))
            
            return label, confidence
        except Exception as e:
            print(f"[DrawingMLP] Prediction error: {e}")
            return "Error", 0.0
    
    def predict_all_probs(self, image):
        """
        Get predictions for all classes.
        
        Returns:
            Dict mapping labels to probabilities
        """
        if self.model is None:
            return {}
        
        try:
            image_flat = image.reshape(1, -1).astype(np.float32)
            image_flat = image_flat / 255.0  # Normalize to match training
            probabilities = self.model.predict_proba(image_flat)[0]
            
            return {label: float(prob) for label, prob in zip(self.labels, probabilities)}
        except:
            return {}
    
    def set_mode(self, mode: MLPMode):
        """Switch between STANDARD (4) and EXTENDED (30) modes at runtime"""
        print(f"[DrawingMLP] Switching from {self.mode.value} to {mode.value} mode")
        self.mode = mode
        self.model = None  # Clear current model
        
        # Reconfigure for new mode
        if mode == MLPMode.EXTENDED:
            self.model_path = MODEL_PATH_EXTENDED
            self.labels = LABELS_EXTENDED
            self.num_classes = 30
        else:
            self.model_path = MODEL_PATH_STANDARD
            self.labels = LABELS_STANDARD
            self.num_classes = 4
        
        # Try to load new model
        return self.load()
