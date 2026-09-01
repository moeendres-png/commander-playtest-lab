#!/usr/bin/env python3
"""WS-33 Forge successor v1.0.2 foundational construction-gate preflight.

This is deliberately fail-closed. It executes the first canonical WS-33 record through
the separate Forge JVM, validates the narrow native snapshot that the current provider
actually emits, and then checks the stronger WS-32 v1.0.2 construction-credit contract.
No historical v1.0.1 result is promoted.
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
CONTRACT_COMMIT = "038d0f386acc5dbd8b2cebfcf7d3ab4e87fb84de"
CONTRACT_TREE = "9d3592d8ab8d232b8e3f55128b1951ab4564e8e5"
CONTRACT_BUNDLE = "61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
FORGE_VERSION = "2.0.15-SNAPSHOT"
FIRST_FIXTURE = "PLAYER_COUNT_2P"

def unique_kind(frame: dict[str, Any], wanted: str) -> str:
    opts = frame.get("payload", {}).get("options", [])
    matches = [str(x["option_id"]) for x in opts if str(x.get("kind")) == wanted]
    if len(matches) != 1:
        raise RuntimeError(f"SEMANTIC_OPTION_NOT_UNIQUE:{wanted}:{opts}")
    return matches[0]

def submit(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({
        "protocol": PROTOCOL,
        "message_type": "SUBMIT_DECISION",
        "request_id": f"reply-{frame['payload']['decision_id']}",
        "session_id": frame.get("session_id"),
        "payload": {"decision_id": frame["payload"]["decision_id"], "option_id": option_id},
    }, separators=(",", ":")) + "\n")
    proc.stdin.flush()

def run_first_record(record: dict[str, Any], command: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = "2"
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(record["rules_randomness"]["rules_seed"])
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "0"
    result = None
    decisions: list[dict[str, str]] = []
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            text=True, env=env, bufsize=1
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps({
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": "ws33-successor-player-count-2p",
            "payload": {"fixture_id": FIRST_FIXTURE, "rules_seed": record["rules_randomness"]["rules_seed"]},
        }, separators=(",", ":")) + "\n")
        proc.stdin.flush()
        for _ in range(256):
            line = proc.stdout.readline()
            if not line:
                break
            msg = json.loads(line)
            if msg.get("message_type") == "DECISION_FRAME":
                kind = msg["payload"]["decision_kind"]
                actor = str(msg.get("actor_id"))
                if kind == "chooseStartingPlayer":
                    selected = unique_kind(msg, "PLAYER:seat-1")
                    semantic = "P1"
                elif kind == "mulliganKeepHand":
                    selected = unique_kind(msg, "KEEP")
                    semantic = "KEEP"
                else:
                    raise RuntimeError(f"UNEXPECTED_DISCRETION:{kind}")
                decisions.append({"decision_kind": kind, "actor": actor, "selection": semantic})
                submit(proc, msg, selected)
            elif msg.get("message_type") == "SESSION_RESULT":
                result = msg
                break
        if proc.stdin:
            proc.stdin.close()
        try:
            rc = proc.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.wait(timeout=10)
            raise RuntimeError("FORGE_PROVIDER_TIMEOUT") from exc
        stderr.seek(0)
        err = stderr.read()
    if rc != 0:
        raise RuntimeError(f"FORGE_PROVIDER_EXIT:{rc}:{err[-4000:]}")
    if result is None:
        raise RuntimeError(f"SESSION_RESULT_MISSING:{err[-4000:]}")
    payload = result.get("payload", {})
    snap = payload.get("snapshot")
    if not isinstance(snap, dict):
        raise RuntimeError("NATIVE_SNAPSHOT_MISSING")
    if int(snap.get("player_count", -1)) != 2:
        raise RuntimeError(f"NATIVE_PLAYER_COUNT_MISMATCH:{snap}")
    players = snap.get("players", [])
    if len(players) != 2:
        raise RuntimeError(f"NATIVE_PLAYER_ROWS_MISMATCH:{players}")
    for row in players:
        if int(row.get("life", -1)) != 40:
            raise RuntimeError(f"NATIVE_LIFE_MISMATCH:{row}")
        if int(row.get("hand_count", -1)) != 7:
            raise RuntimeError(f"NATIVE_HAND_COUNT_MISMATCH:{row}")
        if int(row.get("library_count", -1)) != 92:
            raise RuntimeError(f"NATIVE_LIBRARY_COUNT_MISMATCH:{row}")
        if int(row.get("command_count", -1)) != 1:
            raise RuntimeError(f"NATIVE_COMMAND_COUNT_MISMATCH:{row}")
        if row.get("commander") != "Rograkh, Son of Rohgahh":
            raise RuntimeError(f"NATIVE_COMMANDER_MISMATCH:{row}")
    normalized = payload.get("normalized_constructed_state")
    normalized_digest = payload.get("normalized_constructed_state_digest")
    return {
        "fixture_id": FIRST_FIXTURE,
        "record_digest": record["materialization_digest"],
        "requested_state_digest": record["requested_state_digest"],
        "native_runtime_reached": True,
        "narrow_native_snapshot_validation": "PASS",
        "native_snapshot": snap,
        "decision_trace": decisions,
        "provider_emitted_normalized_constructed_state": isinstance(normalized, dict),
        "provider_emitted_normalized_constructed_state_digest": normalized_digest,
        "provider_message_keys": sorted(payload),
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
    if materialization.get("schema_version") != CONTRACT_VERSION:
        raise SystemExit("WS32_CONTRACT_VERSION_MISMATCH")
    if materialization.get("canonical_bundle_digest") != CONTRACT_BUNDLE:
        raise SystemExit("WS32_BUNDLE_DIGEST_MISMATCH")
    if spec.get("spec_version") != "commander-lab.requested-state-digest/1.0.0":
        raise SystemExit("REQUESTED_STATE_DIGEST_SPEC_MISMATCH")

    records = materialization["records"]
    by_id = {r["fixture_id"]: r for r in records}
    if len(by_id) != 135:
        raise SystemExit("WS32_RECORD_DENOMINATOR_MISMATCH")
    owned = sorted(fid for fid in by_id if not fid.startswith("CARD_"))
    owned.append("CARD_02")
    owned = sorted(owned)
    if len(owned) != 107:
        raise SystemExit(f"WS33_OWNED_DENOMINATOR_MISMATCH:{len(owned)}")

    first = run_first_record(by_id[FIRST_FIXTURE], shlex.split(args.provider_command))
    missing_projection_keys = list(spec["projection_keys"])
    if first["provider_emitted_normalized_constructed_state"]:
        raise SystemExit(
            "CURRENT_PROVIDER_UNEXPECTEDLY_EMITS_NORMALIZED_STATE:"
            "update WS33 preflight instead of silently granting credit"
        )

    first.update({
        "status": "CANONICAL_SETUP_UNSUPPORTED",
        "behavioral_credit": False,
        "defect_taxonomy": "FORGE_PROVIDER_DEFECT",
        "failure_signature": "WS32_V1_0_2_NORMALIZED_CONSTRUCTED_STATE_NOT_EMITTED",
        "missing_required_projection_keys": missing_projection_keys,
        "credit_gate": spec["provider_credit_gate"],
    })

    ledger = []
    for fid in owned:
        r = by_id[fid]
        if fid == FIRST_FIXTURE:
            status = "CANONICAL_SETUP_UNSUPPORTED"
            attempted = True
            defect = "FORGE_PROVIDER_DEFECT"
            reason = first["failure_signature"]
        else:
            status = "NOT_RUN_AFTER_STOP_CONDITION"
            attempted = False
            defect = None
            reason = f"STOP_AFTER_{FIRST_FIXTURE}_CONSTRUCTION_GATE"
        ledger.append({
            "fixture_id": fid,
            "fixture_family": r["fixture_family"],
            "materialization_digest": r["materialization_digest"],
            "requested_state_digest": r["requested_state_digest"],
            "execution_entry_mode": r["execution_entry_mode"],
            "attempted": attempted,
            "status": status,
            "behavioral_credit": False,
            "defect_taxonomy": defect,
            "reason": reason,
        })

    family_counts: dict[str, int] = {}
    for row in ledger:
        family_counts[row["fixture_family"]] = family_counts.get(row["fixture_family"], 0) + 1

    out = {
        "schema_version": "commander-lab.ws33-forge-successor-preflight/1.0.0",
        "status": "STOPPED_FAIL_CLOSED",
        "stop_condition": "CANONICAL_STATE_DIGEST_GATE_NOT_SATISFIABLE_BY_CURRENT_PROVIDER_OUTPUT",
        "contract": {
            "version": CONTRACT_VERSION,
            "commit": CONTRACT_COMMIT,
            "tree": CONTRACT_TREE,
            "bundle_digest": CONTRACT_BUNDLE,
            "record_count": 135,
            "ws33_owned_denominator": 107,
            "owned_family_counts": family_counts,
        },
        "forge": {
            "commit": FORGE_COMMIT,
            "tree": FORGE_TREE,
            "version": FORGE_VERSION,
            "process_boundary": "SEPARATE_GPL_JVM",
        },
        "first_record_result": first,
        "counts": {
            "CANONICAL_SETUP_UNSUPPORTED": 1,
            "NOT_RUN_AFTER_STOP_CONDITION": 106,
            "PASS": 0,
            "FAIL": 0,
        },
        "ledger": ledger,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "WS33_SUCCESSOR_PREFLIGHT.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "WS33_SUCCESSOR_RESULT_LEDGER.json").write_text(
        json.dumps({
            "schema_version": "commander-lab.ws33-result-ledger/1.0.0",
            "denominator": 107,
            "counts": out["counts"],
            "rows": ledger,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": out["status"],
        "denominator": 107,
        "first_fixture": FIRST_FIXTURE,
        "first_status": first["status"],
        "defect_taxonomy": first["defect_taxonomy"],
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
