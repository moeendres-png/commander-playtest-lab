from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.engine import IllegalActionProposal, validate_action_proposal
from commander_lab.engine.structural import (
    AbstractTrigger,
    StructuralSimulator,
    commander_cast_cost,
    commander_damage_is_lethal,
    order_simultaneous_triggers,
    trigger_resolution_order,
)
from commander_lab.evals import event_log_sha256, load_jsonl, validate_event_log
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PlayerState,
    StructuralAbortLimits,
    StructuralMatchConfig,
)


def test_commander_tax_progression() -> None:
    assert [commander_cast_cost(5, casts) for casts in range(4)] == [5, 7, 9, 11]
    with pytest.raises(ValueError):
        commander_cast_cost(5, -1)


def test_commander_damage_is_separate_by_commander() -> None:
    assert not commander_damage_is_lethal({"Ishai": 12, "Rograkh": 10})
    assert commander_damage_is_lethal({"Ishai": 21, "Rograkh": 0})
    assert commander_damage_is_lethal([0, 24])


def test_abstract_trigger_order_uses_apnap_and_deterministic_controller_order() -> None:
    triggers = (
        AbstractTrigger("p2-second", 1, "B Source", controller_order=2),
        AbstractTrigger("p1", 0, "A Source", controller_order=0),
        AbstractTrigger("p3", 2, "C Source", controller_order=0),
        AbstractTrigger("p2-first", 1, "A Source", controller_order=1),
    )
    stack_order = order_simultaneous_triggers(triggers, active_player_seat=0, pod_size=3)
    assert [item.trigger_id for item in stack_order] == [
        "p1",
        "p2-first",
        "p2-second",
        "p3",
    ]
    assert [item.trigger_id for item in trigger_resolution_order(
        triggers, active_player_seat=0, pod_size=3
    )] == ["p3", "p2-second", "p2-first", "p1"]


def test_action_proposal_must_match_one_legal_action() -> None:
    legal = LegalAction(
        action_id="cast-1",
        actor_id="p1",
        action_type=ActionType.CAST_SPELL,
        source_object_id="card-1",
        allowed_target_ids=("p2",),
        modes=("destroy",),
        choices_schema={"required": ["x"], "properties": {"x": {"type": "integer"}}},
    )
    state = GameState(
        game_id="g",
        seed=1,
        status=GameStatus.IN_PROGRESS,
        priority_player_id="p1",
        players=(PlayerState(player_id="p1", seat=0), PlayerState(player_id="p2", seat=1)),
        legal_actions=(legal,),
    )
    proposal = ActionProposal(
        proposal_id="p",
        actor_id="p1",
        legal_action_id="cast-1",
        action_type=ActionType.CAST_SPELL,
        source_object_id="card-1",
        target_ids=("p2",),
        selected_modes=("destroy",),
        choices={"x": 2},
    )
    assert validate_action_proposal(state, proposal) == legal

    with pytest.raises(IllegalActionProposal):
        validate_action_proposal(
            state,
            proposal.model_copy(update={"target_ids": ("p1",)}),
        )
    with pytest.raises(IllegalActionProposal):
        validate_action_proposal(
            state,
            proposal.model_copy(update={"actor_id": "p2"}),
        )


def test_mulligan_and_event_log_invariants(tmp_path: Path, structural_decks) -> None:
    path = tmp_path / "events.jsonl"
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="phase6-events",
            seed=6006,
            deck_ids=("korvold/current", "rogshai/current", "synthetic/aggro"),
            limits=StructuralAbortLimits(
                max_turns=35,
                max_events=50_000,
                max_no_progress_turns=20,
            ),
        ),
        event_log_path=path,
    )
    events = load_jsonl(path)
    mulligans = [event for event in events if event["event_type"] == "london_mulligan"]
    assert len(mulligans) == 3
    assert all(0 <= event["payload"]["kept_hand_size"] <= 7 for event in mulligans)
    assert validate_event_log(events) == ()
    assert event_log_sha256(events) == result.log_sha256
    assert any(event["event_type"] == "state_checkpoint" for event in events)
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[-1])["event_type"] == "game_ended"
