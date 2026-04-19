"""
train_drawing_cnn.py - Train the CNN for shape recognition.
"""
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader, random_split

from utils.dataset_generator import create_dataset, IMG_SIZE
from ml.drawing_cnn import DrawingCNN, MODEL_PATH

# --- Training Parameters ---
EPOCHS = 20
BATCH_SIZE = 64
LEARNING_RATE = 0.001
VALIDATION_SPLIT = 0.2

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 1. Generate Dataset
    print("Generating synthetic dataset...")
    X_data, y_data = create_dataset()
    
    # Reshape and convert to tensors
    X_tensor = torch.from_numpy(X_data).float().unsqueeze(1) # Add channel dimension
    y_tensor = torch.from_numpy(y_data).long()
    
    dataset = TensorDataset(X_tensor, y_tensor)
    
    # 2. Create DataLoaders
    val_size = int(len(dataset) * VALIDATION_SPLIT)
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)
    
    print(f"Dataset created: {len(dataset)} samples")
    print(f"Training set: {len(train_ds)}, Validation set: {len(val_ds)}")

    # 3. Initialize Model, Loss, Optimizer
    model = DrawingCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    # 4. Training Loop
    best_val_acc = 0.0
    print("\nStarting training...")

    for epoch in range(EPOCHS):
        model.train()
        running_loss = 0.0
        for i, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)
            
            # Zero the parameter gradients
            optimizer.zero_grad()
            
            # Forward + backward + optimize
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            
        train_loss = running_loss / len(train_loader)
        
        # Validation
        model.eval()
        correct = 0
        total = 0
        val_loss = 0.0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                val_loss += criterion(outputs, labels).item()
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        val_accuracy = 100 * correct / total
        val_loss /= len(val_loader)

        print(f"Epoch [{epoch+1}/{EPOCHS}], "
              f"Train Loss: {train_loss:.4f}, "
              f"Val Loss: {val_loss:.4f}, "
              f"Val Acc: {val_accuracy:.2f}%")
        
        # Save the best model
        if val_accuracy > best_val_acc:
            best_val_acc = val_accuracy
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"  -> New best model saved to {MODEL_PATH} (Acc: {best_val_acc:.2f}%)")

    print("\nFinished Training!")
    print(f"Final best model saved with accuracy: {best_val_acc:.2f}%")

if __name__ == '__main__':
    main()
