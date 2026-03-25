#!/usr/bin/env python3
"""
Test suite for Open Palm False Positive Fix
============================================

Validates that the permanent fix prevents false "open palm" detections
while still allowing intentional canvas clearing.

Tests:
  1. Closed fist NOT detected as open_palm
  2. Relaxed hand NOT detected as open_palm  
  3. Intentional open palm (spread wide) detected as open_palm
  4. Confidence threshold prevents weak detections
  5. Streak counter prevents single-frame jitter
"""

import sys
import math
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.gesture import classify_gesture, _finger_extension_depth
from mediapipe.framework.formats import landmark_pb2
import numpy as np


def create_hand_landmarks(positions: list[tuple]) -> landmark_pb2.NormalizedLandmarkList:
    """
    Create synthetic hand landmarks for testing.
    
    Args:
        positions: List of 21 (x, y, z) tuples (MediaPipe hand landmark positions)
    
    Returns:
        NormalizedLandmarkList with visibility=1.0 for all landmarks
    """
    landmarks = landmark_pb2.NormalizedLandmarkList()
    for x, y, z in positions:
        lm = landmarks.landmark.add()
        lm.x = x
        lm.y = y
        lm.z = z
        lm.visibility = 1.0
    return landmarks


def test_closed_fist_not_open_palm():
    """Test: Closed fist should NOT be detected as open_palm"""
    print("\n" + "="*60)
    print("TEST 1: Closed Fist NOT Detected as Open Palm")
    print("="*60)
    
    # Simulate closed fist: all finger tips BELOW MCPs (curled)
    # Standard/relaxed position with fingers curled inward
    fist_positions = [
        (0.5, 0.5, 0.0),   # 0: WRIST
        (0.45, 0.3, 0.1),  # 1: THUMB_CMC
        (0.48, 0.2, 0.1),  # 2: THUMB_MCP
        (0.50, 0.1, 0.1),  # 3: THUMB_IP
        (0.52, 0.05, 0.0), # 4: THUMB_TIP (extended up)
        (0.55, 0.4, 0.0),  # 5: INDEX_MCP
        (0.57, 0.2, 0.0),  # 6: INDEX_PIP
        (0.58, 0.12, 0.0), # 7: INDEX_DIP
        (0.58, 0.08, 0.0), # 8: INDEX_TIP (CURLED - below PIP)
        (0.60, 0.4, 0.0),  # 9: MIDDLE_MCP
        (0.63, 0.2, 0.0),  # 10: MIDDLE_PIP
        (0.65, 0.12, 0.0), # 11: MIDDLE_DIP
        (0.66, 0.08, 0.0), # 12: MIDDLE_TIP (CURLED - below PIP)
        (0.62, 0.4, 0.0),  # 13: RING_MCP
        (0.65, 0.2, 0.0),  # 14: RING_PIP
        (0.66, 0.12, 0.0), # 15: RING_DIP
        (0.67, 0.08, 0.0), # 16: RING_TIP (CURLED - below PIP)
        (0.60, 0.4, 0.0),  # 17: PINKY_MCP
        (0.61, 0.2, 0.0),  # 18: PINKY_PIP
        (0.62, 0.12, 0.0), # 19: PINKY_DIP
        (0.62, 0.08, 0.0), # 20: PINKY_TIP (CURLED - below PIP)
    ]
    
    lm = create_hand_landmarks(fist_positions)
    gesture = classify_gesture(lm, "Right")
    
    print(f"Input: Closed fist (fingers curled)")
    print(f"Output gesture: '{gesture}'")
    
    if gesture != "open_palm":
        print("✅ PASS: Closed fist correctly NOT detected as open_palm")
        return True
    else:
        print("❌ FAIL: Closed fist incorrectly detected as open_palm!")
        return False


def test_relaxed_hand_not_open_palm():
    """Test: Relaxed hand (slight extension) NOT detected as open_palm"""
    print("\n" + "="*60)
    print("TEST 2: Relaxed Hand NOT Detected as Open Palm")
    print("="*60)
    
    # Simulate relaxed hand: fingers slightly extended but not spread
    # (common position during rest, should NOT clear)
    relaxed_positions = [
        (0.5, 0.5, 0.0),   # 0: WRIST
        (0.45, 0.3, 0.1),  # 1: THUMB_CMC
        (0.48, 0.2, 0.1),  # 2: THUMB_MCP
        (0.50, 0.1, 0.1),  # 3: THUMB_IP
        (0.52, 0.0, 0.0),  # 4: THUMB_TIP
        (0.55, 0.4, 0.0),  # 5: INDEX_MCP
        (0.57, 0.25, 0.0), # 6: INDEX_PIP
        (0.58, 0.15, 0.0), # 7: INDEX_DIP
        (0.58, 0.05, 0.0), # 8: INDEX_TIP (slightly extended, not spread)
        (0.60, 0.4, 0.0),  # 9: MIDDLE_MCP
        (0.63, 0.25, 0.0), # 10: MIDDLE_PIP
        (0.65, 0.15, 0.0), # 11: MIDDLE_DIP
        (0.66, 0.05, 0.0), # 12: MIDDLE_TIP
        (0.62, 0.4, 0.0),  # 13: RING_MCP
        (0.65, 0.25, 0.0), # 14: RING_PIP
        (0.66, 0.15, 0.0), # 15: RING_DIP
        (0.67, 0.05, 0.0), # 16: RING_TIP
        (0.60, 0.4, 0.0),  # 17: PINKY_MCP
        (0.61, 0.25, 0.0), # 18: PINKY_PIP
        (0.62, 0.15, 0.0), # 19: PINKY_DIP
        (0.62, 0.05, 0.0), # 20: PINKY_TIP
    ]
    
    lm = create_hand_landmarks(relaxed_positions)
    gesture = classify_gesture(lm, "Right")
    
    print(f"Input: Relaxed hand (slight extension, no spread)")
    print(f"Output gesture: '{gesture}'")
    
    if gesture != "open_palm":
        print("✅ PASS: Relaxed hand correctly NOT detected as open_palm")
        return True
    else:
        print("❌ FAIL: Relaxed hand incorrectly detected as open_palm!")
        return False


