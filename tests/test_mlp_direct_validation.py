"""
test_mlp_direct_validation.py - Direct MLP validation on 28x28 images.

Tests the trained MLP classifier directly on the same synthetic 28x28 images
it was trained on, without the lossy contour->point->image conversion.
"""
import numpy as np
from utils.dataset_generator import generate_shape, create_dataset
from ml.drawing_mlp import DrawingMLP


def validate_mlp_direct():
    """Directly validate MLP on 28x28 synthetic images."""
    print("========== MLP DIRECT VALIDATION ==========")
    print("Testing trained MLP on 28x28 synthetic images\n")
    
    # Load the trained model
    clf = DrawingMLP()
    if not clf.load():
        print("ERROR: Could not load model")
        return
    
    # Generate fresh test dataset
    print("Generating fresh test dataset...")
    X_test, y_test = create_dataset()
    
    # Test on 100 samples (25 per class)
    shape_names = ["circle", "square", "triangle", "line"]
    results = {
        "correct": 0,
        "total": 0,
        "per_class": {shape: {"correct": 0, "total": 0} for shape in shape_names}
    }
    
    config = {0: 25, 1: 25, 2: 25, 3: 25}  # 25 per class
    
    for shape_id in range(4):
        shape_name = shape_names[shape_id]
        correct = 0
        total = config[shape_id]
        
        for i in range(total):
            # Generate test image
            img = generate_shape(shape_id)
            
            # Predict
            label, confidence = clf.predict(img)
            
            is_correct = (label == shape_name)
            if is_correct:
                correct += 1
            
            results["correct"] += (1 if is_correct else 0)
            results["total"] += 1
            results["per_class"][shape_name]["correct"] += (1 if is_correct else 0)
            results["per_class"][shape_name]["total"] += 1
        
        accuracy = correct / total
        print(f"{shape_name:8s}: {correct}/{total} = {accuracy*100:.1f}%")
    
    # Summary
    overall_acc = results["correct"] / results["total"]
    print(f"\nOverall Accuracy: {overall_acc*100:.1f}% ({results['correct']}/{results['total']})")
    
    print("\nPer-Class Breakdown:")
    for shape in shape_names:
        class_result = results["per_class"][shape]
        acc = class_result["correct"] / class_result["total"]
        print(f"  {shape:8s}: {acc*100:6.1f}% ({class_result['correct']}/{class_result['total']})")
    
    # Recommendation
    print("\n" + "="*50)
    if overall_acc >= 0.95:
        print("[OK] MLP accuracy >=95% - Excellent for production!")
    elif overall_acc >= 0.85:
        print("[OK] MLP accuracy 85-95% - Good for production")
    elif overall_acc >= 0.70:
        print("[!] MLP accuracy 70-85% - Acceptable, monitor performance")
    else:
        print("[X] MLP accuracy <70% - Needs retraining")
    
    return results


if __name__ == "__main__":
    validate_mlp_direct()
