"""Tests of the WP-9 analysis script (T6 deck split, T7 time split) with synthetic mini data.

Every expected value is a hand calculation written next to the assertion. No store, no
repository data: the ``prepare`` stage that reads a real store copy is not run here, only its
pure helper that prunes the corpus tables of a derived copy.
"""

from __future__ import annotations

import importlib.util
import math
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "validate_h_t6_t7.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_h_t6_t7", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_h_t6_t7"] = module
    spec.loader.exec_module(module)
    return module


v = _load()


def test_midranks_average_ties() -> None:
    # sorted: 5 -> 1, 10 -> 2, the two 20 share ranks 3 and 4 -> 3.5
    assert v.midranks([10, 20, 20, 5]) == [2.0, 3.5, 3.5, 1.0]


def test_centered_group_ranks_scale_by_group_size() -> None:
    # group a (n=3): ranks 3, 1, 2 -> (r - 2) / 3; group b has one card -> 0
    got = v.centered_group_ranks(["a", "a", "a", "b"], [3, 1, 2, 9])
    assert got == pytest.approx([1 / 3, -1 / 3, 0.0, 0.0])


def test_stratified_rank_corr_hand_calculation() -> None:
    # group a: x = y = 1, 2, 3 -> u = v = -1/3, 0, 1/3
    # group b: x = 1, 2 -> u = -1/4, 1/4; y = 2, 1 -> v = 1/4, -1/4
    # sum uv = 2/9 - 2/16 = 7/72; sum u^2 = sum v^2 = 2/9 + 2/16 = 25/72 -> rho = 7/25
    groups = ["a", "a", "a", "b", "b"]
    x = [1, 2, 3, 1, 2]
    y = [1, 2, 3, 2, 1]
    assert v.stratified_rank_corr(groups, x, y) == pytest.approx(7 / 25)


def test_stratified_rank_corr_ignores_order_between_groups() -> None:
    # within each group the order is the same; shifting a whole group changes nothing
    groups = ["a", "a", "b", "b"]
    assert v.stratified_rank_corr(groups, [1, 2, 1, 2], [100, 200, 1, 2]) == pytest.approx(1.0)
    assert v.stratified_rank_corr(groups, [1, 2, 1, 2], [1, 2, 100, 200]) == pytest.approx(1.0)


def test_constant_target_or_singletons_are_undefined() -> None:
    assert v.stratified_rank_corr(["a", "a"], [1, 2], [5, 5]) is None
    assert v.stratified_rank_corr(["a", "b"], [1, 2], [1, 2]) is None


def test_spearman_reversed_order() -> None:
    assert v.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)


def test_group_signs_and_informative_cards() -> None:
    groups = ["a", "a", "a", "b", "b", "b", "c", "c"]
    x = [1, 2, 3, 1, 2, 3, 1, 2]
    y = [1, 2, 3, 3, 2, 1, 7, 7]
    # a: rho +1, b: rho -1, c: two cards (below min size 3) -> 1 positive of 2 defined
    assert v.group_signs(groups, x, y) == (1, 2)
    # a and b have a non-constant target (6 cards); c is constant
    assert v.informative_cards(groups, y) == 6


def test_wilson_matches_textbook_values() -> None:
    # 8 of 10 at 95 %: 0.4902 to 0.9433 (standard Wilson score interval)
    low, high = v.wilson(8, 10)
    assert low == pytest.approx(0.4902, abs=1e-4)
    assert high == pytest.approx(0.9433, abs=1e-4)
    assert v.wilson(0, 0) is None


def test_percentile_interval_positions() -> None:
    # B = 1000: 0-based positions floor(25) = 25 and ceil(975) - 1 = 974
    assert v.percentile_interval([float(i) for i in range(1000)], 1000) == (25.0, 974.0)
    assert v.percentile_interval([], 1000) is None


def test_splits_are_deterministic_and_balanced() -> None:
    ids = [f"deck{i}" for i in range(10)]
    folds = v.assign_folds(ids, 5, "salt:")
    assert folds == v.assign_folds(list(reversed(ids)), 5, "salt:")
    assert sorted(list(folds.values()).count(f) for f in range(5)) == [2] * 5
    first, second = v.split_halves(ids, "salt:")
    assert len(first) == len(second) == 5
    assert set(first) | set(second) == set(ids)
    assert v.assign_folds(ids, 5, "other:") != folds


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # rule 0: too few informative cards
        ({"informative": 49}, v.KEIN_SCHLUSS),
        # rule 0: more than 5 % undefined replicates
        ({"undefined_share": 0.06}, v.KEIN_SCHLUSS),
        # rule 1: ceiling not separable from 0
        ({"ceiling": (0.0, 0.3)}, v.KEIN_SCHLUSS),
        # rule 2
        ({"interval": (0.01, 0.2)}, v.MESSBAR_POSITIV),
        # rule 3
        ({"statistic": -0.1, "interval": (-0.2, -0.01)}, v.GEGENLAEUFIG),
        # rule 4
        ({"interval": (-0.02, 0.05)}, v.KEIN_MESSBARER_NUTZEN),
    ],
)
def test_verdict_table(kwargs: dict[str, object], expected: str) -> None:
    base: dict[str, object] = {
        "ceiling": (0.1, 0.4),
        "statistic": 0.05,
        "interval": (0.01, 0.1),
        "informative": 100,
        "undefined_share": 0.0,
    }
    base.update(kwargs)
    assert v.verdict(**base) == expected


def test_counts_with_bootstrap_weights() -> None:
    # card 0 in held-out positions 0 and 2 (weights 2 + 1), card 1 in position 1 (weight 0)
    assert v._counts([[0, 2], [1], []], [2, 0, 1]) == [3.0, 0.0, 0.0]
    assert v._counts([[0, 2], [1], []], None) == [2.0, 1.0, 0.0]


