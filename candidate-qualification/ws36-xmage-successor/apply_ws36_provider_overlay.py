#!/usr/bin/env python3
"""WS-36 qualification-only provider remediations.

Applies after the existing Primitive-A native-state overlay.  It may expose or
invoke genuine XMage state primitives, but must never implement Magic rules.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"

OLD = '''                if (permanent == null) {
                    throw fail("NATIVE_VALIDATION_FAILED: missing battlefield object " + text(cardSpec, "semantic_id"));
                }
                permanent.setFaceDown(booleanValue(cardSpec, "face_down", false), game);
'''
NEW = '''                if (permanent == null) {
                    throw fail("NATIVE_VALIDATION_FAILED: missing battlefield object " + text(cardSpec, "semantic_id"));
                }
                // NATIVE_STATE_LOAD describes a snapshot, not an enter-the-battlefield
                // transaction. game.cheat correctly exercises XMage's native ETB path,
                // but cards such as Path of Ancestry can thereby acquire a tapped state
                // that differs from the requested midgame snapshot. XMage explicitly
                // exposes setTapped as a no-event state setter, so normalize the snapshot
                // here and let validateNative independently read it back below.
                permanent.setTapped(booleanValue(cardSpec, "tapped", false));
                permanent.setFaceDown(booleanValue(cardSpec, "face_down", false), game);
'''


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")
    if NEW in text:
        print("WS36_PROVIDER_OVERLAY=ALREADY_APPLIED")
        return 0
    if text.count(OLD) != 1:
        raise SystemExit("WS36_TAPPED_SNAPSHOT_OVERLAY_ANCHOR_MISMATCH")
    SCENARIO.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print("WS36_PROVIDER_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
