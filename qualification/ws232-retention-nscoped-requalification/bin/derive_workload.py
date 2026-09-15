#!/usr/bin/env python3
"""WS232 workload derivation: mechanically recompute the S8 retained workload
from source-locked JSON + manifest. No hardcoded counts: every number is
derived; the script FAILS (nonzero exit) if the derived shape differs from
the S8 entry expectation, which the caller must classify as
SOURCE_AUTHORITY_DRIFT instead of running the campaign.

Inputs (audit-base bytes):
  qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json
  qualification/ws215-xmage-variable-player-multicardinality/COMMON_FIXTURE_DISPOSITION.json

Output:
  qualification/ws232-retention-nscoped-requalification/WORKLOAD_DERIVATION.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"

MANIFEST = REPO_ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"
DISPOSITION = (
    REPO_ROOT
    / "qualification/ws215-xmage-variable-player-multicardinality/COMMON_FIXTURE_DISPOSITION.json"
)

EXPECTED = {
    "common_fixture_total": 135,
    "rerun_required": 72,
    "retained_after_impact_adjudication": 47,
    "unknown": 16,
    "blocked": 0,
    "retained_actual_card": 29,
    "retained_micro_rules": 13,
    "retained_replay_rng": 5,
}

REQUIRED_N_CELLS = [2, 3, 5]


def main() -> int:
    manifest = json.loads(MANIFEST.read_text())
    disp = json.loads(DISPOSITION.read_text())

    fixtures = manifest["fixtures"]
    rows = disp["rows"]
    by_id = {f["fixture_id"]: f for f in fixtures}

    # 1. Manifest total + category census (derived, not copied).
    manifest_total = len(fixtures)
    manifest_cats = Counter(f["category"] for f in fixtures)

    # 2. Every disposition row must join to the manifest.
    unjoined = [r["fixture_id"] for r in rows if r["fixture_id"] not in by_id]
    if unjoined:
        print(f"DRIFT: disposition rows missing from manifest: {unjoined}")
        return 2

    # 3. Disposition census.
    disp_counts = Counter(r["disposition"] for r in rows)
    retained = [r for r in rows if r["disposition"] == "RETAINED_AFTER_IMPACT_ADJUDICATION"]
    unknown = [r for r in rows if r["disposition"] == "UNKNOWN"]
    rerun = [r for r in rows if r["disposition"] == "RERUN_REQUIRED"]
    blocked = [r for r in rows if r["disposition"] == "BLOCKED"]

    retained_cats = Counter(by_id[r["fixture_id"]]["category"] for r in retained)

    derived = {
        "common_fixture_total": manifest_total,
        "rerun_required": len(rerun),
        "retained_after_impact_adjudication": len(retained),
        "unknown": len(unknown),
        "blocked": len(blocked),
        "retained_actual_card": retained_cats.get("actual_card", 0),
        "retained_micro_rules": retained_cats.get("micro_rules", 0),
        "retained_replay_rng": retained_cats.get("replay_rng", 0),
    }

    mismatches = {
        k: {"expected": EXPECTED[k], "derived": derived[k]}
        for k in EXPECTED
        if EXPECTED[k] != derived[k]
    }
    if mismatches or manifest_total != len(rows):
        print("SOURCE_AUTHORITY_DRIFT:")
        print(json.dumps(
            {"mismatches": mismatches,
             "manifest_total": manifest_total,
             "disposition_rows": len(rows),
             "manifest_category_census": dict(manifest_cats),
             "disposition_census": dict(disp_counts)},
            indent=1, sort_keys=True))
        return 3

    # 4. Retained workload rows with historical rationale + required N cells.
    workload_rows = []
    for r in sorted(retained, key=lambda r: r["fixture_id"]):
        f = by_id[r["fixture_id"]]
        workload_rows.append({
            "fixture_id": r["fixture_id"],
            "category": f["category"],
            "manifest_player_count": f.get("player_count"),
            "manifest_seed": f.get("seed"),
            "card_identity": f.get("card_identity"),
            "requirement_ids": f.get("requirement_ids"),
            "historical_rationale": r.get("evidence"),
            "historical_outcome": r.get("outcome"),
            "required_n_cells": list(REQUIRED_N_CELLS),
        })

    unknown_rows = [
        {"fixture_id": r["fixture_id"],
         "category": by_id[r["fixture_id"]]["category"],
         "historical_rationale": r.get("evidence"),
         "s8_target": False,
         "successor": "S9"}
        for r in sorted(unknown, key=lambda r: r["fixture_id"])
    ]

    artifact = {
        "schema_version": "ws232-workload-derivation-1.0.0",
        "derivation": "mechanical recomputation from source-locked manifest + disposition; no copied counts",
        "inputs": {
            "manifest": "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json",
            "disposition": "qualification/ws215-xmage-variable-player-multicardinality/COMMON_FIXTURE_DISPOSITION.json",
        },
        "manifest_category_census": dict(sorted(manifest_cats.items())),
        "derived_counts": derived,
        "entry_expectation": EXPECTED,
        "shape_match": True,
        "retained_total": len(workload_rows),
        "retained_rows": workload_rows,
        "unknown_total": len(unknown_rows),
        "unknown_rows": unknown_rows,
        "n_scoped_cells_per_retained_row": list(REQUIRED_N_CELLS),
        "total_n_scoped_cells": len(workload_rows) * len(REQUIRED_N_CELLS),
    }

    out = NS / "WORKLOAD_DERIVATION.json"
    out.write_text(json.dumps(artifact, indent=1, sort_keys=True) + "\n")
    print(f"shape_match=True total={manifest_total} "
          f"rerun={len(rerun)} retained={len(retained)} "
          f"unknown={len(unknown)} blocked={len(blocked)} "
          f"retained(actual={derived['retained_actual_card']},"
          f"micro={derived['retained_micro_rules']},"
          f"replay={derived['retained_replay_rng']}) "
          f"cells={artifact['total_n_scoped_cells']} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
