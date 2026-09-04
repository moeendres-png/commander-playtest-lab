#!/usr/bin/env python3
"""WS42 v1.0.3 construction probe with full request-independent readback metadata.

The base probe intentionally consumes only the explicit WS42 native-readback
object. This wrapper preserves the provider-emitted configuration fields needed
for independent normalization without ever exposing or consuming the inherited
WS34 whole-request echo.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_full107_construction_probe_v103 as base  # noqa: E402

_ORIGINAL_CAPTURE = base.capture_non_echo_readback


def capture_non_echo_readback(
    record: dict[str, Any], scenario: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    proof = _ORIGINAL_CAPTURE(record, scenario, state)
    raw = state.get("ws42_native_construction_readback")
    if not isinstance(raw, dict):
        raise RuntimeError("WS42_NATIVE_CONSTRUCTION_READBACK_MISSING")

    required = (
        "execution_entry_mode",
        "rules_seed",
        "starting_player_seat",
        "starting_life",
        "player_count",
        "snapshot_boundary",
    )
    for key in required:
        if key not in raw:
            raise RuntimeError(f"WS42_NATIVE_READBACK_CONFIGURATION_FIELD_MISSING:{key}")
        proof[key] = raw[key]

    if proof["execution_entry_mode"] != record["execution_entry_mode"]:
        raise RuntimeError("WS42_NATIVE_READBACK_ENTRY_MODE_MISMATCH")
    if int(proof["player_count"]) != len(record["players"]):
        raise RuntimeError("WS42_NATIVE_READBACK_PLAYER_COUNT_MISMATCH")
    if int(proof["starting_player_seat"]) < 1 or int(proof["starting_player_seat"]) > int(proof["player_count"]):
        raise RuntimeError("WS42_NATIVE_READBACK_STARTING_PLAYER_INVALID")
    if int(proof["starting_life"]) <= 0:
        raise RuntimeError("WS42_NATIVE_READBACK_STARTING_LIFE_INVALID")

    proof["evidence_class"] = "LOWER_LEVEL_NATIVE_READBACK_READY_FOR_INDEPENDENT_NORMALIZATION"
    return proof


def main() -> int:
    base.capture_non_echo_readback = capture_non_echo_readback
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
