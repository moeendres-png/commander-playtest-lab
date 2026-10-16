"""Paired seed-noise comparison in scripts/pilot_decision_report.py (#835).

Small hand-made report JSONs; no JVM, no games are played.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_under_test", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


def _row(
    pod: str = "real", seed: int = 1, players: int = 4, status: str = "ok", **metrics: float
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pod": pod,
        "seed": seed,
        "players": players,
        "status": status,
        "rounds": 10.0,
    }
    for key in pdr._COMPARE_METRICS:
        row[key] = metrics.get(key, 0.0)
    return row


def _report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"jar": "bridge.jar", "games": rows}


def test_identical_reports_nothing_changed() -> None:
    rows = [_row(seed=s, spells_cast=40.0 + s, turns=40 + s) for s in range(1, 13)]
    result = pdr.compare_reports(_report(rows), _report([dict(row) for row in rows]))
    assert result["paired_games"] == 12
    assert result["unpaired_games"] == []
    assert result["warnings"] == []
    assert result["metrics"], "expected metrics for paired games"
    assert all(not metric["changed"] for metric in result["metrics"].values())


def test_consistent_shift_marks_changed_with_sign() -> None:
    rows_a = [_row(seed=s, spells_cast=40.0) for s in range(1, 13)]
    rows_b = [_row(seed=s, spells_cast=46.0) for s in range(1, 13)]
    result = pdr.compare_reports(_report(rows_a), _report(rows_b))
    metric = result["metrics"]["spells_cast"]
    assert metric["changed"]
    assert metric["mean_delta"] == pytest.approx(6.0)
    lo, hi = metric["ci95"]
    assert lo > 0, "interval must exclude 0 on the positive side"
    assert hi > 0
    # An unchanged metric on the same pairing stays quiet.
    assert not result["metrics"]["turns"]["changed"]


def test_single_outlier_does_not_mark_changed() -> None:
    rows_a = [_row(seed=s, spells_cast=40.0) for s in range(1, 13)]
    rows_b = [_row(seed=s, spells_cast=40.0) for s in range(1, 13)]
    rows_b[0] = _row(seed=1, spells_cast=4000.0)
    result = pdr.compare_reports(_report(rows_a), _report(rows_b))
    metric = result["metrics"]["spells_cast"]
    # A naive totals comparison would see a huge shift here (wrong reason);
    # the paired bootstrap must not call it a change.
    naive_shift = (
        pdr.totals(_report(rows_b))["spells_cast"] - pdr.totals(_report(rows_a))["spells_cast"]
    )
    assert naive_shift > 1000
    assert not metric["changed"]
    lo, hi = metric["ci95"]
    assert lo <= 0 <= hi


def test_totals_uses_per_game_player_count() -> None:
    games = [
        _row(seed=1, players=4, spells_cast=40.0, rounds=10.0),
        _row(seed=2, players=6, spells_cast=60.0, rounds=10.0),
    ]
    out = pdr.totals(_report(games))
    # (40 + 60) spells / (4*10 + 6*10) player-rounds = 1.0; hardcoding 4 would give 0.83.
    assert out["spells_per_player_round"] == pytest.approx(1.0)


def test_totals_falls_back_to_four_players_without_field() -> None:
    rows = [
        {"pod": "real", "seed": seed, "status": "ok", "spells_cast": 40.0, "rounds": 10.0}
        for seed in (1, 2)
    ]
    out = pdr.totals({"games": rows})
    assert out["spells_per_player_round"] == pytest.approx(80.0 / (4 * 20.0))


def test_unpaired_and_failed_games_are_listed_not_dropped() -> None:
    rows_a = [_row(seed=1), _row(seed=2), _row(seed=3, status="failed")]
    rows_b = [_row(seed=1), _row(seed=2), _row(seed=4)]
    result = pdr.compare_reports(_report(rows_a), _report(rows_b))
    assert result["paired_games"] == 2
    by_key = {(game["report"], game["seed"]): game for game in result["unpaired_games"]}
    assert by_key[("a", 3)]["reason"] == "status=failed"
    assert by_key[("b", 4)]["reason"] == "no match in a"
    assert len(by_key) == 2


def test_fewer_than_ten_paired_seeds_warns(tmp_path: Path, capsys: Any) -> None:
    rows = [_row(seed=seed) for seed in range(1, 5)]
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_a.write_text(json.dumps(_report(rows)), encoding="utf-8")
    path_b.write_text(json.dumps(_report(rows)), encoding="utf-8")
    assert pdr.compare(argparse.Namespace(a=path_a, b=path_b, json=None)) == 0
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "fewer than 10" in out
    assert "paired games: 4" in out


def test_json_output(tmp_path: Path) -> None:
    rows_a = [_row(seed=s, spells_cast=40.0) for s in range(1, 13)]
    rows_b = [_row(seed=s, spells_cast=40.0) for s in range(1, 13)]
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    out_path = tmp_path / "comparison.json"
    path_a.write_text(json.dumps(_report(rows_a)), encoding="utf-8")
    path_b.write_text(json.dumps(_report(rows_b)), encoding="utf-8")
    assert pdr.compare(argparse.Namespace(a=path_a, b=path_b, json=out_path)) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["report_a"] == str(path_a)
    assert payload["report_b"] == str(path_b)
    assert payload["paired_games"] == 12
    assert payload["paired_seeds_per_pod"] == {"real": 12}
    metric = payload["metrics"]["spells_cast"]
    assert metric["changed"] is False
    assert metric["mean_delta"] == pytest.approx(0.0)
    assert payload["warnings"] == []
