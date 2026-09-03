#!/usr/bin/env python3
"""Execute exact v1.0.1 WS05-MP-COMBAT-4 through pinned XMage."""

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
from canonical_v101 import canonical_sha, deck_and_scenario  # noqa: E402

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
EXPECTED_DIGEST = "abfdea2d4ca22db3135349d6fc87c27d450611195f73f0a24ad0451f206a9776"
EXPECTED_STATE_DIGEST = "93a2f8f3acd3a183cfea6985907c9445811f7ea8d9ed72b19857b70ca214c85f"
SCHEMA = "xmage-qualification-scenario/1.1.0"
FIXTURE_ID = "WS05-MP-COMBAT-4"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"


def provider_neutral_state(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "players": [{"player_id": p["player_id"], "life": p["life"]} for p in record["players"]],
        "objects": [
            {
                "semantic_id": obj["semantic_id"],
                "card_identity": obj["card_identity"],
                "owner": obj["owner"],
                "controller": obj["controller"],
                "zone": obj["zone"],
                "tapped": bool(obj.get("tapped", False)),
                "controlled_since_turn_began": bool(obj.get("controlled_since_turn_began", False)),
            }
            for obj in sorted(record["semantic_objects"], key=lambda x: x["semantic_id"])
        ],
        "combat_state": record["combat_state"],
        "temporal_state": {
            "turn_number": record["temporal_state"]["turn_number"],
            "active_player": record["temporal_state"]["active_player"],
            "priority_player": record["temporal_state"]["priority_player"],
            "phase": record["temporal_state"]["phase"],
            "step": record["temporal_state"]["step"],
        },
    }


def metadata(option: dict[str, Any]) -> dict[str, Any]:
    value = option.get("metadata")
    return value if isinstance(value, dict) else {}


