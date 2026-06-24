#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""
build_test_game.py -- thin entry for Game-target only (WITH_EDITOR=0).

Delegates to build_test.py --game-only. Full build_test.py runs Editor + Game by default.

Usage:
    python build_test_game.py [--versions UE_X.Y ...]
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from build_test import main  # noqa: E402

if __name__ == "__main__":
    if "--game-only" not in sys.argv:
        sys.argv.insert(1, "--game-only")
    sys.exit(main())
