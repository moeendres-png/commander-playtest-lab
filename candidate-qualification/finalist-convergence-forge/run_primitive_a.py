#!/usr/bin/env python3
"""Execute only the two frozen v1.0.1 Primitive-A records against Forge.

The runner distinguishes bootstrap-only pregame choices from the canonical midgame
transaction. Every provider decision is selected by a unique semantic label emitted
from engine-generated native options; zero or multiple matches fail closed.
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
from typing import Any, Callable

PROTOCOL = "commander-lab.rules-service/1.1.0"
CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
IDS = ("PILOT_PRIORITY", "PILOT_TARGET")
EXPECTED_DIGESTS = {
    "PILOT_PRIORITY": "252b416e0022cf41ce42cc1a516c55866c874c6b239f10d04043430fc3966d2a",
    "PILOT_TARGET": "854a5cb7e4a6aee3a733e004972decbd503f5e7fc53980a4b5c7fd640ed3351b",
}


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def unique_option(frame: dict[str, Any], predicate: Callable[[dict[str, Any]], bool], label: str) -> str:
    options = frame.get("payload", {}).get("options", [])
    matches = [item for item in options if predicate(item)]
    if len(matches) != 1:
        raise RuntimeError(f"SEMANTIC_OPTION_MATCH_NOT_UNIQUE:{label}:matches={len(matches)}:offered={options}")
    return str(matches[0]["option_id"])


def kind(item: dict[str, Any]) -> str:
    return str(item.get("kind", ""))


def submit(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({
        "protocol": PROTOCOL,
        "message_type": "SUBMIT_DECISION",
        "request_id": f"reply-{frame['payload']['decision_id']}",
        "session_id": frame.get("session_id"),
        "payload": {
            "decision_id": frame["payload"]["decision_id"],
            "option_id": option_id,
        },
    }, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def normalized_requested_state() -> dict[str, Any]:
    return {
        "player_count": 4,
        "turn": "1",
        "phase": "MAIN1",
        "active_actor": "seat-1",
        "priority_actor": "seat-1",
        "players": [
            {"actor_id": "seat-1", "life": 40, "hand_names": "Lightning Bolt", "battlefield_names": "Grizzly Bears|Mountain", "graveyard_names": ""},
            {"actor_id": "seat-2", "life": 40, "hand_names": "", "battlefield_names": "Grizzly Bears", "graveyard_names": ""},
            {"actor_id": "seat-3", "life": 40, "hand_names": "", "battlefield_names": "Grizzly Bears", "graveyard_names": ""},
            {"actor_id": "seat-4", "life": 40, "hand_names": "", "battlefield_names": "", "graveyard_names": ""},
        ],
    }


def project_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    players = []
    for raw in snapshot["players"]:
        players.append({
            "actor_id": raw["actor_id"],
            "life": int(raw["life"]),
            "hand_names": raw.get("hand_names", ""),
            "battlefield_names": raw.get("battlefield_names", ""),
            "graveyard_names": raw.get("graveyard_names", ""),
        })
    return {
        "player_count": int(snapshot["player_count"]),
        "turn": str(snapshot["turn"]),
        "phase": str(snapshot["phase"]),
        "active_actor": snapshot.get("active_actor"),
        "priority_actor": snapshot.get("priority_actor"),
        "players": players,
    }


def terminal_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    by_actor = {item["actor_id"]: item for item in snapshot["players"]}
    return {
        "obj:pilot-bolt": {"zone": "graveyard" if "Lightning Bolt" in by_actor["seat-1"].get("graveyard_names", "").split("|") else "UNKNOWN"},
        "P2": {"life": int(by_actor["seat-2"]["life"])},
    }


def run_one(record: dict[str, Any], command: list[str]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    if record["materialization_digest"] != EXPECTED_DIGESTS[fixture_id]:
        raise RuntimeError("RECORD_DIGEST_LOCK_MISMATCH")
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = "4"
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(record["rules_randomness"]["rules_seed"])
    env["COMMANDER_LAB_FORGE_FIXTURE_ID"] = fixture_id
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "128"

    bootstrap_trace: list[dict[str, Any]] = []
    canonical_trace: list[dict[str, Any]] = []
    setup_snapshot: dict[str, Any] | None = None
    result_message: dict[str, Any] | None = None
    cast_selected = False
    target_selected = False
    mana_selected = False

    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            text=True, env=env, bufsize=1,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps({
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": f"forge-primitive-a-{fixture_id}",
            "payload": {"fixture_id": fixture_id, "rules_seed": record["rules_randomness"]["rules_seed"]},
        }, separators=(",", ":")) + "\n")
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
                if message.get("payload", {}).get("stage") != "after_native_setup_validation":
                    raise RuntimeError(f"UNEXPECTED_QUALIFICATION_STATE:{message}")
                if setup_snapshot is not None:
                    raise RuntimeError("DUPLICATE_QUALIFICATION_STATE")
                setup_snapshot = project_snapshot(message["payload"]["snapshot"])
                expected = normalized_requested_state()
                if setup_snapshot != expected:
                    raise AssertionError(f"requested/native state mismatch: requested={expected} native={setup_snapshot}")
                continue
            if mtype == "DECISION_FRAME":
                decision_kind = message["payload"]["decision_kind"]
                actor = str(message["actor_id"])
                if setup_snapshot is None:
                    if decision_kind == "chooseStartingPlayer":
                        selected = unique_option(message, lambda x: kind(x) == "PLAYER:seat-1", "bootstrap:P1-start")
                        semantic = "P1"
                    elif decision_kind == "mulliganKeepHand":
                        selected = unique_option(message, lambda x: kind(x) == "KEEP", "bootstrap:KEEP")
                        semantic = "KEEP"
                    else:
                        raise RuntimeError(f"UNEXPECTED_BOOTSTRAP_DECISION:{decision_kind}")
                    bootstrap_trace.append({"decision_family": decision_kind, "actor": actor, "selection": semantic})
                    submit(proc, message, selected)
                    continue

                if decision_kind == "priority" and not cast_selected:
                    selected = unique_option(
                        message,
                        lambda x: kind(x).startswith("FORGE_LEGAL_ACTION:Lightning Bolt:"),
                        "cast:obj:pilot-bolt",
                    )
                    cast_selected = True
                    canonical_trace.append({"actor": "P1", "decision_family": "priority", "selection": {"action": "cast", "object": "obj:pilot-bolt"}})
                elif decision_kind == "target" and not target_selected:
                    selected = unique_option(message, lambda x: kind(x) == "TARGET_PLAYER:seat-2", "target:P2")
                    target_selected = True
                    canonical_trace.append({"actor": "P1", "decision_family": "target", "selection": "P2"})
                elif decision_kind == "mana_payment":
                    selected = unique_option(message, lambda x: kind(x).startswith("MANA_ABILITY:Mountain:"), "mana:obj:pilot-mountain")
                    mana_selected = True
                    canonical_trace.append({"actor": "P1", "decision_family": "mana_payment", "selection": {"source": "obj:pilot-mountain", "mana": "R"}})
                elif decision_kind == "priority" and cast_selected:
                    selected = unique_option(message, lambda x: kind(x) == "PASS", "pass_priority")
                else:
                    raise RuntimeError(f"DECISION_SELECTOR_UNSUPPORTED:{decision_kind}:{message['payload'].get('options')}")
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
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=10)
            raise RuntimeError("FORGE_PRIMITIVE_A_PROVIDER_TIMEOUT")
        stderr.seek(0)
        error_text = stderr.read()

    if return_code != 0:
        raise RuntimeError(f"Forge provider exit {return_code}: {error_text[-5000:]}")
    if setup_snapshot is None:
        raise RuntimeError("NATIVE_SETUP_EVIDENCE_MISSING")
    if result_message is None:
        raise RuntimeError(f"SESSION_RESULT_MISSING:{error_text[-5000:]}")
    payload = result_message["payload"]
    if payload.get("stop_reason") != "FINALIST_PRIMITIVE_A_TERMINAL":
        raise AssertionError(f"unexpected stop reason: {payload.get('stop_reason')}")
    if not (cast_selected and target_selected and mana_selected):
        raise AssertionError(f"canonical decision evidence incomplete: cast={cast_selected} target={target_selected} mana={mana_selected}")

    terminal = terminal_projection(payload["snapshot"])
    expected_terminal = {"obj:pilot-bolt": {"zone": "graveyard"}, "P2": {"life": 37}}
    if terminal != expected_terminal:
        raise AssertionError(f"terminal mismatch: expected={expected_terminal} native={terminal}")
    native_events = [str(x) for x in payload.get("native_events", []) if str(x).startswith("NATIVE_SPELL_")]
    if "NATIVE_SPELL_CAST:Lightning Bolt" not in native_events:
        raise AssertionError(f"native Forge cast event missing: {native_events}")
    if "NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false" not in native_events:
        raise AssertionError(f"native Forge resolution event missing: {native_events}")

    event_tape = [
        {"event_kind": "spell_cast", "object": "obj:pilot-bolt", "source": "Forge GameEventSpellAbilityCast"},
        {"event_kind": "target_selected", "target": "P2", "source": "engine-first TargetRestrictions candidate"},
        {"event_kind": "spell_resolved", "object": "obj:pilot-bolt", "source": "Forge GameEventSpellResolved", "P2_life": 37},
    ]
    return {
        "fixture_id": fixture_id,
        "status": "PASS",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": canonical_sha(normalized_requested_state()),
        "normalized_native_constructed_state_digest": canonical_sha(setup_snapshot),
        "requested_native_state_equal": True,
        "setup": "PASS",
        "bootstrap_decision_trace": bootstrap_trace,
        "canonical_decision_trace": canonical_trace,
        "decision_tape": canonical_trace,
        "rules_rng_tape": {"authority": "forge.util.MyRandom", "seed": record["rules_randomness"]["rules_seed"], "cross_provider_raw_sequence_comparable": False},
        "event_tape": event_tape,
        "raw_native_events": native_events,
        "checkpoints": [{"name": "after_native_setup_validation", "semantic_state_sha256": canonical_sha(setup_snapshot)}],
        "terminal_semantic_state": terminal,
        "terminal_postcondition_result": "PASS",
        "native_stop_reason": payload["stop_reason"],
    }


def failed_row(record: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "fixture_id": record["fixture_id"], "status": "FAIL",
        "record_digest": record["materialization_digest"], "setup": "FAIL",
        "failure_signature": f"{type(exc).__name__}:{exc}",
        "requested_semantic_state_digest": None,
        "normalized_native_constructed_state_digest": None,
        "decision_tape": [], "event_tape": [], "rules_rng_tape": [], "checkpoints": [],
        "terminal_semantic_state": None, "terminal_postcondition_result": "NOT_RUN",
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
    by_id = {r["fixture_id"]: r for r in contract["records"]}
    command = shlex.split(args.provider_command)
    rows = []
    for fixture_id in IDS:
        record = by_id[fixture_id]
        try:
            rows.append(run_one(record, command))
        except Exception as exc:
            rows.append(failed_row(record, exc))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    evidence = {
        "schema_version": "commander-lab.forge-finalist-canonical-results/1.1.0",
        "selected_fixture_ids": list(IDS),
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "convergence_branch_head": os.environ.get("COMMANDER_LAB_CONVERGENCE_BRANCH_HEAD", "UNKNOWN"),
        "forge_commit": FORGE_COMMIT,
        "forge_tree": FORGE_TREE,
        "provider": "separate GPL JVM / existing WS25 provider + qualification-only Primitive-A overlay",
        "counts": counts,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    return 0 if counts.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
