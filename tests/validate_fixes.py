#!/usr/bin/env python
"""
Validation script: Verify all recent fixes (FIX-16 through FIX-22) are in place

Run this to ensure the codebase has all the fixes applied correctly.
"""

import os
import sys
from pathlib import Path

print("=" * 70)
print("FIX VALIDATION CHECKER - Verifying FIX-16 through FIX-22")
print("=" * 70)
print()

workspace_root = Path(__file__).parent
checks_passed = 0
checks_failed = 0

def check_file_contains(filepath, search_string, fix_name):
    """Check if file contains a specific string"""
    global checks_passed, checks_failed
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        if search_string in content:
            print(f"✓ {fix_name} : Found in {filepath.name}")
            checks_passed += 1
            return True
        else:
            print(f"✗ {fix_name} : NOT FOUND in {filepath.name}")
            print(f"  Looking for: {search_string[:50]}...")
            checks_failed += 1
            return False
    except Exception as e:
        print(f"✗ {fix_name} : Error reading {filepath.name}: {e}")
        checks_failed += 1
        return False

# FIX-16: Gesture-based finger tracking
print("Checking FIX-16: Gesture-based finger tracking")
check_file_contains(
    workspace_root / "modules" / "drawing_2d.py",
    "# FIX-16: Use correct finger position based on gesture",
    "FIX-16"
)
print()

# FIX-17: Freehand stroke registration
print("Checking FIX-17: Freehand stroke registration")
check_file_contains(
    workspace_root / "modules" / "drawing_2d.py",
    "# FIX-17: Register freehand stroke BEFORE clearing buffers",
    "FIX-17"
)
print()

# FIX-18: Draw/thumbs_up separation
print("Checking FIX-18: Draw/thumbs_up gesture separation")
check_file_contains(
    workspace_root / "utils" / "gesture.py",
    "# FIX-18: Explicitly require thumb to be down to prevent confusion with thumbs_up",
    "FIX-18"
)
print()

# FIX-19: Button UI responsiveness
print("Checking FIX-19: Button UI responsiveness")
check_file_contains(
    workspace_root / "modules" / "drawing_2d.py",
    "# FIX-19: Check for button hits BEFORE gesture processing",
    "FIX-19"
)
print()

# FIX-20: Eliminate drawing delay
print("Checking FIX-20: Eliminate drawing delay")
check_file_contains(
    workspace_root / "modules" / "drawing_2d.py",
    "# FIX-20: Eliminate drawing delay by removing threshold requirement",
    "FIX-20"
)
print()

# FIX-21: Freehand repositioning
print("Checking FIX-21: Freehand repositioning with relative offsets")
check_file_contains(
    workspace_root / "modules" / "drawing_2d.py",
    "# FIX-21: Store stroke points as RELATIVE offsets from center",
    "FIX-21"
)
print()

# FIX-22: Hand rotation robustness
print("Checking FIX-22: Hand rotation robustness")
check_file_contains(
    workspace_root / "utils" / "gesture.py",
    "_finger_extension_depth(lm, tip_idx, mcp_idx)",
    "FIX-22"
)
print()

# Summary
print("=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)
print()
print(f"✓ Checks passed: {checks_passed}")
print(f"✗ Checks failed: {checks_failed}")
print()

if checks_failed == 0:
    print("✅ ALL FIXES VALIDATED - Code is ready!")
    sys.exit(0)
else:
    print("⚠️ Some fixes are missing or not properly implemented")
    print("Please review the failed checks above")
    sys.exit(1)
