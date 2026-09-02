#!/usr/bin/env python3
"""WS-39 qualification-only semantic source-id correction for runtime evidence.

Run after apply_ws39_provider_overlay.py. This changes no rules or legality; it
only binds a native ability source to the already actor-visible semantic object
identity so exact contract payment sources can be selected without first/random
fallbacks.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java"

OLD = ").get(ability.getSourceId());"
NEW = ").get(ability.getSourceId().toString());"


def main() -> int:
    text = PLAYER.read_text(encoding="utf-8")
    if NEW in text:
        print("WS39_RUNTIME_EVIDENCE_OVERLAY=ALREADY_APPLIED")
        return 0
    if text.count(OLD) != 1:
        raise SystemExit(f"WS39_RUNTIME_EVIDENCE_ANCHOR_MISMATCH:count={text.count(OLD)}")
    PLAYER.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print("WS39_RUNTIME_EVIDENCE_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
