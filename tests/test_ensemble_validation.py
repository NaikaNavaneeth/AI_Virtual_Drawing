"""
test_ensemble_validation.py - Complete validation suite (Phase 3.3)

Test three approaches:
1. MLP DIRECT: Test model on native 28x28 images (baseline/expected accuracy)
2. MLP STROKE: Test model via point-cloud stroke pipeline (real-world scenario)
3. ENSEMBLE: Full ensemble detection (production)

This helps identify data pipeline losses and ensemble effectiveness.
"""
import numpy as np
import cv2
from utils.dataset_generator import generate_shape
from utils.shape_mlp_ai import detect_and_snap_mlp
from utils.ensemble_detection import EnsembleDetector
from ml.drawing_mlp import DrawingMLP


def run_validation():
    """Run complete 3-method validation on 100 synthetic shapes."""
    print("="*70)
    print("ENSEMBLE VALIDATION TEST SUITE")
    print("="*70)
    
    # Setup
    shape_names = ["circle", "square", "triangle", "line"]
    shapes_per_class = 25
    total_shapes = shapes_per_class * 4
    
    # Initialize results tracking
    results = {}
    for method in ["mlp_direct", "mlp_stroke", "ensemble"]:
        results[method] = {
            "correct": 0, "total": 0,
            "per_class": {shape: {"correct": 0, "total": 0} for shape in shape_names},
            "confidences": []
        }
    
    # Load MLP once for all tests
    clf = DrawingMLP()
    clf.load()
    
    # Generate and test
    print(f"\nGenerating {total_shapes} test shapes...")
    test_count = 0
    
    for shape_id in range(4):
        shape_name = shape_names[shape_id]
        print(f"  Testing {shape_name}... ", end="", flush=True)
        
        for i in range(shapes_per_class):
            # Generate test image
            img = generate_shape(shape_id)
            
            # Extract points from contours (point cloud)
            contours, _ = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            pts = []
            for contour in contours:
                for point in contour:
                    x, y = int(point[0][0]), int(point[0][1])
                    pts.append((x, y))
            
            if len(pts) < 12:  # Skip if not enough points
                continue
            
            # TEST 1: MLP DIRECT (model on native 28x28 image)
            predicted_shape, confidence = clf.predict(img)
            _record_result(results, "mlp_direct", shape_name, predicted_shape, confidence)
            
            # TEST 2: MLP STROKE (model via point pipeline)
            try:
                predicted_shape, _, confidence = detect_and_snap_mlp(pts, return_confidence=True)
                _record_result(results, "mlp_stroke", shape_name, predicted_shape, confidence)
            except:
                _record_result(results, "mlp_stroke", shape_name, None, 0.0)
            
            # TEST 3: ENSEMBLE (full pipeline)
            try:
                result = EnsembleDetector.detect(pts)
                predicted_shape = result.shape if result else None
                confidence = result.confidence if result else 0.0
                _record_result(results, "ensemble", shape_name, predicted_shape, confidence)
            except:
                _record_result(results, "ensemble", shape_name, None, 0.0)
            
            test_count += 1
        
        print("[OK]")
    
    # Print report
    print_report(results, total_shapes)


def _record_result(results, method, true_label, pred_label, confidence):
    """Record a detection result."""
    results[method]["total"] += 1
    results[method]["per_class"][true_label]["total"] += 1
    results[method]["confidences"].append(confidence)
    
    if pred_label == true_label:
        results[method]["correct"] += 1
        results[method]["per_class"][true_label]["correct"] += 1


def print_report(results, total_shapes):
    """Print validation report."""
    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)
    
    shape_names = ["circle", "square", "triangle", "line"]
    
    for method in ["mlp_direct", "mlp_stroke", "ensemble"]:
        data = results[method]
        total = data["total"]
        correct = data["correct"]
        acc = (correct / total * 100) if total > 0 else 0
        
        avg_conf = np.mean(data["confidences"]) if data["confidences"] else 0
        std_conf = np.std(data["confidences"]) if data["confidences"] else 0
        
        print(f"\n{method.upper()}")
        print(f"  Overall: {correct}/{total} = {acc:.1f}%")
        print(f"  Confidence: {avg_conf:.3f} +- {std_conf:.3f}")
        print(f"  Per-class:")
        
        for shape in shape_names:
            class_data = data["per_class"][shape]
            c_total = class_data["total"]  
            c_correct = class_data["correct"]
            c_acc = (c_correct / c_total * 100) if c_total > 0 else 0
            print(f"    {shape:10s}: {c_correct:2d}/{c_total:2d} = {c_acc:5.1f}%")
    
    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    direct_acc = results["mlp_direct"]["correct"] / max(results["mlp_direct"]["total"], 1)
    stroke_acc = results["mlp_stroke"]["correct"] / max(results["mlp_stroke"]["total"], 1)
    ensemble_acc = results["ensemble"]["correct"] / max(results["ensemble"]["total"], 1)
    
    print(f"\nMLP DIRECT Accuracy: {direct_acc*100:.1f}% (BASELINE - expected)")
    print(f"MLP STROKE Accuracy: {stroke_acc*100:.1f}% (via point pipeline)")
    print(f"ENSEMBLE Accuracy:   {ensemble_acc*100:.1f}% (real-world)")
    
    pipe_loss = direct_acc - stroke_acc
    print(f"\nPipeline accuracy loss: {pipe_loss*100:.1f}%")
    
    if pipe_loss > 0.05:
        print("  [!] Significant pipeline loss detected!")
    else:
        print("  [OK] Pipeline preserves accuracy well")
    
    if ensemble_acc >= stroke_acc * 0.95:
        print("  [OK] Ensemble matches stroke pipeline")
    else:
        print("  [!] Ensemble underperforms pipeline")
    
    if direct_acc >= 0.95:
        print("\n[OK] MODEL STATUS: Production-ready (>95% baseline accuracy)")
    elif direct_acc >= 0.85:
        print("\n[!] MODEL STATUS: Good but could improve (85-95%)")
    else:
        print("\n[X] MODEL STATUS: Needs work (<85%)")


if __name__ == "__main__":
    run_validation()
