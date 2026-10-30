"""The benchmark launches the bridge by an absolute jar path.

With ``--private-card-repository`` every bridge JVM starts in its own scratch
directory; a relative ``--jar`` then no longer resolved and every game ended at
once with BRIDGE_EXITED.
"""

from __future__ import annotations

import importlib.util
import json
import os
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_xmage_full_games", ROOT / "scripts/benchmark_xmage_full_games.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_relative_jar_is_launched_by_its_absolute_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    command = _module().bridge_command(Path("bridge.jar"), ["-Xmx2g"])
    assert command == ("java", "-Xmx2g", "-jar", str(tmp_path / "bridge.jar"), "full-game")
    assert os.path.isabs(command[3])


def _report(path: Path, games: list[tuple[str, int, str, str | None]]) -> Path:
    rows = [
        {"pod": pod, "seed": seed, "status": status, "semantic": semantic}
        | {"wall_s": 10.0, "child_cpu_s": 20.0}
        for pod, seed, status, semantic in games
    ]
    path.write_text(json.dumps({"games": rows}), encoding="utf-8")
    return path


def _compare(tmp_path: Path, a: list, b: list) -> int:
    return _module().main(
        ["compare", str(_report(tmp_path / "a.json", a)), str(_report(tmp_path / "b.json", b))]
    )


def test_compare_passes_when_every_game_is_identical(tmp_path: Path, capsys) -> None:
    games = [("p1", 1, "ok", "s1"), ("p1", 2, "ok", "s2")]
    assert _compare(tmp_path, games, games) == 0
    assert "identical 2/2" in capsys.readouterr().out


def test_compare_fails_on_a_different_transcript(tmp_path: Path, capsys) -> None:
    a = [("p1", 1, "ok", "s1"), ("p1", 2, "ok", "s2")]
    b = [("p1", 1, "ok", "s1"), ("p1", 2, "ok", "XX")]
    assert _compare(tmp_path, a, b) == 1
    out = capsys.readouterr().out
    assert "identical 1/2" in out and "DIFFERENT ('p1', 2)" in out


def test_compare_fails_when_a_status_changes(tmp_path: Path) -> None:
    a = [("p1", 1, "ok", "s1")]
    b = [("p1", 1, "failed", None)]
    assert _compare(tmp_path, a, b) == 1


def test_compare_fails_when_a_game_is_missing_on_either_side(tmp_path: Path) -> None:
    a = [("p1", 1, "ok", "s1"), ("p1", 2, "ok", "s2")]
    assert _compare(tmp_path, a, a[:1]) == 1
    assert _compare(tmp_path, a[:1], a) == 1


def test_two_failed_games_are_not_identical(tmp_path: Path) -> None:
    games = [("p1", 1, "failed", None)]
    assert _compare(tmp_path, games, games) == 1


def test_compare_names_games_present_in_only_one_file(tmp_path: Path, capsys) -> None:
    a = [("p1", 1, "ok", "s1"), ("p1", 2, "ok", "s2")]
    assert _compare(tmp_path, a, a[:1]) == 1
    assert "MISSING 1 game(s)" in capsys.readouterr().out


class _Outcome:
    def __init__(self, semantic: str, decisions: int, winners: tuple[int, ...]) -> None:
        self.semantic_transcript_sha256 = semantic
        self.decision_count = decisions
        self.winner_seats = winners


def test_a_batch_is_played_in_one_runner_and_keeps_every_game_in_its_row(monkeypatch) -> None:
    module = _module()
    played: list[list[int]] = []

    class FakeRunner:
        def __init__(self, command, *, private_card_repository):
            assert command == ("java", "-jar", "x.jar", "full-game")
            assert private_card_repository is True

        def run_batch(self, games):
            played.append([scenario.seed for scenario, _, _ in games])
            return [
                _Outcome(f"s{scenario.seed}", 100 + scenario.seed, (1,)) for scenario, _, _ in games
            ]

    class Scenario:
        def __init__(self, seed=0):
            self.seed = seed

        def model_copy(self, update):
            return Scenario(update["seed"])

    monkeypatch.setattr(module, "XmageFullGameRunner", FakeRunner)
    setup = (Scenario(), "decks", "pilots")
    rows = module._play_batch(
        ("java", "-jar", "x.jar", "full-game"),
        [("real", setup, 1), ("real", setup, 2), ("real", setup, 3)],
        True,
    )
    assert played == [[1, 2, 3]]
    assert [(row["seed"], row["semantic"], row["decisions"]) for row in rows] == [
        (1, "s1", 101),
        (2, "s2", 102),
        (3, "s3", 103),
    ]
    assert {row["batched"] for row in rows} == {3}
    assert len({(row["wall_s"], row["child_cpu_s"]) for row in rows}) == 1


