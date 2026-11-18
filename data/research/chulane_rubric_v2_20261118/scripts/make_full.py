#!/usr/bin/env python3
"""Full run (922 cards, rater F1): shortcut for ``make_batches.py --out <dir> --run full``."""

from __future__ import annotations

import sys

import make_batches

if __name__ == "__main__":
    sys.argv += ["--run", "full"]
    make_batches.main()
