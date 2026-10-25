"""The deck guides in data/deck_guides stay consistent with the deck pool.

A guide is a set of hypotheses about one deck; what can be checked without playing is that it
describes the deck it is filed under: same commander, cards that are in the list, parameters
inside their documented bounds, and one guide for every deck the project plays.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.models.pilots import PilotUtilityWeights

ROOT = Path(__file__).resolve().parents[2]
GUIDES = ROOT / "data" / "deck_guides" / "guides"
POOL_DIRECTORIES = ("precons", "precon_variants")
OWNER_DECKS = {"custom/rogshai", "custom/chulane"}
CLASSES = {"REAL", "SYNTHETIC", "ORIGINAL_MIT_PROXY", "FOKUS"}
REQUIRED_KEYS = frozenset(
    {
        "schema",
        "deck_id",
        "guide_slug",
        "deck_name",
        "deck_klasse",
        "evidenz",
        "commander",
        "farbidentitaet",
        "manabasis",
        "kurve",
        "rollen",
        "archetypen",
        "win_plan",
        "schluesselkarten",
        "keep_test",
        "utility_deltas",
        "bedrohung",
        "sequenzierung",
        "pakete",
        "proxy",
    }
)
# FORMAT.md section 3: the generator caps every delta at this size.
MAX_DELTA = 0.5
# The synthetic replacement decks live in precon_variants/ under this id prefix.
SYNTHETIC_PREFIX = "precon-synthetic/"


def _guides() -> dict[str, dict[str, Any]]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(GUIDES.glob("*.json"))
    }


def _pool() -> dict[str, dict[str, Any]]:
    pool: dict[str, dict[str, Any]] = {}
    for directory in POOL_DIRECTORIES:
        for path in sorted((ROOT / "data" / "decks" / directory).glob("*.json")):
            deck = json.loads(path.read_text(encoding="utf-8"))
            pool[str(deck["deck_id"])] = deck
    return pool


def _front_face(name: str) -> str:
    return name.split(" // ")[0]


def test_every_pool_deck_has_exactly_one_guide_and_nothing_else_does() -> None:
    guided = {guide["deck_id"] for guide in _guides().values()}
    assert guided - OWNER_DECKS == set(_pool()), "regenerate data/deck_guides for the current pool"
    assert guided >= OWNER_DECKS
    assert len(guided) == len(_guides()), "two guides share one deck_id"


def test_every_json_guide_has_its_markdown_partner_and_a_matching_slug() -> None:
    for slug, guide in _guides().items():
        assert guide["guide_slug"] == slug
        expected = guide["deck_id"].removeprefix("custom/").replace("/", "_")
        assert expected == slug
        assert (GUIDES / f"{slug}.md").is_file(), slug
    assert {path.stem for path in GUIDES.glob("*.md")} == set(_guides())


def test_every_guide_carries_the_required_fields_and_a_known_class() -> None:
    for slug, guide in _guides().items():
        assert guide["schema"] == "deck-guide/1", slug
        assert guide.keys() >= REQUIRED_KEYS, (slug, sorted(REQUIRED_KEYS - guide.keys()))
        assert guide["deck_klasse"] in CLASSES, slug
        assert guide["evidenz"], slug


def test_the_class_follows_the_deck_it_describes() -> None:
    pool = _pool()
    for slug, guide in _guides().items():
        deck_id = guide["deck_id"]
        if deck_id in OWNER_DECKS:
            assert guide["deck_klasse"] == "FOKUS", slug
        elif deck_id.startswith(SYNTHETIC_PREFIX):
            assert guide["deck_klasse"] == "SYNTHETIC", slug
        else:
            assert guide["deck_klasse"] in {"REAL", "ORIGINAL_MIT_PROXY"}, slug
            assert deck_id in pool, slug


def test_the_commander_and_the_named_cards_belong_to_the_deck() -> None:
    pool = _pool()
    for slug, guide in _guides().items():
        deck = pool.get(guide["deck_id"])
        if deck is None:
            continue  # the Owner decks are not part of the precon pool
        assert {_front_face(name) for name in guide["commander"]} == {
            _front_face(name) for name in deck["commander"]["commanders"]
        }, slug
        listed = {card["oracle_name"] for card in deck["cards"]}
        named = list(guide["schluesselkarten"]) + [
            card for package in guide["pakete"] for card in package["karten"]
        ]
        assert [card for card in named if card not in listed] == [], slug


def test_utility_deltas_are_weight_names_inside_their_bounds() -> None:
    weights = set(PilotUtilityWeights.model_fields)
    for slug, guide in _guides().items():
        numbers = {
            name: value
            for name, value in guide["utility_deltas"].items()
            if isinstance(value, int | float) and not isinstance(value, bool)
        }
        assert numbers.keys() <= weights, (slug, sorted(numbers.keys() - weights))
        assert all(abs(value) <= MAX_DELTA for value in numbers.values()), slug


@pytest.mark.parametrize("field", ["keep_test", "manabasis", "kurve"])
def test_the_mulligan_window_and_the_mana_base_are_consistent(field: str) -> None:
    for slug, guide in _guides().items():
        section = guide[field]
        if field == "keep_test":
            assert 0 <= section["laender_min"] <= section["laender_max"], slug
            assert section["laender_max"] <= section["laender_max_gezogen"], slug
            assert section["nie_unter_karten"] >= 1, slug
        elif field == "manabasis":
            assert section["laender_gesamt"] >= 0, slug
        else:
            assert section["durchschnitt_nonland"] >= 0, slug
