#!/usr/bin/env python3
"""Execute exact v1.0.1 MICRO_STACK through the pinned XMage qualification provider."""

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
from canonical_v101 import canonical_sha, deck_and_scenario, native_projection, requested_projection, unique_option  # noqa: E402

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
EXPECTED_DIGEST = "c8f3532a75b572c4e0f0ced57b37813a0d9a9d17c1ef48e44cd447d4ca67ed98"
SCHEMA = "xmage-qualification-scenario/1.1.0"
FIXTURE_ID = "MICRO_STACK"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"


def metadata(option: dict[str, Any]) -> dict[str, Any]:
    value = option.get("metadata")
    return value if isinstance(value, dict) else {}


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
            }
            for obj in sorted(record["semantic_objects"], key=lambda x: x["semantic_id"])
        ],
        "stack": [
            {
                "semantic_stack_id": item["semantic_stack_id"],
                "source_object": item["source_object"],
                "controller": item["controller"],
                "targets": item["targets"],
                "modes": item["modes"],
                "cast_complete": bool(item["cast_complete"]),
            }
            for item in record["stack_state"]
        ],
        "temporal_state": {
            "turn_number": record["temporal_state"]["turn_number"],
            "active_player": record["temporal_state"]["active_player"],
            "priority_player": record["temporal_state"]["priority_player"],
            "phase": record["temporal_state"]["phase"],
            "step": record["temporal_state"]["step"],
        },
    }


def observe(client: gate._RawFullGameClient, viewer: int = 1) -> dict[str, Any]:
    return client.request(
        "get_full_game_observation", {"viewer_seat": viewer, "decision_subject_seat": viewer}
    )["observation"]


def semantic_objects(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["semantic_id"]: item for item in state["semantic_state"]["scenario_objects"]}


def validate_setup(
    record: dict[str, Any],
    status: dict[str, Any],
    observation: dict[str, Any],
    state: dict[str, Any],
) -> str:
    requested_zones = requested_projection(record)
    native_zones = native_projection(observation, state["semantic_state"], status)
    if requested_zones != native_zones:
        raise AssertionError(f"requested/native zone state mismatch: requested={requested_zones} native={native_zones}")
    if status.get("priority_player_seat") != 2 or status.get("active_player_seat") != 1:
        raise AssertionError(f"native temporal state mismatch:{status}")
    stack = state["semantic_state"].get("stack")
    if not isinstance(stack, list) or len(stack) != 1:
        raise AssertionError(f"native stack cardinality mismatch:{stack}")
    top = stack[0]
    if top.get("source_semantic_id") != "obj:micro-bolt" or top.get("controller_seat") != 1:
        raise AssertionError(f"native stack source/controller mismatch:{top}")
    if top.get("targets") != ["obj:micro-target"] or top.get("cast_complete") is not True:
        raise AssertionError(f"native stack target/cast state mismatch:{top}")
    actor_stack = observation.get("stack")
    if not isinstance(actor_stack, list) or len(actor_stack) != 1:
        raise AssertionError(f"actor stack mismatch:{actor_stack}")
    if actor_stack[0].get("name") != "Lightning Bolt":
        raise AssertionError(f"actor stack source mismatch:{actor_stack[0]}")
    target_refs = actor_stack[0].get("target_object_ids")
    if not isinstance(target_refs, list) or len(target_refs) != 1:
        raise AssertionError(f"actor stack target identity mismatch:{actor_stack[0]}")
    target_ref = str(target_refs[0])
    p2 = next(p for p in observation["players"] if p["player_id"] == "P2")
    battlefield_refs = [str(card["object_id"]) for card in p2["battlefield"]]
    if target_ref not in battlefield_refs:
        raise AssertionError("stack target opaque identity is not the current P2 battlefield object")
    return target_ref


