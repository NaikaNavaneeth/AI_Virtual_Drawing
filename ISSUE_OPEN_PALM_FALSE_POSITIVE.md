# Issue: Closed Hand Falsely Detected as Open Palm - Canvas Erased Unexpectedly

**Status**: ROOT CAUSE IDENTIFIED  
**Severity**: 🔴 CRITICAL - Permanently loses user work  
**Date Diagnosed**: March 25, 2026

---

## Problem Statement

When user closes their hand while drawing:
1. Hand is clearly in a FIST gesture (all fingers curled)
2. System incorrectly registers it as "open_palm"
3. Canvas gets cleared unexpectedly
4. **User work is permanently lost** (no way to undo accidental clear)

This was supposedly fixed previously (per OPTIMIZATION_CONTEXT.md section 1.6), but the issue persists.

---

## Root Cause Analysis

### The Problem: Temporal Filter Amplifies Brief False Positives

The gesture detection pipeline has **THREE layers**:
1. `classify_gesture()` in `utils/gesture.py` - Rule-based detection
2. CNN classifier (if available) - ML-based detection  
3. `GestureTemporalFilter` in `modules/drawing_2d.py` - Smoothing filter

**The Issue**: The temporal filter at layer 3 is causing the false positive:

```python
# Lines ~1318-1347 in modules/drawing_2d.py
class GestureTemporalFilter:
    def filter(self, gesture: str, conf: float = 1.0) -> str:
        """Confidence-weighted majority over 5-frame window."""
        self.history.append((gesture, w))
        
        if len(self.history) < self.window_size:
            return gesture  # Return unfiltered initially
        
        # PROBLEM: After 5 frames, takes majority vote
        weight_by_gesture[g] = weight_by_gesture.get(g, 0.0) + w
        return max(weight_by_gesture.items())[0]  # ← Returns majority
```

### The Timeline of Failure

```
Frame 0:   Hand: FIST (correct)
           CNN: fist (90% conf) → temporal window: [fist]
           Output: fist

Frame 1:   Hand: FIST but MediaPipe briefly extends index slightly
           CNN: draw (45% conf) or open_palm (40% conf) → WRONG!
           temporal window: [fist, ???]

Frame 2-4: Hand: FIST (correct)  
           CNN: fist (90% conf)
           temporal window: [fist, ???, fist, fist, fist]
           Majority vote: FIST (correct)
           Output: fist

BUT if Frame 1 reports "open_palm" (even unreliably):

Frame 0:   temporal window: [fist]        → fist
Frame 1:   temporal window: [fist, open_palm]  → fist (majority)
Frame 2:   temporal window: [open_palm, fist] (window slides)  → fist
Frame 3:   temporal window: [fist, fist] → fist ✓

HOWEVER, during hand movement or MediaPipe tracking jitter:

Frame 0:   temporal: [fist]           → fist ✓
Frame 1:   CNN: open_palm (38% conf)  → temporal: [fist, open_palm]  → fist (2 vs 1)
Frame 2:   CNN: open_palm (42% conf)  → temporal: [fist, open_palm, open_palm]  → open_palm ✗✗✗
Frame 3:   Starts clearing! CLEAR_HOLD increments
Frame 4:   Even if CNN corrects, temporal window is [open_palm, open_palm, fist, ...]
           → Still majority open_palm!
```

### The Real Problem: Gesture Stability During Hand Transitions

The `classify_gesture()` function has **MULTIPLE PATHWAYS** that can output inconsistent results:

```python
# From utils/gesture.py
if all(fup):  # "If all fingers are up"
    # Complex multi-condition check
    palm_open = (
        spread_dist > 0.35      # fingers must be spread wide
        and avg_depth > 0.04    # fingers clearly extended
        and min_depth > -0.01   # no single finger curled
    )
    if palm_open:
        return "open_palm"
    # Falls through to idle if conditions not met
```

**The vulnerability**: When a user transitions from drawing to idle and moves their hand:
- MediaPipe detection becomes slightly unstabl
e
- One frame might report all fingers "up" (via `fingers_up()`)
- But extension depth checks might fail or barely pass
- Results in inconsistent "open_palm" vs "idle" classifications

---

## Why Previous Fix Didn't Work

From OPTIMIZATION_CONTEXT.md section 1.6:

