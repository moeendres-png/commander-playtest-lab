#!/usr/bin/env python3
"""Build the fail-closed WS-34 v1.0.2 native-construction and decision reachability ledger."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from successor_contract import (
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    FREEZE_BUNDLE_DIGEST,
    FREEZE_COMMIT,
    FREEZE_TREE,
    MATERIALIZATION_FILE_SHA256,
    VALIDATION_MARKER_COMMIT,
    VALIDATION_RUN_ID,
    XMAGE_COMMIT,
    XMAGE_TREE,
    load_contract,
    ws34_records,
)

SUPPORTED_ZONES = {"command", "hand", "library", "graveyard", "exile", "battlefield"}
SOURCE_SUPPORTED_DECISIONS = {
    "priority", "target", "target_amount", "mulligan", "choose_use", "choice", "pile",
    "mana_payment", "announce_x", "replacement_effect", "trigger_order", "choose_mode",
    "declare_attacker", "declare_blocker", "amount", "multi_amount",
}
NATURAL_IDS = {
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN", "WS05-CMD-MULL-2", "WS05-CMD-MULL-4",
}


def nonempty(value: Any) -> bool:
    return value not in (None, [], {}, "")


def knowledge_requires_injection(record: dict[str, Any]) -> bool:
    state = record.get("knowledge_state") or {}
    for viewer in state.get("viewer_states", []):
        for key in (
            "face_down_look_permissions", "known_library_ranges", "known_object_identities",
            "temporary_permissions", "invalidation_conditions",
        ):
            if nonempty(viewer.get(key)):
                return True
    return False


def construction_blockers(record: dict[str, Any]) -> list[str]:
    if record["execution_entry_mode"] == "NATURAL_GAME_START":
        return [] if record["fixture_id"] in NATURAL_IDS else ["UNKNOWN_NATURAL_START_RECORD"]

    blockers: list[str] = []
    temporal = record.get("temporal_state") or {}
    if temporal.get("phase") != "precombat_main" or temporal.get("step") != "main":
        blockers.append("UNSUPPORTED_TEMPORAL_PHASE_STEP")
    if nonempty(record.get("combat_state")):
        blockers.append("UNSUPPORTED_INITIAL_COMBAT_STATE")
    if nonempty(record.get("stack_state")):
        blockers.append("UNSUPPORTED_INITIAL_STACK_STATE")
    if nonempty(record.get("extra_turn_creation")):
        blockers.append("UNSUPPORTED_EXTRA_TURN_CONSTRUCTION")
    if nonempty(record.get("elimination_trigger")):
        blockers.append("UNSUPPORTED_ELIMINATION_CONSTRUCTION")
    if nonempty(record.get("zone_move_event")):
        blockers.append("UNSUPPORTED_ZONE_MOVE_EVENT_CONSTRUCTION")
    if knowledge_requires_injection(record):
        blockers.append("UNSUPPORTED_DIRECT_KNOWLEDGE_GRANT_CONSTRUCTION")

    for obj in record.get("semantic_objects", []):
        zone = obj.get("zone")
        if zone not in SUPPORTED_ZONES:
            blockers.append(f"UNSUPPORTED_ZONE:{zone}")
        if obj.get("controller") != obj.get("owner"):
            blockers.append("UNSUPPORTED_OWNER_CONTROLLER_SPLIT")
        if nonempty(obj.get("counters")):
            blockers.append("UNSUPPORTED_COUNTERS")
        if nonempty(obj.get("attached_to")):
            blockers.append("UNSUPPORTED_ATTACHMENTS")
        if obj.get("face_down") is True:
            blockers.append("FACE_DOWN_REQUIRES_QUALIFICATION_OVERLAY")

    commander_state = record.get("commander_state") or {}
    if nonempty(commander_state.get("commander_damage_matrix")):
        blockers.append("UNSUPPORTED_COMMANDER_DAMAGE_CONSTRUCTION")
    if nonempty(commander_state.get("multiple_commander_relations")):
        blockers.append("UNSUPPORTED_MULTIPLE_COMMANDER_RELATION_CONSTRUCTION")
    for commander in commander_state.get("commanders", []):
        if commander.get("zone") != "command":
            blockers.append("UNSUPPORTED_CURRENT_COMMANDER_ZONE")
        if int(commander.get("prior_command_zone_cast_count", 0)) != 0:
            blockers.append("UNSUPPORTED_PRIOR_COMMAND_ZONE_CAST_COUNT")

    return sorted(set(blockers))


def decision_families(record: dict[str, Any]) -> list[str]:
    rows = []
    for decision in record.get("decision_script", []):
        family = decision.get("decision_family")
        if isinstance(family, str):
            rows.append(family)
    return sorted(set(rows))


def decision_blockers(record: dict[str, Any]) -> list[str]:
    return [
        f"UNSUPPORTED_DECISION_FAMILY:{family}"
        for family in decision_families(record)
        if family not in SOURCE_SUPPORTED_DECISIONS
    ]


def classify(record: dict[str, Any]) -> dict[str, Any]:
    construction = construction_blockers(record)
    decisions = decision_blockers(record)
    if construction:
        status = "CANONICAL_SETUP_UNSUPPORTED_XMAGE"
    elif decisions:
        status = "XMAGE_PROVIDER_DECISION_UNSUPPORTED"
    else:
        status = "READY_FOR_EXACT_RUNTIME_QUALIFICATION"
    return {
        "fixture_id": record["fixture_id"],
        "fixture_family": record["fixture_family"],
        "materialization_digest": record["materialization_digest"],
        "requested_state_digest": record["requested_state_digest"],
        "execution_entry_mode": record["execution_entry_mode"],
        "decision_families": decision_families(record),
        "construction_blockers": construction,
        "decision_blockers": decisions,
        "pre_runtime_status": status,
        "successor_runtime_credit": "NOT_RUN",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = ws34_records(contract)
    rows = [classify(record) for record in records]
    counts = Counter(row["pre_runtime_status"] for row in rows)
    entry = Counter(row["execution_entry_mode"] for row in rows)
    blocker_counts = Counter(
        blocker for row in rows for blocker in row["construction_blockers"] + row["decision_blockers"]
    )
    value = {
        "schema_version": "commander-lab.ws34-xmage-successor-ledger/1.0.0",
        "contract_version": CONTRACT_VERSION,
        "canonical_materialization_digest": CANONICAL_MATERIALIZATION_DIGEST,
        "materialization_file_sha256": MATERIALIZATION_FILE_SHA256,
        "ws32_freeze_bundle_digest": FREEZE_BUNDLE_DIGEST,
        "ws32_freeze_commit": FREEZE_COMMIT,
        "ws32_freeze_tree": FREEZE_TREE,
        "ws32_validation_marker_commit": VALIDATION_MARKER_COMMIT,
        "ws32_validation_run_id": VALIDATION_RUN_ID,
        "xmage_commit": XMAGE_COMMIT,
        "xmage_tree": XMAGE_TREE,
        "ws34_denominator": len(rows),
        "entry_mode_counts": dict(sorted(entry.items())),
        "pre_runtime_counts": dict(sorted(counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "credit_policy": {
            "not_run_is_not_pass": True,
            "source_supported_is_not_runtime_verified": True,
            "requested_state_digest_must_equal_constructed_state_digest": True,
            "native_legal_options_required": True,
            "actor_safe_observation_required": True,
            "one_active_game_per_engine_process": True,
        },
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "ws34_denominator": len(rows),
        "entry_mode_counts": value["entry_mode_counts"],
        "pre_runtime_counts": value["pre_runtime_counts"],
        "blocker_counts": value["blocker_counts"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
