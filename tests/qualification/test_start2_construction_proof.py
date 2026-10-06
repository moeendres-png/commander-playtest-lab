"""WS05-CMD-START-2 carries its own construction proof (#441, Owner decision (c)).

START-2 runs on a keyed (orchestration) launch, so the provider's constructed
state is read and compared with the record's requested state. Only an
established equality lifts the construction gap; a missing or unequal proof
keeps the fully observed CR 103.8a obligation UNKNOWN, and a Rules-visible
draw stays FAIL whatever the proof says.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import full107, generic_construction
from commander_lab.qualification.current_boundary.game_driver import (
    CommandedGameResult,
    DecisionTapeEntry,
)
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

FIXTURE = "WS05-CMD-START-2"
RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_current_boundary_qualification.py"


@pytest.fixture(scope="module")
def record() -> dict[str, Any]:
    return load_effective_materialization().record(FIXTURE)


def _observed(*, keyed: bool) -> CommandedGameResult:
    """A fully observed CR 103.8a skip; ``keyed`` marks an orchestration launch."""
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
            "starting_seat_channel": "create_request_echo_verified",
        }
    )
    if keyed:
        result.terminal_facts.update(
            {
                "provider_constructed_state_supported": True,
                "constructed_state_channel": "orchestration_keyed_launch",
                "constructed_state_capture": generic_construction.CAPTURE_POINT,
            }
        )
        result.constructed_state = {"schema": generic_construction.SCHEMA}
        result.orchestration_key = b"k" * 32
    result.decision_tape = [
        DecisionTapeEntry(
            "priority", "PRIORITY", "p1", 1, "pass_when_offered", "a", ["a"], "observed"
        )
    ]
    return result


def _proof(verdict: str) -> generic_construction.ConstructionProof:
    check = generic_construction.FieldCheck(
        "temporal_state.phase",
        "EQUAL" if verdict == generic_construction.EQUAL else "MISMATCH",
        "precombat_main",
        "precombat_main" if verdict == generic_construction.EQUAL else "pregame",
        "test proof",
    )
    return generic_construction.ConstructionProof(verdict, (check,))


def _run(
    record: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    game: CommandedGameResult,
    proof: generic_construction.ConstructionProof | None,
) -> full107.RowResult:
    monkeypatch.setattr(full107, "drive_commander_game", lambda *a, **k: game)
    if proof is not None:
        monkeypatch.setattr(full107.generic_construction, "compare", lambda *a, **k: proof)
    return full107.start2_row(record, object(), candidate="xmage", runtime_identity={})


def test_an_equal_construction_proof_credits_pass(record, monkeypatch) -> None:
    row = _run(record, monkeypatch, _observed(keyed=True), _proof(generic_construction.EQUAL))
    assert row.outcome == "PASS"
    assert row.evidence["construction_proof"]["verdict"] == generic_construction.EQUAL


def test_a_missing_proof_stays_unknown(record, monkeypatch) -> None:
    # An un-keyed launch emits no constructed state, so there is no proof at all.
    row = _run(record, monkeypatch, _observed(keyed=False), None)
    assert row.outcome == "UNKNOWN"
    assert "emits no normalized constructed state" in row.reason
    assert "construction_proof" not in row.evidence


def test_a_mismatch_proof_stays_unknown(record, monkeypatch) -> None:
    row = _run(record, monkeypatch, _observed(keyed=True), _proof(generic_construction.MISMATCH))
    assert row.outcome == "UNKNOWN"
    assert "CR 103.8a obligation was observed" in row.reason
    assert "does not establish it" in row.reason
    assert row.evidence["construction_proof"]["verdict"] == generic_construction.MISMATCH


def test_an_observed_draw_still_fails_with_an_equal_proof(record, monkeypatch) -> None:
    game = _observed(keyed=True)
    game.semantic_events.append("draw:P1:turn1")
    row = _run(record, monkeypatch, game, _proof(generic_construction.EQUAL))
    assert row.outcome == "FAIL"
    assert "draw event" in row.reason


def test_changed_counts_still_fail_with_an_equal_proof(record, monkeypatch) -> None:
    game = _observed(keyed=True)
    game.terminal_facts["start2_post_zone_counts"] = [{"hand_count": 8, "library_count": 91}]
    row = _run(record, monkeypatch, game, _proof(generic_construction.EQUAL))
    assert row.outcome == "FAIL"


def test_the_effective_record_is_a_natural_game_start(record) -> None:
    """Contract 1.0.22 (#441 comment 6007651998) made START-2 a natural-start record.

    The 1.0.21 record requested a native state load at turn-1 precombat main
    with non-commander battlefield objects and no deck state, which the generic
    lane could never construct. The successor requests what the lane builds: a
    natural game start read at the first mulligan, with the record's own decks
    and seed (test_start2_mull_errata_conditions proves the proof and the row).
    """
    assert record["execution_entry_mode"] == "NATURAL_GAME_START"
    assert (record["temporal_state"]["phase"], record["temporal_state"]["turn_number"]) == (
        "pregame",
        0,
    )
    assert {o["zone"] for o in record["semantic_objects"]} == {"command"}
    assert full107.record_rules_seed(record) == 424242
    assert len(full107.record_decks(record)) == 2


def test_the_runner_runs_start2_on_a_keyed_launch() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    block = source[source.index("# ---- START-2 under the v1.0.6 successor") :]
    block = block[: block.index("# ---- scripted pregame")]
    assert "with launch(orchestration_plan(plan)) as keyed:" in block
    assert 'by_id["WS05-CMD-START-2"], keyed,' in " ".join(block.split())
