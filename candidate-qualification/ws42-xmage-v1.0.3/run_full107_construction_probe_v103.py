#!/usr/bin/env python3
"""Fresh fail-closed construction census for WS-42 v1.0.3.

This is construction diagnostics only. It grants no behavior/runtime PASS and
imports no historical successor PASS. In particular, it deliberately ignores
the inherited WS-34 ``normalized_constructed_state`` request echo and records
only lower-level native readback/validation for subsequent independent
normalization.
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
WS39 = HERE.parents[0] / "ws39-xmage-successor"
WS34 = HERE.parents[0] / "ws34-xmage-successor"
sys.path[:0] = [str(ROOT / "src"), str(HERE), str(WS39), str(WS34)]

import canonical_v103  # noqa: E402
import run_tax3  # noqa: E402
from successor_contract_v103 import load_contract, provider_records  # noqa: E402

BASE_ZONES = {"command", "hand", "library", "graveyard", "exile", "battlefield"}
CURRENT_NATIVE_DIMENSIONS = {
    "face_down",
    "commander_history",
    "zone_position",
    "controlled_since_turn_began",
    "stack_state",
    "zone:stack",
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


def start_fixture_v103(record: dict[str, Any]):
    """Start exactly one record using the WS-42 v1.0.3 translator, never WS-39 v1.0.2."""
    decks, scenario = canonical_v103.deck_and_scenario(record)
    client = run_tax3.gate._RawFullGameClient(run_tax3.gate.command(), request_timeout_seconds=240.0)
    client.__enter__()
    try:
        client.request("start_engine")
        handles = run_tax3.gate.import_decks(client, decks)
        starting_lives = {int(player["starting_life"]) for player in record["players"]}
        if len(starting_lives) != 1:
            raise RuntimeError(f"WS42_NONUNIFORM_STARTING_LIFE_UNSUPPORTED:{sorted(starting_lives)}")
        client.request(
            "create_full_game",
            {
                "game_id": f"WS42-V103-{record['fixture_id']}",
                "deck_handles": handles,
                "starting_player_seat": int(scenario["starting_player_seat"]) - 1,
                "starting_life": next(iter(starting_lives)),
                "seed": int(scenario["seed"]),
            },
        )
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        if configured.get("execution_entry_mode") != record["execution_entry_mode"]:
            raise RuntimeError("WS42_CONFIGURED_ENTRY_MODE_MISMATCH")
        client.request("start_full_game")
        state = client.request("get_qualification_state")
        return client, scenario, state
    except Exception:
        client.__exit__(*sys.exc_info())
        raise


def capture_non_echo_readback(record: dict[str, Any], scenario: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Capture only independent lower-level provider/native evidence.

    The inherited top-level normalized_constructed_state and declared digest are
    intentionally not consumed. Native validation is accepted here only as a
    diagnostic lower-level query result; this function does not grant the exact
    requested-vs-normalized construction gate.
    """
    semantic_state = state.get("semantic_state")
    if not isinstance(semantic_state, dict):
        raise RuntimeError("WS42_NATIVE_SEMANTIC_STATE_MISSING")
    validation = state.get("normalized_constructed_state_native_validation")
    if not isinstance(validation, dict) or validation.get("valid") is not True:
        raise RuntimeError("WS42_LOWER_LEVEL_NATIVE_VALIDATION_NOT_PASS")
    rng_tape = state.get("rules_rng_tape")
    if not isinstance(rng_tape, dict):
        raise RuntimeError("WS42_RULES_RNG_TAPE_MISSING")
    if int(scenario["seed"]) != int(record["rules_randomness"]["rules_seed"]):
        raise RuntimeError("WS42_SCENARIO_RULES_SEED_NOT_IMMUTABLE_CONTRACT_SEED")

    return {
        "evidence_class": "LOWER_LEVEL_NATIVE_READBACK_AWAITING_INDEPENDENT_NORMALIZATION",
        "legacy_normalized_constructed_state_present_but_ignored": isinstance(
            state.get("normalized_constructed_state"), dict
        ),
        "legacy_declared_digest_present_but_ignored": isinstance(
            state.get("normalized_constructed_state_declared_digest"), str
        ),
        "scenario_execution_seed": int(scenario["seed"]),
        "contract_rules_seed": int(record["rules_randomness"]["rules_seed"]),
        "semantic_state": semantic_state,
        "native_validation": validation,
        "rules_rng_tape": rng_tape,
        "construction_credit_granted": False,
    }


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
        row.update({
            "construction_status": "DEFERRED_TO_FRESH_NATURAL_EXECUTOR",
            "native_setup_ready": True,
            "behavior_runtime_executed": False,
        })
        return row

    unsupported = sorted(required - CURRENT_NATIVE_DIMENSIONS)
    if unsupported:
        row.update({
            "construction_status": "FAIL_CLOSED_UNSUPPORTED_NATIVE_DIMENSION",
            "native_setup_ready": False,
            "unsupported_dimensions": unsupported,
            "behavior_runtime_executed": False,
        })
        return row

    client = None
    try:
        client, scenario, state = start_fixture_v103(record)
        readback = capture_non_echo_readback(record, scenario, state)
        row.update({
            "construction_status": "NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION",
            "native_setup_ready": True,
            "behavior_runtime_executed": False,
            "non_echo_native_readback": readback,
        })
    except Exception as exc:
        row.update({
            "construction_status": "FAIL_CLOSED_NATIVE_CONSTRUCTION",
            "native_setup_ready": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "behavior_runtime_executed": False,
        })
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
    records = provider_records(contract)
    rows = [probe_record(record) for record in records]
    counts: dict[str, int] = {}
    unsupported_dimension_counts: dict[str, int] = {}
    for row in rows:
        status = row["construction_status"]
        counts[status] = counts.get(status, 0) + 1
        for dimension in row.get("unsupported_dimensions") or []:
            unsupported_dimension_counts[dimension] = unsupported_dimension_counts.get(dimension, 0) + 1

    output = {
        "schema_version": "commander-lab.ws42-full107-construction-probe/1.1.0",
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.3",
        "candidate_commit": run_tax3.exact_provider_identity()[0],
        "engine_commit": os.environ.get("XMAGE_WS42_COMMIT", "UNKNOWN"),
        "denominator": 107,
        "record_count": len(rows),
        "counts": counts,
        "unsupported_dimension_counts": dict(sorted(unsupported_dimension_counts.items())),
        "current_native_dimensions": sorted(CURRENT_NATIVE_DIMENSIONS),
        "translator": "candidate-qualification/ws42-xmage-v1.0.3/canonical_v103.py",
        "legacy_request_echo_accepted_as_proof": False,
        "independent_normalized_construction_gate_closed": False,
        "historical_pass_imported": False,
        "runtime_credit_granted": False,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "unsupported_dimension_counts": output["unsupported_dimension_counts"]}, sort_keys=True))
    if len(rows) != 107:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
