#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
PLAYER_COUNTS = (2, 3, 4, 5)


def digest(option_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(option_ids).encode()).hexdigest()


def send(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def choose(frame: dict[str, Any]) -> str:
    payload = frame["payload"]
    kind = payload["decision_kind"]
    options = payload["options"]
    ids = [option["option_id"] for option in options]
    if payload["options_digest"] != digest(ids):
        raise AssertionError(f"options digest mismatch: {payload}")
    if kind == "chooseStartingPlayer":
        if "o0" not in ids:
            raise AssertionError("starting-player choice did not offer o0")
        return "o0"
    if kind == "mulliganKeepHand":
        keep = [option for option in options if option.get("kind") == "KEEP"]
        if len(keep) != 1:
            raise AssertionError(f"KEEP not uniquely offered: {options}")
        return keep[0]["option_id"]
    if kind == "priority":
        passes = [
            option
            for option in options
            if option.get("kind") == "PASS" or option.get("public_ref") == "pass"
        ]
        if len(passes) != 1:
            raise AssertionError(f"priority PASS not uniquely offered: {options}")
        return passes[0]["option_id"]
    if kind == "discardToMaximumHandSize":
        if not options:
            raise AssertionError("cleanup discard offered no Forge-native hand options")
        return min(ids, key=lambda value: int(value[1:]))
    raise AssertionError(f"unexpected broad lifecycle decision: {kind}")


def run_one(command: str, player_count: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = str(player_count)
    proc = subprocess.Popen(
        shlex.split(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    send(
        proc,
        {
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": f"ws23-broad-{player_count}p",
            "session_id": None,
            "actor_id": None,
            "state_revision": None,
            "payload": {
                "player_count": player_count,
                "seat_ids": [f"seat-{i}" for i in range(1, player_count + 1)],
                "qualification": "ws23-broad-player-count-full-lifecycle",
            },
        },
    )
    transcript: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        msg = json.loads(line)
        transcript.append(msg)
        if msg.get("protocol") != PROTOCOL:
            raise AssertionError(f"protocol drift: {msg}")
        if msg.get("message_type") == "DECISION_FRAME":
            chosen = choose(msg)
            payload = msg["payload"]
            send(
                proc,
                {
                    "protocol": PROTOCOL,
                    "message_type": "SUBMIT_DECISION",
                    "request_id": f"submit-{payload['decision_id']}",
                    "session_id": msg["session_id"],
                    "actor_id": msg["actor_id"],
                    "state_revision": msg["state_revision"],
                    "decision_id": payload["decision_id"],
                    "option_id": chosen,
                    "options_digest": payload["options_digest"],
                    "payload": {},
                },
            )
        elif msg.get("message_type") == "SESSION_RESULT":
            result = msg
            break
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        raise AssertionError(f"{player_count}P Forge lifecycle timed out") from exc
    stderr = proc.stderr.read() if proc.stderr is not None else ""
    if result is None:
        raise AssertionError(f"{player_count}P produced no SESSION_RESULT: {stderr}")
    payload = result["payload"]
    snapshot = payload.get("snapshot", {})
    stop_reason = payload.get("stop_reason")
    passed = (
        proc.returncode == 0
        and stop_reason == "FORGE_GAME_RETURNED"
        and snapshot.get("player_count") == player_count
    )
    return {
        "player_count": player_count,
        "fixture_id": f"PLAYER_COUNT_{player_count}P",
        "status": "PASS" if passed else "FAIL",
        "evidence_class": "RUNTIME_VERIFIED",
        "stop_reason": stop_reason,
        "priority_decisions": payload.get("priority_decisions"),
        "snapshot": snapshot,
        "decision_count": sum(item.get("message_type") == "DECISION_FRAME" for item in transcript),
        "exit_code": proc.returncode,
        "stderr": stderr,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    command = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "").strip()
    if not command:
        raise SystemExit("COMMANDER_LAB_FORGE_PROVIDER_CMD is required")

    rows = [run_one(command, count) for count in PLAYER_COUNTS]
    output = {
        "schema_version": "ws23-player-count-matrix/1.0.0",
        "rows": rows,
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "denominator": len(rows),
        "all_pass": all(row["status"] == "PASS" for row in rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass_count": output["pass_count"],
                "denominator": output["denominator"],
                "all_pass": output["all_pass"],
            },
            sort_keys=True,
        )
    )
    return 0 if output["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
