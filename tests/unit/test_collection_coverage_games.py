from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_collection_coverage_games as coverage  # noqa: E402


@pytest.mark.parametrize("size", [4, 5, 6])
def test_every_deck_plays_in_a_pod_of_every_size(size: int) -> None:
    pods = coverage.coverage_pods(18, size)
    assert {deck for pod in pods for deck in pod} == set(range(18))
    assert all(len(pod) == size and len(set(pod)) == size for pod in pods)


def test_the_collection_has_eighteen_loadable_decks() -> None:
    decks = coverage._load_decks()
    assert len(decks) == 18
    assert len({deck.deck_id for deck in decks}) == 18
    assert all(deck.deck_hash for deck in decks)


def test_batched_twins_play_in_two_processes_in_reverse_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batches: list[list[int]] = []

    def fake_batch(_command: object, jobs: list[tuple[object, int]], _max: int) -> list[dict]:
        batches.append([seed for _, seed in jobs])
        return [{"status": "ok", "semantic": f"s{seed}", "wall_s": 0.0} for _, seed in jobs]

    monkeypatch.setattr(coverage, "_play_batch", fake_batch)
    decks = tuple(coverage._load_decks()[:4])
    pods = coverage.play_pods_batched(("java",), [(decks, 1), (decks, 2), (decks, 3)], 10)
    assert batches == [[1, 2, 3], [3, 2, 1]]
    assert [pod["seed"] for pod in pods] == [1, 2, 3]
    assert all(pod["twin"] == "identical" for pod in pods)


def test_games_per_jvm_must_be_positive() -> None:
    with pytest.raises(SystemExit):
        coverage.main(["--jar", "x.jar", "--out", "x.json", "--games-per-jvm", "0"])


@pytest.mark.parametrize(
    ("first", "second", "label"),
    [
        ({"status": "ok", "semantic": "a"}, {"status": "ok", "semantic": "a"}, "identical"),
        ({"status": "ok", "semantic": "a"}, {"status": "ok", "semantic": "b"}, "DIVERGED"),
        ({"status": "ok", "semantic": "a"}, {"status": "failed", "error": "x"}, "not_compared"),
        ({"status": "failed", "error": "x"}, {"status": "failed", "error": "x"}, "not_compared"),
    ],
)
def test_play_pod_labels_the_twin_pair(
    monkeypatch: pytest.MonkeyPatch, first: dict, second: dict, label: str
) -> None:
    runs = iter([first, second])
    monkeypatch.setattr(coverage, "_play_once", lambda *_args: next(runs))
    decks = tuple(coverage._load_decks()[:4])
    pod = coverage.play_pod(("java",), decks, 7, 10)
    assert pod["twin"] == label
    assert pod["runs"] == [first, second]
    assert (pod["size"], pod["seed"]) == (4, 7)
