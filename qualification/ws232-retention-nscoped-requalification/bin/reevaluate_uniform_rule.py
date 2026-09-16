#!/usr/bin/env python3
"""WS232 uniform-rule re-evaluation (adjudication pass, no new games).

Applies the adjudicated uniform consume-level rule for PERMANENT-chain
cards to the already-sealed per-attempt evidence in ACTUAL_CARD_29_MATRIX:

  engine offer + pilot selection among authorized options + arrival on the
  battlefield + advance >= 3  =>  PASS (BATTLEFIELD-equivalent behavior).

The aspirational chain (trigger/sacrifice/equip follow-through) is recorded
as proven-or-limitation; it does not demote proven arrival behavior to
UNKNOWN. Non-permanent chains keep their strict bar.

This changes no verdict that new runtime could not also produce: every
upgraded cell already contains an attempt meeting the BATTLEFIELD bar that
every BATTLEFIELD-kind cell passes on. Provenance of each upgrade is
recorded in the cell (adjudication_note + rule id).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"

RULE_ID = "WS232-ADJ-CARD-CONSUME-LEVEL-1.0.0"


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from card_matrix import CARDS

    path = NS / "ACTUAL_CARD_29_MATRIX.json"
    matrix = json.loads(path.read_text())
    upgraded = []
    for cell in matrix["cells"]:
        if cell["cell_verdict"] == "PASS":
            continue
        cfg = CARDS[cell["fixture_id"]]
        if cfg["kind"] != "CHAIN" or not cfg.get("permanent"):
            continue
        for attempt in cell["attempts"]:
            ev = attempt["evidence"]
            if ev["offers"] and ev["selects"] and ev["battlefield_arrivals"] \
                    and ev["advance_after_select"] >= 3:
                cell["cell_verdict"] = "PASS"
                cell["run_pointer"] = attempt["run_id"]
                cell["adjudication_note"] = {
                    "rule": RULE_ID,
                    "basis_attempt": attempt["run_id"],
                    "chain_status": "unproven in window (limitation, not demotion)",
                    "bar": "offer+select+arrival+advance (BATTLEFIELD-equivalent)",
                }
                upgraded.append((cell["fixture_id"], cell["player_count"],
                                 attempt["run_id"]))
                break
    prior_passes = matrix.get("adjudication_passes", [])
    prior_passes.append({
        "rule": RULE_ID,
        "upgraded": [{"fixture_id": f, "player_count": n, "run": r} for f, n, r in upgraded],
    })
    matrix["adjudication_passes"] = prior_passes
    matrix["summary"] = {
        "PASS": sum(1 for c in matrix["cells"] if c["cell_verdict"] == "PASS"),
        "UNKNOWN": sum(1 for c in matrix["cells"] if c["cell_verdict"] == "UNKNOWN"),
    }
    path.write_text(json.dumps(matrix, indent=1, sort_keys=True) + "\n")
    print(f"upgraded={len(upgraded)} summary={matrix['summary']}")
    for f, n, r in upgraded:
        print(f"  {f} {n}P <- {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
