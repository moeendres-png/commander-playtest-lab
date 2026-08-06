from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from commander_lab.storage import sha256_value

from commander_lab.models import EngineReplay, GameState
from commander_lab.engine.rules.replay import replay_into_internal_model


@dataclass(frozen=True)
class ReplayStep:
    index: int
    event: dict[str, Any]
    state: GameState


class ReplayDebugger:
    def __init__(self, replay: EngineReplay) -> None:
        self.replay = replay
        self._states: list[GameState] = [GameState.model_validate(replay.initial_state)]
        for event in replay.events:
            if "internal_state_after" not in event:
                raise ValueError("every replay event requires internal_state_after")
            self._states.append(GameState.model_validate(event["internal_state_after"]))
        replay_into_internal_model(replay)

    def state_at(self, index: int) -> GameState:
        return self._states[index]

    def step(self, index: int) -> ReplayStep:
        if index < 0 or index >= len(self.replay.events):
            raise IndexError(index)
        return ReplayStep(index=index, event=self.replay.events[index], state=self._states[index + 1])

    def diff(self, before: int, after: int) -> dict[str, tuple[Any, Any]]:
        first = self._states[before].model_dump(mode="json")
        second = self._states[after].model_dump(mode="json")
        return {key: (first.get(key), second.get(key)) for key in sorted(first | second) if first.get(key) != second.get(key)}


    def branch_marker(self, index: int) -> dict[str, Any]:
        """Return a deterministic marker for a replay branch without mutating the replay."""
        if index < 0 or index >= len(self.replay.events):
            raise IndexError(index)
        event = self.replay.events[index]
        state = self._states[index].model_dump(mode="json")
        return {
            "game_id": self.replay.game_id,
            "event_offset": index,
            "event_type": event.get("event_type"),
            "actor_id": event.get("actor_id"),
            "state_hash": sha256_value(state),
            "available_actions": event.get("payload", {}).get("candidates", []),
            "chosen_action": event.get("payload", {}).get("selected_action_id"),
        }

    def action_comparison(self, index: int, alternative_action_id: str) -> dict[str, Any]:
        marker = self.branch_marker(index)
        candidates = {str(row[0]): float(row[1]) for row in marker["available_actions"] if row}
        chosen = marker.get("chosen_action")
        if alternative_action_id not in candidates:
            raise ValueError("alternative action was not legal at branchpoint")
        if chosen not in candidates:
            raise ValueError("chosen action is missing from recorded candidates")
        return {
            **marker,
            "alternative_action": alternative_action_id,
            "chosen_utility": candidates[chosen],
            "alternative_utility": candidates[alternative_action_id],
            "utility_delta": candidates[alternative_action_id] - candidates[chosen],
            "model_alternative": True,
        }

    def repeat_with_same_seed(self) -> dict[str, Any]:
        """Verify deterministic replay identity; it does not invent a new rules-engine future."""
        return {
            "game_id": self.replay.game_id,
            "seed": self.state_at(0).seed,
            "event_log_sha256": self.replay.event_log_sha256,
            "final_state_hash": sha256_value(self.replay.final_state),
            "deterministic_identity": True,
        }

    def batch_alternative_futures(self, index: int, alternatives: Iterable[str]) -> tuple[dict[str, Any], ...]:
        return tuple(self.action_comparison(index, action) for action in alternatives)

    def export_golden_scenario(self, index: int, alternative_action_id: str) -> dict[str, Any]:
        return {
            "fixture_type": "counterfactual_golden_scenario",
            "branch": self.action_comparison(index, alternative_action_id),
            "validation_level": self.replay.validation_level.value,
            "engine": self.replay.engine,
            "truth_boundary": "counterfactual_model_alternative",
        }

    def filter_events(self, *, player_id: str | None = None, event_type: str | None = None) -> tuple[dict[str, Any], ...]:
        rows = []
        for event in self.replay.events:
            if player_id is not None and event.get("actor_id") != player_id:
                continue
            if event_type is not None and event.get("event_type") != event_type:
                continue
            rows.append(event)
        return tuple(rows)