def test_a_failed_game_in_a_batch_is_a_failed_row_not_an_identical_one(monkeypatch) -> None:
    module = _module()

    class FakeRunner:
        def __init__(self, command, *, private_card_repository):
            pass

        def run_batch(self, games):
            return [_Outcome("s1", 1, (1,)), RuntimeError("DECISION_ADVANCE_TIMEOUT")]

    class Scenario:
        seed = 0

        def model_copy(self, update):
            return self

    monkeypatch.setattr(module, "XmageFullGameRunner", FakeRunner)
    setup = (Scenario(), "decks", "pilots")
    rows = module._play_batch(("java",), [("real", setup, 1), ("real", setup, 2)], False)
    assert [row["status"] for row in rows] == ["ok", "failed"]
    assert "DECISION_ADVANCE_TIMEOUT" in rows[1]["error"]
    assert "semantic" not in rows[1]


def test_a_batch_that_raises_marks_every_game_failed(monkeypatch) -> None:
    module = _module()

    class FakeRunner:
        def __init__(self, command, *, private_card_repository):
            pass

        def run_batch(self, games):
            raise OSError("no java")

    class Scenario:
        seed = 0

        def model_copy(self, update):
            return self

    monkeypatch.setattr(module, "XmageFullGameRunner", FakeRunner)
    setup = (Scenario(), "decks", "pilots")
    rows = module._play_batch(("java",), [("real", setup, 1), ("real", setup, 2)], False)
    assert [row["status"] for row in rows] == ["failed", "failed"]


def test_compare_reads_pod_sweep_files_too(tmp_path: Path, capsys) -> None:
    def sweep(path: Path, rows: list[tuple[str, str]]) -> Path:
        body = {
            "game_seed": 1,
            "rows": [
                {
                    "pod": pod,
                    "status": "ok",
                    "semantic": semantic,
                    "wall_s": 5.0,
                    "child_cpu_s": 9.0,
                }
                for pod, semantic in rows
            ],
        }
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    a = sweep(tmp_path / "a.json", [("pod-000", "h0"), ("pod-001", "h1")])
    same = sweep(tmp_path / "b.json", [("pod-000", "h0"), ("pod-001", "h1")])
    other = sweep(tmp_path / "c.json", [("pod-000", "h0"), ("pod-001", "XX")])
    assert _module().main(["compare", str(a), str(same)]) == 0
    assert _module().main(["compare", str(a), str(other)]) == 1
    assert "DIFFERENT ('pod-001', 1)" in capsys.readouterr().out


def test_fast_options_use_the_jars_cds_archive_only_when_it_exists(tmp_path: Path) -> None:
    module = _module()
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"")
    assert module.fast_jvm_options(jar) == ["-XX:+UseSerialGC"]
    (tmp_path / "bridge.jsa").write_bytes(b"")
    options = module.fast_jvm_options(jar)
    assert options[0] == "-XX:+UseSerialGC"
    assert f"-XX:SharedArchiveFile={tmp_path / 'bridge.jsa'}" in options
    # the JVM's own warnings must never reach the protocol on stdout
    assert options[1:3] == ["-Xlog:disable", "-Xlog:all=warning:stderr"]


def test_failure_isolation_check_reads_only_ok_games_of_a_reference(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "check_batch_failure_isolation", ROOT / "scripts/check_batch_failure_isolation.py"
    )
    assert spec is not None and spec.loader is not None
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    report = _report(tmp_path / "ref.json", [("real", 1, "ok", "s1"), ("real", 2, "failed", None)])
    assert check.reference_hashes(report) == {1: "s1"}
    # the broken game of each plan is a different seed from the good ones it sits between
    for plan in check.PLANS.values():
        assert len({seed for seed, _ in plan}) == len(plan)
        assert any(bad for _, bad in plan) and not all(bad for _, bad in plan)


def test_parse_reference_metadata_reads_commit_and_pin() -> None:
    module = _module()
    meta = module.parse_reference_metadata(module.REFERENCE_DOC)
    assert meta == {"lab_commit": "6db6934f5", "xmage_pin": "2ec507b721"}


def test_parse_reference_metadata_fails_closed_without_commit_row(tmp_path: Path) -> None:
    module = _module()
    doc = tmp_path / "ref.md"
    doc.write_text(
        "| XMage pin | `90f5c4d3f8` (`config/rules_engines.json`, v13) |\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing required"):
        module.parse_reference_metadata(doc)


def test_reference_is_current_at_its_own_commit() -> None:
    module = _module()
    res = module.check_reference_staleness(target_ref="5d85d2dc4")
    assert res["stale"] is False
    assert res["changed_files"] == ()
    assert res["pin_matches"] is True
    assert "current at 5d85d2dc4" in str(res["message"])


