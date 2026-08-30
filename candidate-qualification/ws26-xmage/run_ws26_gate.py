#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shlex
from copy import deepcopy
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.full_game import _RawFullGameClient, FullGameProtocolError

SEED = 424242
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"
WS22_HEAD = "99cdc2372a6d87a4a09bba2d4f3c23713f53a444"
SCHEMA = "xmage-qualification-scenario/1.0.0"


def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def command() -> tuple[str, ...]:
    raw = os.environ.get("COMMANDER_LAB_XMAGE_WS26_BRIDGE_CMD", "").strip()
    if not raw:
        raise RuntimeError("COMMANDER_LAB_XMAGE_WS26_BRIDGE_CMD is required")
    cmd = tuple(shlex.split(raw))
    if "full-game" not in cmd:
        raise RuntimeError("WS26 bridge command must contain full-game marker")
    return cmd


def deck_payload(deck_id: str, commander_names: list[str], special_cards: list[str]) -> dict[str, Any]:
    main_count = 100 - len(commander_names)
    if len(special_cards) > main_count:
        raise ValueError("too many special cards")
    mainboard = list(special_cards) + ["Plains"] * (main_count - len(special_cards))
    body = {"deck_id": deck_id, "mainboard": mainboard, "commander_names": commander_names, "sideboard": []}
    body["deck_hash"] = sha(body)
    return body


def import_decks(client: _RawFullGameClient, decks: list[dict[str, Any]]) -> list[str]:
    handles: list[str] = []
    for deck in decks:
        result = client.request("import_deck", {"deck": deck})
        handles.append(str(result["deck_handle"]["handle_id"]))
    return handles


def base_player(seat: int, commanders: list[str], *, library_count: int = 24) -> dict[str, Any]:
    return {
        "seat": seat,
        "life": 40,
        "commander_names": commanders,
        "zones": {
            "hand": [],
            "library": [
                {"semantic_id": f"p{seat}-library-{i:02d}", "card_name": "Plains", "face": "main"}
                for i in range(1, library_count + 1)
            ],
            "graveyard": [],
            "exile": [],
            "battlefield": [],
        },
    }


def replay_scenario() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    commanders = ["Kenrith, the Returned King"]
    decks = [deck_payload(f"ws26-replay-p{i}", commanders, ["Mana Crypt"] if i == 1 else []) for i in range(1, 5)]
    players = [base_player(i, commanders) for i in range(1, 5)]
    players[0]["zones"]["battlefield"].append(
        {"semantic_id": "p1-mana-crypt", "card_name": "Mana Crypt", "tapped": False, "controller_seat": 1, "face": "main"}
    )
    scenario = {
        "schema_version": SCHEMA,
        "scenario_id": "WS26-REPLAY-MANA-CRYPT",
        "seed": SEED,
        "starting_player_seat": 1,
        "players": players,
    }
    return decks, scenario


def hidden03_scenario() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    commanders = ["Kenrith, the Returned King"]
    decks = [
        deck_payload("ws26-hidden-p1", commanders, []),
        deck_payload("ws26-hidden-p2", commanders, ["Lightning Bolt"]),
        deck_payload("ws26-hidden-p3", commanders, []),
        deck_payload("ws26-hidden-p4", commanders, []),
    ]
    players = [base_player(i, commanders) for i in range(1, 5)]
    players[1]["zones"]["exile"].append(
        {"semantic_id": "p2-public-exile", "card_name": "Lightning Bolt", "face": "main"}
    )
    return decks, {
        "schema_version": SCHEMA,
        "scenario_id": "HIDDEN_03",
        "seed": SEED,
        "starting_player_seat": 1,
        "players": players,
    }


def create_and_configure(client: _RawFullGameClient, decks: list[dict[str, Any]], scenario: dict[str, Any]) -> dict[str, Any]:
    handles = import_decks(client, decks)
    client.request("create_full_game", {
        "game_id": scenario["scenario_id"],
        "deck_handles": handles,
        "starting_player_seat": scenario["starting_player_seat"] - 1,
        "starting_life": 40,
        "seed": scenario["seed"],
    })
    return client.request("configure_qualification_scenario", {"scenario": scenario})


