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
EXPECTED_STOP = "WS23_GATE_D_POST_COMBAT_MAIN2"


def digest(option_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(option_ids).encode()).hexdigest()


def send(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def action_matches(options: list[dict[str, Any]], card_ref: str) -> list[dict[str, Any]]:
    prefix = f"action:{card_ref.split(':', 1)[1]}:"
    return [o for o in options if o.get("public_ref", "").startswith(prefix)]


def choose_option(
    frame: dict[str, Any],
    scenario: dict[str, str],
    state: dict[str, Any],
) -> str:
    payload = frame["payload"]
    kind = payload["decision_kind"]
    options = payload["options"]
    ids = [x["option_id"] for x in options]
    if payload["options_digest"] != digest(ids):
        raise AssertionError(f"options digest mismatch: {payload}")

    if kind == "chooseStartingPlayer":
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
            matches = action_matches(options, scenario["bolt_ref"])
            if len(matches) == 1:
                state["bolt_cast"] = True
                return matches[0]["option_id"]
        if scenario and state["bolt_cast"] and not state["commander_cast"]:
            matches = action_matches(options, scenario["commander_ref"])
            if len(matches) == 1:
                state["commander_cast"] = True
                return matches[0]["option_id"]
        if (
            scenario
            and state["commander_cast"]
            and state["trigger_resolved"]
            and not state["fog_cast"]
        ):
            matches = action_matches(options, scenario["fog_ref"])
            if len(matches) == 1:
                state["fog_cast"] = True
                return matches[0]["option_id"]
        passes = [o for o in options if o.get("public_ref") == "pass" or o.get("kind") == "PASS"]
        if len(passes) != 1:
            raise AssertionError(f"priority must contain exactly one explicit PASS: {options}")
        return passes[0]["option_id"]
    if kind == "getAbilityToPlay":
        raise AssertionError(
            "bounded Gate-D cards unexpectedly required an unresolved multi-ability choice: "
            f"{options}"
        )
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
        state["mana_payments"] += 1
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


def replay_choice(frame: dict[str, Any], expected: dict[str, Any]) -> str:
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
                f"DecisionTape replay drift for {key}: "
                f"expected={expected.get(key)!r} actual={value!r}"
            )
    selected = expected.get("selected_option_id")
    if selected not in ids:
        raise AssertionError(f"recorded option not offered during replay: {selected} / {ids}")
    return str(selected)


def observe_replayed_choice(
    frame: dict[str, Any],
    scenario: dict[str, str],
    state: dict[str, Any],
    selected: str,
) -> None:
    payload = frame["payload"]
    kind = payload["decision_kind"]
    matches = [option for option in payload["options"] if option.get("option_id") == selected]
    if len(matches) != 1:
        raise AssertionError(f"replayed option must resolve exactly once: {selected}")
    chosen = matches[0]
    public_ref = chosen.get("public_ref")

    if kind == "priority":
        for state_key, scenario_key in (
            ("bolt_cast", "bolt_ref"),
            ("commander_cast", "commander_ref"),
            ("fog_cast", "fog_ref"),
        ):
            prefix = f"action:{scenario[scenario_key].split(':', 1)[1]}:"
            if isinstance(public_ref, str) and public_ref.startswith(prefix):
                state[state_key] = True
                return
        if public_ref == "pass" or chosen.get("kind") == "PASS":
            return
        raise AssertionError(f"unexpected replayed priority semantic: {chosen}")
    if kind == "target":
        if public_ref != scenario["target_player_ref"]:
            raise AssertionError(f"replayed target semantic drift: {chosen}")
        state["target"] = True
    elif kind == "mana_payment":
        if chosen.get("kind") != "NATIVE_MANA":
            raise AssertionError(f"replayed mana semantic drift: {chosen}")
        state["mana_payments"] += 1
    elif kind == "declareAttackers":
        wanted = f"attack:{scenario['attacker_ref']}->{scenario['target_player_ref']}"
        if public_ref != wanted:
            raise AssertionError(f"replayed attack semantic drift: {chosen}")
        state["attack"] = True
    elif kind == "declareBlockers":
        wanted = f"block:{scenario['blocker_ref']}->{scenario['attacker_ref']}"
        if public_ref != wanted:
            raise AssertionError(f"replayed block semantic drift: {chosen}")
        state["block"] = True
    elif kind == "chooseSingleReplacementEffect":
        state["replacement_selection"] = True
    elif kind == "confirmReplacementEffect":
        if chosen.get("kind") != "APPLY":
            raise AssertionError(f"replayed replacement semantic drift: {chosen}")
        state["replacement"] = True
    elif kind == "orderSimultaneousSa":
        if public_ref != "order:0,1":
            raise AssertionError(f"replayed trigger-order semantic drift: {chosen}")
        state["trigger_order"] = True
    elif kind in {
        "chooseStartingPlayer",
        "mulliganKeepHand",
        "confirmAction",
        "chooseBinary",
        "confirmPayment",
    }:
        return
    else:
        raise AssertionError(f"unexpected replayed decision semantic: {kind}")


