"""
ml/drawing_cnn.py - CNN model for shape/drawing recognition.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "drawing_cnn.pkl")

class DrawingCNN(nn.Module):
    def __init__(self, num_classes=4):
        super(DrawingCNN, self).__init__()
        # Input is 28x28x1
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        
        # After two pools, 28x28 -> 14x14 -> 7x7
        self.fc1 = nn.Linear(64 * 7 * 7, 128)
        self.dropout = nn.Dropout(0.5)
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        
        # Flatten the tensor
        x = x.view(-1, 64 * 7 * 7)
        
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x

class DrawingClassifier:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = DrawingCNN().to(self.device)
        self.labels = ['circle', 'square', 'triangle', 'line']

    def load(self):
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.model.eval()
                print(f"[DrawingCNN] Loaded model from {self.model_path}")
                return True
            except Exception as e:
                print(f"[DrawingCNN] Error loading model: {e}")
                return False
        print(f"[DrawingCNN] Model file not found at {self.model_path}")
        return False

    def predict(self, image):
        """
        Predict the shape from a single image patch.
        The image should be a preprocessed 28x28 numpy array.
        """
        if not hasattr(self, 'model'):
            return "Model not loaded", 0.0

        image = image.astype(np.float32)
        # Normalize to [0, 1]
        image /= 255.0
        
        tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(tensor)
            probabilities = F.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)
            
            label = self.labels[predicted.item()]
            return label, confidence.item()
