"""--games-per-jvm is wired: the -D property reaches the JVM command and the
value lands in the report (#877).

This test fails if the flag is defined but never read (the #895 bug).
"""

from __future__ import annotations

import importlib.util
import json
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
