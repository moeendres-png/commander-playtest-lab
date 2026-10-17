"""#875: finishing order as a second outcome in deck comparison.

Pure unit tests (no JVM): scripted batch records drive ``aggregate_comparison``
so the finishing-order scores, the paired placement difference and its
interval can be checked by hand.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FullGameConformanceResult,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameBatchRecord,
    FullGameBatchReport,
)
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonSpec,
    aggregate_comparison,
    finishing_scores,
    plan_comparison_cases,
)
from commander_lab.models import RulesDeckInput

XMAGE_COMMIT = "0" * 40  # any engine commit; not the live pin


def _deck(deck_id: str, index: int) -> RulesDeckInput:
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=tuple("Plains" for _ in range(99)),
        deck_hash=(f"{index:x}" * 64)[:64],
    )


def _spec(seeds: tuple[int, ...]) -> DeckComparisonSpec:
    return DeckComparisonSpec(
        comparison_id="finish-test",
        contenders=(_deck("base", 1), _deck("variant", 2)),
        opponents=(_deck("opp-a", 3), _deck("opp-b", 4), _deck("opp-c", 5)),
        seeds=seeds,
        rotate_seats=False,  # tested_seats == (1,)
        xmage_commit=XMAGE_COMMIT,
    )


def _outcome(
    seat: int,
    *,
    won: bool = False,
    lost: bool = False,
    lost_on_turn: int | None = None,
    with_turn_key: bool = True,
) -> dict[str, object]:
    outcome: dict[str, object] = {
        "seat": seat,
        "life": 20 if won else 0,
        "won": won,
        "lost": lost,
        "left": False,
    }
    if with_turn_key:
        outcome["lost_on_turn"] = lost_on_turn
    return outcome


def _conformance(
    scenario: FutureXmageScenario,
    winner_seats: tuple[int, ...],
    outcomes: list[dict[str, object]],
) -> FullGameConformanceResult:
    return FullGameConformanceResult(
        scenario=scenario,
        engine_version="1.4.61",
        xmage_commit=XMAGE_COMMIT,
        decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
        decision_count=100 + scenario.seed,
        terminal=True,
        winner_seats=winner_seats,
        result_payload={
            "evidence_class": FULL_GAME_EVIDENCE_CLASS,
            "seed": scenario.seed,
            "terminal": True,
            "turn_number": 10 + scenario.seat,
            "transcript": [],
            "outcomes": outcomes,
        },
        semantic_transcript_sha256="a" * 64,
        raw_result_sha256="b" * 64,
        shutdown_disposition="graceful_shutdown",
    )


def _records(
    cases: Sequence[FullGameBatchCase],
    script: dict[tuple[str, int], tuple[tuple[int, ...], list[dict[str, object]]]],
) -> list[FullGameBatchRecord]:
    records = []
    for case in cases:
        scenario = case.scenario
        winner_seats, outcomes = script[(scenario.candidate_id, scenario.seed)]
        records.append(
            FullGameBatchRecord(
                case_id=case.case_id,
                run_key="0" * 64,
                status="completed",
                elapsed_seconds=1.0,
                result=_conformance(scenario, winner_seats, outcomes),
            )
        )
    return records


def _report(records: list[FullGameBatchRecord]) -> FullGameBatchReport:
    return FullGameBatchReport(
        total_cases=len(records),
        completed_cases=sum(1 for record in records if record.status == "completed"),
        failed_cases=sum(1 for record in records if record.status == "failed"),
        resumed_cases=sum(1 for record in records if record.resumed_from_completed_record),
        records=tuple(records),
    )


def test_finishing_scores_winner_and_losses() -> None:
    # (a) Winner seat 2; seats 1, 3, 4 lost on turns 20, 31, 12.
    # Ranks: seat 2 -> 1, seat 3 (latest loss) -> 2, seat 1 -> 3,
    # seat 4 (first out) -> 4. s = (4 - rank) / 3.
    outcomes = [
        _outcome(1, lost=True, lost_on_turn=20),
        _outcome(2, won=True),
        _outcome(3, lost=True, lost_on_turn=31),
        _outcome(4, lost=True, lost_on_turn=12),
    ]
    scores = finishing_scores(outcomes, 4)
    assert scores[2] == pytest.approx(1.0)
    assert scores[3] == pytest.approx(2 / 3)
    assert scores[1] == pytest.approx(1 / 3)
    assert scores[4] == pytest.approx(0.0)


def test_finishing_scores_equal_loss_turns_share_rank() -> None:
    # (b) Seats 2 and 3 lost on the same turn: they share ranks 2 and 3,
    # average 2.5, so (4 - 2.5) / 3 = 0.5 each.
    outcomes = [
        _outcome(1, won=True),
        _outcome(2, lost=True, lost_on_turn=15),
        _outcome(3, lost=True, lost_on_turn=15),
        _outcome(4, lost=True, lost_on_turn=10),
    ]
    scores = finishing_scores(outcomes, 4)
    assert scores[1] == pytest.approx(1.0)
    assert scores[2] == pytest.approx(0.5)
    assert scores[3] == pytest.approx(0.5)
    assert scores[4] == pytest.approx(0.0)


def test_finishing_scores_missing_loss_turn_gives_none() -> None:
    # (c) A lost seat without lost_on_turn (pre-#874 result): no ranks at all.
    outcomes = [
        _outcome(1, lost=True, lost_on_turn=20),
        _outcome(2, lost=True, with_turn_key=False),
        _outcome(3),
        _outcome(4),
    ]
    scores = finishing_scores(outcomes, 4)
    assert set(scores) == {1, 2, 3, 4}
    assert all(score is None for score in scores.values())


def test_finishing_scores_survivors_share_top_ranks() -> None:
    # (d) No winner, two survivors: they share ranks 1 and 2 (average 1.5),
    # so (4 - 1.5) / 3 = 5/6 each. Losers rank below by loss turn.
    outcomes = [
        _outcome(1),
        _outcome(2),
        _outcome(3, lost=True, lost_on_turn=30),
        _outcome(4, lost=True, lost_on_turn=10),
    ]
    scores = finishing_scores(outcomes, 4)
    assert scores[1] == pytest.approx(5 / 6)
    assert scores[2] == pytest.approx(5 / 6)
    assert scores[3] == pytest.approx(1 / 3)
    assert scores[4] == pytest.approx(0.0)


def _win(seat0: int) -> tuple[int, ...]:
    """1-based winner_seats for a 0-based winning outcome seat."""
    return (seat0 + 1,)


def _placement_script() -> dict[tuple[str, int], tuple[tuple[int, ...], list[dict[str, object]]]]:
    # Three pairs; the tested deck sits on outcomes seat 0 (tested seat 1).
    # Pair 1: baseline wins (1.0), variant first out (0.0) -> d = -1.0.
    # Pair 2: baseline first out (0.0), variant wins (1.0) -> d = +1.0.
    # Pair 3: baseline loses turn 20 (rank 3 -> 1/3),
    #         variant loses turn 30 (rank 2 -> 2/3) -> d = 1/3.
    return {
        ("base", 1): (
            _win(0),
            [
                _outcome(0, won=True),
                _outcome(1, lost=True, lost_on_turn=10),
                _outcome(2, lost=True, lost_on_turn=20),
                _outcome(3, lost=True, lost_on_turn=30),
            ],
        ),
        ("variant", 1): (
            _win(1),
            [
                _outcome(0, lost=True, lost_on_turn=10),
                _outcome(1, won=True),
                _outcome(2, lost=True, lost_on_turn=20),
                _outcome(3, lost=True, lost_on_turn=30),
            ],
        ),
        ("base", 2): (
            _win(1),
            [
                _outcome(0, lost=True, lost_on_turn=10),
                _outcome(1, won=True),
                _outcome(2, lost=True, lost_on_turn=20),
                _outcome(3, lost=True, lost_on_turn=30),
            ],
        ),
        ("variant", 2): (
            _win(0),
            [
                _outcome(0, won=True),
                _outcome(1, lost=True, lost_on_turn=10),
                _outcome(2, lost=True, lost_on_turn=20),
                _outcome(3, lost=True, lost_on_turn=30),
            ],
        ),
        ("base", 3): (
            _win(1),
            [
                _outcome(0, lost=True, lost_on_turn=20),
                _outcome(1, won=True),
                _outcome(2, lost=True, lost_on_turn=10),
                _outcome(3, lost=True, lost_on_turn=30),
            ],
        ),
        ("variant", 3): (
            _win(2),
            [
                _outcome(0, lost=True, lost_on_turn=30),
                _outcome(1, lost=True, lost_on_turn=10),
                _outcome(2, won=True),
                _outcome(3, lost=True, lost_on_turn=20),
            ],
        ),
    }


def test_aggregate_comparison_placement_difference() -> None:
    # (e) Hand-computed: d = [-1.0, +1.0, 1/3], mean 1/9.
    # sd = sqrt(((10/9)^2 + (8/9)^2 + (2/9)^2) / 2) = sqrt(28/27);
    # 95% half-width = 1.96 * sd / sqrt(3).
    spec = _spec((1, 2, 3))
    cases = plan_comparison_cases(spec)
    report = aggregate_comparison(spec, _report(_records(cases, _placement_script())))
    paired = report.paired[0]
    assert paired.placement_pairs == 3
    assert paired.placement_difference == pytest.approx(1 / 9)
    mean, sd = 1 / 9, math.sqrt(28 / 27)
    half = 1.96 * sd / math.sqrt(3)
    assert paired.placement_difference_interval_95 is not None
    assert paired.placement_difference_interval_95.low == pytest.approx(mean - half)
    assert paired.placement_difference_interval_95.high == pytest.approx(mean + half)
    # Contender means over the tested seat's games: base (1 + 0 + 1/3)/3,
    # variant (0 + 1 + 2/3)/3.
    by_id = {c.deck_id: c for c in report.contenders}
    assert by_id["base"].mean_finishing_score == pytest.approx(4 / 9)
    assert by_id["variant"].mean_finishing_score == pytest.approx(5 / 9)


def test_aggregate_comparison_without_loss_turns() -> None:
    # (f) Old results without lost_on_turn still aggregate: the placement
    # fields stay None/0 and the win verdict logic is untouched.
    script = {
        key: (
            winners,
            [
                _outcome(o["seat"], won=bool(o["won"]), lost=bool(o["lost"]), with_turn_key=False)
                for o in outcomes
            ],
        )
        for key, (winners, outcomes) in _placement_script().items()
    }
    spec = _spec((1, 2, 3))
    cases = plan_comparison_cases(spec)
    report = aggregate_comparison(spec, _report(_records(cases, script)))
    paired = report.paired[0]
    assert paired.placement_difference is None
    assert paired.placement_difference_interval_95 is None
    assert paired.placement_pairs == 0
    for contender in report.contenders:
        assert contender.mean_finishing_score is None
    # Win verdict from the same games: 1 variant-only, 1 baseline-only win.
    assert paired.variant_only_wins == 1
    assert paired.baseline_only_wins == 1
    assert paired.verdict == "NO_CLEAR_DIFFERENCE"
