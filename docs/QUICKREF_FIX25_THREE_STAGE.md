# FIX-25 Quick Reference

## TL;DR

Three-stage learning system for shape recognition:

```
Stage 1: Synthetic data (automatic baseline)
Stage 2: External datasets (MNIST support)
Stage 3: User feedback RL (continuous improvement)
```

---

## Quick Start

### 1. Train (First Time Only)
```bash
python train_rl_classifier.py
# Generates: synthetic data, fine-tunes, activates RL
# Time: ~10-15 seconds
```

### 2. Use App
```bash
python main.py
# Now recognizes any shape with learned adjustments
# Give feedback: SPACE (confirm) or E (correct)
```

### 3. Monitor Learning
Inside drawing app:
- Press `L` to see learning statistics
- Accuracy improves with each feedback
- Models saved automatically

---

## What Gets Created

```
assets/
├── datasets/synthetic_train.pkl .... Stage 1 training
├── datasets/synthetic_val.pkl ...... Stage 1 validation
├── checkpoints/checkpoint_stage1.pkl
├── checkpoints/checkpoint_stage2.pkl
├── rl_adjustments.json ............ Your RL weights
└── feedback/all_feedback.jsonl .... Your feedback history
```

---

## CLI Options

```bash
# All stages (recommended)
python train_rl_classifier.py

# Only synthetic training
python train_rl_classifier.py --stage 1

# With MNIST dataset
python train_rl_classifier.py --external-dataset mnist

# Verbose output
python train_rl_classifier.py --verbose

# Custom dataset
python train_rl_classifier.py --external-dataset custom --dataset-path data.pkl
```

---

## Expected Performance

| Stage | Description | Accuracy |
|-------|-------------|----------|
| 1 | Synthetic baseline | ~82% |
| 2 | + External fine-tuning | ~86% |
| 3 | + User RL (20 samples) | ~88% |
| 3 | + User RL (100 samples) | ~94% |

---

## Feedback During Drawing

Press these keys after drawing:

- **SPACE** → Prediction correct ✓ (confidence +5%)
- **E** → Prediction wrong, fix it (edit, -10%)
- **?** → Show help
- **ESC** → Skip this shape

---

## Key Files

| File | Purpose |
|------|---------|
| `train_rl_classifier.py` | **Run this first** to train |
| `utils/training_dataset.py` | Synthetic + external data |
| `utils/model_training.py` | Training orchestrator |
| `utils/universal_classifier.py` | Stage 3 (RL) classifier |
| `modules/drawing_2d.py` | Uses trained models |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Low accuracy | Run training: `python train_rl_classifier.py` |
| RL not improving | Give more feedback (need 20+ samples) |
| Reset learning | Delete `assets/rl_adjustments.json` |
| External datasets fail | Install scikit-learn: `pip install scikit-learn` |

---

## Architecture

```
┌──────────────────┐
│ Synthetic Data   │  Stage 1
│ (50 per shape)   │  ────────
└────────┬─────────┘      ↓
         │
    ┌────v─────────────────────┐
    │ Feature Extraction &      │
    │ Threshold Calculation     │  Stage 2
    │ + External Dataset        │  ────────
    │ (MNIST optional)          │      ↓
    └────┬──────────────────────┘
         │
    ┌────v──────────────────────┐
    │ User Feedback RL          │
    │ Confidence Adjustments    │  Stage 3
    │ (continuous)              │  ────────
    │ +5% correct, -10% wrong   │  (active)
    └────┬──────────────────────┘
         │
         v
    ┌─────────────────────┐
    │ Final Prediction    │
    │ (for each draw)     │
    └─────────────────────┘
```

---

## Expected Files After Training

✓ `assets/datasets/synthetic_train.pkl` - 160+ synthetic examples  
✓ `assets/datasets/synthetic_val.pkl` - 32 validation examples  
✓ `assets/datasets/metadata.json` - Dataset info  
✓ `assets/checkpoints/checkpoint_stage1.pkl` - After Stage 1  
✓ `assets/checkpoints/checkpoint_stage2.pkl` - After Stage 2  
✓ `assets/rl_adjustments.json` - Your RL weights (auto-updated)  
✓ `assets/feedback/all_feedback.jsonl` - Feedback history  

---

## Next Steps

1. ✓ Code implemented - all three stages
2. → Run training pipeline
3. → Draw shapes in app
4. → Give feedback
5. → Watch accuracy improve!

---

## Contact

For issues or customization, refer to:
- `FIX25_THREE_STAGE_LEARNING.md` - Full documentation
- `QUICKREF_FIX24_RL.md` - RL system reference
- `utils/model_training.py` - Code comments
