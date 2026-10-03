"""B8 (#489): the Real4P smoke must show deterministic meaningful progress."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from commander_lab.engine.rules.full_game import smoke_progress_contract

ROOT = Path(__file__).resolve().parents[2]


DIGEST = "ab" * 32


def _trace(
    turns: int = 4,
    seats: tuple[int, ...] = (0, 1, 2, 3),
    active: tuple[int | None, ...] = (2, 3, 0, 1),
) -> tuple:
    # Mulligans happen before the engine has an active player.
    trace = [("mulligan", seat, 1, None, None, DIGEST) for seat in seats]
    for turn in range(1, turns + 1):
        trace += [
            ("priority", seat, turn, "precombat_main", active[(turn - 1) % len(active)], DIGEST)
            for seat in seats
        ]
    return tuple(trace)


def test_full_seat_cycle_meets_the_contract() -> None:
    contract = smoke_progress_contract(_trace(), player_count=4, through_turn=4)
    assert contract["met"] is True, contract["violations"]
    assert contract["priority_turns"] == [1, 2, 3, 4]
    assert contract["priority_seats"] == [0, 1, 2, 3]
    assert contract["active_seat_by_turn"] == [2, 3, 0, 1]


def test_one_seat_taking_turns_two_to_four_fails() -> None:
    """Wrong-reason control: every seat answers priority, yet one seat is active
    for turns 2-4, so the table never completed a round."""
    trace = _trace(turns=1, active=(0,)) + tuple(
        ("priority", seat, turn, "precombat_main", 1, DIGEST)
        for turn in range(2, 5)
        for seat in range(4)
    )
    contract = smoke_progress_contract(trace, player_count=4, through_turn=4)
    assert contract["priority_seats"] == [0, 1, 2, 3]
    assert contract["priority_turns"] == [1, 2, 3, 4]
    assert contract["active_seat_by_turn"] == [0, 1, 1, 1]
    assert contract["met"] is False
    assert contract["violations"] == [
        "the first full round was not taken by every seat (active seats by turn [0, 1, 1, 1])"
    ]


def test_missing_engine_active_seat_fails_closed() -> None:
    """Wrong-reason control: without the engine's active-player field the turn
    cannot be bound to a seat, so the contract fails instead of inferring one."""
    trace = tuple((*row[:4], None, *row[5:]) for row in _trace())
    contract = smoke_progress_contract(trace, player_count=4, through_turn=4)
    assert contract["met"] is False
    assert contract["active_seat_by_turn"] == [None, None, None, None]
    assert "a priority decision carried no engine-reported active seat" in contract["violations"]
    assert any("no engine-reported active seat (" in v for v in contract["violations"])


def test_one_missing_active_seat_in_a_turn_fails_closed() -> None:
    trace = list(_trace())
    trace[-1] = (*trace[-1][:4], None, *trace[-1][5:])
    contract = smoke_progress_contract(tuple(trace), player_count=4, through_turn=4)
    assert contract["met"] is False
    assert contract["violations"] == ["a priority decision carried no engine-reported active seat"]


def test_two_active_seats_in_one_turn_fail() -> None:
    trace = (*_trace(), ("priority", 0, 2, "end", 1, DIGEST))
    contract = smoke_progress_contract(trace, player_count=4, through_turn=4)
    assert contract["met"] is False
    assert "a required turn reported more than one active seat" in contract["violations"]


@pytest.mark.parametrize("active", [-1, 4, True, 1.5, "op-1"])
def test_invalid_active_seat_is_not_progress(active) -> None:
    trace = (*_trace(), ("priority", 0, 4, "end", active, DIGEST))
    contract = smoke_progress_contract(trace, player_count=4, through_turn=4)
    assert contract["met"] is False
    assert "a decision carried an invalid active seat" in contract["violations"]


def test_a_pre_active_seat_trace_row_is_malformed() -> None:
    legacy = tuple(row[:4] + row[5:] for row in _trace())
    contract = smoke_progress_contract(legacy, player_count=4, through_turn=4)
    assert contract["met"] is False
    assert "a decision carried a malformed progress row" in contract["violations"]


@pytest.mark.parametrize(
    ("trace", "violation"),
    [
        # The observed trivial start: mulligans and opening passes, turn 1 only.
        (_trace(turns=1), "did not reach turn 4"),
        # Only mulligans: priority never answered.
        (tuple(("mulligan", seat, 1, None, None, DIGEST) for seat in range(4)), "priority missing"),
        # One seat never had priority.
        (_trace(seats=(0, 1, 2)), "not every seat"),
        # A decision without a seat cannot be attributed.
        ((*_trace(), ("priority", None, 2, "end", 3, DIGEST)), "no seat"),
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
        'sorted(contract["active_seat_by_turn"]) == [0, 1, 2, 3]',
        'report["twin_active_seat_by_turn"]',
    ):
        assert clause in verify, clause


@pytest.mark.parametrize("seat", [-1, 4, True, 1.5])
def test_invalid_seat_is_not_progress(seat) -> None:
    contract = smoke_progress_contract(
        (*_trace(), ("priority", seat, 4, "end", 1, DIGEST)), player_count=4, through_turn=4
    )
    assert contract["met"] is False
    assert "a decision carried an invalid seat" in contract["violations"]
