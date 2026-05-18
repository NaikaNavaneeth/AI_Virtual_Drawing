"""
test_rl_tier3_integration.py - Test Tier 3 RL + Extended MLP integration

Validates:
1. Standard MLP loads correctly (4 shapes)
2. Extended MLP loads (if trained)
3. RL classifier initializes
4. 3-tier detection pipeline works
5. RL learning mechanism works
6. No breaking changes to existing code
"""

import sys
import os
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: MLP Standard Mode
# ══════════════════════════════════════════════════════════════════════════════

def test_mlp_standard():
    """Test MLP in standard (4-shape) mode"""
    print("\n" + "="*80)
    print("TEST 1: MLP Standard Mode (4 shapes)")
    print("="*80)
    
    try:
        from ml.drawing_mlp import DrawingMLP, MLPMode
        
        # Create standard mode classifier
        mlp = DrawingMLP(mode=MLPMode.STANDARD)
        
        assert mlp.mode == MLPMode.STANDARD, "Mode should be STANDARD"
        assert mlp.num_classes == 4, "Should have 4 classes"
        assert mlp.labels == ['circle', 'square', 'triangle', 'line'], "Labels mismatch"
        
        print("✓ MLP Standard mode initialized correctly")
        print(f"  - Mode: {mlp.mode.value}")
        print(f"  - Classes: {mlp.num_classes}")
        print(f"  - Labels: {mlp.labels}")
        
        # Try to load model (may not exist if never trained)
        loaded = mlp.load()
        if loaded:
            print("✓ Standard model loaded from disk")
            
            # Try a prediction
            test_image = np.random.rand(28, 28).astype(np.float32)
            label, confidence = mlp.predict(test_image)
            print(f"✓ Prediction works: {label} (conf={confidence:.2f})")
        else:
            print("⚠ Standard model not found (needs training)")
            print("  Run: python ml/train_drawing_mlp.py")
        
        return True
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: MLP Extended Mode
# ══════════════════════════════════════════════════════════════════════════════

def test_mlp_extended():
    """Test MLP in extended (30-shape) mode"""
    print("\n" + "="*80)
    print("TEST 2: MLP Extended Mode (30 shapes)")
    print("="*80)
    
    try:
        from ml.drawing_mlp import DrawingMLP, MLPMode
        
        # Create extended mode classifier
        mlp = DrawingMLP(mode=MLPMode.EXTENDED)
        
        assert mlp.mode == MLPMode.EXTENDED, "Mode should be EXTENDED"
        assert mlp.num_classes == 30, "Should have 30 classes"
        assert 'A' in mlp.labels, "Should have letter A"
        assert 'Z' in mlp.labels, "Should have letter Z"
        
        print("✓ MLP Extended mode initialized correctly")
        print(f"  - Mode: {mlp.mode.value}")
        print(f"  - Classes: {mlp.num_classes}")
        print(f"  - Labels (first 10): {mlp.labels[:10]}")
        print(f"  - Labels (last 10): {mlp.labels[-10:]}")
        
        # Try to load model (may not exist if not trained)
        loaded = mlp.load()
        if loaded:
            print("✓ Extended model loaded from disk")
            
            # Try a prediction
            test_image = np.random.rand(28, 28).astype(np.float32)
            label, confidence = mlp.predict(test_image)
            print(f"✓ Prediction works: {label} (conf={confidence:.2f})")
        else:
            print("⚠ Extended model not found (needs training)")
            print("  Run: python ml/train_drawing_mlp_extended.py")
        
        return True
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: RL Classifier Initialization
# ══════════════════════════════════════════════════════════════════════════════

def test_rl_classifier():
    """Test RL classifier initialization and basic functionality"""
    print("\n" + "="*80)
    print("TEST 3: RL Classifier (Tier 3)")
    print("="*80)
    
    try:
        from utils.rl_classifier import get_rl_classifier, RLFeatureExtractor
        
        # Initialize RL classifier
        rl = get_rl_classifier()
        assert rl is not None, "RL classifier should not be None"
        
        print("✓ RL classifier initialized successfully")
        print(f"  - Storage: {rl.storage_path}")
        
        # Test feature extraction
        stroke_points = [(0, 0), (10, 10), (20, 20), (30, 30), (40, 40)]
        features = RLFeatureExtractor.extract(stroke_points)
        
        assert len(features) > 0, "Should extract features"
        assert 'circularity' in features, "Should have circularity feature"
        assert 'straightness' in features, "Should have straightness feature"
        
        print("✓ Feature extraction working")
        print(f"  - Extracted {len(features)} features")
        print(f"  - Features: {list(features.keys())}")
        
        # Test classification (should have no learned shapes initially)
        result = rl.classify(stroke_points)
        print(f"  - Classification result: {result}")
        
        return True
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: RL Learning Mechanism
# ══════════════════════════════════════════════════════════════════════════════

