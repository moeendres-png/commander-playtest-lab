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
        # Gate-A startup has already proven this callback. The v2 pilot deliberately
        # selects an offered seat; this is not an unsupported fallback path.
        if "o0" not in ids:
            raise AssertionError(f"expected offered startup option o0: {options}")
        return "o0"
    if kind == "mulliganKeepHand":
        keep = [o for o in options if o.get("kind") == "KEEP"]
        if len(keep) != 1:
            raise AssertionError(f"KEEP must be offered exactly once: {options}")
        return keep[0]["option_id"]
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
    if kind == "getAbilityToPlay":
        prefix = f"ability:{scenario['bolt_ref'].split(':', 1)[1]}:"
        matches = [o for o in options if o.get("public_ref", "").startswith(prefix)]
        if len(matches) != 1:
            raise AssertionError(f"expected one public Bolt ability variant: {options}")
        state["ability_choice"] = True
        return matches[0]["option_id"]
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
    if kind == "chooseSingleReplacementEffect":
        if len(options) != 1:
            raise AssertionError(
                f"bounded Commander probe expects exactly one Forge replacement candidate: {options}"
            )
        state["replacement_selection"] = True
        return options[0]["option_id"]
    if kind == "confirmReplacementEffect":
        apply_options = [o for o in options if o.get("kind") == "APPLY"]
        if len(apply_options) != 1:
            raise AssertionError(f"replacement apply option missing: {options}")
        state["replacement"] = True
        return apply_options[0]["option_id"]
    if kind == "orderSimultaneousSa":
        wanted = [o for o in options if o.get("public_ref") == "order:0,1"]
        if len(wanted) != 1:
            raise AssertionError(f"canonical two-trigger ordering not offered: {options}")
        state["trigger_order"] = True
        return wanted[0]["option_id"]
    if kind in {"confirmAction", "chooseBinary", "confirmPayment"}:
        if len(options) != 2:
            raise AssertionError(
                f"bounded binary frame must contain exactly two options: {options}"
            )
        yes_like = [o for o in options if o.get("kind") in {"YES", "TRUE", "PAY"}]
        if len(yes_like) != 1:
            raise AssertionError(f"explicit affirmative option missing: {options}")
        return yes_like[0]["option_id"]

    raise AssertionError(f"unexpected decision kind escaped strict v2 surface: {kind}")


def replay_choice(
    frame: dict[str, Any],
    expected: dict[str, Any],
) -> str:
    payload = frame["payload"]
    ids = [x["option_id"] for x in payload["options"]]
    checks = {
        "actor_id": frame.get("actor_id"),
        "decision_kind": payload.get("decision_kind"),
        "options_digest": payload.get("options_digest"),
        "offered_option_ids": ids,
    }
    for key, value in checks.items():
        if expected.get(key) != value:
            raise AssertionError(
                f"DecisionTape replay drift for {key}: expected={expected.get(key)!r} actual={value!r}"
            )
    selected = expected.get("selected_option_id")
    if selected not in ids:
        raise AssertionError(f"recorded option not offered during replay: {selected} / {ids}")
    return str(selected)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--replay-proof", type=Path)
    args = ap.parse_args()
    command = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not command:
        raise SystemExit("COMMANDER_LAB_FORGE_PROVIDER_CMD is required")

    replay_tape: list[dict[str, Any]] | None = None
    if args.replay_proof is not None:
        previous = json.loads(args.replay_proof.read_text(encoding="utf-8"))
        replay_tape = list(previous.get("decision_tape", []))
        if not replay_tape:
            raise AssertionError("replay proof does not contain a DecisionTape")

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
    decision_tape: list[dict[str, Any]] = []
    scenario: dict[str, str] = {}
    observation: dict[str, Any] | None = None
    stack_observation: dict[str, Any] | None = None
    commander_proof: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    replay_index = 0
    state = {
        "bolt_cast": False,
        "ability_choice": False,
        "target": False,
        "mana": False,
        "attack": False,
        "block": False,
        "replacement_selection": False,
        "replacement": False,
        "trigger_order": False,
        "stack": False,
        "commander": False,
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
        elif mtype == "STACK_OBSERVATION_PROOF":
            stack_observation = msg["payload"]
            state["stack"] = stack_observation.get("public_stack_identity_visible") is True
        elif mtype == "COMMANDER_PROOF":
            commander_proof = msg["payload"]
            state["commander"] = commander_proof.get("native_commander_replacement_applied") is True
        elif mtype == "DECISION_FRAME":
            if not scenario and msg["payload"]["decision_kind"] not in {
                "chooseStartingPlayer",
                "mulliganKeepHand",
            }:
                raise AssertionError("scenario metadata missing before production decision")
            payload = msg["payload"]
            ids = [x["option_id"] for x in payload["options"]]
            if payload["options_digest"] != digest(ids):
                raise AssertionError(f"options digest mismatch: {payload}")
            if replay_tape is None:
                chosen = choose_option(msg, scenario, state)
            else:
                if replay_index >= len(replay_tape):
                    raise AssertionError(
                        "fresh run produced more decisions than recorded DecisionTape"
                    )
                chosen = replay_choice(msg, replay_tape[replay_index])
                replay_index += 1
            decision_tape.append(
                {
                    "actor_id": msg.get("actor_id"),
                    "decision_id": payload["decision_id"],
                    "decision_kind": payload["decision_kind"],
                    "options_digest": payload["options_digest"],
                    "offered_option_ids": ids,
                    "selected_option_id": chosen,
                }
            )
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

    if replay_tape is not None and replay_index != len(replay_tape):
        raise AssertionError(
            f"fresh run consumed {replay_index} of {len(replay_tape)} recorded decisions"
        )

    stderr = proc.stderr.read() if proc.stderr is not None else ""
    evidence = {
        "schema_version": "ws23-v2-runtime-proof/1.1.0",
        "transcript": transcript,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "scenario": scenario,
        "observation": observation,
        "stack_observation": stack_observation,
        "commander_proof": commander_proof,
        "decision_coverage": state,
        "decision_tape": decision_tape,
        "replay_mode": replay_tape is not None,
        "replay_tape_consumed": replay_index if replay_tape is not None else None,
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
    if (
        stack_observation is None
        or stack_observation.get("public_stack_identity_visible") is not True
    ):
        return 4
    if (
        commander_proof is None
        or commander_proof.get("native_commander_replacement_applied") is not True
    ):
        return 5
    if not all(
        state[key]
        for key in (
            "bolt_cast",
            "target",
            "mana",
            "attack",
            "block",
            "replacement",
            "stack",
            "commander",
        )
    ):
        return 6
    stop_reason = result["payload"].get("stop_reason", "")
    if stop_reason != "WS23_CONTROLLED_AFTER_PRIORITY_128":
        return 7

    print(
        json.dumps(
            {
                "verdict": "PASS",
                "stop_reason": stop_reason,
                "decision_coverage": state,
                "observation_proof": True,
                "decision_tape_entries": len(decision_tape),
                "replay_mode": replay_tape is not None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
