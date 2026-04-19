# Developer Quick Reference - All Phases Complete

## 🚀 Quick Start

### Import All New Modules
```python
# Shape fitting
from utils.shape_fitting import fit_circle, fit_rectangle, fit_triangle, fit_line

# Temporal smoothing
from utils.temporal_smooth import LandmarkTemporalSmoother, ExponentialLandmarkFilter

# Ensemble detection
from utils.ensemble_detection import EnsembleDetector, ensemble_detect

# Performance monitoring
from utils.performance_monitor import init_monitor, FrameMetrics, FrameTimer

# Threshold tuning
from utils.threshold_tuner import ThresholdProfile, ThresholdConfig
```

---

## 📐 Shape Fitting API

### Fit a Circle
```python
from utils.shape_fitting import fit_circle

result = fit_circle(points)
# {
#   'center': (cx, cy),
#   'radius': r,
#   'error': rms_error,
#   'quality': quality_score (0-1)
# }

if result['quality'] > 0.3:  # Good quality
    cv2.circle(canvas, result['center'], result['radius'], color, thickness)
```

### Fit a Rectangle
```python
from utils.shape_fitting import fit_rectangle

result = fit_rectangle(points)
# {
#   'center': (cx, cy),
#   'width': w,
#   'height': h,
#   'angle': rotation_radians,
#   'corners': [(x1,y1), (x2,y2), (x3,y3), (x4,y4)],
#   'quality': quality_score
# }

# Draw rotated rectangle
corners = result['corners']
pts = np.array(corners, dtype=np.int32)
cv2.polylines(canvas, [pts], True, color, thickness)
```

### Fit Triangle & Line
```python
from utils.shape_fitting import fit_triangle, fit_line

triangle_result = fit_triangle(points)
line_result = fit_line(points)
```

---

## 🎬 Temporal Smoothing API

### Initialize Smoothers
```python
from utils.temporal_smooth import LandmarkTemporalSmoother, ExponentialLandmarkFilter

# Per-hand smoother
temporal_smoothers = {}
landmark_filters = {}

hand_id = 0
temporal_smoothers[hand_id] = LandmarkTemporalSmoother(history_size=2)
landmark_filters[hand_id] = ExponentialLandmarkFilter(alpha=0.15)
```

### Apply Smoothing
```python
# Smooth landmarks (handles frame gaps via interpolation)
smoothed_hand = temporal_smoothers[hand_id].smooth(hand, hand_quality, time.time())

# Filter jitter from landmarks
smoothed_hand.landmarks = landmark_filters[hand_id].filter(smoothed_hand.landmarks)
```

---

## 🤖 Ensemble Detection API

### Single-Line Detection
```python
from utils.ensemble_detection import ensemble_detect

shape, points, confidence = ensemble_detect(raw_stroke_points)
# shape: "circle", "rectangle", "triangle", "line", or None
# points: clean point list or None
# confidence: 0.0-1.0
```

### Detailed Result
```python
from utils.ensemble_detection import EnsembleDetector

result = EnsembleDetector.detect(raw_pts)
if result:
    print(f"Shape: {result.shape}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Method: {result.method}")  # "rule", "mlp", or "ensemble"
    print(f"Details: {result.details}")
```

---

## 📊 Performance Monitoring API

### Initialize Global Monitor
```python
from utils.performance_monitor import init_monitor

monitor = init_monitor(window_size=300)  # Keep last 300 frames
```

### Record Frame Metrics
```python
from utils.performance_monitor import FrameMetrics
import time

metrics = FrameMetrics(
    timestamp=time.time(),
    frame_time=16.7,  # ms
    rule_detect_time=2.5,
    mlp_detect_time=8.3,
    ensemble_time=1.2,
    shape_fitting_time=3.4,
    detection_result="circle",
    confidence=0.92,
    method="ensemble"
)
monitor.record_frame(metrics)
```

### Get Performance Stats
```python
# Summary
print(monitor.get_summary())

# Specific metrics
fps = monitor.get_fps()  # Frames per second
avg_frame = monitor.get_avg_frame_time()  # ms
detection_times = monitor.get_avg_detection_time()  # Dict of times
uptime = monitor.get_uptime_seconds()

# UI overlay
overlay_text = monitor.get_ui_overlay_text()  # "FPS: 60.0 | Frame: 16.7ms"
```

### Time Operations
```python
from utils.performance_monitor import FrameTimer

with FrameTimer() as timer:
    # Do some work
    detect_shape(points)

elapsed_ms = timer.get_ms()
```

---

## ⚙️ Threshold Tuning API

