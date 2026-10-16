"""#832: sequential deck comparison with early stopping.

Pure unit tests (no JVM): scripted batch records drive the sequential look
loop, so the Bonferroni-split per-look threshold and the stop logic can be
checked by hand against the sign-test p-values.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Sequence
from pathlib import Path

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
    plan_comparison_cases,
    sequential_look_alpha,
    sequential_look_decided,
    sequential_looks_planned,
    sequential_stop_now,
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
        comparison_id="seq-test",
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


def _baseline_sweep(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
    return (seat,) if contender_id == "base" else (_other_seat(seat),)


def _alternating(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
    if (seed + seat) % 2 == 0:
        return _variant_sweep(contender_id, seed, seat)
    return _baseline_sweep(contender_id, seed, seat)


def _marginal(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
    """First look: 15 variant-won and 5 baseline-won pairs (p ~ 0.041).

    That p-value sits between alpha/4 = 0.0125 and alpha = 0.05, so the naive
    threshold would stop at the first look while the per-look threshold must
    not. Later seeds alternate, so the final verdict stays undecided.
    """
    if seed <= 5:
        if seat != 4:
            return _variant_sweep(contender_id, seed, seat)
        return _baseline_sweep(contender_id, seed, seat)
    return _alternating(contender_id, seed, seat)


class _ScriptedBlocks:
    """Fake batch runner: ``winner`` maps (contender_id, seed, seat) to winners."""

    def __init__(self, winner: WinnerFn) -> None:
        self.winner = winner
        self.blocks: list[tuple[int, ...]] = []

    def __call__(self, cases: tuple[FullGameBatchCase, ...]) -> FullGameBatchReport:
        self.blocks.append(tuple(dict.fromkeys(case.scenario.seed for case in cases)))
        return _report(_records_for(cases, self.winner))


def _script_module():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "scripts/run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("run_full_game_deck_comparison", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_threshold_helpers() -> None:
    assert sequential_looks_planned(20, 5) == 4
    assert sequential_looks_planned(21, 5) == 5
    assert sequential_looks_planned(3, 5) == 1
    assert sequential_look_alpha(0.05, 4) == pytest.approx(0.0125)
    assert sequential_look_alpha(0.05, 1) == pytest.approx(0.05)
    with pytest.raises(ValueError, match="significance_level"):
        sequential_look_alpha(0.0, 4)
    with pytest.raises(ValueError, match="looks_planned"):
        sequential_look_alpha(0.05, 0)
    with pytest.raises(ValueError, match="look_every"):
        sequential_looks_planned(10, 0)
    with pytest.raises(ValueError, match="seed_count"):
        sequential_looks_planned(0, 5)


def test_clear_win_stops_at_first_look() -> None:
    cli = _script_module()
    spec = _spec(tuple(range(1, 21)), rotate=True)
    cases = plan_comparison_cases(spec)
    blocks = _ScriptedBlocks(_variant_sweep)
    comparison, combined, sequential = cli.run_sequential_blocks(spec, cases, blocks, look_every=5)
    # 20 discordant pairs at the first look: p = 2/2^20 < 0.05/4.
    assert blocks.blocks == [(1, 2, 3, 4, 5)]
    assert combined.total_cases == 5 * 4 * 2
    assert comparison.seeds == (1, 2, 3, 4, 5)  # the look aggregates played seeds
    assert sequential == {
        "looks_planned": 4,
        "looks_used": 1,
        "per_look_alpha": pytest.approx(0.0125),
        "stopped_early": True,
        "seeds_played": 5,
    }
    paired = comparison.paired[0]
    assert paired.sign_test_p_value < 0.0125
    assert paired.verdict == "VARIANT_BETTER"
    assert sequential_look_decided(paired) is True
    assert sequential_stop_now(comparison.paired) is True


def test_fifty_fifty_never_stops_early() -> None:
    cli = _script_module()
    spec = _spec(tuple(range(1, 11)), rotate=False)
    cases = plan_comparison_cases(spec)
    blocks = _ScriptedBlocks(_alternating)
    comparison, combined, sequential = cli.run_sequential_blocks(spec, cases, blocks, look_every=5)
    assert blocks.blocks == [(1, 2, 3, 4, 5), (6, 7, 8, 9, 10)]
    assert combined.total_cases == 10 * 1 * 2
    assert sequential["looks_used"] == 2
    assert sequential["stopped_early"] is False
    assert sequential["seeds_played"] == 10
    paired = comparison.paired[0]
    assert paired.variant_only_wins == paired.baseline_only_wins == 5
    assert paired.verdict == "NO_CLEAR_DIFFERENCE"
    assert sequential_stop_now(comparison.paired) is False


def test_marginal_p_does_not_stop_early() -> None:
    cli = _script_module()
    spec = _spec(tuple(range(1, 21)), rotate=True)
    cases = plan_comparison_cases(spec)
    blocks = _ScriptedBlocks(_marginal)
    comparison, _combined, sequential = cli.run_sequential_blocks(spec, cases, blocks, look_every=5)
    assert sequential["looks_used"] == 4
    assert sequential["stopped_early"] is False
    assert sequential["seeds_played"] == 20
    assert comparison.paired[0].verdict == "NO_CLEAR_DIFFERENCE"
    # Wrong-reason control: the first look's p sits between alpha/4 and alpha.
    look1_spec = _spec(tuple(range(1, 6)), rotate=True)
    look1_cases = [case for case in plan_comparison_cases(look1_spec)]
    look1 = _report(_records_for(look1_cases, _marginal))
    naive = aggregate_comparison(look1_spec, look1)
    assert 0.0125 < naive.paired[0].sign_test_p_value < 0.05
    assert naive.paired[0].verdict == "VARIANT_BETTER"  # naive alpha would stop here
    strict = aggregate_comparison(
        look1_spec, look1, significance_level=sequential_look_alpha(0.05, 4)
    )
    assert strict.paired[0].verdict == "NO_CLEAR_DIFFERENCE"  # per-look alpha does not


def test_default_path_unchanged() -> None:
    # The default aggregation never applies the sequential threshold: the same
    # marginal first look still declares VARIANT_BETTER at alpha = 0.05.
    look1_spec = _spec(tuple(range(1, 6)), rotate=True)
    look1_cases = plan_comparison_cases(look1_spec)
    comparison = aggregate_comparison(look1_spec, _report(_records_for(look1_cases, _marginal)))
    assert comparison.significance_level == 0.05
    assert comparison.paired[0].verdict == "VARIANT_BETTER"


def test_blocks_follow_seed_order() -> None:
    cli = _script_module()
    spec = _spec((9, 3, 7), rotate=False)
    cases = plan_comparison_cases(spec)
    blocks = _ScriptedBlocks(_alternating)
    _, _, sequential = cli.run_sequential_blocks(spec, cases, blocks, look_every=2)
    assert blocks.blocks == [(9, 3), (7,)]
    assert sequential["looks_planned"] == 2
    assert sequential["seeds_played"] == 3


def test_summary_reports_seeds_played() -> None:
    cli = _script_module()
    payload = {
        "contenders": [],
        "paired": [],
        "seeds": [1, 2, 3, 4, 5],
        "sequential": {
            "looks_planned": 4,
            "looks_used": 1,
            "per_look_alpha": 0.0125,
            "stopped_early": True,
            "seeds_played": 5,
        },
    }
    assert cli._summary_lines(payload)[-1] == "stopped after 5 of 5 seeds"
    assert cli._summary_lines({"contenders": [], "paired": [], "seeds": [1]}) == []


def test_cli_accepts_sequential_options(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _script_module()
    root = Path(__file__).resolve().parents[2]
    code = cli.main(
        [
            "--baseline",
            str(root / "data/decks/rogshai_current.json"),
            "--variant",
            str(root / "data/decks/rogshai_current.json"),
            "--opponent",
            str(root / "data/decks/opponents/kaervek/current/deck.json"),
            "--opponent",
            str(root / "data/opponents/hosts_of_mordor_precon.json"),
            "--opponent",
            str(root / "data/opponents/lorehold_spirit_precon.json"),
            "--seeds",
            "1-3",
            "--out",
            "unused",
            "--workers",
            "2",
            "--stop-when-decided",
            "--look-every",
            "5",
            "--plan-only",
        ]
    )
    assert code == 0
    assert (
        "24 games: 2 contenders x 3 seeds x 4 seats, 4 players, 2 workers"
        in capsys.readouterr().out
    )
