import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECKS = sorted((ROOT / "data/coverage_decks/collection").glob("*.json"))
COLLECTION = ROOT / "data/collections/owner_collection_2026-10-12.txt"
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def _collection_names() -> set[str]:
    names = set()
    for line in COLLECTION.read_text(encoding="utf-8").splitlines():
        if line.strip():
            names.add(line.strip())
            # XMage names double-faced and adventure cards by their front face.
            names.add(line.strip().split(" // ")[0])
    return names


def _cards(deck: dict) -> Counter:
    return Counter({e["oracle_name"]: e["quantity"] for e in deck["cards"]})


def test_eighteen_singleton_decks_of_100_cards_from_the_collection():
    owned = _collection_names()
    assert len(DECKS) == 18
    for path in DECKS:
        deck = json.loads(path.read_text(encoding="utf-8"))
        cards = _cards(deck)
        assert sum(cards.values()) == 100, path.name
        assert [e["oracle_name"] for e in deck["cards"] if e["zone"] == "commander"] == deck[
            "commander"
        ]["commanders"]
        assert {n for n, q in cards.items() if q > 1} <= BASICS, path.name
        assert set(cards) <= owned, sorted(set(cards) - owned)


def test_non_basic_cards_are_used_by_at_most_one_deck():
    seen: Counter = Counter()
    for path in DECKS:
        seen.update(
            n for n in _cards(json.loads(path.read_text(encoding="utf-8"))) if n not in BASICS
        )
    assert [n for n, count in seen.items() if count > 1] == []
    assert len(seen) == 1254
