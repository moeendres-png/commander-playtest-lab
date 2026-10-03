"""B8 (#489): the Real4P smoke must show deterministic meaningful progress."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from commander_lab.engine.rules.full_game import smoke_progress_contract

ROOT = Path(__file__).resolve().parents[2]


def _trace(turns: int = 4, seats: tuple[int, ...] = (0, 1, 2, 3)) -> tuple:
    trace = [("mulligan", seat, 1, None, "ab" * 32) for seat in seats]
    for turn in range(1, turns + 1):
        trace += [("priority", seat, turn, "precombat_main", "ab" * 32) for seat in seats]
    return tuple(trace)


def test_full_seat_cycle_meets_the_contract() -> None:
    contract = smoke_progress_contract(_trace(), player_count=4, through_turn=4)
    assert contract["met"] is True
    assert contract["priority_turns"] == [1, 2, 3, 4]
    assert contract["priority_seats"] == [0, 1, 2, 3]


@pytest.mark.parametrize(
    ("trace", "violation"),
    [
        # The observed trivial start: mulligans and opening passes, turn 1 only.
        (_trace(turns=1), "did not reach turn 4"),
        # Only mulligans: priority never answered.
        (tuple(("mulligan", seat, 1, None, "ab" * 32) for seat in range(4)), "priority missing"),
        # One seat never had priority.
        (_trace(seats=(0, 1, 2)), "not every seat"),
        # A decision without a seat cannot be attributed.
        ((*_trace(), ("priority", None, 2, "end", "ab" * 32)), "no seat"),
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
    ):
        assert clause in verify, clause


@pytest.mark.parametrize("seat", [-1, 4, True, 1.5])
def test_invalid_seat_is_not_progress(seat) -> None:
    contract = smoke_progress_contract(
        (*_trace(), ("priority", seat, 4, "end", "ab" * 32)), player_count=4, through_turn=4
    )
    assert contract["met"] is False
    assert "a decision carried an invalid seat" in contract["violations"]
