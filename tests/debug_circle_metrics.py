"""
Debug script to analyze circle metrics
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("CIRCLE DETECTION METRICS DEBUG")
print("=" * 80)

try:
    # Import metric functions
    from utils.shape_ai import (
        _subsample, _circularity, _aspect_ratio, _straightness,
        _closure_ratio, _rdp_simplify
    )
    
    # Create test circles
    print("\n[TEST 1] Perfect circle (no noise)...")
    perfect_circle = []
    for i in range(40):
        angle = (i / 40) * 2 * np.pi
        x = int(100 + 50 * np.cos(angle))
        y = int(100 + 50 * np.sin(angle))
        perfect_circle.append((x, y))
    
    sub = _subsample(perfect_circle, 64)
    circ = _circularity(sub)
    ar = _aspect_ratio(sub)
    strt = _straightness(sub)
    clos = _closure_ratio(sub)
    
    print(f"  Points: {len(perfect_circle)}")
    print(f"  Circularity: {circ:.3f} (threshold: > 0.90)")
    print(f"  Aspect ratio: {ar:.3f} (threshold: < 1.4)")
    print(f"  Closure ratio: {clos:.3f} (threshold: < 0.15)")
    print(f"  Straightness: {strt:.3f}")
    print(f"  ✓ PASS" if (circ > 0.90 and clos < 0.15 and ar < 1.4) else "  ✗ FAIL")
    
    # Test with rough circle
    print("\n[TEST 2] Rough circle with noise...")
    rough_circle = []
    for i in range(40):
        angle = (i / 40) * 2 * np.pi
        x = int(100 + 50 * np.cos(angle) + np.random.randint(-8, 8))  # Noise
        y = int(100 + 50 * np.sin(angle) + np.random.randint(-8, 8))
        rough_circle.append((x, y))
    
    sub = _subsample(rough_circle, 64)
    circ = _circularity(sub)
    ar = _aspect_ratio(sub)
    strt = _straightness(sub)
    clos = _closure_ratio(sub)
    
    print(f"  Points: {len(rough_circle)}")
    print(f"  Circularity: {circ:.3f} (threshold: > 0.90)")
    print(f"  Aspect ratio: {ar:.3f} (threshold: < 1.4)")
    print(f"  Closure ratio: {clos:.3f} (threshold: < 0.15)")
    print(f"  Straightness: {strt:.3f}")
    print(f"  ✓ PASS" if (circ > 0.90 and clos < 0.15 and ar < 1.4) else "  ✗ FAIL")
    
    # Test with hand-drawn like circle (real user input)
    print("\n[TEST 3] Hand-drawn circle simulation (irregular spacing)...")
    hand_drawn = []
    for i in range(35):  # Fewer points, irregular
        angle = (i / 35) * 2 * np.pi + np.random.rand() * 0.3
        radius = 50 + np.random.randint(-5, 5)
        x = int(100 + radius * np.cos(angle))
        y = int(100 + radius * np.sin(angle))
        hand_drawn.append((x, y))
    
    sub = _subsample(hand_drawn, 64)
    circ = _circularity(sub)
    ar = _aspect_ratio(sub)
    strt = _straightness(sub)
    clos = _closure_ratio(sub)
    
    print(f"  Points: {len(hand_drawn)}")
    print(f"  Circularity: {circ:.3f} (threshold: > 0.90)")
    print(f"  Aspect ratio: {ar:.3f} (threshold: < 1.4)")
    print(f"  Closure ratio: {clos:.3f} (threshold: < 0.15)")
    print(f"  Straightness: {strt:.3f}")
    print(f"  ✓ PASS" if (circ > 0.90 and clos < 0.15 and ar < 1.4) else "  ✗ FAIL")
    
    # Test with open circle (user drew and didn't close it completely)
    print("\n[TEST 4] Open circle (user didn't close it)...")
    open_circle = []
    for i in range(32):  # Only 32/40 points = 80% around the circle
        angle = (i / 40) * 2 * np.pi
        x = int(100 + 50 * np.cos(angle) + np.random.randint(-5, 5))
        y = int(100 + 50 * np.sin(angle) + np.random.randint(-5, 5))
        open_circle.append((x, y))
    
    sub = _subsample(open_circle, 64)
    circ = _circularity(sub)
    ar = _aspect_ratio(sub)
    strt = _straightness(sub)
    clos = _closure_ratio(sub)
    
    print(f"  Points: {len(open_circle)}")
    print(f"  Circularity: {circ:.3f} (threshold: > 0.90)")
    print(f"  Aspect ratio: {ar:.3f} (threshold: < 1.4)")
    print(f"  Closure ratio: {clos:.3f} (threshold: < 0.15)")
    print(f"  Straightness: {strt:.3f}")
    print(f"  ✓ PASS" if (circ > 0.90 and clos < 0.15 and ar < 1.4) else "  ✗ FAIL")
    
    print("\n" + "=" * 80)
    print("ANALYSIS:")
    print("The thresholds might be too strict. Rough circles fail the circularity test.")
    print("Recommendation: Reduce circularity threshold from 0.90 to 0.80-0.85")
    print("=" * 80)
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
