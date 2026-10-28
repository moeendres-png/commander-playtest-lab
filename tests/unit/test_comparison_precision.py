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


def test_cluster_difference_stats_matches_iid_when_one_pair_per_seed() -> None:
    diffs = [1.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    clustered = [(i, d) for i, d in enumerate(diffs, start=1)]
    interval, detectable, se = fgc.cluster_difference_stats(clustered)
    iid_interval, iid_detectable = fgc._paired_difference_stats(diffs)
    assert interval is not None and detectable is not None and se is not None
    assert iid_interval is not None and iid_detectable is not None
    assert interval == iid_interval
    assert detectable == iid_detectable
    assert interval.low == pytest.approx(iid_interval.low)
    assert interval.high == pytest.approx(iid_interval.high)
    assert detectable == pytest.approx(iid_detectable)
    assert round(se, 4) == 0.1795
    assert round(interval.low, 3) == -0.252
    assert round(interval.high, 3) == 0.452
    assert round(detectable, 3) == 0.503


def test_student_t_quantile_reference_values_and_validation() -> None:
    # Cauchy (df=1): F_1^-1(0.975) = tan(0.475 * pi) = 12.706204736...
    assert fgc.student_t_quantile(0.975, 1) == pytest.approx(math.tan(0.475 * math.pi))
    # df=3 (G=4): t_0.975,3 = 3.182446..., t_0.80,3 = 0.978472...
    assert round(fgc.student_t_quantile(0.975, 3), 4) == 3.1824
    assert round(fgc.student_t_quantile(0.80, 3), 4) == 0.9785
    # df=9 (G=10): t_0.975,9 = 2.262157..., t_0.80,9 = 0.883360...
    assert round(fgc.student_t_quantile(0.975, 9), 4) == 2.2622
    assert round(fgc.student_t_quantile(0.80, 9), 4) == 0.8834
    # Symmetry and median
    assert fgc.student_t_quantile(0.5, 5) == 0.0
    assert fgc.student_t_quantile(0.025, 3) == pytest.approx(-fgc.student_t_quantile(0.975, 3))
    with pytest.raises(ValueError, match="p must be within"):
        fgc.student_t_quantile(1.0, 3)
    with pytest.raises(ValueError, match="df must be at least 1"):
        fgc.student_t_quantile(0.975, 0)


def _assert_cluster_t_quantile_hand_arithmetic() -> None:
    # Hand arithmetic for G=4 seeds x 4 seats = 16 pairs (df = G - 1 = 3):
    # Seeds 1, 2, 3 have 4 pairs of +1.0; seed 4 has 4 pairs of -1.0.
    # mean = (12 - 4) / 16 = 0.5.
    # Cluster residual sums: u_1 = u_2 = u_3 = 4*(1.0 - 0.5) = +2.0 (u^2 = 4);
    # u_4 = 4*(-1.0 - 0.5) = -6.0 (u^2 = 36). sum(u^2) = 3*4 + 36 = 48.
    # se_cluster^2 = (4/3) * (48 / 256) = 0.25 -> se_cluster = 0.5 (exact).
    # With z=1.96 (wrong): width = 2*1.96*0.5 = 1.9600, detectable = (1.96+0.8416)*0.5 = 1.4008.
    # With t_df=3 (correct): t_0.975,3 = 3.1824463..., t_0.80,3 = 0.9784723...
    # half_width = 3.1824463... * 0.5 = 1.59122315... -> [-1.0912, +2.0912], width = 3.1824.
    # detectable = (3.1824463... + 0.9784723...) * 0.5 = 2.0804593... -> 2.0805.
    clustered_g4: list[tuple[int, float]] = [
        *((seed, 1.0) for seed in (1, 2, 3) for _ in range(4)),
        *((4, -1.0) for _ in range(4)),
    ]
    interval_g4, detectable_g4, se_g4 = fgc.cluster_difference_stats(clustered_g4)
    assert interval_g4 is not None and detectable_g4 is not None and se_g4 is not None
    assert se_g4 == pytest.approx(0.5)
    assert round(interval_g4.low, 4) == -1.0912
    assert round(interval_g4.high, 4) == 2.0912
    assert round(interval_g4.high - interval_g4.low, 4) == 3.1824
    assert round(detectable_g4, 4) == 2.0805

    # Hand arithmetic for G=10 seeds x 4 seats = 40 pairs (df = G - 1 = 9):
    # 6 seeds at +1.0, 4 seeds at -1.0 -> mean = 0.2, se_cluster = sqrt(9.6 / 90) = 0.3265986...
    # With z (wrong): width = 2 * 1.96 * 0.3265986... = 1.2803, detectable = 0.9150.
    # With t_df=9 (correct): width = 2 * 2.262157... * 0.3265986... = 1.4776, detectable = 1.0273.
    clustered_g10: list[tuple[int, float]] = [
        *((seed, 1.0) for seed in range(1, 7) for _ in range(4)),
        *((seed, -1.0) for seed in range(7, 11) for _ in range(4)),
    ]
    interval_g10, detectable_g10, se_g10 = fgc.cluster_difference_stats(clustered_g10)
    assert interval_g10 is not None and detectable_g10 is not None and se_g10 is not None
    assert round(se_g10, 6) == 0.326599
    assert round(interval_g10.low, 4) == -0.5388
    assert round(interval_g10.high, 4) == 0.9388
    assert round(interval_g10.high - interval_g10.low, 4) == 1.4776
    assert round(detectable_g10, 4) == 1.0273


def test_cluster_t_quantile_hand_arithmetic_and_wrong_reason_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_cluster_t_quantile_hand_arithmetic()
    # Wrong-reason control: falling back to normal quantiles z95 / z80 must fail the test.
    monkeypatch.setattr(
        fgc,
        "student_t_quantile",
        lambda p, df: fgc.DIFFERENCE_Z95 if p > 0.9 else fgc.DIFFERENCE_Z80,
    )
    with pytest.raises(AssertionError):
        _assert_cluster_t_quantile_hand_arithmetic()


def test_reanalyze_paired_variant_compares_old_z_and_new_t() -> None:
    # Synthetic report recorded under old z quantiles with G=4, N=16, se_cluster=0.5, mean=1.1:
    # Under z=1.96: interval is 1.1 +/- 0.98 = [+0.12, +2.08] (excludes 0.0).
    # Under t_df=3 (3.1824): interval is 1.1 +/- 1.5912 = [-0.4912, +2.6912] (includes 0.0).
    old_paired = fgc.PairedVariantResult(
        variant_deck_id="variant",
        baseline_deck_id="base",
        pairs_completed=16,
        pairs_censored=0,
        variant_win_share=0.80,
        baseline_win_share=0.25,
        win_share_difference=1.10,
        variant_only_wins=11,
        baseline_only_wins=5,
        identical_pairs=0,
        sign_test_p_value=fgc.sign_test_p_value(11, 5),
        verdict="NO_CLEAR_DIFFERENCE",
        seed_clusters_completed=4,
        win_share_difference_interval_95=fgc.DifferenceInterval(low=0.60, high=1.60),
        cluster_difference_interval_95=fgc.DifferenceInterval(low=0.12, high=2.08),
        detectable_difference_80pct_power=0.70,
        cluster_detectable_difference_80pct_power=1.4008,
        underpowered=True,
    )
    reanalyzed = fgc.reanalyze_paired_variant(old_paired, source_quantiles="z")
    assert reanalyzed.cluster_se == pytest.approx(0.5)
    assert reanalyzed.z_cluster_interval_95 is not None
    assert reanalyzed.t_cluster_interval_95 is not None
    assert round(reanalyzed.z_cluster_interval_95.low, 4) == 0.1200
    assert round(reanalyzed.t_cluster_interval_95.low, 4) == -0.4912
    assert round(reanalyzed.t_cluster_interval_95.high, 4) == 2.6912
    assert reanalyzed.old_interval_excludes_zero is True
    assert reanalyzed.new_interval_excludes_zero is False
    assert reanalyzed.interval_zero_crossing_changed is True
    assert reanalyzed.verdict_changed is False
    summary = fgc.format_reanalysis_summary(reanalyzed)
    assert "variant vs base" in summary
    assert "verdict_changed=False" in summary
    assert "zero_crossing_changed=True" in summary


def test_cluster_difference_stats_recovers_true_cluster_spread_wrong_reason_control() -> None:
    clustered: list[tuple[int, float]] = []
    for seed in range(1, 7):
        for _ in range(4):
            clustered.append((seed, 1.0))
    for seed in range(7, 11):
        for _ in range(4):
            clustered.append((seed, -1.0))

    assert len(clustered) == 40
    diffs = [d for _, d in clustered]

    interval, detectable, se_cluster = fgc.cluster_difference_stats(clustered)
    iid_interval, iid_detectable = fgc._paired_difference_stats(diffs)

    assert interval is not None and detectable is not None and se_cluster is not None
    assert iid_interval is not None and iid_detectable is not None

    expected_se = math.sqrt(9.6 / 90)
    assert round(se_cluster, 6) == round(expected_se, 6) == 0.326599
    assert detectable > 2.0 * iid_detectable
    assert (interval.high - interval.low) > 2.0 * (iid_interval.high - iid_interval.low)


def test_reanalysis_of_recorded_comparisons_with_cluster_intervals() -> None:
    # Fall A (M4 / #1008-Typ: 25 Seeds x 4 Sitze = 100 Paare, moderate Seed-Korrelation)
    def winner_fall_a(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
        if seed in (1, 2, 3) and seat in (1, 2):
            return (seat,) if contender_id == "variant" else (_other_seat(seat),)
        if seed in (4, 5) and seat in (1, 2):
            return (seat,) if contender_id == "base" else (_other_seat(seat),)
        return (_other_seat(seat),)

    spec_a = _spec(tuple(range(1, 26)), rotate=True)
    cases_a = plan_comparison_cases(spec_a)
    comp_a = aggregate_comparison(spec_a, _report(_records_for(cases_a, winner_fall_a)))
    paired_a = comp_a.paired[0]

    assert paired_a.pairs_completed == 100
    assert paired_a.seed_clusters_completed == 25
    assert paired_a.verdict == "NO_CLEAR_DIFFERENCE"
    assert paired_a.win_share_difference_interval_95 is not None
    assert paired_a.cluster_difference_interval_95 is not None
    assert paired_a.detectable_difference_80pct_power is not None
    assert paired_a.cluster_detectable_difference_80pct_power is not None

    width_iid_a = (
        paired_a.win_share_difference_interval_95.high
        - paired_a.win_share_difference_interval_95.low
    )
    width_cluster_a = (
        paired_a.cluster_difference_interval_95.high - paired_a.cluster_difference_interval_95.low
    )
    assert width_cluster_a > width_iid_a
    assert (
        paired_a.cluster_detectable_difference_80pct_power
        > paired_a.detectable_difference_80pct_power
    )

    # Fall B (Schein-Signifikanz: 8 Seeds x 4 Sitze = 32 Paare, 5 Seeds +1, 3 Seeds -1)
    def winner_fall_b(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
        if seed in (1, 2, 3, 4, 5):
            return (seat,) if contender_id == "variant" else (_other_seat(seat),)
        return (seat,) if contender_id == "base" else (_other_seat(seat),)

    spec_b = _spec(tuple(range(1, 9)), rotate=True)
    cases_b = plan_comparison_cases(spec_b)
    comp_b = aggregate_comparison(spec_b, _report(_records_for(cases_b, winner_fall_b)))
    paired_b = comp_b.paired[0]

    assert paired_b.pairs_completed == 32
    assert paired_b.seed_clusters_completed == 8
    assert paired_b.variant_only_wins == 20
    assert paired_b.baseline_only_wins == 12
    assert paired_b.verdict == "NO_CLEAR_DIFFERENCE"
    assert paired_b.underpowered is True
    assert paired_b.cluster_detectable_difference_80pct_power is not None
    assert paired_b.cluster_detectable_difference_80pct_power > 0.90


def test_power_table_anchors_and_monotonicity() -> None:
    table = fgc.power_table()
    assert len(table) == 9

    # Anker 1: diff=0.10, q=0.40
    row_010_040 = next(r for r in table if r.difference == 0.10 and r.discordant_share_q == 0.40)
    assert row_010_040.pair_sd == 0.63
    assert row_010_040.pairs_needed_iid == 312
    assert row_010_040.seeds_needed_4_seats_iid == 78
    assert row_010_040.seeds_needed_4_seats_rho_025 == 137

    # Anker 2: diff=0.05, q=0.40
    row_005_040 = next(r for r in table if r.difference == 0.05 and r.discordant_share_q == 0.40)
    assert row_005_040.pair_sd == 0.63
    assert row_005_040.pairs_needed_iid == 1247
    assert row_005_040.seeds_needed_4_seats_iid == 312
    assert row_005_040.seeds_needed_4_seats_rho_025 == 546

    # Anker 3: diff=0.10, q=0.09 (M4-Anker)
    row_010_009 = next(r for r in table if r.difference == 0.10 and r.discordant_share_q == 0.09)
    assert row_010_009.pair_sd == 0.30
    assert row_010_009.pairs_needed_iid == 71
    assert row_010_009.seeds_needed_4_seats_iid == 18

    # Cluster vs i.i.d. Verhältnis
    for row in table:
        assert row.seeds_needed_4_seats_rho_025 > row.seeds_needed_4_seats_iid

    # Monotonie über effect size
    for q in fgc.POWER_TABLE_DISCORDANT_SHARES:
        r_005 = next(r for r in table if r.difference == 0.05 and r.discordant_share_q == q)
        r_010 = next(r for r in table if r.difference == 0.10 and r.discordant_share_q == q)
        r_020 = next(r for r in table if r.difference == 0.20 and r.discordant_share_q == q)
        assert r_005.pairs_needed_iid > r_010.pairs_needed_iid > r_020.pairs_needed_iid
        assert (
            r_005.seeds_needed_4_seats_rho_025
            > r_010.seeds_needed_4_seats_rho_025
            > r_020.seeds_needed_4_seats_rho_025
        )

    # Monotonie über q
    for diff in fgc.POWER_TABLE_DIFFERENCES:
        r_009 = next(r for r in table if r.difference == diff and r.discordant_share_q == 0.09)
        r_020 = next(r for r in table if r.difference == diff and r.discordant_share_q == 0.20)
        r_040 = next(r for r in table if r.difference == diff and r.discordant_share_q == 0.40)
        assert r_040.pairs_needed_iid > r_020.pairs_needed_iid > r_009.pairs_needed_iid
        assert (
            r_040.seeds_needed_4_seats_rho_025
            > r_020.seeds_needed_4_seats_rho_025
            > r_009.seeds_needed_4_seats_rho_025
        )
