#!/usr/bin/env python3
"""WS49 separate independent native-readback normalization for v1.0.5 (G49-08).

This observer is deliberately independent of the construction proof:

- It never imports the construction probe, its translator, or its runner.
  Shared sub-derivations for surfaces already qualified under WS42 are reused
  from the WS42 *normalizer* modules only (never from construction code).
- Its inputs are the immutable WS-47 v1.0.5 contract plus the native readback
  payloads captured live from XMage and transported in the construction
  artifact. The construction VERDICT is never consumed as proof: every row is
  re-derived field-by-field and every credential re-checked here.
- Requested state is used for comparison and for explicitly allowlisted
  semantic-identity/descriptive/policy metadata only. Dynamic values always
  come from native readback. Whole-request echo, declared digests, and the
  construction normalizer output are never consumed as proof.
- Unsupported, ambiguous, or unclassified native surfaces fail closed.

Two entry modes:

- NATIVE_STATE_LOAD (100 rows): canonical normalization must equal the
  requested state projection exactly (digest equality), exactly as in WS42,
  extended here for the v1.0.5 dimension profile (combat_state,
  extra_turn_creation, elimination_trigger, zone_move_event, knowledge
  grants, face-down exile) and enforced absence of unrequested dimensions.
- NATURAL_GAME_START (7 rows): the requested deck_state is an entry template,
  not an opening state, so no requested digest can match. These rows instead
  pass a full native opening-state verification battery federating four
  independent native surfaces (preflight deck readback, native decision
  transcript, native observation query, replay-checkpoint snapshots) against
  the immutable entry obligations. No requested-opening equality is claimed.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path[:0] = [str(HERE), str(WS42)]

import normalize_construction_v103 as v103  # noqa: E402
import normalize_construction_v103_enriched as v103e  # noqa: E402
from successor_contract_v105 import (  # noqa: E402
    canonical_sha,
    load_contract,
    provider_records,
    requested_state_projection,
)

ADMITTED_PROBE_STATUS = "NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION"
PASS_STATUS = "PASS_INDEPENDENT_NORMALIZATION"
SCHEMA_VERSION = "commander-lab.ws49-independent-construction-normalization/1.0.0"
MATERIALIZATION_VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"
NATURAL_BOUNDARY = "AFTER_NATIVE_SHUFFLE_DRAW_AND_SCRIPTED_MULLIGANS_AT_FIRST_PRIORITY"
SETUP_BOUNDARY = "AFTER_NATIVE_SETUP_VALIDATION_BEFORE_PRIORITY_RESUME"
READBACK_CLASS = "LOWER_LEVEL_NATIVE_READBACK_READY_FOR_INDEPENDENT_NORMALIZATION"
RNG_TAPE_IDENTITY = "ws26-randomutil-recording/1.0.0"
HONEY_SENTINEL = "WS30_HONEY_P2_PRIVATE_7F3A"
REDACTED_CARD_LABEL = "Hidden card"

STATE_LOAD_BASE_KEYS = {
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
EXTRA_DIMENSION_KEYS = {
    "combat_state",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
}
# Exact requested-state profiles admitted for NATIVE_STATE_LOAD rows. Any
# other key combination fails closed as an unclassified state profile.
ADMITTED_STATE_LOAD_PROFILES = frozenset(
    [
        frozenset(STATE_LOAD_BASE_KEYS),
        frozenset(STATE_LOAD_BASE_KEYS | {"combat_state"}),
        frozenset(STATE_LOAD_BASE_KEYS | {"zone_move_event"}),
        frozenset(STATE_LOAD_BASE_KEYS | {"elimination_trigger"}),
        frozenset(STATE_LOAD_BASE_KEYS | {"extra_turn_creation"}),
    ]
)
NATURAL_REQUESTED_KEYS = frozenset(
    {
        "execution_entry_mode",
        "players",
        "deck_state",
        "commander_state",
        "semantic_objects",
        "temporal_state",
        "knowledge_state",
        "rules_randomness",
        "stack_state",
        "setup_validation",
    }
)

STATE_LOAD_READBACK_KEYS = frozenset(
    {
        "construction_credit_granted",
        "evidence_class",
        "execution_entry_mode",
        "legacy_declared_digest_consumed",
        "legacy_normalized_constructed_state_consumed",
        "native_validation",
        "player_count",
        "request_object_copied_as_proof",
        "rules_rng_tape",
        "rules_seed",
        "seed_binding",
        "semantic_state",
        "snapshot_boundary",
        "starting_life",
        "starting_player_seat",
        "ws42_readback_schema",
    }
)
VIEW_KEYS = frozenset(
    {
        "active_player_id",
        "decision_authority_player_id",
        "decision_subject_player_id",
        "decision_subject_seat",
        "live_player_count",
        "live_player_order",
        "phase",
        "player_count",
        "players",
        "priority_player_id",
        "seat",
        "stack",
        "step",
        "turn_number",
        "viewer_player_id",
    }
)
SELF_PLAYER_VIEW_KEYS = frozenset(
    {
        "battlefield",
        "command",
        "exile",
        "exile_count",
        "graveyard",
        "graveyard_count",
        "hand",
        "hand_count",
        "has_left",
        "has_lost",
        "has_won",
        "is_decision_subject",
        "is_viewer",
        "known_library",
        "land_plays_remaining",
        "library_count",
        "life",
        "mana_pool",
        "player_id",
        "poison_counters",
        "remembered_library_composition",
        "seat",
        "turn_controlled_by",
    }
)
OTHER_PLAYER_VIEW_KEYS = frozenset(
    {
        "battlefield",
        "command",
        "exile",
        "exile_count",
        "graveyard",
        "graveyard_count",
        "hand_count",
        "has_left",
        "has_lost",
        "has_won",
        "is_decision_subject",
        "is_viewer",
        "known_library",
        "library_count",
        "life",
        "player_id",
        "poison_counters",
        "remembered_library_composition",
        "seat",
        "turn_controlled_by",
    }
)
# A controller-visible but non-self hand carries identities without
# self-operational fields (observed once: controlled-player audience).
CONTROL_VISIBLE_PLAYER_VIEW_KEYS = OTHER_PLAYER_VIEW_KEYS | {"hand"}

KNOWLEDGE_METADATA_STRING_LIST_KEYS = (
    "channels_under_test",
    "honey_sentinels",
    "invalidation_conditions",
    "obligation",
    "ordered_known_information",
    "permitted_public_metadata",
    "prohibited_metadata",
)
DYNAMIC_GRANT_KEYS = (
    "face_down_look_permissions",
    "known_library_ranges",
    "known_object_identities",
    "temporary_permissions",
)


def fail(code: str, fixture_id: str, detail: Any = None) -> None:
    suffix = "" if detail is None else ":" + json.dumps(detail, sort_keys=True, ensure_ascii=False)
    raise RuntimeError(f"{code}:{fixture_id}{suffix}")


def require(cond: bool, code: str, fixture_id: str, detail: Any = None) -> None:
    if not cond:
        fail(code, fixture_id, detail)


# ---------------------------------------------------------------------------
# Readback credential gates
# ---------------------------------------------------------------------------


def check_probe_row_identity(record: dict[str, Any], probe_row: dict[str, Any]) -> None:
    fixture_id = record["fixture_id"]
    if probe_row.get("fixture_id") != fixture_id:
        fail("WS49_NORMALIZE_PROBE_FIXTURE_MISMATCH", fixture_id, probe_row.get("fixture_id"))
    if probe_row.get("construction_status") != ADMITTED_PROBE_STATUS:
        fail(
            "WS49_NORMALIZE_PROBE_ROW_NOT_ADMITTED",
            fixture_id,
            probe_row.get("construction_status"),
        )
    if probe_row.get("record_digest") != record["materialization_digest"]:
        fail("WS49_NORMALIZE_RECORD_DIGEST_MISMATCH", fixture_id)
    if probe_row.get("requested_state_digest") != record["requested_state_digest"]:
        fail("WS49_NORMALIZE_PROBE_REQUESTED_DIGEST_MISMATCH", fixture_id)
    if probe_row.get("native_setup_ready") is not True:
        fail("WS49_NORMALIZE_NATIVE_SETUP_NOT_READY", fixture_id)
    if probe_row.get("historical_pass_imported") is not False:
        fail("WS49_NORMALIZE_HISTORICAL_PASS_IMPORTED", fixture_id)


def readback_credentials_stateload(
    record: dict[str, Any], probe_row: dict[str, Any]
) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    proof = probe_row.get("non_echo_native_readback")
    if not isinstance(proof, dict):
        fail("WS49_NORMALIZE_NON_ECHO_READBACK_MISSING", fixture_id)
    if set(proof) != STATE_LOAD_READBACK_KEYS:
        fail(
            "WS49_NORMALIZE_READBACK_KEY_SET_CHANGED",
            fixture_id,
            sorted(set(proof) ^ STATE_LOAD_READBACK_KEYS),
        )
    if proof.get("request_object_copied_as_proof") is not False:
        fail("WS49_NORMALIZE_REQUEST_ECHO_FLAG_INVALID", fixture_id)
    if proof.get("legacy_normalized_constructed_state_consumed") is not False:
        fail("WS49_NORMALIZE_LEGACY_STATE_ECHO_CONSUMED", fixture_id)
    if proof.get("legacy_declared_digest_consumed") is not False:
        fail("WS49_NORMALIZE_LEGACY_DIGEST_CONSUMED", fixture_id)
    if proof.get("construction_credit_granted") is not False:
        fail("WS49_NORMALIZE_CONSTRUCTION_CREDIT_PRESENT", fixture_id)
    if proof.get("evidence_class") != READBACK_CLASS:
        fail("WS49_NORMALIZE_READBACK_CLASS_INVALID", fixture_id, proof.get("evidence_class"))
    if proof.get("snapshot_boundary") != SETUP_BOUNDARY:
        fail("WS49_NORMALIZE_SNAPSHOT_BOUNDARY_INVALID", fixture_id)
    if proof.get("execution_entry_mode") != "NATIVE_STATE_LOAD":
        fail("WS49_NORMALIZE_ENTRY_MODE_MISMATCH", fixture_id)
    if proof.get("ws42_readback_schema") != "xmage-ws42-native-construction-readback/1.0.0":
        fail("WS49_NORMALIZE_READBACK_SCHEMA_MISMATCH", fixture_id)
    native = proof.get("native_validation")
    if not isinstance(native, dict) or native.get("valid") is not True:
        fail("WS49_NORMALIZE_NATIVE_VALIDATION_NOT_PASS", fixture_id)
    return proof


# ---------------------------------------------------------------------------
# Reused WS42 sub-derivations (normalizer code only, never construction code)
# ---------------------------------------------------------------------------


def normalize_players_105(record: dict[str, Any], proof: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return v103.normalize_players(record, proof)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_PLAYERS:{record['fixture_id']}:{exc}") from exc


def normalize_temporal_105(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    try:
        return v103.normalize_temporal_state(record, proof)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_TEMPORAL:{record['fixture_id']}:{exc}") from exc


def normalize_stack_105(record: dict[str, Any], proof: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return v103.normalize_stack_state(record, proof)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_STACK:{record['fixture_id']}:{exc}") from exc


def normalize_setup_105(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    try:
        return v103.normalize_setup_validation(record, proof)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_SETUP:{record['fixture_id']}:{exc}") from exc


def normalize_commander_105(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    try:
        return v103e.normalize_commander_state(record, proof)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_COMMANDER:{record['fixture_id']}:{exc}") from exc


def normalize_semantic_objects_105(
    record: dict[str, Any], proof: dict[str, Any]
) -> list[dict[str, Any]]:
    fixture_id = record["fixture_id"]
    try:
        rows = v103e.normalize_semantic_objects(record, proof)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_OBJECTS:{fixture_id}:{exc}") from exc
    # v1.0.5 admits face-down exile. The shared base hard-codes face_down=False
    # outside battlefield/stack/command; correct it here from the privileged
    # native face-down readback (Card.isFaceDown via the replay recorder).
    native = v103.native_scenario_objects(proof, fixture_id)
    rows_by_id = {str(row["semantic_id"]): row for row in rows}
    for metadata in record["semantic_objects"]:
        if metadata.get("zone") != "exile":
            continue
        sid = str(metadata["semantic_id"])
        native_object = native.get(sid)
        if native_object is None:
            fail("WS49_NORMALIZE_EXILE_NATIVE_OBJECT_MISSING", fixture_id, sid)
        if "face_down" not in native_object:
            fail("WS49_NORMALIZE_EXILE_FACE_DOWN_READBACK_MISSING", fixture_id, sid)
        row = rows_by_id.get(sid)
        if row is None:
            fail("WS49_NORMALIZE_EXILE_ROW_MISSING", fixture_id, sid)
        row["face_down"] = bool(native_object["face_down"])
    reconcile_counter_zero_convention(record, rows_by_id, fixture_id)
    verify_sickness_fidelity(record, proof, fixture_id)
    return rows


def verify_sickness_fidelity(
    record: dict[str, Any], proof: dict[str, Any], fixture_id: str
) -> None:
    """Pin installed summoning-sickness state to the modeled flag.

    The setup installs sickness per object (ETB default sick; lift only where
    the immutable record models controlled-since-turn-began). The native
    readback must therefore report True exactly where requested and False
    everywhere else on the battlefield; other zones never carry the flag.
    """
    native = v103.native_scenario_objects(proof, fixture_id)
    by_id = {str(o["semantic_id"]): o for o in record.get("semantic_objects") or []}
    for sid, obj in native.items():
        requested = by_id.get(sid)
        if requested is None:
            fail("WS49_NORMALIZE_SICKNESS_UNMAPPED_NATIVE_OBJECT", fixture_id, sid)
        if requested.get("zone") == "battlefield":
            if "controlled_since_turn_began" not in obj:
                fail("WS49_NORMALIZE_SICKNESS_READBACK_MISSING", fixture_id, sid)
            expected = requested.get("controlled_since_turn_began") is True
            if bool(obj["controlled_since_turn_began"]) != expected:
                fail(
                    "WS49_NORMALIZE_SICKNESS_STATE_MISMATCH",
                    fixture_id,
                    {"object": sid, "native": obj["controlled_since_turn_began"]},
                )
        elif "controlled_since_turn_began" in obj:
            fail("WS49_NORMALIZE_SICKNESS_OFF_BATTLEFIELD", fixture_id, sid)


def reconcile_counter_zero_convention(
    record: dict[str, Any], rows_by_id: dict[str, dict[str, Any]], fixture_id: str
) -> None:
    """Merge the counters zero-convention explicitly.

    Both XMage (Counters maps omit zero counts) and the contract (explicit
    zeros such as age 0) agree that an absent counter means zero. The merge
    is therefore a normalization convention, never inference: every
    requested nonzero counter must be present natively with equal value, no
    native counter may exist outside the requested set, and explicit
    requested zeros are emitted only after proving native absence.
    """
    for metadata in record["semantic_objects"]:
        sid = str(metadata["semantic_id"])
        requested = metadata.get("counters") or {}
        if not isinstance(requested, dict):
            fail("WS49_NORMALIZE_REQUESTED_COUNTERS_INVALID", fixture_id, sid)
        row = rows_by_id.get(sid)
        if row is None:
            fail("WS49_NORMALIZE_COUNTER_ROW_MISSING", fixture_id, sid)
        native_counters = row.get("counters")
        if not isinstance(native_counters, dict):
            fail("WS49_NORMALIZE_NATIVE_COUNTERS_INVALID", fixture_id, sid)
        for counter_type, value in requested.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail("WS49_NORMALIZE_REQUESTED_COUNTER_VALUE_INVALID", fixture_id, sid)
            if value == 0:
                if counter_type in native_counters and native_counters[counter_type] != 0:
                    fail("WS49_NORMALIZE_ZERO_COUNTER_NONZERO_NATIVE", fixture_id, sid)
                native_counters[counter_type] = 0
            elif native_counters.get(counter_type) != value:
                fail(
                    "WS49_NORMALIZE_COUNTER_VALUE_MISMATCH",
                    fixture_id,
                    {"object": sid, "counter": counter_type},
                )
        for counter_type in native_counters:
            if counter_type not in requested:
                fail("WS49_NORMALIZE_UNREQUESTED_NATIVE_COUNTER", fixture_id, sid)


def normalize_randomness_105(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    """Normalize rules randomness for the three admitted v1.0.5 profiles.

    Fixed-seed rows reuse the shared derivation, then additionally pin the
    readback seed. Scenario-bound rows carry no fixed seed in the contract, so
    the tape is verified as genuine native Rules-RNG output (integrity,
    authority, unmixed) without asserting a value the contract never states.
    """
    fixture_id = record["fixture_id"]
    metadata = record["rules_randomness"]
    tape = proof.get("rules_rng_tape")
    if not isinstance(tape, dict):
        fail("WS49_NORMALIZE_RULES_RNG_TAPE_MISSING", fixture_id)
    if tape.get("schema_version") != "rules-rng-tape/1.0.0":
        fail("WS49_NORMALIZE_RULES_RNG_TAPE_SCHEMA_INVALID", fixture_id)
    if tape.get("authority") != "mage.util.RandomUtil":
        fail("WS49_NORMALIZE_RULES_RNG_AUTHORITY_INVALID", fixture_id)
    if tape.get("source_identity") != RNG_TAPE_IDENTITY:
        fail("WS49_NORMALIZE_RULES_RNG_SOURCE_IDENTITY_INVALID", fixture_id)
    if tape.get("pilot_rng_mixed") is not False:
        fail("WS49_NORMALIZE_PILOT_RNG_MIXED", fixture_id)
    operations = tape.get("operations")
    if not isinstance(operations, list) or not all(isinstance(o, str) for o in operations):
        fail("WS49_NORMALIZE_RULES_RNG_OPERATIONS_INVALID", fixture_id)
    if int(tape.get("operation_count", -1)) != len(operations):
        fail("WS49_NORMALIZE_RULES_RNG_OPERATION_COUNT_MISMATCH", fixture_id)
    seed = tape.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        fail("WS49_NORMALIZE_RULES_RNG_SEED_INVALID", fixture_id)

    keys = set(metadata)
    if keys == {
        "channels",
        "pilot_randomness_prohibited",
        "predetermined_semantic_draws",
        "rules_seed",
    }:
        channels = metadata.get("channels")
        if not isinstance(channels, list) or any(not isinstance(c, str) or not c for c in channels):
            fail("WS49_NORMALIZE_RNG_CHANNELS_INVALID", fixture_id)
        if metadata.get("pilot_randomness_prohibited") is not True:
            fail("WS49_NORMALIZE_RNG_PILOT_POLICY_INVALID", fixture_id)
        if int(metadata.get("rules_seed", -1)) != seed:
            fail("WS49_NORMALIZE_FIXED_RULES_SEED_MISMATCH", fixture_id)
        if int(proof.get("rules_seed", -2)) != seed:
            fail("WS49_NORMALIZE_RULES_RNG_READBACK_SEED_MISMATCH", fixture_id)
        draws = metadata.get("predetermined_semantic_draws")
        if not isinstance(draws, list):
            fail("WS49_NORMALIZE_PREDETERMINED_DRAWS_INVALID", fixture_id)
        normalized_draws = verify_predetermined_draws(record, proof, draws)
        return {
            "channels": copy.deepcopy(channels),
            "pilot_randomness_prohibited": True,
            "predetermined_semantic_draws": normalized_draws,
            "rules_seed": seed,
        }
    if keys == {
        "channels",
        "pilot_randomness_prohibited",
        "provider_native_rng_calls_recorded",
        "seed_binding",
    }:
        if metadata.get("seed_binding") != "SCENARIO_SEED":
            fail(
                "WS49_NORMALIZE_RNG_SEED_BINDING_INVALID", fixture_id, metadata.get("seed_binding")
            )
        if metadata.get("pilot_randomness_prohibited") is not True:
            fail("WS49_NORMALIZE_RNG_PILOT_POLICY_INVALID", fixture_id)
        if metadata.get("provider_native_rng_calls_recorded") is not True:
            fail("WS49_NORMALIZE_RNG_RECORDING_FLAG_INVALID", fixture_id)
        if int(proof.get("rules_seed", -2)) != seed:
            fail("WS49_NORMALIZE_RULES_RNG_READBACK_SEED_MISMATCH", fixture_id)
        if not isinstance(metadata.get("channels"), list) or not metadata["channels"]:
            fail("WS49_NORMALIZE_RNG_CHANNELS_INVALID", fixture_id)
        return {
            "channels": copy.deepcopy(metadata["channels"]),
            "pilot_randomness_prohibited": True,
            "provider_native_rng_calls_recorded": True,
            "seed_binding": "SCENARIO_SEED",
        }
    fail("WS49_NORMALIZE_RNG_PROFILE_UNCLASSIFIED", fixture_id, sorted(keys))
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# v1.0.5 extra native dimensions (NATIVE_STATE_LOAD)
# ---------------------------------------------------------------------------


def verify_predetermined_draws(
    record: dict[str, Any], proof: dict[str, Any], draws: list[Any]
) -> list[dict[str, Any]]:
    """Verify predetermined semantic draws as pending behavior obligations.

    A predetermined draw fixes a future Rules-RNG outcome (e.g. a coin flip
    on resolution). At the setup snapshot the only verifiable native facts
    are wellformedness, channel declaration, and that the source spell is
    still natively unresolved on the stack (the outcome is still future).
    The predetermined RESULT itself is a behavior-stage obligation and is
    carried as descriptive metadata, never claimed as observed here.
    """
    fixture_id = record["fixture_id"]
    channels = record["rules_randomness"].get("channels") or []
    native = proof.get("native_validation")
    stack = native.get("stack_state") if isinstance(native, dict) else None
    if not isinstance(stack, dict) or stack.get("valid") is not True:
        fail("WS49_NORMALIZE_PREDETERMINED_STACK_VALIDATION_MISSING", fixture_id)
    stack_sids = {
        item.get("source_semantic_id")
        for item in stack.get("objects_top_to_bottom") or []
        if isinstance(item, dict)
    }
    normalized: list[dict[str, Any]] = []
    for entry in draws:
        if not isinstance(entry, dict):
            fail("WS49_NORMALIZE_PREDETERMINED_ENTRY_INVALID", fixture_id, entry)
        if set(entry) != {"channel", "operation", "result"}:
            fail("WS49_NORMALIZE_PREDETERMINED_ENTRY_KEYS_INVALID", fixture_id, sorted(entry))
        channel = entry.get("channel")
        operation = entry.get("operation")
        result = entry.get("result")
        if not all(isinstance(x, str) and x for x in (channel, operation, result)):
            fail("WS49_NORMALIZE_PREDETERMINED_ENTRY_VALUES_INVALID", fixture_id, entry)
        if channel not in channels:
            fail("WS49_NORMALIZE_PREDETERMINED_CHANNEL_UNDECLARED", fixture_id, channel)
        sid = entry_channel_source(channel, operation, fixture_id)
        if sid not in stack_sids:
            fail("WS49_NORMALIZE_PREDETERMINED_SOURCE_NOT_PENDING", fixture_id, sid)
        normalized.append({"channel": channel, "operation": operation, "result": result})
    return normalized


def entry_channel_source(channel: str, operation: str, fixture_id: str) -> str:
    """Split '<operation>:<semantic_id>' channels; fail closed otherwise."""
    prefix = operation + ":"
    if not channel.startswith(prefix) or len(channel) <= len(prefix):
        fail("WS49_NORMALIZE_PREDETERMINED_CHANNEL_SHAPE_INVALID", fixture_id, channel)
    return channel[len(prefix) :]


def native_extension_block(proof: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    native = proof.get("native_validation")
    ext = native.get("ws46_native_construction_state") if isinstance(native, dict) else None
    if not isinstance(ext, dict):
        fail("WS49_NORMALIZE_WS46_EXTENSION_MISSING", fixture_id)
    if ext.get("validator") != "xmage-ws46-native-construction-state/1.0.0":
        fail("WS49_NORMALIZE_WS46_EXTENSION_VALIDATOR_INVALID", fixture_id)
    if ext.get("valid") is not True:
        fail("WS49_NORMALIZE_WS46_EXTENSION_NOT_VALID", fixture_id)
    if ext.get("rules_core_authoritative") is not True:
        fail("WS49_NORMALIZE_WS46_EXTENSION_AUTHORITY_INVALID", fixture_id)
    if ext.get("snapshot_restore_only") is not True:
        fail("WS49_NORMALIZE_WS46_EXTENSION_RESTORE_ONLY_INVALID", fixture_id)
    if ext.get("historical_events_fabricated") is not False:
        fail("WS49_NORMALIZE_WS46_EXTENSION_FABRICATED_HISTORY", fixture_id)
    if ext.get("rules_behavior_credit_granted") is not False:
        fail("WS49_NORMALIZE_WS46_EXTENSION_BEHAVIOR_CREDIT", fixture_id)
    return ext


def normalize_combat_state(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize combat_state, or None when the record carries no such dimension.

    Requested keys are verified against the native Combat/CombatGroup readback
    and emitted from native values. Attacker eligibility is natively scoped to
    the active player and compared exactly. Blocker eligibility is aggregated
    natively across defending players, so the requested list is verified as
    exactly the boundary actor's (temporal priority player's) options while
    every extra must defend some native attacker. Native-only surfaces are
    otherwise verified well-formed and membership-bound but never carried, so
    the digest still compares exactly the requested profile.
    """
    fixture_id = record["fixture_id"]
    requested = record.get("combat_state")
    ext = native_extension_block(proof, fixture_id)
    block = ext.get("combat_state")
    if not isinstance(block, dict):
        fail("WS49_NORMALIZE_COMBAT_BLOCK_MISSING", fixture_id)
    if requested is None:
        if block.get("present") is not False:
            fail("WS49_NORMALIZE_UNREQUESTED_NATIVE_COMBAT", fixture_id, block.get("present"))
        if block.get("valid") is not True:
            fail("WS49_NORMALIZE_COMBAT_ABSENT_BLOCK_INVALID", fixture_id)
        return None
    if block.get("valid") is not True or block.get("present") is not True:
        fail("WS49_NORMALIZE_COMBAT_NOT_PRESENT", fixture_id)
    if block.get("native_surface") != "GameState.Combat/CombatGroup":
        fail("WS49_NORMALIZE_COMBAT_NATIVE_SURFACE_INVALID", fixture_id)
    if block.get("historical_declare_events_fabricated") is not False:
        fail("WS49_NORMALIZE_COMBAT_FABRICATED_HISTORY", fixture_id)
    allowed_requested = {
        "attackers",
        "blockers",
        "unblocked",
        "unblocked_attackers",
        "eligible_attackers",
        "eligible_blockers",
    }
    unknown = set(requested) - allowed_requested
    if unknown:
        fail("WS49_NORMALIZE_COMBAT_FIELD_UNCLASSIFIED", fixture_id, sorted(unknown))
    privileged = v103.native_scenario_objects(proof, fixture_id)
    for list_key in ("eligible_attackers", "eligible_blockers"):
        value = block.get(list_key)
        if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
            fail("WS49_NORMALIZE_COMBAT_ELIGIBILITY_MALFORMED", fixture_id, list_key)
        for sid in value:
            if sid not in privileged:
                fail("WS49_NORMALIZE_COMBAT_ELIGIBILITY_UNMAPPED", fixture_id, sid)
    if (
        "unblocked" in block
        and "unblocked_attackers" in block
        and sorted(block["unblocked"]) != sorted(block["unblocked_attackers"])
    ):
        fail("WS49_NORMALIZE_COMBAT_UNBLOCKED_INCOHERENT", fixture_id)
    normalized: dict[str, Any] = {}
    for key in ("attackers", "blockers"):
        if key not in requested:
            continue
        native_map = block.get(key)
        if not isinstance(native_map, dict):
            fail("WS49_NORMALIZE_COMBAT_MAP_MISSING", fixture_id, key)
        if dict(native_map) != dict(requested[key]):
            fail(
                "WS49_NORMALIZE_COMBAT_MAP_MISMATCH",
                fixture_id,
                {"key": key, "native": native_map, "requested": requested[key]},
            )
        normalized[key] = copy.deepcopy(native_map)
    for key in ("unblocked", "unblocked_attackers", "eligible_attackers"):
        if key not in requested:
            continue
        native_list = block.get(key)
        if not isinstance(native_list, list):
            fail("WS49_NORMALIZE_COMBAT_LIST_MISSING", fixture_id, key)
        if sorted(native_list) != sorted(requested[key]):
            fail(
                "WS49_NORMALIZE_COMBAT_LIST_MISMATCH",
                fixture_id,
                {"key": key, "native": native_list, "requested": requested[key]},
            )
        normalized[key] = copy.deepcopy(native_list)
    if "eligible_blockers" in requested:
        normalized["eligible_blockers"] = normalize_eligible_blockers(record, block, privileged)
    return normalized


