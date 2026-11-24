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
from typing import Any

import pytest

from commander_lab.engine.rules.frame_digest import FrameDigest
from tests.unit.test_xmage_full_game import _binding, _boolean_request, _decks, _scenario

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


def _timed_report(path: Path, *, workers: int, total_wall_s: float | None, wall: float) -> Path:
    doc: dict = {
        "workers": workers,
        "games_per_jvm": 9,
        "games": [
            {"pod": "p1", "seed": seed, "status": "ok", "semantic": f"s{seed}"}
            | {"wall_s": wall, "child_cpu_s": 2 * wall}
            for seed in (1, 2)
        ],
    }
    if total_wall_s is not None:
        doc["total_wall_s"] = total_wall_s
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_compare_gives_no_cpu_percentage_for_runs_with_several_workers(
    tmp_path: Path, capsys
) -> None:
    # Per-game CPU and wall of overlapping games are not additive (#1075): the sums say -50 %
    # here, the elapsed times say +20 %.
    a = _timed_report(tmp_path / "a.json", workers=4, total_wall_s=100.0, wall=40.0)
    b = _timed_report(tmp_path / "b.json", workers=4, total_wall_s=120.0, wall=20.0)
    assert _module().main(["compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "identical 2/2" in out
    assert "cpu  n/a" in out and "elapsed 100.0 -> 120.0 s (+20.0 %)" in out
    assert "wall 80.0" not in out and "cpu  160.0" not in out


def test_compare_keeps_the_sums_for_single_worker_runs(tmp_path: Path, capsys) -> None:
    # Control: with one worker the sums are real time, as before.
    a = _timed_report(tmp_path / "a.json", workers=1, total_wall_s=100.0, wall=40.0)
    b = _timed_report(tmp_path / "b.json", workers=1, total_wall_s=70.0, wall=30.0)
    assert _module().main(["compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "wall 80.0 -> 60.0 s (-25.0 %)" in out and "cpu  160.0 -> 120.0 s (-25.0 %)" in out
    assert "NOTE" not in out and "n/a" not in out


def test_compare_warns_when_the_worker_counts_differ(tmp_path: Path, capsys) -> None:
    a = _timed_report(tmp_path / "a.json", workers=1, total_wall_s=100.0, wall=40.0)
    b = _timed_report(tmp_path / "b.json", workers=4, total_wall_s=None, wall=10.0)
    assert _module().main(["compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "NOTE workers 1 -> 4" in out and "elapsed n/a" in out


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
    assert module.fast_jvm_options(jar) == ["-XX:+UseSerialGC", "-Dh2.bindAddress=127.0.0.1"]
    (tmp_path / "bridge.jsa").write_bytes(b"")
    options = module.fast_jvm_options(jar)
    assert options[0] == "-XX:+UseSerialGC"
    assert f"-XX:SharedArchiveFile={tmp_path / 'bridge.jsa'}" in options
    # the JVM's own warnings must never reach the protocol on stdout
    assert options[2:4] == ["-Xlog:disable", "-Xlog:all=warning:stderr"]


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
    assert meta == {"lab_commit": "2cc29df14", "xmage_pin": "f4d12f6e80"}


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
    res = module.check_reference_staleness(target_ref="2cc29df14")
    assert res["stale"] is False
    assert res["changed_files"] == ()
    assert res["pin_matches"] is True
    assert "current at 2cc29df14" in str(res["message"])


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
    assert module.main(["check-reference", "--target", "2cc29df14"]) == 0
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


# Files that decide the 36-seed hashes without being pilot code (#1076).
_HASH_INPUTS = (
    "data/cards/pilot_card_knowledge.json",
    "data/decks/rogshai_current.json",
    "scripts/run_real_4p_full_game_smoke.py",
    "engine-bridge/pom.xml",
)


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
    for relative in (*_HASH_INPUTS, "docs/note.md"):
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
        (repo / relative).write_text("v1\n", encoding="utf-8")
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


def test_a_change_outside_the_watched_paths_keeps_the_reference_current(tmp_path: Path) -> None:
    module = _module()
    repo, doc = _reference_repo(tmp_path)
    (repo / "docs/note.md").write_text("v2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "unrelated")
    assert module.check_reference_staleness(doc_path=doc, repo_root=repo)["stale"] is False


@pytest.mark.parametrize(
    "relative",
    ["src/commander_lab/engine/rules/full_game.py", *_HASH_INPUTS],
)
def test_a_change_to_an_input_of_the_hashes_makes_the_reference_stale(
    tmp_path: Path, relative: str
) -> None:
    # The hashes depend on the card knowledge the pilot reads, the pod decks, the script that
    # builds pod and pilot configuration, the engine pom and the module that forms the hash
    # (#1076): none of them is pilot code, and the watcher used to call the reference current.
    module = _module()
    repo, doc = _reference_repo(tmp_path)
    (repo / relative).write_text("v2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "input")
    res = module.check_reference_staleness(doc_path=doc, repo_root=repo)
    assert res["stale"] is True
    assert res["changed_files"] == (relative,)


def test_every_pod_deck_of_the_smoke_script_is_watched() -> None:
    module = _module()
    decks = {str(path) for path in module.smoke.REAL_DECK_PATHS}
    assert len(decks) == 4
    assert decks <= set(module.REFERENCE_WATCHED_PATHS)


# --- the gate options of ``compare``: frame digests, expected game count, different jars --------


def _framed(
    path: Path,
    games: list[tuple[int, str, str, dict[str, str]]],
    *,
    jar: str | None = "jar-a",
) -> Path:
    rows = [
        {"pod": "p1", "seed": seed, "status": "ok", "semantic": sem, "frame_digest": fd}
        | {"frame_digest_by_seat": seats, "frames": 7, "wall_s": 1.0, "child_cpu_s": 1.0}
        for seed, sem, fd, seats in games
    ]
    doc: dict = {"games": rows}
    if jar is not None:
        doc["bridge_jar_sha256"] = jar
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


_SEATS = {"0": "x0", "1": "x1"}
_GAMES = [(1, "s1", "1" * 64, _SEATS), (2, "s2", "2" * 64, _SEATS)]


def _gate(tmp_path: Path, a: Path, b: Path, *options: str) -> int:
    return _module().main(["compare", str(a), str(b), *options])


def test_compare_passes_when_hashes_and_frames_are_identical(tmp_path: Path, capsys) -> None:
    a = _framed(tmp_path / "a.json", _GAMES)
    b = _framed(tmp_path / "b.json", _GAMES, jar="jar-b")
    assert _gate(tmp_path, a, b, "--expect-games", "2", "--require-different-jars") == 0
    out = capsys.readouterr().out
    assert "identical 2/2" in out and "frames identical 2/2" in out


def test_compare_fails_when_frames_differ_although_the_hashes_are_equal(
    tmp_path: Path, capsys
) -> None:
    a = _framed(tmp_path / "a.json", _GAMES)
    b = _framed(tmp_path / "b.json", [_GAMES[0], (2, "s2", "OTHER", {"0": "x0", "1": "changed"})])
    assert _gate(tmp_path, a, b) == 1
    out = capsys.readouterr().out
    assert "identical 2/2" in out and "frames identical 1/2" in out
    assert "FRAMES DIFFERENT ('p1', 2) first differing seat: 1;" in out


def test_compare_without_frame_digests_in_one_file_keeps_the_old_behaviour(
    tmp_path: Path, capsys
) -> None:
    a = _framed(tmp_path / "a.json", _GAMES)
    b = _report(tmp_path / "b.json", [("p1", 1, "ok", "s1"), ("p1", 2, "ok", "s2")])
    assert _gate(tmp_path, a, b) == 0
    assert "frames not compared" in capsys.readouterr().out


def test_expect_games_fails_on_a_missing_game_or_a_wrong_count(tmp_path: Path) -> None:
    a = _framed(tmp_path / "a.json", _GAMES)
    b = _framed(tmp_path / "b.json", _GAMES[:1])
    assert _gate(tmp_path, a, b, "--expect-games", "2") == 1
    assert _gate(tmp_path, a, a, "--expect-games", "3") == 1
    assert _gate(tmp_path, a, a, "--expect-games", "2") == 0


def test_expect_games_demands_frame_digests_and_finished_games(tmp_path: Path) -> None:
    plain = _report(tmp_path / "p.json", [("p1", 1, "ok", "s1")])
    assert _gate(tmp_path, plain, plain, "--expect-games", "1") == 1
    failed = _report(tmp_path / "f.json", [("p1", 1, "failed", None)])
    assert _gate(tmp_path, failed, failed, "--expect-games", "1") == 1


def test_zero_games_in_common_is_an_error(tmp_path: Path, capsys) -> None:
    a = _report(tmp_path / "a.json", [("p1", 1, "ok", "s1")])
    b = _report(tmp_path / "b.json", [("p1", 2, "ok", "s1")])
    assert _gate(tmp_path, a, b) == 1
    empty = tmp_path / "e.json"
    empty.write_text(json.dumps({"games": []}), encoding="utf-8")
    assert _gate(tmp_path, empty, empty) == 1
    assert "no game is present in both files" in capsys.readouterr().out


def test_require_different_jars(tmp_path: Path, capsys) -> None:
    same_a = _framed(tmp_path / "a.json", _GAMES)
    same_b = _framed(tmp_path / "b.json", _GAMES)
    assert _gate(tmp_path, same_a, same_b, "--require-different-jars") == 1
    assert "both reports used jar jar-a" in capsys.readouterr().out
    other = _framed(tmp_path / "c.json", _GAMES, jar="jar-b")
    assert _gate(tmp_path, same_a, other, "--require-different-jars") == 0
    unknown = _framed(tmp_path / "d.json", _GAMES, jar=None)
    assert _gate(tmp_path, same_a, unknown, "--require-different-jars") == 1


def _with_skip_mode(path: Path) -> Path:
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["frame_digest_skip_forced"] = True
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_compare_rejects_mixed_frame_digest_modes(tmp_path: Path, capsys) -> None:
    plain = _framed(tmp_path / "a.json", _GAMES)
    skipped = _with_skip_mode(_framed(tmp_path / "b.json", _GAMES, jar="jar-b"))
    assert _gate(tmp_path, plain, skipped) == 1
    assert "frame digest modes differ" in capsys.readouterr().out
    also_skipped = _with_skip_mode(_framed(tmp_path / "c.json", _GAMES, jar="jar-b"))
    assert _gate(tmp_path, skipped, also_skipped) == 0


def test_compare_rejects_mixed_frame_digest_modes_in_the_other_direction(
    tmp_path: Path, capsys
) -> None:
    skipped = _with_skip_mode(_framed(tmp_path / "a.json", _GAMES, jar="jar-b"))
    plain = _framed(tmp_path / "b.json", _GAMES)
    assert _gate(tmp_path, skipped, plain) == 1
    assert "frame digest modes differ" in capsys.readouterr().out


def test_compare_rejects_a_legacy_report_against_a_skip_mode_report(tmp_path: Path, capsys) -> None:
    legacy = _framed(tmp_path / "a.json", _GAMES)
    # Premise of the case: a report written before the mode existed carries no field.
    assert "frame_digest_skip_forced" not in json.loads(legacy.read_text(encoding="utf-8"))
    skipped = _with_skip_mode(_framed(tmp_path / "b.json", _GAMES, jar="jar-b"))
    assert _gate(tmp_path, legacy, skipped) == 1
    assert "frame digest modes differ" in capsys.readouterr().out
    assert _gate(tmp_path, skipped, legacy) == 1
    assert "frame digest modes differ" in capsys.readouterr().out


def test_skip_forced_flag_needs_the_frame_digest(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        _module().main(
            [
                "run",
                "--jar",
                str(tmp_path / "bridge.jar"),
                "--out",
                str(tmp_path / "out.json"),
                "--no-frame-digest",
                "--frame-digest-skip-forced",
            ]
        )


def _forced_boolean_request(offset: int) -> dict[str, Any]:
    """A decidable request with no choice in it: one option, and it must be taken."""
    request = _boolean_request(decision_id=f"forced-{offset}", offset=offset)
    request["legal_options"] = request["legal_options"][:1]
    return request


def _digest_after_requests(skip_forced_frames: bool, requests: list[dict[str, Any]]):
    """Requests decided through the benchmark runner's policy; the digest it recorded."""
    decks = _decks()
    scenario = _scenario(decks)
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 5))
    runner = _module()._runner(
        ("java", "-jar", "unused.jar", "full-game"), False, True, skip_forced_frames
    )
    policy = runner._validated_policy(scenario, decks, pilots)
    for request in requests:
        policy.decide(request)
    return runner.digest_for(scenario.seed, decks)


def test_the_runner_skips_forced_frames_only_when_the_mode_is_on() -> None:
    requests = [_forced_boolean_request(3), _boolean_request(decision_id="open-5", offset=5)]
    skipped = _digest_after_requests(True, requests)
    assert skipped is not None and skipped.skipped == 1 and skipped.frames == 1
    # The runner's digest is the digest of the remaining frames alone.
    manual = FrameDigest()
    manual.observe(_boolean_request(decision_id="open-5", offset=5))
    assert skipped.digest == manual.result().digest
    plain = _digest_after_requests(False, requests)
    assert plain is not None and plain.skipped == 0 and plain.frames == 2
    assert plain.digest != skipped.digest


def test_file_sha256_is_the_sha256_of_the_bytes(tmp_path: Path) -> None:
    jar = tmp_path / "x.jar"
    jar.write_bytes(b"abc")
    assert _module().file_sha256(jar) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_duplicate_games_in_a_report_are_an_error(tmp_path: Path, capsys) -> None:
    dup = _report(tmp_path / "d.json", [("p1", 1, "failed", None), ("p1", 1, "ok", "s1")])
    ok = _report(tmp_path / "o.json", [("p1", 1, "ok", "s1")])
    assert _gate(tmp_path, dup, ok) == 1
    assert _gate(tmp_path, ok, dup) == 1
    assert "duplicate game" in capsys.readouterr().out


def _hexed(seed: int, text: str) -> tuple[int, str, str, dict[str, str]]:
    return (seed, f"s{seed}", text * 64, {"0": text * 64})


def test_expect_games_demands_equal_seed_sets_and_hex_digests(tmp_path: Path) -> None:
    a = _framed(tmp_path / "a.json", [_hexed(1, "a"), _hexed(2, "b")])
    other_seeds = _framed(tmp_path / "b.json", [_hexed(1, "a"), _hexed(3, "b")])
    assert _gate(tmp_path, a, other_seeds, "--expect-games", "2") == 1
    assert _gate(tmp_path, a, a, "--expect-games", "2") == 0
    short = _framed(tmp_path / "s.json", [(1, "s1", "f1", {"0": "x"}), _hexed(2, "b")])
    assert _gate(tmp_path, short, short, "--expect-games", "2") == 1


def test_frames_and_seat_digests_must_agree_and_the_seat_is_named(tmp_path: Path, capsys) -> None:
    a = _framed(tmp_path / "a.json", [_hexed(1, "a")])
    seats = {"0": "a" * 64, "1": "c" * 64}
    b = _framed(tmp_path / "b.json", [(1, "s1", "a" * 64, seats)])
    assert _gate(tmp_path, a, b) == 1
    assert "first differing seat: 1" in capsys.readouterr().out
    c = _framed(tmp_path / "c.json", [_hexed(1, "a")])
    doc = json.loads(c.read_text(encoding="utf-8"))
    doc["games"][0]["frames"] = 8
    c.write_text(json.dumps(doc), encoding="utf-8")
    assert _gate(tmp_path, a, c) == 1


def test_the_summary_prints_both_reports_settings(tmp_path: Path, capsys) -> None:
    a = _framed(tmp_path / "a.json", _GAMES)
    doc = json.loads(a.read_text(encoding="utf-8"))
    doc |= {"workers": 2, "games_per_jvm": 2, "jvm_options": ["-Xfoo"]}
    a.write_text(json.dumps(doc), encoding="utf-8")
    assert _gate(tmp_path, a, a) == 0
    out = capsys.readouterr().out
    assert "settings A: workers 2, games_per_jvm 2, jvm_options ['-Xfoo']" in out
    assert "settings B:" in out


def test_benchmark_and_identity_scripts_run_without_resource_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "resource", None)
    bench = _module()
    assert bench.resource is None
    assert bench._children_cpu_seconds() is None
    with pytest.raises(SystemExit) as exc_info:
        bench.main(["--help"])
    assert exc_info.value.code == 0

    spec = importlib.util.spec_from_file_location(
        "check_studio_series_identity", ROOT / "scripts/check_studio_series_identity.py"
    )
    assert spec is not None and spec.loader is not None
    identity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(identity)
    assert identity.resource is None
    assert identity._cpu_seconds() is None
    assert identity._cpu_delta(None, None) is None
    assert identity._format_cpu(None) == "nicht verfügbar"
    with pytest.raises(SystemExit) as exc_info2:
        identity.main(["--help"])
    assert exc_info2.value.code == 0


def test_compare_handles_unavailable_cpu_time_without_reporting_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [
        {
            "pod": "p1",
            "seed": 1,
            "status": "ok",
            "semantic": "s1",
            "wall_s": 5.0,
            "child_cpu_s": None,
        }
    ]
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"games": rows}), encoding="utf-8")
    b.write_text(json.dumps({"games": rows}), encoding="utf-8")
    assert _module().main(["compare", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "wall 5.0 -> 5.0 s" in out
    assert "cpu  nicht verfügbar" in out


# --- paired-series identity check (scripts/check_studio_series_identity.py, Refs #1521) -------


def _identity_module():
    spec = importlib.util.spec_from_file_location(
        "check_studio_series_identity", ROOT / "scripts/check_studio_series_identity.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fp_row(
    game_id: str,
    *,
    status: str = "finished",
    semantic: str | None = "h1",
    winners: list[int] | None = None,
    decisions: int | None = 42,
) -> dict[str, object]:
    return {
        "game_id": game_id,
        "status": status,
        "semantic": semantic,
        "winners": [1] if winners is None else winners,
        "decisions": decisions,
        "failure": None,
    }


def _paired_cli_fixtures(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"jar")
    base_deck = tmp_path / "base.json"
    base_deck.write_text("{}", encoding="utf-8")
    variant_deck = tmp_path / "variant.json"
    variant_deck.write_text("{}", encoding="utf-8")
    work = tmp_path / "work"
    out = tmp_path / "report.json"
    return jar, base_deck, variant_deck, work, out


def _patch_paired_players(
    monkeypatch: pytest.MonkeyPatch,
    identity: object,
    *,
    alone_by_arm: dict[str, dict[int, dict[str, object]]],
    paired_rows: dict[tuple[str, int], dict[str, object]],
) -> None:
    def fake_play_alone(
        data: Path,
        deck: Path,
        opponents: list[Path],
        seeds: list[int],
        env: dict[str, str],
    ) -> dict[int, dict[str, object]]:
        arm = data.name
        return dict(alone_by_arm[arm])

    def fake_play_paired_series(
        data: Path,
        base_deck_path: Path,
        variant_deck_path: Path,
        opponents: list[Path],
        seeds: list[int],
        workers: int,
        games_per_jvm: int,
    ) -> tuple[dict[tuple[str, int], dict[str, object]], dict[str, object]]:
        return dict(paired_rows), {
            "series_id": "identity-paired",
            "workers": workers,
            "games_per_jvm": games_per_jvm,
            "pool": None,
        }

    monkeypatch.setattr(identity, "play_alone", fake_play_alone)
    monkeypatch.setattr(identity, "play_paired_series", fake_play_paired_series)


def test_paired_identity_passes_when_all_games_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = _identity_module()
    jar, base_deck, variant_deck, work, out = _paired_cli_fixtures(tmp_path)
    seeds = [1, 2, 3]
    alone_by_arm = {
        arm: {
            seed: _fp_row(
                f"a-{arm}-{seed}",
                semantic=f"hash-{arm}-{seed}",
                winners=[1 if arm == "base" else 2],
                decisions=50 + seed,
            )
            for seed in seeds
        }
        for arm in ("base", "variant")
    }
    paired_rows = {
        (arm, seed): _fp_row(
            f"b-{arm}-{seed}",
            semantic=f"hash-{arm}-{seed}",
            winners=[1 if arm == "base" else 2],
            decisions=50 + seed,
        )
        for arm in ("base", "variant")
        for seed in seeds
    }
    _patch_paired_players(monkeypatch, identity, alone_by_arm=alone_by_arm, paired_rows=paired_rows)

    rc = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(variant_deck),
            "--seeds",
            "1-3",
            "--workers",
            "2",
            "--games-per-jvm",
            "3",
            "--work",
            str(work),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "6 identisch von 6" in stdout
    assert "IDENTITY PASS" in stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["mode"] == "paired"
    assert report["status"] == "PASS"
    assert report["passed"] is True
    assert report["summary"] == "6 identisch von 6"
    assert report["identical"] == 6
    assert report["total"] == 6
    assert report["mismatches"] == []


def test_paired_identity_fails_on_single_semantic_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = _identity_module()
    jar, base_deck, variant_deck, work, out = _paired_cli_fixtures(tmp_path)
    seeds = [1, 2]
    alone_by_arm = {
        arm: {seed: _fp_row(f"a-{arm}-{seed}", semantic=f"h-{arm}-{seed}") for seed in seeds}
        for arm in ("base", "variant")
    }
    paired_rows = {
        (arm, seed): _fp_row(f"b-{arm}-{seed}", semantic=f"h-{arm}-{seed}")
        for arm in ("base", "variant")
        for seed in seeds
    }
    paired_rows[("variant", 2)] = _fp_row("b-variant-2", semantic="DIFFERENT-HASH")
    _patch_paired_players(monkeypatch, identity, alone_by_arm=alone_by_arm, paired_rows=paired_rows)

    rc = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(variant_deck),
            "--seeds",
            "1-2",
            "--work",
            str(work),
            "--out",
            str(out),
        ]
    )
    assert rc == 1
    stdout = capsys.readouterr().out
    assert "3 identisch von 4" in stdout
    assert "semantic_hash_mismatch" in stdout
    assert "IDENTITY FAIL" in stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["passed"] is False
    assert len(report["mismatches"]) == 1
    assert report["mismatches"][0]["arm"] == "variant"
    assert report["mismatches"][0]["seed"] == 2
    assert "semantic_hash_mismatch" in report["mismatches"][0]["reasons"]


@pytest.mark.parametrize(
    ("field", "mutated_value", "expected_reason"),
    [
        ("winners", [3], "winner_seat_mismatch"),
        ("decisions", 999, "decision_count_mismatch"),
    ],
)
def test_paired_identity_fails_on_winner_or_decision_count_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    mutated_value: object,
    expected_reason: str,
) -> None:
    identity = _identity_module()
    jar, base_deck, variant_deck, work, out = _paired_cli_fixtures(tmp_path)
    seeds = [1, 2]
    alone_by_arm = {
        arm: {seed: _fp_row(f"a-{arm}-{seed}", semantic=f"h-{arm}-{seed}") for seed in seeds}
        for arm in ("base", "variant")
    }
    paired_rows = {
        (arm, seed): _fp_row(f"b-{arm}-{seed}", semantic=f"h-{arm}-{seed}")
        for arm in ("base", "variant")
        for seed in seeds
    }
    paired_rows[("base", 1)][field] = mutated_value
    _patch_paired_players(monkeypatch, identity, alone_by_arm=alone_by_arm, paired_rows=paired_rows)

    rc = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(variant_deck),
            "--seeds",
            "1-2",
            "--work",
            str(work),
            "--out",
            str(out),
        ]
    )
    assert rc == 1
    stdout = capsys.readouterr().out
    assert "3 identisch von 4" in stdout
    assert expected_reason in stdout
    assert "IDENTITY FAIL" in stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["passed"] is False
    assert expected_reason in report["mismatches"][0]["reasons"]


