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

EXPECTED_ENTRY_MODE_COUNTS = {
    "NATIVE_STATE_LOAD": 100,
    "NATURAL_GAME_START": 7,
}
EXPECTED_NATURAL_START_FIXTURES = [
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
]

_LEGACY_REQUIRED_DIMENSIONS = legacy.required_dimensions


def required_dimensions_v104(record: dict) -> set[str]:
    """Admit immutable v1.0.4 natural-start records to fresh native execution.

    WS42 used the synthetic ``natural_game_start`` required-dimension sentinel
    only to defer those records to another executor. WS46 has no such split:
    all seven immutable NATURAL_GAME_START records execute through the same
    fresh one-game XMage process and request-independent readback path. No
    historical result is imported and no Magic legality is supplied here.
    """
    if record.get("execution_entry_mode") == "NATURAL_GAME_START":
        return set()
    return _LEGACY_REQUIRED_DIMENSIONS(record)


def configure_v104_runtime() -> None:
    legacy.canonical_v103 = canonical_v104
    legacy.load_contract = load_contract
    legacy.provider_records = provider_records
    legacy.CURRENT_NATIVE_DIMENSIONS.update(WS46_IMPLEMENTED_NATIVE_DIMENSIONS)
    legacy.capture_non_echo_readback = enriched.capture_non_echo_readback
    legacy.required_dimensions = required_dimensions_v104


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

    entry_mode_counts: dict[str, int] = {}
    natural_start_fixtures: list[str] = []
    for record in records:
        mode = record.get("execution_entry_mode")
        entry_mode_counts[mode] = entry_mode_counts.get(mode, 0) + 1
        if mode == "NATURAL_GAME_START":
            natural_start_fixtures.append(record["fixture_id"])
    if entry_mode_counts != EXPECTED_ENTRY_MODE_COUNTS:
        raise RuntimeError(
            "WS46_V104_ENTRY_MODE_DISTRIBUTION_MISMATCH:"
            f"expected={EXPECTED_ENTRY_MODE_COUNTS}:observed={entry_mode_counts}"
        )
    if natural_start_fixtures != EXPECTED_NATURAL_START_FIXTURES:
        raise RuntimeError(
            "WS46_V104_NATURAL_START_IDENTITY_MISMATCH:"
            f"expected={EXPECTED_NATURAL_START_FIXTURES}:observed={natural_start_fixtures}"
        )

    rows = [legacy.probe_record(record) for record in records]
    counts: dict[str, int] = {}
    unsupported_dimension_counts: dict[str, int] = {}
    for row in rows:
        status = row["construction_status"]
        counts[status] = counts.get(status, 0) + 1
        for dimension in row.get("unsupported_dimensions") or []:
            unsupported_dimension_counts[dimension] = unsupported_dimension_counts.get(dimension, 0) + 1

    if counts.get("DEFERRED_TO_FRESH_NATURAL_EXECUTOR", 0) != 0:
        raise RuntimeError("WS46_NATURAL_START_DEFERRED_INSTEAD_OF_EXECUTED")

    output = {
        "schema_version": "commander-lab.ws46-full107-construction-probe/1.0.1",
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.4",
        "candidate_commit": legacy.run_tax3.exact_provider_identity()[0],
        "engine_commit": os.environ.get("XMAGE_WS46_COMMIT", "UNKNOWN"),
        "denominator": 107,
        "record_count": len(rows),
        "entry_mode_counts": entry_mode_counts,
        "natural_start_fixture_ids": natural_start_fixtures,
        "natural_start_fresh_execution_required": True,
        "natural_start_historical_credit_imported": False,
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
    print(json.dumps({
        "counts": counts,
        "entry_mode_counts": entry_mode_counts,
        "unsupported_dimension_counts": output["unsupported_dimension_counts"],
    }, sort_keys=True))
    if len(rows) != 107 or not output["record_order_preserved"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
