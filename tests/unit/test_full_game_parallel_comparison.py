"""#731: parallel full-game batches and paired deck comparison.

The fake runners stand in for the bridge: they decide winners from the case
inputs alone, so a parallel run must give exactly the records a sequential run
gives, and the comparison statistics can be checked by hand.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FullGameConformanceResult,
    FullGameProtocolError,
)
from commander_lab.engine.rules.full_game_batch import XmageFullGameBatchRunner
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonSpec,
    aggregate_comparison,
    plan_comparison_cases,
    pod_decks,
    sign_test_p_value,
    wilson_interval,
)
from commander_lab.models import RulesDeckInput

XMAGE_COMMIT = "3cbf7741d29a2fe820725456b90f305f9f793ad1"


def _deck(deck_id: str, index: int) -> RulesDeckInput:
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=tuple("Plains" for _ in range(99)),
        deck_hash=(f"{index:x}" * 64)[:64],
    )


def _spec(seeds: tuple[int, ...] = (1, 2, 3), *, rotate: bool = True) -> DeckComparisonSpec:
    return DeckComparisonSpec(
        comparison_id="cmp-test",
        contenders=(_deck("base", 1), _deck("variant", 2)),
        opponents=(_deck("opp-a", 3), _deck("opp-b", 4), _deck("opp-c", 5)),
        seeds=seeds,
        rotate_seats=rotate,
        xmage_commit=XMAGE_COMMIT,
    )


def _result(scenario: FutureXmageScenario, winners: tuple[int, ...]) -> FullGameConformanceResult:
    return FullGameConformanceResult(
        scenario=scenario,
        engine_version="1.4.61",
        xmage_commit=XMAGE_COMMIT,
        decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
        decision_count=100 + scenario.seed,
        terminal=True,
        winner_seats=winners,
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


class _VariantWinsRunner:
    """The variant wins every game; the baseline wins only on even seeds.

    Seed 3 at seat 2 fails for the variant, so one pair is censored.
    """

    command = ("python", "-c", "pass")

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        # Counters live in one shared object: the batch hands every parallel
        # game its own shallow copy of the runner.
        self.stats = {"calls": 0, "active": 0, "peak": 0}
        self._lock = threading.Lock()
        self._current_case: str | None = None

    @property
    def calls(self) -> int:
        return self.stats["calls"]

    @property
    def peak(self) -> int:
        return self.stats["peak"]

    def run(self, *, scenario: FutureXmageScenario, decks: object, pilots: object) -> object:
        with self._lock:
            self.stats["calls"] += 1
            self.stats["active"] += 1
            self.stats["peak"] = max(self.stats["peak"], self.stats["active"])
        # Per-game state on the runner, like the real runner's hidden audit.
        self._current_case = f"{scenario.candidate_id}:{scenario.seed}:{scenario.seat}"
        mine = self._current_case
        try:
            if self.delay:
                time.sleep(self.delay)
            if self._current_case != mine:
                raise RuntimeError("per-game runner state leaked between games")
            if scenario.candidate_id == "variant" and scenario.seed == 3 and scenario.seat == 2:
                raise FullGameProtocolError("unsupported discretionary decision class: x")
            tested = scenario.seat
            other = 1 if tested != 1 else 2
            if scenario.candidate_id == "variant" or scenario.seed % 2 == 0:
                return _result(scenario, (tested,))
            return _result(scenario, (other,))
        finally:
            with self._lock:
                self.stats["active"] -= 1


def test_pod_rotation_keeps_opponent_order_and_seats_the_contender() -> None:
    spec = _spec()
    base = spec.contenders[0]
    ids = [[deck.deck_id for deck in pod_decks(base, spec.opponents, seat)] for seat in (1, 2, 4)]
    assert ids[0] == ["base", "opp-a", "opp-b", "opp-c"]
    assert ids[1] == ["opp-c", "base", "opp-a", "opp-b"]
    assert ids[2] == ["opp-a", "opp-b", "opp-c", "base"]


def test_plan_pairs_contenders_on_identical_pods() -> None:
    spec = _spec()
    cases = plan_comparison_cases(spec)
    assert len(cases) == len(spec.seeds) * 4 * 2
    for left, right in zip(cases[0::2], cases[1::2], strict=True):
        assert left.scenario.seed == right.scenario.seed
        assert left.scenario.seat == right.scenario.seat
        assert left.scenario.opponent_deck_ids == right.scenario.opponent_deck_ids
        seat = left.scenario.seat
        assert [d.deck_id for i, d in enumerate(left.decks, 1) if i != seat] == [
            d.deck_id for i, d in enumerate(right.decks, 1) if i != seat
        ]
        assert left.decks[seat - 1].deck_id == "base"
        assert right.decks[seat - 1].deck_id == "variant"
    assert len({case.case_id for case in cases}) == len(cases)


def test_spec_rejects_a_contender_that_is_also_an_opponent() -> None:
    with pytest.raises(ValueError, match="contender cannot also be an opponent"):
        DeckComparisonSpec(
            comparison_id="bad",
            contenders=(_deck("base", 1), _deck("opp-a", 2)),
            opponents=(_deck("opp-a", 3),),
            seeds=(1,),
            xmage_commit=XMAGE_COMMIT,
        )


def test_parallel_batch_equals_sequential_batch_in_case_order(tmp_path: Path) -> None:
    cases = plan_comparison_cases(_spec())
    sequential = XmageFullGameBatchRunner(_VariantWinsRunner(), tmp_path / "seq").run(cases)  # type: ignore[arg-type]
    runner = _VariantWinsRunner(delay=0.02)
    parallel = XmageFullGameBatchRunner(runner, tmp_path / "par").run(  # type: ignore[arg-type]
        cases, workers=4
    )
    assert runner.peak > 1, "workers=4 never ran two games at once"
    assert runner.peak <= 4
    assert [r.case_id for r in parallel.records] == [c.case_id for c in cases]
    strip = {"elapsed_seconds"}
    assert [r.model_dump(exclude=strip) for r in parallel.records] == [
        r.model_dump(exclude=strip) for r in sequential.records
    ]
    assert parallel.failed_cases == 1
    assert all(
        record.failure_class is None or record.failure_class.value == "protocol"
        for record in parallel.records
    ), "per-game runner state leaked between parallel games"


def test_parallel_batch_resumes_without_replaying_completed_games(tmp_path: Path) -> None:
    cases = plan_comparison_cases(_spec())
    first = _VariantWinsRunner()
    XmageFullGameBatchRunner(first, tmp_path).run(cases, workers=3)  # type: ignore[arg-type]
    again = _VariantWinsRunner()
    report = XmageFullGameBatchRunner(again, tmp_path).run(cases, workers=3)  # type: ignore[arg-type]
    assert again.calls == 0
    assert report.resumed_cases == report.completed_cases == len(cases) - 1
    retried = _VariantWinsRunner()
    XmageFullGameBatchRunner(retried, tmp_path).run(  # type: ignore[arg-type]
        cases, workers=3, retry_failed=True
    )
    assert retried.calls == 1


def test_parallel_batch_rejects_duplicate_cases(tmp_path: Path) -> None:
    cases = plan_comparison_cases(_spec(seeds=(1,), rotate=False))
    with pytest.raises(ValueError, match="distinct run keys"):
        XmageFullGameBatchRunner(_VariantWinsRunner(), tmp_path).run(  # type: ignore[arg-type]
            (cases[0], cases[0]), workers=2
        )


def test_invalid_worker_settings_fail_closed(tmp_path: Path) -> None:
    batch = XmageFullGameBatchRunner(_VariantWinsRunner(), tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="workers must be positive"):
        batch.run((), workers=0)
    with pytest.raises(ValueError, match="parallelism"):
        batch.run((), workers=2, parallelism="fork")  # type: ignore[arg-type]


def test_aggregate_censors_failures_and_pairs_by_pod(tmp_path: Path) -> None:
    spec = _spec()
    report = XmageFullGameBatchRunner(_VariantWinsRunner(), tmp_path).run(  # type: ignore[arg-type]
        plan_comparison_cases(spec), workers=2
    )
    comparison = aggregate_comparison(spec, report)
    base, variant = comparison.contenders
    assert base.games_planned == variant.games_planned == 12
    assert base.games_completed == 12 and base.games_failed == 0
    assert variant.games_completed == 11 and variant.games_failed == 1
    assert variant.failure_classes == {"protocol": 1}
    assert base.wins == 4  # seed 2 at all four seats
    assert variant.wins == 11
    assert base.mean_turns == pytest.approx(12.5)
    paired = comparison.paired[0]
    assert paired.pairs_completed == 11 and paired.pairs_censored == 1
    assert paired.variant_only_wins == 7 and paired.baseline_only_wins == 0
    assert paired.win_share_difference == pytest.approx(1 - 4 / 11)
    assert paired.verdict == "VARIANT_BETTER"
    assert comparison.official_campaign_eligible is False
    assert comparison.evidence_class == "exploratory_xmage_full_game"


def test_heavily_censored_comparison_gets_no_verdict(tmp_path: Path) -> None:
    # One of the twelve pods is censored (seed 3, seat 2): fine under the
    # default 20% cap, too many under a 5% cap.
    spec = _spec(seeds=(1, 2, 3), rotate=True)
    report = XmageFullGameBatchRunner(_VariantWinsRunner(), tmp_path).run(  # type: ignore[arg-type]
        plan_comparison_cases(spec), workers=2
    )
    assert aggregate_comparison(spec, report).paired[0].verdict == "VARIANT_BETTER"
    strict = aggregate_comparison(spec, report, max_censored_fraction=0.05)
    assert strict.paired[0].verdict == "INSUFFICIENT"
    assert strict.paired[0].pairs_censored == 1


def test_aggregate_without_completed_pairs_is_insufficient(tmp_path: Path) -> None:
    spec = _spec(seeds=(3,), rotate=False)
    comparison = aggregate_comparison(
        spec, XmageFullGameBatchRunner(_VariantWinsRunner(), tmp_path).run(())
    )  # type: ignore[arg-type]
    assert comparison.paired[0].verdict == "INSUFFICIENT"
    assert comparison.contenders[0].win_share is None


def test_statistics_helpers() -> None:
    assert sign_test_p_value(0, 0) == 1.0
    assert sign_test_p_value(7, 0) == pytest.approx(2 / 128)
    assert sign_test_p_value(3, 3) == 1.0
    interval = wilson_interval(5, 10)
    assert interval.low == pytest.approx(0.2366, abs=1e-3)
    assert interval.high == pytest.approx(0.7634, abs=1e-3)
    assert wilson_interval(0, 0).model_dump() == {"low": 0.0, "high": 1.0}


def _cli():  # type: ignore[no-untyped-def]
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts/run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("run_full_game_deck_comparison", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_seed_parsing_and_worker_default() -> None:
    cli = _cli()
    assert cli.parse_seeds("1-3,7") == (1, 2, 3, 7)
    with pytest.raises(ValueError):
        cli.parse_seeds("5-1")
    assert cli.default_workers(cpu_count=4, memory_gb=15.0) == 2
    assert cli.default_workers(cpu_count=16, memory_gb=5.0) == 2
    assert cli.default_workers(cpu_count=1, memory_gb=1.0) == 1


def test_cli_plan_only_on_the_real_decks(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _cli()
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
            "--plan-only",
        ]
    )
    assert code == 0
    assert (
        "24 games: 2 contenders x 3 seeds x 4 seats, 4 players, 2 workers"
        in capsys.readouterr().out
    )
