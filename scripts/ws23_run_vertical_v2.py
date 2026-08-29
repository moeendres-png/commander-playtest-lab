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


def digest(option_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(option_ids).encode()).hexdigest()


def send(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def choose_option(
    frame: dict[str, Any],
    scenario: dict[str, str],
    state: dict[str, bool],
) -> str:
    payload = frame["payload"]
    kind = payload["decision_kind"]
    options = payload["options"]
    ids = [x["option_id"] for x in options]
    if payload["options_digest"] != digest(ids):
        raise AssertionError(f"options digest mismatch: {payload}")

    if kind == "chooseStartingPlayer":
        return "o0"
    if kind == "mulliganKeepHand":
        return "o0"
    if kind == "priority":
        if scenario and not state["bolt_cast"]:
            prefix = f"action:{scenario['bolt_ref'].split(':', 1)[1]}:"
            matches = [o for o in options if o.get("public_ref", "").startswith(prefix)]
            if len(matches) == 1:
                state["bolt_cast"] = True
                return matches[0]["option_id"]
        passes = [o for o in options if o.get("public_ref") == "pass" or o.get("kind") == "PASS"]
        if len(passes) != 1:
            raise AssertionError(f"priority must contain exactly one explicit PASS: {options}")
        return passes[0]["option_id"]
    if kind == "target":
        matches = [o for o in options if o.get("public_ref") == scenario["target_player_ref"]]
        if len(matches) != 1:
            raise AssertionError(f"target seat not offered exactly once: {options}")
        state["target"] = True
        return matches[0]["option_id"]
    if kind == "mana_payment":
        if len(options) != 1 or options[0].get("kind") != "NATIVE_MANA":
            raise AssertionError(
                f"bounded mana probe expected one Forge-filtered mana option: {options}"
            )
        state["mana"] = True
        return options[0]["option_id"]
    if kind == "declareAttackers":
        wanted = f"attack:{scenario['attacker_ref']}->{scenario['target_player_ref']}"
        matches = [o for o in options if o.get("public_ref") == wanted]
        if len(matches) != 1:
            raise AssertionError(f"seat-1 attacker -> seat-2 not offered exactly once: {options}")
        state["attack"] = True
        return matches[0]["option_id"]
    if kind == "declareBlockers":
        wanted = f"block:{scenario['blocker_ref']}->{scenario['attacker_ref']}"
        matches = [o for o in options if o.get("public_ref") == wanted]
        if len(matches) != 1:
            raise AssertionError(f"seat-2 blocker assignment not offered exactly once: {options}")
        state["block"] = True
        return matches[0]["option_id"]
    if kind == "confirmReplacementEffect":
        apply_options = [o for o in options if o.get("kind") == "APPLY"]
        if len(apply_options) != 1:
            raise AssertionError(f"replacement apply option missing: {options}")
        state["replacement"] = True
        return apply_options[0]["option_id"]
    if kind in {"confirmAction", "chooseBinary", "confirmPayment"}:
        if len(options) != 2:
            raise AssertionError(
                f"bounded binary frame must contain exactly two options: {options}"
            )
        return options[0]["option_id"]

    raise AssertionError(f"unexpected decision kind escaped strict v2 surface: {kind}")


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
            "request_id": "ws23-v2-create-session",
            "session_id": None,
            "actor_id": None,
            "state_revision": None,
            "payload": {
                "player_count": 4,
                "seat_ids": ["seat-1", "seat-2", "seat-3", "seat-4"],
                "qualification": "ws23-v2-bounded",
            },
        },
    )

    transcript: list[dict[str, Any]] = []
    scenario: dict[str, str] = {}
    observation: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    state = {
        "bolt_cast": False,
        "target": False,
        "mana": False,
        "attack": False,
        "block": False,
        "replacement": False,
    }

    assert proc.stdout is not None
    for line in proc.stdout:
        msg = json.loads(line)
        transcript.append(msg)
        if msg.get("protocol") != PROTOCOL:
            raise AssertionError(f"protocol drift: {msg}")
        mtype = msg.get("message_type")
        if mtype == "SCENARIO_READY":
            scenario = dict(msg["payload"])
        elif mtype == "OBSERVATION_PROOF":
            observation = msg["payload"]
        elif mtype == "DECISION_FRAME":
            if not scenario and msg["payload"]["decision_kind"] not in {
                "chooseStartingPlayer",
                "mulliganKeepHand",
            }:
                raise AssertionError("scenario metadata missing before production decision")
            chosen = choose_option(msg, scenario, state)
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
        elif mtype == "SESSION_RESULT":
            result = msg
            break

    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        raise AssertionError("v2 provider did not terminate after controlled slice stop") from exc

    stderr = proc.stderr.read() if proc.stderr is not None else ""
    evidence = {
        "schema_version": "ws23-v2-runtime-proof/1.0.0",
        "transcript": transcript,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "scenario": scenario,
        "observation": observation,
        "decision_coverage": state,
        "result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if result is None:
        return 2
    if observation is None or not all(
        observation.get(key) is True
        for key in (
            "own_hand_identity_visible",
            "opponent_hand_identity_hidden",
            "opponent_own_hand_identity_visible",
            "public_battlefield_visible",
            "facedown_identity_hidden",
            "library_identity_hidden",
        )
    ):
        return 3
    if not all(state[key] for key in ("bolt_cast", "target", "mana", "attack", "block")):
        return 4
    stop_reason = result["payload"].get("stop_reason", "")
    if stop_reason != "WS23_CONTROLLED_AFTER_PRIORITY_128":
        return 5

    print(
        json.dumps(
            {
                "verdict": "PASS",
                "stop_reason": stop_reason,
                "decision_coverage": state,
                "observation_proof": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
