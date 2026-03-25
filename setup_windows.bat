@echo off
echo ============================================================
echo  AI Virtual Drawing Platform -- Setup (Windows)
echo ============================================================

REM Step 1: Fix NumPy version (mediapipe requires < 2.0)
python -m pip install "numpy>=1.24.0,<2.0" --upgrade --force-reinstall

REM Step 2: Remove conflicting OpenCV builds
python -m pip uninstall opencv-contrib-python opencv-contrib-python-headless -y

REM Step 3: Install core dependencies
python -m pip install "opencv-python>=4.8.0,<5.0"
python -m pip install "mediapipe>=0.10.13,<0.11"
python -m pip install scipy Pillow trimesh PyOpenGL PyOpenGL_accelerate

REM Step 4: Install CNN backend (try torch first, fall back to sklearn)
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install scikit-learn

REM Step 5: Train the CNN bootstrap model
echo.
echo Training gesture CNN model...
python train_gesture_cnn.py

echo.
echo ============================================================
echo  Setup complete!  Run:  python main.py
echo ============================================================
pause
