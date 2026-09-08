#!/usr/bin/env python3
"""Fresh fail-closed WS46 v1.0.4 XMage construction probe.

All 107 provider-denominator records start from zero v1.0.4 runtime credit. The
probe reuses source-audited WS42 process/bootstrap code, but binds the immutable
WS44 contract, the v1.0.4 translator, and the complete WS46 native dimension
set. Construction credit remains pending until independent normalization.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path[:0] = [str(HERE), str(WS42)]

import canonical_v104  # noqa: E402
import run_full107_construction_probe_v103 as legacy  # noqa: E402
import run_full107_construction_probe_v103_enriched as enriched  # noqa: E402
from successor_contract_v104 import load_contract, provider_records  # noqa: E402

WS46_IMPLEMENTED_NATIVE_DIMENSIONS = set(enriched.WS42_IMPLEMENTED_NATIVE_DIMENSIONS) | {
    "combat_state",
    "extra_turn_creation",
    "elimination_trigger",
    "knowledge_grants",
    "zone_move_event",
}


def configure_v104_runtime() -> None:
    legacy.canonical_v103 = canonical_v104
    legacy.load_contract = load_contract
    legacy.provider_records = provider_records
    legacy.CURRENT_NATIVE_DIMENSIONS.update(WS46_IMPLEMENTED_NATIVE_DIMENSIONS)
    legacy.capture_non_echo_readback = enriched.capture_non_echo_readback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()
    if args.max_workers != 1:
        raise SystemExit("WS46_UNQUALIFIED_PARALLEL_XMAGE_PROBE_FORBIDDEN")

    configure_v104_runtime()
    contract = load_contract(args.contract)
    records = provider_records(contract)
    if any(record.get("execution_entry_mode") == "NATURAL_GAME_START" for record in records):
        raise RuntimeError("WS46_V104_UNEXPECTED_NATURAL_GAME_START_RECORD")

    rows = [legacy.probe_record(record) for record in records]
    counts: dict[str, int] = {}
    unsupported_dimension_counts: dict[str, int] = {}
    for row in rows:
        status = row["construction_status"]
        counts[status] = counts.get(status, 0) + 1
        for dimension in row.get("unsupported_dimensions") or []:
            unsupported_dimension_counts[dimension] = unsupported_dimension_counts.get(dimension, 0) + 1

    output = {
        "schema_version": "commander-lab.ws46-full107-construction-probe/1.0.0",
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.4",
        "candidate_commit": legacy.run_tax3.exact_provider_identity()[0],
        "engine_commit": os.environ.get("XMAGE_WS46_COMMIT", "UNKNOWN"),
        "denominator": 107,
        "record_count": len(rows),
        "counts": counts,
        "unsupported_dimension_counts": dict(sorted(unsupported_dimension_counts.items())),
        "current_native_dimensions": sorted(legacy.CURRENT_NATIVE_DIMENSIONS),
        "translator": "candidate-qualification/ws46-xmage-v1.0.4/canonical_v104.py",
        "max_workers": 1,
        "parallel_probe_qualified": False,
        "record_order_preserved": [row["fixture_id"] for row in rows] == [record["fixture_id"] for record in records],
        "legacy_request_echo_accepted_as_proof": False,
        "independent_normalized_construction_gate_closed": False,
        "historical_pass_imported": False,
        "runtime_credit_granted": False,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "unsupported_dimension_counts": output["unsupported_dimension_counts"]}, sort_keys=True))
    if len(rows) != 107 or not output["record_order_preserved"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
