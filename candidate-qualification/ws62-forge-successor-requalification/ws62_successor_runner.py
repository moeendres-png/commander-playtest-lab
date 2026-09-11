#!/usr/bin/env python3
"""WS62 successor runner shim (WS62-owned, qualification-only).

Delegates to candidate-qualification/ws55r-forge-rqc3-impact-closure/
ws55r_breadth_runner_full.py (VERBATIM, never modified) but enforces the
successor pin and stamps WS62 identity on every journal.

- Requires FORGE_COMMIT/TREE from the successor-patched runners dir to equal
  the production successor (a9a95db / 2c18327...). Fails loud otherwise.
- Requires COMMANDER_LAB_FORGE_PROVIDER_CMD to reference /tmp/ws62-ev
  (successor provider.classpath first) and to contain no old-pin path.
- Stamps ws62_runner / ws62_forge fields on the result (additive only).

Grants no behavior credit (BEHAVIOR_CREDIT=0/107).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS55R = HERE.parent / "ws55r-forge-rqc3-impact-closure"
sys.path.insert(0, str(WS55R))

FORGE_SUCCESSOR_COMMIT = "a9a95db6662c2d28814390a9c0c2f986e39aa8b4"
FORGE_SUCCESSOR_TREE = "2c18327f79e330f2ed167067166ffd42d61b0849"
FORGE_OLD_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"

# Import the WS55R runner module (verbatim donor, never modified).
import ws55r_breadth_runner_full as donor  # noqa: E402


def _assert_successor_runtime(runners: str) -> None:
    sys.path.insert(0, runners)
    try:
        import run_behavior_transcript_probe as base  # type: ignore
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(runners)
    if getattr(base, "FORGE_COMMIT", None) != FORGE_SUCCESSOR_COMMIT:
        raise SystemExit(f"WS62_RUNNER_PIN_MISMATCH:FORGE_COMMIT={getattr(base,'FORGE_COMMIT',None)}")
    if getattr(base, "FORGE_TREE", None) != FORGE_SUCCESSOR_TREE:
        raise SystemExit(f"WS62_RUNNER_PIN_MISMATCH:FORGE_TREE={getattr(base,'FORGE_TREE',None)}")
    import os as _os
    cmd = _os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "")
    if "/tmp/ws62-ev" not in cmd:
        raise SystemExit("WS62_RUNNER_PROVIDER_CMD_NOT_SUCCESSOR:/tmp/ws62-ev missing")
    if FORGE_OLD_COMMIT in cmd or "forge-66caae" in cmd:
        raise SystemExit("WS62_RUNNER_OLD_PIN_ON_CMD_FAIL_CLOSED")


def main() -> int:
    # Parse only WS62-owned flags, pass through the rest to the donor.
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--runners", default=".")
    ap.add_argument("--output", type=Path, required=True)
    known, _rest = ap.parse_known_args()
    _assert_successor_runtime(known.runners)
    # Delegate to donor main with the original argv (donor parses all flags).
    rc = donor.main()
    # Stamp WS62 identity on the produced journal (additive, never rewrites proof).
    try:
        doc = json.loads(known.output.read_text())
    except Exception as ex:
        raise SystemExit(f"WS62_RUNNER_OUTPUT_MISSING:{ex}") from ex
    if (doc.get("forge") or {}).get("commit") != FORGE_SUCCESSOR_COMMIT:
        raise SystemExit(f"WS62_JOURNAL_PIN_MISMATCH:{(doc.get('forge') or {}).get('commit')}")
    if (doc.get("forge") or {}).get("tree") != FORGE_SUCCESSOR_TREE:
        raise SystemExit("WS62_JOURNAL_TREE_MISMATCH")
    doc["ws62_runner"] = "ws62_successor_runner.py (donor ws55r_breadth_runner_full.py verbatim + successor pin gate)"
    doc["ws62_forge"] = {"commit": FORGE_SUCCESSOR_COMMIT, "tree": FORGE_SUCCESSOR_TREE}
    doc["ws62_old_pin_absent"] = FORGE_OLD_COMMIT not in json.dumps(doc)
    known.output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"WS62_RUNNER_PIN_OK:{FORGE_SUCCESSOR_COMMIT[:7]}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
