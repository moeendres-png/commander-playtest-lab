#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

PROTOCOL = "commander-lab.rules-service/1.1.0"
ALLOWED_KINDS = {
    "chooseStartingPlayer": "o0",
    "mulliganKeepHand": "o0",  # KEEP, explicitly chosen by the external test pilot
    "priority": "o0",  # PASS, explicitly chosen on every offered priority frame
}


def canonical_digest(option_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(option_ids).encode()).hexdigest()


def send(proc: subprocess.Popen[str], msg: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(msg, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    command = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not command:
        raise SystemExit("COMMANDER_LAB_FORGE_PROVIDER_CMD is required")
    proc = subprocess.Popen(
        shlex.split(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    send(
        proc,
        {
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": "ws23-create-session",
            "session_id": None,
            "actor_id": None,
            "state_revision": None,
            "payload": {"player_count": 4, "seat_ids": ["seat-1", "seat-2", "seat-3", "seat-4"]},
        },
    )
    transcript: list[dict] = []
    result = None
    assert proc.stdout is not None
    for line in proc.stdout:
        msg = json.loads(line)
        transcript.append(msg)
        if msg.get("protocol") != PROTOCOL:
            raise AssertionError(f"protocol drift: {msg}")
        mtype = msg.get("message_type")
        if mtype == "DECISION_FRAME":
            payload = msg["payload"]
            kind = payload["decision_kind"]
            if kind not in ALLOWED_KINDS:
                raise AssertionError(
                    f"unexpected decision kind escaped fail-closed surface: {kind}"
                )
            option_ids = [o["option_id"] for o in payload["options"]]
            if payload["options_digest"] != canonical_digest(option_ids):
                raise AssertionError(f"options digest mismatch: {payload}")
            chosen = ALLOWED_KINDS[kind]
            if chosen not in option_ids:
                raise AssertionError(f"scripted external choice {chosen} not offered for {kind}")
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
        elif mtype == "SESSION_RESULT":
            result = msg
            break
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise AssertionError("provider did not terminate after controlled slice stop") from None
    stderr = proc.stderr.read() if proc.stderr is not None else ""
    evidence = {
        "schema_version": "ws23-real-session-proof/1.0.0",
        "transcript": transcript,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result is None:
        print(json.dumps(evidence, indent=2), file=sys.stderr)
        return 2
    stop_reason = result["payload"].get("stop_reason", "")
    if stop_reason != "WS23_CONTROLLED_AFTER_PRIORITY_16":
        print(json.dumps(evidence, indent=2), file=sys.stderr)
        return 3
    if result["payload"].get("priority_decisions", 0) < 16:
        return 4
    created = next((m for m in transcript if m.get("message_type") == "SESSION_CREATED"), None)
    if created is None or created["payload"]["snapshot"]["player_count"] != 4:
        return 5
    print(
        json.dumps(
            {
                "verdict": "PASS",
                "priority_decisions": result["payload"]["priority_decisions"],
                "stop_reason": stop_reason,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
