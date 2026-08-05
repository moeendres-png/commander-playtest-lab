from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

    def filter_events(self, *, player_id: str | None = None, event_type: str | None = None) -> tuple[dict[str, Any], ...]:
        rows = []
        for event in self.replay.events:
            if player_id is not None and event.get("actor_id") != player_id:
                continue
            if event_type is not None and event.get("event_type") != event_type:
                continue
            rows.append(event)
        return tuple(rows)
