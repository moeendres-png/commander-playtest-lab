#!/usr/bin/env python3
"""Run the exact neutral v1.0.1 Starter-18 against the isolated Forge sidecar.

Only native paths actually implemented by the convergence provider receive PASS. Every
other canonical dimension is terminally reported as setup-unsupported. The runner never
chooses an unspecified first/default option: starting player, mulligan, and all other
selections are matched by explicit semantic labels from the provider.
"""

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
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
NATURAL_IDS = {
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
}


def gate_order() -> list[str]:
    return [
        "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
        "PILOT_MULLIGAN", "PILOT_PRIORITY", "PILOT_TARGET", "HIDDEN_01", "HIDDEN_02",
        "MICRO_STACK", "MICRO_REPLACEMENT", "WS05-MP-COMBAT-4", "RNG_RULES_TAPE",
        "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
        "REPLAY_STATE_HASHES", "CARD_02",
    ]


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def expected_projection(player_count: int) -> dict[str, Any]:
    return {
        "player_count": player_count,
        "players": [
            {
                "player_id": f"P{seat}",
                "life": 40,
                "hand_count": 7,
                "library_count": 92,
                "commander": "Rograkh, Son of Rohgahh",
            }
            for seat in range(1, player_count + 1)
        ],
    }


def native_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    players = []
    for raw in snapshot.get("players", []):
        actor = str(raw.get("actor_id", ""))
        if not actor.startswith("seat-"):
            raise AssertionError(f"unexpected Forge actor id: {actor}")
        seat = int(actor.split("-", 1)[1])
        if raw.get("command_count") != 1:
            raise AssertionError(f"native command-zone count mismatch for {actor}: {raw}")
        players.append({
            "player_id": f"P{seat}",
            "life": int(raw["life"]),
            "hand_count": int(raw["hand_count"]),
            "library_count": int(raw["library_count"]),
            "commander": raw.get("commander"),
        })
    players.sort(key=lambda item: int(item["player_id"][1:]))
    return {"player_count": int(snapshot["player_count"]), "players": players}


def option_for_kind(frame: dict[str, Any], wanted: str) -> str:
    options = frame.get("payload", {}).get("options", [])
    matches = [str(option["option_id"]) for option in options if option.get("kind") == wanted]
    if len(matches) != 1:
        raise AssertionError(f"semantic option {wanted!r} was not unique: {options}")
    return matches[0]


