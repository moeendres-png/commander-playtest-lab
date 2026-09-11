#!/usr/bin/env python3
"""Execute the v1.0.1 natural-start slice through the WS26 XMage provider.

Every row is terminal and bound to the exact neutral record digest. Unsupported
midgame dimensions are reported fail-closed; no historical same-ID PASS is
imported. This first candidate increment intentionally establishes the native
Commander lifecycle/mulligan path before extending the state loader.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS26 = HERE.parents[0] / "ws26-xmage"
sys.path.insert(0, str(WS26))
import run_ws26_gate as gate  # noqa: E402
from canonical_v101 import (  # noqa: E402
    canonical_sha,
    deck_and_scenario,
    native_projection,
    requested_projection,
    unique_option,
)


CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
BEHAVIORAL_BASE_COMMIT = "a53c2312983384eb0870746132e281bbed2f5a1d"
SCHEMA = "xmage-qualification-scenario/1.1.0"
NATURAL_IDS = {
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
}
PRIMITIVE_A_IDS = {"PILOT_PRIORITY", "PILOT_TARGET"}


def deck_payload(deck_id: str) -> dict[str, Any]:
    body = {
        "deck_id": deck_id,
        "mainboard": ["Mountain"] * 99,
        "commander_names": ["Rograkh, Son of Rohgahh"],
        "sideboard": [],
    }
    body["deck_hash"] = gate.sha(body)
    return body


def scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    count = len(record["players"])
    decks = [deck_payload(f"fc-{record['fixture_id'].lower()}-p{seat}") for seat in range(1, count + 1)]
    players = []
    for seat in range(1, count + 1):
        players.append({
            "seat": seat,
            "life": 40,
            "commander_names": ["Rograkh, Son of Rohgahh"],
            "natural_library_card_name": "Mountain",
            "natural_library_card_count": 99,
            "zones": {"hand": [], "library": [], "graveyard": [], "exile": [], "battlefield": []},
        })
    return decks, {
        "schema_version": SCHEMA,
        "scenario_id": f"FINALIST-{record['fixture_id']}",
        "execution_entry_mode": "NATURAL_GAME_START",
        "seed": record["rules_randomness"]["rules_seed"],
        "starting_player_seat": 1,
        "players": players,
    }


def choose_mulligan(record_id: str, decision: dict[str, Any], p1_seen: int) -> tuple[str, int]:
    actor = int(decision["seat"]) + 1
    if record_id == "PILOT_MULLIGAN" and actor == 1 and p1_seen == 0:
        option = gate.unique_option(decision, option_type="mulligan")
        return str(option["option_id"]), p1_seen + 1
    option = gate.unique_option(decision, option_type="keep")
    return str(option["option_id"]), p1_seen + (1 if actor == 1 else 0)


def expected_projection(player_count: int) -> dict[str, Any]:
    return {
        "player_count": player_count,
        "players": [
            {
                "player_id": f"P{seat}", "life": 40, "hand_count": 7,
                "library_count": 92, "commander": "Rograkh, Son of Rohgahh",
            }
            for seat in range(1, player_count + 1)
        ],
    }


def observed_projection(observation: dict[str, Any]) -> dict[str, Any]:
    projected = []
    for player in observation["players"]:
        command = player.get("command") or []
        names = sorted(card.get("name") for card in command if card.get("name"))
        projected.append({
            "player_id": player["player_id"], "life": player["life"],
            "hand_count": player["hand_count"], "library_count": player["library_count"],
            "commander": names[0] if len(names) == 1 else None,
        })
    return {"player_count": observation["player_count"], "players": projected}


def run_natural(record: dict[str, Any]) -> dict[str, Any]:
    decks, payload = scenario(record)
    player_count = len(record["players"])
    decisions = []
    with gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0) as client:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        client.request("create_full_game", {
            "game_id": payload["scenario_id"], "deck_handles": handles,
            "starting_player_seat": 0, "starting_life": 40,
            "seed": record["rules_randomness"]["rules_seed"],
        })
        configured = client.request("configure_qualification_scenario", {"scenario": payload})
        if configured.get("execution_entry_mode") != "NATURAL_GAME_START":
            raise AssertionError(f"native execution entry mismatch: {configured}")
        client.request("start_full_game")
        p1_seen = 0
        for _ in range(80):
            status = client.request("get_full_game_decision")
            pending = status.get("decision")
            if not isinstance(pending, dict):
                raise RuntimeError(f"natural game reached no decision: {status}")
            kind = pending["decision_class"]
            actor = int(pending["seat"]) + 1
            if kind == "choose_object":
                selected = [gate.scenario_starting_player_option(pending, payload)]
            elif kind == "mulligan":
                option_id, p1_seen = choose_mulligan(record["fixture_id"], pending, p1_seen)
                selected = [option_id]
            elif kind == "priority":
                break
            else:
                raise RuntimeError(f"unexpected natural-start decision: {kind}")
            decisions.append({"decision_family": kind, "actor": f"P{actor}", "selected_option_id": selected[0]})
            gate.submit_one(client, pending, selected)
        else:
            raise RuntimeError("first native priority was not reached")
        observation = client.request(
            "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
        )["observation"]
        state = client.request("get_qualification_state")
        result = client.request("get_full_game_result")

    requested = expected_projection(player_count)
    native = observed_projection(observation)
    if native != requested:
        raise AssertionError(f"requested/native state mismatch: requested={requested} native={native}")
    if int(state["rules_rng_tape"]["operation_count"]) < player_count:
        raise AssertionError("native seeded initial shuffles were not recorded")
    mulligans = [item for item in decisions if item["decision_family"] == "mulligan"]
    expected_mulligan_count = player_count + (1 if record["fixture_id"] == "PILOT_MULLIGAN" else 0)
    if len(mulligans) != expected_mulligan_count:
        raise AssertionError(f"mulligan decision count mismatch: {mulligans}")
    return {
        "fixture_id": record["fixture_id"], "status": "PASS",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(requested),
        "normalized_native_constructed_state_digest": canonical_sha(native),
        "setup": "PASS", "decision_tape": result["replay"]["decision_tape"],
        "rules_rng_tape": result["replay"]["rules_rng_tape"],
        "event_tape": result["replay"]["event_tape"],
        "checkpoints": result["replay"]["checkpoints"],
        "terminal_semantic_state": native,
        "terminal_postcondition_result": "PASS",
    }


def _metadata(option: dict[str, Any]) -> dict[str, Any]:
    value = option.get("metadata")
    return value if isinstance(value, dict) else {}


def _observation(client: gate._RawFullGameClient) -> dict[str, Any]:
    return client.request(
        "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
    )["observation"]


def _terminal_bolt_state(state: dict[str, Any], observation: dict[str, Any]) -> bool:
    objects = {item["semantic_id"]: item for item in state["semantic_state"]["scenario_objects"]}
    players = {item["player_id"]: item for item in observation["players"]}
    return objects.get("obj:pilot-bolt", {}).get("zone") == "graveyard" and players["P2"]["life"] == 37


def run_primitive_a(record: dict[str, Any]) -> dict[str, Any]:
    decks, payload = deck_and_scenario(record, SCHEMA)
    canonical_trace: list[dict[str, Any]] = []
    normalized_events: list[dict[str, Any]] = []
    stack_observed = False
    cast_selected = False
    target_selected = False
    with gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0) as client:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        client.request("create_full_game", {
            "game_id": payload["scenario_id"], "deck_handles": handles,
            "starting_player_seat": 0, "starting_life": 40,
            "seed": record["rules_randomness"]["rules_seed"],
        })
        configured = client.request("configure_qualification_scenario", {"scenario": payload})
        if configured.get("execution_entry_mode") != "NATIVE_STATE_LOAD":
            raise AssertionError(f"native execution entry mismatch: {configured}")
        client.request("start_full_game")

        status = client.request("get_full_game_decision")
        pending = status.get("decision")
        if not isinstance(pending, dict) or pending.get("decision_class") != "priority":
            raise RuntimeError(f"native loaded state did not enter P1 priority: {status}")
        observation = _observation(client)
        setup_state = client.request("get_qualification_state")
        requested = requested_projection(record)
        native = native_projection(observation, setup_state["semantic_state"], status)
        if requested != native:
            raise AssertionError(f"requested/native state mismatch: requested={requested} native={native}")

        for _ in range(80):
            state = client.request("get_qualification_state")
            observation = _observation(client)
            if cast_selected:
                bolt = next(
                    item for item in state["semantic_state"]["scenario_objects"]
                    if item["semantic_id"] == "obj:pilot-bolt"
                )
                if bolt["zone"] == "stack" and not stack_observed:
                    stack_observed = True
                    normalized_events.append({
                        "event_kind": "spell_cast", "object": "obj:pilot-bolt",
                        "native_observation": "zone:stack",
                    })
            if _terminal_bolt_state(state, observation):
                normalized_events.append({
                    "event_kind": "spell_resolved", "object": "obj:pilot-bolt",
                    "native_observation": {"zone": "graveyard", "P2_life": 37},
                })
                break
            status = client.request("get_full_game_decision")
            pending = status.get("decision")
            if not isinstance(pending, dict):
                raise RuntimeError(f"native cast transaction reached no decision: {status}")
            kind = pending["decision_class"]
            if kind == "priority" and not cast_selected:
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "activated_ability"
                    and _metadata(item).get("source_name") == "Lightning Bolt",
                    "cast:obj:pilot-bolt",
                )
                cast_selected = True
                canonical_trace.append({
                    "actor": "P1", "decision_family": "priority",
                    "selection": {"action": "cast", "object": "obj:pilot-bolt"},
                })
            elif kind == "target" and not target_selected:
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "target"
                    and str(item.get("label", "")).casefold() == "ws26 seat 2",
                    "target:P2",
                )
                target_selected = True
                canonical_trace.append({
                    "actor": "P1", "decision_family": "target", "selection": "P2",
                })
                normalized_events.append({"event_kind": "target_selected", "target": "P2"})
            elif kind == "mana_payment":
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "mana_ability"
                    and _metadata(item).get("source_name") == "Mountain",
                    "mana:obj:pilot-mountain",
                )
            elif kind == "choice":
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "cast_ability"
                    and _metadata(item).get("card_name") == "Lightning Bolt",
                    "cast-ability:obj:pilot-bolt",
                )
            elif kind == "priority" and cast_selected:
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "pass_priority",
                    "pass_priority",
                )
            else:
                raise RuntimeError(f"DECISION_SELECTOR_UNSUPPORTED:{kind}")
            gate.submit_one(client, pending, [str(option["option_id"])])
        else:
            raise RuntimeError("native Bolt transaction did not reach canonical terminal state")

        if not cast_selected or not target_selected or not stack_observed:
            raise AssertionError(
                f"native cast evidence incomplete: cast={cast_selected} target={target_selected} stack={stack_observed}"
            )
        terminal_state = client.request("get_qualification_state")
        result = client.request("get_full_game_result")

    return {
        "fixture_id": record["fixture_id"], "status": "PASS",
        "materialization_version": CONTRACT_VERSION,
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(requested),
        "normalized_native_constructed_state_digest": canonical_sha(native),
        "requested_native_state_equal": True,
        "setup": "PASS", "canonical_decision_trace": canonical_trace,
        "decision_tape": result["replay"]["decision_tape"],
        "rules_rng_tape": result["replay"]["rules_rng_tape"],
        "event_tape": normalized_events,
        "raw_event_tape": result["replay"]["event_tape"],
        "checkpoints": result["replay"]["checkpoints"],
        "terminal_semantic_state": {
            "obj:pilot-bolt": {"zone": "graveyard"}, "P2": {"life": 37},
        },
        "terminal_native_state_sha256": terminal_state["semantic_state"]["sha256"],
        "terminal_postcondition_result": "PASS",
    }


def unsupported(record: dict[str, Any]) -> dict[str, Any]:
    dimensions = sorted({
        step["operation"] for step in record.get("native_procedure", [])
        if step["operation"] not in {"NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE"}
    })
    return {
        "fixture_id": record["fixture_id"],
        "status": "CANONICAL_SETUP_UNSUPPORTED",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": None,
        "normalized_native_constructed_state_digest": None,
        "setup": "CANONICAL_SETUP_UNSUPPORTED",
        "failure_signature": "XMAGE_V101_TRANSLATOR_DIMENSION_NOT_YET_IMPLEMENTED:" + ",".join(dimensions),
        "decision_tape": [], "rules_rng_tape": [], "event_tape": [], "checkpoints": [],
        "terminal_semantic_state": None, "terminal_postcondition_result": "NOT_RUN",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-id", action="append", choices=gate_order())
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_VERSION or contract.get("canonical_bundle_digest") != CONTRACT_BUNDLE:
        raise SystemExit("CONTRACT_LOCK_MISMATCH")
    starter = [record for record in contract["records"] if record["fixture_id"] in gate_order()]
    by_id = {record["fixture_id"]: record for record in starter}
    selected_ids = args.fixture_id or gate_order()
    rows = []
    for fixture_id in selected_ids:
        record = by_id[fixture_id]
        try:
            if fixture_id in NATURAL_IDS:
                rows.append(run_natural(record))
            elif fixture_id in PRIMITIVE_A_IDS:
                rows.append(run_primitive_a(record))
            else:
                rows.append(unsupported(record))
        except Exception as exc:  # terminal evidence, never silent fallback
            rows.append({
                **unsupported(record), "status": "FAIL", "setup": "FAIL",
                "failure_signature": f"{type(exc).__name__}:{exc}",
            })
    counts: dict[str, int] = {}
    for row in rows: counts[row["status"]] = counts.get(row["status"], 0) + 1
    evidence = {
        "schema_version": "commander-lab.xmage-finalist-canonical-results/1.1.0",
        "contract_commit": CONTRACT_COMMIT, "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "provider_implementation_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "behavioral_base_commit": BEHAVIORAL_BASE_COMMIT,
        "xmage_commit": gate.XMAGE_COMMIT, "xmage_tree": gate.XMAGE_TREE,
        "provider": "strict external WS26 qualification controller", "counts": counts,
        "selected_fixture_ids": selected_ids,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    return 0 if counts.get("FAIL", 0) == 0 else 1


def gate_order() -> list[str]:
    return [
        "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
        "PILOT_MULLIGAN", "PILOT_PRIORITY", "PILOT_TARGET", "HIDDEN_01", "HIDDEN_02",
        "MICRO_STACK", "MICRO_REPLACEMENT", "WS05-MP-COMBAT-4", "RNG_RULES_TAPE",
        "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
        "REPLAY_STATE_HASHES", "CARD_02",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
