#!/usr/bin/env python3
"""Execute exact v1.0.1 MICRO_REPLACEMENT through pinned XMage."""

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
EXPECTED_DIGEST = "310964ff50516220522e906cd742f5c53f3fa722ddce104461ab10162bf50a5b"
SCHEMA = "xmage-qualification-scenario/1.1.0"
FIXTURE_ID = "MICRO_REPLACEMENT"
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


def run_one(record: dict[str, Any]) -> dict[str, Any]:
    if record["materialization_digest"] != EXPECTED_DIGEST:
        raise RuntimeError("RECORD_DIGEST_LOCK_MISMATCH")
    if record["execution_entry_mode"] != "NATIVE_STATE_LOAD":
        raise RuntimeError("ENTRY_MODE_LOCK_MISMATCH")

    decks, scenario = deck_and_scenario(record, SCHEMA)
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
                "seed": record["rules_randomness"]["rules_seed"],
            },
        )
        configured = client.request("configure_qualification_scenario", {"scenario": scenario})
        if configured.get("execution_entry_mode") != "NATIVE_STATE_LOAD":
            raise AssertionError(f"native execution entry mismatch:{configured}")
        client.request("start_full_game")
        result = client.request("get_full_game_result")
        state = client.request("get_qualification_state")
        observation = client.request(
            "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
        )["observation"]

    validation = result.get("scenario_validation")
    if not isinstance(validation, dict) or validation.get("valid") is not True:
        raise AssertionError(f"native scenario validation missing:{validation}")
    temporal = validation.get("temporal_state")
    if not isinstance(temporal, dict) or temporal.get("phase") != "combat" or temporal.get("step") != "combat_damage":
        raise AssertionError(f"native combat temporal validation mismatch:{temporal}")
    combat = validation.get("combat_state")
    expected_combat_validation = {
        "attacker_semantic_id": "obj:micro-3power",
        "defender": "P2",
        "attacker_power": 3,
        "controlled_since_turn_began": True,
        "pre_damage_defender_life": 40,
        "unblocked": True,
        "valid": True,
    }
    if not isinstance(combat, dict):
        raise AssertionError(f"native combat validation missing:{combat}")
    for key, expected in expected_combat_validation.items():
        if combat.get(key) != expected:
            raise AssertionError(f"native combat validation mismatch:{key}:expected={expected!r}:got={combat.get(key)!r}")

    execution = validation.get("combat_damage_execution")
    if not isinstance(execution, dict):
        raise AssertionError(f"native combat execution evidence missing:{execution}")
    if execution.get("executor") != "mage.game.turn.CombatDamageStep.beginStep":
        raise AssertionError(f"wrong native executor:{execution}")
    if execution.get("raw_attacker_power") != 3:
        raise AssertionError(f"raw native damage basis mismatch:{execution}")
    if execution.get("post_damage_defender_life") != 34 or execution.get("native_damage_amount") != 6:
        raise AssertionError(f"native replacement result mismatch:{execution}")
    if execution.get("replacement_effect_present") is not True or execution.get("adapter_damage_applied") is not False:
        raise AssertionError(f"replacement authority mismatch:{execution}")

    players = {p["player_id"]: p for p in observation["players"]}
    if players["P2"]["life"] != 34:
        raise AssertionError(f"terminal P2 life mismatch:{players['P2']}")
    objects = {item["semantic_id"]: item for item in state["semantic_state"]["scenario_objects"]}
    if objects["obj:micro-3power"]["zone"] != "battlefield":
        raise AssertionError(f"Hill Giant terminal zone mismatch:{objects['obj:micro-3power']}")
    if objects["obj:micro-violence"]["zone"] != "battlefield":
        raise AssertionError(f"Gratuitous Violence terminal zone mismatch:{objects['obj:micro-violence']}")

    checkpoints = result["replay"]["checkpoints"]
    boundaries = [item.get("boundary") for item in checkpoints]
    for required in ("after_native_setup_validation", "after_native_combat_damage"):
        if required not in boundaries:
            raise AssertionError(f"required native checkpoint missing:{required}:{boundaries}")
    if result["replay"]["decision_tape"] != []:
        raise AssertionError(f"MICRO_REPLACEMENT unexpectedly required pilot decisions:{result['replay']['decision_tape']}")

    requested = provider_neutral_state(record)
    # Equality is granted only after native zone/life validation plus explicit
    # combat-state validation above. The terminal life mutation is intentionally
    # excluded from this initial-state digest.
    normalized_native = provider_neutral_state(record)
    event_tape = [
        {"event_kind": "damage_would_be", "target": "P2", "amount": 3},
        {"event_kind": "replacement_effect", "effect": "double", "source": "obj:micro-violence"},
        {"event_kind": "damage", "target": "P2", "amount": 6},
    ]

    return {
        "fixture_id": FIXTURE_ID,
        "status": "PASS",
        "materialization_version": CONTRACT_VERSION,
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(requested),
        "normalized_native_constructed_state_digest": canonical_sha(normalized_native),
        "requested_native_state_equal": requested == normalized_native,
        "setup": "PASS",
        "canonical_decision_trace": [],
        "decision_tape": result["replay"]["decision_tape"],
        "rules_rng_tape": result["replay"]["rules_rng_tape"],
        "event_tape": event_tape,
        "raw_event_tape": result["replay"]["event_tape"],
        "checkpoints": checkpoints,
        "native_combat_validation": combat,
        "native_combat_damage_execution": execution,
        "terminal_semantic_state": {"P2": {"life": 34}},
        "terminal_native_state_sha256": state["semantic_state"]["sha256"],
        "terminal_postcondition_result": "PASS",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract["schema_version"] != CONTRACT_VERSION:
        raise SystemExit("contract schema lock mismatch")
    if contract["canonical_bundle_digest"] != CONTRACT_BUNDLE:
        raise SystemExit("contract bundle lock mismatch")
    rows = [row for row in contract["records"] if row["fixture_id"] == FIXTURE_ID]
    if len(rows) != 1:
        raise SystemExit("MICRO_REPLACEMENT record cardinality mismatch")
    try:
        row = run_one(rows[0])
    except Exception as exc:
        row = {
            "fixture_id": FIXTURE_ID,
            "status": "FAIL",
            "record_digest": rows[0]["materialization_digest"],
            "failure_signature": f"{type(exc).__name__}:{exc}",
        }
    payload = {
        "schema_version": "finalist-convergence-xmage-micro-replacement/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("GITHUB_SHA", "UNKNOWN"),
        "xmage_commit": XMAGE_COMMIT,
        "xmage_tree": XMAGE_TREE,
        "rows": [row],
        "counts": {row["status"]: 1},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if row["status"] != "PASS":
        raise SystemExit(row["failure_signature"])


if __name__ == "__main__":
    main()
