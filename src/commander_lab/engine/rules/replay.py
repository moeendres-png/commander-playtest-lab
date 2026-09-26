from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from commander_lab.models import EngineReplay, GameState


class ReplayValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplayValidationResult:
    passed: bool
    events_applied: int
    final_state_hash: str
    mismatches: tuple[str, ...] = ()


def canonical_state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def replay_into_internal_model(replay: EngineReplay) -> ReplayValidationResult:
    """Strictly replay state snapshots and reject unknown event shapes.

    External bridges may emit rich engine-specific events, but each externally
    supplied event must include an `internal_state_after` snapshot until a typed
    reducer exists. This prevents silent event loss.
    """
    state = dict(replay.initial_state)
    applied = 0
    sequence_seen: list[int] = []
    for index, event in enumerate(replay.events):
        if not isinstance(event, dict):
            raise ReplayValidationError(f"event {index} is not an object")
        sequence = event.get("sequence")
        if sequence is None:
            raise ReplayValidationError(f"event {index} has no sequence")
        sequence_seen.append(int(sequence))
        if "internal_state_after" not in event:
            raise ReplayValidationError(
                f"event {index} ({event.get('event_type')}) has no internal_state_after snapshot"
            )
        state = dict(event["internal_state_after"])
        # Validate every snapshot through the authoritative internal schema.
        GameState.model_validate(state)
        applied += 1
    if sequence_seen != sorted(sequence_seen) or len(sequence_seen) != len(set(sequence_seen)):
        raise ReplayValidationError("event sequence is not strictly ordered and unique")
    expected = GameState.model_validate(replay.final_state).model_dump(mode="json")
    observed = GameState.model_validate(state).model_dump(mode="json")
    mismatches: list[str] = []
    for key in (
        "players",
        "stack",
        "turn_number",
        "active_player_id",
        "priority_player_id",
        "phase",
        "step",
        "event_sequence",
    ):
        if observed.get(key) != expected.get(key):
            mismatches.append(key)
    return ReplayValidationResult(
        passed=not mismatches,
        events_applied=applied,
        final_state_hash=canonical_state_hash(observed),
        mismatches=tuple(mismatches),
    )


__all__ = [
    "ReplayValidationError",
    "ReplayValidationResult",
    "canonical_state_hash",
    "replay_into_internal_model",
]