def _old_reference_doc(tmp_path: Path) -> Path:
    """A note at the commit of the 2026-10-26 reference (before the pilot steps of #1041/#1044)."""
    doc = tmp_path / "old_reference.md"
    doc.write_text(
        "| Lab commit | `b528082d5` (main after #1023) |\n"
        "| XMage pin | `90f5c4d3f8` (`config/rules_engines.json`, v13) |\n",
        encoding="utf-8",
    )
    return doc


def test_reference_is_stale_after_pilot_changes(tmp_path: Path) -> None:
    module = _module()
    res = module.check_reference_staleness(
        doc_path=_old_reference_doc(tmp_path), target_ref="a8d6e54a5"
    )
    assert res["stale"] is True
    assert res["changed_files"] == (
        "src/commander_lab/engine/rules/full_game_pilot/choices.py",
        "src/commander_lab/engine/rules/full_game_pilot/payment.py",
        "src/commander_lab/engine/rules/full_game_pilot/priority.py",
        "src/commander_lab/engine/rules/full_game_pilot/state.py",
        # Sibling modules: the first version of the watcher did not see them (#1035 review).
        "src/commander_lab/engine/rules/full_game_pilot_mana_hold.py",
        "src/commander_lab/engine/rules/full_game_pilot_target_discount.py",
    )
    assert "stale" in str(res["message"])


def test_reference_staleness_at_head_is_reported_not_enforced() -> None:
    """A stale reference is a warning, not a failure: pilot work is allowed to outrun the note."""
    module = _module()
    try:
        res = module.check_reference_staleness(target_ref="HEAD")
    except RuntimeError as exc:  # a shallow checkout does not hold the reference commit
        pytest.skip(f"reference commit not available in this checkout: {exc}")
    if res["stale"]:
        warnings.warn(str(res["message"]), stacklevel=1)


def test_unknown_reference_commit_fails_closed(tmp_path: Path) -> None:
    module = _module()
    doc = tmp_path / "ref.md"
    doc.write_text(
        "| Lab commit | `deadbeef0` (unknown) |\n"
        "| XMage pin | `90f5c4d3f8` (`config/rules_engines.json`, v13) |\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError):
        module.check_reference_staleness(doc_path=doc)


def test_check_reference_cli_exit_codes(tmp_path: Path) -> None:
    module = _module()
    assert module.main(["check-reference", "--target", "5d85d2dc4"]) == 0
    old = _old_reference_doc(tmp_path)
    assert module.main(["check-reference", "--doc", str(old), "--target", "a8d6e54a5"]) == 1


def _git(repo: Path, *args: str) -> str:
    import subprocess

    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _reference_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A throw-away repo that has a reference commit, a pilot sibling module and an unrelated file."""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    rules = repo / "src/commander_lab/engine/rules"
    (rules / "full_game_pilot").mkdir(parents=True)
    (repo / "config/rules_engines.json").write_text(
        json.dumps({"primary_engine": {"commit": "90f5c4d3f8" + "0" * 30}}), encoding="utf-8"
    )
    (rules / "full_game_pilot/payment.py").write_text("x = 1\n", encoding="utf-8")
    (rules / "full_game_pilot_mana_hold.py").write_text("y = 1\n", encoding="utf-8")
    (rules / "full_game.py").write_text("z = 1\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "reference")
    commit = _git(repo, "rev-parse", "--short", "HEAD")
    doc = tmp_path / "ref.md"
    doc.write_text(
        f"| Lab commit | `{commit}` |\n| XMage pin | `90f5c4d3f8` |\n",
        encoding="utf-8",
    )
    return repo, doc


def test_a_change_only_in_a_sibling_pilot_module_makes_the_reference_stale(tmp_path: Path) -> None:
    module = _module()
    repo, doc = _reference_repo(tmp_path)
    kwargs = {"doc_path": doc, "repo_root": repo}
    assert module.check_reference_staleness(**kwargs)["stale"] is False

    sibling = repo / "src/commander_lab/engine/rules/full_game_pilot_mana_hold.py"
    sibling.write_text("y = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "sibling")
    res = module.check_reference_staleness(**kwargs)
    assert res["stale"] is True
    assert res["changed_files"] == ("src/commander_lab/engine/rules/full_game_pilot_mana_hold.py",)


def test_a_change_outside_the_pilot_paths_keeps_the_reference_current(tmp_path: Path) -> None:
    module = _module()
    repo, doc = _reference_repo(tmp_path)
    other = repo / "src/commander_lab/engine/rules/full_game.py"
    other.write_text("z = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "unrelated")
    assert module.check_reference_staleness(doc_path=doc, repo_root=repo)["stale"] is False
