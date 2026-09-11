#!/usr/bin/env python3
"""Lock and classify the exact WS-39 WS-32-v1.0.2 107-record denominator.

This is census/planning evidence only. It deliberately grants zero runtime
credit and imports no historical PASS results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.2"
EXPECTED_FILE_SHA = "0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261"
EXPECTED_BUNDLE = "ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23"
EXPECTED_DENOMINATOR = 107
EXPECTED_FAMILIES = {
    "player_count": 4,
    "pilot_boundary": 17,
    "pilot_boundary_negative": 7,
    "hidden_information": 20,
    "replay_rng": 5,
    "micro_rules": 17,
    "actual_card": 1,
    "multiplayer_commander": 36,
}


def nonempty(value: Any) -> bool:
    return value not in (None, {}, [], "", False)


def special_dimensions(record: dict[str, Any]) -> list[str]:
    dimensions: list[str] = []
    for key in (
        "stack_state",
        "combat_state",
        "extra_turn_creation",
        "elimination_trigger",
        "zone_move_event",
    ):
        if nonempty(record.get(key)):
            dimensions.append(key)

    commander_state = record.get("commander_state") or {}
    if nonempty(commander_state.get("commander_damage_matrix")):
        dimensions.append("commander_damage_matrix")
    if any(
        int(commander.get("prior_command_zone_cast_count", 0)) > 0
        for commander in commander_state.get("commanders") or []
    ):
        dimensions.append("commander_history")

    objects = record.get("semantic_objects") or []
    if any(obj.get("controller") != obj.get("owner") for obj in objects):
        dimensions.append("owner_controller_split")
    if any(nonempty(obj.get("counters")) for obj in objects):
        dimensions.append("counters")
    if any(nonempty(obj.get("attached_to")) for obj in objects):
        dimensions.append("attachments")
    if any(obj.get("face_down") is True for obj in objects):
        dimensions.append("face_down")
    if any("zone_position" in obj for obj in objects):
        dimensions.append("zone_position")
    if any("controlled_since_turn_began" in obj for obj in objects):
        dimensions.append("controlled_since_turn_began")

    commander_objects = {
        commander.get("object_id")
        for commander in commander_state.get("commanders") or []
        if commander.get("object_id")
    }
    objects_by_id = {obj.get("semantic_id"): obj for obj in objects}
    if any(
        objects_by_id.get(object_id, {}).get("zone") != "command"
        for object_id in commander_objects
        if object_id in objects_by_id
    ):
        dimensions.append("commander_outside_command_zone")
    return sorted(set(dimensions))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.contract.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    if file_sha != EXPECTED_FILE_SHA:
        raise SystemExit(f"WS32_FILE_SHA_MISMATCH:{file_sha}")
    contract = json.loads(raw)
    if contract.get("schema_version") != SCHEMA:
        raise SystemExit("WS32_SCHEMA_MISMATCH")
    if contract.get("canonical_bundle_digest") != EXPECTED_BUNDLE:
        raise SystemExit("WS32_BUNDLE_MISMATCH")

    records = [
        record
        for record in contract["records"]
        if record.get("fixture_family") != "actual_card" or record.get("fixture_id") == "CARD_02"
    ]
    if len(records) != EXPECTED_DENOMINATOR or len(
        {record["fixture_id"] for record in records}
    ) != EXPECTED_DENOMINATOR:
        raise SystemExit("WS39_DENOMINATOR_MISMATCH")

    family_counts = Counter(record["fixture_family"] for record in records)
    if dict(family_counts) != EXPECTED_FAMILIES:
        raise SystemExit(f"WS39_FAMILY_COUNTS_MISMATCH:{dict(family_counts)}")

    operation_counts: Counter[str] = Counter()
    operation_sets: defaultdict[tuple[str, ...], list[str]] = defaultdict(list)
    dimension_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for record in records:
        operations = [step["operation"] for step in record.get("native_procedure") or []]
        operation_counts.update(operations)
        operation_sets[tuple(operations)].append(record["fixture_id"])
        dimensions = special_dimensions(record)
        dimension_counts.update(dimensions)
        rows.append(
            {
                "fixture_id": record["fixture_id"],
                "fixture_family": record["fixture_family"],
                "materialization_digest": record["materialization_digest"],
                "requested_state_digest": record["requested_state_digest"],
                "execution_entry_mode": record["execution_entry_mode"],
                "native_operations": operations,
                "special_dimensions": dimensions,
                "decision_families": [
                    decision["decision_family"] for decision in (record.get("decision_script") or [])
                ],
                "terminal_postcondition_count": len(record.get("terminal_postconditions") or []),
            }
        )

    groups = []
    for index, (operations, fixture_ids) in enumerate(
        sorted(operation_sets.items(), key=lambda item: (-len(item[1]), item[1][0])), 1
    ):
        groups.append(
            {
                "operation_set_id": f"OPS-{index:02d}",
                "record_count": len(fixture_ids),
                "fixture_ids": fixture_ids,
                "operations": list(operations),
            }
        )

    output = {
        "schema_version": "commander-lab.ws39-full107-census/1.0.0",
        "contract_schema": SCHEMA,
        "contract_file_sha256": file_sha,
        "contract_bundle_digest": EXPECTED_BUNDLE,
        "denominator": len(records),
        "unique_fixture_ids": len({record["fixture_id"] for record in records}),
        "family_counts": dict(sorted(family_counts.items())),
        "unique_native_operation_names": len(operation_counts),
        "native_operation_counts": dict(sorted(operation_counts.items())),
        "unique_ordered_operation_sets": len(operation_sets),
        "operation_sets": groups,
        "special_dimension_record_counts": dict(sorted(dimension_counts.items())),
        "historical_pass_imported": False,
        "runtime_credit_granted": False,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "denominator": len(records),
                "operation_names": len(operation_counts),
                "operation_sets": len(operation_sets),
                "runtime_credit_granted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