def proof_keys_match(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
    keys: tuple[str, ...],
) -> bool:
    return (
        previous is not None
        and current is not None
        and all(previous.get(key) == current.get(key) for key in keys)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--replay-proof", type=Path)
    args = ap.parse_args()
    command = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not command:
        raise SystemExit("COMMANDER_LAB_FORGE_PROVIDER_CMD is required")

    previous: dict[str, Any] | None = None
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
                "qualification": "ws23-v2-bounded-gate-d",
            },
        },
    )

    transcript: list[dict[str, Any]] = []
    decision_tape: list[dict[str, Any]] = []
    scenario: dict[str, str] = {}
    observation: dict[str, Any] | None = None
    stack_observation: dict[str, Any] | None = None
    commander_proof: dict[str, Any] | None = None
    trigger_proof: dict[str, Any] | None = None
    prevention_proof: dict[str, Any] | None = None
    rng_proof: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    replay_index = 0
    state: dict[str, Any] = {
        "bolt_cast": False,
        "commander_cast": False,
        "fog_cast": False,
        "target": False,
        "mana_payments": 0,
        "attack": False,
        "block": False,
        "replacement_selection": False,
        "replacement": False,
        "trigger_order": False,
        "trigger_resolved": False,
        "stack": False,
        "commander": False,
        "prevention": False,
        "rng": False,
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
            state["commander"] = commander_proof.get("actual_card_behavior_verified") is True
        elif mtype == "TRIGGER_PROOF":
            trigger_proof = msg["payload"]
            state["trigger_resolved"] = (
                trigger_proof.get("native_trigger_resolution_verified") is True
                and trigger_proof.get("life_gain_after_resolution") == 2
            )
        elif mtype == "PREVENTION_PROOF":
            prevention_proof = msg["payload"]
            state["prevention"] = prevention_proof.get("native_prevention_verified") is True
        elif mtype == "RNG_PROOF":
            rng_proof = msg["payload"]
            state["rng"] = (
                rng_proof.get("common_fixture_id") == "RNG_RULES_TAPE"
                and rng_proof.get("engine_path") == "FlipCoinEffect/MyRandom"
                and rng_proof.get("seed") == 230023
                and rng_proof.get("flip_count") == 16
                and len(rng_proof.get("sequence", "")) == 16
            )
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
                observe_replayed_choice(msg, scenario, state, chosen)
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
    previous_rng = None if previous is None else previous.get("rng_proof")
    previous_snapshot = (
        None
        if previous is None
        else ((previous.get("result") or {}).get("payload", {}).get("snapshot"))
    )
    current_snapshot = None if result is None else result.get("payload", {}).get("snapshot")
    rng_replay_match = (
        None
        if previous is None
        else proof_keys_match(
            previous_rng,
            rng_proof,
            ("common_fixture_id", "engine_path", "seed", "flip_count", "sequence"),
        )
    )
    snapshot_replay_match = None if previous is None else previous_snapshot == current_snapshot

    evidence = {
        "schema_version": "ws23-v2-runtime-proof/1.3.0",
        "transcript": transcript,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "scenario": scenario,
        "observation": observation,
        "stack_observation": stack_observation,
        "commander_proof": commander_proof,
        "trigger_proof": trigger_proof,
        "prevention_proof": prevention_proof,
        "rng_proof": rng_proof,
        "decision_coverage": state,
        "decision_tape": decision_tape,
        "replay_mode": replay_tape is not None,
        "replay_tape_consumed": replay_index if replay_tape is not None else None,
        "rng_replay_match": rng_replay_match,
        "snapshot_replay_match": snapshot_replay_match,
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
        or commander_proof.get("cast_from_command_runtime_verified") is not True
        or commander_proof.get("commander_cast_count") != 1
        or commander_proof.get("actual_card_behavior_verified") is not True
    ):
        return 5
    if (
        trigger_proof is None
        or trigger_proof.get("ordered_trigger_count") != 2
        or trigger_proof.get("life_gain_after_resolution") != 2
        or trigger_proof.get("native_trigger_resolution_verified") is not True
    ):
        return 6
    if (
        prevention_proof is None
        or prevention_proof.get("native_prevention_verified") is not True
        or prevention_proof.get("fog_resolved_to_graveyard") is not True
        or prevention_proof.get("attacker_damage") != 0
        or prevention_proof.get("blocker_damage") != 0
    ):
        return 7
    if not state["rng"]:
        return 8
    required = (
        "bolt_cast",
        "commander_cast",
        "fog_cast",
        "target",
        "attack",
        "block",
        "replacement_selection",
        "replacement",
        "trigger_order",
        "trigger_resolved",
        "stack",
        "commander",
        "prevention",
        "rng",
    )
    if not all(state[key] for key in required) or state["mana_payments"] < 2:
        return 9
    stop_reason = result["payload"].get("stop_reason", "")
    if stop_reason != EXPECTED_STOP:
        return 10
    if result["payload"].get("snapshot", {}).get("phase") != "MAIN2":
        return 11
    if previous is not None and (rng_replay_match is not True or snapshot_replay_match is not True):
        return 12

    print(
        json.dumps(
            {
                "verdict": "PASS",
                "stop_reason": stop_reason,
                "decision_coverage": state,
                "observation_proof": True,
                "decision_tape_entries": len(decision_tape),
                "replay_mode": replay_tape is not None,
                "rng_replay_match": rng_replay_match,
                "snapshot_replay_match": snapshot_replay_match,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
