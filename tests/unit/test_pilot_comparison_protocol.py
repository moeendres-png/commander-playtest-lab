"""Multiple-comparison protocol of scripts/pilot_decision_report.py compare (#835, roadmap M-1).

Hand-made reports; no JVM, no games are played.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_protocol_test", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)

sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_xmage_full_games as bench  # noqa: E402

NOISY = ("turns", "decisions", "spells_cast", "own_turns", "attacks", "blocks", "pilot_s", "wall_s")


def _row(seed: int, **metrics: float) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pod": "real",
        "seed": seed,
        "players": 4,
        "status": "ok",
        "rounds": 10.0,
    }
    for key in pdr._COMPARE_METRICS:
        row[key] = metrics.get(key, 0.0)
    return row


def _report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"jar": "bridge.jar", "games": rows}


def _noise_report(games: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    return _report([_row(i, **{k: rng.gauss(50, 10) for k in NOISY}) for i in range(games)])


def test_holm_adjustment_matches_the_textbook_example() -> None:
    adjusted = pdr.holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    assert pdr.holm_adjust({}) == {}
    assert pdr.holm_adjust({"only": 0.2}) == {"only": 0.2}


def test_adjusted_p_values_never_exceed_one_and_never_fall_below_the_raw_value() -> None:
    raw = {"a": 0.6, "b": 0.7, "c": 0.0005}
    adjusted = pdr.holm_adjust(raw)
    assert all(raw[k] <= adjusted[k] <= 1.0 for k in raw)


@pytest.mark.parametrize(
    ("deltas", "expected"),
    [
        ([1.0] * 5, 2 / 32),  # all five signs equal: 2 of 32 flips are as extreme
        ([1.0, -1.0, 1.0, -1.0], 1.0),  # observed mean zero: every flip is as extreme
        ([0.0, 0.0, 0.0], 1.0),
        ([2.0, 1.0, 1.0], 2 / 8),
    ],
)
def test_sign_flip_p_value_is_exact_for_few_pairs(deltas: list[float], expected: float) -> None:
    assert pdr.sign_flip_p_value(deltas) == pytest.approx(expected)


def test_sign_flip_p_value_with_many_pairs_is_seeded_and_small_for_a_clear_shift() -> None:
    deltas = [1.0 + 0.1 * (i % 3) for i in range(30)]
    first = pdr.sign_flip_p_value(deltas)
    assert first == pdr.sign_flip_p_value(list(deltas))
    assert first < 0.01
    noisy = [(-1.0) ** i * (1 + i % 4) for i in range(30)]
    assert pdr.sign_flip_p_value(noisy) > 0.2


def test_minimum_detectable_change_follows_the_spread_of_the_deltas() -> None:
    assert pdr.minimum_detectable_change([0.0, 2.0] * 6) == pytest.approx(0.8443, abs=1e-3)
    assert pdr.minimum_detectable_change([3.0] * 12) == 0.0
    assert pdr.minimum_detectable_change([1.0]) == float("inf")
    wide = pdr.minimum_detectable_change([0.0, 20.0] * 6)
    assert wide == pytest.approx(10 * 0.8443, abs=1e-2)


def test_a_clear_shift_stays_significant_after_holm_and_a_flat_metric_does_not() -> None:
    rows_a = [_row(s, spells_cast=40.0 + s % 3, turns=30.0) for s in range(1, 13)]
    rows_b = [_row(s, spells_cast=46.0 + s % 3, turns=30.0) for s in range(1, 13)]
    result = pdr.compare_reports(_report(rows_a), _report(rows_b))
    assert result["metrics"]["spells_cast"]["significant"]
    assert not result["metrics"]["turns"]["significant"]
    assert result["family_size"] == 1, "only a metric that moves in some pair is tested"


def test_identical_reports_have_an_empty_family_and_nothing_significant() -> None:
    rows = [_row(s, spells_cast=40.0 + s, turns=30.0 + s) for s in range(1, 13)]
    result = pdr.compare_reports(_report(rows), _report([dict(r) for r in rows]))
    assert result["family_size"] == 0
    assert not any(m["significant"] for m in result["metrics"].values())
    assert all(m["p"] == 1.0 for m in result["metrics"].values())


def test_the_primary_metric_is_tested_alone_and_the_others_are_exploratory() -> None:
    rows_a = [_row(s, spells_cast=40.0 + s % 3, turns=30.0 + s % 5) for s in range(1, 13)]
    rows_b = [_row(s, spells_cast=42.0 + s % 3, turns=30.0 + (s + 1) % 5) for s in range(1, 13)]
    broad = pdr.compare_reports(_report(rows_a), _report(rows_b))
    named = pdr.compare_reports(_report(rows_a), _report(rows_b), primary="spells_cast")
    assert named["metrics"]["spells_cast"]["role"] == "primary"
    assert named["metrics"]["turns"]["role"] == "exploratory"
    assert named["metrics"]["spells_cast"]["p_adjusted"] == named["metrics"]["spells_cast"]["p"]
    assert named["family_size"] == broad["family_size"] - 1
    assert (
        named["metrics"]["spells_cast"]["p_adjusted"]
        <= broad["metrics"]["spells_cast"]["p_adjusted"]
    )


def test_an_unknown_primary_metric_is_refused() -> None:
    rows = [_row(s, spells_cast=float(s)) for s in range(1, 13)]
    with pytest.raises(ValueError, match="not among the compared metrics"):
        pdr.compare_reports(_report(rows), _report(rows), primary="wins")


def test_comparing_many_metrics_flags_noise_by_interval_but_not_after_holm() -> None:
    """The reason for the protocol: pilots that differ in nothing, eight metrics looked at."""
    result = pdr.calibrate_report(_noise_report(16, seed=7), rounds=80, resamples=200, flips=256)
    assert result["pairs"] == 8
    assert result["any_metric_flagged_by_interval"] >= 0.25
    assert result["any_metric_significant_after_holm"] <= 0.10


def test_calibration_is_seeded_and_needs_enough_games() -> None:
    report = _noise_report(12, seed=3)
    first = pdr.calibrate_report(report, rounds=10, resamples=100, flips=64)
    assert first == pdr.calibrate_report(report, rounds=10, resamples=100, flips=64)
    with pytest.raises(ValueError, match="at least 6 ok games"):
        pdr.calibrate_report(_noise_report(5, seed=3), rounds=2)


def test_calibration_sees_a_real_difference_that_the_null_split_does_not_have() -> None:
    """Negative control: the same code path flags an arm that really is shifted."""
    rows_a = [_row(s, spells_cast=40.0 + s % 4) for s in range(1, 13)]
    rows_b = [_row(s, spells_cast=47.0 + s % 4) for s in range(1, 13)]
    result = pdr.compare_reports(_report(rows_a), _report(rows_b))
    assert result["metrics"]["spells_cast"]["significant"]


def test_master_seeds_are_reproducible_distinct_and_depend_on_the_master() -> None:
    first = bench.master_seeds("plan-a", 40)
    assert first == bench.master_seeds("plan-a", 40)
    assert len(set(first)) == 40
    assert first != bench.master_seeds("plan-b", 40)
    assert bench.master_seeds("plan-a", 5) == first[:5]
    assert all(1 <= seed < 2**31 for seed in first)
    assert bench._seeds("hash:plan-a:40") == first
    assert bench._seeds("hash:a:b:3") == bench.master_seeds("a:b", 3)
    assert bench._seeds("1-3,7") == [1, 2, 3, 7]


@pytest.mark.parametrize("text", ["hash:plan", "hash::5", "hash:plan:x"])
def test_a_malformed_seed_set_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="hash:MASTER:COUNT"):
        bench._seeds(text)


def test_compare_prints_primary_adjusted_p_and_a_markdown_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows_a = [_row(s, spells_cast=40.0 + s % 3) for s in range(1, 13)]
    rows_b = [_row(s, spells_cast=46.0 + s % 3) for s in range(1, 13)]
    path_a, path_b, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "c.json"
    path_a.write_text(json.dumps(_report(rows_a)), encoding="utf-8")
    path_b.write_text(json.dumps(_report(rows_b)), encoding="utf-8")
    args = argparse.Namespace(a=path_a, b=path_b, json=out, primary="spells_cast", markdown=True)
    assert pdr.compare(args) == 0
    text = capsys.readouterr().out
    assert "PRIMARY spells_cast: CHANGED" in text
    assert "| **spells_cast** (primary) |" in text
    assert "adjusted p" in text
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["primary"] == "spells_cast"
    assert payload["metrics"]["spells_cast"]["significant"] is True
    assert payload["metrics"]["turns"]["role"] == "exploratory"


def test_without_a_primary_metric_the_output_says_every_row_is_exploratory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [_row(s, spells_cast=40.0 + s) for s in range(1, 13)]
    path_a, path_b = tmp_path / "a.json", tmp_path / "b.json"
    for path in (path_a, path_b):
        path.write_text(json.dumps(_report(rows)), encoding="utf-8")
    assert pdr.compare(argparse.Namespace(a=path_a, b=path_b, json=None)) == 0
    assert "no primary metric named" in capsys.readouterr().out


def test_a_metric_whose_interval_excludes_zero_but_not_the_adjusted_p_is_called_ci_only() -> None:
    """Eight pairs, eight moving metrics: +1 in every pair gives p = 2/256, Holm x 8 = 0.0625."""
    others = [k for k in NOISY if k != "turns"]
    rows_a = [_row(s, **{k: 50.0 for k in NOISY}) for s in range(1, 9)]
    rows_b = [
        _row(s, **{"turns": 51.0, **{k: 50.0 + (1.0 if s % 2 else -1.0) for k in others}})
        for s in range(1, 9)
    ]
    result = pdr.compare_reports(_report(rows_a), _report(rows_b))
    turns = result["metrics"]["turns"]
    assert result["family_size"] == 8
    assert turns["ci95"] == [1.0, 1.0] and turns["changed"]
    assert turns["p"] == pytest.approx(2 / 256)
    assert turns["p_adjusted"] == pytest.approx(8 * 2 / 256)
    assert not turns["significant"]
    assert pdr._verdict(turns) == "ci only"
    # The same shift is CHANGED when it is the one metric the change was judged on.
    named = pdr.compare_reports(_report(rows_a), _report(rows_b), primary="turns")
    assert named["metrics"]["turns"]["significant"]
    assert pdr._verdict(named["metrics"]["turns"]) == "CHANGED"
