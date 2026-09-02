#!/usr/bin/env python3
"""Produce an exact v1.0.2 WS-36 denominator/capability census.

This is read-only contract analysis. It grants no runtime credit and does not
reinterpret the immutable WS-32 materialization.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS34 = HERE.parents[0] / "ws34-xmage-successor"
sys.path.insert(0, str(WS34))

import build_successor_matrix as ws34_matrix  # noqa: E402
import successor_contract as contractlib  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    contract = contractlib.load_contract(args.contract)
    records = contractlib.ws34_records(contract)
    if len(records) != 107 or len({r["fixture_id"] for r in records}) != 107:
        raise SystemExit("WS36_DENOMINATOR_INTEGRITY_FAILURE")

    blocker_to_ids: dict[str, list[str]] = defaultdict(list)
    decision_to_ids: dict[str, list[str]] = defaultdict(list)
    operation_to_ids: dict[str, list[str]] = defaultdict(list)
    entry = Counter()
    family = Counter()
    rows: list[dict[str, Any]] = []

    for record in records:
        classified = ws34_matrix.classify(record)
        fixture_id = record["fixture_id"]
        blockers = classified["construction_blockers"] + classified["decision_blockers"]
        decisions = sorted({
            d.get("decision_family")
            for d in record.get("decision_script", [])
            if isinstance(d.get("decision_family"), str)
        })
        operations = sorted({
            p.get("operation")
            for p in record.get("native_procedure", [])
            if isinstance(p.get("operation"), str)
        })
        for blocker in blockers:
            blocker_to_ids[blocker].append(fixture_id)
        for decision in decisions:
            decision_to_ids[decision].append(fixture_id)
        for operation in operations:
            operation_to_ids[operation].append(fixture_id)
        entry[record["execution_entry_mode"]] += 1
        family[record["fixture_family"]] += 1
        rows.append({
            "fixture_id": fixture_id,
            "fixture_family": record["fixture_family"],
            "entry_mode": record["execution_entry_mode"],
            "materialization_digest": record["materialization_digest"],
            "requested_state_digest": record["requested_state_digest"],
            "construction_blockers_ws34": classified["construction_blockers"],
            "decision_blockers_ws34": classified["decision_blockers"],
            "decision_families": decisions,
            "native_operations": operations,
        })

    result = {
        "schema_version": "commander-lab.ws36-contract-census/1.0.0",
        "contract_version": contractlib.CONTRACT_VERSION,
        "canonical_materialization_digest": contractlib.CANONICAL_MATERIALIZATION_DIGEST,
        "ws32_freeze_commit": contractlib.FREEZE_COMMIT,
        "ws32_freeze_tree": contractlib.FREEZE_TREE,
        "xmage_commit": contractlib.XMAGE_COMMIT,
        "xmage_tree": contractlib.XMAGE_TREE,
        "denominator": 107,
        "unique_fixture_ids": 107,
        "entry_mode_counts": dict(sorted(entry.items())),
        "family_counts": dict(sorted(family.items())),
        "ws34_blocker_counts": {
            k: len(v) for k, v in sorted(blocker_to_ids.items())
        },
        "ws34_blocker_fixture_ids": {
            k: sorted(v) for k, v in sorted(blocker_to_ids.items())
        },
        "decision_family_counts": {
            k: len(v) for k, v in sorted(decision_to_ids.items())
        },
        "decision_family_fixture_ids": {
            k: sorted(v) for k, v in sorted(decision_to_ids.items())
        },
        "native_operation_counts": {
            k: len(v) for k, v in sorted(operation_to_ids.items())
        },
        "native_operation_fixture_ids": {
            k: sorted(v) for k, v in sorted(operation_to_ids.items())
        },
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "denominator": 107,
        "blocker_counts": result["ws34_blocker_counts"],
        "decision_family_counts": result["decision_family_counts"],
        "native_operation_counts": result["native_operation_counts"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