@pytest.mark.parametrize("missing_side", ["paired", "alone"])
def test_paired_identity_fails_when_a_game_is_missing_on_either_side(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing_side: str,
) -> None:
    identity = _identity_module()
    jar, base_deck, variant_deck, work, out = _paired_cli_fixtures(tmp_path)
    seeds = [1, 2]
    alone_by_arm = {
        arm: {seed: _fp_row(f"a-{arm}-{seed}", semantic=f"h-{arm}-{seed}") for seed in seeds}
        for arm in ("base", "variant")
    }
    paired_rows = {
        (arm, seed): _fp_row(f"b-{arm}-{seed}", semantic=f"h-{arm}-{seed}")
        for arm in ("base", "variant")
        for seed in seeds
    }
    if missing_side == "paired":
        del paired_rows[("variant", 1)]
        expected_reason = "missing_paired"
    else:
        del alone_by_arm["base"][2]
        expected_reason = "missing_alone"

    _patch_paired_players(monkeypatch, identity, alone_by_arm=alone_by_arm, paired_rows=paired_rows)

    rc = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(variant_deck),
            "--seeds",
            "1-2",
            "--work",
            str(work),
            "--out",
            str(out),
        ]
    )
    assert rc == 1
    stdout = capsys.readouterr().out
    assert "3 identisch von 4" in stdout
    assert expected_reason in stdout
    assert "IDENTITY FAIL" in stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["passed"] is False