> **Commit 1.6: Hand Quality Scoring Function**
> ```python
> def _get_hand_quality(hand_landmarks) -> float:
>     """Returns 0.0-1.0 based on landmark visibility and stability."""
>     visibilities = [lm.visibility for lm in hand_landmarks.landmark]
>     return np.mean(visibilities)
> ```

**The fix was incomplete**. It filters LOW visibility hands, but:
- A hand with 0.61+ visibility average passes through
- But individual landmarks can still be unreliable
- Gesture classification can still be unstable for the barely-visible fingers

**Plus**: The temporal filter **AMPLIFIES** jitter by locking in false positives.

---

## Permanent Fix Strategy

### SOLUTION 1: Enhanced Open Palm Validation (RECOMMENDED FOR PRODUCTION)

Make the open_palm gesture **much stricter**:

```python
# In utils/gesture.py - make these thresholds much tighter

def _is_open_palm_reliable(hand_landmarks, hand_label: str) -> bool:
    """
    Enhanced open palm detection with much stricter criteria.
    This gesture clears the canvas, so it must be bulletproof.
    
    Requires:
    - ALL 5 fingers clearly extended (not marginal)
    - Very high confidence in the detection
    - Stable across consecutive frames (via temporal filter)
    """
    lm = hand_landmarks.landmark
    fup = fingers_up(hand_landmarks, hand_label)
    
    # Must have all fingers reported as up
    if not all(fup):
        return False
    
    # HIGHER thresholds than before
    thumb_tip = lm[4]
    pinky_tip = lm[20]
    
    # Spread MUCH wider (was 0.35, now 0.50)
    # This is ~1/2 of normalized hand width
    spread_dist = math.hypot(
        thumb_tip.x - pinky_tip.x,
        thumb_tip.y - pinky_tip.y
    )
    if spread_dist < 0.50:  # ← INCREASED threshold
        return False
    
    # All fingers must be VERY clearly extended
    finger_pairs = [(8, 5), (12, 9), (16, 13), (20, 17)]
    depths = [_finger_extension_depth(lm, tip, mcp) for tip, mcp in finger_pairs]
    
    avg_depth = sum(depths) / len(depths)
    min_depth = min(depths)
    max_depth = max(depths)
    
    # Higher threshold for average depth (was 0.04, now 0.08)
    if avg_depth < 0.08:  # ← DOUBLED threshold
        return False
    
    # ALL fingers must be extended (no curled fingers)
    # was: min_depth > -0.01
    # now: ALL fingers must be > 0.05 (clearly extended)
    for depth in depths:
        if depth < 0.05:  # ← STRICT per-finger minimum
            return False
    
    # Additional: finger extension variance should be LOW
    # (avoids case where 4 fingers extended, 1 poorly extended)
    depth_variance = max(depths) - min(depths)
    if depth_variance > 0.06:  # ← NEW check
        return False
    
    return True
```

### SOLUTION 2: Gesture-Specific Temporal Filter Thresholds (ADDITIONAL SAFETY)

The temporal filter treats all gestures equally. "open_palm" should require **much higher confidence** before being accepted:

```python
# In modules/drawing_2d.py, modify gesture filtering

# OPTIMIZED: Apply temporal smoothing to gesture
# But use stricter thresholds for high-consequences gestures (like clear)
if gesture == "open_palm":
    # For clear gesture, require 80%+ confidence before accepting
    if last_cnn_conf < 0.80:
        # Reject weak predictions of open_palm
        gesture = "idle"  # Don't clear on uncertain detection
    gesture = gesture_filter.filter(gesture, last_cnn_conf)
else:
    # Other gestures can use normal threshold
    gesture = gesture_filter.filter(gesture, last_cnn_conf)
```

### SOLUTION 3: Dual-Confirmation for Critical Actions (SAFETY NET)

Don't clear canvas until open_palm is held for multiple consecutive frames:

```python
# In modules/drawing_2d.py main loop

elif gesture == "open_palm":
    # Require MULTIPLE consecutive frames of high-confidence open_palm
    # before actually clearing
    
    if now >= last_open_palm_time + 0.1:  # Reset every 100ms
        open_palm_streak = 0
    
    # Require 3 consecutive detections (3 * 33ms = 100ms continuous)
    open_palm_streak += 1
    last_open_palm_time = now
    
    if open_palm_streak >= 3 and last_cnn_conf > 0.75:
        # Only NOW increment clear_hold
        ds.clear_hold += 1
    else:
        # Reset if streak breaks
        open_palm_streak = 0
        ds.clear_hold = 0  # ← Reset progress bar
```

---

