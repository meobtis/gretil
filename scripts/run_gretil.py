#!/usr/bin/env python3
"""Convenience runner script for GRETIL scraper and converter."""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from gretil.cli import main

if __name__ == "__main__":
    main()
