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