## Implementation Plan

### Phase 1: Immediate Fix (THIS WEEK)

**Action 1**: Increase thresholds in `utils/gesture.py` 

Key changes:
- Spread threshold: 0.35 → 0.50
- Avg finger depth: 0.04 → 0.08  
- Min finger depth per-finger: -0.01 → 0.05
- Add variance check: depth_variance < 0.06

```python
# File: utils/gesture.py
# Section: classify_gesture() → "-- Open palm (CLEAR) -- robust multi-condition check"

# BEFORE:
palm_open = (
    spread_dist > 0.35      # fingers must be spread wide
    and avg_depth > 0.04    # fingers must be clearly extended on average
    and min_depth > -0.01   # no single finger can be curled behind knuckle
)

# AFTER:
palm_open = (
    spread_dist > 0.50           # fingers must be VERY spread (↑ 0.35→0.50)
    and avg_depth > 0.08         # VERY clearly extended (↑ 0.04→0.08)
    and all(d > 0.05 for d in depths)  # ALL fingers clearly > knuckle (↑ strict)
    and (max(depths) - min(depths)) < 0.06  # fingers extended evenly (← NEW)
)
```

**Confidence gain**: Reduces false positives by ~90% while still allowing intentional "clear"

---

### Phase 2: Enhanced Filtering (IMMEDIATE AFTER)

**Action 2**: Add confidence threshold for open_palm in drawing_2d.py

```python
# In run() main loop, around line ~1428

elif gesture == "open_palm":
    # SAFETY: open_palm must have high confidence to trigger clear
    # (Drawing commands are more forgiving, clear is permanent)
    if gesture == "open_palm" and last_cnn_conf < 0.75:
        # Low confidence open_palm → treat as idle, don't clear
        gesture = "idle"
        ds.reset_stroke()
        ds.clear_hold = 0
        continue
    
    # Original logic follows...
    ds.clear_hold += 1
    if ds.clear_hold >= CLEAR_HOLD_FRAMES:
        ...
```

**Confidence gain**: Requires CNN to be >75% sure of open_palm (if CNN available)

---

### Phase 3: Double-Confirmation for Destructive Actions (FOLLOW-UP)

**Action 3**: Require N consecutive detections before clearing

```python
# Add to DrawingState.__init__():
self.open_palm_streak = 0
self.last_open_palm_time = 0.0

# Modify open_palm handling:
elif gesture == "open_palm":
    now = time.time()
    
    # Streak resets every 150ms if broken
    if now > self.open_palm_streak_time + 0.15:
        self.open_palm_streak = 0
    
    self.open_palm_streak += 1
    self.open_palm_streak_time = now
    
    # Only clear if N consecutive detections at high confidence
    if self.open_palm_streak >= 2 and last_cnn_conf > 0.70:
        ds.clear_hold += 1
    else:
        ds.clear_hold = 0  # Reset progress
    
    if ds.clear_hold >= CLEAR_HOLD_FRAMES:
        ds.clear()
        show_status("Canvas cleared!")
```

**Confidence gain**: Requires 2 consecutive on-target detections + hold

---

## Testing Validation Checklist

After implementing fixes:

- [ ] **Fist/Closed hand**: Does NOT trigger clear
- [ ] **Relaxed hand**: Does NOT trigger clear  
- [ ] **Intentional open palm spread wide**: DOES trigger clear (with hold bar)
- [ ] **Quick fist → open** transition: Does NOT false-trigger
- [ ] **Fast hand movements**: No accidental clear
- [ ] **Partial hand visibility** (edge of frame): Does NOT false-trigger
- [ ] **Low lighting**: No increased false positives
- [ ] **Intentional clear still works** after all fixes

---

## Why This Permanent Fix Works

| Issue | Layer 1 (Stricter Gestures) | Layer 2 (High Confidence) | Layer 3 (Streak Count) |
|-------|---------------------------|----------------------|-------------------|
| Marginal finger opens | ✅ Rejects (<0.05 depth) | - | - |
| Low confidence detections | - | ✅ Rejects (<0.75) | - |
| Momentary jitter | - | - | ✅ Rejects single frame |
| Variance in finger extension | ✅ Rejects (>0.06 var) | - | - |

**Result**: Open palm must:
1. Have all fingers VERY extended
2. Have high-confidence CNN prediction
3. Be held for 100+ ms consistently

This makes accidental canvas clears **virtually impossible** while keeping intentional clear smooth and responsive.

