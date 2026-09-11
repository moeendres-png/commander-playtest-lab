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


def _natural_mulligan_plan(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the complete pregame plan from immutable procedure data.

    The provider never supplies a keep/mulligan default.  Every response must
    be named by the frozen record, either in its explicit pregame plan or in
    the procedure's response-plan step.  Both representations, when present,
    must agree exactly.
    """
    fixture_id = record["fixture_id"]
    plan = record.get("pregame_decision_plan")
    if not isinstance(plan, list) or not plan:
        raise RuntimeError(f"WS49_NATURAL_PREGAME_PLAN_MISSING:{fixture_id}")
    normalized: list[dict[str, Any]] = []
    for item in plan:
        if not isinstance(item, dict):
            raise RuntimeError(f"WS49_NATURAL_PREGAME_PLAN_ITEM_INVALID:{fixture_id}")
        decision = item.get("decision")
        player_id = item.get("player_id")
        round_number = item.get("round")
        if decision not in {"KEEP", "MULLIGAN"} or not isinstance(player_id, str) or not isinstance(round_number, int):
            raise RuntimeError(f"WS49_NATURAL_PREGAME_PLAN_VALUE_INVALID:{fixture_id}:{item!r}")
        normalized.append({"decision": decision, "player_id": player_id, "round": round_number})

    procedure_plan = None
    for step in record.get("native_procedure") or []:
        if step.get("operation") == "EXTERNAL_SUBMIT_EXPLICIT_MULLIGAN_KEEP_RESPONSES":
            procedure_plan = (step.get("details") or {}).get("plan")
            break
    if procedure_plan is not None and procedure_plan != normalized:
        raise RuntimeError(f"WS49_NATURAL_PROCEDURE_PLAN_MISMATCH:{fixture_id}")
    return normalized


def _mulligan_plan_by_player(
    plan: list[dict[str, Any]], player_count: int, fixture_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Bind immutable mulligan responses to the native player, not callback order.

    XMage may solicit private mulligan responses in an internal callback order.
    That order is not a player-visible Rules choice.  The contract instead
    binds each response to its canonical player and round, which this helper
    validates exhaustively before any response is submitted.
    """
    by_player = {f"P{seat}": [] for seat in range(1, player_count + 1)}
    for item in plan:
        player_id = item["player_id"]
        if player_id not in by_player:
            raise RuntimeError(f"WS49_NATURAL_MULLIGAN_PLAYER_OUT_OF_RANGE:{fixture_id}:{player_id}")
        by_player[player_id].append(item)
    for player_id, items in by_player.items():
        expected_rounds = list(range(1, len(items) + 1))
        actual_rounds = [int(item["round"]) for item in items]
        if actual_rounds != expected_rounds:
            raise RuntimeError(
                f"WS49_NATURAL_MULLIGAN_ROUND_PLAN_INVALID:{fixture_id}:{player_id}:"
                f"expected={expected_rounds}:actual={actual_rounds}"
            )
    return by_player


def _canonical_player_from_native_seat(
    pending: dict[str, Any], player_count: int, fixture_id: str
) -> str:
    seat = pending.get("seat")
    if not isinstance(seat, int) or not 0 <= seat < player_count:
        raise RuntimeError(f"WS49_NATURAL_NATIVE_ACTOR_SEAT_INVALID:{fixture_id}:{seat!r}")
    return f"P{seat + 1}"


def _natural_starting_player_option(decision: dict[str, Any], player_count: int) -> str:
    """Select only the contract's P1 native starting-player option.

    This is a setup datum from the immutable temporal state, not an AI choice.
    The offered native option set is still validated exactly and no option
    position, UUID, GUI default, or fallback is ever consumed.
    """
    context = decision.get("context") or {}
    if (
        decision.get("decision_class") != "choose_object"
        or decision.get("prompt") != "Select a starting player"
        or decision.get("minimum_selections") != 1
        or decision.get("maximum_selections") != 1
        or context.get("target_name") != "starting player"
        or context.get("target_description") != "target starting player"
        or context.get("required") is not True
        or context.get("targeted") is not False
    ):
        raise RuntimeError("WS49_NATURAL_STARTING_PLAYER_DECISION_SIGNATURE_INVALID")
    options = decision.get("legal_options") or []
    # XMage correctly exposes the actual player objects as opaque option IDs.
    # Their stable, native labels are assigned when this qualification session is
    # created: ``WS26 Seat <n>``.  Bind canonical P<n> to that semantic native
    # identity after checking the complete offer set.  Never select by position,
    # raw UUID, or a GUI convention.
    expected_labels = {f"WS26 Seat {seat}" for seat in range(1, player_count + 1)}
    by_label = {
        str(option.get("label")): option
        for option in options
        if isinstance(option, dict)
        and option.get("option_type") == "choice"
        and isinstance(option.get("option_id"), str)
        and isinstance(option.get("metadata"), dict)
        and option["metadata"].get("name") == option.get("label")
    }
    if set(by_label) != expected_labels or len(by_label) != player_count:
        raise RuntimeError(
            "WS49_NATURAL_STARTING_PLAYER_OPTION_SET_INVALID:"
            f"expected_labels={sorted(expected_labels)}:actual_labels={sorted(by_label)}"
        )
    chosen = by_label.get("WS26 Seat 1")
    if chosen is None:
        raise RuntimeError("WS49_NATURAL_STARTING_PLAYER_P1_OPTION_INVALID")
    return str(chosen["option_id"])


_LONDON_BOTTOM_DESCRIPTION_FRAGMENT = "put on the bottom of your library"


def _contract_london_bottom_total(record: dict[str, Any]) -> int | None:
    """Return the immutable expected London-bottom total, when modeled.

    New-format natural records carry an explicit
    NATIVE_COMPLETE_LONDON_MULLIGAN_BOTTOMING step with expected_bottom_count.
    Old-format records (PILOT_MULLIGAN) carry no bottoming step; the runner
    then verifies purely from its own native submission log.
    """
    total: int | None = None
    for step in record.get("native_procedure") or []:
        if not isinstance(step, dict):
            continue
        if step.get("operation") != "NATIVE_COMPLETE_LONDON_MULLIGAN_BOTTOMING":
            continue
        details = step.get("details")
        if not isinstance(details, dict) or not isinstance(
            details.get("expected_bottom_count"), int
        ):
            raise RuntimeError(
                f"WS49_NATURAL_BOTTOM_STEP_INVALID:{record.get('fixture_id')}:{details!r}"
            )
        if total is not None:
            raise RuntimeError(
                f"WS49_NATURAL_BOTTOM_STEP_DUPLICATE:{record.get('fixture_id')}"
            )
        total = int(details["expected_bottom_count"])
    if total is not None and total < 0:
        raise RuntimeError(
            f"WS49_NATURAL_BOTTOM_TOTAL_NEGATIVE:{record.get('fixture_id')}"
        )
    return total


def _natural_london_bottom_selection(
    pending: dict[str, Any], fixture_id: str
) -> tuple[list[str], dict[str, Any]]:
    """Select native London-bottom cards only across proven-identical options.

    XMage natively prompts the mulliganing player to put N drawn cards on the
    bottom of their library (London mulligan).  The immutable WS-47 record
    models only the bottom COUNT, never which physical cards bottom, so the
    runner may complete this prompt only when every natively offered option
    is semantically identical through the actor-safe surface.  Any divergence
    fails closed: choosing among differing cards would be an unsanctioned
    pilot decision, and no first/random/default/AI/GUI fallback exists here.
    """
    context = pending.get("context") or {}
    if (
        pending.get("decision_class") != "target"
        or context.get("targeted") is not True
        or context.get("outcome") != "discard"
        or context.get("required") is not True
        or _LONDON_BOTTOM_DESCRIPTION_FRAGMENT
        not in str(context.get("target_description") or "")
    ):
        raise RuntimeError(f"WS49_NATURAL_BOTTOM_SIGNATURE_INVALID:{fixture_id}")
    if pending.get("source_object") is not None:
        raise RuntimeError(f"WS49_NATURAL_BOTTOM_SOURCE_UNEXPECTED:{fixture_id}")
    try:
        minimum = int(pending.get("minimum_selections"))
        maximum = int(pending.get("maximum_selections"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"WS49_NATURAL_BOTTOM_BOUNDS_INVALID:{fixture_id}") from exc
    if minimum < 1 or minimum != maximum:
        raise RuntimeError(
            f"WS49_NATURAL_BOTTOM_COUNT_NOT_EXACT:{fixture_id}:"
            f"min={minimum}:max={maximum}"
        )
    options = pending.get("legal_options") or []
    if len(options) < maximum:
        raise RuntimeError(f"WS49_NATURAL_BOTTOM_OPTION_SHORTAGE:{fixture_id}")
    semantic: set[str] = set()
    for option in options:
        if not isinstance(option, dict):
            raise RuntimeError(f"WS49_NATURAL_BOTTOM_OPTION_INVALID:{fixture_id}")
        metadata = option.get("metadata")
        if not isinstance(metadata, dict):
            raise RuntimeError(
                f"WS49_NATURAL_BOTTOM_OPTION_METADATA_INVALID:{fixture_id}"
            )
        label = option.get("label")
        name = metadata.get("name")
        if (
            option.get("option_type") != "target"
            or not isinstance(label, str)
            or not label
            or label != name
        ):
            raise RuntimeError(
                f"WS49_NATURAL_BOTTOM_OPTION_IDENTITY_INVALID:{fixture_id}"
            )
        semantic.add(f"{option.get('option_type')}\x00{label}")
    if len(semantic) != 1:
        raise RuntimeError(
            f"WS49_NATURAL_BOTTOM_OPTIONS_DIVERGE:{fixture_id}:"
            f"distinct={len(semantic)}"
        )
    ordered_ids = sorted(
        str(option["option_id"])
        for option in options
        if isinstance(option.get("option_id"), str) and option["option_id"]
    )
    if len(ordered_ids) != len(options):
        raise RuntimeError(f"WS49_NATURAL_BOTTOM_OPTION_ID_INVALID:{fixture_id}")
    proof = {
        "option_count": len(options),
        "distinct_semantic_identities": 1,
        "common_label": next(iter(semantic)).split("\x00", 1)[1],
        "submitted_count": minimum,
    }
    return ordered_ids[:minimum], proof


def _natural_pregame_runtime(record: dict[str, Any]) -> dict[str, Any]:
    """Execute the native shuffle/draw/mulligan lifecycle for one natural row.

    This deliberately runs past XMage's initial starting-player prompt.  The
    former construction probe sampled at that prompt, which is too early to
    prove the immutable record's actual Rules-RNG shuffle, opening hand and
    explicitly scripted mulligan obligations.
    """
    fixture_id = record["fixture_id"]
    player_count = len(record["players"])
    plan = _natural_mulligan_plan(record)
    planned_by_player = _mulligan_plan_by_player(plan, player_count, fixture_id)
    mulligan_cursors = {player_id: 0 for player_id in planned_by_player}
    mulligans_taken = {player_id: 0 for player_id in planned_by_player}
    bottoms_submitted = {player_id: 0 for player_id in planned_by_player}
    contract_bottom_total = _contract_london_bottom_total(record)
    decks, scenario = canonical_v105.deck_and_scenario(record)
    decisions: list[dict[str, Any]] = []

    with legacy.run_tax3.gate._RawFullGameClient(
        legacy.run_tax3.gate.command(), request_timeout_seconds=240.0
    ) as client:
        client.request("start_engine")
        handles = legacy.run_tax3.gate.import_decks(client, decks)
        client.request(
            "create_full_game",
            {
                "game_id": f"WS49-V105-NATURAL-{fixture_id}",
                "deck_handles": handles,
                "starting_player_seat": 0,
                "starting_life": 40,
                "seed": int(scenario["seed"]),
            },
        )
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        native_preflight = configured.get("native_validation")
        if configured.get("execution_entry_mode") != "NATURAL_GAME_START":
            raise RuntimeError(f"WS49_NATURAL_ENTRY_MODE_MISMATCH:{fixture_id}")
        if not isinstance(native_preflight, dict) or native_preflight.get("valid") is not True:
            raise RuntimeError(f"WS49_NATURAL_NATIVE_PREFLIGHT_FAILED:{fixture_id}")
        client.request("start_full_game")

        starting_player_selected = False
        for _ in range(128):
            status = client.request("get_full_game_decision")
            pending = status.get("decision")
            if not isinstance(pending, dict):
                raise RuntimeError(f"WS49_NATURAL_PENDING_DECISION_MISSING:{fixture_id}:{status!r}")
            kind = pending.get("decision_class")
            if kind == "choose_object" and not starting_player_selected:
                selected = _natural_starting_player_option(pending, player_count)
                legacy.run_tax3.gate.submit_one(client, pending, [selected])
                starting_player_selected = True
                continue
            if kind == "mulligan":
                actual_actor = _canonical_player_from_native_seat(pending, player_count, fixture_id)
                cursor = mulligan_cursors[actual_actor]
                expected_for_actor = planned_by_player[actual_actor]
                if cursor >= len(expected_for_actor):
                    raise RuntimeError(
                        f"WS49_NATURAL_UNPLANNED_MULLIGAN:{fixture_id}:{actual_actor}:"
                        f"native_round={cursor + 1}"
                    )
                expected = expected_for_actor[cursor]
                option_type = "keep" if expected["decision"] == "KEEP" else "mulligan"
                option = legacy.run_tax3.gate.unique_option(pending, option_type=option_type)
                legacy.run_tax3.gate.submit_one(client, pending, [str(option["option_id"])])
                decisions.append(
                    {
                        "actor": actual_actor,
                        "round": expected["round"],
                        "semantic_decision": expected["decision"],
                        "native_decision_class": "mulligan",
                        "selected_option_type": option_type,
                    }
                )
                mulligan_cursors[actual_actor] += 1
                if expected["decision"] == "MULLIGAN":
                    mulligans_taken[actual_actor] += 1
                continue
            if kind == "target":
                # Native London-bottom prompt after a non-free mulligan.  The
                # runner completes it only across proven-identical options and
                # only while a taken mulligan still covers the bottom count.
                actual_actor = _canonical_player_from_native_seat(pending, player_count, fixture_id)
                if bottoms_submitted[actual_actor] >= mulligans_taken[actual_actor]:
                    raise RuntimeError(
                        f"WS49_NATURAL_BOTTOM_WITHOUT_MULLIGAN_COVER:{fixture_id}:{actual_actor}"
                    )
                selected, proof = _natural_london_bottom_selection(pending, fixture_id)
                legacy.run_tax3.gate.submit_one(client, pending, selected)
                bottoms_submitted[actual_actor] += len(selected)
                decisions.append(
                    {
                        "actor": actual_actor,
                        "native_decision_class": "target",
                        "london_bottom_cards": len(selected),
                        "identical_option_neutrality_proof": proof,
                    }
                )
                continue
            if kind == "priority":
                break
            diagnostic = {
                "actor": _canonical_player_from_native_seat(pending, player_count, fixture_id),
                "class": kind,
                "context": pending.get("context"),
                "maximum_selections": pending.get("maximum_selections"),
                "minimum_selections": pending.get("minimum_selections"),
                "option_types": [
                    option.get("option_type")
                    for option in (pending.get("legal_options") or [])
                    if isinstance(option, dict)
                ],
            }
            raise RuntimeError(
                f"WS49_NATURAL_UNSUPPORTED_PREGAME_DECISION:{fixture_id}:"
                f"{json.dumps(diagnostic, sort_keys=True)}"
            )
        else:
            raise RuntimeError(f"WS49_NATURAL_PREGAME_PRIORITY_NOT_REACHED:{fixture_id}")

        if not starting_player_selected:
            raise RuntimeError(f"WS49_NATURAL_STARTING_PLAYER_NOT_SELECTED:{fixture_id}")
        unconsumed = {
            player_id: items[mulligan_cursors[player_id]:]
            for player_id, items in planned_by_player.items()
            if mulligan_cursors[player_id] != len(items)
        }
        if unconsumed:
            raise RuntimeError(
                f"WS49_NATURAL_PREGAME_PLAN_NOT_CONSUMED:{fixture_id}:"
                f"{json.dumps(unconsumed, sort_keys=True)}"
            )

        observation = client.request(
            "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
        ).get("observation")
        state = client.request("get_qualification_state")
        result = client.request("get_full_game_result")

    if not isinstance(observation, dict) or not isinstance(state, dict) or not isinstance(result, dict):
        raise RuntimeError(f"WS49_NATURAL_RUNTIME_READBACK_MISSING:{fixture_id}")
    players: dict[str, dict[str, Any]] = {}
    for player in observation.get("players") or []:
        if not isinstance(player, dict):
            raise RuntimeError(f"WS49_NATURAL_PLAYER_READBACK_ENTRY_INVALID:{fixture_id}")
        player_id = _canonical_player_from_native_seat(player, player_count, fixture_id)
        if player_id in players:
            raise RuntimeError(f"WS49_NATURAL_PLAYER_READBACK_DUPLICATE_SEAT:{fixture_id}:{player_id}")
        players[player_id] = player
    expected_players = {f"P{seat}" for seat in range(1, player_count + 1)}
    if set(players) != expected_players:
        raise RuntimeError(
            f"WS49_NATURAL_PLAYER_READBACK_MISMATCH:{fixture_id}:"
            f"expected={sorted(expected_players)}:actual={sorted(players)}"
        )
    # Opening-hand expectation is empirical, never predicted from a mirrored
    # mulligan rule: XMage natively reports each non-free mulligan through a
    # London-bottom prompt, and the runner submits exactly those prompts above.
    # A free first mulligan (multiplayer Commander) therefore yields 7 cards
    # with zero submissions, while a non-free one yields 7 minus bottoms.
    # The immutable contract bottom total cross-checks the submission log
    # wherever the record models it.
    if contract_bottom_total is not None and sum(
        bottoms_submitted.values()
    ) != contract_bottom_total:
        raise RuntimeError(
            f"WS49_NATURAL_BOTTOM_TOTAL_MISMATCH:{fixture_id}:"
            f"submitted={dict(sorted(bottoms_submitted.items()))}:"
            f"contract={contract_bottom_total}"
        )
    for player_id, player in players.items():
        if bottoms_submitted[player_id] > mulligans_taken[player_id]:
            raise RuntimeError(
                f"WS49_NATURAL_BOTTOM_EXCEEDS_MULLIGANS:{fixture_id}:{player_id}"
            )
        expected_hand = 7 - bottoms_submitted[player_id]
        if player.get("hand_count") != expected_hand:
            raise RuntimeError(
                f"WS49_NATURAL_OPENING_HAND_MISMATCH:{fixture_id}:{player_id}:"
                f"actual={player.get('hand_count')}:expected={expected_hand}"
            )
        expected_library = 99 - expected_hand
        if player.get("library_count") != expected_library:
            raise RuntimeError(
                f"WS49_NATURAL_LIBRARY_COUNT_MISMATCH:{fixture_id}:{player_id}:"
                f"actual={player.get('library_count')}:expected={expected_library}"
            )
        if player.get("life") != 40 or player.get("has_lost") is not False or player.get("has_left") is not False:
            raise RuntimeError(f"WS49_NATURAL_PLAYER_STATE_MISMATCH:{fixture_id}:{player_id}")

    rng = state.get("rules_rng_tape")
    if not isinstance(rng, dict) or int(rng.get("operation_count", 0)) < player_count:
        raise RuntimeError(f"WS49_NATURAL_INITIAL_SHUFFLE_NOT_CAPTURED:{fixture_id}")
    replay = result.get("replay")
    if not isinstance(replay, dict):
        raise RuntimeError(f"WS49_NATURAL_REPLAY_MISSING:{fixture_id}")
    return {
        "native_preflight": native_preflight,
        "native_pregame_boundary": "AFTER_NATIVE_SHUFFLE_DRAW_AND_SCRIPTED_MULLIGANS_AT_FIRST_PRIORITY",
        "starting_player_selected_from_native_offer": "P1",
        "semantic_pregame_decisions": decisions,
        "native_mulligans_taken": dict(sorted(mulligans_taken.items())),
        "native_london_bottoms_submitted": dict(sorted(bottoms_submitted.items())),
        "contract_london_bottom_total": contract_bottom_total,
        "native_public_player_state": [
            {
                "player_id": player_id,
                "life": players[player_id]["life"],
                "hand_count": players[player_id]["hand_count"],
                "library_count": players[player_id]["library_count"],
                "has_lost": players[player_id]["has_lost"],
                "has_left": players[player_id]["has_left"],
            }
            for player_id in sorted(players)
        ],
        "rules_rng_tape": rng,
        "decision_tape": replay.get("decision_tape"),
        "event_tape": replay.get("event_tape"),
        "checkpoints": replay.get("checkpoints"),
        "request_object_copied_as_proof": False,
    }


def probe_record_v105(record: dict[str, Any]) -> dict[str, Any]:
    """Use the native pregame executor only where the immutable entry mode requires it."""
    if record.get("execution_entry_mode") != "NATURAL_GAME_START":
        return legacy.probe_record(record)
    row = {
        "fixture_id": record["fixture_id"],
        "fixture_family": record["fixture_family"],
        "record_digest": record["materialization_digest"],
        "requested_state_digest": record["requested_state_digest"],
        "required_dimensions": ["natural_game_start"],
        "runtime_credit": "NONE",
        "historical_pass_imported": False,
    }
    try:
        runtime = _natural_pregame_runtime(record)
        row.update(
            {
                "construction_status": "NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION",
                "native_setup_ready": True,
                "behavior_runtime_executed": False,
                "non_echo_native_readback": {
                    "evidence_class": "LOWER_LEVEL_NATIVE_READBACK_READY_FOR_INDEPENDENT_NORMALIZATION",
                    "execution_entry_mode": "NATURAL_GAME_START",
                    "request_object_copied_as_proof": False,
                    "legacy_normalized_constructed_state_consumed": False,
                    "legacy_declared_digest_consumed": False,
                    "natural_pregame_runtime": runtime,
                    "construction_credit_granted": False,
                },
            }
        )
    except Exception as exc:
        row.update(
            {
                "construction_status": "FAIL_CLOSED_NATIVE_CONSTRUCTION",
                "native_setup_ready": False,
                "behavior_runtime_executed": False,
                "failure_signature": str(exc),
            }
        )
    return row


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

    rows = [probe_record_v105(record) for record in records]
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
