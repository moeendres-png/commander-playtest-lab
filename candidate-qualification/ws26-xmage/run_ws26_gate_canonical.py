#!/usr/bin/env python3
"""WS-26 clean-process replay entrypoint with canonical legal-option set ordering.

This wrapper deliberately changes only replay comparison presentation. Legal actions
remain provider-owned; selected option order and explicit `ordering` values are not
sorted or otherwise rewritten. Each replay capture is also persisted as qualification
diagnostic evidence so semantic-state mismatches can be compared fail-closed.
"""
from __future__ import annotations

import json
from pathlib import Path

import run_ws26_gate as gate


_original_offer_map = gate.replay_semantic_offer_map
_original_capture_replay_run = gate.capture_replay_run
_capture_index = 0


def canonical_offer_map(decision):
    semantic_ids, raw_by_semantic = _original_offer_map(decision)
    return sorted(semantic_ids), raw_by_semantic


def diagnostic_capture_replay_run(expected_tape=None):
    global _capture_index
    result = _original_capture_replay_run(expected_tape)
    _capture_index += 1
    out = Path("qualification/evidence/ws26-xmage")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"REPLAY_CAPTURE_{_capture_index}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


gate.replay_semantic_offer_map = canonical_offer_map
gate.capture_replay_run = diagnostic_capture_replay_run


if __name__ == "__main__":
    raise SystemExit(gate.main())
