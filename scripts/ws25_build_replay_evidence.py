#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DYNAMIC_REF = re.compile(r"(?:(?:card|action|ability|entity):)\\d+")
EVENT_TYPES = {
    "OBSERVATION_PROOF",
    "STACK_OBSERVATION_PROOF",
    "COMMANDER_PROOF",
    "TRIGGER_PROOF",
    "PREVENTION_PROOF",
    "RNG_PROOF",
    "SESSION_RESULT",
}
DROP_KEYS = {"request_id", "session_id", "state_revision", "decision_id", "object_id"}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in sorted(value.items()) if k not in DROP_KEYS}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, str):
        return DYNAMIC_REF.sub(lambda m: m.group(0).split(":", 1)[0] + ":#", value)
    return value


def event_tape(proof: dict[str, Any]) -> list[dict[str, Any]]:
    tape = []
    for message in proof.get("transcript", []):
        if message.get("message_type") not in EVENT_TYPES:
            continue
        tape.append(
            {
                "message_type": message.get("message_type"),
                "actor_id": message.get("actor_id"),
                "payload": normalize(message.get("payload", {})),
            }
        )
    return tape


def semantic_decision_tape(proof: dict[str, Any]) -> list[dict[str, Any]]:
    frames = {
        item.get("payload", {}).get("decision_id"): item
        for item in proof.get("transcript", [])
        if item.get("message_type") == "DECISION_FRAME"
    }
    out = []
    for entry in proof.get("decision_tape", []):
        frame = frames.get(entry.get("decision_id"), {})
        options = frame.get("payload", {}).get("options", [])
        selected = next(
            (x for x in options if x.get("option_id") == entry.get("selected_option_id")),
            None,
        )
        out.append(
            {
                "actor_id": entry.get("actor_id"),
                "decision_kind": entry.get("decision_kind"),
                "options_digest": entry.get("options_digest"),
                "offered_option_ids": entry.get("offered_option_ids"),
                "selected_option_id": entry.get("selected_option_id"),
                "selected_semantic": normalize(selected),
            }
        )
    return out


def state_checkpoints(proof: dict[str, Any]) -> dict[str, Any]:
    observation = normalize(proof.get("observation"))
    result = normalize((proof.get("result") or {}).get("payload", {}).get("snapshot"))
    return {
        "actor_observation": observation,
        "terminal_snapshot": result,
        "decision_coverage": normalize(proof.get("decision_coverage", {})),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-proof", type=Path, required=True)
    ap.add_argument("--replay-proof", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    first = load(args.runtime_proof)
    replay = load(args.replay_proof)
    first_events = event_tape(first)
    replay_events = event_tape(replay)
    first_decisions = semantic_decision_tape(first)
    replay_decisions = semantic_decision_tape(replay)
    first_states = state_checkpoints(first)
    replay_states = state_checkpoints(replay)

    event_match = first_events == replay_events and len(first_events) > 0
    decision_match = first_decisions == replay_decisions and len(first_decisions) > 0
    state_match = first_states == replay_states
    rng_match = replay.get("rng_replay_match") is True
    clean_process = replay.get("replay_mode") is True and replay.get("exit_code") == 0

    fixture_results = {
        "RNG_RULES_TAPE": rng_match,
        "REPLAY_DECISION_TAPE": decision_match,
        "REPLAY_EVENT_TAPE": event_match,
        "REPLAY_CLEAN_PROCESS": clean_process and event_match and decision_match and state_match,
        "REPLAY_STATE_HASHES": state_match,
    }
    output = {
        "schema_version": "ws25-replay-evidence/1.0.0",
        "provider_identity": {
            "provider": "forge",
            "forge_commit": "1e604105f9e279331063824943b9222b6589f5d8",
            "forge_tree": "994976e06aaf99b807646b60b1aa2ac9f7703df4",
            "forge_version": "2.0.15-SNAPSHOT",
        },
        "rules_rng_source": "FlipCoinEffect/MyRandom",
        "fixture_results": fixture_results,
        "event_tape": first_events,
        "event_tape_sha256": canonical_hash(first_events),
        "replay_event_tape_sha256": canonical_hash(replay_events),
        "decision_tape_semantic_sha256": canonical_hash(first_decisions),
        "replay_decision_tape_semantic_sha256": canonical_hash(replay_decisions),
        "state_checkpoints": first_states,
        "state_checkpoint_hashes": {k: canonical_hash(v) for k, v in first_states.items()},
        "replay_state_checkpoint_hashes": {k: canonical_hash(v) for k, v in replay_states.items()},
        "process_local_identity_excluded": True,
        "all_five_pass": all(fixture_results.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"fixture_results": fixture_results, "all_five_pass": output["all_five_pass"]}, sort_keys=True))
    return 0 if output["all_five_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
