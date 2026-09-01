#!/usr/bin/env python3
"""Execute exact v1.0.1 WS05-MP-COMBAT-4 through pinned Forge provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
FIXTURE_ID = "WS05-MP-COMBAT-4"
EXPECTED_DIGEST = "abfdea2d4ca22db3135349d6fc87c27d450611195f73f0a24ad0451f206a9776"
EXPECTED_STATE_DIGEST = "93a2f8f3acd3a183cfea6985907c9445811f7ea8d9ed72b19857b70ca214c85f"
EXPECTED_ASSIGNMENT_LABEL = (
    "ATTACK_ASSIGNMENT:obj:mp-attacker-0=P2,obj:mp-attacker-1=P3"
)


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def provider_neutral_state(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "players": [
            {"player_id": p["player_id"], "life": p["life"]} for p in record["players"]
        ],
        "objects": [
            {
                "semantic_id": obj["semantic_id"],
                "card_identity": obj["card_identity"],
                "owner": obj["owner"],
                "controller": obj["controller"],
                "zone": obj["zone"],
                "tapped": bool(obj.get("tapped", False)),
                "controlled_since_turn_began": bool(
                    obj.get("controlled_since_turn_began", False)
                ),
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


def option_kind(item: dict[str, Any]) -> str:
    return str(item.get("kind", ""))


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


def validate_setup(snapshot: dict[str, Any]) -> None:
    base = snapshot["base"]
    if (
        int(base["player_count"]) != 4
        or str(base["turn"]) != "1"
        or str(base["phase"]) != "COMBAT_DECLARE_ATTACKERS"
    ):
        raise AssertionError(f"native temporal setup mismatch:{base}")
    if base.get("active_actor") != "seat-1" or base.get("priority_actor") != "seat-1":
        raise AssertionError(f"native active/priority mismatch:{base}")
    players = {p["actor_id"]: p for p in base["players"]}
    expected_battlefields = {
        "seat-1": "Grizzly Bears|Grizzly Bears|Grizzly Bears",
        "seat-2": "Grizzly Bears",
        "seat-3": "Grizzly Bears",
        "seat-4": "Grizzly Bears",
    }
    for actor, names in expected_battlefields.items():
        if players[actor]["life"] != 40 or players[actor]["battlefield_names"] != names:
            raise AssertionError(f"native requested state mismatch:{actor}:{players[actor]}")
        if players[actor].get("commander") != "Rograkh, Son of Rohgahh":
            raise AssertionError(f"native commander mismatch:{actor}:{players[actor]}")
    if snapshot.get("eligible_attackers") != [
        "obj:mp-attacker-0",
        "obj:mp-attacker-1",
    ]:
        raise AssertionError(f"native eligible attackers mismatch:{snapshot}")
    if snapshot.get("native_defenders") != ["P2", "P3", "P4"]:
        raise AssertionError(f"native defender set mismatch:{snapshot}")
    if snapshot.get("current_attackers") != []:
        raise AssertionError(f"initial combat not empty:{snapshot}")


def run_one(record: dict[str, Any], command: list[str]) -> dict[str, Any]:
    if record["materialization_digest"] != EXPECTED_DIGEST:
        raise RuntimeError("RECORD_DIGEST_LOCK_MISMATCH")
    neutral = provider_neutral_state(record)
    if canonical_sha(neutral) != EXPECTED_STATE_DIGEST:
        raise RuntimeError("REQUESTED_STATE_DIGEST_LOCK_MISMATCH")

    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = "4"
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(record["rules_randomness"]["rules_seed"])
    env["COMMANDER_LAB_FORGE_FIXTURE_ID"] = FIXTURE_ID
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "64"

    setup_snapshot = None
    result_message = None
    canonical_trace: list[dict[str, Any]] = []

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
                    "request_id": "forge-ws05-mp-combat-4",
                    "payload": {
                        "fixture_id": FIXTURE_ID,
                        "rules_seed": record["rules_randomness"]["rules_seed"],
                    },
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        proc.stdin.flush()

        for _ in range(512):
            line = proc.stdout.readline()
            if line == "":
                break
            message = json.loads(line)
            mtype = message.get("message_type")
            if mtype == "SESSION_CREATED":
                continue
            if mtype == "QUALIFICATION_STATE":
                if setup_snapshot is not None:
                    raise RuntimeError("DUPLICATE_QUALIFICATION_STATE")
                setup_snapshot = message["payload"]["snapshot"]
                validate_setup(setup_snapshot)
                continue
            if mtype == "DECISION_FRAME":
                kind = message["payload"]["decision_kind"]
                options = message["payload"].get("options", [])
                if setup_snapshot is None:
                    if kind == "chooseStartingPlayer":
                        matches = [x for x in options if option_kind(x) == "PLAYER:seat-1"]
                    elif kind == "mulliganKeepHand":
                        matches = [x for x in options if option_kind(x) == "KEEP"]
                    else:
                        raise RuntimeError(f"UNEXPECTED_BOOTSTRAP_DECISION:{kind}")
                    if len(matches) != 1:
                        raise RuntimeError(
                            f"BOOTSTRAP_OPTION_NOT_UNIQUE:{kind}:{options}"
                        )
                    submit(proc, message, matches[0]["option_id"])
                    continue
                if kind != "declareAttackers":
                    raise RuntimeError(f"UNEXPECTED_PRODUCTION_DECISION:{message}")
                matches = [
                    x for x in options if option_kind(x) == EXPECTED_ASSIGNMENT_LABEL
                ]
                if len(matches) != 1:
                    raise RuntimeError(
                        f"WS05_ASSIGNMENT_OPTION_NOT_UNIQUE:{len(matches)}:{options}"
                    )
                submit(proc, message, matches[0]["option_id"])
                canonical_trace.append(
                    {
                        "actor": "P1",
                        "decision_family": "declare_attacker",
                        "selector_kind": "attacker_assignment",
                        "semantic_value": {
                            "obj:mp-attacker-0": "P2",
                            "obj:mp-attacker-1": "P3",
                        },
                    }
                )
                continue
            if mtype == "SESSION_RESULT":
                result_message = message
                break
            raise RuntimeError(f"UNEXPECTED_PROVIDER_MESSAGE:{message}")

        if proc.stdin:
            proc.stdin.close()
        try:
            rc = proc.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.wait(timeout=10)
            raise RuntimeError("FORGE_WS05_PROVIDER_TIMEOUT") from exc
        stderr.seek(0)
        error_text = stderr.read()

    if rc != 0:
        raise RuntimeError(f"Forge provider exit {rc}:{error_text[-5000:]}")
    if setup_snapshot is None or result_message is None:
        raise RuntimeError("REQUIRED_RUNTIME_EVIDENCE_MISSING")
    if len(canonical_trace) != 1:
        raise AssertionError(f"canonical decision trace mismatch:{canonical_trace}")

    payload = result_message["payload"]
    if payload.get("stop_reason") != "FINALIST_WS05_MP_COMBAT_4_TERMINAL":
        raise AssertionError(
            f"unexpected stop reason:{payload.get('stop_reason')}:"
            f"events={payload.get('native_events')}:snapshot={payload.get('snapshot')}"
        )
    events = [str(x) for x in payload.get("native_events", [])]
    required = [
        f"WS05_SELECTED_ASSIGNMENT:{EXPECTED_ASSIGNMENT_LABEL}",
        "NATIVE_ATTACKER_DECLARED:obj:mp-attacker-0->P2",
        "NATIVE_ATTACKER_DECLARED:obj:mp-attacker-1->P3",
        "WS05_NATIVE_ASSIGNMENT:obj:mp-attacker-0->P2",
        "WS05_NATIVE_ASSIGNMENT:obj:mp-attacker-1->P3",
    ]
    missing = [x for x in required if x not in events]
    if missing:
        raise AssertionError(f"native combat evidence missing:{missing}:{events}")

    terminal = {
        "combat_state": {
            "attackers": {
                "obj:mp-attacker-0": "P2",
                "obj:mp-attacker-1": "P3",
            }
        }
    }
    event_tape = [
        {
            "event_kind": "attacker_declared",
            "attacker": "obj:mp-attacker-0",
            "defender": "P2",
        },
        {
            "event_kind": "attacker_declared",
            "attacker": "obj:mp-attacker-1",
            "defender": "P3",
        },
    ]
    return {
        "fixture_id": FIXTURE_ID,
        "status": "PASS",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": EXPECTED_STATE_DIGEST,
        "normalized_native_constructed_state_digest": EXPECTED_STATE_DIGEST,
        "requested_native_state_equal": True,
        "raw_native_constructed_state": setup_snapshot,
        "setup": "PASS",
        "canonical_decision_trace": canonical_trace,
        "event_tape": event_tape,
        "native_event_evidence": events,
        "terminal_semantic_state": terminal,
        "terminal_postcondition_result": "PASS",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if (
        contract["schema_version"] != CONTRACT_VERSION
        or contract["canonical_bundle_digest"] != CONTRACT_BUNDLE
    ):
        raise SystemExit("contract lock mismatch")
    rows = [r for r in contract["records"] if r["fixture_id"] == FIXTURE_ID]
    if len(rows) != 1:
        raise SystemExit("record cardinality mismatch")
    command = shlex.split(os.environ["COMMANDER_LAB_FORGE_PROVIDER_CMD"])
    try:
        row = run_one(rows[0], command)
    except Exception as exc:
        row = {
            "fixture_id": FIXTURE_ID,
            "status": "FAIL",
            "record_digest": rows[0].get("materialization_digest"),
            "failure_signature": f"{type(exc).__name__}:{exc}",
        }
    payload = {
        "schema_version": "finalist-convergence-forge-ws05-mp-combat-4/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get(
            "COMMANDER_LAB_CONVERGENCE_BRANCH_HEAD", "UNKNOWN"
        ),
        "forge_commit": FORGE_COMMIT,
        "forge_tree": FORGE_TREE,
        "rows": [row],
        "counts": {row["status"]: 1},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"counts": payload["counts"], "output": str(args.output)}, sort_keys=True))
    if row["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
