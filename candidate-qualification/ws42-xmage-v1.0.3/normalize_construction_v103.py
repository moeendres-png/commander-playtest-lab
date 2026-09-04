#!/usr/bin/env python3
"""Independently normalize WS42 XMage construction evidence against WS41 v1.0.3.

The normalizer is deliberately field-by-field. It never copies the complete
requested state and never consumes the inherited WS34 normalized-state echo or
its declared digest. Mutable/native state comes from the WS42 provider readback.
Only explicitly allowlisted semantic identity, descriptive and qualification
policy metadata is carried from the immutable contract, and those fields are
recorded as metadata rather than Rules-Core proof.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from successor_contract_v103 import (  # noqa: E402
    canonical_sha,
    load_contract,
    provider_records,
    requested_state_projection,
)

ADMITTED_PROBE_STATUS = "NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION"
PASS_STATUS = "PASS_INDEPENDENT_NORMALIZATION"
BASE_STATE_KEYS = {
    "execution_entry_mode",
    "players",
    "commander_state",
    "semantic_objects",
    "temporal_state",
    "knowledge_state",
    "rules_randomness",
    "stack_state",
    "setup_validation",
}
DYNAMIC_KNOWLEDGE_KEYS = {
    "face_down_look_permissions",
    "known_library_ranges",
    "known_object_identities",
    "temporary_permissions",
    "invalidation_conditions",
    "ordered_known_information",
}
SEMANTIC_OBJECT_METADATA_KEYS = {
    "semantic_id",
    "card_lineage_id",
    "commander_id",
    "construction_notes",
}
KNOWLEDGE_METADATA_KEYS = {
    "viewer",
    "channels_under_test",
    "honey_sentinels",
    "obligation",
    "permitted_public_metadata",
    "prohibited_metadata",
}
RNG_POLICY_METADATA_KEYS = {
    "channels",
    "pilot_randomness_prohibited",
    "seed_binding",
}


def fail(code: str, fixture_id: str, detail: Any = None) -> None:
    suffix = "" if detail is None else ":" + json.dumps(detail, sort_keys=True, ensure_ascii=False)
    raise RuntimeError(f"{code}:{fixture_id}{suffix}")


def actor_views(readback: dict[str, Any], fixture_id: str) -> dict[str, dict[str, Any]]:
    semantic = readback.get("semantic_state")
    if not isinstance(semantic, dict):
        fail("WS42_NORMALIZE_SEMANTIC_STATE_MISSING", fixture_id)
    raw = semantic.get("actor_entitled_union")
    if not isinstance(raw, list) or not raw:
        fail("WS42_NORMALIZE_ACTOR_VIEWS_MISSING", fixture_id)
    views: dict[str, dict[str, Any]] = {}
    for view in raw:
        if not isinstance(view, dict):
            fail("WS42_NORMALIZE_ACTOR_VIEW_INVALID", fixture_id)
        viewer = view.get("viewer_player_id")
        if not isinstance(viewer, str) or viewer in views:
            fail("WS42_NORMALIZE_ACTOR_VIEWER_INVALID", fixture_id, viewer)
        views[viewer] = view
    return views


def public_player_state(views: dict[str, dict[str, Any]], fixture_id: str) -> dict[str, dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] | None = None
    for viewer, view in sorted(views.items()):
        players = view.get("players")
        if not isinstance(players, list):
            fail("WS42_NORMALIZE_PLAYERS_MISSING", fixture_id, viewer)
        current: dict[str, dict[str, Any]] = {}
        for player in players:
            if not isinstance(player, dict) or not isinstance(player.get("player_id"), str):
                fail("WS42_NORMALIZE_PLAYER_INVALID", fixture_id, viewer)
            pid = player["player_id"]
            current[pid] = {
                "player_id": pid,
                "life": player.get("life"),
                "poison_counters": player.get("poison_counters"),
                "has_lost": player.get("has_lost"),
                "has_left": player.get("has_left"),
            }
        if canonical is None:
            canonical = current
        elif current != canonical:
            fail("WS42_NORMALIZE_PUBLIC_PLAYER_DISAGREEMENT", fixture_id, viewer)
    if canonical is None:
        fail("WS42_NORMALIZE_PUBLIC_PLAYER_EMPTY", fixture_id)
    return canonical


def normalize_players(record: dict[str, Any], readback: dict[str, Any]) -> list[dict[str, Any]]:
    fixture_id = record["fixture_id"]
    views = actor_views(readback, fixture_id)
    native = public_player_state(views, fixture_id)
    count = int(readback.get("player_count", -1))
    if count != len(record["players"]) or len(native) != count:
        fail("WS42_NORMALIZE_PLAYER_COUNT_MISMATCH", fixture_id, {"native": len(native), "readback": count})
    starting_life = int(readback.get("starting_life", -1))
    if starting_life <= 0:
        fail("WS42_NORMALIZE_STARTING_LIFE_INVALID", fixture_id, starting_life)

    rows: list[dict[str, Any]] = []
    for seat in range(1, count + 1):
        pid = f"P{seat}"
        player = native.get(pid)
        if player is None:
            fail("WS42_NORMALIZE_PLAYER_ID_MISSING", fixture_id, pid)
        rows.append(
            {
                "player_id": pid,
                "seat": seat,
                "starting_life": starting_life,
                "life": int(player["life"]),
                "poison": int(player["poison_counters"]),
                "lost": bool(player["has_lost"]),
                "eliminated": bool(player["has_left"]),
            }
        )
    return rows


def native_scenario_objects(readback: dict[str, Any], fixture_id: str) -> dict[str, dict[str, Any]]:
    semantic = readback["semantic_state"]
    raw = semantic.get("scenario_objects")
    if not isinstance(raw, list):
        fail("WS42_NORMALIZE_SCENARIO_OBJECTS_MISSING", fixture_id)
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        sid = item.get("semantic_id") if isinstance(item, dict) else None
        if not isinstance(sid, str) or sid in result:
            fail("WS42_NORMALIZE_SCENARIO_OBJECT_ID_INVALID", fixture_id, sid)
        result[sid] = item
    return result


def native_commander_history(readback: dict[str, Any], fixture_id: str) -> dict[str, dict[str, Any]]:
    validation = readback.get("native_validation")
    history = validation.get("commander_history") if isinstance(validation, dict) else None
    raw = history.get("commanders") if isinstance(history, dict) else None
    if not isinstance(raw, list) or history.get("valid") is not True:
        fail("WS42_NORMALIZE_COMMANDER_HISTORY_MISSING", fixture_id)
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        cid = item.get("commander_id") if isinstance(item, dict) else None
        if not isinstance(cid, str) or cid in result:
            fail("WS42_NORMALIZE_COMMANDER_ID_INVALID", fixture_id, cid)
        result[cid] = item
    return result


def command_names_by_player(readback: dict[str, Any], fixture_id: str) -> dict[str, list[str]]:
    views = actor_views(readback, fixture_id)
    baseline: dict[str, list[str]] | None = None
    for viewer, view in sorted(views.items()):
        current: dict[str, list[str]] = {}
        for player in view.get("players") or []:
            pid = player.get("player_id")
            if not isinstance(pid, str):
                fail("WS42_NORMALIZE_COMMAND_PLAYER_INVALID", fixture_id, viewer)
            command = player.get("command") or []
            names = sorted(str(card.get("name")) for card in command if isinstance(card, dict) and card.get("name"))
            current[pid] = names
        if baseline is None:
            baseline = current
        elif current != baseline:
            fail("WS42_NORMALIZE_COMMAND_VIEW_DISAGREEMENT", fixture_id, viewer)
    return baseline or {}


def contract_commander_object_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in record["semantic_objects"]:
        cid = item.get("commander_id")
        if cid is not None:
            if cid in result:
                fail("WS42_NORMALIZE_DUPLICATE_COMMANDER_OBJECT", record["fixture_id"], cid)
            result[cid] = item
    return result


def normalize_commander_state(record: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    history = native_commander_history(readback, fixture_id)
    objects = native_scenario_objects(readback, fixture_id)
    command_names = command_names_by_player(readback, fixture_id)
    contract_objects = contract_commander_object_map(record)

    commanders: list[dict[str, Any]] = []
    for metadata in record["commander_state"]["commanders"]:
        cid = metadata.get("commander_id")
        native_history = history.get(cid)
        if native_history is None:
            fail("WS42_NORMALIZE_COMMANDER_HISTORY_ID_MISSING", fixture_id, cid)
        semantic_object = contract_objects.get(cid)
        native_object = None if semantic_object is None else objects.get(semantic_object["semantic_id"])
        history_owner = f"P{int(native_history['seat'])}"

        if native_object is not None:
            zone = "exile" if native_object.get("zone") == "exiled" else native_object.get("zone")
            identity = native_object.get("card_name")
            owner = f"P{int(native_object['owner_seat'])}"
        else:
            native_names = command_names.get(history_owner, [])
            identity = native_history.get("card_name")
            if identity not in native_names:
                fail(
                    "WS42_NORMALIZE_COMMANDER_NOT_NATIVE_COMMAND_OR_OBJECT",
                    fixture_id,
                    {"commander_id": cid, "identity": identity, "command": native_names},
                )
            zone = "command"
            owner = history_owner

        row = {
            "card_identity": identity,
            "commander_id": cid,
            "owner": owner,
            "prior_command_zone_cast_count": int(native_history["prior_command_zone_cast_count"]),
            "zone": zone,
        }
        if "partner_with" in metadata:
            partner = metadata["partner_with"]
            if partner not in history:
                fail("WS42_NORMALIZE_PARTNER_NATIVE_ID_MISSING", fixture_id, partner)
            # partner_with is immutable semantic relationship metadata. Presence
            # of both native commander identities is checked here; partner rules
            # behavior receives no credit from construction normalization.
            row["partner_with"] = partner
        commanders.append(row)

    relations: list[dict[str, Any]] = []
    for metadata in record["commander_state"]["multiple_commander_relations"]:
        ids = metadata.get("commander_ids")
        if not isinstance(ids, list) or any(cid not in history for cid in ids):
            fail("WS42_NORMALIZE_RELATION_NATIVE_ID_MISSING", fixture_id, ids)
        relations.append(
            {
                "commander_ids": list(ids),
                "relation": metadata.get("relation"),
            }
        )

    # BASE53 admits no commander-damage history. Empty is an independently
    # constructed clean-process default, never copied from the requested array.
    if record["commander_state"].get("commander_damage_matrix") != []:
        fail("WS42_NORMALIZE_NONEMPTY_COMMANDER_DAMAGE_NOT_ADMITTED", fixture_id)
    return {
        "commander_damage_matrix": [],
        "commanders": commanders,
        "multiple_commander_relations": relations,
    }


def normalize_semantic_objects(record: dict[str, Any], readback: dict[str, Any]) -> list[dict[str, Any]]:
    fixture_id = record["fixture_id"]
    native = native_scenario_objects(readback, fixture_id)
    history = native_commander_history(readback, fixture_id)
    validation = readback["native_validation"]
    stack_validation = validation.get("stack_state")
    if not isinstance(stack_validation, dict) or stack_validation.get("valid") is not True:
        fail("WS42_NORMALIZE_STACK_VALIDATION_MISSING", fixture_id)
    stack_by_source: dict[str, dict[str, Any]] = {}
    for item in stack_validation.get("objects_top_to_bottom") or []:
        sid = item.get("source_semantic_id")
        if not isinstance(sid, str) or sid in stack_by_source:
            fail("WS42_NORMALIZE_STACK_SOURCE_INVALID", fixture_id, sid)
        stack_by_source[sid] = item

    result: list[dict[str, Any]] = []
    for metadata in record["semantic_objects"]:
        unknown_metadata = set(metadata) - (
            SEMANTIC_OBJECT_METADATA_KEYS
            | {
                "card_identity",
                "owner",
                "controller",
                "zone",
                "tapped",
                "counters",
                "face_down",
                "controlled_since_turn_began",
                "zone_position",
            }
        )
        if unknown_metadata:
            fail("WS42_NORMALIZE_OBJECT_FIELD_UNCLASSIFIED", fixture_id, sorted(unknown_metadata))

        sid = metadata["semantic_id"]
        row: dict[str, Any] = {"semantic_id": sid}
        for key in ("card_lineage_id", "commander_id", "construction_notes"):
            if key in metadata:
                row[key] = copy.deepcopy(metadata[key])

        native_object = native.get(sid)
        if native_object is None:
            commander_id = metadata.get("commander_id")
            native_history = history.get(commander_id) if commander_id is not None else None
            if native_history is None:
                fail("WS42_NORMALIZE_NATIVE_OBJECT_MISSING", fixture_id, sid)
            owner = f"P{int(native_history['seat'])}"
            row.update(
                {
                    "card_identity": native_history["card_name"],
                    "controller": owner,
                    "counters": {},
                    "face_down": False,
                    "owner": owner,
                    "tapped": False,
                    "zone": "command",
                }
            )
        else:
            native_zone = native_object.get("zone")
            zone = "exile" if native_zone == "exiled" else native_zone
            owner = f"P{int(native_object['owner_seat'])}"
            row["card_identity"] = native_object.get("card_name")
            row["owner"] = owner
            row["zone"] = zone
            if zone == "battlefield":
                if "controller_seat" not in native_object or "tapped" not in native_object:
                    fail("WS42_NORMALIZE_PERMANENT_READBACK_INCOMPLETE", fixture_id, sid)
                row["controller"] = f"P{int(native_object['controller_seat'])}"
                row["tapped"] = bool(native_object["tapped"])
                row["counters"] = copy.deepcopy(native_object.get("counters") or {})
                row["face_down"] = bool(native_object.get("face_down", False))
            elif zone == "stack":
                stack = stack_by_source.get(sid)
                if stack is None:
                    fail("WS42_NORMALIZE_STACK_OBJECT_NOT_VALIDATED", fixture_id, sid)
                row["controller"] = stack["controller"]
                row["tapped"] = False
                row["counters"] = {}
                row["face_down"] = False
            else:
                # For cards outside the battlefield/stack, the contract's
                # normalized controller is the owner. This is a provider-neutral
                # normalization convention, not a Magic legality decision.
                row["controller"] = owner
                row["tapped"] = False
                row["counters"] = {}
                row["face_down"] = False

            if "controlled_since_turn_began" in metadata:
                if "controlled_since_turn_began" not in native_object:
                    fail("WS42_NORMALIZE_CONTROLLED_SINCE_MISSING", fixture_id, sid)
                row["controlled_since_turn_began"] = bool(native_object["controlled_since_turn_began"])
            if "zone_position" in metadata:
                if "zone_position" not in native_object:
                    fail("WS42_NORMALIZE_ZONE_POSITION_MISSING", fixture_id, sid)
                row["zone_position"] = int(native_object["zone_position"])

        result.append(row)
    return result


def normalize_temporal_state(record: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    validation = readback.get("native_validation")
    temporal = validation.get("temporal_state") if isinstance(validation, dict) else None
    if not isinstance(temporal, dict) or temporal.get("valid") is not True:
        fail("WS42_NORMALIZE_TEMPORAL_VALIDATION_MISSING", fixture_id)
    if record["temporal_state"].get("extra_turn_queue") != []:
        fail("WS42_NORMALIZE_EXTRA_TURN_QUEUE_NOT_ADMITTED", fixture_id)
    return {
        "active_player": temporal["active_player"],
        "extra_turn_queue": [],
        "phase": temporal["phase"],
        "priority_player": temporal["priority_player"],
        "step": temporal["step"],
        "turn_number": int(temporal["turn_number"]),
    }


def normalize_knowledge_state(record: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    views = actor_views(readback, fixture_id)
    result = {
        "channel_policy": record["knowledge_state"]["channel_policy"],
        "viewer_states": [],
    }
    for metadata in record["knowledge_state"]["viewer_states"]:
        viewer = metadata.get("viewer")
        if viewer not in views:
            fail("WS42_NORMALIZE_KNOWLEDGE_VIEWER_MISSING", fixture_id, viewer)
        unknown = set(metadata) - DYNAMIC_KNOWLEDGE_KEYS - KNOWLEDGE_METADATA_KEYS
        if unknown:
            fail("WS42_NORMALIZE_KNOWLEDGE_FIELD_UNCLASSIFIED", fixture_id, sorted(unknown))

        view = views[viewer]
        # BASE53 explicit grant lists are all empty. Prove the native knowledge
        # ledger currently exposes no remembered/known library grant in the
        # viewer snapshot. Descriptive obligations and channel names remain
        # immutable metadata and are not treated as native proof.
        for player in view.get("players") or []:
            if player.get("known_library") not in (None, []):
                fail("WS42_NORMALIZE_NATIVE_KNOWN_LIBRARY_NOT_EMPTY", fixture_id, viewer)
            if player.get("remembered_library_composition") not in (None, []):
                fail("WS42_NORMALIZE_NATIVE_REMEMBERED_LIBRARY_NOT_EMPTY", fixture_id, viewer)

        normalized: dict[str, Any] = {}
        for key, value in metadata.items():
            if key in DYNAMIC_KNOWLEDGE_KEYS:
                if value != []:
                    fail("WS42_NORMALIZE_NONEMPTY_KNOWLEDGE_GRANT_NOT_ADMITTED", fixture_id, {"viewer": viewer, "key": key})
                normalized[key] = []
            else:
                normalized[key] = copy.deepcopy(value)
        result["viewer_states"].append(normalized)
    return result


def normalize_rules_randomness(record: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    metadata = record["rules_randomness"]
    tape = readback.get("rules_rng_tape")
    if not isinstance(tape, dict) or tape.get("pilot_rng_mixed") is not False:
        fail("WS42_NORMALIZE_RULES_RNG_TAPE_INVALID", fixture_id)
    if int(tape.get("seed", -1)) != int(readback.get("rules_seed", -2)):
        fail("WS42_NORMALIZE_RULES_RNG_READBACK_SEED_MISMATCH", fixture_id)

    unknown = set(metadata) - RNG_POLICY_METADATA_KEYS - {
        "rules_seed",
        "predetermined_semantic_draws",
        "provider_native_rng_calls_recorded",
    }
    if unknown:
        fail("WS42_NORMALIZE_RNG_FIELD_UNCLASSIFIED", fixture_id, sorted(unknown))

    result: dict[str, Any] = {}
    for key, value in metadata.items():
        if key == "rules_seed":
            if int(value) != int(tape["seed"]):
                fail("WS42_NORMALIZE_FIXED_RULES_SEED_MISMATCH", fixture_id)
            result[key] = int(tape["seed"])
        elif key == "predetermined_semantic_draws":
            if value != []:
                fail("WS42_NORMALIZE_PREDETERMINED_DRAWS_NOT_ADMITTED", fixture_id)
            result[key] = []
        elif key == "provider_native_rng_calls_recorded":
            if value is not True or tape.get("source_identity") != "ws26-randomutil-recording/1.0.0":
                fail("WS42_NORMALIZE_NATIVE_RNG_RECORDING_NOT_PROVEN", fixture_id)
            result[key] = True
        else:
            result[key] = copy.deepcopy(value)
    return result


def normalize_stack_state(record: dict[str, Any], readback: dict[str, Any]) -> list[dict[str, Any]]:
    fixture_id = record["fixture_id"]
    validation = readback.get("native_validation")
    stack = validation.get("stack_state") if isinstance(validation, dict) else None
    if not isinstance(stack, dict) or stack.get("valid") is not True:
        fail("WS42_NORMALIZE_STACK_VALIDATION_MISSING", fixture_id)
    objects = stack.get("objects_top_to_bottom")
    if not isinstance(objects, list):
        fail("WS42_NORMALIZE_STACK_OBJECTS_MISSING", fixture_id)
    return copy.deepcopy(objects)


def normalize_setup_validation(record: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    native = readback.get("native_validation")
    if not isinstance(native, dict) or native.get("valid") is not True or native.get("fail_closed") is not True:
        fail("WS42_NORMALIZE_NATIVE_SETUP_VALIDATION_NOT_PASS", fixture_id)
    # setup_validation is immutable qualification policy, not native game state.
    # It is copied field-by-field only after the provider-native validator passed.
    allowed = {
        "compare_requested_vs_constructed",
        "construct_inside_rules_process",
        "expose_normalized_constructed_state",
        "forbidden_external_rules",
        "native_structural_validation_required",
        "on_mismatch",
        "requested_vs_normalized_native_constructed_state_equality_required",
    }
    metadata = record["setup_validation"]
    if set(metadata) != allowed:
        fail("WS42_NORMALIZE_SETUP_POLICY_FIELD_SET_CHANGED", fixture_id, sorted(metadata))
    return {key: copy.deepcopy(metadata[key]) for key in sorted(allowed)}


def normalize_record(record: dict[str, Any], probe_row: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    if probe_row.get("record_digest") != record["materialization_digest"]:
        fail("WS42_NORMALIZE_RECORD_DIGEST_MISMATCH", fixture_id)
    if probe_row.get("requested_state_digest") != record["requested_state_digest"]:
        fail("WS42_NORMALIZE_PROBE_REQUESTED_DIGEST_MISMATCH", fixture_id)
    proof = probe_row.get("non_echo_native_readback")
    if not isinstance(proof, dict):
        fail("WS42_NORMALIZE_NON_ECHO_READBACK_MISSING", fixture_id)
    if proof.get("request_object_copied_as_proof") is not False:
        fail("WS42_NORMALIZE_REQUEST_ECHO_FLAG_INVALID", fixture_id)
    if proof.get("legacy_normalized_constructed_state_consumed") is not False:
        fail("WS42_NORMALIZE_LEGACY_STATE_ECHO_CONSUMED", fixture_id)
    if proof.get("legacy_declared_digest_consumed") is not False:
        fail("WS42_NORMALIZE_LEGACY_DIGEST_CONSUMED", fixture_id)
    if proof.get("evidence_class") != "LOWER_LEVEL_NATIVE_READBACK_READY_FOR_INDEPENDENT_NORMALIZATION":
        fail("WS42_NORMALIZE_READBACK_CLASS_INVALID", fixture_id, proof.get("evidence_class"))
    if proof.get("snapshot_boundary") != "AFTER_NATIVE_SETUP_VALIDATION_BEFORE_PRIORITY_RESUME":
        fail("WS42_NORMALIZE_SNAPSHOT_BOUNDARY_INVALID", fixture_id)

    requested = requested_state_projection(record)
    if set(requested) != BASE_STATE_KEYS:
        fail("WS42_NORMALIZE_BASE_STATE_PROFILE_CHANGED", fixture_id, sorted(requested))

    normalized = {
        "execution_entry_mode": proof["execution_entry_mode"],
        "players": normalize_players(record, proof),
        "commander_state": normalize_commander_state(record, proof),
        "semantic_objects": normalize_semantic_objects(record, proof),
        "temporal_state": normalize_temporal_state(record, proof),
        "knowledge_state": normalize_knowledge_state(record, proof),
        "rules_randomness": normalize_rules_randomness(record, proof),
        "stack_state": normalize_stack_state(record, proof),
        "setup_validation": normalize_setup_validation(record, proof),
    }
    normalized_digest = canonical_sha(normalized)
    if normalized_digest != record["requested_state_digest"] or normalized != requested:
        differing = sorted(key for key in requested if normalized.get(key) != requested.get(key))
        fail(
            "WS42_NORMALIZE_REQUESTED_VS_NATIVE_MISMATCH",
            fixture_id,
            {"normalized_digest": normalized_digest, "requested_digest": record["requested_state_digest"], "keys": differing},
        )

    return {
        "fixture_id": fixture_id,
        "fixture_family": record["fixture_family"],
        "record_digest": record["materialization_digest"],
        "status": PASS_STATUS,
        "requested_state_digest": record["requested_state_digest"],
        "normalized_constructed_state_digest": normalized_digest,
        "requested_native_state_equal": True,
        "normalized_constructed_state": normalized,
        "construction_credit_granted": True,
        "behavior_runtime_credit_granted": False,
        "whole_requested_state_object_copied": False,
        "legacy_request_echo_consumed": False,
        "metadata_policy": {
            "semantic_object_metadata_keys": sorted(SEMANTIC_OBJECT_METADATA_KEYS),
            "knowledge_metadata_keys": sorted(KNOWLEDGE_METADATA_KEYS | {"channel_policy"}),
            "rules_randomness_policy_metadata_keys": sorted(RNG_POLICY_METADATA_KEYS),
            "setup_validation_is_qualification_policy_metadata": True,
            "commander_relationship_metadata_grants_rules_behavior_credit": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = provider_records(contract)
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    if probe.get("denominator") != 107 or probe.get("record_count") != 107:
        raise RuntimeError("WS42_NORMALIZE_PROBE_DENOMINATOR_MISMATCH")
    if probe.get("legacy_request_echo_accepted_as_proof") is not False:
        raise RuntimeError("WS42_NORMALIZE_PROBE_ACCEPTED_LEGACY_ECHO")
    if probe.get("historical_pass_imported") is not False:
        raise RuntimeError("WS42_NORMALIZE_PROBE_IMPORTED_HISTORICAL_PASS")

    probe_rows = probe.get("records")
    if not isinstance(probe_rows, list) or len(probe_rows) != 107:
        raise RuntimeError("WS42_NORMALIZE_PROBE_RECORDS_INVALID")
    by_id = {row.get("fixture_id"): row for row in probe_rows}
    if len(by_id) != 107 or None in by_id:
        raise RuntimeError("WS42_NORMALIZE_PROBE_FIXTURE_IDS_INVALID")

    output_rows: list[dict[str, Any]] = []
    pass_count = 0
    for record in records:
        row = by_id.get(record["fixture_id"])
        if row is None:
            raise RuntimeError(f"WS42_NORMALIZE_PROBE_ROW_MISSING:{record['fixture_id']}")
        if row.get("construction_status") == ADMITTED_PROBE_STATUS:
            normalized = normalize_record(record, row)
            output_rows.append(normalized)
            pass_count += 1
        else:
            output_rows.append(
                {
                    "fixture_id": record["fixture_id"],
                    "fixture_family": record["fixture_family"],
                    "record_digest": record["materialization_digest"],
                    "requested_state_digest": record["requested_state_digest"],
                    "status": row.get("construction_status"),
                    "construction_credit_granted": False,
                    "behavior_runtime_credit_granted": False,
                }
            )

    counts: dict[str, int] = {}
    for row in output_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    admitted = int((probe.get("counts") or {}).get(ADMITTED_PROBE_STATUS, 0))
    if pass_count != admitted:
        raise RuntimeError(f"WS42_NORMALIZE_ADMITTED_PASS_COUNT_MISMATCH:{pass_count}:{admitted}")

    output = {
        "schema_version": "commander-lab.ws42-independent-construction-normalization/1.0.0",
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.3",
        "candidate_commit": probe.get("candidate_commit"),
        "engine_commit": probe.get("engine_commit"),
        "denominator": 107,
        "record_count": len(output_rows),
        "source_probe_schema": probe.get("schema_version"),
        "source_probe_native_setup_pass": admitted,
        "counts": counts,
        "construction_credit_count": pass_count,
        "global_construction_complete": pass_count == 107,
        "behavior_runtime_credit_granted": False,
        "historical_pass_imported": False,
        "legacy_request_echo_consumed": False,
        "whole_requested_state_object_copied": False,
        "records": output_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"construction_credit_count": pass_count, "counts": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
