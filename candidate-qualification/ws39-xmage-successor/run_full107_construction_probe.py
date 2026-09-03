#!/usr/bin/env python3
"""Fresh fail-closed construction census against the current WS-39 provider.

This probe is deliberately not a behavior qualification runner. It may prove
native construction for records whose complete requested starting-state surface
is currently implemented and natively validated, but it never grants successor
runtime PASS or imports historical PASS results.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WS34 = HERE.parents[0] / "ws34-xmage-successor"
sys.path[:0] = [str(ROOT / "src"), str(HERE), str(WS34)]

import run_tax3  # noqa: E402
from successor_contract import load_contract, ws34_records  # noqa: E402

BASE_ZONES = {"command", "hand", "library", "graveyard", "exile", "battlefield"}
CURRENT_NATIVE_DIMENSIONS = {
    "face_down",
    "commander_history",
    "zone_position",
    "controlled_since_turn_began",
}


def nonempty(value: Any) -> bool:
    return value not in (None, {}, [], "", False)


def required_dimensions(record: dict[str, Any]) -> set[str]:
    if record["execution_entry_mode"] == "NATURAL_GAME_START":
        return {"natural_game_start"}

    dimensions: set[str] = set()
    temporal = record["temporal_state"]
    phase_step = (temporal["phase"], temporal["step"])
    if phase_step != ("precombat_main", "main"):
        dimensions.add(f"temporal:{phase_step[0]}/{phase_step[1]}")

    objects = record.get("semantic_objects") or []
    for obj in objects:
        zone = obj["zone"]
        if zone not in BASE_ZONES:
            dimensions.add(f"zone:{zone}")
        if obj.get("face_down") is True:
            dimensions.add("face_down")
        if "zone_position" in obj:
            dimensions.add("zone_position")
        if "controlled_since_turn_began" in obj:
            dimensions.add("controlled_since_turn_began")
        if obj.get("controller") != obj.get("owner"):
            dimensions.add("owner_controller_split")
        if nonempty(obj.get("counters")):
            dimensions.add("counters")
        if nonempty(obj.get("attached_to")):
            dimensions.add("attachments")

    if nonempty(record.get("stack_state")):
        dimensions.add("stack_state")
    if nonempty(record.get("combat_state")):
        dimensions.add("combat_state")
    if nonempty(record.get("extra_turn_creation")):
        dimensions.add("extra_turn_creation")
    if nonempty(record.get("elimination_trigger")):
        dimensions.add("elimination_trigger")
    if nonempty(record.get("zone_move_event")):
        dimensions.add("zone_move_event")

    commander_state = record.get("commander_state") or {}
    commanders = commander_state.get("commanders") or []
    if any(int(item.get("prior_command_zone_cast_count", 0)) > 0 for item in commanders):
        dimensions.add("commander_history")
    if nonempty(commander_state.get("commander_damage_matrix")):
        dimensions.add("commander_damage_matrix")
    objects_by_id = {item["semantic_id"]: item for item in objects}
    for commander in commanders:
        object_id = commander.get("object_id")
        if object_id in objects_by_id and objects_by_id[object_id]["zone"] != "command":
            dimensions.add("commander_outside_command_zone")

    knowledge_state = record.get("knowledge_state") or {}
    for viewer in knowledge_state.get("viewer_states") or []:
        if any(
            nonempty(viewer.get(key))
            for key in (
                "face_down_look_permissions",
                "known_library_ranges",
                "known_object_identities",
                "temporary_permissions",
                "invalidation_conditions",
            )
        ):
            dimensions.add("knowledge_grants")
            break

    if any(int(player["life"]) <= 0 for player in record["players"]):
        dimensions.add("nonpositive_life")
    return dimensions


def probe_record(record: dict[str, Any]) -> dict[str, Any]:
    required = required_dimensions(record)
    row: dict[str, Any] = {
        "fixture_id": record["fixture_id"],
        "fixture_family": record["fixture_family"],
        "record_digest": record["materialization_digest"],
        "requested_state_digest": record["requested_state_digest"],
        "required_dimensions": sorted(required),
        "runtime_credit": "NONE",
        "historical_pass_imported": False,
    }
    if required == {"natural_game_start"}:
        row.update(
            {
                "construction_status": "DEFERRED_TO_FRESH_NATURAL_EXECUTOR",
                "native_setup_ready": True,
                "behavior_runtime_executed": False,
            }
        )
        return row

    unsupported = sorted(required - CURRENT_NATIVE_DIMENSIONS)
    if unsupported:
        row.update(
            {
                "construction_status": "FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION",
                "native_setup_ready": False,
                "unsupported_dimensions": unsupported,
                "behavior_runtime_executed": False,
            }
        )
        return row

    client = None
    try:
        client, _scenario, state = run_tax3.start_fixture(record)
        proof = run_tax3.assert_construction(record, state)
        row.update(
            {
                "construction_status": "NATIVE_SETUP_PASS_NO_RUNTIME_CREDIT",
                "native_setup_ready": True,
                "behavior_runtime_executed": False,
                "construction_proof": proof,
            }
        )
    except Exception as exc:
        row.update(
            {
                "construction_status": "FAIL_CLOSED_NATIVE_CONSTRUCTION",
                "native_setup_ready": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "behavior_runtime_executed": False,
            }
        )
    finally:
        if client is not None:
            client.__exit__(None, None, None)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = ws34_records(contract)
    rows = [probe_record(record) for record in records]
    counts: dict[str, int] = {}
    for row in rows:
        status = row["construction_status"]
        counts[status] = counts.get(status, 0) + 1

    output = {
        "schema_version": "commander-lab.ws39-full107-construction-probe/1.0.0",
        "candidate_commit": run_tax3.exact_provider_identity()[0],
        "engine_commit": os.environ.get("XMAGE_WS39_COMMIT", "UNKNOWN"),
        "denominator": 107,
        "record_count": len(rows),
        "counts": counts,
        "current_native_dimensions": sorted(CURRENT_NATIVE_DIMENSIONS),
        "historical_pass_imported": False,
        "runtime_credit_granted": False,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(counts, sort_keys=True))
    if len(rows) != 107:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
