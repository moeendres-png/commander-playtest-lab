#!/usr/bin/env python3
"""WS55 mechanical derivation of FIRST_WAVE_REQUIRED_DECISION_KINDS from RQ-C1.

Reads ONLY the exact RQ-C1 source lock (git ref, read-only via `git show`;
never checks out, never modifies RQ-C1) and derives the union of
discretionary decision kinds required by the 15 first-wave scenarios.

Triple cross-check:
  1. RQ_C1_SCENARIO_MANIFEST.json (first_wave=true scenarios' decision_kinds)
  2. RQ_C1_DECISION_SURFACE_MATRIX.csv (first-wave rows' 1-columns)
  3. The 15 first-wave scenario files' own decision_kinds

All three must agree exactly or the script fails loud (no silent union edit).

Writes WS55_FIRST_WAVE_DECISION_REQUIREMENTS.json next to this script's
output dir argument. Grants no behavior credit. Evidence class: CODE_DERIVED
(mechanical read of MODELED corpus design input; RQ-C1 expected Magic
outcomes are NOT used as Rules truth here).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

RQ_C1_REF = "research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910"
RQ_C1_DIR = "research/candidate-qualification/common/rq-c1"
RQ_C1_HEAD = "714ad417c1c090eb4ddf1ccd0828a2e869a80a74"
RQ_C1_TREE = "709a5944c9826dbaaa433052f3538425c8f0573b"


def show(ref_path: str) -> str:
    r = subprocess.run(["git", "show", f"{RQ_C1_REF}:{ref_path}"],
                       capture_output=True, text=True, check=True)
    return r.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    head = subprocess.run(["git", "rev-parse", RQ_C1_REF],
                          capture_output=True, text=True, check=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", f"{RQ_C1_REF}^{{tree}}"],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != RQ_C1_HEAD or tree != RQ_C1_TREE:
        raise SystemExit(f"WS55_RQC1_LOCK_MISMATCH:head={head}:tree={tree}")

    manifest = json.loads(show(f"{RQ_C1_DIR}/RQ_C1_SCENARIO_MANIFEST.json"))
    scenarios = manifest["scenarios"]
    fw_manifest = [s for s in scenarios if s.get("first_wave") is True]
    if len(fw_manifest) != 15:
        raise SystemExit(f"WS55_FIRST_WAVE_COUNT_MISMATCH:{len(fw_manifest)}")
    fw_ids = sorted(s["scenario_id"] for s in fw_manifest)

    union_manifest: set[str] = set()
    per_scenario: dict[str, dict] = {}
    for s in fw_manifest:
        kinds = list(s.get("decision_kinds") or [])
        union_manifest.update(kinds)
        per_scenario[s["scenario_id"]] = {
            "title": s.get("title"),
            "decision_kinds": sorted(kinds),
            "native_setup_boundary": s.get("native_setup_boundary"),
            "player_count": s.get("player_count"),
            "authority_status": s.get("authority_status"),
        }

    matrix_text = show(f"{RQ_C1_DIR}/RQ_C1_DECISION_SURFACE_MATRIX.csv")
    rows = list(csv.DictReader(io.StringIO(matrix_text)))
    fw_rows = [r for r in rows if r["scenario_id"] in set(fw_ids)]
    if len(fw_rows) != 15:
        raise SystemExit(f"WS55_MATRIX_FIRST_WAVE_COUNT_MISMATCH:{len(fw_rows)}")
    kind_cols = [c for c in rows[0].keys() if c != "scenario_id"]
    union_matrix: set[str] = set()
    for r in fw_rows:
        for c in kind_cols:
            if r[c].strip() == "1":
                union_matrix.add(c)
        mk = set(per_scenario[r["scenario_id"]]["decision_kinds"])
        ck = {c for c in kind_cols if r[c].strip() == "1"}
        if mk != ck:
            raise SystemExit(
                f"WS55_MANIFEST_MATRIX_DIVERGENCE:{r['scenario_id']}:"
                f"manifest_only={sorted(mk - ck)}:matrix_only={sorted(ck - mk)}")

    union_files: set[str] = set()
    for sid in fw_ids:
        s = json.loads(show(f"{RQ_C1_DIR}/scenarios/{sid}.json"))
        kinds = list(s.get("decision_kinds") or [])
        union_files.update(kinds)
        if set(kinds) != set(per_scenario[sid]["decision_kinds"]):
            raise SystemExit(f"WS55_SCENARIO_FILE_DIVERGENCE:{sid}")

    if union_manifest != union_matrix or union_manifest != union_files:
        raise SystemExit(
            "WS55_UNION_DIVERGENCE:manifest=%s:matrix=%s:files=%s"
            % (sorted(union_manifest), sorted(union_matrix), sorted(union_files)))

    out = {
        "schema": "ws55.first-wave-decision-requirements.v1",
        "rq_c1_ref": RQ_C1_REF,
        "rq_c1_head": RQ_C1_HEAD,
        "rq_c1_tree": RQ_C1_TREE,
        "derivation": "union of discretionary decision_kinds over the 15 "
                      "first_wave=true scenarios; manifest JSON x matrix CSV x "
                      "scenario files triple-agree (script fails loud otherwise)",
        "first_wave_scenario_count": 15,
        "first_wave_scenario_ids": fw_ids,
        "FIRST_WAVE_REQUIRED_DECISION_KINDS": sorted(union_manifest),
        "FIRST_WAVE_REQUIRED_DECISION_KINDS_COUNT": len(union_manifest),
        "per_scenario": per_scenario,
        "usage_note": "RQ-C1 is MODELED corpus design input. Its expected "
                      "Magic outcomes are NOT Rules truth. Only the "
                      "decision-surface requirements are consumed here.",
        "evidence_class": "CODE_DERIVED",
        "grants_behavior_credit": False,
    }
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"WS55_FIRST_WAVE_DERIVATION_OK N={len(union_manifest)} "
          f"scenarios=15 triple_agree=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
