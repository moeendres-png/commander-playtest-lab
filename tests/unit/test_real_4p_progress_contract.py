"""B8 (#489): the Real4P smoke must show deterministic meaningful progress."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from commander_lab.engine.rules.full_game import smoke_progress_contract

ROOT = Path(__file__).resolve().parents[2]


def _trace(
    turns: int = 4, seats: tuple[int, ...] = (0, 1, 2, 3), active=lambda turn: (turn - 1) % 4
) -> tuple:
    trace = [("mulligan", seat, 1, None, "ab" * 32, active(1)) for seat in seats]
    for turn in range(1, turns + 1):
        trace += [
            ("priority", seat, turn, "precombat_main", "ab" * 32, active(turn)) for seat in seats
        ]
    return tuple(trace)


def test_full_seat_cycle_meets_the_contract() -> None:
    contract = smoke_progress_contract(_trace(), player_count=4, through_turn=4)
    assert contract["met"] is True
    assert contract["priority_turns"] == [1, 2, 3, 4]
    assert contract["priority_seats"] == [0, 1, 2, 3]
    assert contract["active_seats_by_turn"] == {"1": [0], "2": [1], "3": [2], "4": [3]}


@pytest.mark.parametrize(
    ("trace", "violation"),
    [
        # The observed trivial start: mulligans and opening passes, turn 1 only.
        (_trace(turns=1), "did not reach turn 4"),
        # Only mulligans: priority never answered.
        (tuple(("mulligan", seat, 1, None, "ab" * 32, 0) for seat in range(4)), "priority missing"),
        # One seat never had priority.
        (_trace(seats=(0, 1, 2)), "not every seat"),
        # A decision without a seat cannot be attributed.
        ((*_trace(), ("priority", None, 2, "end", "ab" * 32, 1)), "no seat"),
        # Codex P1: every seat has priority in turn 1, but one player takes turns 2-4.
        (_trace(active=lambda turn: 0 if turn == 1 else 1), "not taken by every seat"),
        # A turn whose decisions disagree on the active player.
        ((*_trace(), ("priority", 0, 2, "end", "ab" * 32, 3)), "more than one active seat"),
        # A priority decision whose active player cannot be resolved.
        ((*_trace(), ("priority", 0, 3, "end", "ab" * 32, None)), "no valid active seat"),
        # A pre-game choice may lack an active seat, but never contradict it.
        ((*_trace(), ("target", 0, 1, None, "ab" * 32, 2)), "more than one active seat"),
    ],
)
def test_trivial_or_unattributed_progress_fails(trace, violation) -> None:
    contract = smoke_progress_contract(trace, player_count=4, through_turn=4)
    assert contract["met"] is False
    assert any(violation in item for item in contract["violations"])


def test_the_workflow_requires_the_contract_and_the_twin() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/xmage-real-4p-smoke.yml").read_text())
    steps = [
        step for job in workflow["jobs"].values() for step in job.get("steps", ()) if "run" in step
    ]
    run = next(s["run"] for s in steps if s.get("name") == "Run bounded real 4P technical smoke")
    assert "--progress-turns 4" in run
    verify = next(s["run"] for s in steps if s.get("name") == "Verify evidence boundary")
    for clause in (
        'contract["met"] is True',
        'report["twin_progress_digest_match"] is True',
        'contract["priority_seats"] == [0, 1, 2, 3]',
        'actives = contract["active_seats_by_turn"]',
    ):
        assert clause in verify, clause


@pytest.mark.parametrize("seat", [-1, 4, True, 1.5])
def test_invalid_seat_is_not_progress(seat) -> None:
    contract = smoke_progress_contract(
        (*_trace(), ("priority", seat, 4, "end", "ab" * 32, 3)), player_count=4, through_turn=4
    )
    assert contract["met"] is False
    assert "a decision carried an invalid seat" in contract["violations"]


def test_pre_game_choices_without_an_active_player_are_progress() -> None:
    """Live XMage: mulligans and commander placement precede the first active turn."""
    pre_game = tuple(("mulligan", seat, 1, None, "ab" * 32, None) for seat in range(4))
    contract = smoke_progress_contract((*pre_game, *_trace()), player_count=4, through_turn=4)
    assert contract["met"] is True, contract["violations"]
