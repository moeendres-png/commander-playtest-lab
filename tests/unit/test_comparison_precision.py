"""#870: deck comparison reports how sure the answer is.

Pure unit tests (no JVM): the paired-difference interval, the detectable
difference, the pairs-needed helper and the underpowered flag are checked
against hand arithmetic; scripted batch records drive aggregate_comparison
and _summary_lines.
"""

from __future__ import annotations

import importlib.util
import math
import statistics
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules import full_game_comparison as fgc
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
    pairs_needed,
    plan_comparison_cases,
)
from commander_lab.models import RulesDeckInput

XMAGE_COMMIT = "0" * 40  # any engine commit; not the live pin
WinnerFn = Callable[[str, int, int], tuple[int, ...]]


def _deck(deck_id: str, index: int) -> RulesDeckInput:
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=tuple("Plains" for _ in range(99)),
        deck_hash=(f"{index:x}" * 64)[:64],
    )


def _spec(seeds: tuple[int, ...], *, rotate: bool = False) -> DeckComparisonSpec:
    return DeckComparisonSpec(
        comparison_id="precision-test",
        contenders=(_deck("base", 1), _deck("variant", 2)),
        opponents=(_deck("opp-a", 3), _deck("opp-b", 4), _deck("opp-c", 5)),
        seeds=seeds,
        rotate_seats=rotate,
        xmage_commit=XMAGE_COMMIT,
    )


def _conformance(
    scenario: FutureXmageScenario, winner_seats: tuple[int, ...]
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
        },
        semantic_transcript_sha256="a" * 64,
        raw_result_sha256="b" * 64,
        shutdown_disposition="graceful_shutdown",
    )


