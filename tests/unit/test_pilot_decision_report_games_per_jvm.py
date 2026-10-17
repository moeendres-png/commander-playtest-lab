"""--games-per-jvm is wired: the -D property reaches the JVM command and the
value lands in the report (#877).

This test fails if the flag is defined but never read (the #895 bug).
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_gpjvm_under_test", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


def test_games_per_jvm_adds_property_to_command(monkeypatch: Any, tmp_path: Path) -> None:
    """With --games-per-jvm N>1, the -D property must be in the JVM command."""
    captured: dict[str, Any] = {}

    def fake_bridge_command(jar: Path, jvm_options: list[str]) -> tuple[str, ...]:
        captured["jvm_options"] = list(jvm_options)
        return ("java", *jvm_options, "-jar", str(jar), "full-game")

    monkeypatch.setattr(pdr.bench, "bridge_command", fake_bridge_command)
    # Stub out the heavy parts: no real setups, no real games
    monkeypatch.setattr(pdr.bench, "_pods", lambda coverage: {})
    monkeypatch.setattr(pdr, "_play_batch", lambda command, chunk: [])

    out = tmp_path / "report.json"
    args = SimpleNamespace(
        jar=Path("x.jar"),
        out=out,
        seeds=[],
        coverage_pods=False,
        jvm_option=["-Xmx1g"],
        workers=1,
        games_per_jvm=4,
    )
    pdr.run(args)

    assert "-Dcommanderlab.fullGame.gamesPerJvm=4" in captured["jvm_options"]
    assert "-Xmx1g" in captured["jvm_options"]  # user options preserved

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["games_per_jvm"] == 4


def test_games_per_jvm_defaults_to_one(monkeypatch: Any, tmp_path: Path) -> None:
    """Default is 1: no -D property, single game per JVM."""
    captured: dict[str, Any] = {}

    def fake_bridge_command(jar: Path, jvm_options: list[str]) -> tuple[str, ...]:
        captured["jvm_options"] = list(jvm_options)
        return ("java", *jvm_options, "-jar", str(jar), "full-game")

    monkeypatch.setattr(pdr.bench, "bridge_command", fake_bridge_command)
    monkeypatch.setattr(pdr.bench, "_pods", lambda coverage: {})
    monkeypatch.setattr(pdr, "_play", lambda command, pod, setup, seed: {"status": "ok"})

    out = tmp_path / "report.json"
    args = SimpleNamespace(
        jar=Path("x.jar"),
        out=out,
        seeds=[],
        coverage_pods=False,
        jvm_option=[],
        workers=1,
        games_per_jvm=1,
    )
    pdr.run(args)

    assert not any("gamesPerJvm" in opt for opt in captured["jvm_options"])

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["games_per_jvm"] == 1


def test_games_per_jvm_rejects_zero(monkeypatch: Any, tmp_path: Path) -> None:
    """N < 1 is rejected."""
    import pytest

    monkeypatch.setattr(pdr.bench, "_pods", lambda coverage: {})
    out = tmp_path / "report.json"
    args = SimpleNamespace(
        jar=Path("x.jar"),
        out=out,
        seeds=[],
        coverage_pods=False,
        jvm_option=[],
        workers=1,
        games_per_jvm=0,
    )
    with pytest.raises(ValueError, match="must be positive"):
        pdr.run(args)


class _FakeScenario:
    seed = 0

    def model_copy(self, update: dict[str, Any]) -> _FakeScenario:
        return self


class _FakeBatchRunner:
    """Stands in for XmageFullGameRunner: the first game is ok, the second fails."""

    def __init__(self, command: Any, private_card_repository: bool = False) -> None:
        self.command = command

    def run_batch(self, games: Any) -> list[Any]:
        time.sleep(0.2)
        outcomes: list[Any] = [
            SimpleNamespace(semantic_transcript_sha256="b" * 64, winner_seats=(2,)),
            RuntimeError("boom"),
        ]
        return outcomes[: len(games)]


def test_play_batch_rows_have_a_wall_time_and_say_they_have_no_decisions(
    monkeypatch: Any,
) -> None:
    """The batched row is built after the games ran; its wall time still is the chunk's."""
    monkeypatch.setattr(pdr, "XmageFullGameRunner", _FakeBatchRunner)
    setup = (_FakeScenario(), ("d1", "d2"), ("p1", "p2"))
    rows = pdr._play_batch(("java",), [("pod", setup, 1), ("pod", setup, 2)])

    assert [row["status"] for row in rows] == ["ok", "failed"]
    assert rows[0]["semantic"] == "b" * 64
    assert rows[0]["winners"] == [2]
    assert "boom" in rows[1]["error"]
    assert all(row["decisions_recorded"] is False for row in rows)
    # Two games share one 0.2 s chunk: each row carries its share, not 0.0.
    assert all(row["wall_s"] >= 0.09 for row in rows)


def test_totals_accepts_batched_rows(monkeypatch: Any) -> None:
    """A batched game has no `rounds`; totals() used to raise KeyError on it."""
    monkeypatch.setattr(pdr, "XmageFullGameRunner", _FakeBatchRunner)
    setup = (_FakeScenario(), ("d1", "d2"), ("p1", "p2"))
    rows = pdr._play_batch(("java",), [("pod", setup, 1), ("pod", setup, 2)])
    totals = pdr.totals({"games": rows})

    assert totals["games_ok"] == 1
    assert totals["games_failed"] == 1
    assert totals["games_without_decision_record"] == 1
    assert totals["mean_wall_s"] >= 0.1


def test_a_batched_run_writes_its_report(monkeypatch: Any, tmp_path: Path) -> None:
    """End to end through run(): the games are played, then the report must exist."""
    monkeypatch.setattr(pdr, "XmageFullGameRunner", _FakeBatchRunner)
    monkeypatch.setattr(pdr.bench, "bridge_command", lambda jar, opts: ("java", *opts))
    monkeypatch.setattr(pdr.bench, "_pods", lambda coverage: [("pod", ["deck"])])
    monkeypatch.setattr(
        pdr.bench, "_setup", lambda paths: (_FakeScenario(), ("d1", "d2"), ("p1", "p2"))
    )
    out = tmp_path / "report.json"
    args = SimpleNamespace(
        jar=Path("x.jar"),
        out=out,
        seeds=[1, 2],
        coverage_pods=False,
        jvm_option=[],
        workers=1,
        games_per_jvm=2,
    )
    pdr.run(args)

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["games_per_jvm"] == 2
    assert report["elapsed_s"] >= 0.1
    assert len(report["games"]) == 2
    assert report["totals"]["games_without_decision_record"] == 1
