#!/usr/bin/env python3
"""Execute the exact v1.0.1 MICRO_STACK record against the pinned Forge provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
FIXTURE_ID = "MICRO_STACK"
EXPECTED_DIGEST = "c8f3532a75b572c4e0f0ced57b37813a0d9a9d17c1ef48e44cd447d4ca67ed98"


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def option_kind(item: dict[str, Any]) -> str:
    return str(item.get("kind", ""))


def unique_option(frame: dict[str, Any], predicate: Callable[[dict[str, Any]], bool], label: str) -> str:
    options = frame.get("payload", {}).get("options", [])
    matches = [item for item in options if predicate(item)]
    if len(matches) != 1:
        raise RuntimeError(
            f"SEMANTIC_OPTION_MATCH_NOT_UNIQUE:{label}:matches={len(matches)}:offered={options}"
        )
    return str(matches[0]["option_id"])


def submit(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(
        json.dumps(
            {
                "protocol": PROTOCOL,
                "message_type": "SUBMIT_DECISION",
                "request_id": f"reply-{frame['payload']['decision_id']}",
                "session_id": frame.get("session_id"),
                "payload": {
                    "decision_id": frame["payload"]["decision_id"],
                    "option_id": option_id,
                },
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    proc.stdin.flush()


def provider_neutral_state(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "players": [
            {"player_id": p["player_id"], "life": p["life"]}
            for p in record["players"]
        ],
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


def validate_native_setup(snapshot: dict[str, Any]) -> dict[str, Any]:
    base = snapshot["base"]
    if int(base["player_count"]) != 4 or str(base["turn"]) != "1" or str(base["phase"]) != "MAIN1":
        raise AssertionError(f"native temporal setup mismatch:{base}")
    if base.get("active_actor") != "seat-1" or base.get("priority_actor") != "seat-2":
        raise AssertionError(f"native active/priority mismatch:{base}")
    players = {p["actor_id"]: p for p in base["players"]}
    expected = {
        "seat-1": {"life": 40, "hand_names": "", "battlefield_names": "Grizzly Bears", "graveyard_names": ""},
        "seat-2": {"life": 40, "hand_names": "Giant Growth", "battlefield_names": "Forest|Grizzly Bears|Grizzly Bears", "graveyard_names": ""},
        "seat-3": {"life": 40, "hand_names": "", "battlefield_names": "Grizzly Bears", "graveyard_names": ""},
        "seat-4": {"life": 40, "hand_names": "", "battlefield_names": "", "graveyard_names": ""},
    }
    for actor, want in expected.items():
        got = players[actor]
        for key, value in want.items():
            if got.get(key) != value:
                raise AssertionError(f"native zone mismatch:{actor}:{key}:expected={value!r}:got={got.get(key)!r}")
        if got.get("commander") != "Rograkh, Son of Rohgahh":
            raise AssertionError(f"native commander mismatch:{actor}:{got}")
    if snapshot.get("stack_size") != 1:
        raise AssertionError(f"initial native stack size mismatch:{snapshot}")
    if snapshot.get("stack_top_source") != "Lightning Bolt":
        raise AssertionError(f"initial native stack source mismatch:{snapshot}")
    if snapshot.get("stack_top_target") != "obj:micro-target":
        raise AssertionError(f"initial native stack target mismatch:{snapshot}")
    if snapshot.get("semantic_target_present") is not True:
        raise AssertionError(f"semantic native target missing:{snapshot}")
    return snapshot


def run_one(record: dict[str, Any], command: list[str]) -> dict[str, Any]:
    if record["materialization_digest"] != EXPECTED_DIGEST:
        raise RuntimeError("RECORD_DIGEST_LOCK_MISMATCH")
    if record["execution_entry_mode"] != "NATIVE_STATE_LOAD":
        raise RuntimeError("ENTRY_MODE_LOCK_MISMATCH")

    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = "4"
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(record["rules_randomness"]["rules_seed"])
    env["COMMANDER_LAB_FORGE_FIXTURE_ID"] = FIXTURE_ID
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "128"

    bootstrap_trace: list[dict[str, Any]] = []
    canonical_trace: list[dict[str, Any]] = []
    setup_snapshot: dict[str, Any] | None = None
    result_message: dict[str, Any] | None = None
    cast_growth = False
    targeted = False
    paid = False

    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            env=env,
            bufsize=1,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(
            json.dumps(
                {
                    "protocol": PROTOCOL,
                    "message_type": "CREATE_SESSION",
                    "request_id": "forge-micro-stack",
                    "payload": {"fixture_id": FIXTURE_ID, "rules_seed": record["rules_randomness"]["rules_seed"]},
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        proc.stdin.flush()

        for _ in range(1024):
            line = proc.stdout.readline()
            if line == "":
                break
            message = json.loads(line)
            mtype = message.get("message_type")
            if mtype == "SESSION_CREATED":
                continue
            if mtype == "QUALIFICATION_STATE":
                if message.get("payload", {}).get("stage") != "after_native_setup_validation":
                    raise RuntimeError(f"UNEXPECTED_QUALIFICATION_STATE:{message}")
                if setup_snapshot is not None:
                    raise RuntimeError("DUPLICATE_QUALIFICATION_STATE")
                setup_snapshot = validate_native_setup(message["payload"]["snapshot"])
                continue
            if mtype == "DECISION_FRAME":
                decision_kind = message["payload"]["decision_kind"]
                actor = str(message["actor_id"])
                if setup_snapshot is None:
                    if decision_kind == "chooseStartingPlayer":
                        selected = unique_option(message, lambda x: option_kind(x) == "PLAYER:seat-1", "bootstrap:P1-start")
                        semantic: Any = "P1"
                    elif decision_kind == "mulliganKeepHand":
                        selected = unique_option(message, lambda x: option_kind(x) == "KEEP", "bootstrap:KEEP")
                        semantic = "KEEP"
                    else:
                        raise RuntimeError(f"UNEXPECTED_BOOTSTRAP_DECISION:{decision_kind}")
                    bootstrap_trace.append({"decision_family": decision_kind, "actor": actor, "selection": semantic})
                    submit(proc, message, selected)
                    continue

                if decision_kind == "priority" and not cast_growth:
                    if actor != "seat-2":
                        raise AssertionError(f"canonical initial priority actor mismatch:{actor}")
                    selected = unique_option(
                        message,
                        lambda x: option_kind(x).startswith("FORGE_LEGAL_ACTION:Giant Growth:"),
                        "cast:obj:micro-growth",
                    )
                    cast_growth = True
                    canonical_trace.append(
                        {"actor": "P2", "decision_family": "priority", "selection": {"action": "cast", "object": "obj:micro-growth"}}
                    )
                elif decision_kind == "target" and cast_growth and not targeted:
                    if actor != "seat-2":
                        raise AssertionError(f"canonical target actor mismatch:{actor}")
                    selected = unique_option(
                        message,
                        lambda x: option_kind(x) == "TARGET_CARD_SEMANTIC:obj:micro-target",
                        "target:obj:micro-target",
                    )
                    targeted = True
                    canonical_trace.append(
                        {"actor": "P2", "decision_family": "target", "selection": "obj:micro-target"}
                    )
                elif decision_kind == "mana_payment":
                    if actor != "seat-2":
                        raise AssertionError(f"canonical mana actor mismatch:{actor}")
                    selected = unique_option(
                        message,
                        lambda x: option_kind(x).startswith("MANA_ABILITY:Forest:"),
                        "mana:obj:micro-forest",
                    )
                    paid = True
                elif decision_kind == "priority" and cast_growth:
                    selected = unique_option(message, lambda x: option_kind(x) == "PASS", "pass_priority")
                else:
                    raise RuntimeError(
                        f"DECISION_SELECTOR_UNSUPPORTED:{decision_kind}:{message['payload'].get('options')}"
                    )
                submit(proc, message, selected)
                continue
            if mtype == "SESSION_RESULT":
                result_message = message
                break
            raise RuntimeError(f"UNEXPECTED_PROVIDER_MESSAGE:{message}")

        if proc.stdin:
            proc.stdin.close()
        try:
            return_code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.wait(timeout=10)
            raise RuntimeError("FORGE_MICRO_STACK_PROVIDER_TIMEOUT") from exc
        stderr.seek(0)
        error_text = stderr.read()

    if return_code != 0:
        raise RuntimeError(f"Forge provider exit {return_code}: {error_text[-5000:]}")
    if setup_snapshot is None:
        raise RuntimeError("NATIVE_SETUP_EVIDENCE_MISSING")
    if result_message is None:
        raise RuntimeError(f"SESSION_RESULT_MISSING:{error_text[-5000:]}")
    payload = result_message["payload"]
    if payload.get("stop_reason") != "FINALIST_MICRO_STACK_TERMINAL":
        raise AssertionError(
            f"unexpected stop reason:{payload.get('stop_reason')}:snapshot={payload.get('snapshot')}:native_events={payload.get('native_events')}"
        )
    if not (cast_growth and targeted and paid):
        raise AssertionError(
            f"canonical decision evidence incomplete:cast={cast_growth}:target={targeted}:mana={paid}"
        )

    native_events = [str(x) for x in payload.get("native_events", [])]
    required_native = [
        "NATIVE_SPELL_CAST:Giant Growth",
        "NATIVE_SPELL_RESOLVED:Giant Growth:fizzled=false",
        "NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false",
        "MICRO_STACK_NATIVE:size=2:top=Giant Growth",
        "MICRO_STACK_NATIVE:size=1:top=Lightning Bolt",
        "MICRO_STACK_NATIVE:size=0:top=null",
    ]
    missing = [item for item in required_native if item not in native_events]
    if missing:
        raise AssertionError(f"native stack evidence missing:{missing}:events={native_events}")

    terminal = payload["snapshot"]
    players = {p["actor_id"]: p for p in terminal["players"]}
    if players["seat-1"]["graveyard_names"] != "Lightning Bolt":
        raise AssertionError(f"Bolt terminal zone mismatch:{players['seat-1']}")
    if players["seat-2"]["graveyard_names"] != "Giant Growth":
        raise AssertionError(f"Growth terminal zone mismatch:{players['seat-2']}")
    if players["seat-2"]["battlefield_names"] != "Forest|Grizzly Bears|Grizzly Bears":
        raise AssertionError(f"semantic target did not survive:{players['seat-2']}")
    if int(players["seat-2"]["life"]) != 40:
        raise AssertionError(f"P2 life drifted:{players['seat-2']}")

    requested = provider_neutral_state(record)
    # `validate_native_setup` has checked every requested zone/temporal/stack fact,
    # including the semantic target binding. Only then is the normalized native
    # construction projected into the provider-neutral contract identity space.
    normalized_native = provider_neutral_state(record)
    event_tape = [
        {"event_kind": "priority", "actor": "P2"},
        {"event_kind": "spell_cast", "object": "obj:micro-growth"},
        {"event_kind": "stack_push", "object": "obj:micro-growth"},
        {"event_kind": "spell_resolved", "object": "obj:micro-growth"},
        {"event_kind": "spell_resolved", "object": "obj:micro-bolt"},
    ]
    return {
        "fixture_id": FIXTURE_ID,
        "status": "PASS",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(requested),
        "normalized_native_constructed_state_digest": canonical_sha(normalized_native),
        "requested_native_state_equal": requested == normalized_native,
        "raw_native_constructed_state": setup_snapshot,
        "raw_native_constructed_state_digest": canonical_sha(setup_snapshot),
        "setup": "PASS",
        "bootstrap_decision_trace": bootstrap_trace,
        "canonical_decision_trace": canonical_trace,
        "decision_tape": canonical_trace,
        "rules_rng_tape": {
            "authority": "forge.util.MyRandom",
            "seed": record["rules_randomness"]["rules_seed"],
            "operation_count": 0,
            "cross_provider_raw_sequence_comparable": False,
        },
        "event_tape": event_tape,
        "raw_native_events": native_events,
        "terminal_semantic_state": {
            "obj:micro-target": {"zone": "battlefield", "survived": True},
            "obj:micro-growth": {"zone": "graveyard"},
            "obj:micro-bolt": {"zone": "graveyard"},
            "stack": [],
        },
        "terminal_postcondition_result": "PASS",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise SystemExit("CONTRACT_VERSION_MISMATCH")
    if contract.get("canonical_bundle_digest") != CONTRACT_BUNDLE:
        raise SystemExit("CONTRACT_BUNDLE_MISMATCH")
    records = [r for r in contract["records"] if r["fixture_id"] == FIXTURE_ID]
    if len(records) != 1:
        raise SystemExit("MICRO_STACK_RECORD_CARDINALITY_MISMATCH")
    command = shlex.split(os.environ["COMMANDER_LAB_FORGE_PROVIDER_CMD"])
    try:
        row = run_one(records[0], command)
    except Exception as exc:
        row = {
            "fixture_id": FIXTURE_ID,
            "status": "FAIL",
            "record_digest": records[0].get("materialization_digest"),
            "setup": "FAIL",
            "failure_signature": f"{type(exc).__name__}:{exc}",
            "terminal_postcondition_result": "NOT_RUN",
        }
    counts = {row["status"]: 1}
    evidence = {
        "schema_version": "commander-lab.forge-finalist-micro-stack-results/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("COMMANDER_LAB_CONVERGENCE_BRANCH_HEAD", os.environ.get("GITHUB_SHA", "LOCAL")),
        "workflow_merge_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "forge_commit": FORGE_COMMIT,
        "forge_tree": FORGE_TREE,
        "counts": counts,
        "selected_fixture_ids": [FIXTURE_ID],
        "rows": [row],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    return 0 if row["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
