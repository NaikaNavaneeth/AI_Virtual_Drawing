"""
main.py  —  AI Powered Virtual Drawing & 3D Modeling Platform

Usage
-----
    python main.py            # interactive GUI launcher
    python main.py 2d         # jump to 2D drawing
    python main.py 3d         # jump to 3D viewer
    python main.py train      # train CNN gesture model
"""

from __future__ import annotations
import sys
import os
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# Also add utils/ parent explicitly for Windows
import importlib, pathlib
for _sub in ('utils', 'modules', 'core', 'ml'):
    _p = str(pathlib.Path(_ROOT))
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Dependency pre-flight ────────────────────────────────────────────────────
def _check_deps() -> bool:
    errors = []

    try:
        import numpy as np
        major = int(np.__version__.split(".")[0])
        if major >= 2:
            errors.append(
                f"NumPy {np.__version__} is too new. mediapipe requires NumPy < 2.0.\n"
                "  Fix: pip install \"numpy>=1.24.0,<2.0\" --upgrade --force-reinstall"
            )
    except ImportError:
        errors.append("NumPy not installed.")

    try:
        import cv2
    except ImportError:
        errors.append("OpenCV not installed. Fix: pip install opencv-python>=4.8.0,<5.0")

    try:
        import mediapipe
    except ImportError:
        errors.append("mediapipe not installed. Fix: pip install \"mediapipe>=0.10.13,<0.11\"")
    except Exception as e:
        errors.append("mediapipe import error: " + str(e))

    if errors:
        print("\n" + "=" * 60)
        print("  DEPENDENCY ERROR")
        print("=" * 60)
        for err in errors:
            print("  •", err)
        print("=" * 60 + "\n")
        return False
    return True


# ── Launcher ─────────────────────────────────────────────────────────────────
def _show_launcher() -> str:
    import cv2
    import numpy as np
    from core.config import SCREEN_W, SCREEN_H

    W = min(SCREEN_W, 960)
    H = min(SCREEN_H, 580)
    win = "AI Virtual Drawing Platform"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, W, H)
    choice = None

    btn_2d    = (W // 2 - 260, 180, W // 2 - 40,  280)
    btn_3d    = (W // 2 + 40,  180, W // 2 + 260, 280)
    btn_train = (W // 2 - 110, 310, W // 2 + 110, 380)
    btn_ex    = (W // 2 - 70,  410, W // 2 + 70,  460)

    def _on_mouse(event, x, y, flags, param):
        nonlocal choice
        if event == cv2.EVENT_LBUTTONDOWN:
            def _hit(b): return b[0] < x < b[2] and b[1] < y < b[3]
            if _hit(btn_2d):    choice = "2d"
            elif _hit(btn_3d):  choice = "3d"
            elif _hit(btn_train): choice = "train"
            elif _hit(btn_ex):  choice = "exit"

    cv2.setMouseCallback(win, _on_mouse)

    while choice is None:
        bg = np.zeros((H, W, 3), dtype=np.uint8)
        for row in range(H):
            t = row / H
            bg[row, :] = (int(30 + t * 40), int(10 + t * 15), int(10 + t * 5))

        cv2.putText(bg, "AI POWERED VIRTUAL DRAWING",
                    (W // 2 - 295, 75), cv2.FONT_HERSHEY_DUPLEX, 0.95, (0, 200, 255), 2, cv2.LINE_AA)
        cv2.putText(bg, "& 3D MODELING PLATFORM",
                    (W // 2 - 210, 118), cv2.FONT_HERSHEY_DUPLEX, 0.85, (80, 180, 255), 2, cv2.LINE_AA)
        cv2.line(bg, (50, 142), (W - 50, 142), (50, 80, 120), 1)

        def _btn(rect, label, sub, col):
            x1, y1, x2, y2 = rect
            cv2.rectangle(bg, (x1, y1), (x2, y2), col, -1)
            cv2.rectangle(bg, (x1, y1), (x2, y2), (200, 200, 200), 2)
            tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.8, 2)[0][0]
            cv2.putText(bg, label, (x1 + (x2 - x1 - tw) // 2, y1 + 48),
                        cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
            sw = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0][0]
            cv2.putText(bg, sub, (x1 + (x2 - x1 - sw) // 2, y1 + 72),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 230, 230), 1, cv2.LINE_AA)

        _btn(btn_2d,    "2D DRAWING",    "Gesture drawing board",    (20,  80, 160))
        _btn(btn_3d,    "3D VIEWER",     "Gesture 3D interaction",   (140, 50, 20))
        _btn(btn_train, "TRAIN CNN",     "Improve gesture model",    (40,  120, 40))
        _btn(btn_ex,    "EXIT",          "Close platform",           (60,  20, 20))

        # CNN status indicator
        cnn_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml", "gesture_cnn.pkl")
        cnn_status = "CNN model: READY" if os.path.exists(cnn_path) else "CNN model: not trained (run Train CNN)"
        cnn_color  = (0, 200, 100) if os.path.exists(cnn_path) else (0, 120, 200)
        cv2.putText(bg, cnn_status, (W // 2 - 160, H - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, cnn_color, 1, cv2.LINE_AA)

        legend = ["[1] 2D Drawing", "[2] 3D Viewer", "[3] Train CNN", "[Q/ESC] Exit"]
        for i, line in enumerate(legend):
            cv2.putText(bg, line, (50, 460 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 180, 200), 1, cv2.LINE_AA)

        cv2.imshow(win, bg)
        key = cv2.waitKey(30) & 0xFF
        if key == ord('1'): choice = "2d"
        elif key == ord('2'): choice = "3d"
        elif key == ord('3'): choice = "train"
        elif key in (ord('q'), ord('Q'), 27): choice = "exit"

    cv2.destroyWindow(win)
    return choice


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    if not _check_deps():
        sys.exit(1)

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        mode_map = {
            "2d": "2d", "draw": "2d", "drawing": "2d",
            "3d": "3d", "viewer": "3d", "3dview": "3d",
            "train": "train",
        }
        if arg not in mode_map:
            print(f"Unknown argument '{arg}'. Valid: 2d | 3d | train")
            sys.exit(1)
        mode = mode_map[arg]
    else:
        mode = _show_launcher()

    if mode == "exit":
        print("Goodbye.")
        sys.exit(0)

    if mode == "2d":
        print("Starting 2D Virtual Drawing Board ...")
        try:
            from modules.drawing_2d import run as run_2d
            run_2d(use_voice=False)
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)

    elif mode == "3d":
        print("Starting 3D Object Viewer ...")
        try:
            from modules.viewer_3d import run as run_3d
            run_3d()
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)

    elif mode == "train":
        print("Starting CNN Trainer ...")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, os.path.join("train", "train_gesture_cnn.py")],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
        except Exception as e:
            print(f"\nERROR: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