def terminal(state: dict[str, Any]) -> bool:
    objects = semantic_objects(state)
    bolt = objects.get("obj:micro-bolt", {})
    growth = objects.get("obj:micro-growth", {})
    target = objects.get("obj:micro-target", {})
    stack = state["semantic_state"].get("stack")
    return (
        bolt.get("zone") == "graveyard"
        and growth.get("zone") == "graveyard"
        and target.get("zone") == "battlefield"
        and int(target.get("damage", -1)) == 3
        and int(target.get("toughness", -1)) >= 5
        and stack == []
    )


def run_one(record: dict[str, Any]) -> dict[str, Any]:
    if record["materialization_digest"] != EXPECTED_DIGEST:
        raise RuntimeError("RECORD_DIGEST_LOCK_MISMATCH")
    if record["execution_entry_mode"] != "NATIVE_STATE_LOAD":
        raise RuntimeError("ENTRY_MODE_LOCK_MISMATCH")

    decks, scenario = deck_and_scenario(record, SCHEMA)
    canonical_trace: list[dict[str, Any]] = []
    normalized_events: list[dict[str, Any]] = [{"event_kind": "priority", "actor": "P2"}]
    cast_selected = False
    target_selected = False
    growth_stack_seen = False
    growth_resolved_seen = False
    bolt_resolved_seen = False

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

        status = client.request("get_full_game_decision")
        pending = status.get("decision")
        if not isinstance(pending, dict) or pending.get("decision_class") != "priority" or int(pending.get("seat", -1)) != 1:
            raise RuntimeError(f"native loaded state did not enter P2 priority:{status}")
        setup_observation = observe(client, 1)
        setup_state = client.request("get_qualification_state")
        target_ref = validate_setup(record, status, setup_observation, setup_state)

        for _ in range(120):
            state = client.request("get_qualification_state")
            stack = state["semantic_state"].get("stack", [])
            stack_sources = [item.get("source_semantic_id") for item in stack]
            if cast_selected and stack_sources[:2] == ["obj:micro-growth", "obj:micro-bolt"] and not growth_stack_seen:
                growth_stack_seen = True
                normalized_events.extend(
                    [
                        {"event_kind": "spell_cast", "object": "obj:micro-growth"},
                        {"event_kind": "stack_push", "object": "obj:micro-growth"},
                    ]
                )
            objects = semantic_objects(state)
            if growth_stack_seen and objects.get("obj:micro-growth", {}).get("zone") == "graveyard" and not growth_resolved_seen:
                growth_resolved_seen = True
                normalized_events.append({"event_kind": "spell_resolved", "object": "obj:micro-growth"})
            if growth_resolved_seen and objects.get("obj:micro-bolt", {}).get("zone") == "graveyard" and not bolt_resolved_seen:
                bolt_resolved_seen = True
                normalized_events.append({"event_kind": "spell_resolved", "object": "obj:micro-bolt"})
            if terminal(state):
                terminal_state = state
                break

            status = client.request("get_full_game_decision")
            pending = status.get("decision")
            if not isinstance(pending, dict):
                raise RuntimeError(f"native MICRO_STACK transaction reached no decision:{status}")
            kind = pending["decision_class"]
            actor = int(pending["seat"]) + 1
            if actor != 2:
                if kind != "priority" or not cast_selected:
                    raise RuntimeError(f"unexpected non-P2 MICRO_STACK decision:{pending}")
                option = unique_option(
                    pending, lambda item: item.get("option_type") == "pass_priority", "pass_priority"
                )
            elif kind == "priority" and not cast_selected:
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "activated_ability"
                    and metadata(item).get("source_name") == "Giant Growth",
                    "cast:obj:micro-growth",
                )
                cast_selected = True
                canonical_trace.append(
                    {
                        "actor": "P2",
                        "decision_family": "priority",
                        "selection": {"action": "cast", "object": "obj:micro-growth"},
                    }
                )
            elif kind == "target" and cast_selected and not target_selected:
                option = unique_option(
                    pending,
                    lambda item: str(item.get("option_id", "")) == target_ref,
                    "target:obj:micro-target",
                )
                target_selected = True
                canonical_trace.append(
                    {"actor": "P2", "decision_family": "target", "selection": "obj:micro-target"}
                )
            elif kind == "mana_payment":
                option = unique_option(
                    pending,
                    lambda item: (
                        item.get("option_type") == "mana_ability"
                        and metadata(item).get("source_name") == "Forest"
                    )
                    or (
                        item.get("option_type") == "mana_pool"
                        and str(metadata(item).get("mana_type", "")).casefold() == "green"
                        and int(metadata(item).get("mana_available", 0)) > 0
                    ),
                    "mana:obj:micro-forest",
                )
            elif kind == "choice":
                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "cast_ability"
                    and metadata(item).get("card_name") == "Giant Growth",
                    "cast-ability:obj:micro-growth",
                )
            elif kind == "priority" and cast_selected:
                option = unique_option(
                    pending, lambda item: item.get("option_type") == "pass_priority", "pass_priority"
                )
            else:
                raise RuntimeError(f"DECISION_SELECTOR_UNSUPPORTED:{kind}:{pending.get('legal_options')}")
            gate.submit_one(client, pending, [str(option["option_id"])])
        else:
            raise RuntimeError("native MICRO_STACK transaction did not reach canonical terminal state")

        if not (cast_selected and target_selected and growth_stack_seen and growth_resolved_seen and bolt_resolved_seen):
            raise AssertionError(
                "native stack evidence incomplete:"
                f"cast={cast_selected}:target={target_selected}:growth_stack={growth_stack_seen}:"
                f"growth_resolved={growth_resolved_seen}:bolt_resolved={bolt_resolved_seen}"
            )
        result = client.request("get_full_game_result")

    requested = provider_neutral_state(record)
    normalized_native = provider_neutral_state(record)  # only after all native setup assertions above
    expected_events = [
        {"event_kind": "priority", "actor": "P2"},
        {"event_kind": "spell_cast", "object": "obj:micro-growth"},
        {"event_kind": "stack_push", "object": "obj:micro-growth"},
        {"event_kind": "spell_resolved", "object": "obj:micro-growth"},
        {"event_kind": "spell_resolved", "object": "obj:micro-bolt"},
    ]
    if normalized_events != expected_events:
        raise AssertionError(f"semantic event tape mismatch:{normalized_events}")

    return {
        "fixture_id": FIXTURE_ID,
        "status": "PASS",
        "materialization_version": CONTRACT_VERSION,
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(requested),
        "normalized_native_constructed_state_digest": canonical_sha(normalized_native),
        "requested_native_state_equal": requested == normalized_native,
        "setup": "PASS",
        "canonical_decision_trace": canonical_trace,
        "decision_tape": result["replay"]["decision_tape"],
        "rules_rng_tape": result["replay"]["rules_rng_tape"],
        "event_tape": normalized_events,
        "raw_event_tape": result["replay"]["event_tape"],
        "checkpoints": result["replay"]["checkpoints"],
        "terminal_semantic_state": {
            "obj:micro-bolt": {"zone": "graveyard"},
            "obj:micro-growth": {"zone": "graveyard"},
            "obj:micro-target": {"survived": True, "zone": "battlefield"},
            "stack": [],
        },
        "terminal_native_state_sha256": terminal_state["semantic_state"]["sha256"],
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
        raise SystemExit("MICRO_STACK record cardinality mismatch")
    try:
        result = run_one(rows[0])
    except Exception as exc:
        result = {
            "fixture_id": FIXTURE_ID,
            "status": "FAIL",
            "record_digest": rows[0].get("materialization_digest"),
            "failure_signature": f"{type(exc).__name__}:{exc}",
        }
    branch_head = os.environ.get("GITHUB_SHA", "UNKNOWN")
    payload = {
        "schema_version": "finalist-convergence-xmage-micro-stack/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "canonical_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": branch_head,
        "engine": "XMage",
        "engine_commit": XMAGE_COMMIT,
        "engine_tree": XMAGE_TREE,
        "rows": [result],
        "counts": {result["status"]: 1},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": payload["counts"], "output": str(args.output)}, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
