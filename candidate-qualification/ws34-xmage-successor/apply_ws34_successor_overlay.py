#!/usr/bin/env python3
"""Qualification-only WS-34 provider overlay; never edits the pinned XMage engine."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java"

OLD = "MulliganType.LONDON.getMulligan(1),"
NEW = "MulliganType.LONDON.getMulligan(playerCount >= 3 ? 1 : 0),"


def main() -> int:
    text = SESSION.read_text(encoding="utf-8")
    if NEW in text:
        return 0
    if text.count(OLD) != 1:
        raise SystemExit("WS34_MULLIGAN_OVERLAY_ANCHOR_MISMATCH")
    SESSION.write_text(text.replace(OLD, NEW), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
