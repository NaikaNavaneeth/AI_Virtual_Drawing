#!/usr/bin/env python
"""
Real-time test: Verify gesture detection at different hand angles

Run this and rotate your hand while keeping index finger extended.
The gesture should remain "draw" at any reasonable angle (15° to 45°+).

KEY TEST: 
  1. Extend only index finger (draw position)
  2. Rotate hand side-to-side (15-45 degrees)
  3. Gesture should stay "draw" throughout rotation
  
If you see it switch to "idle" or "select" during rotation, the fix isn't working.
If it stays "draw" at all angles, FIX-22 is successful.
"""

import cv2
import mediapipe as mp
from utils.gesture import classify_gesture
import math

# MediaPipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

print()
print("=" * 70)
print("REAL-TIME ROTATION ROBUSTNESS TEST")
print("=" * 70)
print()
print("Instructions:")
print("  1. Extend ONLY your index finger (draw position)")
print("  2. Keep hand flat and ROTATE side-to-side (like turning a steering wheel)")
print("  3. Watch the 'Gesture:' display below")
print("  4. Expected: Should stay 'DRAW' even when rotated 15-45°")
print()
print("Controls:")
print("  q - Quit")
print("  d - Show debug histogram of detected gestures")
print()
print("=" * 70)
print()

cap = cv2.VideoCapture(0)
frame_count = 0
gesture_history = []
last_gesture = None

while True:
    success, frame = cap.read()
    if not success:
        print("Failed to capture frame")
        break

    frame_count += 1
    h, w, c = frame.shape
    
    # Flip for selfie view
    frame = cv2.flip(frame, 1)
    
    # Convert to RGB
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Detect hands
    results = hands.process(image_rgb)
    
    # Display info
    cv2.putText(frame, f"Frame: {frame_count}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    if results.multi_hand_landmarks and results.multi_handedness:
        hand_landmarks = results.multi_hand_landmarks[0]
        hand_info = results.multi_handedness[0]
        
        # Get handedness (Left or Right)
        hand_label = hand_info.classification[0].label
        
        # Detect gesture
        gesture = classify_gesture(hand_landmarks, hand_label)
        last_gesture = gesture
        gesture_history.append(gesture)
        
        # Determine color based on gesture
        if gesture == "draw":
            color = (0, 255, 0)  # Green
            status = "✓ DRAW (Expected)"
        else:
            color = (0, 0, 255)  # Red
            status = f"✗ {gesture.upper()} (Wrong!)"
        
        # Display gesture
        cv2.putText(frame, f"Gesture: {gesture.upper()}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)
        cv2.putText(frame, status, (10, 110), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        
        # Draw hand landmarks
        mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                               mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                               mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2))
        
        # Display test hint
        cv2.putText(frame, "Rotate your hand side-to-side to test", (10, h - 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    else:
        cv2.putText(frame, "No hand detected", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
    # Show frame
    cv2.imshow("Rotation Robustness Test", frame)
    
    # Handle keys
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('d'):
        # Show gesture histogram
        if gesture_history:
            from collections import Counter
            counts = Counter(gesture_history)
            print()
            print(f"Gesture histogram (last {len(gesture_history)} frames):")
            for gesture, count in sorted(counts.items(), key=lambda x: -x[1]):
                pct = (count / len(gesture_history)) * 100
                bar = "█" * int(pct / 2)
                print(f"  {gesture:12} : {bar} {pct:5.1f}% ({count})")
            print()

cap.release()
cv2.destroyAllWindows()

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
if gesture_history:
    from collections import Counter
    counts = Counter(gesture_history)
    draw_pct = (counts.get('draw', 0) / len(gesture_history)) * 100
    print()
    print(f"Summary:")
    print(f"  Total frames: {len(gesture_history)}")
    print(f"  'draw' frames: {counts.get('draw', 0)} ({draw_pct:.1f}%)")
    print()
    if draw_pct > 80:
        print("✓ PASS: FIX-22 appears to be working!")
        print("  Gesture detection remained stable at 'draw' through rotation")
    else:
        print("✗ FAIL: Gesture detection is unstable")
        print(f"  Expected 'draw' to be >80% of frames, got {draw_pct:.1f}%")
    print()
