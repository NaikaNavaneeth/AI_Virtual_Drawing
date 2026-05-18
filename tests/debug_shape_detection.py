"""
Debug script to test shape detection pipeline
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("SHAPE DETECTION DEBUG")
print("=" * 80)

# Test 1: Check if MLP model loads
print("\n[TEST 1] MLP Model Loading...")
try:
    from ml.drawing_mlp import DrawingMLP, MLPMode
    mlp = DrawingMLP(mode=MLPMode.STANDARD)
    loaded = mlp.load()
    if loaded:
        print(f"✓ MLP Model loaded successfully")
        print(f"  - Model path: {mlp.model_path}")
        print(f"  - Num classes: {mlp.num_classes}")
        print(f"  - Labels: {mlp.labels}")
    else:
        print("✗ MLP Model failed to load")
except Exception as e:
    print(f"✗ Error loading MLP: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check if utils functions work
print("\n[TEST 2] Shape Detection Functions...")
try:
    from utils.shape_mlp_ai import get_classifier, _preprocess_stroke, _bounding_box
    from utils.shape_ai import detect_and_snap
    print("✓ All shape detection functions imported successfully")
except Exception as e:
    print(f"✗ Error importing functions: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Test with a simple circle stroke (not a perfect circle)
print("\n[TEST 3] Testing with sample circle stroke...")
try:
    from utils.shape_mlp_ai import detect_and_snap_mlp
    
    # Create a simple circle stroke (rough drawing)
    # This simulates what a user might draw - not perfect
    circle_stroke = []
    for angle in np.linspace(0, 2*np.pi, 40):  # 40 points for circle
        x = int(100 + 50 * np.cos(angle))
        y = int(100 + 50 * np.sin(angle))
        circle_stroke.append((x, y))
    
    print(f"  - Stroke points: {len(circle_stroke)}")
    print(f"  - First point: {circle_stroke[0]}")
    print(f"  - Last point: {circle_stroke[-1]}")
    
    # Try detection
    result = detect_and_snap_mlp(circle_stroke, (480, 640))
    if result:
        shape, clean_pts = result
        if shape:
            print(f"✓ Detected: {shape}")
            print(f"  - Clean points: {len(clean_pts) if clean_pts else 0}")
        else:
            print(f"⚠ Detection returned (None, None)")
    else:
        print(f"⚠ Detection returned None")
        
except Exception as e:
    print(f"✗ Error in detection: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test with rough short circle (like user drawing)
print("\n[TEST 4] Testing with rough SHORT circle stroke (user-like)...")
try:
    from utils.shape_mlp_ai import detect_and_snap_mlp
    
    # Create a rougher, shorter circle stroke (what user actually draws)
    rough_circle = []
    for i in range(15):  # Only 15 points - less than minimum 20
        angle = (i / 15) * 2 * np.pi
        x = int(100 + 50 * np.cos(angle) + np.random.randint(-5, 5))  # Add noise
        y = int(100 + 50 * np.sin(angle) + np.random.randint(-5, 5))
        rough_circle.append((x, y))
    
    print(f"  - Stroke points: {len(rough_circle)}")
    
    result = detect_and_snap_mlp(rough_circle, (480, 640))
    if result:
        shape, clean_pts = result
        if shape:
            print(f"✓ Detected: {shape}")
        else:
            print(f"✗ Detection failed (returned None) - likely due to < 20 points")
    else:
        print(f"✗ Detection failed completely")
        
except Exception as e:
    print(f"✗ Error: {e}")

# Test 5: Check minimum points requirement
print("\n[TEST 5] Analyzing minimum points issue...")
print("Current minimum points requirement: 20")
print("Issue: User drawing 15-20 points might be rejected")
print("Solution: Reduce minimum from 20 to 10-15 points")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)
