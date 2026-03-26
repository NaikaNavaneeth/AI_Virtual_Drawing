# User Guide: Immediate Gesture-Based Drawing Controls

**Version**: 3.0 (Enhanced UX)  
**Effective**: March 26, 2026  
**Status**: Current

---

## Quick Start - Draw in 2 Gestures

### How to Draw
1. **Show index finger** (draw gesture) → **Drawing starts IMMEDIATELY**
2. **Draw anything on canvas** → Strokes appear in real-time
3. **Stop drawing by switching gesture** (erase, palm, fist, etc.) → **Stops IMMEDIATELY**

That's it! No waiting, no complicated timers, just draw.

---

## Detailed Gesture Controls

### ✏️ DRAW - Index Finger UP

```
Gesture: Open hand with index finger extended upward
         (other 3 fingers relaxed, thumb up or down)

Action:  Drawing mode ACTIVE
         • Strokes captured in real-time
         • Starts immediately when gesture shown
         • Continues while gesture held
         • Stops when you switch gesture

Duration: As long as you want - you control it!
          (no auto-stop after idle time)

Pro Tip:  Pause your hand for 1 second while drawing
          → Shape snaps automatically (circle, square, etc.)
          → No need to stop gesture!
```

---

### 🗑️ ERASE - Index + Middle Finger UP

```
Gesture: Index and middle fingers extended
         (ring, pinky, thumb others)

Action:  Erasing mode ACTIVE
         • Erases strokes under finger position
         • Stops draw mode (if active)
         • Real-time erasing

Duration: As long as needed
```

---

### 🆓 OPEN PALM - All Fingers Spread

```
Gesture: All five fingers extended and spread apart

Action:  Clear canvas
         • Hold position for ~65ms (2-3 frames)
         • Entire canvas clears
         • All strokes erased

Duration: Quick gesture (not continuous)

Pro Tip:  Great for starting fresh drawing
```

---

### ✊ FIST - All Fingers Closed

```
Gesture: Make a fist (all fingers closed)

Action:  Stop drawing (safe mode)
         • Draws no strokes
         • Doesn't clear canvas
         • Safe idle pose

Pro Tip:  Rest your hand without accidents
```

---

### 👍 THUMBS UP

```
Gesture: Thumb pointing up, other fingers closed

Action:  Alternative stop gesture
         • Stops drawing
         • Similar to fist
```

---

### 👌 OK GESTURE / PINCH

```
Gesture: Thumb + Index finger together, others extended

Action:  Stop drawing
         • Stops drawing mode
         • Doesn't clear
```

---

### 🎨 SELECT - Index + Middle + Ring UP

```
Gesture: Three fingers extended (index, middle, ring)
         (thumb and pinky relaxed)

Action:  Select/interact with UI
         • Pick colors from palette
         • Activate buttons
         • Select tools
```

---

## Complete Workflow Example

### Simple Drawing Session

```
START HERE
    ↓
1. Show "draw" gesture
   └─ Drawing starts immediately ✓
    ↓
2. Draw on canvas
   └─ Strokes appear in real-time
    ↓
3. Do whatever you want:
   ├─ Pause (hand still, < 1s) → Drawing pauses
   ├─ Move hand (> 1s still) → Shape may snap
   ├─ Keep drawing (move hand) → Continues
   └─ Switch gesture → Stops immediately
    ↓
4. Want to stop? 
   └─ Switch gesture (erase, palm, fist, etc.)
      → Drawing stops immediately ✓
    ↓
5. Want to keep drawing?
   └─ Switch back to "draw" gesture
      → Drawing resumes immediately ✓
```

---

## Common Scenarios

### Scenario 1: Draw a Circle

```
1. Show "draw" gesture    → Drawing starts
2. Draw circular motion    → Circle appears
3. Stop hand (don't move)  → Wait 1 second
4. Circle auto-snaps       → Perfect circle!
5. Keep hand still         → Drawing auto-stops
   OR switch gesture       → Drawing stops
```

**Total time**: ~2-3 seconds (you control it)

---

### Scenario 2: Draw, Erase, Draw Again

```
1. Show "draw"      → Start drawing
2. Draw something
3. Show "erase"     → Stop drawing, erase mode active
4. Erase part of it
5. Show "draw"      → Back to drawing, continue
6. Draw more
7. Show "palm"      → Stop drawing
```

**Total time**: As long as you need - free control!

---

### Scenario 3: Quick Correction

```
1. Show "draw"           → Start drawing
2. Draw, realize mistake → Stop with different gesture
3. Show "erase"          → Erase the mistake
4. Show "draw"           → Continue drawing
5. Done? Show any gesture → Stop
```

**No waiting, no delays!**

---

## Keyboard Shortcuts (Still Available)

| Key | Action |
|-----|--------|
| **Z** | Undo |
| **S** | Save PNG |
| **L** | Load last save |
| **C** | Clear canvas |
| **A** | Toggle AI shape snap ON/OFF |
| **T** | Train gesture model (collect data) |
| **Q/ESC** | Quit |

---

## Tips & Tricks

### Pro Tip 1: Use Pause-to-Snap
```
Draw shape → Hold hand still for 1 second → Auto-snap!
(No need to stop drawing gesture)
```

