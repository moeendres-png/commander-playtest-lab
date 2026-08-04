from __future__ import annotations

from commander_lab.engine import IllegalActionProposal, validate_action_proposal
from commander_lab.engine.structural import StructuralSimulator
from commander_lab.evals import load_jsonl, validate_event_log
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


def test_cards_zones_elimination_and_logs_remain_consistent_across_seeds(
    tmp_path, structural_decks
) -> None:
    simulator = StructuralSimulator(structural_decks)
    pods = (
        ("korvold/current",),
        ("korvold/current", "synthetic/aggro", "synthetic/control"),
        (
            "korvold/current",
            "rogshai/current",
            "synthetic/aggro",
            "synthetic/control",
        ),
        (
            "korvold/current",
            "rogshai/current",
            "synthetic/aggro",
            "synthetic/control",
            "synthetic/engine",
        ),
    )
    for pod_index, deck_ids in enumerate(pods):
        for seed in range(16):
            path = tmp_path / f"pod-{pod_index}-seed-{seed}.jsonl"
            result = simulator.simulate(
                StructuralMatchConfig(
                    match_id=f"property-{pod_index}-{seed}",
                    seed=pod_index * 1000 + seed,
                    deck_ids=deck_ids,
                    limits=StructuralAbortLimits(
                        max_turns=40,
                        max_events=60_000,
                        max_no_progress_turns=22,
                    ),
                ),
                event_log_path=path,
            )
            assert not result.aborted
            assert validate_event_log(load_jsonl(path)) == ()


def test_identical_seed_produces_identical_result_and_log(tmp_path, structural_decks) -> None:
    simulator = StructuralSimulator(structural_decks)
    config = StructuralMatchConfig(
        match_id="same-seed",
        seed=123456,
        deck_ids=("korvold/current", "rogshai/current", "synthetic/engine"),
    )
    first_path = tmp_path / "a.jsonl"
    second_path = tmp_path / "b.jsonl"
    first = simulator.simulate(config, event_log_path=first_path)
    second = simulator.simulate(config, event_log_path=second_path)
    first_payload = first.model_dump(mode="json", exclude={"event_log_path"})
    second_payload = second.model_dump(mode="json", exclude={"event_log_path"})
    assert first_payload == second_payload
    assert first_path.read_bytes() == second_path.read_bytes()


def test_illegal_actions_are_rejected_for_many_invalid_targets() -> None:
    legal = LegalAction(
        action_id="choose",
        actor_id="p1",
        action_type=ActionType.CHOOSE_TARGETS,
        allowed_target_ids=("p2", "p3"),
    )
    state = GameState(
        game_id="property-actions",
        seed=9,
        status=GameStatus.IN_PROGRESS,
        priority_player_id="p1",
        players=(
            PlayerState(player_id="p1", seat=0),
            PlayerState(player_id="p2", seat=1),
            PlayerState(player_id="p3", seat=2),
        ),
        legal_actions=(legal,),
    )
    for invalid_target in ("p1", "p4", "unknown", "card-99"):
        proposal = ActionProposal(
            proposal_id=f"bad-{invalid_target}",
            actor_id="p1",
            legal_action_id="choose",
            action_type=ActionType.CHOOSE_TARGETS,
            target_ids=(invalid_target,),
        )
        try:
            validate_action_proposal(state, proposal)
        except IllegalActionProposal:
            pass
        else:
            raise AssertionError(f"illegal target was accepted: {invalid_target}")
