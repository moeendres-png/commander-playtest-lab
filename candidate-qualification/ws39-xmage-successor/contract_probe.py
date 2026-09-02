#!/usr/bin/env python3
"""Inspect the immutable WS-32 v1.0.2 denominator for WS-39.

This probe is intentionally read-only. It records exact canonical structures for
the mandatory commander-history records and proves the 107-record XMage
successor denominator before runtime translation is attempted.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS34 = HERE.parents[0] / "ws34-xmage-successor"
sys.path.insert(0, str(WS34))

from successor_contract import load_contract, requested_state_digest, ws34_records  # noqa: E402

MANDATORY = ("WS05-CMD-TAX-2", "WS05-CMD-TAX-4", "WS05-CMD-PARTNER-TAX")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = ws34_records(contract)
    ids = [record["fixture_id"] for record in records]
    if len(records) != 107 or len(set(ids)) != 107:
        raise SystemExit(f"WS39_DENOMINATOR_MISMATCH:{len(records)}:{len(set(ids))}")

    by_id = {record["fixture_id"]: record for record in records}
    missing = [fixture_id for fixture_id in MANDATORY if fixture_id not in by_id]
    if missing:
        raise SystemExit(f"WS39_MANDATORY_RECORDS_MISSING:{missing}")

    mandatory = {}
    for fixture_id in MANDATORY:
        record = by_id[fixture_id]
        calculated = requested_state_digest(record)
        declared = record.get("requested_state_digest")
        if calculated != declared:
            raise SystemExit(f"WS39_REQUESTED_DIGEST_MISMATCH:{fixture_id}:{declared}:{calculated}")
        mandatory[fixture_id] = {
            "fixture_id": fixture_id,
            "execution_entry_mode": record.get("execution_entry_mode"),
            "requested_state_digest": declared,
            "commander_state": record.get("commander_state"),
            "players": record.get("players"),
            "semantic_objects": record.get("semantic_objects"),
            "temporal_state": record.get("temporal_state"),
            "setup_validation": record.get("setup_validation"),
            "transaction": record.get("transaction"),
            "expected": record.get("expected"),
            "oracle": record.get("oracle"),
        }

    result = {
        "schema_version": "commander-lab.ws39-contract-probe/1.0.0",
        "contract_schema_version": contract.get("schema_version"),
        "materialization_digest": contract.get("materialization_digest"),
        "denominator": len(records),
        "unique_fixture_ids": len(set(ids)),
        "mandatory_ids": list(MANDATORY),
        "mandatory_records": mandatory,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
