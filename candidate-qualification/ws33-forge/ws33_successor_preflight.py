#!/usr/bin/env python3
"""WS-33 baseline v1.0.2 construction-gate probe.

This runner deliberately gives zero successor behavioral credit. It proves whether the
current Finalist Forge provider emits the exact WS-32 normalized constructed-state
surface before any remediation is applied.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.2"
CONTRACT_COMMIT = "038d0f38635eecee4e331c99af41f148de267a26"
CONTRACT_TREE = "0d160128119f2bad30b220a17c43419b50b7edbe"
CONTRACT_BUNDLE = "61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
FORGE_VERSION = "2.0.15-SNAPSHOT"
FIXTURE = "PLAYER_COUNT_2P"


def one_option(frame: dict[str, Any], wanted: str) -> str:
    options = frame.get("payload", {}).get("options", [])
    matches = [str(x["option_id"]) for x in options if str(x.get("kind")) == wanted]
    if len(matches) != 1:
        raise RuntimeError(f"SEMANTIC_OPTION_NOT_UNIQUE:{wanted}:{options}")
    return matches[0]


def reply(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({
        "protocol": PROTOCOL,
        "message_type": "SUBMIT_DECISION",
        "request_id": f"reply-{frame['payload']['decision_id']}",
        "session_id": frame.get("session_id"),
        "payload": {"decision_id": frame["payload"]["decision_id"], "option_id": option_id},
    }, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def execute(record: dict[str, Any], command: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = "2"
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(record["rules_randomness"]["rules_seed"])
    env["COMMANDER_LAB_FORGE_FIXTURE_ID"] = FIXTURE
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "0"
    result: dict[str, Any] | None = None
    qualification_states: list[dict[str, Any]] = []
    decisions: list[dict[str, str]] = []
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=stderr, text=True, env=env, bufsize=1)
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps({
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": "ws33-baseline-player-count-2p",
            "payload": {"fixture_id": FIXTURE, "rules_seed": record["rules_randomness"]["rules_seed"]},
        }, separators=(",", ":")) + "\n")
        proc.stdin.flush()
        for _ in range(256):
            line = proc.stdout.readline()
            if not line:
                break
            msg = json.loads(line)
            mtype = msg.get("message_type")
            if mtype == "SESSION_CREATED":
                continue
            if mtype == "QUALIFICATION_STATE":
                qualification_states.append(msg)
                continue
            if mtype == "DECISION_FRAME":
                kind = str(msg["payload"]["decision_kind"])
                if kind == "chooseStartingPlayer":
                    selected, semantic = one_option(msg, "PLAYER:seat-1"), "P1"
                elif kind == "mulliganKeepHand":
                    selected, semantic = one_option(msg, "KEEP"), "KEEP"
                else:
                    raise RuntimeError(f"UNEXPECTED_DISCRETION:{kind}")
                decisions.append({"decision_kind": kind, "actor": str(msg.get("actor_id")), "selection": semantic})
                reply(proc, msg, selected)
                continue
            if mtype == "SESSION_RESULT":
                result = msg
                break
            raise RuntimeError(f"UNEXPECTED_PROVIDER_MESSAGE:{msg}")
        if proc.stdin:
            proc.stdin.close()
        try:
            rc = proc.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            proc.kill(); proc.wait(timeout=10)
            raise RuntimeError("FORGE_PROVIDER_TIMEOUT") from exc
        stderr.seek(0)
        err = stderr.read()
    if rc != 0:
        raise RuntimeError(f"FORGE_PROVIDER_EXIT:{rc}:{err[-5000:]}")
    if result is None:
        raise RuntimeError(f"SESSION_RESULT_MISSING:{err[-5000:]}")
    payload = result.get("payload", {})
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        raise RuntimeError("NATIVE_SNAPSHOT_MISSING")
    if int(snapshot.get("player_count", -1)) != 2:
        raise RuntimeError(f"NATIVE_PLAYER_COUNT_MISMATCH:{snapshot}")
    rows = snapshot.get("players", [])
    if len(rows) != 2:
        raise RuntimeError(f"NATIVE_PLAYER_ROWS_MISMATCH:{rows}")
    for row in rows:
        expected = {"life": 40, "hand_count": 7, "library_count": 92, "command_count": 1,
                    "commander": "Rograkh, Son of Rohgahh"}
        for key, value in expected.items():
            if row.get(key) != value:
                raise RuntimeError(f"NATIVE_FIELD_MISMATCH:{key}:{row}")
    normalized_messages = [m for m in qualification_states
                           if isinstance(m.get("payload", {}).get("normalized_constructed_state"), dict)]
    return {
        "fixture_id": FIXTURE,
        "materialization_digest": record["materialization_digest"],
        "requested_state_digest": record["requested_state_digest"],
        "native_runtime_reached": True,
        "narrow_native_snapshot_validation": "PASS",
        "native_snapshot": snapshot,
        "decision_trace": decisions,
        "qualification_state_count": len(qualification_states),
        "normalized_constructed_state_count": len(normalized_messages),
        "provider_emitted_normalized_constructed_state": bool(normalized_messages),
        "stop_reason": payload.get("stop_reason"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--digest-spec", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--provider-command", default=os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD"))
    args = ap.parse_args()
    if not args.provider_command:
        raise SystemExit("COMMANDER_LAB_FORGE_PROVIDER_CMD_REQUIRED")
    materialization = json.loads(args.materialization.read_text(encoding="utf-8"))
    spec = json.loads(args.digest_spec.read_text(encoding="utf-8"))
    assert materialization["schema_version"] == CONTRACT_VERSION
    assert materialization["canonical_bundle_digest"] == CONTRACT_BUNDLE
    assert spec["spec_version"] == "commander-lab.requested-state-digest/1.0.0"
    by_id = {r["fixture_id"]: r for r in materialization["records"]}
    assert len(by_id) == 135
    owned = sorted({x for x in by_id if not x.startswith("CARD_")} | {"CARD_02"})
    assert len(owned) == 107
    first = execute(by_id[FIXTURE], shlex.split(args.provider_command))
    if first["provider_emitted_normalized_constructed_state"]:
        raise SystemExit("BASELINE_ASSUMPTION_CHANGED:CURRENT_PROVIDER_ALREADY_EMITS_NORMALIZED_STATE")
    first.update({
        "status": "BASELINE_PROVIDER_GAP_CONFIRMED",
        "behavioral_credit": False,
        "defect_taxonomy": "FORGE_PROVIDER_DEFECT",
        "failure_signature": "WS32_NORMALIZED_CONSTRUCTED_STATE_NOT_EMITTED",
        "required_projection_keys": spec["projection_keys"],
        "credit_gate": spec["provider_credit_gate"],
    })
    out = {
        "schema_version": "commander-lab.ws33-baseline-preflight/1.0.0",
        "status": "BASELINE_PROVIDER_GAP_CONFIRMED",
        "contract": {"version": CONTRACT_VERSION, "commit": CONTRACT_COMMIT, "tree": CONTRACT_TREE,
                     "bundle_digest": CONTRACT_BUNDLE, "record_count": 135, "ws33_owned_denominator": 107},
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE, "version": FORGE_VERSION},
        "first_record_result": first,
        "successor_behavioral_credit": 0,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "WS33_BASELINE_PREFLIGHT.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": out["status"], "fixture": FIXTURE, "successor_behavioral_credit": 0}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
