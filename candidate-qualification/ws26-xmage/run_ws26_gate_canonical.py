#!/usr/bin/env python3
"""WS-26 clean-process replay entrypoint with canonical legal-option set ordering.

This wrapper deliberately changes only replay comparison presentation. Legal actions
remain provider-owned; selected option order and explicit `ordering` values are not
sorted or otherwise rewritten.
"""
from __future__ import annotations

import run_ws26_gate as gate


_original_offer_map = gate.replay_semantic_offer_map


def canonical_offer_map(decision):
    semantic_ids, raw_by_semantic = _original_offer_map(decision)
    return sorted(semantic_ids), raw_by_semantic


gate.replay_semantic_offer_map = canonical_offer_map


if __name__ == "__main__":
    raise SystemExit(gate.main())
