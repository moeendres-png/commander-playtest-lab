#!/usr/bin/env python3
"""WS46 binding of the proven WS39 runtime-evidence overlay.

The semantic-source evidence transform is reused unchanged. The only changed
binding is the RNG instrumentation executable, which is the WS46 source-lock
wrapper for XMage 0c1f455. Historical WS39 runtime PASS is not imported.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS39 = HERE.parents[0] / "ws39-xmage-successor"
sys.path.insert(0, str(WS39))

import apply_ws39_runtime_evidence_overlay as base  # noqa: E402

base.RNG_OVERLAY = HERE / "apply_ws46_rng_instrumentation.py"


if __name__ == "__main__":
    raise SystemExit(base.main())