def submit(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    if proc.stdin is None:
        raise RuntimeError("provider stdin unavailable")
    payload = {
        "protocol": PROTOCOL,
        "message_type": "SUBMIT_DECISION",
        "request_id": f"reply-{frame['payload']['decision_id']}",
        "session_id": frame.get("session_id"),
        "payload": {
            "decision_id": frame["payload"]["decision_id"],
            "option_id": option_id,
        },
    }
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def run_natural(record: dict[str, Any], command: list[str]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    player_count = len(record["players"])
    rules_seed = record["rules_randomness"]["rules_seed"]
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = str(player_count)
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(rules_seed)
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "0"

    semantic_decisions: list[dict[str, Any]] = []
    p1_mulligans = 0
    result_message: dict[str, Any] | None = None
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
        proc.stdin.write(json.dumps({
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": f"finalist-{fixture_id}",
            "payload": {"fixture_id": fixture_id, "rules_seed": rules_seed},
        }, separators=(",", ":")) + "\n")
        proc.stdin.flush()

        for _ in range(256):
            line = proc.stdout.readline()
            if line == "":
                break
            message = json.loads(line)
            mtype = message.get("message_type")
            if mtype == "DECISION_FRAME":
                kind = message["payload"]["decision_kind"]
                actor = str(message["actor_id"])
                if kind == "chooseStartingPlayer":
                    selected = option_for_kind(message, "PLAYER:seat-1")
                    semantic = "P1"
                elif kind == "mulliganKeepHand":
                    if fixture_id == "PILOT_MULLIGAN" and actor == "seat-1" and p1_mulligans == 0:
                        selected = option_for_kind(message, "MULLIGAN")
                        semantic = "MULLIGAN"
                        p1_mulligans += 1
                    else:
                        selected = option_for_kind(message, "KEEP")
                        semantic = "KEEP"
                else:
                    raise RuntimeError(f"unexpected natural-start discretion: {kind}")
                semantic_decisions.append({
                    "decision_kind": kind,
                    "actor": actor.replace("seat-", "P"),
                    "selected_semantic_option": semantic,
                })
                submit(proc, message, selected)
            elif mtype == "SESSION_RESULT":
                result_message = message
                break
        if proc.stdin:
            proc.stdin.close()
        try:
            return_code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.wait(timeout=10)
            raise RuntimeError(
                "Forge provider did not terminate after canonical natural-start stop"
            ) from exc
        stderr.seek(0)
        error_text = stderr.read()

    if return_code != 0:
        raise RuntimeError(f"Forge provider exit {return_code}: {error_text[-4000:]}")
    if result_message is None:
        raise RuntimeError(f"Forge provider emitted no SESSION_RESULT: {error_text[-4000:]}")
    payload = result_message["payload"]
    if payload.get("stop_reason") != "WS23_CONTROLLED_AFTER_PRIORITY_0":
        raise AssertionError(f"unexpected provider stop: {payload.get('stop_reason')}")
    if int(payload.get("priority_decisions", -1)) != 1:
        raise AssertionError(f"first native priority was not reached exactly once: {payload}")

    requested = expected_projection(player_count)
    native = native_projection(payload["snapshot"])
    if requested != native:
        raise AssertionError(f"requested/native state mismatch: requested={requested} native={native}")

    p1_trace = [item["selected_semantic_option"] for item in semantic_decisions if item["actor"] == "P1" and item["decision_kind"] == "mulliganKeepHand"]
    if fixture_id == "PILOT_MULLIGAN":
        if p1_trace != ["MULLIGAN", "KEEP"]:
            raise AssertionError(f"P1 canonical free-mulligan trace mismatch: {p1_trace}")
    elif p1_trace != ["KEEP"]:
        raise AssertionError(f"P1 keep trace mismatch: {p1_trace}")

    return {
        "fixture_id": fixture_id,
        "status": "PASS",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(requested),
        "normalized_native_constructed_state_digest": canonical_sha(native),
        "setup": "PASS",
        "semantic_decisions": semantic_decisions,
        "decision_tape": semantic_decisions,
        "rules_rng_tape": {
            "authority": "forge.util.MyRandom",
            "seed": rules_seed,
            "cross_provider_raw_sequence_comparable": False,
        },
        "event_tape": [],
        "checkpoints": [],
        "terminal_semantic_state": native,
        "terminal_postcondition_result": "PASS",
        "native_stop_reason": payload["stop_reason"],
    }


def unsupported(record: dict[str, Any]) -> dict[str, Any]:
    dimensions = sorted({
        str(step.get("operation"))
        for step in record.get("native_procedure", [])
        if step.get("operation") != "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE"
    })
    return {
        "fixture_id": record["fixture_id"],
        "status": "CANONICAL_SETUP_UNSUPPORTED",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": None,
        "normalized_native_constructed_state_digest": None,
        "setup": "CANONICAL_SETUP_UNSUPPORTED",
        "failure_signature": "FORGE_V101_TRANSLATOR_DIMENSION_NOT_YET_IMPLEMENTED:" + ",".join(dimensions),
        "semantic_decisions": [],
        "decision_tape": [],
        "rules_rng_tape": [],
        "event_tape": [],
        "checkpoints": [],
        "terminal_semantic_state": None,
        "terminal_postcondition_result": "NOT_RUN",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--provider-command", default=os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD"))
    args = ap.parse_args()
    if not args.provider_command:
        raise SystemExit("COMMANDER_LAB_FORGE_PROVIDER_CMD_REQUIRED")

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise SystemExit("CONTRACT_SCHEMA_LOCK_MISMATCH")
    if contract.get("canonical_bundle_digest") != CONTRACT_BUNDLE:
        raise SystemExit("CONTRACT_BUNDLE_LOCK_MISMATCH")
    by_id = {record["fixture_id"]: record for record in contract["records"]}
    if any(fixture_id not in by_id for fixture_id in gate_order()):
        raise SystemExit("STARTER18_ID_MISSING_FROM_CONTRACT")

    command = shlex.split(args.provider_command)
    rows: list[dict[str, Any]] = []
    for fixture_id in gate_order():
        record = by_id[fixture_id]
        if fixture_id not in NATURAL_IDS:
            rows.append(unsupported(record))
            continue
        try:
            rows.append(run_natural(record, command))
        except Exception as exc:
            failed = unsupported(record)
            failed.update({
                "status": "FAIL",
                "setup": "FAIL",
                "failure_signature": f"{type(exc).__name__}:{exc}",
            })
            rows.append(failed)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    evidence = {
        "schema_version": "commander-lab.forge-finalist-starter18/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "forge_commit": FORGE_COMMIT,
        "forge_tree": FORGE_TREE,
        "provider": "separate GPL JVM / WS25 broad provider + finalist semantic overlay",
        "counts": counts,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    return 0 if counts.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
