#!/usr/bin/env python3
"""WS-36 compatibility wrapper for the WS-34 terminal runtime attempts.

The only compatibility change here is v1.0.2 SCENARIO_SEED materialization.
No historical PASS is imported and no canonical record is mutated.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS34 = HERE.parents[0] / "ws34-xmage-successor"
FC = HERE.parents[0] / "finalist-convergence-xmage"
WS26 = HERE.parents[0] / "ws26-xmage"
sys.path[:0] = [str(HERE), str(WS34), str(FC), str(WS26)]

import run_terminal_attempts as ws34  # noqa: E402
from successor_runtime import v101_compat_record  # noqa: E402

_ORIGINAL_DECK_AND_SCENARIO = ws34.legacy.deck_and_scenario


def _successor_deck_and_scenario(record, schema):
    return _ORIGINAL_DECK_AND_SCENARIO(v101_compat_record(record), schema)


def main() -> int:
    ws34.legacy.deck_and_scenario = _successor_deck_and_scenario
    return ws34.main()


if __name__ == "__main__":
    raise SystemExit(main())