def unique_option(decision: dict[str, Any], *, option_type: str | None = None, label_contains: str | None = None) -> dict[str, Any]:
    options = decision.get("legal_options") or []
    matches = []
    for option in options:
        if option_type is not None and option.get("option_type") != option_type:
            continue
        if label_contains is not None and label_contains.casefold() not in str(option.get("label", "")).casefold():
            continue
        matches.append(option)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one offered option type={option_type!r} label~={label_contains!r}; got {matches!r}")
    return matches[0]


def submit_one(client: _RawFullGameClient, decision: dict[str, Any], selected_ids: list[str], ordering: list[str] | None = None, numeric: int | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "decision_id": decision["decision_id"],
        "actor_id": decision["actor_id"],
        "selected_option_ids": selected_ids,
        "ordering": ordering or [],
    }
    if numeric is not None:
        response["numeric_choice"] = numeric
    return client.request("submit_full_game_decision", {"response": response})


def capture_replay_run(expected_tape: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    decks, scenario = replay_scenario()
    with _RawFullGameClient(command(), request_timeout_seconds=180.0) as client:
        client.request("start_engine")
        configured = create_and_configure(client, decks, scenario)
        assert configured["native_validation"]["valid"] is True
        client.request("start_full_game")
        steps = 0
        while steps < 120:
            state = client.request("get_qualification_state")
            if int(state["rules_rng_tape"]["operation_count"]) > 0:
                break
            status = client.request("get_full_game_decision")
            decision = status.get("decision")
            if not isinstance(decision, dict):
                raise RuntimeError(f"no pending decision before RNG operation: {status}")
            if expected_tape is not None and steps < len(expected_tape):
                recorded = expected_tape[steps]
                if decision["decision_class"] != recorded["decision_kind"]:
                    raise RuntimeError("clean replay decision kind mismatch")
                selected = [str(x) for x in recorded["selected_semantic_option_ids"]]
                offered = {str(o["option_id"]) for o in decision.get("legal_options") or []}
                if not set(selected).issubset(offered):
                    raise RuntimeError(f"clean replay semantic option identity mismatch: selected={selected} offered={offered}")
            elif decision["decision_class"] == "mulligan":
                selected = [str(unique_option(decision, option_type="keep")["option_id"])]
            elif decision["decision_class"] == "priority":
                selected = [str(unique_option(decision, option_type="pass_priority")["option_id"])]
            else:
                raise RuntimeError(f"unexpected discretionary class in replay seed fixture: {decision['decision_class']}")
            submit_one(client, decision, selected)
            steps += 1
        else:
            raise RuntimeError("Rules RNG tape did not record an operation within 120 decisions")
        final_state = client.request("get_qualification_state")
        result = client.request("get_full_game_result")
        replay = result["replay"]
        return {
            "scenario": scenario,
            "configured": configured,
            "steps": steps,
            "final_state": final_state["semantic_state"],
            "rules_rng_tape": replay["rules_rng_tape"],
            "decision_tape": replay["decision_tape"],
            "event_tape": replay["event_tape"],
            "checkpoints": replay["checkpoints"],
            "hashes": {
                "rules_rng": replay["rules_rng_tape"]["sha256"],
                "decision": replay["decision_tape_sha256"],
                "event": replay["event_tape_sha256"],
                "checkpoints": replay["checkpoints_sha256"],
                "final_state": final_state["semantic_state"]["sha256"],
            },
        }


def negative_suite() -> list[dict[str, Any]]:
    decks, valid = replay_scenario()
    cases: list[tuple[str, dict[str, Any], str]] = []
    def add(name: str, mutate, expected: str) -> None:
        data = deepcopy(valid); mutate(data); cases.append((name, data, expected))

    add("object_in_two_zones", lambda s: s["players"][0]["zones"]["hand"].append(deepcopy(s["players"][0]["zones"]["battlefield"][0])), "DUPLICATE_SEMANTIC_IDENTITY")
    add("invalid_player_identity", lambda s: s["players"][3].__setitem__("seat", 99), "INVALID_PLAYER_IDENTITY")
    add("nonexistent_controller", lambda s: s["players"][0]["zones"]["battlefield"][0].__setitem__("controller_seat", 99), "UNSUPPORTED_SCENARIO_DIMENSION")
    add("invalid_commander_ownership", lambda s: s["players"][0].__setitem__("commander_names", ["Isamaru, Hound of Konda"]), "INVALID_COMMANDER_OWNERSHIP")
    add("invalid_priority_holder", lambda s: s.__setitem__("priority_holder", 1), "UNSUPPORTED_SCENARIO_DIMENSION")
    add("unauthorized_hidden_information", lambda s: s["players"][0]["zones"]["hand"].append({"semantic_id":"secret","card_name":"Plains","known_to":[2]}), "UNSUPPORTED_SCENARIO_DIMENSION")
    add("stale_object_reference", lambda s: s["players"][0]["zones"]["hand"].append({"semantic_id":"stale","card_name":"Definitely Not A Real Card"}), "STALE_OBJECT_OR_CARD_REFERENCE")
    add("impossible_attachment", lambda s: s["players"][0]["zones"]["battlefield"][0].__setitem__("attached_to", "missing"), "UNSUPPORTED_SCENARIO_DIMENSION")
    add("duplicate_semantic_identity", lambda s: s["players"][1]["zones"]["library"][0].__setitem__("semantic_id", s["players"][0]["zones"]["library"][0]["semantic_id"]), "DUPLICATE_SEMANTIC_IDENTITY")
    add("invalid_card_face", lambda s: s["players"][0]["zones"]["battlefield"][0].__setitem__("face", "nonexistent-face"), "INVALID_CARD_FACE_REFERENCE")

    observed = []
    with _RawFullGameClient(command(), request_timeout_seconds=180.0) as client:
        client.request("start_engine")
        handles = import_decks(client, decks)
        client.request("create_full_game", {"game_id":"WS26-NEGATIVES","deck_handles":handles,"starting_player_seat":0,"starting_life":40,"seed":SEED})
        for name, scenario, expected in cases:
            try:
                client.request("configure_qualification_scenario", {"scenario": scenario})
            except FullGameProtocolError as exc:
                text = str(exc)
                if expected not in text:
                    raise AssertionError(f"{name}: expected {expected}, got {text}") from exc
                observed.append({"case": name, "verdict": "PASS", "expected_rejection": expected})
            else:
                raise AssertionError(f"{name}: malformed scenario silently became configured")
    return observed


def hidden03() -> dict[str, Any]:
    decks, scenario = hidden03_scenario()
    with _RawFullGameClient(command(), request_timeout_seconds=180.0) as client:
        client.request("start_engine")
        create_and_configure(client, decks, scenario)
        client.request("start_full_game")
        obs = client.request("get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0})["observation"]
        text = json.dumps(obs, sort_keys=True)
        if "Lightning Bolt" not in text:
            raise AssertionError("HIDDEN_03: P1 did not receive face-up exile identity")
        return {"fixture_id": "HIDDEN_03", "verdict": "PASS", "evidence_class": "RUNTIME_VERIFIED", "observation_sha256": sha(obs)}


def main() -> int:
    out = Path("qualification/evidence/ws26-xmage")
    out.mkdir(parents=True, exist_ok=True)
    negatives = negative_suite()
    first = capture_replay_run()
    second = capture_replay_run(first["decision_tape"])
    if first["hashes"] != second["hashes"]:
        raise AssertionError(f"clean-process replay mismatch: {first['hashes']} != {second['hashes']}")
    if first["rules_rng_tape"]["operation_count"] <= 0:
        raise AssertionError("Rules RNG tape did not record semantic RNG operations")
    hidden = hidden03()
    report = {
        "schema_version": "ws26-runtime-gate/1.0.0",
        "source_lock": {"commander_lab_ws22_head": WS22_HEAD, "xmage_commit": XMAGE_COMMIT, "xmage_tree": XMAGE_TREE},
        "scenario_negative_suite": negatives,
        "replay_first": first,
        "replay_second": second,
        "clean_process_replay_match": True,
        "replay_common_fixtures": {
            "RNG_RULES_TAPE": "PASS",
            "REPLAY_DECISION_TAPE": "PASS",
            "REPLAY_EVENT_TAPE": "PASS",
            "REPLAY_CLEAN_PROCESS": "PASS",
            "REPLAY_STATE_HASHES": "PASS",
        },
        "representative_common_fixtures": [hidden],
    }
    (out / "WS26_RUNTIME_GATE.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"clean_process_replay_match": True, "rng_operations": first["rules_rng_tape"]["operation_count"], "negative_cases": len(negatives), "hidden": hidden}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