### Pro Tip 2: Multi-hand Drawing
```
Can draw with both hands simultaneously!
Each hand independent with its own gesture
```

### Pro Tip 3: Smooth Curves
```
• Draw slowly for better control
• Move hand smoothly
• Pause to auto-snap clean shapes
```

### Pro Tip 4: Quick Canvas Clear
```
Show open palm gesture → Hold for ~65ms → Canvas clears
Much faster than keyboard shortcut!
```

### Pro Tip 5: Save Frequently
```
Press S to save PNG of your drawing
No delay, no complication
Can load it back with L
```

---

## Comparison: Old vs New

### Old System (Timing-Based - ❌ Removed)

```
To draw: 1. Show gesture
         2. Wait 2 seconds ⏳
         3. THEN drawing starts

To stop: 1. Keep gesture
         2. Don't move hand
         3. Wait 2.5 seconds ⏳
         4. Auto-stops (if you forgot)
         
Problems: 
- Slow startup (2 second delay frustrating)
- Confusing stop behavior (didn't know when it would stop)
- Didn't feel real-time
```

### New System (Gesture-Based - ✅ Current)

```
To draw: 1. Show gesture
         2. Drawing starts IMMEDIATELY ⚡
         
To stop: 1. Switch gesture
         2. Stops IMMEDIATELY ⚡
         
Benefits:
- Instant response (like real drawing!)
- You control everything (intuitive)
- Feels real-time (no artificial delays)
- Professional (like actual drawing apps)
```

---

## Troubleshooting

### Issue: Drawing doesn't start
**Solution**:
- Make sure hand is visible to camera
- Try showing gesture more clearly
- Check hand quality (camera distance 30-100cm)
- Verify gesture is "draw" (index finger pointing up)

### Issue: Drawing stops unexpectedly
**Solution**:
- You switched gestures (intentionally?)
- Try showing "draw" gesture again
- Drawing only stops when you change gesture (that's the feature!)

### Issue: Want to pause without stopping
**Solution**:
- Keep "draw" gesture active
- Just pause your hand
- Shape will auto-snap after 1 second
- Drawing resumes when you move again

### Issue: Can't erase cleanly
**Solution**:
- Use "erase" gesture (index + middle finger)
- Keep eraser circle visible on screen
- Move hand over strokes you want to erase

---

## Gesture Quality Tips

### For Better Recognition

1. **Lighting**: Well-lit environment (not backlit)
2. **Distance**: 30-100 cm from camera (arm's length)
3. **Angle**: Face camera (not extreme angles)
4. **Contrast**: Good background contrast helps
5. **Speed**: Slow, deliberate hand movements
6. **Clarity**: Show complete gesture (all fingers visible)

### Example: Good Draw Gesture
```
✓ Index finger pointing UP
✓ Other fingers relaxed (not pinched)
✓ Thumb visible and relaxed
✓ Hand ~60cm from camera
✓ Good lighting
✓ Clear background
```

### Example: Bad Draw Gesture
```
✗ Index finger pointing down
✗ Other fingers pinched together
✗ Thumb hidden
✗ Too close/far from camera
✗ Backlit (shadow on face)
✗ Hand partially off-screen
```

---

## Advanced: Gesture Lock (Future Feature)

Currently under consideration:
- Option to "lock" gesture so it's sticky
- Won't accidentally switch on brief misdetection
- Would preserve current immediate response

For now: Drawing responds immediately to gesture changes (as designed)

---

## Questions & Answers

**Q: Why does drawing stop when I change gesture?**  
A: That's by design! User controls it via gestures. Want to stop? Change gesture. Want to continue? Keep the same gesture or switch back.

**Q: Can I use Procreate-style pressure sensing?**  
A: Not currently (requires depth camera), but hand distance to camera could theoretically be used in future versions.

**Q: What if light changes?**  
A: Gesture detection might become less reliable. Keep good lighting. The CNN model is trained on various conditions, but good lighting helps most.

**Q: Can I change the controls?**  
A: Currently no, but the gesture mapping is in `core/config.py`. Developers can modify `GESTURE_LABELS` and add custom gestures.

**Q: Drawing feels laggy sometimes?**  
A: Check FPS (shown in top-left). Should be 28-30 FPS. If lower:
- Reduce screen resolution
- Improve lighting (faster detection)
- Close other apps
- Update camera drivers

---

## Getting Help

1. **Check FPS**: Top-left of screen - should be 28-30
2. **Verify Gestures**: Look at hand landmarks overlay
3. **Test Lighting**: Try different room/angles
4. **Check Camera**: Run `python verify_env.py`
5. **Retrain Model**: Press T to collect real-world data

---

## Summary

✨ **Drawing Controls: Immediate & Intuitive**

- **Draw Gesture** = Drawing starts immediately
- **Change Gesture** = Drawing stops immediately  
- **Pause (1s no movement)** = Shape auto-snaps
- **Real-time feedback** = See it as you draw

**Result**: Professional-grade drawing experience! 🎨

---

**Version**: 3.0 (Gesture-Based, Immediate)  
**Date**: March 26, 2026  
**Status**: Current  

For technical details, see: DRAWING_2D_UPDATES_MARCH26.md

