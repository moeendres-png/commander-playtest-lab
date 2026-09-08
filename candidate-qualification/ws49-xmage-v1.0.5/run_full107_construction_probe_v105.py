#!/usr/bin/env python3
"""Fresh fail-closed WS49 v1.0.5 XMage construction probe from record 1.

All 107 rows start from zero v1.0.5 credit.  The probe consumes immutable WS47,
executes one XMage game process per row, and accepts only lower-level native
readback at the correct construction boundary.  Final construction credit is
withheld until the separate independent normalizer passes all 107 rows.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path[:0] = [str(HERE), str(WS42)]

import canonical_v105  # noqa: E402
import run_full107_construction_probe_v103 as legacy  # noqa: E402
import run_full107_construction_probe_v103_enriched as enriched  # noqa: E402
from successor_contract_v105 import load_contract, provider_records  # noqa: E402

WS49_IMPLEMENTED_NATIVE_DIMENSIONS = set(enriched.WS42_IMPLEMENTED_NATIVE_DIMENSIONS) | {
    "combat_state",
    "extra_turn_creation",
    "elimination_trigger",
    "knowledge_grants",
    "zone_move_event",
}

EXPECTED_ENTRY_MODE_COUNTS = {"NATIVE_STATE_LOAD": 100, "NATURAL_GAME_START": 7}
EXPECTED_NATURAL_START_FIXTURES = [
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
]
NATIVE_SETUP_BOUNDARY = "AFTER_NATIVE_SETUP_VALIDATION_BEFORE_PRIORITY_RESUME"
NATURAL_START_BOUNDARY = "AFTER_NATURAL_GAME_START_AT_FIRST_EXTERNAL_DECISION_BEFORE_SUBMISSION"

_LEGACY_REQUIRED_DIMENSIONS = legacy.required_dimensions


def required_dimensions_v105(record: dict) -> set[str]:
    if record.get("execution_entry_mode") == "NATURAL_GAME_START":
        return set()
    return _LEGACY_REQUIRED_DIMENSIONS(record)


def capture_non_echo_readback_v105(
    record: dict[str, Any], scenario: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    mode = record.get("execution_entry_mode")
    if mode == "NATIVE_STATE_LOAD":
        proof = enriched.capture_non_echo_readback(record, scenario, state)
        if proof.get("snapshot_boundary") != NATIVE_SETUP_BOUNDARY:
            raise RuntimeError("WS49_NATIVE_SETUP_BOUNDARY_REGRESSION")
        if proof.get("request_object_copied_as_proof") is not False:
            raise RuntimeError("WS49_NATIVE_SETUP_REQUEST_ECHO_NOT_FALSE")
        return proof
    if mode != "NATURAL_GAME_START":
        raise RuntimeError(f"WS49_UNSUPPORTED_EXECUTION_ENTRY_MODE:{mode}")

    readback = state.get("ws42_native_construction_readback")
    if not isinstance(readback, dict):
        raise RuntimeError("WS49_NATURAL_START_NATIVE_READBACK_MISSING")
    if readback.get("schema_version") != "xmage-ws42-native-construction-readback/1.0.0":
        raise RuntimeError("WS49_NATURAL_START_READBACK_SCHEMA_MISMATCH")
    if readback.get("request_object_copied_as_proof") is not False:
        raise RuntimeError("WS49_NATURAL_START_REQUEST_ECHO_NOT_FALSE")
    if readback.get("snapshot_boundary") != NATURAL_START_BOUNDARY:
        raise RuntimeError(
            "WS49_NATURAL_START_SNAPSHOT_BOUNDARY_INVALID:"
            f"{readback.get('snapshot_boundary')}"
        )
    if readback.get("pending_external_decision_present") is not True:
        raise RuntimeError("WS49_NATURAL_START_PENDING_EXTERNAL_DECISION_NOT_PROVEN")

    semantic_state = readback.get("semantic_state")
    if not isinstance(semantic_state, dict):
        raise RuntimeError("WS49_NATURAL_START_NATIVE_SEMANTIC_STATE_MISSING")
    validation = readback.get("native_validation")
    if not isinstance(validation, dict) or validation.get("valid") is not True:
        raise RuntimeError("WS49_NATURAL_START_NATIVE_VALIDATION_NOT_PASS")
    rng_tape = readback.get("rules_rng_tape")
    if not isinstance(rng_tape, dict):
        raise RuntimeError("WS49_NATURAL_START_RULES_RNG_TAPE_MISSING")

    for key in ("execution_entry_mode", "rules_seed", "starting_player_seat", "starting_life", "player_count"):
        if key not in readback:
            raise RuntimeError(f"WS49_NATURAL_START_CONFIGURATION_FIELD_MISSING:{key}")
    if readback["execution_entry_mode"] != mode:
        raise RuntimeError("WS49_NATURAL_START_ENTRY_MODE_MISMATCH")
    if int(readback["player_count"]) != len(record["players"]):
        raise RuntimeError("WS49_NATURAL_START_PLAYER_COUNT_MISMATCH")
    if not 1 <= int(readback["starting_player_seat"]) <= int(readback["player_count"]):
        raise RuntimeError("WS49_NATURAL_START_STARTING_PLAYER_INVALID")
    if int(readback["starting_life"]) <= 0:
        raise RuntimeError("WS49_NATURAL_START_STARTING_LIFE_INVALID")

    seed_evidence = legacy.seed_binding_evidence(record, scenario)
    if int(readback.get("rules_seed", -1)) != int(seed_evidence["scenario_execution_seed"]):
        raise RuntimeError("WS49_NATURAL_START_EXECUTION_SEED_MISMATCH")

    return {
        "evidence_class": "LOWER_LEVEL_NATIVE_READBACK_READY_FOR_INDEPENDENT_NORMALIZATION",
        "ws42_readback_schema": readback["schema_version"],
        "execution_entry_mode": mode,
        "rules_seed": readback["rules_seed"],
        "starting_player_seat": readback["starting_player_seat"],
        "starting_life": readback["starting_life"],
        "player_count": readback["player_count"],
        "snapshot_boundary": readback["snapshot_boundary"],
        "pending_external_decision_present": True,
        "request_object_copied_as_proof": False,
        "legacy_normalized_constructed_state_consumed": False,
        "legacy_declared_digest_consumed": False,
        "seed_binding": seed_evidence,
        "semantic_state": semantic_state,
        "native_validation": validation,
        "rules_rng_tape": rng_tape,
        "construction_credit_granted": False,
    }


def configure_runtime() -> None:
    legacy.canonical_v103 = canonical_v105
    legacy.load_contract = load_contract
    legacy.provider_records = provider_records
    legacy.CURRENT_NATIVE_DIMENSIONS.update(WS49_IMPLEMENTED_NATIVE_DIMENSIONS)
    legacy.capture_non_echo_readback = capture_non_echo_readback_v105
    legacy.required_dimensions = required_dimensions_v105


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()
    if args.max_workers != 1:
        raise SystemExit("WS49_UNQUALIFIED_PARALLEL_XMAGE_PROBE_FORBIDDEN")

    configure_runtime()
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
            f"WS49_V105_ENTRY_MODE_DISTRIBUTION_MISMATCH:expected={EXPECTED_ENTRY_MODE_COUNTS}:observed={entry_mode_counts}"
        )
    if natural_start_fixtures != EXPECTED_NATURAL_START_FIXTURES:
        raise RuntimeError(
            f"WS49_V105_NATURAL_START_IDENTITY_MISMATCH:expected={EXPECTED_NATURAL_START_FIXTURES}:observed={natural_start_fixtures}"
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
        raise RuntimeError("WS49_NATURAL_START_DEFERRED_INSTEAD_OF_EXECUTED")

    output = {
        "schema_version": "commander-lab.ws49-full107-construction-probe/1.0.0",
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.5",
        "candidate_commit": legacy.run_tax3.exact_provider_identity()[0],
        "engine_commit": os.environ.get("XMAGE_WS49_COMMIT", "UNKNOWN"),
        "engine_tree": os.environ.get("XMAGE_WS49_TREE", "UNKNOWN"),
        "denominator": 107,
        "record_count": len(rows),
        "entry_mode_counts": entry_mode_counts,
        "natural_start_fixture_ids": natural_start_fixtures,
        "natural_start_fresh_execution_required": True,
        "natural_start_historical_credit_imported": False,
        "natural_start_snapshot_boundary": NATURAL_START_BOUNDARY,
        "counts": counts,
        "unsupported_dimension_counts": dict(sorted(unsupported_dimension_counts.items())),
        "current_native_dimensions": sorted(legacy.CURRENT_NATIVE_DIMENSIONS),
        "translator": "candidate-qualification/ws49-xmage-v1.0.5/canonical_v105.py",
        "max_workers": 1,
        "parallel_probe_qualified": False,
        "record_order_preserved": [row["fixture_id"] for row in rows] == [record["fixture_id"] for record in records],
        "legacy_request_echo_accepted_as_proof": False,
        "independent_normalized_construction_gate_closed": False,
        "historical_pass_imported": False,
        "historical_successor_runtime_credit": 0,
        "construction_credit_granted": False,
        "behavior_credit_granted": False,
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