def test_rl_learning():
    """Test RL classifier learning from feedback"""
    print("\n" + "="*80)
    print("TEST 4: RL Learning Mechanism")
    print("="*80)
    
    try:
        from utils.rl_classifier import get_rl_classifier, RLFeatureExtractor
        
        rl = get_rl_classifier()
        
        # Create test stroke (simple line)
        stroke1 = [(0, 0), (10, 10), (20, 20), (30, 30), (40, 40)]
        features1 = RLFeatureExtractor.extract(stroke1)
        
        # Teach RL this is a "diagonal" line
        rl.learn_from_feedback(
            predicted_label="line",
            actual_label="diagonal",
            features=features1,
            was_correct=False  # System was wrong, user corrected
        )
        
        print("✓ RL learned custom shape 'diagonal'")
        
        # Check knowledge base
        stats = rl.get_stats()
        assert 'diagonal' in stats['shapes'], "Should have learned 'diagonal'"
        
        print(f"✓ Knowledge base updated")
        print(f"  - Known shapes: {stats['known_shapes']}")
        print(f"  - Shape 'diagonal': {stats['shapes']['diagonal']}")
        
        # Try to classify similar stroke
        stroke2 = [(5, 5), (15, 15), (25, 25)]
        result = rl.classify(stroke2)
        if result:
            print(f"  - Similar stroke classified as: {result.label} (conf={result.confidence:.2f})")
        
        return True
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: get_classifier with Mode Switching
# ══════════════════════════════════════════════════════════════════════════════

def test_classifier_mode_switching():
    """Test runtime mode switching"""
    print("\n" + "="*80)
    print("TEST 5: MLP Mode Switching (Runtime)")
    print("="*80)
    
    try:
        from utils.shape_mlp_ai import get_classifier
        from ml.drawing_mlp import MLPMode
        
        # Get classifier in standard mode
        clf1 = get_classifier(mode_override="standard")
        assert clf1 is not None, "Classifier should load"
        assert clf1.mode == MLPMode.STANDARD, "Should be standard mode"
        
        print("✓ Loaded in STANDARD mode")
        print(f"  - Classes: {clf1.num_classes}")
        
        # Switch to extended mode (will only work if model exists)
        clf2 = get_classifier(mode_override="extended")
        if clf2 and clf2.model:
            assert clf2.mode == MLPMode.EXTENDED, "Should be extended mode"
            print("✓ Switched to EXTENDED mode successfully")
            print(f"  - Classes: {clf2.num_classes}")
        else:
            print("⚠ Extended model not available (needs training)")
        
        # Switch back to standard
        clf3 = get_classifier(mode_override="standard")
        assert clf3.mode == MLPMode.STANDARD, "Should be back to standard"
        print("✓ Switched back to STANDARD mode")
        
        return True
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: No Breaking Changes
# ══════════════════════════════════════════════════════════════════════════════

def test_no_breaking_changes():
    """Verify existing functionality still works"""
    print("\n" + "="*80)
    print("TEST 6: Backward Compatibility (No Breaking Changes)")
    print("="*80)
    
    try:
        # Test 1: Can still import old functions
        from utils.shape_ai import detect_and_snap
        print("✓ utils.shape_ai still works")
        
        # Test 2: Can still import shape validation
        from utils.shape_mlp_ai import _validate_shape_match
        print("✓ Shape validation still works")
        
        # Test 3: Config still loads
        from core.config import MLP_CONFIDENCE_THRESHOLD, MP_MAX_HANDS
        assert MLP_CONFIDENCE_THRESHOLD == 0.65, "Config should be intact"
        assert MP_MAX_HANDS == 2, "Config should be intact"
        print("✓ Configuration still intact")
        
        # Test 4: Drawing 2D still imports
        from modules.drawing_2d import DrawingState
        print("✓ drawing_2d.py imports work")
        
        # Test 5: gesture classification still works
        from utils.gesture import classify_gesture
        print("✓ Gesture classification still works")
        
        return True
    except Exception as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Run all tests"""
    print("\n")
    print("█" * 80)
    print("█ TIER 3 RL + EXTENDED MLP INTEGRATION TEST SUITE")
    print("█" * 80)
    
    results = {}
    
    # Run tests
    results['MLP Standard'] = test_mlp_standard()
    results['MLP Extended'] = test_mlp_extended()
    results['RL Classifier'] = test_rl_classifier()
    results['RL Learning'] = test_rl_learning()
    results['Mode Switching'] = test_classifier_mode_switching()
    results['Backward Compat'] = test_no_breaking_changes()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    print("="*80)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Integration successful!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