def normalize_eligible_blockers(
    record: dict[str, Any],
    block: dict[str, Any],
    privileged: dict[str, dict[str, Any]],
) -> list[str]:
    """Verify requested eligible blockers as the boundary actor's options.

    The native aggregation spans every defending player while the requested
    list models the temporal priority player's declaration options at this
    boundary. Extras must therefore all belong to other players, and each
    must defend some native attacker (catches declaration-authority leaks).
    """
    defenders = (
        set(block.get("attackers", {}).values())
        if isinstance(block.get("attackers"), dict)
        else set()
    )
    fixture_id = record["fixture_id"]
    requested_list = record["combat_state"]["eligible_blockers"]
    native_list = block.get("eligible_blockers")
    if not isinstance(requested_list, list) or not isinstance(native_list, list):
        fail("WS49_NORMALIZE_ELIGIBLE_BLOCKERS_SHAPE_INVALID", fixture_id)
    priority = (record.get("temporal_state") or {}).get("priority_player")
    if not isinstance(priority, str) or not priority:
        fail("WS49_NORMALIZE_BLOCKER_PRIORITY_MISSING", fixture_id)
    controllers: dict[str, str] = {}
    for sid in native_list:
        obj = privileged.get(sid)
        if obj is None or "controller_seat" not in obj:
            fail("WS49_NORMALIZE_BLOCKER_CONTROLLER_MISSING", fixture_id, sid)
        controllers[sid] = owner_of(obj["controller_seat"], fixture_id)
    if sorted(s for s in native_list if controllers[s] == priority) != sorted(requested_list):
        fail(
            "WS49_NORMALIZE_ELIGIBLE_BLOCKERS_SCOPE_MISMATCH",
            fixture_id,
            {"native_priority": sorted(s for s in native_list if controllers[s] == priority)},
        )
    for sid in native_list:
        if controllers[sid] == priority:
            continue
        if controllers[sid] not in defenders:
            fail("WS49_NORMALIZE_BLOCKER_DEFENDS_NOTHING", fixture_id, sid)
    # Emit the requested order: every requested element was proven present in
    # the native priority subset above, and digest equality arbitrates order.
    return copy.deepcopy(requested_list)