### Use Built-in Profiles
```python
from utils.threshold_tuner import ThresholdProfile

# Production balanced (default)
config = ThresholdProfile.balanced()

# High precision (fewer false positives)
strict_config = ThresholdProfile.strict()

# High recall (catch more shapes, more false positives)
lenient_config = ThresholdProfile.lenient()
```

### Custom Configuration
```python
from utils.threshold_tuner import ThresholdConfig

config = ThresholdConfig(
    CIRCLE_CIRCULARITY_MIN=0.92,  # Stricter circle detection
    RECTANGLE_ASPECT_RATIO_MAX=3.5,  # Allow slightly stretched rectangles
    LINE_STRAIGHTNESS_MIN=0.90
)
```

### Apply Thresholds
```python
from utils.threshold_tuner import apply_thresholds

circle_thresholds = apply_thresholds(config, "circle")
# {
#   'circularity_min': 0.90,
#   'closure_max': 0.15,
#   'aspect_ratio_max': 1.4
# }
```

---

## 🧪 Validation Testing

### Run Validation Suite
```python
from test_ensemble_validation import ValidationTestSuite

suite = ValidationTestSuite(shapes_per_class=25)
suite.generate_test_data()
suite.run_validation()
report = suite.print_report()
print(report)
```

---

## 📈 Example: Complete Pipeline

```python
from utils.ensemble_detection import EnsembleDetector
from utils.shape_fitting import fit_circle
from utils.performance_monitor import init_monitor, FrameMetrics, FrameTimer
import time

# Initialize
monitor = init_monitor()

# Main detection loop
while drawing:
    frame_start = time.time()
    
    # Detect shape
    with FrameTimer() as detection_timer:
        result = EnsembleDetector.detect(stroke_points, use_fallback=True)
    
    if result:
        shape, points, confidence = result.shape, result.points, result.confidence
        
        # Apply advanced fitting
        if shape == "circle":
            fit_result = fit_circle(stroke_points)
            if fit_result['quality'] > 0.3:
                draw_circle(fit_result)
        
        # Record metrics
        metrics = FrameMetrics(
            timestamp=time.time(),
            frame_time=(time.time() - frame_start) * 1000,
            rule_detect_time=0,  # Measured separately if needed
            mlp_detect_time=0,
            ensemble_time=detection_timer.get_ms(),
            shape_fitting_time=0,
            detection_result=shape,
            confidence=confidence,
            method=result.method
        )
        monitor.record_frame(metrics)
        
        # Periodic reporting
        if frame_count % 60 == 0:
            print(f"FPS: {monitor.get_fps():.1f}")
```

---

## 🐛 Debugging

### Check if MLP model is loaded
```python
from utils.shape_mlp_ai import get_classifier

clf = get_classifier()
if clf:
    print("✓ MLP classifier loaded")
else:
    print("✗ MLP classifier failed to load")
```

### Test ensemble detection directly
```python
from utils.ensemble_detection import EnsembleDetector

# Generate test points
test_points = [(100, 100), (110, 95), (115, 105), (105, 115)]

result = EnsembleDetector.detect(test_points)
if result:
    print(f"Detection: {result}")
else:
    print("No detection")
```

### Verify modules import
```python
try:
    from utils.shape_fitting import fit_circle
    from utils.temporal_smooth import LandmarkTemporalSmoother
    from utils.ensemble_detection import EnsembleDetector
    from utils.performance_monitor import PerformanceMonitor
    from utils.threshold_tuner import ThresholdProfile
    print("✓ All modules loaded successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
```

---

## ⚡ Performance Tips

1. **Cache the classifier**
   - `get_classifier()` is already cached
   - Don't create multiple classifier instances

2. **Monitor FPS regularly**
   - Track FPS to catch performance regressions
   - Target: 60 FPS minimum

3. **Use ensemble for best accuracy**
   - Trades ~10ms latency for 10-15% accuracy improvement
   - Worth it for most use cases

4. **Tune thresholds per use case**
   - Strict for clean drawings
   - Lenient for rough sketches
   - Balanced for general use

5. **Profile with FrameTimer**
   - Identify bottlenecks
   - MLP detection (~8-10ms) is most expensive

---

## 📚 Related Files

- **IMPLEMENTATION_COMPLETE.md** - Full implementation summary
- **MASTER_CHANGELOG.md** - Complete change history
- **ml/drawing_mlp.py** - MLP classifier wrapper
- **utils/shape_ai.py** - Rule-based detection (unchanged)
- **modules/drawing_2d.py** - Main drawing module (integrated)

---

**Last Updated:** April 5, 2026  
**Status:** ✅ All Phases Complete  
**Ready for Production:** Yes
