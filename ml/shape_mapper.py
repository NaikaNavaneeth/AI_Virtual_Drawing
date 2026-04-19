"""
ml/shape_mapper.py - Load and use the trained shape mapping model.

This module provides inference for the shape mapping CNN that converts
rough sketches to clean geometric shapes.

Usage:
    from ml.shape_mapper import ShapeMapperInference
    mapper = ShapeMapperInference()
    clean_img = mapper.map_rough_to_clean(rough_img_28x28)
"""
import os
import sys
import torch
import numpy as np
import cv2
from typing import Optional

# Add parent directory to path for imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class ShapeMapperInference:
    """
    Load and use the trained shape mapper model for inference.
    
    The model converts 28x28 rough sketches to clean geometric shapes
    using an encoder-decoder CNN architecture.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the shape mapper.
        
        Args:
            model_path: Path to saved model (default: ml/shape_mapping_model.pth)
        """
        if model_path is None:
            model_path = os.path.join(_PROJECT_ROOT, "ml", "shape_mapping_model.pth")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.model_path = model_path
        self.is_loaded = False
        
        # Try to load the model
        self.load_model()
    
    def load_model(self) -> bool:
        """
        Load the trained shape mapper model.
        
        Returns:
            True if model loaded successfully, False otherwise
        """
        if not os.path.exists(self.model_path):
            print(f"[ShapeMapper] Model not found at {self.model_path}")
            print(f"[ShapeMapper] Train the model with: python train/train_shape_mapping.py")
            return False
        
        try:
            # Import the model architecture
            from train.train_shape_mapping import ShapeMapper
            
            self.model = ShapeMapper().to(self.device)
            state_dict = torch.load(self.model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.is_loaded = True
            
            print(f"[ShapeMapper] Model loaded successfully (device: {self.device})")
            return True
        except Exception as e:
            print(f"[ShapeMapper] Failed to load model: {e}")
            self.model = None
            self.is_loaded = False
            return False
    
    def map_rough_to_clean(self, rough_img: np.ndarray) -> Optional[np.ndarray]:
        """
        Convert a rough sketch to a clean geometric shape.
        
        Args:
            rough_img: 28x28 grayscale image (0-255) or (0.0-1.0)
        
        Returns:
            Clean 28x28 image (0-255), or None if model not loaded
        """
        if not self.is_loaded or self.model is None:
            return None
        
        try:
            # Ensure input is proper size
            if rough_img.shape != (28, 28):
                rough_img = cv2.resize(rough_img, (28, 28))
            
            # Normalize to 0-1 range if needed
            if rough_img.max() > 1.0:
                rough_img = rough_img.astype(np.float32) / 255.0
            else:
                rough_img = rough_img.astype(np.float32)
            
            # Convert to tensor and add batch + channel dimensions
            rough_tensor = torch.FloatTensor(rough_img).unsqueeze(0).unsqueeze(0)
            rough_tensor = rough_tensor.to(self.device)
            
            # Inference
            with torch.no_grad():
                clean_tensor = self.model(rough_tensor)
            
            # Convert back to numpy and scale to 0-255
            clean_img = (clean_tensor.cpu().numpy()[0, 0] * 255).astype(np.uint8)
            
            return clean_img
        except Exception as e:
            print(f"[ShapeMapper] Inference failed: {e}")
            return None
    
    def batch_map_rough_to_clean(self, rough_imgs: np.ndarray) -> Optional[np.ndarray]:
        """
        Convert multiple rough sketches to clean shapes (batch processing).
        
        Args:
            rough_imgs: N x 28 x 28 grayscale images (0-255)
        
        Returns:
            N x 28 x 28 clean images (0-255), or None if model not loaded
        """
        if not self.is_loaded or self.model is None:
            return None
        
        try:
            # Normalize
            if rough_imgs.max() > 1.0:
                rough_imgs = rough_imgs.astype(np.float32) / 255.0
            else:
                rough_imgs = rough_imgs.astype(np.float32)
            
            # Add channel dimension
            rough_tensor = torch.FloatTensor(rough_imgs).unsqueeze(1)
            rough_tensor = rough_tensor.to(self.device)
            
            # Batch inference
            with torch.no_grad():
                clean_tensor = self.model(rough_tensor)
            
            # Convert back
            clean_imgs = (clean_tensor.cpu().numpy() * 255).astype(np.uint8)
            clean_imgs = clean_imgs.squeeze(1)  # Remove channel dimension
            
            return clean_imgs
        except Exception as e:
            print(f"[ShapeMapper] Batch inference failed: {e}")
            return None