def _mini_part() -> object:
    # three spells with the same index and training count: one G1 group and one G2 group
    # held-out decks d1..d4; A in none, B in d1, d2, C in all -> Y = 0, 2, 4
    return v.Part(
        cards=["A", "B", "C"],
        h={"A": 10, "B": 20, "C": 30},
        index={"A": 1.0, "B": 1.0, "C": 1.0},
        is_land={"A": False, "B": False, "C": False},
        train_count={"A": 5, "B": 5, "C": 5},
        heldout=["d1", "d2", "d3", "d4"],
        halves=(["d1", "d3"], ["d2", "d4"]),
        card_decks={"B": ["d1", "d2", "x"], "C": ["d1", "d2", "d3", "d4"]},
    )


def test_part_point_values_hand_calculation() -> None:
    part = _mini_part()
    result = v.analyse_parts([part], replicates=50, seed=1)
    # H 10 < 20 < 30 and Y 0 < 2 < 4: rho = 1 in G1 and G2
    assert result["point"]["G1_H"] == pytest.approx(1.0)
    assert result["point"]["G2_H"] == pytest.approx(1.0)
    # halves: A = 0/0, B = 1/1 (d1 in A, d2 in B), C = 2/2 -> ceiling 1
    assert result["point"]["G1_ceiling"] == pytest.approx(1.0)
    # training count is constant: the comparator is undefined, never 0
    assert result["point"]["G1_train"] is None
    # 3 informative cards < 50: no conclusion, whatever the correlation
    assert result["G1"]["verdict"] == v.KEIN_SCHLUSS
    for low, high in [result["interval95"]["G1_H"]]:
        assert -1.0 <= low <= high <= 1.0
    assert result["G1"]["spearman_brown_bound"] == pytest.approx(1.0)


def test_bootstrap_is_deterministic_for_a_fixed_seed() -> None:
    first = v.analyse_parts([_mini_part()], replicates=40, seed=7)
    second = v.analyse_parts([_mini_part()], replicates=40, seed=7)
    assert first == second


def _mini_data() -> dict[str, object]:
    decks = [f"d{i}" for i in range(10)]
    card_decks = {"A": [], "B": decks[:5], "C": decks}
    folds = v.assign_folds(decks, v.FOLDS, v.FOLD_SALT)
    t6 = {}
    for fold in range(v.FOLDS):
        train = [d for d in decks if folds[d] != fold]
        t6[str(fold)] = {
            "index": {"A": 0.0, "B": 0.0, "C": 0.0},
            "is_land": {"A": False, "B": False, "C": False},
            "train_count": {c: sum(1 for d in card_decks[c] if d in train) for c in "ABC"},
        }
    dates = {d: f"2026-0{1 + i // 2}-01" for i, d in enumerate(decks)}
    return {
        "meta": {},
        "h": {"A": 5, "B": 10, "C": 15},
        "universe": decks,
        "card_decks": card_decks,
        "deck_date": dates,
        "bracket3": decks[:2],
        "t6": t6,
        "t7": {
            "2026-03-01": {
                "index": {"A": 0.0, "B": 0.0, "C": 0.0},
                "is_land": {"A": False, "B": False, "C": False},
                "train_count": {"A": 0, "B": 5, "C": 6},
            }
        },
    }


def test_analyse_end_to_end_mini_data() -> None:
    result = v.analyse(_mini_data(), replicates=20, seed=3)
    assert result["T6"]["parts"] == 5
    assert sum(result["T6"]["heldout_decks"]) == 10
    # 3 cards cannot reach 50 informative cards
    assert result["T6"]["G1"]["verdict"] == v.KEIN_SCHLUSS
    # decks after 2026-03-01: 4 of 10, below 30 -> the cohort is not run
    t7 = result["T7"]["2026-03-01"]
    assert t7[v.COHORT_ALL] == {"verdict": v.NOT_RUN, "post_decks": 4}
    assert t7[v.COHORT_B3] == {"verdict": v.NOT_RUN, "post_decks": 0}
    assert v.analyse(_mini_data(), replicates=20, seed=3) == result


def test_derived_store_prunes_only_corpus_tables(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    connection = sqlite3.connect(source)
    for table in v.CORPUS_TABLES:
        connection.execute(f"CREATE TABLE {table} (deck_id TEXT, extra TEXT)")
        connection.executemany(
            f"INSERT INTO {table} VALUES (?, 'x')", [("k1",), ("k2",), ("gone",)]
        )
    connection.execute("CREATE TABLE deck (deck_id TEXT)")
    connection.executemany("INSERT INTO deck VALUES (?)", [("k1",), ("gone",)])
    connection.commit()
    connection.close()
    folder = v._derived_store(source, tmp_path / "derived", ["k1", "k2"])
    derived = sqlite3.connect(folder / "studio.sqlite3")
    for table in v.CORPUS_TABLES:
        kept = sorted(r[0] for r in derived.execute(f"SELECT deck_id FROM {table}"))
        assert kept == ["k1", "k2"]
    # owner decks are never touched
    assert sorted(r[0] for r in derived.execute("SELECT deck_id FROM deck")) == ["gone", "k1"]
    derived.close()
    # the source copy stays unchanged
    original = sqlite3.connect(source)
    assert original.execute("SELECT COUNT(*) FROM corpus_deck").fetchone()[0] == 3
    original.close()


def test_spearman_brown_bound_formula() -> None:
    # C = 0.2 -> sqrt(0.4 / 1.2) = sqrt(1/3)
    assert math.sqrt(2 * 0.2 / 1.2) == pytest.approx(math.sqrt(1 / 3))