def normalize_extra_turns(
    record: dict[str, Any], proof: dict[str, Any]
) -> list[dict[str, Any]] | None:
    fixture_id = record["fixture_id"]
    requested = record.get("extra_turn_creation")
    ext = native_extension_block(proof, fixture_id)
    block = ext.get("extra_turn_creation")
    if not isinstance(block, dict):
        fail("WS49_NORMALIZE_EXTRA_TURN_BLOCK_MISSING", fixture_id)
    if requested is None:
        if block.get("present") is not False:
            fail("WS49_NORMALIZE_UNREQUESTED_NATIVE_EXTRA_TURNS", fixture_id)
        if block.get("valid") is not True:
            fail("WS49_NORMALIZE_EXTRA_TURN_ABSENT_BLOCK_INVALID", fixture_id)
        return None
    if block.get("valid") is not True or block.get("present") is not True:
        fail("WS49_NORMALIZE_EXTRA_TURN_NOT_PRESENT", fixture_id)
    if block.get("native_surface") != "GameState.turnMods/TurnMod":
        fail("WS49_NORMALIZE_EXTRA_TURN_NATIVE_SURFACE_INVALID", fixture_id)
    if block.get("historical_spell_resolution_events_fabricated") is not False:
        fail("WS49_NORMALIZE_EXTRA_TURN_FABRICATED_HISTORY", fixture_id)
    native_rows = block.get("resolutions")
    if not isinstance(native_rows, list):
        fail("WS49_NORMALIZE_EXTRA_TURN_RESOLUTIONS_MISSING", fixture_id)
    if not isinstance(requested, list) or len(native_rows) != len(requested):
        fail(
            "WS49_NORMALIZE_EXTRA_TURN_COUNT_MISMATCH",
            fixture_id,
            {
                "native": len(native_rows) if isinstance(native_rows, list) else None,
                "requested": len(requested) if isinstance(requested, list) else None,
            },
        )
    native_by_sequence: dict[int, dict[str, Any]] = {}
    for item in native_rows:
        if not isinstance(item, dict):
            fail("WS49_NORMALIZE_EXTRA_TURN_ROW_INVALID", fixture_id, item)
        sequence = item.get("sequence")
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence in native_by_sequence
        ):
            fail("WS49_NORMALIZE_EXTRA_TURN_SEQUENCE_INVALID", fixture_id, item)
        if item.get("native_extra_turn") is not True:
            fail("WS49_NORMALIZE_EXTRA_TURN_NOT_NATIVE", fixture_id, item)
        native_by_sequence[sequence] = item
    if set(native_by_sequence) != set(range(1, len(requested) + 1)):
        fail(
            "WS49_NORMALIZE_EXTRA_TURN_SEQUENCE_SET_INVALID", fixture_id, sorted(native_by_sequence)
        )
    rows: list[dict[str, Any]] = []
    for expected in requested:
        if not isinstance(expected, dict):
            fail("WS49_NORMALIZE_EXTRA_TURN_EXPECTED_ROW_INVALID", fixture_id, expected)
        sequence = expected.get("sequence")
        native = native_by_sequence.get(sequence) if isinstance(sequence, int) else None
        if native is None:
            fail("WS49_NORMALIZE_EXTRA_TURN_NATIVE_ROW_MISSING", fixture_id, sequence)
        if native.get("player") != expected.get("player") or native.get("source") != expected.get(
            "source"
        ):
            fail(
                "WS49_NORMALIZE_EXTRA_TURN_ROW_MISMATCH",
                fixture_id,
                {"native": native, "requested": expected},
            )
        # semantic_resolution is immutable descriptive metadata of the
        # resolution the native TurnMod proves; the dynamic proof is the
        # native extra-turn entry itself.
        if (
            not isinstance(expected.get("semantic_resolution"), str)
            or not expected["semantic_resolution"]
        ):
            fail("WS49_NORMALIZE_EXTRA_TURN_RESOLUTION_TEXT_INVALID", fixture_id, expected)
        rows.append(
            {
                "player": str(native["player"]),
                "semantic_resolution": str(expected["semantic_resolution"]),
                "sequence": int(sequence),
                "source": str(native["source"]),
            }
        )
    rows.sort(key=lambda row: row["sequence"])
    return rows


def normalize_elimination(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any] | None:
    fixture_id = record["fixture_id"]
    requested = record.get("elimination_trigger")
    ext = native_extension_block(proof, fixture_id)
    block = ext.get("elimination_trigger")
    if not isinstance(block, dict):
        fail("WS49_NORMALIZE_ELIMINATION_BLOCK_MISSING", fixture_id)
    if requested is None:
        if block.get("present") is not False:
            fail("WS49_NORMALIZE_UNREQUESTED_NATIVE_ELIMINATION", fixture_id)
        if block.get("valid") is not True:
            fail("WS49_NORMALIZE_ELIMINATION_ABSENT_BLOCK_INVALID", fixture_id)
        return None
    if block.get("valid") is not True or block.get("present") is not True:
        fail("WS49_NORMALIZE_ELIMINATION_NOT_PRESENT", fixture_id)
    if block.get("native_surface") != "Player.life + GameImpl.stateBasedActions":
        fail("WS49_NORMALIZE_ELIMINATION_NATIVE_SURFACE_INVALID", fixture_id)
    if set(requested) != {"player", "reason"}:
        fail("WS49_NORMALIZE_ELIMINATION_REQUESTED_SHAPE_INVALID", fixture_id, sorted(requested))
    if block.get("player") != requested.get("player"):
        fail("WS49_NORMALIZE_ELIMINATION_PLAYER_MISMATCH", fixture_id, block.get("player"))
    if block.get("reason") != "life_total_0" or requested.get("reason") != "life_total_0":
        fail("WS49_NORMALIZE_ELIMINATION_REASON_INVALID", fixture_id, block.get("reason"))
    if block.get("native_life") != 0:
        fail("WS49_NORMALIZE_ELIMINATION_NATIVE_LIFE_INVALID", fixture_id, block.get("native_life"))
    if block.get("native_player_already_lost") is not False:
        fail("WS49_NORMALIZE_ELIMINATION_ALREADY_LOST", fixture_id)
    if block.get("sba_not_preexecuted") is not True:
        fail("WS49_NORMALIZE_ELIMINATION_SBA_PREEXECUTED", fixture_id)
    return {"player": str(block["player"]), "reason": "life_total_0"}


def normalize_zone_move(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any] | None:
    fixture_id = record["fixture_id"]
    requested = record.get("zone_move_event")
    ext = native_extension_block(proof, fixture_id)
    block = ext.get("zone_move_event")
    if not isinstance(block, dict):
        fail("WS49_NORMALIZE_ZONE_MOVE_BLOCK_MISSING", fixture_id)
    if requested is None:
        if block.get("present") is not False:
            fail("WS49_NORMALIZE_UNREQUESTED_NATIVE_ZONE_MOVE", fixture_id)
        if block.get("valid") is not True:
            fail("WS49_NORMALIZE_ZONE_MOVE_ABSENT_BLOCK_INVALID", fixture_id)
        return None
    if block.get("valid") is not True or block.get("present") is not True:
        fail("WS49_NORMALIZE_ZONE_MOVE_NOT_PRESENT", fixture_id)
    if block.get("native_entry_class") != (
        "mage.game.ZoneChangeInfo$Library"
        if requested.get("to") == "library"
        else "mage.game.ZoneChangeInfo"
    ):
        fail(
            "WS49_NORMALIZE_ZONE_MOVE_NATIVE_SURFACE_INVALID",
            fixture_id,
            block.get("native_entry_class"),
        )
    if block.get("historical_zone_change_event_fabricated") is not False:
        fail("WS49_NORMALIZE_ZONE_MOVE_FABRICATED_HISTORY", fixture_id)
    if block.get("pending_not_executed") is not True:
        fail("WS49_NORMALIZE_ZONE_MOVE_EXECUTED", fixture_id)
    if set(requested) != {"commander_choice_timing", "commander_id", "from", "to"}:
        fail("WS49_NORMALIZE_ZONE_MOVE_REQUESTED_SHAPE_INVALID", fixture_id, sorted(requested))
    for key in ("commander_id", "from", "to", "commander_choice_timing"):
        if block.get(key) != requested.get(key):
            fail(
                "WS49_NORMALIZE_ZONE_MOVE_FIELD_MISMATCH",
                fixture_id,
                {"key": key, "native": block.get(key), "requested": requested.get(key)},
            )
    # Cross-check the commander mapping exactly as the provider translator
    # must: one semantic object, owner match, source zone match.
    commander_id = str(requested["commander_id"])
    matches = [
        obj
        for obj in (record.get("semantic_objects") or [])
        if isinstance(obj, dict) and obj.get("commander_id") == commander_id
    ]
    if len(matches) != 1:
        fail("WS49_NORMALIZE_ZONE_MOVE_COMMANDER_MAPPING_NOT_UNIQUE", fixture_id, commander_id)
    if matches[0].get("zone") != requested.get("from"):
        fail("WS49_NORMALIZE_ZONE_MOVE_SOURCE_ZONE_MISMATCH", fixture_id, matches[0].get("zone"))
    if block.get("owner") != matches[0].get("owner"):
        fail("WS49_NORMALIZE_ZONE_MOVE_OWNER_MISMATCH", fixture_id, block.get("owner"))
    if block.get("semantic_id") != matches[0].get("semantic_id"):
        fail("WS49_NORMALIZE_ZONE_MOVE_SEMANTIC_ID_MISMATCH", fixture_id, block.get("semantic_id"))
    return {
        "commander_choice_timing": str(block["commander_choice_timing"]),
        "commander_id": commander_id,
        "from": str(block["from"]),
        "to": str(block["to"]),
    }


# ---------------------------------------------------------------------------
# Knowledge-state normalization (v1.0.5)
#
# The native actor views partition hidden information per viewer. Every grant
# is verified against those views; audience prohibitions are enforced
# structurally; behavioral permissions (reveal/search/control/invalidation)
# that cannot culminate at a setup snapshot are carried as qualified policy
# metadata with an explicit behavior-stage boundary note. Sentinel absence is
# scanned across the whole readback.
# ---------------------------------------------------------------------------


def native_views_by_player(proof: dict[str, Any], fixture_id: str) -> dict[str, dict[str, Any]]:
    views = v103.actor_views(proof, fixture_id)
    for viewer, view in views.items():
        if set(view) != VIEW_KEYS:
            fail(
                "WS49_NORMALIZE_VIEW_KEY_SET_CHANGED",
                fixture_id,
                {"viewer": viewer, "keys": sorted(view)},
            )
    return views


def player_bucket(view: dict[str, Any], pid: str, fixture_id: str, viewer: str) -> dict[str, Any]:
    players = view.get("players")
    if not isinstance(players, list):
        fail("WS49_NORMALIZE_VIEW_PLAYERS_MISSING", fixture_id, viewer)
    matches = [p for p in players if isinstance(p, dict) and p.get("player_id") == pid]
    if len(matches) != 1:
        fail(
            "WS49_NORMALIZE_VIEW_PLAYER_BUCKET_INVALID",
            fixture_id,
            {"viewer": viewer, "player": pid},
        )
    entry = matches[0]
    keys = set(entry)
    if viewer == pid:
        if keys != SELF_PLAYER_VIEW_KEYS and keys != CONTROL_VISIBLE_PLAYER_VIEW_KEYS:
            fail(
                "WS49_NORMALIZE_SELF_VIEW_KEY_SET_CHANGED",
                fixture_id,
                {"viewer": viewer, "keys": sorted(keys)},
            )
    else:
        if keys != OTHER_PLAYER_VIEW_KEYS and keys != CONTROL_VISIBLE_PLAYER_VIEW_KEYS:
            fail(
                "WS49_NORMALIZE_OTHER_VIEW_KEY_SET_CHANGED",
                fixture_id,
                {"viewer": viewer, "player": pid, "keys": sorted(keys)},
            )
    if entry.get("has_won") is not False:
        fail("WS49_NORMALIZE_UNEXPECTED_WINNER", fixture_id, {"viewer": viewer, "player": pid})
    if entry.get("is_viewer") is not (viewer == pid):
        fail("WS49_NORMALIZE_IS_VIEWER_FLAG_INVALID", fixture_id, {"viewer": viewer, "player": pid})
    return entry


def privileged_zone_index(proof: dict[str, Any], fixture_id: str) -> dict[str, dict[str, Any]]:
    objects = v103.native_scenario_objects(proof, fixture_id)
    for sid, obj in objects.items():
        if not isinstance(obj.get("card_name"), str) or not obj["card_name"]:
            fail("WS49_NORMALIZE_PRIVILEGED_NAME_MISSING", fixture_id, sid)
        if not isinstance(obj.get("zone"), str) or not obj["zone"]:
            fail("WS49_NORMALIZE_PRIVILEGED_ZONE_MISSING", fixture_id, sid)
        if not isinstance(obj.get("owner_seat"), int):
            fail("WS49_NORMALIZE_PRIVILEGED_OWNER_MISSING", fixture_id, sid)
    return objects


def owner_of(owner_seat: int, fixture_id: str) -> str:
    """Native owner/controller seats are 1-based player numbers (P1 == 1)."""
    if not isinstance(owner_seat, int) or isinstance(owner_seat, bool) or owner_seat < 1:
        fail("WS49_NORMALIZE_NATIVE_SEAT_INVALID", fixture_id, owner_seat)
    return f"P{owner_seat}"


V105_STATE_KEYS = frozenset(
    {
        "execution_entry_mode",
        "players",
        "deck_state",
        "commander_state",
        "semantic_objects",
        "temporal_state",
        "knowledge_state",
        "rules_randomness",
        "combat_state",
        "stack_state",
        "continuous_rules_effects",
        "extra_turn_creation",
        "elimination_trigger",
        "zone_move_event",
        "setup_validation",
    }
)


