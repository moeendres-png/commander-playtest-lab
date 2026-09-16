#!/usr/bin/env python3
"""WS232 successor disposition sealer (mechanical join, no hand edits).

Joins, per retained fixture x {2P,3P,5P}:
  - ACTUAL_CARD_29_MATRIX / MICRO_RULE_13_MATRIX / REPLAY_RNG_5_MATRIX cells
  - RETENTION_PREDICATES (static bind half)
into N_SCOPED_DISPOSITION.json. Every cell ends PASS (current rerun pointer)
or UNKNOWN (explicit cause). No other verdict exists. Prose-only retention
is impossible by construction: a PASS cell without a run pointer is
rejected (exit nonzero).

Also writes UNKNOWN_16_PRESERVATION.json (S9 set untouched) and joins the
behavior-discharge half back into RETENTION_PREDICATE_RESULTS.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"


def load(name):
    return json.loads((NS / name).read_text())


def main() -> int:
    deriv = load("WORKLOAD_DERIVATION.json")
    cards = load("ACTUAL_CARD_29_MATRIX.json")
    micros = load("MICRO_RULE_13_MATRIX.json")
    replays = load("REPLAY_RNG_5_MATRIX.json")
    pred_results = load("RETENTION_PREDICATE_RESULTS.json")

    card_cells = {(c["fixture_id"], c["player_count"]): c for c in cards["cells"]}
    micro_cells = {(c["fixture_id"], c["player_count"]): c for c in micros["cells"]}
    replay_cells = {(c["fixture_id"], c["player_count"]): c for c in replays["cells"]}
    static = {r["fixture_id"]: r["static_verdict"] for r in pred_results["results"]}

    rows = []
    for row in deriv["retained_rows"]:
        fid, cat = row["fixture_id"], row["category"]
        src = {"actual_card": card_cells, "micro_rules": micro_cells,
               "replay_rng": replay_cells}[cat]
        for n in (2, 3, 5):
            cell = src.get((fid, n))
            if cell is None:
                print(f"MISSING cell {fid} {n}P")
                return 2
            verdict = cell["cell_verdict"]
            pointer = cell.get("run_pointer")
            if verdict == "PASS" and not pointer:
                print(f"PROSE-ONLY RETENTION REJECTED: {fid} {n}P")
                return 3
            if verdict not in ("PASS", "UNKNOWN"):
                print(f"ILLEGAL VERDICT {verdict}: {fid} {n}P")
                return 4
            cause = None
            if verdict == "UNKNOWN":
                cause = cell.get("rationale") or "see attempts"
            rows.append({
                "fixture_id": fid,
                "category": cat,
                "player_count": n,
                "n_scoped_verdict": verdict,
                "predicate_id": "PRED-" + fid,
                "predicate_static": static.get(fid, "MISSING"),
                "rerun_pointer": pointer,
                "unknown_cause": cause,
            })

    disp = {"schema_version": "ws232-n-scoped-disposition-1.0.0",
            "retained_total": 47,
            "cells": rows,
            "summary": {
                "PASS": sum(1 for r in rows if r["n_scoped_verdict"] == "PASS"),
                "UNKNOWN": sum(1 for r in rows if r["n_scoped_verdict"] == "UNKNOWN"),
                "by_count": {
                    str(n): {
                        "PASS": sum(1 for r in rows if r["player_count"] == n and r["n_scoped_verdict"] == "PASS"),
                        "UNKNOWN": sum(1 for r in rows if r["player_count"] == n and r["n_scoped_verdict"] == "UNKNOWN"),
                    } for n in (2, 3, 5)},
            }}
    (NS / "N_SCOPED_DISPOSITION.json").write_text(json.dumps(disp, indent=1, sort_keys=True) + "\n")

    # UNKNOWN_16 preservation (S9 set: present, unmodified, still UNKNOWN).
    unk = deriv["unknown_rows"]
    assert len(unk) == 16
    assert all(u["successor"] == "S9" and u["s8_target"] is False for u in unk)
    (NS / "UNKNOWN_16_PRESERVATION.json").write_text(json.dumps(
        {"schema_version": "ws232-unknown-16-preservation-1.0.0",
         "unknown_total": 16,
         "s8_target": False,
         "successor": "S9",
         "note": "S9 Commander/multiplayer rows: neither upgraded nor lost by WS232",
         "rows": unk}, indent=1, sort_keys=True) + "\n")

    # Behavior-discharge join back into predicate results.
    by_cell = {(r["fixture_id"], r["player_count"]): r for r in rows}
    for res in pred_results["results"]:
        parts = []
        for n in (2, 3, 5):
            c = by_cell[(res["fixture_id"], n)]
            parts.append(f"{n}P:{c['n_scoped_verdict']}:{(c['rerun_pointer'] or 'no-pointer')}")
        res["behavior_discharge"] = "DISCHARGED(" + ",".join(parts) + ")"
    (NS / "RETENTION_PREDICATE_RESULTS.json").write_text(
        json.dumps(pred_results, indent=1, sort_keys=True) + "\n")

    print(f"disposition cells={len(rows)} summary={disp['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
