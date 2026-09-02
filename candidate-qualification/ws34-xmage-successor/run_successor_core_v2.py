#!/usr/bin/env python3
"""WS-34 successor core runner with provider-emitted setup proof.

This is a compatibility/admission wrapper around the historical v1.0.1 runtime
transactions.  It does not import historical PASS.  Each selected v1.0.2 record
is executed again against the pinned provider, and a separate clean process
must first emit the complete successor requested-state projection after its
native setup validator accepted the scenario.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FC = HERE.parents[0] / "finalist-convergence-xmage"
WS26 = HERE.parents[0] / "ws26-xmage"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FC))
sys.path.insert(0, str(WS26))

import run_successor_core as core  # noqa: E402
import run_canonical_starter18 as legacy  # noqa: E402
import run_ws26_gate as gate  # noqa: E402
from successor_contract import canonical_sha, requested_state_digest, requested_state_projection  # noqa: E402


def dynamic_starting_player_option(decision: dict[str, Any], scenario: dict[str, Any]) -> str:
    """Resolve only the unique provider-offered semantic starting-player option.

    Historical WS26 expected exactly four players and one metadata spelling.
    Successor qualification covers 2P-5P.  UUID/object ids are provider-local;
    the exact visible seat label is the stable semantic selector.
    """
    if decision.get("decision_class") != "choose_object":
        raise RuntimeError("STARTING_PLAYER_DECISION_CLASS_MISMATCH")
    if decision.get("prompt") != "Select a starting player":
        raise RuntimeError("STARTING_PLAYER_PROMPT_MISMATCH")
    if decision.get("minimum_selections") != 1 or decision.get("maximum_selections") != 1:
        raise RuntimeError("STARTING_PLAYER_CARDINALITY_MISMATCH")

    player_count = len(scenario.get("players") or [])
    wanted = int(scenario["starting_player_seat"])
    if player_count < 2 or player_count > 5 or wanted < 1 or wanted > player_count:
        raise RuntimeError("STARTING_PLAYER_SCENARIO_RANGE_MISMATCH")

    options = decision.get("legal_options") or []
    if len(options) != player_count:
        raise RuntimeError(
            "STARTING_PLAYER_OPTION_COUNT_MISMATCH:"
            + json.dumps(decision, sort_keys=True)
        )

    expected_label = f"WS26 Seat {wanted}"
    matches = []
    for option in options:
        metadata = option.get("metadata") or {}
        names = {
            str(option.get("label") or ""),
            str(metadata.get("name") or ""),
            str(metadata.get("display_name") or ""),
        }
        option_id = str(option.get("option_id") or "")
        if option.get("option_type") != "choice":
            continue
        if expected_label in names or option_id == f"P{wanted}":
            matches.append(option)
    if len(matches) != 1:
        raise RuntimeError(
            "STARTING_PLAYER_SEMANTIC_MATCH_NOT_UNIQUE:"
            + json.dumps({"expected": expected_label, "matches": matches, "decision": decision}, sort_keys=True)
        )
    return str(matches[0]["option_id"])


def observed_projection(observation: dict[str, Any]) -> dict[str, Any]:
    projected = []
    for index, player in enumerate(observation["players"]):
        raw_seat = player.get("seat")
        seat = int(raw_seat) + 1 if isinstance(raw_seat, int) else index + 1
        command = player.get("command") or []
        names = sorted(card.get("name") for card in command if card.get("name"))
        projected.append({
            "player_id": f"P{seat}",
            "life": player["life"],
            "hand_count": player["hand_count"],
            "library_count": player["library_count"],
            "commander": names[0] if len(names) == 1 else None,
        })
    projected.sort(key=lambda item: int(item["player_id"][1:]))
    return {"player_count": observation["player_count"], "players": projected}


def native_projection(
    observation: dict[str, Any], semantic_state: dict[str, Any], status: dict[str, Any]
) -> dict[str, Any]:
    players = []
    for index, item in enumerate(observation["players"]):
        raw_seat = item.get("seat")
        seat = int(raw_seat) + 1 if isinstance(raw_seat, int) else index + 1
        command = item.get("command") or []
        players.append({
            "player_id": f"P{seat}",
            "life": item["life"],
            "commanders": sorted(card["name"] for card in command if card.get("name")),
        })
    players.sort(key=lambda item: int(item["player_id"][1:]))

    objects = []
    for item in semantic_state["scenario_objects"]:
        owner = f"P{item['owner_seat']}"
        objects.append({
            "semantic_id": item["semantic_id"],
            "card_identity": item["card_name"],
            "owner": owner,
            "controller": f"P{item.get('controller_seat', item['owner_seat'])}",
            "zone": "exile" if item["zone"] == "exiled" else item["zone"],
            "tapped": bool(item.get("tapped", False)),
        })
    objects.sort(key=lambda value: value["semantic_id"])
    step = status["step"]
    if step == "precombat_main":
        step = "main"
    return {
        "players": players,
        "objects": objects,
        "temporal_state": {
            "turn_number": status["turn"],
            "active_player": f"P{status['active_player_seat']}",
            "priority_player": f"P{status['priority_player_seat']}",
            "phase": status["phase"],
            "step": step,
        },
    }


def successor_setup_scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if record["execution_entry_mode"] == "NATURAL_GAME_START":
        decks, scenario = core._scenario(record)
    else:
        decks, scenario = legacy.deck_and_scenario(record, legacy.SCHEMA)
    scenario = deepcopy(scenario)
    scenario["successor_requested_state"] = requested_state_projection(record)
    scenario["successor_requested_state_digest"] = requested_state_digest(record)
    return decks, scenario


def prove_successor_setup(record: dict[str, Any]) -> dict[str, Any]:
    requested = requested_state_projection(record)
    digest = requested_state_digest(record)
    if digest != record["requested_state_digest"]:
        raise AssertionError("CONTRACT_REQUESTED_STATE_DIGEST_MISMATCH")

    decks, scenario = successor_setup_scenario(record)
    with gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0) as client:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        client.request("create_full_game", {
            "game_id": f"{scenario['scenario_id']}-SUCCESSOR-PROOF",
            "deck_handles": handles,
            "starting_player_seat": int(scenario["starting_player_seat"]) - 1,
            "starting_life": 40,
            "seed": int(scenario["seed"]),
        })
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        if configured.get("execution_entry_mode") != record["execution_entry_mode"]:
            raise AssertionError("SUCCESSOR_SETUP_ENTRY_MODE_MISMATCH")
        client.request("start_full_game")
        state = client.request("get_qualification_state")

    constructed = state.get("normalized_constructed_state")
    declared = state.get("normalized_constructed_state_declared_digest")
    proof_kind = state.get("normalized_constructed_state_proof")
    native_validation = state.get("normalized_constructed_state_native_validation")
    if not isinstance(constructed, dict):
        raise AssertionError("PROVIDER_NORMALIZED_CONSTRUCTED_STATE_MISSING")
    if declared != digest:
        raise AssertionError("PROVIDER_DECLARED_CONSTRUCTED_DIGEST_MISMATCH")
    if proof_kind != "PROVIDER_NATIVE_SETUP_VALIDATION_BOUND":
        raise AssertionError("PROVIDER_NATIVE_SETUP_PROOF_MISSING")
    if not isinstance(native_validation, dict) or native_validation.get("valid") is not True:
        raise AssertionError("PROVIDER_NATIVE_SETUP_VALIDATION_NOT_PASS")
    constructed_digest = canonical_sha(constructed)
    if constructed_digest != digest or constructed != requested:
        raise AssertionError("REQUESTED_VS_PROVIDER_CONSTRUCTED_STATE_MISMATCH")
    return {
        "requested_semantic_state_digest": digest,
        "normalized_native_constructed_state_digest": constructed_digest,
        "requested_native_state_equal": True,
        "successor_runtime_credit": "SETUP_PROOF_PASS",
        "construction_proof": {
            "method": "PROVIDER_EMITTED_STATE_AFTER_NATIVE_SETUP_VALIDATION",
            "provider_proof_kind": proof_kind,
            "provider_native_validation": native_validation,
            "separate_clean_process": True,
            "provider_emitted_full_state_projection": True,
            "harness_requested_state_echo_prohibited": True,
        },
    }


def assert_successor_projection(record: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    if row.get("status") != "PASS":
        raise AssertionError("cannot promote non-PASS runtime row")
    if row.get("record_digest") != record["materialization_digest"]:
        raise AssertionError("record digest mismatch")
    proof = prove_successor_setup(record)
    proof["construction_proof"]["behavior_runtime_native_slice_digest_equal"] = bool(
        row.get("legacy_native_slice_equal")
        or row.get("requested_semantic_state_digest")
        == row.get("normalized_native_constructed_state_digest")
    )
    return proof


def main() -> int:
    # Compatibility shims are qualification-only and semantic.  They never
    # choose a non-offered action and fail closed on zero/multiple matches.
    gate.scenario_starting_player_option = dynamic_starting_player_option
    legacy.gate.scenario_starting_player_option = dynamic_starting_player_option
    legacy.observed_projection = observed_projection
    legacy.native_projection = native_projection
    core.gate.scenario_starting_player_option = dynamic_starting_player_option
    core.legacy.observed_projection = observed_projection
    core.legacy.native_projection = native_projection
    core._assert_default_successor_projection = assert_successor_projection
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