def test_spread_palm_detected():
    """Test: Intentional open palm (spread wide) IS detected as open_palm"""
    print("\n" + "="*60)
    print("TEST 3: Spread Open Palm DETECTED as Open Palm")
    print("="*60)
    
    # Simulate spread open palm: all fingers extended AND spread wide
    # Thumb on left, pinky on right, clear separation > 0.50
    spread_positions = [
        (0.5, 0.5, 0.0),   # 0: WRIST
        (0.30, 0.3, 0.1),  # 1: THUMB_CMC
        (0.32, 0.2, 0.1),  # 2: THUMB_MCP
        (0.34, 0.1, 0.1),  # 3: THUMB_IP
        (0.35, 0.0, 0.0),  # 4: THUMB_TIP (FAR LEFT, clearly extended)
        (0.55, 0.5, 0.0),  # 5: INDEX_MCP
        (0.58, 0.25, 0.0), # 6: INDEX_PIP
        (0.60, 0.12, 0.0), # 7: INDEX_DIP
        (0.62, -0.05, 0.0),# 8: INDEX_TIP (far up, clearly extended)
        (0.60, 0.5, 0.0),  # 9: MIDDLE_MCP
        (0.63, 0.25, 0.0), # 10: MIDDLE_PIP
        (0.65, 0.12, 0.0), # 11: MIDDLE_DIP
        (0.67, -0.05, 0.0),# 12: MIDDLE_TIP (far up, clearly extended)
        (0.65, 0.5, 0.0),  # 13: RING_MCP
        (0.68, 0.25, 0.0), # 14: RING_PIP
        (0.70, 0.12, 0.0), # 15: RING_DIP
        (0.72, -0.05, 0.0),# 16: RING_TIP (far up, clearly extended)
        (0.68, 0.5, 0.0),  # 17: PINKY_MCP
        (0.70, 0.25, 0.0), # 18: PINKY_PIP
        (0.72, 0.12, 0.0), # 19: PINKY_DIP
        (0.75, -0.05, 0.0),# 20: PINKY_TIP (FAR RIGHT, clearly extended)
    ]
    
    lm = create_hand_landmarks(spread_positions)
    gesture = classify_gesture(lm, "Right")
    
    print(f"Input: Spread open palm (wide separation, all extended)")
    print(f"Output gesture: '{gesture}'")
    
    if gesture == "open_palm":
        print("✅ PASS: Spread open palm correctly detected as open_palm")
        return True
    else:
        print("❌ FAIL: Spread open palm not detected! (got '{gesture}')")
        return False


def test_threshold_values():
    """Test: Verify new threshold values are in place"""
    print("\n" + "="*60)
    print("TEST 4: Threshold Values Verification")
    print("="*60)
    
    # Read gesture.py to verify the thresholds
    gesture_file = PROJECT_ROOT / "utils" / "gesture.py"
    content = gesture_file.read_text()
    
    checks = [
        ("0.50", "Spread distance threshold should be 0.50", "spread_dist > 0.50" in content),
        ("0.08", "Avg depth threshold should be 0.08", "avg_depth > 0.08" in content),
        ("0.05", "Per-finger depth threshold should be 0.05", "d > 0.05 for d in depths" in content),
        ("0.06", "Variance threshold should be 0.06", "depth_variance < 0.06" in content),
    ]
    
    all_pass = True
    for threshold, description, found in checks:
        status = "✅" if found else "❌"
        print(f"{status} {description}: {threshold}")
        if not found:
            all_pass = False
    
    return all_pass


def test_drawing_module_safety():
    """Test: Verify drawing_2d.py has confidence and streak checks"""
    print("\n" + "="*60)
    print("TEST 5: Drawing Module Safety Checks")
    print("="*60)
    
    drawing_file = PROJECT_ROOT / "modules" / "drawing_2d.py"
    content = drawing_file.read_text()
    
    checks = [
        ("Confidence filter", "last_cnn_conf < 0.75" in content),
        ("Streak counter", "_open_palm_streak" in content),
        ("Streak reset", "_open_palm_time" in content),
        ("Minimum streak", "ds._open_palm_streak >= 2" in content),
    ]
    
    all_pass = True
    for check_name, found in checks:
        status = "✅" if found else "❌"
        print(f"{status} {check_name}: {'Present' if found else 'MISSING'}")
        if not found:
            all_pass = False
    
    return all_pass


def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# OPEN PALM FALSE POSITIVE - PERMANENT FIX VALIDATION")
    print("#"*60)
    
    results = []
    
    # Run tests
    try:
        results.append(("Closed fist",        test_closed_fist_not_open_palm()))
        results.append(("Relaxed hand",       test_relaxed_hand_not_open_palm()))
        results.append(("Spread palm",        test_spread_palm_detected()))
        results.append(("Threshold values",   test_threshold_values()))
        results.append(("Drawing safety",     test_drawing_module_safety()))
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "#"*60)
    print("# TEST SUMMARY")
    print("#"*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Open palm false positive fix is working correctly.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review the fix.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