def _records_for(cases: Sequence[FullGameBatchCase], winner: WinnerFn) -> list[FullGameBatchRecord]:
    records = []
    for case in cases:
        scenario = case.scenario
        records.append(
            FullGameBatchRecord(
                case_id=case.case_id,
                run_key="0" * 64,
                status="completed",
                elapsed_seconds=1.0,
                result=_conformance(
                    scenario, winner(scenario.candidate_id, scenario.seed, scenario.seat)
                ),
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


def _other_seat(seat: int) -> int:
    return seat % 4 + 1


def _variant_sweep(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
    """The variant wins the pair: it wins its game, the baseline loses its own."""
    return (seat,) if contender_id == "variant" else (_other_seat(seat),)


def _alternating(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
    if (seed + seat) % 2 == 0:
        return _variant_sweep(contender_id, seed, seat)
    return (seat,) if contender_id == "base" else (_other_seat(seat),)


def _tie(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
    """The tested seat loses both games: every pair difference is 0."""
    return (_other_seat(seat),)


def _script_module():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "scripts/run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("run_full_game_deck_comparison", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_hand_arithmetic() -> None:
    """The exact assertions of acceptance item (a)."""
    differences = [1.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    sd = statistics.stdev(differences)
    se = sd / math.sqrt(len(differences))
    assert round(sd, 4) == 0.5676
    assert round(se, 4) == 0.1795
    interval, detectable = fgc._paired_difference_stats(differences)
    assert interval is not None and detectable is not None
    assert round(interval.low, 3) == -0.252
    assert round(interval.high, 3) == 0.452
    assert round(detectable, 3) == 0.503


def test_difference_interval_hand_arithmetic() -> None:
    # Hand arithmetic (2026-10-17): n = 10, mean = 1/10 = 0.1. Sum of squared
    # deviations = 2*(1-0.1)^2 + (-1-0.1)^2 + 7*(0-0.1)^2
    #            = 1.62 + 1.21 + 0.07 = 2.90.
    # Sample sd = sqrt(2.90/9) = 0.56765... -> 0.5676.
    # Standard error = 0.56765.../sqrt(10) = 0.17951... -> 0.1795.
    # Interval = 0.1 +/- 1.96*0.17951... = -0.25184...+0.45184... -> -0.252..+0.452.
    # Detectable = (1.96 + 0.8416)*0.17951... = 0.50290... -> 0.503.
    _assert_hand_arithmetic()


def test_pairs_needed() -> None:
    # ceil(((1.96 + 0.8416) * 0.63 / 0.10) ** 2) = ceil(311.525...) = 312.
    assert pairs_needed(0.10, 0.63) == 312
    # ceil(((1.96 + 0.8416) * 0.63 / 0.05) ** 2) = ceil(1246.101...) = 1247.
    assert pairs_needed(0.05, 0.63) == 1247
    with pytest.raises(ValueError, match="difference"):
        pairs_needed(0.0, 0.63)


def test_degenerate_differences_return_none() -> None:
    interval, detectable = fgc._paired_difference_stats([0.0, 0.0, 0.0])
    assert interval is None and detectable is None  # sd == 0
    interval, detectable = fgc._paired_difference_stats([0.5])
    assert interval is None and detectable is None  # n < 2
    interval, detectable = fgc._paired_difference_stats([])
    assert interval is None and detectable is None


def test_zero_spread_run_is_not_underpowered() -> None:
    spec = _spec((1, 2), rotate=False)
    cases = plan_comparison_cases(spec)
    comparison = aggregate_comparison(spec, _report(_records_for(cases, _tie)))
    paired = comparison.paired[0]
    assert paired.win_share_difference == 0.0
    assert paired.win_share_difference_interval_95 is None
    assert paired.detectable_difference_80pct_power is None
    assert paired.underpowered is False
    assert paired.verdict == "NO_CLEAR_DIFFERENCE"


def test_single_pair_run_is_not_underpowered() -> None:
    spec = _spec((1,), rotate=False)
    cases = plan_comparison_cases(spec)
    comparison = aggregate_comparison(spec, _report(_records_for(cases, _variant_sweep)))
    paired = comparison.paired[0]
    assert paired.pairs_completed == 1
    assert paired.win_share_difference_interval_95 is None
    assert paired.detectable_difference_80pct_power is None
    assert paired.underpowered is False


def test_fifty_fifty_100_pair_run_is_underpowered() -> None:
    spec = _spec(tuple(range(1, 26)), rotate=True)
    cases = plan_comparison_cases(spec)
    comparison = aggregate_comparison(spec, _report(_records_for(cases, _alternating)))
    paired = comparison.paired[0]
    assert paired.pairs_completed == 100
    assert paired.variant_only_wins == paired.baseline_only_wins == 50
    assert paired.verdict == "NO_CLEAR_DIFFERENCE"  # sign-test verdict unchanged
    detectable = paired.detectable_difference_80pct_power
    assert detectable is not None and detectable > 0.10
    assert paired.underpowered is True
    interval = paired.win_share_difference_interval_95
    assert interval is not None
    assert interval.low < 0.0 < interval.high


def test_summary_lines_old_payload_unchanged() -> None:
    cli = _script_module()
    payload = {
        "contenders": [
            {
                "deck_id": "base",
                "wins": 50.0,
                "games_completed": 100,
                "games_failed": 0,
                "win_share": 0.5,
                "win_share_interval_95": {"low": 0.4, "high": 0.6},
            }
        ],
        "paired": [
            {
                "variant_deck_id": "variant",
                "baseline_deck_id": "base",
                "verdict": "NO_CLEAR_DIFFERENCE",
                "pairs_completed": 100,
                "variant_only_wins": 50,
                "baseline_only_wins": 50,
                "identical_pairs": 0,
                "sign_test_p_value": 1.0,
            }
        ],
        "seeds": list(range(1, 26)),
    }
    assert cli._summary_lines(payload) == [
        "base: 50.0/100 wins (50.0%, 95% 40.0%-60.0%), failed 0",
        "variant vs base: NO_CLEAR_DIFFERENCE (pairs 100, variant-only 50, "
        "baseline-only 50, identical pairs 0, p=1)",
    ]


def test_summary_lines_new_payload_adds_precision_lines() -> None:
    cli = _script_module()
    spec = _spec(tuple(range(1, 26)), rotate=True)
    cases = plan_comparison_cases(spec)
    comparison = aggregate_comparison(spec, _report(_records_for(cases, _alternating)))
    lines = cli._summary_lines(comparison.model_dump(mode="json"))
    precision = next(line for line in lines if "run could detect" in line)
    assert "difference +0.00" in precision
    assert "0.10 needs ~793 pairs" in precision
    assert "0.05 needs ~" in precision
    assert any(line.startswith("UNDERPOWERED:") for line in lines)


def test_wrong_reason_control_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flipping the 95% quantile (1.96 -> 1.0) must break the hand-arithmetic
    assertions, so test (a) cannot pass for the wrong reason."""
    monkeypatch.setattr(fgc, "DIFFERENCE_Z95", 1.0)
    with pytest.raises(AssertionError):
        _assert_hand_arithmetic()


def test_planned_detectable_difference() -> None:
    # (1.96 + 0.8416) * 0.63 / sqrt(100) = 0.17650... (#873)
    assert round(fgc.planned_detectable_difference(100), 4) == 0.1765
    # Custom sd is honored.
    assert round(fgc.planned_detectable_difference(100, sd=0.5), 4) == 0.1401
    with pytest.raises(ValueError, match="pairs"):
        fgc.planned_detectable_difference(0)


def test_plan_only_prints_time_estimate_and_detectable_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--plan-only is JVM-free: it prints games, time and detectable difference (#873)."""
    cli = _script_module()
    root = Path(__file__).resolve().parents[2]
    code = cli.main(
        [
            "--baseline",
            str(root / "data/decks/rogshai_current.json"),
            "--swap",
            "Sol Ring=>Mind Stone",
            "--opponent",
            str(root / "data/opponents/hosts_of_mordor_precon.json"),
            "--opponent",
            str(root / "data/opponents/lorehold_spirit_precon.json"),
            "--opponent",
            str(root / "data/decks/opponents/kaervek/current/deck.json"),
            "--seeds",
            "1-25",
            "--out",
            str(tmp_path / "out"),
            "--plan-only",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    # 2 contenders x 25 seeds x 4 seats = 200 games
    assert "200 games: 2 contenders x 25 seeds x 4 seats" in out
    assert "Time estimate at 40 games/hour: 5.0 h" in out
    # 25 seeds x 4 tested seats = 100 pairs -> (1.96+0.8416)*0.63/10 = 0.18
    assert "Detectable win-share difference per variant (80% power, 100 pairs)" in out


def test_plan_only_games_per_hour_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = _script_module()
    root = Path(__file__).resolve().parents[2]
    code = cli.main(
        [
            "--baseline",
            str(root / "data/decks/rogshai_current.json"),
            "--swap",
            "Sol Ring=>Mind Stone",
            "--opponent",
            str(root / "data/opponents/hosts_of_mordor_precon.json"),
            "--opponent",
            str(root / "data/opponents/lorehold_spirit_precon.json"),
            "--opponent",
            str(root / "data/decks/opponents/kaervek/current/deck.json"),
            "--seeds",
            "1-25",
            "--out",
            str(tmp_path / "out"),
            "--plan-only",
            "--games-per-hour",
            "100",
        ]
    )
    assert code == 0
    assert "Time estimate at 100 games/hour: 2.0 h" in capsys.readouterr().out
