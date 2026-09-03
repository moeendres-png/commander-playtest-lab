#!/usr/bin/env python3
"""WS-39 qualification-only runtime-evidence overlays.

Run after apply_ws39_provider_overlay.py. The XMage source transform instruments
native RandomUtil for attributable/replayable Rules-RNG evidence; it does not
supply randomness from Commander Lab. The bridge correction binds a native
ability source to the already actor-visible semantic object identity so exact
contract payment sources can be selected without first/random fallbacks.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java"
RNG_OVERLAY = ROOT / "candidate-qualification/ws39-xmage-successor/apply_ws39_rng_instrumentation.py"
XMAGE_ROOT = ROOT / "vendor/engine-source/xmage"
RNG_REPORT = ROOT / "artifacts/ws39-ci/WS39_XMAGE_RNG_SOURCE_TRANSFORM.json"

OLD = ").get(ability.getSourceId());"
NEW = ").get(ability.getSourceId().toString());"


def apply_rng_instrumentation() -> None:
    subprocess.run(
        [
            sys.executable,
            str(RNG_OVERLAY),
            "--xmage-root",
            str(XMAGE_ROOT),
            "--output",
            str(RNG_REPORT),
        ],
        check=True,
    )


def main() -> int:
    apply_rng_instrumentation()
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
