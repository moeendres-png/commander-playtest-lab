from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANT_DIR = ROOT / "data" / "decks" / "pretest_variants"


def _cards(path: Path) -> Counter[str]:
    cards: Counter[str] = Counter()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        qty_text, name = line.split(" ", 1)
        cards[name] += int(qty_text)
    return cards


def _delta(left: Counter[str], right: Counter[str]) -> tuple[Counter[str], Counter[str]]:
    return left - right, right - left


def test_pretest_registry_references_four_100_card_variants() -> None:
    registry = json.loads((VARIANT_DIR / "registry.json").read_text(encoding="utf-8"))
    assert registry["status"] == "pretest_variants_not_ranked"
    assert registry["selection_policy"]["deduplicate_exact_card_multisets"] is True
    assert registry["selection_policy"]["automatic_winner"] is False

    for deck in ("korvold", "rogshai"):
        versions = registry["variants"][deck]
        assert [entry["version"] for entry in versions] == ["V0.1.1", "V0.1.2"]
        for entry in versions:
            path = ROOT / entry["path"]
            assert path.is_file()
            assert sum(_cards(path).values()) == 100


def test_v012_is_exactly_the_checked_in_current_baseline() -> None:
    assert _cards(VARIANT_DIR / "korvold_V0.1.2.txt") == _cards(
        ROOT / "data" / "decks" / "korvold_current.txt"
    )
    assert _cards(VARIANT_DIR / "rogshai_V0.1.2.txt") == _cards(
        ROOT / "data" / "decks" / "rogshai_current.txt"
    )


def test_korvold_fresh_delta_is_exactly_two_swaps() -> None:
    old = _cards(VARIANT_DIR / "korvold_V0.1.1.txt")
    new = _cards(VARIANT_DIR / "korvold_V0.1.2.txt")
    removed, added = _delta(old, new)
    assert removed == Counter({"Eumidian Wastewaker": 1, "Llanowar Elves": 1})
    assert added == Counter({"Exploration Broodship": 1, "Orcish Lumberjack": 1})


def test_rogshai_fresh_delta_is_exactly_three_land_swaps() -> None:
    old = _cards(VARIANT_DIR / "rogshai_V0.1.1.txt")
    new = _cards(VARIANT_DIR / "rogshai_V0.1.2.txt")
    removed, added = _delta(old, new)
    assert removed == Counter(
        {"Mystic Monastery": 1, "Temple of Epiphany": 1, "Coastal Peak": 1}
    )
    assert added == Counter(
        {"Frostboil Snarl": 1, "Scorched Geyser": 1, "Turbulent Springs": 1}
    )
