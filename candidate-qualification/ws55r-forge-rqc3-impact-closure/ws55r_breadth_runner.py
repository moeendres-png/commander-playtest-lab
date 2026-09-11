#!/usr/bin/env python3
"""WS55R breadth runner wrapper (WS55R-owned, qualification-only).

Reuses the WS55 breadth runner verbatim (imported, never modified) with one
harness-configuration change: the engine-side priority polling bound
COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY is raised from 512 to 2048 so a
longer NATURAL_GAME_START game (5+ land drops for the corrected C01
five-Island fixture) can complete inside one transcript.

This bound is harness configuration (like --structural-cap): it changes no
engine source, no provider logic, no Decision offer set, no RNG, no rule.
The effective bound is stamped into every output journal
(`ws55r_stop_after_priority`) for transparency.

Usage mirrors ws55_breadth_runner.py; all other flags pass through.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS55 = HERE.parent / "ws55-forge-mandatory-decision-breadth"
WS53 = HERE.parent / "ws53-forge-convergence-native-progression"
WS48 = HERE.parent / "ws48-forge-v1.0.5"

sys.path.insert(0, str(WS55))
sys.path.insert(0, str(WS53))
sys.path.insert(0, str(WS48))

import run_behavior_transcript_probe as base  # noqa: E402

WS55R_STOP_AFTER_PRIORITY = "2048"

_orig_behavior_env = base.behavior_env


def _ws55r_behavior_env(record, transport):
    e = _orig_behavior_env(record, transport)
    e["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = WS55R_STOP_AFTER_PRIORITY
    return e


base.behavior_env = _ws55r_behavior_env

import ws55_breadth_runner as w55  # noqa: E402


def main() -> int:
    # Patch every already-imported alias of behavior_env used by the drivers.
    try:
        import ws53_sequence_runner as w53  # noqa: E402
        if getattr(w53, "base", None) is base:
            pass
    except Exception:
        pass
    rc = w55.main()
    # Stamp the effective bound into the output journal for transparency.
    try:
        out_arg = sys.argv[sys.argv.index("--output") + 1]
        p = Path(out_arg)
        if p.exists():
            doc = json.loads(p.read_text())
            doc["ws55r_stop_after_priority"] = int(WS55R_STOP_AFTER_PRIORITY)
            doc["ws55r_runner"] = "ws55r_breadth_runner.py (STOP_AFTER_PRIORITY=2048; else WS55-verbatim)"
            p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    except Exception as ex:  # never fail a run on stamping
        print(f"WS55R stamp warning: {ex}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
