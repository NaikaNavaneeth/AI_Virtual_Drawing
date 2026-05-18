#!/usr/bin/env python
"""
Diagnostic tool for the two critical issues:
1. Drawing being triggered when index finger is NOT raised
2. Unrelated shapes being detected and transformed incorrectly
"""

import sys, os, cv2, numpy as np
import mediapipe as mp

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from utils.gesture import fingers_up, classify_gesture, _finger_extension_depth
from utils.mp_compat import HandTracker

print("\n" + "="*80)
print("GESTURE DETECTION & DRAWING MODE DIAGNOSTIC")
print("="*80)

# Setup MediaPipe
tracker = HandTracker(max_hands=1, detect_conf=0.65, track_conf=0.60)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

cv2.namedWindow("Gesture Diagnostic", cv2.WINDOW_NORMAL)

print("\n[ISSUE 1] Testing Index Finger Detection")
print("-" * 80)
print("Instructions:")
print("  1. Make a FIST (all fingers closed) - should see 'fist' gesture")
print("  2. Raise ONLY index finger - should see 'draw' gesture")
print("  3. Keep hand at rest - should see 'idle' or 'fist', NOT 'draw'")
print("  4. Watch for FALSE POSITIVES where 'draw' is detected when you haven't raised index")
print("-" * 80 + "\n")

gesture_history = []
max_history = 30

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame = cv2.flip(frame, 1)
    H, W = frame.shape[:2]
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = tracker.process(rgb)
    
    display_text = []
    
    if result.hands:
        hand = result.hands[0]
        lm = hand.landmarks
        label = hand.label
        
        # Get gesture
        gesture = classify_gesture(lm, label)
        gesture_history.append(gesture)
        if len(gesture_history) > max_history:
            gesture_history.pop(0)
        
        # Get finger states
        fup = fingers_up(lm, label)
        thumb, index, middle, ring, pinky = fup
        
        # Get extension depths for debugging
        index_depth = _finger_extension_depth(lm, 8, 5)
        middle_depth = _finger_extension_depth(lm, 12, 9)
        ring_depth = _finger_extension_depth(lm, 16, 13)
        pinky_depth = _finger_extension_depth(lm, 20, 17)
        
        # Determine if draw gesture should be valid
        is_valid_draw = index and not thumb and not middle and not ring and not pinky
        
        display_text.append(f"GESTURE: {gesture}")
        display_text.append(f"Fingers: T={thumb} I={index} M={middle} R={ring} P={pinky}")
        display_text.append(f"Depths: I={index_depth:.4f} M={middle_depth:.4f} R={ring_depth:.4f} P={pinky_depth:.4f}")
        display_text.append(f"Valid DRAW?: {is_valid_draw} (expected when gesture={gesture})")
        
        # Check for false positives
        if gesture == "draw" and not is_valid_draw:
            display_text.append("⚠️  FALSE POSITIVE: 'draw' detected but fingers not in correct state!")
        elif gesture != "draw" and is_valid_draw:
            display_text.append("⚠️  FALSE NEGATIVE: Fingers in draw position but gesture is '" + gesture + "'")
        
        # Count gesture history
        draw_count = sum(1 for g in gesture_history if g == "draw")
        display_text.append(f"Recent 'draw' detections: {draw_count}/{len(gesture_history)}")
    else:
        display_text.append("No hand detected")
    
    # Render text
    y_offset = 30
    for text in display_text:
        color = (0, 255, 0) if "draw" not in text or "⚠️" not in text else (0, 0, 255)
        if "FALSE" in text:
            color = (0, 0, 255)
        cv2.putText(frame, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y_offset += 25
    
    cv2.imshow("Gesture Diagnostic", frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == 27 or key == ord('q'):
        break
    elif key == ord('r'):
        gesture_history.clear()
        print("[Reset] History cleared")

cap.release()
cv2.destroyAllWindows()

print("\n" + "="*80)
print("DIAGNOSTICS COMPLETE")
print("="*80)