def expected_known_union(
    viewer_states: list[dict[str, Any]],
    privileged: dict[str, dict[str, Any]],
    fixture_id: str,
) -> dict[tuple[str, str], dict[int, str | None]]:
    """Compute expected known_library positions per (viewer, player) pair.

    Positions come from known_library_ranges; names come from privileged
    library objects at those positions (identity grants must agree with the
    same physical truth). Positions with no privileged counterpart are native
    substrate: structure and audience are verified, identities recorded.
    """
    union: dict[tuple[str, str], dict[int, str | None]] = {}

    def add_position(viewer: str, player: str, position: int) -> None:
        union.setdefault((viewer, player), {}).setdefault(position, None)

    for state in viewer_states:
        for grant in state.get("known_library_ranges") or []:
            if not isinstance(grant, dict):
                fail("WS49_NORMALIZE_RANGE_GRANT_INVALID", fixture_id, grant)
            viewer = grant.get("viewer")
            player = grant.get("player")
            start = grant.get("start")
            count = grant.get("count")
            ordered = grant.get("ordered")
            if not isinstance(viewer, str) or not isinstance(player, str):
                fail("WS49_NORMALIZE_RANGE_GRANT_ACTOR_INVALID", fixture_id, grant)
            if not isinstance(start, int) or isinstance(start, bool) or start < 0:
                fail("WS49_NORMALIZE_RANGE_GRANT_START_INVALID", fixture_id, grant)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                fail("WS49_NORMALIZE_RANGE_GRANT_COUNT_INVALID", fixture_id, grant)
            if ordered is not True:
                fail("WS49_NORMALIZE_UNORDERED_RANGE_NOT_ADMITTED", fixture_id, grant)
            if grant.get("before_event") not in (None, "shuffle"):
                fail("WS49_NORMALIZE_RANGE_BEFORE_EVENT_INVALID", fixture_id, grant)
            for position in range(start, start + count):
                add_position(viewer, player, position)
    for state in viewer_states:
        viewer = state.get("viewer")
        if not isinstance(viewer, str):
            fail("WS49_NORMALIZE_KNOWN_VIEWER_INVALID", fixture_id, viewer)
        for sid in state.get("known_object_identities") or []:
            obj = privileged.get(sid)
            if obj is None or obj.get("zone") != "library":
                continue
            position = obj.get("zone_position")
            if not isinstance(position, int) or isinstance(position, bool):
                fail("WS49_NORMALIZE_KNOWN_IDENTITY_POSITION_MISSING", fixture_id, sid)
            player = owner_of(obj["owner_seat"], fixture_id)
            slot = union.setdefault((viewer, player), {})
            current = slot.setdefault(position, obj["card_name"])
            if current != obj["card_name"]:
                fail("WS49_NORMALIZE_KNOWN_IDENTITY_CONFLICT", fixture_id, sid)
    return union


def verify_known_library(
    record: dict[str, Any],
    proof: dict[str, Any],
    views: dict[str, dict[str, Any]],
    privileged: dict[str, dict[str, Any]],
    viewer_states: list[dict[str, Any]],
) -> None:
    fixture_id = record["fixture_id"]
    union = expected_known_union(viewer_states, privileged, fixture_id)
    for viewer, view in sorted(views.items()):
        for pid in sorted(player_bucket_player_ids(view, fixture_id, viewer)):
            entry = player_bucket(view, pid, fixture_id, viewer)
            shown = entry.get("known_library")
            if not isinstance(shown, list):
                fail(
                    "WS49_NORMALIZE_KNOWN_LIBRARY_NOT_LIST",
                    fixture_id,
                    {"viewer": viewer, "player": pid},
                )
            expected = union.get((viewer, pid), {})
            if len(shown) != len(expected):
                fail(
                    "WS49_NORMALIZE_KNOWN_LIBRARY_SIZE_MISMATCH",
                    fixture_id,
                    {
                        "viewer": viewer,
                        "player": pid,
                        "native": len(shown),
                        "expected": len(expected),
                    },
                )
            seen_positions: set[int] = set()
            for item in shown:
                if not isinstance(item, dict):
                    fail("WS49_NORMALIZE_KNOWN_LIBRARY_ENTRY_INVALID", fixture_id, item)
                position = item.get("position_from_top")
                name = item.get("name")
                if (
                    not isinstance(position, int)
                    or isinstance(position, bool)
                    or position in seen_positions
                ):
                    fail("WS49_NORMALIZE_KNOWN_LIBRARY_POSITION_INVALID", fixture_id, item)
                if not isinstance(name, str) or not name:
                    fail("WS49_NORMALIZE_KNOWN_LIBRARY_NAME_INVALID", fixture_id, item)
                seen_positions.add(position)
            if seen_positions != set(expected):
                fail(
                    "WS49_NORMALIZE_KNOWN_LIBRARY_POSITIONS_MISMATCH",
                    fixture_id,
                    {"viewer": viewer, "player": pid},
                )
            # Names at privileged-covered positions must match physical truth.
            # Substrate positions (no privileged counterpart) carry native
            # facts the contract deliberately leaves unspecified; structure
            # and audience are verified, identities recorded.
            priv_by_position = {
                obj["zone_position"]: obj
                for obj in privileged.values()
                if obj.get("zone") == "library"
                and owner_of(obj["owner_seat"], fixture_id) == pid
                and isinstance(obj.get("zone_position"), int)
            }
            for item in shown:
                position = item["position_from_top"]
                counterpart = priv_by_position.get(position)
                if counterpart is not None and item["name"] != counterpart["card_name"]:
                    fail(
                        "WS49_NORMALIZE_KNOWN_LIBRARY_NAME_MISMATCH",
                        fixture_id,
                        {"viewer": viewer, "player": pid, "position": position},
                    )
                pinned = expected.get(position)
                if pinned is not None and item["name"] != pinned:
                    fail(
                        "WS49_NORMALIZE_KNOWN_IDENTITY_NAME_MISMATCH",
                        fixture_id,
                        {"viewer": viewer, "player": pid, "position": position},
                    )
    # Native library-count coherence: granted ranges never shrink the native
    # library; substrate fills exactly to the largest granted end.
    pids = sorted(player_bucket_player_ids(next(iter(views.values())), fixture_id, "count"))
    for pid in pids:
        priv_count = sum(
            1
            for obj in privileged.values()
            if obj.get("zone") == "library" and owner_of(obj["owner_seat"], fixture_id) == pid
        )
        granted_end = 0
        for (_viewer, player), slots in union.items():
            if player == pid and slots:
                granted_end = max(granted_end, max(slots) + 1)
        for viewer, view in sorted(views.items()):
            count = player_bucket(view, pid, fixture_id, viewer).get("library_count")
            if count != max(priv_count, granted_end):
                fail(
                    "WS49_NORMALIZE_LIBRARY_COUNT_INCOHERENT",
                    fixture_id,
                    {
                        "player": pid,
                        "native": count,
                        "privileged": priv_count,
                        "granted_end": granted_end,
                    },
                )


def player_bucket_player_ids(view: dict[str, Any], fixture_id: str, viewer: str) -> list[str]:
    players = view.get("players")
    if not isinstance(players, list) or not players:
        fail("WS49_NORMALIZE_VIEW_PLAYERS_MISSING", fixture_id, viewer)
    ids: list[str] = []
    for player in players:
        if not isinstance(player, dict) or not isinstance(player.get("player_id"), str):
            fail("WS49_NORMALIZE_VIEW_PLAYER_ID_INVALID", fixture_id, viewer)
        if player["player_id"] in ids:
            fail("WS49_NORMALIZE_VIEW_PLAYER_DUPLICATE", fixture_id, viewer)
        ids.append(player["player_id"])
    return ids


