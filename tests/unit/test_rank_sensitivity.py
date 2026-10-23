"""Pilot sensitivity of the deck ranking (S-1): tau, the swap test, the verdicts, the play step."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "rank_sensitivity", ROOT / "scripts/rank_sensitivity.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rank = _module()
DECKS = ["d0", "d1", "d2", "d3"]
FAST = {"flips": 300, "split_rounds": 60}


def _games(strengths: list[float], seeds: int, rng_seed: int, pod: str = "p0") -> list[dict]:
    """Every deck in every seat for each seed; the winner drawn in proportion to strength."""
    rng = random.Random(rng_seed)
    rows = []
    for seed in range(1, seeds + 1):
        for rotation, order in enumerate(rank.rotations(DECKS)):
            weights = [strengths[DECKS.index(deck)] for deck in order]
            winner = rng.choices(range(4), weights=weights)[0]
            rows.append(
                {
                    "pod": pod,
                    "seed": seed,
                    "rotation": rotation,
                    "decks": list(order),
                    "winners": [winner],
                }
            )
    return rows


def test_tau_is_one_for_equal_order_and_minus_one_for_reversed() -> None:
    assert rank.kendall_tau_b([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert rank.kendall_tau_b([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_tau_b_corrects_for_ties_and_is_undefined_when_one_side_is_flat() -> None:
    # one pair tied on x: (3 concordant, 0 discordant, 1 tie on x) over 4 items
    value = rank.kendall_tau_b([1, 1, 2, 3], [1, 2, 3, 4])
    assert value == pytest.approx(5 / (5 * 6) ** 0.5)
    assert rank.kendall_tau_b([2, 2, 2, 2], [1, 2, 3, 4]) is None


def test_credit_shares_a_win_and_gives_nothing_for_a_draw() -> None:
    row = {"decks": DECKS, "winners": [1]}
    assert rank.credit(row) == {"d0": 0.0, "d1": 1.0, "d2": 0.0, "d3": 0.0}
    assert rank.credit({"decks": DECKS, "winners": [0, 3]})["d3"] == 0.5
    assert sum(rank.credit({"decks": DECKS, "winners": []}).values()) == 0.0


def test_a_block_is_the_mean_over_its_rotations() -> None:
    rows = [
        {"pod": "p", "seed": 1, "decks": DECKS, "winners": [0]},
        {"pod": "p", "seed": 1, "decks": DECKS, "winners": [1]},
    ]
    assert rank.block_scores(rows)[("p", 1)] == {"d0": 0.5, "d1": 0.5, "d2": 0.0, "d3": 0.0}


def test_rotations_put_every_deck_in_every_seat_once() -> None:
    orders = rank.rotations(DECKS)
    assert len(orders) == 4
    for seat in range(4):
        assert sorted(order[seat] for order in orders) == DECKS


def test_a_pod_must_keep_its_four_decks() -> None:
    rows = [
        {"pod": "p", "decks": DECKS, "winners": []},
        {"pod": "p", "decks": ["d0", "d1", "d2", "x"], "winners": []},
    ]
    with pytest.raises(ValueError, match="different decks"):
        rank.pod_decks(rows)


def test_equal_variants_show_no_difference_and_say_it_is_only_not_detected() -> None:
    strengths = [0.55, 0.30, 0.10, 0.05]
    variants = {
        "a": _games(strengths, 40, 1),
        "b": _games(strengths, 40, 2),
    }
    result = rank.analyze(variants, **FAST)
    pair = result["pairs"]["a vs b"]
    assert pair["verdict"] == rank.NOT_DETECTED
    assert result["variants"]["a"]["split_half_tau"] >= rank.RESOLVED_TAU


def test_a_variant_that_reverses_the_strengths_is_rank_sensitive_and_names_the_decks() -> None:
    variants = {
        "a": _games([0.55, 0.30, 0.10, 0.05], 40, 1),
        "b": _games([0.05, 0.10, 0.30, 0.55], 40, 2),
    }
    pair = rank.analyze(variants, **FAST)["pairs"]["a vs b"]
    assert pair["verdict"] == rank.RANK_SENSITIVE
    assert pair["tau_observed"] < 0
    reversed_decks = {tuple(r["decks"]) for r in pair["reversed_pairs"]}
    assert ("d0", "d3") in reversed_decks  # the two ends swapped places
    moved = {k for k, v in pair["deck_changes"].items() if v["p_holm"] < 0.05}
    assert {"p0/d0", "p0/d3"} <= moved


def test_decks_of_equal_strength_leave_the_sensitivity_unresolved() -> None:
    flat = [0.25, 0.25, 0.25, 0.25]
    variants = {"a": _games(flat, 40, 3), "b": _games(flat, 40, 4)}
    pair = rank.analyze(variants, **FAST)["pairs"]["a vs b"]
    assert pair["verdict"] == rank.UNRESOLVED
    assert sorted(pair["unresolved_variants"]) == ["a", "b"]


def test_a_pod_with_too_few_paired_blocks_is_not_judged() -> None:
    strengths = [0.4, 0.3, 0.2, 0.1]
    variants = {"a": _games(strengths, 19, 5), "b": _games(strengths, 19, 6)}
    pair = rank.analyze(variants, **FAST)["pairs"]["a vs b"]
    assert pair["verdict"] == rank.TOO_FEW_BLOCKS
    assert pair["blocks_per_pod"] == {"p0": 19}


def test_only_blocks_both_variants_played_are_compared() -> None:
    strengths = [0.4, 0.3, 0.2, 0.1]
    a = _games(strengths, 40, 7)
    b = [row for row in _games(strengths, 40, 8) if row["seed"] <= 25]
    pair = rank.analyze({"a": a, "b": b}, **FAST)["pairs"]["a vs b"]
    assert pair["blocks_per_pod"] == {"p0": 25}


def test_the_same_data_gives_the_same_answer() -> None:
    variants = {
        "a": _games([0.5, 0.3, 0.15, 0.05], 30, 9),
        "b": _games([0.3, 0.5, 0.05, 0.15], 30, 10),
    }
    assert rank.analyze(variants, **FAST) == rank.analyze(variants, **FAST)


def test_variants_with_different_decks_in_a_pod_are_refused() -> None:
    other = _games([0.4, 0.3, 0.2, 0.1], 25, 11)
    for row in other:
        row["decks"] = ["d0", "d1", "d2", "d9"]
    with pytest.raises(ValueError, match="different variants"):
        rank.analyze({"a": _games([0.4, 0.3, 0.2, 0.1], 25, 12), "b": other}, **FAST)


def test_analyze_reads_tables_from_disk_and_skips_failed_games(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    strengths = [0.55, 0.30, 0.10, 0.05]
    paths = []
    for name, seed in (("a", 21), ("b", 22)):
        games = _games(strengths, 30, seed)
        games.append({**games[0], "seed": 999, "status": "failed", "winners": []})
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"variant": name, "games": games}), encoding="utf-8")
        paths.append(str(path))
    out = tmp_path / "result.json"
    assert rank.main(["analyze", *paths, "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "a vs b" in printed
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["variants"]["a"]["blocks"] == 30  # the failed game's seed 999 is not a block


class _Inline:
    """A process pool that runs each job at once in this process."""

    def __init__(self, max_workers: int) -> None:
        pass

    def __enter__(self) -> _Inline:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def submit(self, fn: Any, *args: Any) -> Future[Any]:
        future: Future[Any] = Future()
        future.set_result(fn(*args))
        return future


def test_play_rotates_every_pod_over_all_seats_and_labels_the_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    played: list[tuple[str, int]] = []

    class Bench:
        @staticmethod
        def _seeds(text: str) -> list[int]:
            return [1, 2]

        @staticmethod
        def bridge_command(jar: Path, options: list[str]) -> tuple[str, ...]:
            return ("java", str(jar), *options)

        @staticmethod
        def _setup(paths: tuple[Path, ...]) -> tuple[str, ...]:
            return tuple(p.stem for p in paths)

    class Report:
        @staticmethod
        def _play(command: Any, pod: str, setup: Any, seed: int) -> dict[str, Any]:
            played.append((pod, seed))
            return {"pod": pod, "seed": seed, "status": "ok", "winners": [1], "semantic": "h"}

    monkeypatch.setitem(sys.modules, "benchmark_xmage_full_games", Bench)
    monkeypatch.setitem(sys.modules, "pilot_decision_report", Report)
    monkeypatch.setattr(rank, "ProcessPoolExecutor", _Inline)
    out = tmp_path / "games.json"
    code = rank.main(
        [
            "play",
            "--jar",
            "x.jar",
            "--variant",
            "v1",
            "--out",
            str(out),
            "--pod",
            "w.json,x.json,y.json,z.json",
        ]
    )
    assert code == 0
    table = json.loads(out.read_text(encoding="utf-8"))
    assert table["variant"] == "v1"
    assert len(table["games"]) == 8  # 4 rotations x 2 seeds
    rotation_two = next(g for g in table["games"] if g["rotation"] == 2)
    assert rotation_two["pod"] == "pod0"
    assert rotation_two["decks"] == ["y", "z", "w", "x"]
    assert {seed for _pod, seed in played} == {1, 2}
    # The engine reports seat 1 as the winner; the table holds the index 0 into the seat order.
    assert all(g["winners"] == [0] for g in table["games"])


def test_a_winner_index_outside_the_seats_is_refused() -> None:
    with pytest.raises(ValueError, match="outside"):
        rank.credit({"decks": DECKS, "winners": [4]})


def test_two_neighbours_that_swap_places_are_found_as_that_pair() -> None:
    variants = {
        "a": _games([0.45, 0.30, 0.15, 0.10], 120, 31),
        "b": _games([0.45, 0.15, 0.30, 0.10], 120, 32),
    }
    pair = rank.analyze(variants, **FAST)["pairs"]["a vs b"]
    assert pair["verdict"] == rank.RANK_SENSITIVE
    assert [r["decks"] for r in pair["reversed_pairs"]] == [["d1", "d2"]]


def test_a_shift_in_strength_that_keeps_the_order_is_not_a_reversal() -> None:
    variants = {
        "a": _games([0.50, 0.25, 0.15, 0.10], 120, 33),
        "b": _games([0.40, 0.30, 0.18, 0.12], 120, 34),
    }
    pair = rank.analyze(variants, **FAST)["pairs"]["a vs b"]
    assert pair["reversed_pairs"] == []
    assert pair["verdict"] != rank.RANK_SENSITIVE
    assert pair["tau_observed"] == 1.0


def test_a_block_with_a_failed_rotation_is_dropped_from_every_variant() -> None:
    games_a = _games([0.4, 0.3, 0.2, 0.1], 10, 31)
    games_b = _games([0.4, 0.3, 0.2, 0.1], 10, 32)
    games_b[5]["status"] = "failed"  # seed 2, rotation 1
    tables = {"a": games_a, "b": games_b}
    kept, counts = rank.complete_blocks(tables)
    assert counts == {"blocks_played": 10, "blocks_kept": 9, "blocks_dropped": 1}
    for rows in kept.values():
        assert len(rows) == 36  # nine blocks of four rotations, seed 2 gone from both
        assert all(row["seed"] != 2 for row in rows)


def test_complete_blocks_keeps_everything_when_nothing_failed() -> None:
    games = _games([0.4, 0.3, 0.2, 0.1], 5, 33)
    kept, counts = rank.complete_blocks({"a": games, "b": [dict(g) for g in games]})
    assert counts["blocks_dropped"] == 0
    assert len(kept["a"]) == 20
