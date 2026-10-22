"""#877 step 3: several games per bridge JVM in the batch runner, opt-in, default one.

The evidence lanes keep one game per process and their report byte for byte. A batched
run is a separate branch with its own report type that does not claim process isolation.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGameProtocolError,
)
from commander_lab.engine.rules.full_game_batch import (
    GAMES_PER_JVM_PROPERTY,
    FullGameBatchCase,
    FullGameBatchReport,
    FullGameBatchReportBatched,
    FullGameFailureClass,
    XmageFullGameBatchRunner,
    command_with_games_per_jvm,
    execute_batch_case,
    execution_identity_of,
)
from tests.unit.test_xmage_full_game import _binding, _decks, _result, _scenario

ROOT = Path(__file__).resolve().parents[2]


class _FakeRunner:
    """Plays instantly. ``outcomes`` maps a seed to an exception that run_batch returns for it."""

    def __init__(self, jar: Path, games_per_jvm: int = 1) -> None:
        self.command = command_with_games_per_jvm(
            ("java", "-jar", str(jar), "full-game"), games_per_jvm
        )
        self.outcomes: dict[int, Exception] = {}
        self.run_calls: list[int] = []
        self.chunks: list[list[int]] = []

    def run(self, *, scenario: Any, decks: Any, pilots: Any) -> FullGameConformanceResult:
        self.run_calls.append(scenario.seed)
        return _result(scenario)

    def run_batch(self, games: Any) -> list[FullGameConformanceResult | Exception]:
        self.chunks.append([scenario.seed for scenario, _decks_, _pilots in games])
        return [self.outcomes.get(s.seed) or _result(s) for s, _d, _p in games]


class _PlainRunner:
    """A runner as the evidence lanes use it: no run_batch."""

    def __init__(self, jar: Path) -> None:
        self.command = ("java", "-jar", str(jar), "full-game")
        self.run_calls: list[int] = []

    def run(self, *, scenario: Any, decks: Any, pilots: Any) -> FullGameConformanceResult:
        self.run_calls.append(scenario.seed)
        return _result(scenario)


def _jar(tmp_path: Path) -> Path:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"build-1")
    return jar


def _cases(*seeds: int) -> tuple[FullGameBatchCase, ...]:
    decks = _decks()
    return tuple(
        FullGameBatchCase(
            case_id=f"seed-{seed}",
            scenario=_scenario(decks).model_copy(update={"seed": seed}),
            decks=decks,
            pilots=tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 5)),  # type: ignore[arg-type]
        )
        for seed in seeds
    )


def _batch(runner: Any, tmp_path: Path, n: int) -> XmageFullGameBatchRunner:
    return XmageFullGameBatchRunner(runner, tmp_path / "out", games_per_jvm=n)


def test_the_default_is_one_game_per_jvm_and_the_evidence_report_is_unchanged(
    tmp_path: Path,
) -> None:
    runner = _PlainRunner(_jar(tmp_path))
    report = XmageFullGameBatchRunner(runner, tmp_path / "out").run(_cases(1, 2, 3))  # type: ignore[arg-type]
    assert type(report) is FullGameBatchReport
    assert report.schema_version == "xmage-full-game-batch-report-1.0.0"
    assert report.one_isolated_jvm_per_executed_game is True
    assert "games_per_jvm" not in report.model_dump()
    assert runner.run_calls == [1, 2, 3]


def test_the_evidence_report_keeps_exactly_its_fields() -> None:
    assert set(FullGameBatchReport.model_fields) == {
        "schema_version",
        "total_cases",
        "completed_cases",
        "failed_cases",
        "resumed_cases",
        "records",
        "evidence_class",
        "one_isolated_jvm_per_executed_game",
        "claim_basis",
        "idempotent_completed_run_reuse",
        "failed_runs_retry_only_when_requested",
        "consumed_gameplay_evidence",
        "holdout_consumed",
        "official_campaign_eligible",
        "canonical_data_mutated",
    }
    assert FullGameBatchReport.model_fields["one_isolated_jvm_per_executed_game"].default is True


def test_n_games_share_a_jvm_and_the_report_says_so(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=3)
    report = _batch(runner, tmp_path, 3).run(_cases(1, 2, 3, 4, 5, 6, 7))
    assert runner.chunks == [[1, 2, 3], [4, 5, 6], [7]]
    assert runner.run_calls == []
    assert isinstance(report, FullGameBatchReportBatched)
    assert report.games_per_jvm == 3
    assert report.one_isolated_jvm_per_executed_game is False
    assert report.state_isolation_basis == "SHUTDOWN_GAME_ONLY_NOT_A_PROCESS_BOUNDARY"
    assert report.schema_version == "xmage-full-game-batch-report-games-per-jvm-1.0.0"
    assert [r.case_id for r in report.records] == [f"seed-{s}" for s in range(1, 8)]
    assert report.completed_cases == 7
    assert all(r.elapsed_seconds >= 0 for r in report.records)


def test_a_batched_report_survives_a_json_round_trip(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=2)
    report = _batch(runner, tmp_path, 2).run(_cases(1, 2))
    again = FullGameBatchReportBatched.model_validate_json(report.model_dump_json())
    assert again == report


def test_chunks_run_in_parallel_workers_and_keep_the_case_order(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=2)
    report = _batch(runner, tmp_path, 2).run(_cases(1, 2, 3, 4, 5), workers=2)
    assert sorted(len(chunk) for chunk in runner.chunks) == [1, 2, 2]
    assert [r.case_id for r in report.records] == [f"seed-{s}" for s in range(1, 6)]
    assert report.completed_cases == 5


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (FullGameProtocolError("boom", code="BRIDGE_EXITED"), FullGameFailureClass.PROTOCOL),
        (FullGameConformanceError("boom"), FullGameFailureClass.CONFORMANCE),
        (OSError("boom"), FullGameFailureClass.CONFIGURATION),
        (ValueError("boom"), FullGameFailureClass.CONFIGURATION),
        (RuntimeError("boom"), FullGameFailureClass.ENGINE),
    ],
)
def test_a_failed_game_in_a_chunk_is_classified_like_a_single_game(
    tmp_path: Path, exception: Exception, expected: FullGameFailureClass
) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=3)
    runner.outcomes[2] = exception
    report = _batch(runner, tmp_path, 3).run(_cases(1, 2, 3))
    assert [r.status for r in report.records] == ["completed", "failed", "completed"]
    assert report.records[1].failure_class == expected

    class _Raising(_PlainRunner):
        def run(self, *, scenario: Any, decks: Any, pilots: Any) -> FullGameConformanceResult:
            raise exception

    single = execute_batch_case(
        _Raising(_jar(tmp_path)),  # type: ignore[arg-type]
        _cases(2)[0],
        report.records[1].run_key,
        execution_identity_of(_Raising(_jar(tmp_path))),
    )
    assert single.failure_class == report.records[1].failure_class


def test_a_defect_of_the_lab_in_a_chunk_propagates(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=2)
    runner.outcomes[2] = KeyError("a bug, not a game failure")
    with pytest.raises(KeyError):
        _batch(runner, tmp_path, 2).run(_cases(1, 2))


def test_a_startup_collision_is_retried_one_game_at_a_time(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=2)
    runner.outcomes[2] = FullGameProtocolError(
        "collision", code="BRIDGE_EXITED", diagnostics=("XMAGE_CARD_REPOSITORY_INIT_FAILED",)
    )
    report = _batch(runner, tmp_path, 2).run(_cases(1, 2))
    assert runner.run_calls == [2]
    assert [r.status for r in report.records] == ["completed", "completed"]


def test_resume_chunks_only_the_cases_that_are_still_open(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=2)
    _batch(runner, tmp_path, 2).run(_cases(1, 2, 3, 4))
    runner.chunks.clear()
    report = _batch(runner, tmp_path, 2).run(_cases(1, 2, 3, 4, 5, 6))
    assert runner.chunks == [[5, 6]]
    assert report.resumed_cases == 4
    assert report.completed_cases == 6


def test_a_batched_run_never_reuses_a_one_game_record(tmp_path: Path) -> None:
    jar = _jar(tmp_path)
    plain = _PlainRunner(jar)
    XmageFullGameBatchRunner(plain, tmp_path / "out").run(_cases(1, 2))  # type: ignore[arg-type]
    runner = _FakeRunner(jar, games_per_jvm=2)
    report = _batch(runner, tmp_path, 2).run(_cases(1, 2))
    assert report.resumed_cases == 0
    assert runner.chunks == [[1, 2]]


def test_the_property_is_part_of_the_execution_identity(tmp_path: Path) -> None:
    jar = _jar(tmp_path)
    one = execution_identity_of(_FakeRunner(jar, 1))["runner_configuration_sha256"]
    two = execution_identity_of(_FakeRunner(jar, 2))["runner_configuration_sha256"]
    four = execution_identity_of(_FakeRunner(jar, 4))["runner_configuration_sha256"]
    assert len({one, two, four}) == 3


def test_the_command_helper_puts_the_property_after_the_executable() -> None:
    base = ("java", "-Xmx4g", "-jar", "bridge.jar", "full-game")
    batched = command_with_games_per_jvm(base, 4)
    assert batched[:2] == ("java", f"-D{GAMES_PER_JVM_PROPERTY}=4")
    assert batched[2:] == base[1:]
    assert command_with_games_per_jvm(batched, 2).count(f"-D{GAMES_PER_JVM_PROPERTY}=2") == 1
    assert command_with_games_per_jvm(batched, 1) == base
    with pytest.raises(ValueError):
        command_with_games_per_jvm(base, 0)
    with pytest.raises(ValueError):
        command_with_games_per_jvm((), 2)


def test_a_runner_that_cannot_play_several_games_is_refused(tmp_path: Path) -> None:
    jar = _jar(tmp_path)
    with pytest.raises(ValueError, match="start the bridge"):
        _batch(_FakeRunner(jar, games_per_jvm=1), tmp_path, 3)  # bridge would stop after one game
    with pytest.raises(ValueError, match="start the bridge"):
        _batch(_FakeRunner(jar, games_per_jvm=2), tmp_path, 3)
    with pytest.raises(ValueError, match="run_batch"):
        XmageFullGameBatchRunner(_PlainRunner(jar), tmp_path, games_per_jvm=2)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive"):
        XmageFullGameBatchRunner(_PlainRunner(jar), tmp_path, games_per_jvm=0)  # type: ignore[arg-type]
    # a bridge that permits more than the batch asks for is fine
    _batch(_FakeRunner(jar, games_per_jvm=4), tmp_path, 3)


#: Files that may set up or drive a batched run.
_BATCH_CALLERS = {
    "scripts/run_full_game_deck_comparison.py",  # the only user of the batch runner's option
    "scripts/run_collection_coverage_games.py",  # its own sweep, straight on run_batch
    "scripts/pilot_decision_report.py",  # measurement, straight on run_batch
    "scripts/benchmark_xmage_full_games.py",  # speed benchmark and its pod sweep, on run_batch
    "scripts/precon_pod_sweep.py",  # pod sweep, plays chunks through the benchmark's batch
    "scripts/check_batch_failure_isolation.py",  # measurement check of a failing batch game
    "scripts/qualify_game_batching.py",  # the qualification of batched play itself
    "src/commander_lab/engine/rules/full_game_batch.py",
    "src/commander_lab/engine/rules/full_game.py",
}


def _files_using_batched_play() -> set[str]:
    """Files under scripts/ and src/ that can start games in a shared JVM.

    Any keyword or attribute named ``games_per_jvm``, any reference to ``run_batch`` or
    ``execute_batch_chunk``, and any ``XmageFullGameBatchRunner(...)`` call that takes ``**``
    keywords (which could carry the option unseen).
    """
    watched = {"games_per_jvm", "run_batch", "execute_batch_chunk"}
    found: set[str] = set()
    for folder in ("scripts", "src"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                name = ""
                if isinstance(node, ast.keyword):
                    name = node.arg or ""
                elif isinstance(node, ast.Attribute):
                    name = node.attr
                elif isinstance(node, ast.Name):
                    name = node.id
                elif isinstance(node, ast.alias):
                    name = node.name
                if name in watched:
                    found.add(rel)
                if (
                    isinstance(node, ast.Call)
                    and getattr(node.func, "id", getattr(node.func, "attr", ""))
                    == "XmageFullGameBatchRunner"
                    and any(kw.arg is None for kw in node.keywords)
                ):
                    found.add(rel)
    return found


def test_only_known_files_can_batch_games() -> None:
    """The evidence and gate lanes keep one game per process (Owner decision 2026-10-15)."""
    users = _files_using_batched_play()
    assert users - _BATCH_CALLERS == set(), users - _BATCH_CALLERS
    for gate in ("run_real_deck_gate.py", "run_optimizer_v2_full_game_route.py"):
        assert "XmageFullGameBatchRunner(" in (ROOT / "scripts" / gate).read_text(encoding="utf-8")
        assert f"scripts/{gate}" not in users


# --- the deck comparison script -------------------------------------------------------------


def test_sequential_blocks_keep_the_batched_report_type() -> None:
    from tests.unit.test_sequential_deck_comparison import (
        _alternating,
        _records_for,
        _script_module,
        _spec,
    )

    cli = _script_module()
    spec = _spec((1, 2, 3), rotate=False)
    from commander_lab.engine.rules.full_game_comparison import plan_comparison_cases

    cases = plan_comparison_cases(spec)

    def batched_block(block: tuple[FullGameBatchCase, ...]) -> FullGameBatchReport:
        records = _records_for(block, _alternating)
        return FullGameBatchReportBatched(
            total_cases=len(records),
            completed_cases=len(records),
            failed_cases=0,
            resumed_cases=0,
            records=tuple(records),
            games_per_jvm=4,
        )

    def plain_block(block: tuple[FullGameBatchCase, ...]) -> FullGameBatchReport:
        records = _records_for(block, _alternating)
        return FullGameBatchReport(
            total_cases=len(records),
            completed_cases=len(records),
            failed_cases=0,
            resumed_cases=0,
            records=tuple(records),
        )

    _, combined, _ = cli.run_sequential_blocks(spec, cases, batched_block, look_every=2)
    assert isinstance(combined, FullGameBatchReportBatched)
    assert combined.games_per_jvm == 4
    _, plain, _ = cli.run_sequential_blocks(spec, cases, plain_block, look_every=2)
    assert type(plain) is FullGameBatchReport


def test_the_cli_refuses_a_non_positive_games_per_jvm() -> None:
    from tests.unit.test_sequential_deck_comparison import _script_module

    cli = _script_module()
    with pytest.raises(SystemExit) as stopped:
        cli.main(
            [
                "--baseline",
                "x",
                "--swap",
                "a=>b",
                "--opponent",
                "y",
                "--seeds",
                "1",
                "--out",
                "z",
                "--games-per-jvm",
                "0",
            ]
        )
    assert stopped.value.code == 2


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: list[str],
    env_command: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], list[tuple[str, ...]]]:
    """Run main() against a fake bridge; returns COMPARISON_REPORT.json and the commands used."""
    import json

    from tests.unit.test_sequential_deck_comparison import _conformance, _script_module

    cli = _script_module()
    commands: list[tuple[str, ...]] = []
    jar = _jar(tmp_path)

    class _ComparisonRunner:
        def __init__(
            self,
            command: tuple[str, ...],
            max_decisions: int = 0,
            request_timeout_seconds: float = 0.0,
        ) -> None:
            commands.append(command)
            self.command = command
            self.max_decisions = max_decisions
            self.request_timeout_seconds = request_timeout_seconds

        @staticmethod
        def command_from_environment() -> tuple[str, ...]:
            return env_command or ("java", "-jar", str(jar), "full-game")

        def run(self, *, scenario: Any, decks: Any, pilots: Any) -> FullGameConformanceResult:
            return _conformance(scenario, (1,))

        def run_batch(self, games: Any) -> list[FullGameConformanceResult | Exception]:
            return [_conformance(s, (1,)) for s, _d, _p in games]

    monkeypatch.setattr(cli, "XmageFullGameRunner", _ComparisonRunner)
    root = ROOT
    out = tmp_path / "cmp"
    code = cli.main(
        [
            "--baseline", str(root / "data/decks/rogshai_current.json"),
            "--swap", "Mana Geyser=>Mind Stone",
            "--opponent", str(root / "data/decks/opponents/kaervek/current/deck.json"),
            "--opponent", str(root / "data/opponents/hosts_of_mordor_precon.json"),
            "--opponent", str(root / "data/opponents/lorehold_spirit_precon.json"),
            "--seeds", "1-2", "--no-rotate", "--workers", "1", "--out", str(out), *extra,
        ]
    )  # fmt: skip
    assert code == 0
    return json.loads((out / "COMPARISON_REPORT.json").read_text(encoding="utf-8")), commands


def test_the_cli_batches_when_asked_and_says_so_in_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, commands = _run_cli(tmp_path, monkeypatch, ["--games-per-jvm", "2"])
    assert commands[0][1] == f"-D{GAMES_PER_JVM_PROPERTY}=2"
    assert payload["batch"]["games_per_jvm"] == 2
    assert payload["batch"]["one_isolated_jvm_per_executed_game"] is False
    assert payload["batch"]["state_isolation_basis"] == "SHUTDOWN_GAME_ONLY_NOT_A_PROCESS_BOUNDARY"
    assert payload["batch"]["completed_cases"] == 4


def test_the_cli_report_is_unchanged_without_the_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, commands = _run_cli(tmp_path, monkeypatch, [])
    assert not any(GAMES_PER_JVM_PROPERTY in part for part in commands[0])
    assert set(payload["batch"]) == {
        "total_cases",
        "completed_cases",
        "failed_cases",
        "resumed_cases",
        "workers",
        "parallelism",
    }


def test_a_default_run_never_resumes_batched_records_even_if_the_env_command_has_the_property(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The bridge command of the environment already carries the property. A batched run and
    # an ordinary run must still get different run keys, or the ordinary run would resume
    # the batched records and report them as one isolated JVM per game.
    env = ("java", f"-D{GAMES_PER_JVM_PROPERTY}=4", "-jar", str(_jar(tmp_path)), "full-game")
    batched, _ = _run_cli(tmp_path, monkeypatch, ["--games-per-jvm", "4"], env_command=env)
    assert batched["batch"]["completed_cases"] == 4
    ordinary, commands = _run_cli(tmp_path, monkeypatch, [], env_command=env)
    assert ordinary["batch"]["resumed_cases"] == 0
    assert ordinary["batch"]["completed_cases"] == 4
    assert "games_per_jvm" not in ordinary["batch"]
    assert not any(GAMES_PER_JVM_PROPERTY in part for part in commands[0])


def test_a_one_game_runner_refuses_a_command_that_still_has_the_property(tmp_path: Path) -> None:
    runner = _FakeRunner(_jar(tmp_path), games_per_jvm=4)
    with pytest.raises(ValueError, match="one game per JVM"):
        XmageFullGameBatchRunner(runner, tmp_path / "out")  # type: ignore[arg-type]
    # batched is fine, and so is a command without the property
    _batch(runner, tmp_path, 4)
    XmageFullGameBatchRunner(_PlainRunner(_jar(tmp_path)), tmp_path / "out")  # type: ignore[arg-type]


class _RaisingBatchRunner(_FakeRunner):
    """run_batch raises as a whole, as it does when a replacement bridge process cannot start."""

    def run_batch(self, games: Any) -> list[FullGameConformanceResult | Exception]:
        raise FullGameProtocolError("BRIDGE_START_FAILED: no process")


def test_a_chunk_that_raises_as_a_whole_fails_every_case_of_the_chunk(tmp_path: Path) -> None:
    runner = _RaisingBatchRunner(_jar(tmp_path), games_per_jvm=3)
    report = _batch(runner, tmp_path, 3).run(_cases(1, 2, 3, 4))
    assert report.failed_cases == 4
    assert report.completed_cases == 0
    assert {r.failure_class for r in report.records} == {FullGameFailureClass.PROTOCOL}


class _ShortBatchRunner(_FakeRunner):
    def run_batch(self, games: Any) -> list[FullGameConformanceResult | Exception]:
        return super().run_batch(games)[:-1]


def test_a_chunk_that_loses_an_outcome_is_an_error_not_a_silent_gap(tmp_path: Path) -> None:
    runner = _ShortBatchRunner(_jar(tmp_path), games_per_jvm=3)
    with pytest.raises(RuntimeError, match="lost an outcome"):
        _batch(runner, tmp_path, 3).run(_cases(1, 2, 3))
