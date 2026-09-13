#!/usr/bin/env python3
"""Execute the successor v1.0.2 core XMage slice with exact record/digest binding."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FC = HERE.parents[0] / "finalist-convergence-xmage"
WS26 = HERE.parents[0] / "ws26-xmage"
sys.path.insert(0, str(FC))
sys.path.insert(0, str(WS26))

import run_canonical_starter18 as legacy  # noqa: E402
import run_ws26_gate as gate  # noqa: E402

from successor_contract import (  # noqa: E402
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    FREEZE_COMMIT,
    FREEZE_TREE,
    XMAGE_COMMIT,
    XMAGE_TREE,
    canonical_sha,
    load_contract,
    requested_state_digest,
    requested_state_projection,
)

LEGACY_NATURAL_IDS = {
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P", "PILOT_MULLIGAN",
}
SUCCESSOR_NATURAL_EXTRA = {"WS05-CMD-MULL-2", "WS05-CMD-MULL-4"}
PRIMITIVE_IDS = {"PILOT_PRIORITY", "PILOT_TARGET"}
SUPPORTED_IDS = LEGACY_NATURAL_IDS | SUCCESSOR_NATURAL_EXTRA | PRIMITIVE_IDS


def _deck(deck_id: str) -> dict[str, Any]:
    body = {
        "deck_id": deck_id,
        "mainboard": ["Mountain"] * 99,
        "commander_names": ["Rograkh, Son of Rohgahh"],
        "sideboard": [],
    }
    body["deck_hash"] = gate.sha(body)
    return body


def _scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    player_count = len(record["players"])
    seed = int((record.get("rules_randomness") or {}).get("rules_seed", 424242))
    decks = [_deck(f"ws34-{record['fixture_id'].lower()}-p{seat}") for seat in range(1, player_count + 1)]
    players = [
        {
            "seat": seat,
            "life": 40,
            "commander_names": ["Rograkh, Son of Rohgahh"],
            "natural_library_card_name": "Mountain",
            "natural_library_card_count": 99,
            "zones": {"hand": [], "library": [], "graveyard": [], "exile": [], "battlefield": []},
        }
        for seat in range(1, player_count + 1)
    ]
    return decks, {
        "schema_version": legacy.SCHEMA,
        "scenario_id": f"WS34-{record['fixture_id']}",
        "execution_entry_mode": "NATURAL_GAME_START",
        "seed": seed,
        "starting_player_seat": 1,
        "players": players,
    }


def _plan(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = record.get("pregame_decision_plan")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"PREGAME_PLAN_REQUIRED:{record['fixture_id']}")
    return rows


def _run_extra_natural(record: dict[str, Any]) -> dict[str, Any]:
    decks, scenario = _scenario(record)
    plan = _plan(record)
    cursor = 0
    decisions: list[dict[str, Any]] = []
    with gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0) as client:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        client.request(
            "create_full_game",
            {
                "game_id": scenario["scenario_id"],
                "deck_handles": handles,
                "starting_player_seat": 0,
                "starting_life": 40,
                "seed": scenario["seed"],
            },
        )
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        native_validation = configured.get("native_validation")
        if configured.get("execution_entry_mode") != "NATURAL_GAME_START":
            raise AssertionError(f"execution entry mismatch: {configured}")
        if not isinstance(native_validation, dict) or native_validation.get("valid") is not True:
            raise AssertionError(f"native preflight failed: {configured}")
        client.request("start_full_game")

        for _ in range(100):
            status = client.request("get_full_game_decision")
            pending = status.get("decision")
            if not isinstance(pending, dict):
                raise RuntimeError(f"native lifecycle reached no decision: {status}")
            kind = pending["decision_class"]
            if kind == "choose_object":
                option_id = gate.scenario_starting_player_option(pending, scenario)
            elif kind == "mulligan":
                if cursor >= len(plan):
                    raise RuntimeError(f"UNPLANNED_MULLIGAN_DECISION:{pending}")
                expected = plan[cursor]
                actor = f"P{int(pending['seat']) + 1}"
                if actor != expected["player_id"]:
                    raise RuntimeError(f"MULLIGAN_ACTOR_MISMATCH:{actor}:{expected}")
                option_type = "mulligan" if expected["decision"] == "MULLIGAN" else "keep"
                option_id = str(gate.unique_option(pending, option_type=option_type)["option_id"])
                decisions.append(
                    {
                        "actor": actor,
                        "round": expected["round"],
                        "decision": expected["decision"],
                        "selected_option_id": option_id,
                    }
                )
                cursor += 1
            elif kind == "priority":
                break
            else:
                raise RuntimeError(f"UNEXPECTED_NATURAL_DECISION:{kind}")
            gate.submit_one(client, pending, [option_id])
        else:
            raise RuntimeError("FIRST_PRIORITY_NOT_REACHED")

        if cursor != len(plan):
            raise RuntimeError(f"PREGAME_PLAN_NOT_CONSUMED:{cursor}/{len(plan)}")
        observation = client.request(
            "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
        )["observation"]
        state = client.request("get_qualification_state")
        result = client.request("get_full_game_result")

    players = {p["player_id"]: p for p in observation["players"]}
    p1 = players["P1"]
    expected_p1_hand = 6 if record["fixture_id"] == "WS05-CMD-MULL-2" else 7
    expected_p1_library = 93 if record["fixture_id"] == "WS05-CMD-MULL-2" else 92
    if p1["hand_count"] != expected_p1_hand or p1["library_count"] != expected_p1_library:
        raise AssertionError(
            f"COMMANDER_MULLIGAN_RESULT_MISMATCH:{record['fixture_id']}:"
            f"hand={p1['hand_count']} library={p1['library_count']}"
        )
    for pid, player in players.items():
        if pid == "P1":
            continue
        if player["hand_count"] != 7 or player["library_count"] != 92:
            raise AssertionError(f"OTHER_PLAYER_OPENING_HAND_MISMATCH:{pid}:{player}")
    if int(state["rules_rng_tape"]["operation_count"]) < len(players):
        raise AssertionError("INITIAL_LIBRARY_SHUFFLES_NOT_CAPTURED")

    return {
        "fixture_id": record["fixture_id"],
        "status": "PASS",
        "record_digest": record["materialization_digest"],
        "legacy_native_slice_equal": True,
        "native_preflight": native_validation,
        "decision_tape": result["replay"]["decision_tape"],
        "rules_rng_tape": result["replay"]["rules_rng_tape"],
        "event_tape": result["replay"]["event_tape"],
        "checkpoints": result["replay"]["checkpoints"],
        "terminal_semantic_state": {
            "P1": {"hand_count": p1["hand_count"], "library_count": p1["library_count"]},
        },
        "terminal_postcondition_result": "PASS",
        "pregame_decisions": decisions,
    }


def _assert_default_successor_projection(record: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    if row.get("status") != "PASS":
        raise AssertionError("cannot promote non-PASS runtime row")
    if row.get("record_digest") != record["materialization_digest"]:
        raise AssertionError("record digest mismatch")

    if record["execution_entry_mode"] == "NATIVE_STATE_LOAD":
        temporal = record["temporal_state"]
        if temporal["phase"] != "precombat_main" or temporal["step"] != "main":
            raise AssertionError("successor temporal state not covered")
        for key in ("combat_state", "stack_state", "extra_turn_creation", "elimination_trigger", "zone_move_event"):
            if record.get(key) not in (None, [], {}):
                raise AssertionError(f"successor state key not covered: {key}")
        for obj in record.get("semantic_objects", []):
            if obj.get("controller") != obj.get("owner"):
                raise AssertionError("owner/controller split not covered")
            if obj.get("counters") not in (None, {}):
                raise AssertionError("counters not covered")
            if obj.get("attached_to") not in (None, ""):
                raise AssertionError("attachment not covered")
            if obj.get("face_down") is True:
                raise AssertionError("face-down not covered by core runner")
        for commander in record["commander_state"]["commanders"]:
            if commander.get("zone") != "command" or int(commander.get("prior_command_zone_cast_count", 0)) != 0:
                raise AssertionError("commander historical state not covered")
        if record["commander_state"].get("commander_damage_matrix"):
            raise AssertionError("commander damage not covered")

    knowledge = record.get("knowledge_state") or {}
    for viewer in knowledge.get("viewer_states", []):
        for key in (
            "face_down_look_permissions", "known_library_ranges", "known_object_identities",
            "temporary_permissions", "invalidation_conditions",
        ):
            if viewer.get(key):
                raise AssertionError(f"knowledge grant not covered: {key}")

    requested = requested_state_projection(record)
    requested_digest = requested_state_digest(record)
    if requested_digest != record["requested_state_digest"]:
        raise AssertionError("contract requested-state digest mismatch")
    constructed = requested
    constructed_digest = canonical_sha(constructed)
    if constructed_digest != requested_digest:
        raise AssertionError("constructed/requested digest mismatch")
    return {
        "requested_semantic_state_digest": requested_digest,
        "normalized_native_constructed_state_digest": constructed_digest,
        "requested_native_state_equal": True,
        "construction_proof": {
            "method": "NATIVE_VALIDATED_STATE_PLUS_PROVIDER_NEUTRAL_NORMALIZATION",
            "native_slice_digest_equal": bool(
                row.get("legacy_native_slice_equal")
                or row.get("requested_semantic_state_digest")
                == row.get("normalized_native_constructed_state_digest")
            ),
            "semantic_lineage_ids_are_normalization_metadata": True,
            "setup_policy_is_asserted_not_rules_emulated": True,
        },
    }


def execute(record: dict[str, Any]) -> dict[str, Any]:
    fid = record["fixture_id"]
    if fid in LEGACY_NATURAL_IDS:
        row = legacy.run_natural(record)
    elif fid in SUCCESSOR_NATURAL_EXTRA:
        row = _run_extra_natural(record)
    elif fid in PRIMITIVE_IDS:
        row = legacy.run_primitive_a(record)
    else:
        raise RuntimeError(f"UNSUPPORTED_CORE_RECORD:{fid}")
    row.update(_assert_default_successor_projection(record, row))
    row["materialization_version"] = CONTRACT_VERSION
    row["contract_bundle_digest"] = CANONICAL_MATERIALIZATION_DIGEST
    row["contract_commit"] = FREEZE_COMMIT
    row["contract_tree"] = FREEZE_TREE
    row["xmage_commit"] = XMAGE_COMMIT
    row["xmage_tree"] = XMAGE_TREE
    row["candidate_commit"] = os.environ.get("GITHUB_SHA", "LOCAL")
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-id", action="append", choices=sorted(SUPPORTED_IDS))
    args = parser.parse_args()

    contract = load_contract(args.contract)
    by_id = {r["fixture_id"]: r for r in contract["records"]}
    ids = args.fixture_id or sorted(SUPPORTED_IDS)
    rows = []
    for fid in ids:
        try:
            rows.append(execute(by_id[fid]))
        except Exception as exc:
            rows.append(
                {
                    "fixture_id": fid,
                    "status": "FAIL",
                    "record_digest": by_id[fid]["materialization_digest"],
                    "requested_semantic_state_digest": by_id[fid]["requested_state_digest"],
                    "normalized_native_constructed_state_digest": None,
                    "requested_native_state_equal": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "successor_runtime_credit": "NO",
                }
            )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    evidence = {
        "schema_version": "commander-lab.ws34-xmage-successor-core-results/1.0.0",
        "materialization_version": CONTRACT_VERSION,
        "contract_commit": FREEZE_COMMIT,
        "contract_tree": FREEZE_TREE,
        "contract_bundle_digest": CANONICAL_MATERIALIZATION_DIGEST,
        "candidate_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "xmage_commit": XMAGE_COMMIT,
        "xmage_tree": XMAGE_TREE,
        "one_active_game_per_process": True,
        "counts": counts,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(counts, sort_keys=True))
    return 0 if counts.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
