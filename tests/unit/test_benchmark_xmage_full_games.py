"""The benchmark launches the bridge by an absolute jar path.

With ``--private-card-repository`` every bridge JVM starts in its own scratch
directory; a relative ``--jar`` then no longer resolved and every game ended at
once with BRIDGE_EXITED.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

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
