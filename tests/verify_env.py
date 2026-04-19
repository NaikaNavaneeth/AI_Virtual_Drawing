"""
verify_env.py  —  Check all dependencies and print status report.

Run this before launching the platform:
    python verify_env.py
"""

import sys

print("=" * 55)
print("  AI Virtual Drawing — Environment Check")
print("=" * 55)
print(f"  Python : {sys.version.split()[0]}")

checks = []

def _check(name, fn):
    try:
        result = fn()
        checks.append((True, name, result))
        print(f"  ✓  {name:20s} {result}")
    except Exception as e:
        checks.append((False, name, str(e)))
        print(f"  ✗  {name:20s} {e}")

_check("numpy",        lambda: __import__("numpy").__version__)
_check("opencv",       lambda: __import__("cv2").__version__)
_check("mediapipe",    lambda: __import__("mediapipe").__version__)
_check("Pillow",       lambda: __import__("PIL").__version__)
_check("scipy",        lambda: __import__("scipy").__version__)
_check("trimesh",      lambda: __import__("trimesh").__version__)
_check("PyOpenGL",     lambda: __import__("OpenGL").__version__)
_check("torch",        lambda: __import__("torch").__version__ + " (CNN backend)")
_check("scikit-learn", lambda: __import__("sklearn").__version__ + " (CNN fallback)")
_check("websockets",   lambda: __import__("websockets").__version__ + " (collab, optional)")
_check("speech_recognition", lambda: __import__("speech_recognition").__version__ + " (voice, optional)")

# NumPy version guard
try:
    import numpy as np
    major = int(np.__version__.split(".")[0])
    if major >= 2:
        print(f"\n  ⚠  NumPy {np.__version__} is too new for mediapipe!")
        print("  Fix: pip install \"numpy>=1.24.0,<2.0\" --force-reinstall")
except ImportError:
    pass

# CNN model file
import os
cnn_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml", "gesture_cnn.pkl")
if os.path.exists(cnn_path):
    size = os.path.getsize(cnn_path) // 1024
    print(f"\n  ✓  CNN model found ({size} KB) — ready for inference")
else:
    print(f"\n  ✗  CNN model not found. Run: python train_gesture_cnn.py")

passed  = sum(1 for ok, _, _ in checks if ok)
total   = len(checks)
print(f"\n  {passed}/{total} checks passed")
print("=" * 55)

if passed < 5:
    print("\n  Run setup_windows.bat (Windows) or:")
    print("  pip install -r requirements.txt")
    print("  python train_gesture_cnn.py")
