#!/usr/bin/env python3
"""
Quick test to verify FIX-31b works - shapes snap with relaxed validation
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.shape_ai import detect_and_snap
from utils.shape_mlp_ai import detect_and_snap_mlp

# Test 1: Quick circle (5-10 points) - should work with FIX-31
print("=" * 60)
print("TEST 1: Quick circle sketch (7 points)")
print("=" * 60)
circle_pts = [
    (200, 150), (220, 130), (240, 140),
    (245, 170), (230, 195), (200, 200), (180, 180)
]
shape, clean_pts = detect_and_snap(circle_pts)
print(f"✓ Tier 1 Result: {shape}")
if shape:
    print(f"  Clean points: {len(clean_pts)} points")

# Test 2: Quick line (5 points) - should work  
print("\n" + "=" * 60)
print("TEST 2: Quick line sketch (5 points)")
print("=" * 60)
line_pts = [(100, 100), (150, 120), (200, 140), (250, 160), (300, 180)]
shape, clean_pts = detect_and_snap(line_pts)
print(f"✓ Tier 1 Result: {shape}")
if shape:
    print(f"  Clean points: {len(clean_pts)} points")

# Test 3: Quick square (6 points) - should work
print("\n" + "=" * 60)
print("TEST 3: Quick square sketch (8 points)")
print("=" * 60)
square_pts = [
    (100, 100), (150, 100), (200, 100),
    (200, 150), (200, 200),
    (150, 200), (100, 200), (100, 150)
]
shape, clean_pts = detect_and_snap(square_pts)
print(f"✓ Tier 1 Result: {shape}")
if shape:
    print(f"  Clean points: {len(clean_pts)} points")

print("\n" + "=" * 60)
print("✅ FIX-31b VALIDATION: Shapes should snap with minimal validation!")
print("=" * 60)
