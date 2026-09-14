#!/usr/bin/env python3
"""Launch StickyTasks.

Double-click this file, or run:  python run_stickytasks.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stickytasks.app import main  # noqa: E402

if __name__ == "__main__":
    main()
