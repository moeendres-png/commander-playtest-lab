"""Generic-lane rows are credited only with construction equality (#441, Owner decision (a)).

The effective PLAYER_COUNT_2P..5P, WS05-CMD-START-2 and PILOT_MULLIGAN records
require the provider's normalized constructed state to equal the requested state
(``REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST``). The generic
Protocol-2 lane emits no constructed state, so a fully observed obligation there
is UNKNOWN, never PASS. Rules-visible FAILs stay FAIL.
"""

from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary import full107
from commander_lab.qualification.current_boundary.game_driver import (
    CommandedGameResult,
    DecisionTapeEntry,
)
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

GENERIC_LANE_ROWS = (
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "WS05-CMD-START-2",
    "PILOT_MULLIGAN",
)


@pytest.fixture(scope="module")
def records() -> dict[str, dict]:
    materialization = load_effective_materialization()
    return {fixture_id: materialization.record(fixture_id) for fixture_id in GENERIC_LANE_ROWS}


def test_every_generic_lane_record_requires_construction_equality(records) -> None:
    for fixture_id, record in records.items():
        construction = record["construction_validation"]
        assert construction["required"] is True, fixture_id
        assert (
            construction["credit_condition"]
            == "REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST"
        ), fixture_id
        assert full107.construction_credit_gap(record) is not None, fixture_id


def test_a_record_without_the_requirement_imposes_no_gap() -> None:
    assert full107.construction_credit_gap({"fixture_id": "X"}) is None
    assert full107.construction_credit_gap({"construction_validation": {"required": False}}) is None


def _keeps(count: int) -> list[DecisionTapeEntry]:
    """The record's scripted pregame as the driver tapes it: one keep per seat."""
    return [
        DecisionTapeEntry(
            "mulligan",
            "KEEP_OR_MULLIGAN",
            f"engine-{seat}",
            seat,
            "record_plan",
            None,
            ["opt-keep", "opt-mulligan"],
            "planned",
            seat=f"p{seat}",
            keep=True,
        )
        for seat in range(1, count + 1)
    ]


def _lifecycle(created: int) -> CommandedGameResult:
    result = CommandedGameResult(
        candidate="xmage", player_count=created, deck_identity=["d"] * created, game_id="g"
    )
    result.terminal_facts["created_player_count"] = created
    result.decision_tape = _keeps(created)
    return result


@pytest.fixture
def complete_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        full107.lifecycle,
        "lifecycle_completeness",
        lambda run: {"complete": True, "reasons": []},
    )


@pytest.mark.usefixtures("complete_lifecycle")
@pytest.mark.parametrize("fixture_id", GENERIC_LANE_ROWS[:4])
def test_a_complete_lifecycle_without_construction_proof_is_unknown(records, fixture_id) -> None:
    record = records[fixture_id]
    wanted = len(record["players"])
    row = full107.cardinality_row(
        record, _lifecycle(wanted), candidate="xmage", runtime_identity={}
    )
    assert row.outcome == "UNKNOWN"
    assert "construction equality is unestablished" in row.reason
    assert "REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST" in row.reason


@pytest.mark.usefixtures("complete_lifecycle")
def test_the_same_lifecycle_passes_only_for_a_record_without_the_requirement(records) -> None:
    record = dict(records["PLAYER_COUNT_4P"])
    record.pop("construction_validation")
    row = full107.cardinality_row(record, _lifecycle(4), candidate="xmage", runtime_identity={})
    assert row.outcome == "PASS"


@pytest.mark.usefixtures("complete_lifecycle")
def test_a_wrong_player_count_is_still_fail(records) -> None:
    row = full107.cardinality_row(
        records["PLAYER_COUNT_4P"], _lifecycle(3), candidate="xmage", runtime_identity={}
    )
    assert row.outcome == "FAIL"


def _start2_observed() -> CommandedGameResult:
    result = CommandedGameResult(
        candidate="xmage", player_count=2, deck_identity=["d1", "d2"], game_id="g"
    )
    counts = [{"hand_count": 7, "library_count": 92}]
    result.terminal_facts.update(
        {
            "start2_baseline_zone_counts": counts,
            "start2_baseline_checkpoint": {
                "turn_number": 1,
                "phase": "beginning",
                "step": "upkeep",
            },
            "start2_post_zone_counts": counts,
            "observed_actor_zone_counts": counts,
            "start2_post_checkpoint": {"turn_number": 1, "phase": "precombat_main", "step": "main"},
            "draw_step_decision_frames": [],
            "priority_reached": True,
            "first_priority_seat": "p1",
        }
    )
    result.decision_tape = [
        DecisionTapeEntry(
            "priority", "PRIORITY", "p1", 1, "pass_when_offered", "a", ["a"], "observed"
        )
    ]
    return result


def test_start2_fully_observed_without_construction_proof_is_unknown(
    records, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(full107, "drive_commander_game", lambda *a, **k: _start2_observed())
    row = full107.start2_row(
        records["WS05-CMD-START-2"], object(), candidate="xmage", runtime_identity={}
    )
    assert row.outcome == "UNKNOWN"
    assert "CR 103.8a obligation was observed" in row.reason
    assert "construction equality is unestablished" in row.reason


def test_start2_rules_visible_fail_is_not_hidden_by_the_gap(
    records, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed = _start2_observed()
    observed.terminal_facts["start2_post_zone_counts"] = [{"hand_count": 8, "library_count": 91}]
    monkeypatch.setattr(full107, "drive_commander_game", lambda *a, **k: observed)
    row = full107.start2_row(
        records["WS05-CMD-START-2"], object(), candidate="xmage", runtime_identity={}
    )
    assert row.outcome == "FAIL"
