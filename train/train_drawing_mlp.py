"""
train_drawing_mlp.py - Train the scikit-learn MLP for shape recognition.
"""
import numpy as np
import joblib
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from utils.dataset_generator import create_dataset, IMG_SIZE
from ml.drawing_mlp import MODEL_PATH

def main():
    # 1. Generate Dataset
    print("Generating synthetic dataset...")
    X_data, y_data = create_dataset()
    
    # Flatten the image data for MLP
    n_samples = len(X_data)
    X_data_flat = X_data.reshape((n_samples, -1)).astype(np.float32)
    
    # Normalize to 0-1 range but ensure no NaN
    X_data_flat = X_data_flat / 255.0
    X_data_flat = np.nan_to_num(X_data_flat, nan=0.0, posinf=1.0, neginf=0.0)
    
    print(f"Dataset created: {n_samples} samples")
    print(f"Data range after norm: [{X_data_flat.min():.4f}, {X_data_flat.max():.4f}]")
    print(f"NaN count: {np.isnan(X_data_flat).sum()}")

    # 2. Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_data_flat, y_data, test_size=0.2, random_state=42, stratify=y_data
    )
    
    print(f"Training set: {len(X_train)}, Test set: {len(X_test)}")

    # 3. Initialize and Train MLPClassifier
    print("\nInitializing MLPClassifier...")
    # Optimized hyperparameters for 20K clean dataset
    model = MLPClassifier(
        hidden_layer_sizes=(512, 256, 128),
        activation='relu',
        solver='adam',
        max_iter=100,
        random_state=1,
        verbose=True,
        learning_rate_init=0.001,
        n_iter_no_change=10
    )
    
    print("Starting training...")
    model.fit(X_train, y_train)
    
    # 4. Evaluate the model
    print("\nFinished training. Evaluating model...")
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nModel accuracy on test set: {accuracy * 100:.2f}%")
    
    # 5. Save the trained model
    if accuracy > 0.90: # Only save if it's reasonably good
        print(f"Saving model to {MODEL_PATH}...")
        joblib.dump(model, MODEL_PATH)
        print("Model saved successfully.")
    else:
        print("Model accuracy is below threshold (90%), not saving.")

if __name__ == '__main__':
    main()