def test_paired_identity_empty_seeds_fails_closed() -> None:
    identity = _identity_module()
    res = identity.compare_paired_identity([], {}, {})
    assert res["passed"] is False
    assert res["status"] == "FAIL"
    assert res["summary"] == "0 identisch von 0"


def test_paired_identity_missing_jar_reports_not_run_never_pass(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = _identity_module()
    _, base_deck, variant_deck, work, out = _paired_cli_fixtures(tmp_path)
    missing_jar = tmp_path / "does_not_exist.jar"

    rc = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(missing_jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(variant_deck),
            "--seeds",
            "1-2",
            "--work",
            str(work),
            "--out",
            str(out),
        ]
    )
    assert rc != 0
    stdout = capsys.readouterr().out
    assert "NOT_RUN" in stdout
    assert "PASS" not in stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "NOT_RUN"
    assert report["passed"] is False
    assert report["mode"] == "paired"


def test_paired_identity_requires_existing_variant_deck(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = _identity_module()
    jar, base_deck, _, work, _ = _paired_cli_fixtures(tmp_path)

    rc_missing = identity.main(
        ["--mode", "paired", "--jar", str(jar), "--deck", str(base_deck), "--work", str(work)]
    )
    assert rc_missing != 0
    assert "--variant-deck" in capsys.readouterr().err

    rc_not_found = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(tmp_path / "missing_variant.json"),
            "--work",
            str(work),
        ]
    )
    assert rc_not_found != 0
    assert "variant deck not found" in capsys.readouterr().err


