#!/usr/bin/env python3
"""WS64 full-tape breadth runner (WS64-owned, qualification-only).

WS62-verbatim delegation to ws62_breadth_runner with one harness-only delta:
persist the complete native event tape (not just the first 256) as
native_event_tape_full, plus a ws64 runner stamp. No engine, provider,
Decision, or intent semantics change. Transcript-size bound only.

This lets qualification read Stonecoil-window milestones that occur after
the 256-event prefix (announce X, payment, Moved singleton, DS/HS ordering,
battlefield counters) on the accepted Forge pin.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS64_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "ws62-forge-successor-requalification"))
sys.path.insert(0, str(HERE.parent / "ws53-forge-convergence-native-progression"))
sys.path.insert(0, str(HERE.parent / "ws48-forge-v1.0.5"))

import ws53_sequence_runner as ws53  # noqa: E402
import ws62_breadth_runner as ws62  # noqa: E402

_ORIG_FINISH = ws53.finish_ws53


def ws64_finish(out, drv, stop_reason, snapshot, answered, violations, lifecycle):
    r = _ORIG_FINISH(out, drv, stop_reason, snapshot, answered, violations, lifecycle)
    try:
        r["native_event_tape_full"] = list(drv.events)
    except Exception:
        r["native_event_tape_full"] = []
    r["ws64_runner"] = "ws64_fulltape_runner.py (ws62-verbatim + full tape)"
    return r


ws53.finish_ws53 = ws64_finish
ws62.ws53.finish_ws53 = ws64_finish


def main() -> int:
    return ws62.main()


if __name__ == "__main__":
    raise SystemExit(main())
