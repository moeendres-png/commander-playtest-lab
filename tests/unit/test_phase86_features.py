from __future__ import annotations

import hashlib
import json
from pathlib import Path

from commander_lab.features import ReplayDebugger, ScenarioFixture, save_scenario_fixture
from commander_lab.models import (
    EngineReplay,
    GameState,
    GameStatus,
    PlayerState,
    RuntimeValidationLevel,
)


def _state(life: int) -> dict[str, object]:
    return GameState(
        game_id="g",
        seed=7,
        status=GameStatus.IN_PROGRESS,
        turn_number=1,
        active_player_id="p1",
        priority_player_id="p1",
        players=(PlayerState(player_id="p1", seat=0, life=life),),
        event_sequence=1,
    ).model_dump(mode="json")


def test_scenario_fixture_is_hashed_and_roundtrips(tmp_path: Path) -> None:
    fixture = ScenarioFixture(
        scenario_id="s1",
        description="fixed state",
        seed=7,
        initial_state=GameState.model_validate(_state(40)),
    )
    target = tmp_path / "scenario.json"
    save_scenario_fixture(str(target), fixture)
    loaded = ScenarioFixture.model_validate_json(target.read_text(encoding="utf-8"))
    assert loaded == fixture
    assert loaded.fixture_hash


def test_replay_debugger_steps_and_diffs() -> None:
    event = {
        "sequence": 0,
        "event_type": "damage",
        "actor_id": "p1",
        "internal_state_after": _state(37),
    }
    digest = hashlib.sha256(
        json.dumps([event], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    replay = EngineReplay(
        engine="tactical",
        engine_version="test",
        validation_level=RuntimeValidationLevel.TACTICAL_ORACLE,
        game_id="g",
        initial_state=_state(40),
        events=(event,),
        final_state=_state(37),
        event_log_sha256=digest,
    )
    debugger = ReplayDebugger(replay)
    assert debugger.step(0).state.players[0].life == 37
    assert "players" in debugger.diff(0, 1)
    assert len(debugger.filter_events(event_type="damage")) == 1
