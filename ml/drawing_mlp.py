"""
ml/drawing_mlp.py - scikit-learn MLP model for shape/drawing recognition.
"""
import numpy as np
import os
import joblib
from sklearn.neural_network import MLPClassifier

MODEL_PATH = os.path.join(os.path.dirname(__file__), "drawing_mlp.pkl")

class DrawingMLP:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.labels = ['circle', 'square', 'triangle', 'line']

    def load(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                print(f"[DrawingMLP] Loaded model from {self.model_path}")
                return True
            except Exception as e:
                print(f"[DrawingMLP] Error loading model: {e}")
                return False
        print(f"[DrawingMLP] Model file not found at {self.model_path}, a new one will be created on training.")
        return False

    def predict(self, image):
        """
        Predict the shape from a single image patch.
        The image should be a preprocessed 28x28 numpy array.
        """
        if self.model is None:
            return "Model not loaded", 0.0

        # Flatten the image
        image_flat = image.reshape(1, -1)
        
        # Predict
        probabilities = self.model.predict_proba(image_flat)
        prediction = self.model.predict(image_flat)
        
        label = self.labels[prediction[0]]
        confidence = np.max(probabilities)
        
        return label, confidence
