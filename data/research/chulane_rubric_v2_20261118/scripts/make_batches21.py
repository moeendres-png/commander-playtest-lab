#!/usr/bin/env python3
"""Run v2.1 (raters T1, T2): shortcut for ``make_batches.py --out <dir> --run v2.1``."""

from __future__ import annotations

import sys

import make_batches

if __name__ == "__main__":
    sys.argv += ["--run", "v2.1"]
    make_batches.main()
