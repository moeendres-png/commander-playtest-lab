"""The Owner's Chulane list, its guide and the card data describe the same deck.

``data/decks/chulane_current.txt`` is the Owner's physical Commander deck. Three other places
state facts about it and have to follow when a card changes: the deck guide
(``data/deck_guides/guides/chulane.json``, its curve, roles, colour sources and named cards), the
engine card facts the Structural model reads (``data/cards/xmage_card_facts.json``) and the
printed-card catalog the pilots read (``data/cards/pilot_card_knowledge.json``). The collection
list (``data/collections/owner_collection_2026-10-12.txt``) holds the physical cards.

The guide figures are recomputed here with the formulas of ``data/deck_guides/FORMAT.md`` section
3 (the generator itself is not in the repository). They reproduced the figures of the guide of
2026-10-22 exactly before the card swap of 2026-10-31, so a mismatch means the list or the guide
moved without the other.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from commander_lab.agents.card_knowledge import card_facts, card_roles

ROOT = Path(__file__).resolve().parents[2]
DECK_LIST = ROOT / "data/decks/chulane_current.txt"
GUIDE = ROOT / "data/deck_guides/guides/chulane.json"
ENGINE_FACTS = ROOT / "data/cards/xmage_card_facts.json"
COLLECTION = ROOT / "data/collections/owner_collection_2026-10-12.txt"
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def _read_list() -> tuple[list[str], Counter[str]]:
    """The commander names and the quantities of the 'Deck' section."""
    commanders: list[str] = []
    deck: Counter[str] = Counter()
    section = ""
    for raw in DECK_LIST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line in {"Commander", "Deck"}:
            section = line
            continue
        match = re.match(r"^(\d+) (.+)$", line)
        if match is None:
            continue
        if section == "Commander":
            commanders.append(match.group(2))
        else:
            deck[match.group(2)] += int(match.group(1))
    return commanders, deck


def _guide() -> dict[str, object]:
    loaded = json.loads(GUIDE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _all_names() -> Counter[str]:
    commanders, deck = _read_list()
    names = Counter(deck)
    names.update(commanders)
    return names


def _front_face(name: str) -> str:
    return name.split(" // ")[0]


def test_the_list_is_a_100_card_commander_deck_led_by_the_guides_commander() -> None:
    commanders, deck = _read_list()
    assert commanders == _guide()["commander"]
    assert len(commanders) + sum(deck.values()) == 100
    assert sorted(name for name, count in deck.items() if count > 1 and name not in BASICS) == []
    assert not set(commanders) & set(deck)


def test_every_card_is_known_to_the_engine_and_to_the_pilots() -> None:
    engine = json.loads(ENGINE_FACTS.read_text(encoding="utf-8"))["cards"]
    names = sorted(_all_names())
    assert [name for name in names if name not in engine] == [], "no engine card facts"
    assert [name for name in names if card_facts(name) is None] == [], "no printed-card facts"


def test_the_collection_holds_every_card_of_the_list() -> None:
    owned = {
        _front_face(line.strip())
        for line in COLLECTION.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    missing = [name for name in _all_names() if name not in BASICS and name not in owned]
    assert missing == []


def test_the_guide_names_only_cards_of_the_list() -> None:
    guide = _guide()
    listed = set(_all_names())
    named: list[str] = list(guide["schluesselkarten"])  # type: ignore[call-overload]
    for package in guide["pakete"]:  # type: ignore[attr-defined]
        named.extend(package["karten"])
    for rule in guide["sequenzierung"]:  # type: ignore[attr-defined]
        named.extend(rule.get("karten", []))
    # one entry names an ability of a card in brackets: "Chulane, Teller of Tales (Fähigkeit)"
    named = [re.sub(r" \([^)]*\)$", "", name) for name in named]
    assert [name for name in named if name not in listed] == []


def test_the_guides_curve_roles_and_colour_figures_follow_the_list() -> None:
    guide = _guide()
    commanders, _ = _read_list()
    curve: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    lands = nonland = 0
    mana_value_sum = 0.0
    colour_sources = 0
    early_pips: Counter[str] = Counter()
    for name, count in _all_names().items():
        facts = card_facts(name)
        assert facts is not None, name
        for role in card_roles(facts):
            roles[role.value] += count
        if "land" in facts.types:
            lands += count
            continue
        nonland += count
        curve["7+" if facts.mana_value >= 7 else str(int(facts.mana_value))] += count
        mana_value_sum += facts.mana_value * count
        if facts.produced_mana:
            colour_sources += count
        if facts.mana_value <= 3 or name in commanders:
            for symbol in re.findall(r"\{([^}]+)\}", facts.mana_cost):
                early_pips.update({part: count for part in symbol.split("/") if part in "WUBRG"})

    manabasis = guide["manabasis"]
    assert isinstance(manabasis, dict)
    assert lands == manabasis["laender_gesamt"]
    assert colour_sources == manabasis["farbquellen_nichtland"]
    assert dict(early_pips) == manabasis["pip_bedarf_frueh"]

    expected_curve = guide["kurve"]
    assert isinstance(expected_curve, dict)
    assert {key: curve.get(key, 0) for key in expected_curve if key != "durchschnitt_nonland"} == {
        key: value for key, value in expected_curve.items() if key != "durchschnitt_nonland"
    }
    assert round(mana_value_sum / nonland, 2) == expected_curve["durchschnitt_nonland"]

    expected_roles = guide["rollen"]
    assert isinstance(expected_roles, dict)
    assert {role: roles.get(role, 0) for role in expected_roles} == expected_roles