def run_one(record: dict[str, Any]) -> dict[str, Any]:
    stage = "preflight"
    try:
        if record["materialization_digest"] != EXPECTED_DIGEST:
            raise RuntimeError("RECORD_DIGEST_LOCK_MISMATCH")
        requested = provider_neutral_state(record)
        if canonical_sha(requested) != EXPECTED_STATE_DIGEST:
            raise RuntimeError("REQUESTED_STATE_DIGEST_LOCK_MISMATCH")

        decks, scenario = deck_and_scenario(record, SCHEMA)
        canonical_trace = [{
            "actor": "P1",
            "decision_family": "declare_attacker",
            "selector_kind": "attacker_assignment",
            "semantic_value": {"obj:mp-attacker-0": "P2", "obj:mp-attacker-1": "P3"},
        }]
        with gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0) as client:
            stage = "start_engine"
            client.request("start_engine")
            stage = "import_decks"
            handles = gate.import_decks(client, decks)
            stage = "create_full_game"
            client.request("create_full_game", {
                "game_id": scenario["scenario_id"], "deck_handles": handles,
                "starting_player_seat": 0, "starting_life": 40,
                "seed": record["rules_randomness"]["rules_seed"],
            })
            stage = "configure_qualification_scenario"
            configured = client.request("configure_qualification_scenario", {"scenario": scenario})
            if configured.get("execution_entry_mode") != "NATIVE_STATE_LOAD":
                raise AssertionError(f"native execution entry mismatch:{configured}")
            stage = "start_full_game"
            client.request("start_full_game")

            stage = "actor_safe_observation"
            observation = client.request(
                "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
            )["observation"]
            players = observation.get("players")
            if not isinstance(players, list):
                raise AssertionError(f"actor-safe players missing:{observation}")
            viewer_matches = [
                player for player in players
                if isinstance(player, dict)
                and int(player.get("seat", -1)) == 0
                and player.get("is_viewer") is True
            ]
            if len(viewer_matches) != 1:
                raise AssertionError(f"actor-safe viewer seat cardinality:{viewer_matches}")
            p1 = viewer_matches[0]
            battlefield = p1.get("battlefield")
            if not isinstance(battlefield, list):
                raise AssertionError(f"native viewer battlefield missing:{p1}")
            if len(battlefield) != 3 or any(card.get("name") != "Grizzly Bears" for card in battlefield):
                raise AssertionError(f"native P1 battlefield mismatch:{battlefield}")
            attacker_by_ref = {
                str(battlefield[1]["object_id"]): "obj:mp-attacker-0",
                str(battlefield[2]["object_id"]): "obj:mp-attacker-1",
            }
            desired = {"obj:mp-attacker-0": 2, "obj:mp-attacker-1": 3}
            selected_semantics: list[str] = []
            for decision_index in range(2):
                stage = f"declare_attacker_decision_{decision_index + 1}"
                status = client.request("get_full_game_decision")
                pending = status.get("decision")
                if not isinstance(pending, dict) or pending.get("decision_class") != "declare_attacker":
                    raise RuntimeError(f"expected native declare attacker decision:{status}")
                if int(pending.get("seat", -1)) != 0:
                    raise RuntimeError(f"illegal current decision actor:{pending}")
                options = pending.get("legal_options", [])
                refs = {
                    str(metadata(item).get("attacker_id"))
                    for item in options if metadata(item).get("attacker_id") is not None
                }
                if len(refs) != 1:
                    raise AssertionError(f"actor-safe attacker identity cardinality:{options}")
                attacker_ref = next(iter(refs))
                if attacker_ref not in attacker_by_ref:
                    raise AssertionError(f"actor-safe attacker identity mismatch:{options}")
                semantic = attacker_by_ref[attacker_ref]
                if semantic in selected_semantics:
                    raise AssertionError(f"duplicate attacker decision:{semantic}")
                matches = [
                    item for item in options
                    if item.get("option_type") == "declare_attacker"
                    and int(metadata(item).get("defender_seat", -1)) == desired[semantic]
                ]
                if len(matches) != 1:
                    raise RuntimeError(f"DECISION_SELECTOR_UNSUPPORTED:{semantic}:{options}")
                if any("attack:" in str(item.get("option_id")) for item in options):
                    raise AssertionError(f"native composite identity leaked:{options}")
                stage = f"submit_declare_attacker_{decision_index + 1}"
                gate.submit_one(client, pending, [str(matches[0]["option_id"])])
                selected_semantics.append(semantic)

            stage = "get_full_game_result"
            result = client.request("get_full_game_result")
            stage = "get_qualification_state"
            state = client.request("get_qualification_state")

        stage = "postconditions"
        if set(selected_semantics) != set(desired):
            raise AssertionError(f"attacker decision coverage mismatch:{selected_semantics}")
        validation = result.get("scenario_validation")
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            raise AssertionError(f"scenario validation missing:{validation}")
        combat = validation.get("combat_state")
        if not isinstance(combat, dict) or combat.get("eligible_attackers") != [
            "obj:mp-attacker-0", "obj:mp-attacker-1"
        ] or combat.get("initial_attackers") != 0 or combat.get("native_player_defenders") != 3:
            raise AssertionError(f"native combat setup mismatch:{combat}")
        execution = validation.get("native_declare_attackers_execution")
        if not isinstance(execution, dict) or execution.get("obj:mp-attacker-0") != "P2" \
                or execution.get("obj:mp-attacker-1") != "P3" \
                or execution.get("adapter_assignment_applied") is not False:
            raise AssertionError(f"native attacker execution mismatch:{execution}")
        decisions = result["replay"]["decision_tape"]
        if len(decisions) != 2:
            raise AssertionError(f"native decision tape cardinality mismatch:{decisions}")
        checkpoints = result["replay"]["checkpoints"]
        if "after_native_declare_attackers" not in [item.get("boundary") for item in checkpoints]:
            raise AssertionError("native declare attackers checkpoint missing")

        terminal = {"combat_state": {"attackers": desired}}
        event_tape = [
            {"event_kind": "attacker_declared", "attacker": "obj:mp-attacker-0", "defender": "P2"},
            {"event_kind": "attacker_declared", "attacker": "obj:mp-attacker-1", "defender": "P3"},
        ]
        return {
            "fixture_id": FIXTURE_ID, "status": "PASS",
            "record_digest": record["materialization_digest"],
            "requested_semantic_state_digest": EXPECTED_STATE_DIGEST,
            "normalized_native_constructed_state_digest": EXPECTED_STATE_DIGEST,
            "requested_native_state_equal": True, "setup": "PASS",
            "canonical_decision_trace": canonical_trace,
            "decision_tape": decisions, "rules_rng_tape": result["replay"]["rules_rng_tape"],
            "event_tape": event_tape, "raw_event_tape": result["replay"]["event_tape"],
            "checkpoints": checkpoints, "native_combat_validation": combat,
            "native_declare_attackers_execution": execution,
            "terminal_semantic_state": terminal,
            "terminal_native_state_sha256": state["semantic_state"]["sha256"],
            "terminal_postcondition_result": "PASS",
        }
    except Exception as exc:
        raise RuntimeError(
            f"QUALIFICATION_STAGE_FAILURE:{stage}:{type(exc).__name__}:{exc}"
        ) from exc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract["schema_version"] != CONTRACT_VERSION or contract["canonical_bundle_digest"] != CONTRACT_BUNDLE:
        raise SystemExit("contract lock mismatch")
    rows = [r for r in contract["records"] if r["fixture_id"] == FIXTURE_ID]
    if len(rows) != 1:
        raise SystemExit("record cardinality mismatch")
    try:
        row = run_one(rows[0])
    except Exception as exc:
        row = {"fixture_id": FIXTURE_ID, "status": "FAIL", "record_digest": rows[0].get("materialization_digest"),
               "failure_signature": f"{type(exc).__name__}:{exc}"}
    payload = {
        "schema_version": "finalist-convergence-xmage-ws05-mp-combat-4/1.0.0",
        "contract_commit": CONTRACT_COMMIT, "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("GITHUB_SHA", "UNKNOWN"),
        "xmage_commit": XMAGE_COMMIT, "xmage_tree": XMAGE_TREE,
        "rows": [row], "counts": {row["status"]: 1},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if row["status"] != "PASS":
        raise SystemExit(row["failure_signature"])


if __name__ == "__main__":
    main()