def controllers_of(record: dict[str, Any], views: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Map each player to its native turn controller (self by default)."""
    fixture_id = record["fixture_id"]
    result: dict[str, str] = {}
    for viewer, view in sorted(views.items()):
        for pid in player_bucket_player_ids(view, fixture_id, viewer):
            entry = player_bucket(view, pid, fixture_id, viewer)
            controller = entry.get("turn_controlled_by")
            if not isinstance(controller, str) or not controller:
                fail(
                    "WS49_NORMALIZE_TURN_CONTROLLER_INVALID",
                    fixture_id,
                    {"viewer": viewer, "player": pid},
                )
            if pid in result and result[pid] != controller:
                fail("WS49_NORMALIZE_TURN_CONTROLLER_DISAGREEMENT", fixture_id, pid)
            result[pid] = controller
    for state in record["knowledge_state"].get("viewer_states") or []:
        for permission in state.get("temporary_permissions") or []:
            if not isinstance(permission, dict):
                continue
            if "controlled_player" in permission and "controller" in permission:
                expected = str(permission["controller"])
                actual = result.get(str(permission["controlled_player"]))
                if actual != expected:
                    fail(
                        "WS49_NORMALIZE_CONTROL_GRANT_NOT_NATIVE",
                        fixture_id,
                        {
                            "player": permission.get("controlled_player"),
                            "native": actual,
                            "expected": expected,
                        },
                    )
    return result


def verify_zone_buckets(
    record: dict[str, Any],
    proof: dict[str, Any],
    views: dict[str, dict[str, Any]],
    privileged: dict[str, dict[str, Any]],
    controllers: dict[str, str],
) -> None:
    """Verify per-viewer displayed identities for every physical zone bucket.

    Entitlement model: public zones to all viewers; hands to owner plus native
    turn controller; libraries to granted ranges only; face-down permanents to
    controller plus explicit look grants; face-down exile to explicit look
    grants only (not even the owner).
    """
    fixture_id = record["fixture_id"]
    look_grants: dict[str, set[str]] = {}
    for state in record["knowledge_state"].get("viewer_states") or []:
        viewer = state.get("viewer")
        for grant in state.get("face_down_look_permissions") or []:
            if not isinstance(grant, dict) or grant.get("scope") != "identity":
                fail("WS49_NORMALIZE_LOOK_GRANT_INVALID", fixture_id, grant)
            look_grants.setdefault(str(grant["object"]), set()).add(str(viewer))
        for permission in state.get("temporary_permissions") or []:
            if not isinstance(permission, dict):
                continue
            kind = permission.get("permission")
            if kind in ("look", "look_at_face_down_exile") and "object" in permission:
                look_grants.setdefault(str(permission["object"]), set()).add(
                    str(permission["viewer"])
                )
            elif kind in ("look", "look_at_face_down_exile", "reveal", "search") or (
                "controlled_player" in permission
            ):
                pass
            else:
                fail("WS49_NORMALIZE_PERMISSION_KIND_INVALID", fixture_id, permission)
    priv_by_owner_zone: dict[tuple[str, str], list[dict[str, Any]]] = {}
    priv_battlefield_by_controller: dict[str, list[dict[str, Any]]] = {}
    for sid, obj in privileged.items():
        owner = owner_of(obj["owner_seat"], fixture_id)
        # Same provider-neutral spelling convention as the shared base:
        # native 'exiled' normalizes to requested 'exile'.
        zone = "exile" if obj["zone"] == "exiled" else obj["zone"]
        priv_by_owner_zone.setdefault((owner, zone), []).append({"sid": sid, **obj})
        if obj["zone"] == "battlefield":
            # Battlefield view buckets list controlled permanents, not owned
            # ones; ownership splits (Control Magic and friends) live here.
            if "controller_seat" not in obj:
                fail("WS49_NORMALIZE_BATTLEFIELD_CONTROLLER_MISSING", fixture_id, sid)
            controller = owner_of(obj["controller_seat"], fixture_id)
            priv_battlefield_by_controller.setdefault(controller, []).append({"sid": sid, **obj})
    for viewer, view in sorted(views.items()):
        for pid in player_bucket_player_ids(view, fixture_id, viewer):
            entry = player_bucket(view, pid, fixture_id, viewer)
            verify_hand_bucket(entry, viewer, pid, priv_by_owner_zone, controllers, fixture_id)
            verify_battlefield_bucket(
                entry, viewer, pid, priv_battlefield_by_controller, record, fixture_id
            )
            verify_name_list_bucket(
                entry, viewer, pid, priv_by_owner_zone, record, fixture_id, "exile"
            )
            verify_name_list_bucket(
                entry, viewer, pid, priv_by_owner_zone, record, fixture_id, "graveyard"
            )
            verify_command_bucket(entry, viewer, pid, record, proof, fixture_id)
            verify_remembered_bucket(entry, viewer, pid, record, privileged, fixture_id)


def verify_hand_bucket(
    entry: dict[str, Any],
    viewer: str,
    pid: str,
    priv_by_owner_zone: dict[tuple[str, str], list[dict[str, Any]]],
    controllers: dict[str, str],
    fixture_id: str,
) -> None:
    listed = entry.get("hand")
    entitled = viewer == pid or controllers.get(pid) == viewer
    priv_names = sorted(o["card_name"] for o in priv_by_owner_zone.get((pid, "hand"), []))
    if entry.get("hand_count") != len(priv_names):
        fail(
            "WS49_NORMALIZE_HAND_COUNT_INCOHERENT",
            fixture_id,
            {
                "viewer": viewer,
                "player": pid,
                "native": entry.get("hand_count"),
                "privileged": len(priv_names),
            },
        )
    if not entitled:
        if listed is not None:
            fail(
                "WS49_NORMALIZE_HAND_LEAKED_TO_NON_ENTITLED",
                fixture_id,
                {"viewer": viewer, "player": pid},
            )
        return
    if not isinstance(listed, list):
        fail(
            "WS49_NORMALIZE_HAND_NOT_LISTED_TO_ENTITLED",
            fixture_id,
            {"viewer": viewer, "player": pid},
        )
    shown = sorted(
        item.get("name")
        for item in listed
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    )
    if len(shown) != len(listed) or shown != priv_names:
        fail(
            "WS49_NORMALIZE_HAND_IDENTITIES_MISMATCH",
            fixture_id,
            {"viewer": viewer, "player": pid, "native": shown, "privileged": priv_names},
        )
    for item in listed:
        if item.get("face_down") is not False:
            fail("WS49_NORMALIZE_HAND_FACE_DOWN_FLAG_INVALID", fixture_id, item)


def verify_name_list_bucket(
    entry: dict[str, Any],
    viewer: str,
    pid: str,
    priv_by_owner_zone: dict[tuple[str, str], list[dict[str, Any]]],
    record: dict[str, Any],
    fixture_id: str,
    zone: str,
) -> None:
    listed = entry.get(zone)
    priv = priv_by_owner_zone.get((pid, zone), [])
    count_key = {
        "battlefield": None,
        "exile": "exile_count",
        "graveyard": "graveyard_count",
        "command": None,
    }[zone]
    if count_key is not None and entry.get(count_key) != len(priv):
        fail(
            "WS49_NORMALIZE_ZONE_COUNT_INCOHERENT",
            fixture_id,
            {"viewer": viewer, "player": pid, "zone": zone},
        )
    if not isinstance(listed, list):
        fail(
            "WS49_NORMALIZE_ZONE_BUCKET_NOT_LIST",
            fixture_id,
            {"viewer": viewer, "player": pid, "zone": zone},
        )
    if len(listed) != len(priv):
        fail(
            "WS49_NORMALIZE_ZONE_BUCKET_SIZE_MISMATCH",
            fixture_id,
            {
                "viewer": viewer,
                "player": pid,
                "zone": zone,
                "native": len(listed),
                "privileged": len(priv),
            },
        )
    # Every privileged card is consumed exactly once: a true-name entry
    # consumes its identical, a redacted entry consumes one unmatched
    # face-down card. Face-down identities are entitled only to the native
    # controller or an explicit look grant (face-down exile: look grants
    # only, never the owner). Redacted entries are processed last so a
    # redaction can never consume a card the viewer is entitled to see:
    # over-redaction fails closed instead of masking.
    unmatched = list(priv)
    ordered = sorted(
        listed,
        key=lambda item: (
            1
            if isinstance(item, dict)
            and item.get("face_down") is True
            and item.get("name") == REDACTED_CARD_LABEL
            else 0
        ),
    )
    for item in ordered:
        if not isinstance(item, dict):
            fail("WS49_NORMALIZE_ZONE_ENTRY_INVALID", fixture_id, item)
        name = item.get("name")
        face_down = item.get("face_down")
        if face_down is True and name == REDACTED_CARD_LABEL:
            consumed = next((o for o in unmatched if o.get("face_down") is True), None)
            if consumed is None:
                fail("WS49_NORMALIZE_REDACTION_WITHOUT_FACE_DOWN", fixture_id, item)
            if _look_granted(record, consumed["sid"], viewer):
                fail("WS49_NORMALIZE_REDACTED_DESPITE_LOOK_GRANT", fixture_id, item)
            controller = consumed.get("controller_seat")
            if controller is not None and viewer == owner_of(controller, fixture_id):
                fail("WS49_NORMALIZE_REDACTED_TO_CONTROLLER", fixture_id, item)
            unmatched.remove(consumed)
            continue
        if face_down is True:
            match = next(
                (o for o in unmatched if o.get("face_down") is True and o["card_name"] == name),
                None,
            )
            if match is None:
                fail("WS49_NORMALIZE_FACE_DOWN_IDENTITY_UNENTITLED", fixture_id, item)
            controller = (
                owner_of(match["controller_seat"], fixture_id)
                if "controller_seat" in match
                else None
            )
            if viewer != controller and not _look_granted(record, match["sid"], viewer):
                fail("WS49_NORMALIZE_FACE_DOWN_IDENTITY_UNENTITLED", fixture_id, item)
            unmatched.remove(match)
        else:
            match = next(
                (o for o in unmatched if o.get("face_down") is not True and o["card_name"] == name),
                None,
            )
            if match is None:
                fail("WS49_NORMALIZE_ZONE_IDENTITY_MISMATCH", fixture_id, item)
            unmatched.remove(match)
    if unmatched:
        fail(
            "WS49_NORMALIZE_ZONE_BUCKET_UNMATCHED_PRIVILEGED",
            fixture_id,
            [o["sid"] for o in unmatched],
        )


def verify_battlefield_bucket(
    entry: dict[str, Any],
    viewer: str,
    pid: str,
    priv_by_controller: dict[str, list[dict[str, Any]]],
    record: dict[str, Any],
    fixture_id: str,
) -> None:
    """Battlefield view buckets list controlled permanents.

    Same consume-exactly-once identity logic as owner buckets, keyed by
    native controller instead of owner, plus per-entry controller_id/owner_id
    verification against the privileged native seats.
    """
    listed = entry.get("battlefield")
    priv = priv_by_controller.get(pid, [])
    if not isinstance(listed, list):
        fail(
            "WS49_NORMALIZE_BATTLEFIELD_BUCKET_NOT_LIST",
            fixture_id,
            {"viewer": viewer, "player": pid},
        )
    if len(listed) != len(priv):
        fail(
            "WS49_NORMALIZE_BATTLEFIELD_BUCKET_SIZE_MISMATCH",
            fixture_id,
            {
                "viewer": viewer,
                "player": pid,
                "native": len(listed),
                "privileged": len(priv),
            },
        )
    unmatched = list(priv)
    # Redacted entries are processed last so a redaction can never consume a
    # card the viewer is entitled to see: over-redaction fails closed.
    ordered = sorted(
        listed,
        key=lambda item: (
            1
            if isinstance(item, dict)
            and item.get("face_down") is True
            and item.get("name") == REDACTED_CARD_LABEL
            else 0
        ),
    )
    for item in ordered:
        if not isinstance(item, dict):
            fail("WS49_NORMALIZE_BATTLEFIELD_ENTRY_INVALID", fixture_id, item)
        name = item.get("name")
        face_down = item.get("face_down")
        owner_id = item.get("owner_id")
        if face_down is True and name == REDACTED_CARD_LABEL:
            consumed = next(
                (
                    o
                    for o in unmatched
                    if o.get("face_down") is True
                    and owner_of(o["owner_seat"], fixture_id) == owner_id
                ),
                None,
            )
            if consumed is None:
                fail("WS49_NORMALIZE_BATTLEFIELD_REDACTION_WITHOUT_FACE_DOWN", fixture_id, item)
            if _look_granted(record, consumed["sid"], viewer):
                fail("WS49_NORMALIZE_BATTLEFIELD_REDACTED_DESPITE_LOOK_GRANT", fixture_id, item)
            if viewer == owner_of(consumed["controller_seat"], fixture_id):
                fail("WS49_NORMALIZE_BATTLEFIELD_REDACTED_TO_CONTROLLER", fixture_id, item)
            check_battlefield_seat_ids(item, consumed, pid, fixture_id)
            unmatched.remove(consumed)
            continue
        if face_down is True:
            match = next(
                (
                    o
                    for o in unmatched
                    if o.get("face_down") is True
                    and o["card_name"] == name
                    and owner_of(o["owner_seat"], fixture_id) == owner_id
                ),
                None,
            )
            if match is None:
                fail("WS49_NORMALIZE_BATTLEFIELD_FACE_DOWN_UNENTITLED", fixture_id, item)
            controller = owner_of(match["controller_seat"], fixture_id)
            if viewer != controller and not _look_granted(record, match["sid"], viewer):
                fail("WS49_NORMALIZE_BATTLEFIELD_FACE_DOWN_UNENTITLED", fixture_id, item)
            check_battlefield_seat_ids(item, match, pid, fixture_id)
            unmatched.remove(match)
        else:
            match = next(
                (
                    o
                    for o in unmatched
                    if o.get("face_down") is not True
                    and o["card_name"] == name
                    and owner_of(o["owner_seat"], fixture_id) == owner_id
                ),
                None,
            )
            if match is None:
                fail("WS49_NORMALIZE_BATTLEFIELD_IDENTITY_MISMATCH", fixture_id, item)
            check_battlefield_seat_ids(item, match, pid, fixture_id)
            unmatched.remove(match)
    if unmatched:
        fail(
            "WS49_NORMALIZE_BATTLEFIELD_BUCKET_UNMATCHED_PRIVILEGED",
            fixture_id,
            [o["sid"] for o in unmatched],
        )


def check_battlefield_seat_ids(
    item: dict[str, Any], match: dict[str, Any], pid: str, fixture_id: str
) -> None:
    """The displayed controller/owner refs must equal the privileged seats."""
    if item.get("controller_id") != pid:
        fail("WS49_NORMALIZE_BATTLEFIELD_CONTROLLER_ID_MISMATCH", fixture_id, item)
    if item.get("owner_id") != owner_of(match["owner_seat"], fixture_id):
        fail("WS49_NORMALIZE_BATTLEFIELD_OWNER_ID_MISMATCH", fixture_id, item)


def verify_command_bucket(
    entry: dict[str, Any],
    viewer: str,
    pid: str,
    record: dict[str, Any],
    proof: dict[str, Any],
    fixture_id: str,
) -> None:
    """View command zones list exactly the commanders natively in command.

    Commanders live outside scenario_objects; presence is proven by the
    native command-zone listing cross-checked against commander history
    (identity + owner seat) and the requested command-zone population.
    """
    del viewer
    listed = entry.get("command")
    if not isinstance(listed, list):
        fail("WS49_NORMALIZE_COMMAND_BUCKET_NOT_LIST", fixture_id, pid)
    try:
        history = v103.native_commander_history(proof, fixture_id)
    except RuntimeError as exc:
        raise RuntimeError(f"WS49_NORMALIZE_COMMAND_HISTORY:{fixture_id}:{exc}") from exc
    expected: list[str] = []
    for metadata in record["commander_state"]["commanders"]:
        if metadata.get("owner") != pid or metadata.get("zone") != "command":
            continue
        cid = metadata.get("commander_id")
        native_history = history.get(cid)
        if native_history is None:
            fail("WS49_NORMALIZE_COMMAND_HISTORY_ID_MISSING", fixture_id, cid)
        if owner_of(native_history["seat"], fixture_id) != pid:
            fail("WS49_NORMALIZE_COMMAND_HISTORY_OWNER_MISMATCH", fixture_id, cid)
        if native_history.get("card_name") != metadata.get("card_identity"):
            fail("WS49_NORMALIZE_COMMAND_HISTORY_IDENTITY_MISMATCH", fixture_id, cid)
        expected.append(str(metadata["card_identity"]))
    shown: list[str] = []
    for item in listed:
        if not isinstance(item, dict):
            fail("WS49_NORMALIZE_COMMAND_ENTRY_INVALID", fixture_id, pid)
        if item.get("face_down") is not False:
            fail("WS49_NORMALIZE_COMMAND_FACE_DOWN", fixture_id, pid)
        name = item.get("name")
        if not isinstance(name, str) or not name:
            fail("WS49_NORMALIZE_COMMAND_NAME_INVALID", fixture_id, pid)
        shown.append(name)
    if sorted(shown) != sorted(expected):
        fail(
            "WS49_NORMALIZE_COMMAND_BUCKET_MISMATCH",
            fixture_id,
            {"player": pid, "native": sorted(shown), "expected": sorted(expected)},
        )


def _look_granted(record: dict[str, Any], sid: str, viewer: str) -> bool:
    for state in record["knowledge_state"].get("viewer_states") or []:
        for grant in state.get("face_down_look_permissions") or []:
            if (
                isinstance(grant, dict)
                and str(grant.get("object")) == sid
                and str(grant.get("viewer")) == viewer
            ):
                return True
        for permission in state.get("temporary_permissions") or []:
            if not isinstance(permission, dict):
                continue
            if (
                permission.get("permission") in ("look", "look_at_face_down_exile")
                and str(permission.get("object")) == sid
                and str(permission.get("viewer")) == viewer
            ):
                return True
    return False


def verify_remembered_bucket(
    entry: dict[str, Any],
    viewer: str,
    pid: str,
    record: dict[str, Any],
    privileged: dict[str, dict[str, Any]],
    fixture_id: str,
) -> None:
    remembered = entry.get("remembered_library_composition")
    if not isinstance(remembered, list):
        fail("WS49_NORMALIZE_REMEMBERED_NOT_LIST", fixture_id, {"viewer": viewer, "player": pid})
    search_granted = any(
        isinstance(permission, dict)
        and permission.get("permission") == "search"
        and str(permission.get("viewer")) == viewer
        and str(permission.get("zone")) == f"{viewer}.library"
        for state in record["knowledge_state"].get("viewer_states") or []
        for permission in state.get("temporary_permissions") or []
    )
    if viewer == pid and search_granted:
        expected = sorted(
            obj["card_name"]
            for obj in privileged.values()
            if obj.get("zone") == "library" and owner_of(obj["owner_seat"], fixture_id) == pid
        )
        if sorted(remembered) != expected:
            fail(
                "WS49_NORMALIZE_REMEMBERED_COMPOSITION_MISMATCH",
                fixture_id,
                {"viewer": viewer, "player": pid},
            )
    elif remembered != []:
        fail(
            "WS49_NORMALIZE_REMEMBERED_LEAK",
            fixture_id,
            {"viewer": viewer, "player": pid, "native": remembered},
        )


def verify_view_stacks(
    views: dict[str, dict[str, Any]],
    proof: dict[str, Any],
    privileged: dict[str, dict[str, Any]],
    fixture_id: str,
) -> None:
    """View-stack entries must show exactly the natively stacked sources in
    order (or the face-down redaction): no private identity may leak through
    stack surfaces and no stacked source may be hidden."""
    native = proof.get("native_validation")
    stack = native.get("stack_state") if isinstance(native, dict) else None
    if not isinstance(stack, dict) or stack.get("valid") is not True:
        fail("WS49_NORMALIZE_VIEW_STACK_VALIDATION_MISSING", fixture_id)
    native_spells = stack.get("objects_top_to_bottom") or []
    if int(stack.get("stack_count", -1)) != len(native_spells):
        fail("WS49_NORMALIZE_VIEW_STACK_COUNT_INCOHERENT", fixture_id)
    expected_names: list[str] = []
    for spell in native_spells:
        if not isinstance(spell, dict) or not isinstance(spell.get("source_semantic_id"), str):
            fail("WS49_NORMALIZE_VIEW_STACK_SOURCE_INVALID", fixture_id, spell)
        source = privileged.get(spell["source_semantic_id"])
        if source is None:
            fail("WS49_NORMALIZE_VIEW_STACK_SOURCE_UNMAPPED", fixture_id, spell)
        expected_names.append(source["card_name"])
    for viewer, view in sorted(views.items()):
        shown = view.get("stack")
        if not isinstance(shown, list):
            fail("WS49_NORMALIZE_VIEW_STACK_NOT_LIST", fixture_id, viewer)
        if len(shown) != len(expected_names):
            fail("WS49_NORMALIZE_VIEW_STACK_SIZE_MISMATCH", fixture_id, viewer)
        for item, expected in zip(shown, expected_names, strict=True):
            if not isinstance(item, dict):
                fail("WS49_NORMALIZE_VIEW_STACK_ENTRY_INVALID", fixture_id, viewer)
            name = item.get("name")
            if name == "Face-down spell":
                continue
            if name != expected:
                fail(
                    "WS49_NORMALIZE_VIEW_STACK_NAME_MISMATCH",
                    fixture_id,
                    {"viewer": viewer, "native": name, "expected": expected},
                )


def verify_control_view_equality(
    record: dict[str, Any],
    views: dict[str, dict[str, Any]],
    controllers: dict[str, str],
) -> None:
    """A decision authority acting for a controlled player must see exactly
    the controlled player's own zone picture: nothing more, nothing less."""
    fixture_id = record["fixture_id"]
    controlled = [pid for pid, controller in controllers.items() if controller != pid]
    if not controlled:
        return
    for pid in controlled:
        controller = controllers[pid]
        own = (
            player_bucket(views[controller], pid, fixture_id, controller)
            if controller in views
            else None
        )
        ref = player_bucket(views[pid], pid, fixture_id, pid) if pid in views else None
        if own is None or ref is None:
            fail("WS49_NORMALIZE_CONTROL_VIEW_MISSING", fixture_id, pid)
        for key in ("battlefield", "command", "exile", "graveyard", "hand", "known_library"):
            mine = own.get(key)
            theirs = ref.get(key)
            if mine is None and theirs is None:
                continue
            if json.dumps(mine, sort_keys=True) != json.dumps(theirs, sort_keys=True):
                fail(
                    "WS49_NORMALIZE_CONTROL_VIEW_EXCEEDS_ENTITLEMENT",
                    fixture_id,
                    {"controller": controller, "player": pid, "zone": key},
                )


def normalize_knowledge_state(record: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    requested = record.get("knowledge_state")
    if not isinstance(requested, dict):
        fail("WS49_NORMALIZE_KNOWLEDGE_REQUESTED_MISSING", fixture_id)
    if not isinstance(requested.get("channel_policy"), str) or not requested["channel_policy"]:
        fail("WS49_NORMALIZE_KNOWLEDGE_CHANNEL_POLICY_INVALID", fixture_id)
    viewer_states = requested.get("viewer_states")
    if not isinstance(viewer_states, list) or not viewer_states:
        fail("WS49_NORMALIZE_KNOWLEDGE_VIEWER_STATES_INVALID", fixture_id)
    seen_viewers: set[str] = set()
    for state in viewer_states:
        if not isinstance(state, dict):
            fail("WS49_NORMALIZE_KNOWLEDGE_VIEWER_STATE_INVALID", fixture_id, state)
        viewer = state.get("viewer")
        if not isinstance(viewer, str) or viewer in seen_viewers:
            fail("WS49_NORMALIZE_KNOWLEDGE_VIEWER_INVALID", fixture_id, viewer)
        seen_viewers.add(viewer)
        unknown = (
            set(state)
            - set(DYNAMIC_GRANT_KEYS)
            - {
                "viewer",
                "channels_under_test",
                "honey_sentinels",
                "invalidation_conditions",
                "obligation",
                "ordered_known_information",
                "permitted_public_metadata",
                "prohibited_metadata",
            }
        )
        if unknown:
            fail("WS49_NORMALIZE_KNOWLEDGE_FIELD_UNCLASSIFIED", fixture_id, sorted(unknown))
        for key in KNOWLEDGE_METADATA_STRING_LIST_KEYS:
            if key not in state:
                continue
            value = state[key]
            if key == "obligation":
                if not isinstance(value, str) or not value:
                    fail("WS49_NORMALIZE_KNOWLEDGE_OBLIGATION_INVALID", fixture_id)
                continue
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                fail("WS49_NORMALIZE_KNOWLEDGE_METADATA_INVALID", fixture_id, key)
    views = native_views_by_player(proof, fixture_id)
    for viewer in seen_viewers:
        if viewer not in views:
            fail("WS49_NORMALIZE_KNOWLEDGE_VIEWER_MISSING_NATIVE", fixture_id, viewer)
    privileged = privileged_zone_index(proof, fixture_id)
    # Sentinel hygiene across the whole readback surface.
    if HONEY_SENTINEL in json.dumps(proof, sort_keys=True):
        fail("WS49_NORMALIZE_HONEY_SENTINEL_LEAKED", fixture_id)
    for sentinel_state in viewer_states:
        for sentinel in sentinel_state.get("honey_sentinels") or []:
            if sentinel in json.dumps(proof, sort_keys=True):
                fail("WS49_NORMALIZE_HONEY_SENTINEL_LEAKED", fixture_id, sentinel)
    verify_known_library(record, proof, views, privileged, viewer_states)
    controllers = controllers_of(record, views)
    verify_zone_buckets(record, proof, views, privileged, controllers)
    verify_control_view_equality(record, views, controllers)
    verify_view_stacks(views, proof, privileged, fixture_id)
    verify_reveal_audience(record, proof, views, privileged, fixture_id)
    normalized_states: list[dict[str, Any]] = []
    for state in viewer_states:
        normalized_states.append(copy.deepcopy(state))
    return {"channel_policy": requested["channel_policy"], "viewer_states": normalized_states}


def view_zone_names(view: dict[str, Any], fixture_id: str) -> list[str]:
    """All card names displayed anywhere in one actor view (zone entries)."""
    names: list[str] = []
    for player in view.get("players") or []:
        if not isinstance(player, dict):
            fail("WS49_NORMALIZE_REVEAL_VIEW_PLAYER_INVALID", fixture_id)
        for key in ("battlefield", "command", "exile", "graveyard", "hand", "known_library"):
            bucket = player.get(key)
            if bucket is None:
                continue
            if not isinstance(bucket, list):
                fail("WS49_NORMALIZE_REVEAL_VIEW_BUCKET_INVALID", fixture_id, key)
            for item in bucket:
                if not isinstance(item, dict):
                    fail("WS49_NORMALIZE_REVEAL_VIEW_ENTRY_INVALID", fixture_id, key)
                name = item.get("name")
                if isinstance(name, str) and name and name != REDACTED_CARD_LABEL:
                    names.append(name)
    return names


def verify_reveal_audience(
    record: dict[str, Any],
    proof: dict[str, Any],
    views: dict[str, dict[str, Any]],
    privileged: dict[str, dict[str, Any]],
    fixture_id: str,
) -> None:
    """Reveal-to-audience grants must either be natively executed (revealed
    set contains the object) or carried as unexercised behavior-stage policy
    with snapshot partitioning intact (owner-only visibility)."""
    native = proof.get("native_validation")
    revealed = native.get("ws42_revealed_state") if isinstance(native, dict) else None
    if not isinstance(revealed, dict) or revealed.get("valid") is not True:
        fail("WS49_NORMALIZE_REVEALED_VALIDATION_MISSING", fixture_id)
    if revealed.get("native_surface") != "GameState.getRevealed":
        fail("WS49_NORMALIZE_REVEALED_NATIVE_SURFACE_MISMATCH", fixture_id)
    if revealed.get("physical_zone_fabricated") is not False:
        fail("WS49_NORMALIZE_REVEALED_PHYSICAL_ZONE_FABRICATED", fixture_id)
    native_set = set()
    for row in revealed.get("semantic_revealed_objects") or []:
        if not isinstance(row, dict) or row.get("native_revealed") is not True:
            fail("WS49_NORMALIZE_REVEALED_ROW_INVALID", fixture_id, row)
        sid = row.get("semantic_id")
        if not isinstance(sid, str) or sid in native_set:
            fail("WS49_NORMALIZE_REVEALED_ROW_INVALID", fixture_id, row)
        native_set.add(sid)
    for state in record["knowledge_state"].get("viewer_states") or []:
        for permission in state.get("temporary_permissions") or []:
            if not isinstance(permission, dict) or permission.get("permission") != "reveal":
                continue
            if permission.get("viewer") != "ALL_PLAYERS" or "object" not in permission:
                fail("WS49_NORMALIZE_REVEAL_AUDIENCE_UNSUPPORTED", fixture_id, permission)
            sid = str(permission["object"])
            if sid in native_set:
                continue
            # Unexercised at the setup snapshot: the true identity must not
            # appear in any non-owner view's displayed zone entries.
            obj = privileged.get(sid)
            if obj is None:
                fail("WS49_NORMALIZE_REVEAL_OBJECT_MISSING", fixture_id, sid)
            owner = owner_of(obj["owner_seat"], fixture_id)
            for viewer, view in sorted(views.items()):
                if viewer == owner:
                    continue
                if obj["card_name"] in view_zone_names(view, fixture_id):
                    fail("WS49_NORMALIZE_UNEXERCISED_REVEAL_LEAKED", fixture_id, viewer)


# ---------------------------------------------------------------------------
# NATURAL_GAME_START opening verification battery
#
# The requested deck_state is an entry template, never an opening state, so no
# requested digest can match here. Instead four independent native surfaces
# already present in the readback are federated against the immutable entry
# obligations: (A) preflight native deck readback, (B) native decision
# transcript, (C) native observation query, (D) replay-checkpoint snapshots.
# ---------------------------------------------------------------------------


def parse_natural_template(
    record: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Parse the immutable natural deck template independently of the
    construction translator: two admitted shapes (template list entries and
    direct deck entries), strict field sets, exact Mountain x99 constraint."""
    fixture_id = record["fixture_id"]
    raw = record.get("deck_state")
    if not isinstance(raw, list) or not raw:
        fail("WS49_NORMALIZE_DECK_STATE_NOT_LIST", fixture_id)
    commanders = record.get("commander_state") or {}
    by_id = {}
    for commander in commanders.get("commanders") or []:
        if not isinstance(commander, dict):
            fail("WS49_NORMALIZE_DECK_COMMANDER_ENTRY_INVALID", fixture_id)
        by_id[commander.get("commander_id")] = commander
    result: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            fail("WS49_NORMALIZE_DECK_ENTRY_INVALID", fixture_id, entry)
        player = entry.get("player_id")
        if not isinstance(player, str) or player in result:
            fail("WS49_NORMALIZE_DECK_PLAYER_INVALID", fixture_id, player)
        library = entry.get("library_template")
        commanders_names: list[str] = []
        if isinstance(library, dict):
            if set(entry) != {
                "player_id",
                "library_template",
                "commander_ids",
                "opening_hand_size",
                "shuffle_channel",
            }:
                fail("WS49_NORMALIZE_DECK_TEMPLATE_KEYS_INVALID", fixture_id, sorted(entry))
            if library != {"card_identity": "Mountain", "count": 99}:
                fail("WS49_NORMALIZE_DECK_LIBRARY_TEMPLATE_INVALID", fixture_id, library)
            if entry.get("opening_hand_size") != 7:
                fail(
                    "WS49_NORMALIZE_DECK_OPENING_HAND_INVALID",
                    fixture_id,
                    entry.get("opening_hand_size"),
                )
            if entry.get("shuffle_channel") != f"library_shuffle:{player}":
                fail(
                    "WS49_NORMALIZE_DECK_SHUFFLE_CHANNEL_INVALID",
                    fixture_id,
                    entry.get("shuffle_channel"),
                )
            commander_ids = entry.get("commander_ids")
            if not isinstance(commander_ids, list) or not commander_ids:
                fail("WS49_NORMALIZE_DECK_COMMANDER_IDS_INVALID", fixture_id, commander_ids)
            for cid in commander_ids:
                commander = by_id.get(cid)
                if commander is None or commander.get("owner") != player:
                    fail("WS49_NORMALIZE_DECK_COMMANDER_REFERENCE_INVALID", fixture_id, cid)
                name = commander.get("card_identity")
                if not isinstance(name, str) or not name:
                    fail("WS49_NORMALIZE_DECK_COMMANDER_IDENTITY_INVALID", fixture_id, cid)
                commanders_names.append(name)
            library_name, library_count = "Mountain", 99
        else:
            if set(entry) != {"player_id", "main_deck", "commander", "exact_card_count"}:
                fail("WS49_NORMALIZE_DECK_DIRECT_KEYS_INVALID", fixture_id, sorted(entry))
            if entry.get("main_deck") != [{"card_identity": "Mountain", "count": 99}]:
                fail("WS49_NORMALIZE_DECK_MAIN_DECK_INVALID", fixture_id, entry.get("main_deck"))
            if entry.get("exact_card_count") != 100:
                fail(
                    "WS49_NORMALIZE_DECK_CARD_COUNT_INVALID",
                    fixture_id,
                    entry.get("exact_card_count"),
                )
            direct = entry.get("commander")
            if direct != [{"card_identity": "Rograkh, Son of Rohgahh", "count": 1}]:
                fail("WS49_NORMALIZE_DECK_DIRECT_COMMANDER_INVALID", fixture_id, direct)
            matching = [
                item
                for item in by_id.values()
                if item.get("owner") == player
                and item.get("card_identity") == "Rograkh, Son of Rohgahh"
            ]
            if len(matching) != 1:
                fail("WS49_NORMALIZE_DECK_DIRECT_COMMANDER_MAPPING_INVALID", fixture_id, player)
            commanders_names = ["Rograkh, Son of Rohgahh"]
            library_name, library_count = "Mountain", 99
        result[player] = {
            "library_name": library_name,
            "library_count": library_count,
            "commander_names": sorted(commanders_names),
        }
    expected_players = {p["player_id"] for p in record["players"]}
    if set(result) != expected_players:
        fail("WS49_NORMALIZE_DECK_PLAYERS_MISMATCH", fixture_id, sorted(result))
    return result


def natural_preflight_credentials(
    record: dict[str, Any], probe_row: dict[str, Any]
) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    envelope = probe_row.get("non_echo_native_readback")
    if not isinstance(envelope, dict):
        fail("WS49_NORMALIZE_NATURAL_READBACK_MISSING", fixture_id)
    if envelope.get("request_object_copied_as_proof") is not False:
        fail("WS49_NORMALIZE_REQUEST_ECHO_FLAG_INVALID", fixture_id)
    if envelope.get("legacy_normalized_constructed_state_consumed") is not False:
        fail("WS49_NORMALIZE_LEGACY_STATE_ECHO_CONSUMED", fixture_id)
    if envelope.get("legacy_declared_digest_consumed") is not False:
        fail("WS49_NORMALIZE_LEGACY_DIGEST_CONSUMED", fixture_id)
    if envelope.get("construction_credit_granted") is not False:
        fail("WS49_NORMALIZE_CONSTRUCTION_CREDIT_PRESENT", fixture_id)
    if envelope.get("evidence_class") != READBACK_CLASS:
        fail("WS49_NORMALIZE_READBACK_CLASS_INVALID", fixture_id, envelope.get("evidence_class"))
    if envelope.get("execution_entry_mode") != "NATURAL_GAME_START":
        fail("WS49_NORMALIZE_ENTRY_MODE_MISMATCH", fixture_id)
    runtime = envelope.get("natural_pregame_runtime")
    if not isinstance(runtime, dict):
        fail("WS49_NORMALIZE_NATURAL_RUNTIME_MISSING", fixture_id)
    if runtime.get("request_object_copied_as_proof") is not False:
        fail("WS49_NORMALIZE_NATURAL_REQUEST_ECHO_FLAG_INVALID", fixture_id)
    if runtime.get("native_pregame_boundary") != NATURAL_BOUNDARY:
        fail(
            "WS49_NORMALIZE_NATURAL_BOUNDARY_INVALID",
            fixture_id,
            runtime.get("native_pregame_boundary"),
        )
    preflight = runtime.get("native_preflight")
    if not isinstance(preflight, dict):
        fail("WS49_NORMALIZE_NATURAL_PREFLIGHT_MISSING", fixture_id)
    if preflight.get("valid") is not True or preflight.get("fail_closed") is not True:
        fail("WS49_NORMALIZE_NATURAL_PREFLIGHT_NOT_PASS", fixture_id)
    if preflight.get("execution_entry_mode") != "NATURAL_GAME_START":
        fail("WS49_NORMALIZE_NATURAL_ENTRY_MODE_MISMATCH", fixture_id)
    if not str(preflight.get("validator", "")).startswith("xmage-native-natural-start-preflight/"):
        fail("WS49_NORMALIZE_NATURAL_PREFLIGHT_VALIDATOR_INVALID", fixture_id)
    if preflight.get("request_object_copied_as_readback") is not False:
        fail("WS49_NORMALIZE_NATURAL_PREFLIGHT_ECHO_FLAG_INVALID", fixture_id)
    return runtime


def natural_verify_decks(
    record: dict[str, Any], runtime: dict[str, Any], templates: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """N1: native Deck.getCards/getSideboard readback against the template."""
    fixture_id = record["fixture_id"]
    preflight = runtime["native_preflight"]
    native_decks = preflight.get("native_decks")
    if not isinstance(native_decks, list) or len(native_decks) != len(templates):
        fail("WS49_NORMALIZE_NATURAL_DECKS_INVALID", fixture_id)
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for deck in native_decks:
        if not isinstance(deck, dict):
            fail("WS49_NORMALIZE_NATURAL_DECK_ENTRY_INVALID", fixture_id, deck)
        player = deck.get("player_id")
        if not isinstance(player, str) or player in seen or player not in templates:
            fail("WS49_NORMALIZE_NATURAL_DECK_PLAYER_INVALID", fixture_id, player)
        seen.add(player)
        if deck.get("native_surface") != "Deck.getCards/Deck.getSideboard":
            fail("WS49_NORMALIZE_NATURAL_DECK_SURFACE_INVALID", fixture_id, player)
        template = templates[player]
        if deck.get("native_library_count") != template["library_count"]:
            fail("WS49_NORMALIZE_NATURAL_DECK_COUNT_MISMATCH", fixture_id, player)
        if deck.get("native_library_card_identities") != [template["library_name"]]:
            fail("WS49_NORMALIZE_NATURAL_DECK_IDENTITY_MISMATCH", fixture_id, player)
        if (
            sorted(deck.get("native_commander_card_identities") or [])
            != template["commander_names"]
        ):
            fail("WS49_NORMALIZE_NATURAL_DECK_COMMANDER_MISMATCH", fixture_id, player)
        check = f"{player}:commander+natural-library"
        if check not in (preflight.get("checks") or []):
            fail("WS49_NORMALIZE_NATURAL_DECK_CHECK_MISSING", fixture_id, check)
        normalized.append(
            {
                "player_id": player,
                "native_library_count": int(deck["native_library_count"]),
                "native_library_card_identities": list(deck["native_library_card_identities"]),
                "native_commander_card_identities": sorted(
                    deck["native_commander_card_identities"]
                ),
            }
        )
    normalized.sort(key=lambda row: row["player_id"])
    return normalized


def natural_tape_alignment(
    record: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, dict[str, int]]:
    """N2: native decision transcript aligned event-for-event with the runner
    log and the immutable mulligan plan. Returns per-actor taken/bottomed."""
    fixture_id = record["fixture_id"]
    tape = runtime.get("decision_tape")
    if not isinstance(tape, list) or not tape:
        fail("WS49_NORMALIZE_DECISION_TAPE_INVALID", fixture_id)
    player_count = len(record["players"])
    revisions = [e.get("revision") for e in tape if isinstance(e, dict)]
    if revisions != list(range(1, len(tape) + 1)):
        fail("WS49_NORMALIZE_DECISION_REVISIONS_NOT_CONTIGUOUS", fixture_id, revisions)
    plan_rounds: dict[str, int] = {}
    plan_mulligans: dict[str, int] = {}
    for item in record.get("pregame_decision_plan") or []:
        if not isinstance(item, dict):
            fail("WS49_NORMALIZE_PLAN_ITEM_INVALID", fixture_id, item)
        pid = item.get("player_id")
        if pid not in plan_rounds:
            plan_rounds[pid] = 0
            plan_mulligans[pid] = 0
        plan_rounds[pid] += 1
        if item.get("decision") == "MULLIGAN":
            plan_mulligans[pid] += 1
        elif item.get("decision") != "KEEP":
            fail("WS49_NORMALIZE_PLAN_DECISION_INVALID", fixture_id, item)
    if set(plan_rounds) != {f"P{seat}" for seat in range(1, player_count + 1)}:
        fail("WS49_NORMALIZE_PLAN_PLAYERS_MISMATCH", fixture_id, sorted(plan_rounds))
    semantic = runtime.get("semantic_pregame_decisions")
    if not isinstance(semantic, list):
        fail("WS49_NORMALIZE_SEMANTIC_DECISIONS_INVALID", fixture_id)
    first = tape[0]
    if first.get("decision_kind") != "choose_object" or first.get("result") != "accepted":
        fail("WS49_NORMALIZE_TAPE_FIRST_NOT_STARTING_PLAYER", fixture_id)
    rest = tape[1:]
    if len(rest) != len(semantic):
        fail(
            "WS49_NORMALIZE_TAPE_LOG_LENGTH_MISMATCH",
            fixture_id,
            {"tape": len(rest), "log": len(semantic)},
        )
    taken: dict[str, int] = {pid: 0 for pid in plan_rounds}
    bottomed: dict[str, int] = {pid: 0 for pid in plan_rounds}
    mulligan_events: dict[str, int] = {pid: 0 for pid in plan_rounds}
    for event, logged in zip(rest, semantic, strict=True):
        if not isinstance(event, dict) or not isinstance(logged, dict):
            fail("WS49_NORMALIZE_TAPE_LOG_ENTRY_INVALID", fixture_id)
        if event.get("schema_version") != "semantic-decision/1.0.0":
            fail("WS49_NORMALIZE_TAPE_SCHEMA_INVALID", fixture_id, event.get("schema_version"))
        if event.get("result") != "accepted" or event.get("rejection") is not None:
            fail("WS49_NORMALIZE_TAPE_DECISION_NOT_ACCEPTED", fixture_id, event.get("revision"))
        actor_seat = event.get("actor_seat")
        if not isinstance(actor_seat, int) or not 1 <= actor_seat <= player_count:
            fail("WS49_NORMALIZE_TAPE_ACTOR_SEAT_INVALID", fixture_id, event.get("revision"))
        actor = f"P{actor_seat}"
        if logged.get("actor") != actor:
            fail(
                "WS49_NORMALIZE_TAPE_LOG_ACTOR_MISMATCH",
                fixture_id,
                {"revision": event.get("revision"), "tape": actor, "log": logged.get("actor")},
            )
        kind = event.get("decision_kind")
        if kind != logged.get("native_decision_class"):
            fail("WS49_NORMALIZE_TAPE_LOG_KIND_MISMATCH", fixture_id, event.get("revision"))
        selected = event.get("selected_semantic_option_ids")
        offered = event.get("offered_semantic_option_ids")
        if not isinstance(selected, list) or not selected or not isinstance(offered, list):
            fail("WS49_NORMALIZE_TAPE_OPTIONS_INVALID", fixture_id, event.get("revision"))
        if any(s not in offered for s in selected):
            fail("WS49_NORMALIZE_TAPE_SELECTION_NOT_OFFERED", fixture_id, event.get("revision"))
        if kind == "mulligan":
            if len(selected) != 1:
                fail(
                    "WS49_NORMALIZE_TAPE_MULLIGAN_SELECTION_INVALID",
                    fixture_id,
                    event.get("revision"),
                )
            mulligan_events[actor] += 1
            if logged.get("semantic_decision") == "MULLIGAN":
                taken[actor] += 1
            elif logged.get("semantic_decision") != "KEEP":
                fail("WS49_NORMALIZE_SEMANTIC_MULLIGAN_VALUE_INVALID", fixture_id, logged)
        elif kind == "target":
            bottomed[actor] += len(selected)
            if logged.get("london_bottom_cards") != len(selected):
                fail(
                    "WS49_NORMALIZE_TAPE_LOG_BOTTOM_COUNT_MISMATCH",
                    fixture_id,
                    event.get("revision"),
                )
            proof = logged.get("identical_option_neutrality_proof")
            if not isinstance(proof, dict) or proof.get("distinct_semantic_identities") != 1:
                fail(
                    "WS49_NORMALIZE_BOTTOM_NEUTRALITY_PROOF_MISSING",
                    fixture_id,
                    event.get("revision"),
                )
        else:
            fail("WS49_NORMALIZE_TAPE_KIND_UNSUPPORTED", fixture_id, kind)
    if mulligan_events != plan_rounds:
        fail(
            "WS49_NORMALIZE_MULLIGAN_ROUNDS_MISMATCH",
            fixture_id,
            {"native": mulligan_events, "plan": plan_rounds},
        )
    logged_taken = dict(runtime.get("native_mulligans_taken") or {})
    logged_bottomed = dict(runtime.get("native_london_bottoms_submitted") or {})
    if taken != logged_taken:
        fail("WS49_NORMALIZE_TAKEN_LOG_MISMATCH", fixture_id, {"tape": taken, "log": logged_taken})
    if bottomed != logged_bottomed:
        fail(
            "WS49_NORMALIZE_BOTTOMED_LOG_MISMATCH",
            fixture_id,
            {"tape": bottomed, "log": logged_bottomed},
        )
    for pid in plan_rounds:
        if bottomed[pid] > taken[pid]:
            fail("WS49_NORMALIZE_BOTTOM_EXCEEDS_MULLIGANS", fixture_id, pid)
    total = sum(bottomed.values())
    contract_total = runtime.get("contract_london_bottom_total")
    if contract_total is not None and total != contract_total:
        fail(
            "WS49_NORMALIZE_BOTTOM_TOTAL_MISMATCH",
            fixture_id,
            {"native": total, "contract": contract_total},
        )
    events = runtime.get("event_tape")
    if not isinstance(events, list) or not events:
        fail("WS49_NORMALIZE_EVENT_TAPE_INVALID", fixture_id)
    event_revisions = sorted(e.get("decision_revision") for e in events if isinstance(e, dict))
    if event_revisions != list(range(1, len(tape) + 1)):
        fail("WS49_NORMALIZE_EVENT_REVISIONS_MISMATCH", fixture_id, event_revisions)
    for event_item in events:
        if event_item.get("event_kind") != "external_decision_boundary":
            fail("WS49_NORMALIZE_EVENT_KIND_UNSUPPORTED", fixture_id, event_item.get("event_kind"))
        before = event_item.get("before_checkpoint")
        after = event_item.get("after_checkpoint")
        if not isinstance(before, int) or not isinstance(after, int) or after != before + 1:
            fail(
                "WS49_NORMALIZE_EVENT_CHECKPOINT_LINK_INVALID",
                fixture_id,
                event_item.get("decision_revision"),
            )
    checkpoints = runtime.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        fail("WS49_NORMALIZE_CHECKPOINTS_MISSING", fixture_id)
    if checkpoints[0].get("boundary") != "game_started_or_first_decision":
        fail("WS49_NORMALIZE_FIRST_CHECKPOINT_BOUNDARY_INVALID", fixture_id)
    for event_item in events:
        # Checkpoint references are 1-based indices into the checkpoints list.
        if (
            not 1
            <= event_item["before_checkpoint"]
            < event_item["after_checkpoint"]
            <= len(checkpoints)
        ):
            fail(
                "WS49_NORMALIZE_EVENT_CHECKPOINT_BOUNDS_INVALID",
                fixture_id,
                event_item.get("decision_revision"),
            )
    return {"taken": taken, "bottomed": bottomed}


def natural_opening_coherence(
    record: dict[str, Any], runtime: dict[str, Any], bottomed: dict[str, int]
) -> list[dict[str, Any]]:
    """N3+N4: observation-query state against tape-derived bottoms and against
    the independent replay-checkpoint snapshot."""
    fixture_id = record["fixture_id"]
    player_count = len(record["players"])
    observed = runtime.get("native_public_player_state")
    if not isinstance(observed, list) or len(observed) != player_count:
        fail("WS49_NORMALIZE_OBSERVATION_PLAYERS_INVALID", fixture_id)
    for entry in observed:
        if not isinstance(entry, dict):
            fail("WS49_NORMALIZE_OBSERVATION_ENTRY_INVALID", fixture_id, entry)
    if [p["player_id"] for p in observed] != sorted(bottomed):
        fail("WS49_NORMALIZE_OBSERVATION_PLAYER_SET_INVALID", fixture_id)
    checkpoints = runtime.get("checkpoints") or []
    unions = (checkpoints[-1].get("privileged_state") or {}).get("actor_entitled_union") or []
    if len(unions) != player_count:
        fail("WS49_NORMALIZE_FINAL_UNION_COUNT_INVALID", fixture_id, len(unions))
    normalized: list[dict[str, Any]] = []
    for entry in observed:
        pid = entry.get("player_id")
        hand = 7 - bottomed[pid]
        library = 99 - hand
        if entry.get("hand_count") != hand or entry.get("library_count") != library:
            fail(
                "WS49_NORMALIZE_OPENING_COUNTS_INCOHERENT",
                fixture_id,
                {"player": pid, "native": (entry.get("hand_count"), entry.get("library_count"))},
            )
        if (
            entry.get("life") != 40
            or entry.get("has_lost") is not False
            or entry.get("has_left") is not False
        ):
            fail("WS49_NORMALIZE_OPENING_PLAYER_STATE_INVALID", fixture_id, pid)
        for union in unions:
            matches = [
                p
                for p in (union.get("players") or [])
                if isinstance(p, dict) and p.get("player_id") == pid
            ]
            if len(matches) != 1:
                fail("WS49_NORMALIZE_UNION_PLAYER_MISSING", fixture_id, {"player": pid})
            other = matches[0]
            for key in ("life", "hand_count", "library_count", "has_lost", "has_left"):
                if other.get(key) != entry.get(key):
                    fail(
                        "WS49_NORMALIZE_OBSERVATION_CHECKPOINT_DISAGREE",
                        fixture_id,
                        {"player": pid, "key": key},
                    )
            if other.get("seat", -1) + 1 != int(pid[1:]):
                fail("WS49_NORMALIZE_UNION_SEAT_MISMATCH", fixture_id, pid)
        normalized.append(
            {
                "player_id": pid,
                "seat": int(pid[1:]),
                "life": 40,
                "hand_count": hand,
                "library_count": library,
                "has_lost": False,
                "has_left": False,
            }
        )
    normalized.sort(key=lambda row: row["player_id"])
    return normalized


def natural_commanders_and_objects(
    record: dict[str, Any], runtime: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """N5+N6: command-zone presence from checkpoint unions; zero casts proven
    by the turn-1 pre-action boundary plus decision/event tapes containing
    only pregame decisions."""
    fixture_id = record["fixture_id"]
    checkpoints = runtime.get("checkpoints") or []
    unions = (checkpoints[-1].get("privileged_state") or {}).get("actor_entitled_union") or []
    baseline: dict[str, str] | None = None
    for union in unions:
        current: dict[str, str] = {}
        for player in union.get("players") or []:
            pid = player.get("player_id")
            command = player.get("command")
            if not isinstance(pid, str) or not isinstance(command, list) or len(command) != 1:
                fail("WS49_NORMALIZE_COMMAND_ZONE_INVALID", fixture_id, pid)
            name = command[0].get("name") if isinstance(command[0], dict) else None
            if not isinstance(name, str) or not name or command[0].get("face_down") is not False:
                fail("WS49_NORMALIZE_COMMAND_ZONE_IDENTITY_INVALID", fixture_id, pid)
            current[pid] = name
        if baseline is None:
            baseline = current
        elif current != baseline:
            fail("WS49_NORMALIZE_COMMAND_ZONE_DISAGREEMENT", fixture_id)
    if baseline is None:
        fail("WS49_NORMALIZE_COMMAND_ZONE_EMPTY", fixture_id)
    commanders: list[dict[str, Any]] = []
    for metadata in record["commander_state"]["commanders"]:
        owner = metadata.get("owner")
        if baseline.get(owner) != metadata.get("card_identity"):
            fail(
                "WS49_NORMALIZE_COMMANDER_PRESENCE_MISMATCH",
                fixture_id,
                {"commander": metadata.get("commander_id"), "native": baseline.get(owner)},
            )
        commanders.append(
            {
                "card_identity": baseline[owner],
                "commander_id": metadata.get("commander_id"),
                "owner": owner,
                "prior_command_zone_cast_count": 0,
                "zero_cast_proof": "turn-1-pre-action-boundary-with-pregame-only-tapes",
                "zone": "command",
            }
        )
    objects: list[dict[str, Any]] = []
    for metadata in record.get("semantic_objects") or []:
        if metadata.get("zone") != "command" or not metadata.get("commander_id"):
            fail(
                "WS49_NORMALIZE_NATURAL_OBJECT_SHAPE_UNSUPPORTED",
                fixture_id,
                metadata.get("semantic_id"),
            )
        owner = metadata.get("owner")
        if baseline.get(owner) != metadata.get("card_identity"):
            fail(
                "WS49_NORMALIZE_NATURAL_OBJECT_IDENTITY_MISMATCH",
                fixture_id,
                metadata.get("semantic_id"),
            )
        row = {"semantic_id": metadata["semantic_id"]}
        for key in ("card_lineage_id", "commander_id", "construction_notes"):
            if key in metadata:
                row[key] = copy.deepcopy(metadata[key])
        row.update(
            {
                "card_identity": baseline[owner],
                "controller": owner,
                "counters": {},
                "face_down": False,
                "owner": owner,
                "tapped": False,
                "zone": "command",
            }
        )
        objects.append(row)
    return commanders, objects


def natural_temporal_stack_knowledge_rng(
    record: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """N7+N8+N9+N10+N11: post-pregame temporal wellformedness, knowledge
    vacuity, RNG integrity, empty stack, setup policy."""
    fixture_id = record["fixture_id"]
    checkpoints = runtime.get("checkpoints") or []
    last = (checkpoints[-1].get("privileged_state") or {}).get("actor_entitled_union") or []
    if not last:
        fail("WS49_NORMALIZE_NATURAL_FINAL_UNION_MISSING", fixture_id)
    anchor = last[0]
    temporal = {
        "active_player": anchor.get("active_player_id"),
        "phase": anchor.get("phase"),
        "priority_player": anchor.get("priority_player_id"),
        "step": anchor.get("step"),
        "turn_number": anchor.get("turn_number"),
    }
    if temporal != {
        "active_player": "P1",
        "phase": "beginning",
        "priority_player": "P1",
        "step": "upkeep",
        "turn_number": 1,
    }:
        fail("WS49_NORMALIZE_NATURAL_TEMPORAL_NOT_FIRST_PRIORITY", fixture_id, temporal)
    for union in last:
        if union.get("stack") != []:
            fail("WS49_NORMALIZE_NATURAL_STACK_NOT_EMPTY", fixture_id)
        for player in union.get("players") or []:
            if (
                player.get("known_library") != []
                or player.get("remembered_library_composition") != []
            ):
                fail(
                    "WS49_NORMALIZE_NATURAL_KNOWLEDGE_NOT_VACUOUS",
                    fixture_id,
                    player.get("player_id"),
                )
            if player.get("turn_controlled_by") != player.get("player_id"):
                fail("WS49_NORMALIZE_NATURAL_CONTROL_ANOMALY", fixture_id, player.get("player_id"))
            if player.get("hand") is None and player.get("player_id") == union.get(
                "viewer_player_id"
            ):
                fail("WS49_NORMALIZE_NATURAL_OWN_HAND_ABSENT", fixture_id, player.get("player_id"))
    for state in record["knowledge_state"].get("viewer_states") or []:
        for key in DYNAMIC_GRANT_KEYS:
            if state.get(key):
                fail("WS49_NORMALIZE_NATURAL_GRANT_PRESENT", fixture_id, key)
    tape = runtime.get("rules_rng_tape")
    if not isinstance(tape, dict):
        fail("WS49_NORMALIZE_NATURAL_RNG_TAPE_MISSING", fixture_id)
    if tape.get("schema_version") != "rules-rng-tape/1.0.0":
        fail("WS49_NORMALIZE_NATURAL_RNG_SCHEMA_INVALID", fixture_id)
    if tape.get("authority") != "mage.util.RandomUtil":
        fail("WS49_NORMALIZE_NATURAL_RNG_AUTHORITY_INVALID", fixture_id)
    if tape.get("source_identity") != RNG_TAPE_IDENTITY:
        fail("WS49_NORMALIZE_NATURAL_RNG_SOURCE_IDENTITY_INVALID", fixture_id)
    if tape.get("pilot_rng_mixed") is not False:
        fail("WS49_NORMALIZE_NATURAL_PILOT_RNG_MIXED", fixture_id)
    operations = tape.get("operations")
    if not isinstance(operations, list) or len(operations) < len(record["players"]):
        fail("WS49_NORMALIZE_NATURAL_INITIAL_SHUFFLE_NOT_CAPTURED", fixture_id)
    if int(tape.get("operation_count", -1)) != len(operations):
        fail("WS49_NORMALIZE_NATURAL_RNG_OPERATION_COUNT_MISMATCH", fixture_id)
    seed = tape.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        fail("WS49_NORMALIZE_NATURAL_RNG_SEED_INVALID", fixture_id)
    return {
        "temporal": {
            "active_player": "P1",
            "extra_turn_queue": [],
            "phase": "beginning",
            "priority_player": "P1",
            "step": "upkeep",
            "turn_number": 1,
        },
        "stack_empty": True,
        "knowledge_vacuous": True,
        "rng": {
            "authority": "mage.util.RandomUtil",
            "operation_count": len(operations),
            "pilot_rng_mixed": False,
            "source_identity": RNG_TAPE_IDENTITY,
            "tape_sha256": tape.get("sha256"),
        },
    }


def normalize_record_natural(record: dict[str, Any], probe_row: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    present = {key for key in V105_STATE_KEYS if key in record}
    if frozenset(present) != NATURAL_REQUESTED_KEYS:
        fail("WS49_NORMALIZE_NATURAL_PROFILE_CHANGED", fixture_id, sorted(present))
    if record.get("stack_state") != []:
        fail("WS49_NORMALIZE_NATURAL_REQUESTED_STACK_NONEMPTY", fixture_id)
    runtime = natural_preflight_credentials(record, probe_row)
    templates = parse_natural_template(record)
    decks = natural_verify_decks(record, runtime, templates)
    counts = natural_tape_alignment(record, runtime)
    players = natural_opening_coherence(record, runtime, counts["bottomed"])
    commanders, objects = natural_commanders_and_objects(record, runtime)
    tail = natural_temporal_stack_knowledge_rng(record, runtime)
    if HONEY_SENTINEL in json.dumps(probe_row.get("non_echo_native_readback"), sort_keys=True):
        fail("WS49_NORMALIZE_HONEY_SENTINEL_LEAKED", fixture_id)
    opening = {
        "execution_entry_mode": "NATURAL_GAME_START",
        "players": players,
        "decks": decks,
        "commanders": commanders,
        "commander_damage_matrix": [],
        "semantic_objects": objects,
        "temporal_state": tail["temporal"],
        "knowledge_vacuous": True,
        "stack_empty": True,
        "opening_counts": {
            "mulligans_taken": counts["taken"],
            "bottoms_submitted": counts["bottomed"],
        },
        "contract_london_bottom_total": runtime.get("contract_london_bottom_total"),
        "rng": tail["rng"],
    }
    return {
        "fixture_id": fixture_id,
        "fixture_family": record["fixture_family"],
        "record_digest": record["materialization_digest"],
        "status": PASS_STATUS,
        "requested_state_digest": record["requested_state_digest"],
        "entry_mode": "NATURAL_GAME_START",
        "requested_opening_equality": "NOT_APPLICABLE_ENTRY_TEMPLATE_VERIFIED_ELEMENT_WISE",
        "normalized_native_opening_state": opening,
        "normalized_native_opening_state_digest": canonical_sha(opening),
        "construction_credit_granted": True,
        "behavior_runtime_credit_granted": False,
        "whole_requested_state_object_copied": False,
        "legacy_request_echo_consumed": False,
    }


# ---------------------------------------------------------------------------
# NATIVE_STATE_LOAD record normalization (digest equality)
# ---------------------------------------------------------------------------


def normalize_record_stateload(record: dict[str, Any], probe_row: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    if "deck_state" in record or "continuous_rules_effects" in record:
        fail("WS49_NORMALIZE_STATELOAD_UNEXPECTED_KEYS", fixture_id)
    projection_keys = set(k for k in record if k in (STATE_LOAD_BASE_KEYS | EXTRA_DIMENSION_KEYS))
    if frozenset(projection_keys) not in ADMITTED_STATE_LOAD_PROFILES:
        fail("WS49_NORMALIZE_STATE_PROFILE_UNCLASSIFIED", fixture_id, sorted(projection_keys))
    proof = readback_credentials_stateload(record, probe_row)
    normalized: dict[str, Any] = {"execution_entry_mode": proof["execution_entry_mode"]}
    normalized["players"] = normalize_players_105(record, proof)
    normalized["commander_state"] = normalize_commander_105(record, proof)
    normalized["semantic_objects"] = normalize_semantic_objects_105(record, proof)
    normalized["temporal_state"] = normalize_temporal_105(record, proof)
    normalized["knowledge_state"] = normalize_knowledge_state(record, proof)
    normalized["rules_randomness"] = normalize_randomness_105(record, proof)
    normalized["stack_state"] = normalize_stack_105(record, proof)
    normalized["setup_validation"] = normalize_setup_105(record, proof)
    for key, builder in (
        ("combat_state", normalize_combat_state),
        ("extra_turn_creation", normalize_extra_turns),
        ("elimination_trigger", normalize_elimination),
        ("zone_move_event", normalize_zone_move),
    ):
        value = builder(record, proof)
        if value is not None:
            normalized[key] = value
    requested = requested_state_projection(record)
    normalized_digest = canonical_sha(normalized)
    if normalized_digest != record["requested_state_digest"] or normalized != requested:
        differing = sorted(key for key in requested if normalized.get(key) != requested.get(key))
        fail(
            "WS49_NORMALIZE_REQUESTED_VS_NATIVE_MISMATCH",
            fixture_id,
            {
                "normalized_digest": normalized_digest,
                "requested_digest": record["requested_state_digest"],
                "keys": differing,
            },
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
    }


# ---------------------------------------------------------------------------
# Gate main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = provider_records(contract)
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    if probe.get("materialization_version") != MATERIALIZATION_VERSION:
        fail("WS49_NORMALIZE_PROBE_CONTRACT_MISMATCH", "gate", probe.get("materialization_version"))
    if probe.get("denominator") != 107 or probe.get("record_count") != 107:
        raise RuntimeError("WS49_NORMALIZE_PROBE_DENOMINATOR_MISMATCH")
    if probe.get("legacy_request_echo_accepted_as_proof") is not False:
        raise RuntimeError("WS49_NORMALIZE_PROBE_ACCEPTED_LEGACY_ECHO")
    if probe.get("historical_pass_imported") is not False:
        raise RuntimeError("WS49_NORMALIZE_PROBE_IMPORTED_HISTORICAL_PASS")
    if int(probe.get("historical_successor_runtime_credit", -1)) != 0:
        raise RuntimeError("WS49_NORMALIZE_PROBE_IMPORTED_RUNTIME_CREDIT")
    if probe.get("construction_credit_granted") is not False:
        raise RuntimeError("WS49_NORMALIZE_PROBE_GRANTED_CONSTRUCTION_CREDIT")
    if probe.get("behavior_credit_granted") is not False:
        raise RuntimeError("WS49_NORMALIZE_PROBE_GRANTED_BEHAVIOR_CREDIT")
    if (probe.get("counts") or {}).get(ADMITTED_PROBE_STATUS) != 107:
        raise RuntimeError("WS49_NORMALIZE_PROBE_NOT_FULLY_ADMITTED")

    probe_rows = probe.get("records")
    if not isinstance(probe_rows, list) or len(probe_rows) != 107:
        raise RuntimeError("WS49_NORMALIZE_PROBE_RECORDS_INVALID")
    by_id = {row.get("fixture_id"): row for row in probe_rows}
    if len(by_id) != 107 or None in by_id:
        raise RuntimeError("WS49_NORMALIZE_PROBE_FIXTURE_IDS_INVALID")

    output_rows: list[dict[str, Any]] = []
    pass_count = 0
    for record in records:
        probe_row = by_id.get(record["fixture_id"])
        if probe_row is None:
            raise RuntimeError(f"WS49_NORMALIZE_PROBE_ROW_MISSING:{record['fixture_id']}")
        check_probe_row_identity(record, probe_row)
        mode = record.get("execution_entry_mode")
        if mode == "NATIVE_STATE_LOAD":
            output_rows.append(normalize_record_stateload(record, probe_row))
            pass_count += 1
        elif mode == "NATURAL_GAME_START":
            output_rows.append(normalize_record_natural(record, probe_row))
            pass_count += 1
        else:
            fail("WS49_NORMALIZE_ENTRY_MODE_UNSUPPORTED", record["fixture_id"], mode)

    counts: dict[str, int] = {}
    for row in output_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    if pass_count != 107 or counts != {PASS_STATUS: 107}:
        raise RuntimeError(f"WS49_NORMALIZE_PASS_COUNT_MISMATCH:{pass_count}:{counts}")

    output = {
        "schema_version": SCHEMA_VERSION,
        "materialization_version": MATERIALIZATION_VERSION,
        "candidate_commit": probe.get("candidate_commit"),
        "engine_commit": probe.get("engine_commit"),
        "engine_tree": probe.get("engine_tree"),
        "denominator": 107,
        "record_count": len(output_rows),
        "source_probe_schema": probe.get("schema_version"),
        "source_probe_native_setup_pass": 107,
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