def test_play_paired_series_drives_parallel_window_player_and_closes_pool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity_module()
    calls: list[tuple[str, int, int]] = []
    captured: dict[str, object] = {}
    closed = {"called": False}

    class FakeDeck:
        def __init__(self, deck_id: str) -> None:
            self.deck_id = deck_id

        def model_copy(self, *, update: dict[str, str]) -> FakeDeck:
            return FakeDeck(update["deck_id"])

    class FakeEngine:
        games_per_jvm = 3
        command = ("java", "-jar", "bridge.jar", "full-game")

    class FakeWindowPlayer:
        def __call__(self, arm: str, seed: int, seat: int) -> dict[str, object]:
            calls.append((arm, seed, seat))
            return {"game_id": f"identity-paired-{arm}-s{seed}-t{seat}"}

        def pool_summary(self) -> dict[str, object]:
            return {"games_played": len(calls)}

        def close(self) -> None:
            closed["called"] = True

    def fake_parallel_window_player(data: Path, **kwargs: object) -> FakeWindowPlayer:
        captured["data"] = data
        captured.update(kwargs)
        return FakeWindowPlayer()

    monkeypatch.setattr(identity, "series_engine", lambda _data, _gpj: FakeEngine())
    monkeypatch.setattr(
        identity,
        "load_rules_deck_snapshot",
        lambda path: FakeDeck(
            "same-id" if path.name in ("base.json", "variant.json") else path.stem
        ),
    )
    monkeypatch.setattr(
        identity.paired_comparison, "parallel_window_player", fake_parallel_window_player
    )
    monkeypatch.setattr(
        identity,
        "_fingerprint",
        lambda _data, game_id: _fp_row(game_id, semantic=f"sem-{game_id}"),
    )

    rows, execution = identity.play_paired_series(
        tmp_path / "b",
        tmp_path / "base.json",
        tmp_path / "variant.json",
        [tmp_path / "opp1.json", tmp_path / "opp2.json", tmp_path / "opp3.json"],
        [10, 11],
        workers=2,
        games_per_jvm=3,
    )
    assert closed["called"] is True
    assert captured["workers"] == 2
    assert captured["games_per_jvm"] == 3
    assert captured["tested_seats"] == [0]
    assert captured["budget_pairs"] == 2
    assert captured["look_every_pairs"] == 2
    assert calls == [("base", 10, 0), ("variant", 10, 0), ("base", 11, 0), ("variant", 11, 0)]
    assert set(rows.keys()) == {("base", 10), ("variant", 10), ("base", 11), ("variant", 11)}
    assert rows[("variant", 11)]["game_id"] == "identity-paired-variant-s11-t0"
    assert execution["pool"] == {"games_played": 4}


def test_paired_identity_reports_unavailable_cpu_without_resource_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = _identity_module()
    monkeypatch.setattr(identity, "resource", None)
    jar, base_deck, variant_deck, work, out = _paired_cli_fixtures(tmp_path)
    alone_by_arm = {
        arm: {1: _fp_row(f"a-{arm}-1", semantic=f"h-{arm}-1")} for arm in ("base", "variant")
    }
    paired_rows = {
        (arm, 1): _fp_row(f"b-{arm}-1", semantic=f"h-{arm}-1") for arm in ("base", "variant")
    }
    _patch_paired_players(monkeypatch, identity, alone_by_arm=alone_by_arm, paired_rows=paired_rows)

    rc = identity.main(
        [
            "--mode",
            "paired",
            "--jar",
            str(jar),
            "--deck",
            str(base_deck),
            "--variant-deck",
            str(variant_deck),
            "--seeds",
            "1",
            "--work",
            str(work),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "cpu nicht verfügbar" in stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["cpu_s"] == {"a": None, "b": None}
