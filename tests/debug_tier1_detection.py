"""
Debug script to test rule-based shape detection (Tier 1)
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("RULE-BASED DETECTION DEBUG (TIER 1)")
print("=" * 80)

try:
    from utils.shape_ai import detect_and_snap
    
    # Test with a rough circle
    print("\n[TEST 1] Testing rule-based detector with rough circle...")
    rough_circle = []
    for i in range(30):
        angle = (i / 30) * 2 * np.pi
        x = int(100 + 50 * np.cos(angle) + np.random.randint(-8, 8))  # Add noise
        y = int(100 + 50 * np.sin(angle) + np.random.randint(-8, 8))
        rough_circle.append((x, y))
    
    print(f"  - Stroke points: {len(rough_circle)}")
    
    result = detect_and_snap(rough_circle)
    if result:
        shape, clean_pts = result
        if shape:
            print(f"✓ Tier 1 detected: {shape}")
            print(f"  - Clean points: {len(clean_pts)}")
        else:
            print(f"✗ Tier 1 returned (None, None)")
    else:
        print(f"✗ Tier 1 returned None")
    
    # Test with a square
    print("\n[TEST 2] Testing rule-based detector with square...")
    square = []
    for i in range(40):
        if i < 10:
            square.append((50 + i*5, 50))
        elif i < 20:
            square.append((100, 50 + (i-10)*5))
        elif i < 30:
            square.append((100 - (i-20)*5, 100))
        else:
            square.append((50, 100 - (i-30)*5))
    
    print(f"  - Stroke points: {len(square)}")
    
    result = detect_and_snap(square)
    if result:
        shape, clean_pts = result
        if shape:
            print(f"✓ Tier 1 detected: {shape}")
        else:
            print(f"✗ Tier 1 returned (None, None)")
    else:
        print(f"✗ Tier 1 returned None")
    
    # Test with a line
    print("\n[TEST 3] Testing rule-based detector with line...")
    line = []
    for i in range(20):
        x = 50 + i * 5
        y = 50 + i * 3 + np.random.randint(-3, 3)
        line.append((int(x), int(y)))
    
    print(f"  - Stroke points: {len(line)}")
    
    result = detect_and_snap(line)
    if result:
        shape, clean_pts = result
        if shape:
            print(f"✓ Tier 1 detected: {shape}")
        else:
            print(f"✗ Tier 1 returned (None, None)")
    else:
        print(f"✗ Tier 1 returned None")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
