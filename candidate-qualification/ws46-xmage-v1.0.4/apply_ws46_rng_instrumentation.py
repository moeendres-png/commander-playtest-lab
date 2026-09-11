#!/usr/bin/env python3
"""Run the proven WS39 Rules-RNG transform against the exact WS46 XMage lock.

No transform precondition is weakened: only the candidate commit guard is
advanced from the WS39 parent to the source-audited WS46 child commit. All
per-file replacement counts and exact source anchors remain those of WS39.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS39 = HERE.parents[0] / "ws39-xmage-successor"
sys.path.insert(0, str(WS39))

import apply_ws39_rng_instrumentation as base  # noqa: E402

base.XMAGE_COMMIT = "0c1f455ea8c8fa48ab9d638ad5068ec242800428"


if __name__ == "__main__":
    raise SystemExit(base.main())
