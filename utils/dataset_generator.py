"""
utils/dataset_generator.py - Generates a synthetic dataset of simple shapes.
"""
import numpy as np
import cv2
import random

IMG_SIZE = 28
NUM_SAMPLES_PER_CLASS = 1000
NUM_CLASSES = 4  # 0: circle, 1: square, 2: triangle, 3: line

def _add_noise(img):
    """Adds various types of noise to simulate rough drawing."""
    # Warping
    rows, cols = img.shape
    src_points = np.float32([[0,0], [cols-1,0], [0,rows-1]])
    dst_points = np.float32([
        [random.uniform(0, cols*0.1), random.uniform(0, rows*0.1)],
        [random.uniform(cols*0.9, cols), random.uniform(0, rows*0.1)],
        [random.uniform(0, cols*0.1), random.uniform(rows*0.9, rows)]
    ])
    M = cv2.getAffineTransform(src_points, dst_points)
    img = cv2.warpAffine(img, M, (cols, rows))

    # Random lines (scratches)
    for _ in range(random.randint(0, 1)):
        x1, y1 = random.randint(0, IMG_SIZE-1), random.randint(0, IMG_SIZE-1)
        x2, y2 = x1 + random.randint(-10, 10), y1 + random.randint(-10, 10)
        cv2.line(img, (x1, y1), (x2, y2), 255, 1)

    # Random pixel noise
    noise = np.random.randint(0, 20, img.shape, dtype=np.uint8)
    img = cv2.add(img, noise)

    return img

def generate_shape(shape_type):
    """Generates a single noisy shape image."""
    img = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    color = 255
    thickness = random.randint(1, 2)
    
    margin = 5
    center = IMG_SIZE // 2
    
    if shape_type == 0:  # Circle
        radius = random.randint(5, IMG_SIZE // 2 - margin)
        cx = center + random.randint(-3, 3)
        cy = center + random.randint(-3, 3)
        cv2.circle(img, (cx, cy), radius, color, thickness)
    
    elif shape_type == 1:  # Square
        side = random.randint(8, IMG_SIZE - 2 * margin)
        x1 = center - side // 2 + random.randint(-3, 3)
        y1 = center - side // 2 + random.randint(-3, 3)
        x2 = x1 + side
        y2 = y1 + side
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

    elif shape_type == 2:  # Triangle
        half_side = random.randint(6, IMG_SIZE // 2 - margin)
        cx = center + random.randint(-3, 3)
        cy = center + random.randint(-3, 3)
        
        p1 = (cx, cy - half_side)
        p2 = (cx - half_side, cy + half_side)
        p3 = (cx + half_side, cy + half_side)
        
        pts = np.array([p1, p2, p3], np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(img, [pts], isClosed=True, color=color, thickness=thickness)

    elif shape_type == 3: # Line
        x1 = margin + random.randint(-3,3)
        y1 = margin + random.randint(-3,3)
        x2 = IMG_SIZE - margin + random.randint(-3,3)
        y2 = IMG_SIZE - margin + random.randint(-3,3)
        if random.random() > 0.5: # make it diagonal
            y2 = y1
        cv2.line(img, (x1,y1), (x2,y2), color, thickness)

    return _add_noise(img)

def create_dataset():
    """Creates the full dataset."""
    X = []
    y = []
    for class_id in range(NUM_CLASSES):
        for _ in range(NUM_SAMPLES_PER_CLASS):
            X.append(generate_shape(class_id))
            y.append(class_id)
            
    # Add some blank images as a "negative" class if needed
    # for _ in range(NUM_SAMPLES_PER_CLASS):
    #     X.append(np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8))
    #     y.append(NUM_CLASSES)

    return np.array(X), np.array(y)

if __name__ == '__main__':
    # For testing: generate and show some samples
    X_data, y_data = create_dataset()
    
    print(f"Generated dataset with shape: {X_data.shape}")
    print(f"Labels shape: {y_data.shape}")

    montage = np.zeros((IMG_SIZE * 5, IMG_SIZE * 10, 1), dtype=np.uint8)

    for i in range(50):
        row = i // 10
        col = i % 10
        
        idx = random.randint(0, len(X_data)-1)
        img = X_data[idx]
        label = y_data[idx]
        
        # Put the image in the montage
        montage[row*IMG_SIZE:(row+1)*IMG_SIZE, col*IMG_SIZE:(col+1)*IMG_SIZE] = img.reshape(IMG_SIZE,IMG_SIZE,1)
    
    cv2.imshow("Generated Shapes", montage)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
