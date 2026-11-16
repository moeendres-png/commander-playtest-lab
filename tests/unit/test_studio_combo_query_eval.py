"""Offline Scryfall-query evaluator: colors, identity and type line (fail-closed, exact)."""

from __future__ import annotations

import pytest

from commander_lab.studio import combos


def _card(
    name: str,
    type_line: str,
    cost: str,
    colors: str,
    identity: str | None = None,
    keywords: frozenset[str] = frozenset(),
    colors_known: bool = True,
) -> dict[str, object]:
    return {
        "name": name,
        "front_name": name,
        "type_line": type_line,
        "oracle_text": "",
        "keywords": keywords,
        "mana_value": 1.0,
        "mana_cost": cost,
        "identity": frozenset(colors if identity is None else identity),
        "mana_colors": frozenset(colors),
        "colors_known": colors_known,
        "commander_legal": True,
        "power": None,
        "toughness": None,
    }


CARDS = [
    _card("Mono Blue", "Creature — Merfolk", "{U}", "U"),
    _card("Mono Red", "Instant", "{R}", "R"),
    _card("Azorius Duo", "Legendary Creature — Human Wizard", "{W}{U}", "WU"),
    _card("Esper Trio", "Legendary Artifact Creature — Construct", "{W}{U}{B}", "WUB"),
    _card("Sol Ring", "Artifact", "{1}", "", identity=""),
    _card("Eldrazi Devoid", "Creature — Eldrazi", "{3}{R}", "R", keywords=frozenset({"devoid"})),
    _card("Red Land Pinger", "Land", "", "", identity="R"),
]


def _names(query: str, cards: list[dict[str, object]] | None = None) -> list[str]:
    status, reason, hits = combos.evaluate_scryfall_query(query, cards or CARDS)
    assert status == "OK", (query, reason)
    return [str(c["name"]) for c in hits]


def _unknown(query: str, cards: list[dict[str, object]] | None = None) -> None:
    status, reason, hits = combos.evaluate_scryfall_query(query, cards or CARDS)
    assert status == "UNKNOWN", query
    assert reason
    assert hits == []


def test_type_is_case_insensitive_substring_of_the_type_line() -> None:
    assert _names("t:legend") == ["Azorius Duo", "Esper Trio"]
    assert _names('t:"legendary creature"') == ["Azorius Duo"]  # phrase = substring
    assert set(_names("t:ARTIFACT")) == {"Sol Ring", "Esper Trio"}
    assert _names('t:"artifact creature"') == ["Esper Trio"]
    assert _names("t:elemental") == []  # a real zero, not UNKNOWN
    assert "Mono Red" not in _names("-t:instant")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("c:blue", {"Mono Blue", "Azorius Duo", "Esper Trio"}),
        ("c:u", {"Mono Blue", "Azorius Duo", "Esper Trio"}),
        ("color:red", {"Mono Red"}),
        ("c:wu", {"Azorius Duo", "Esper Trio"}),
        ("c>=wu", {"Azorius Duo", "Esper Trio"}),
        ("c:azorius", {"Azorius Duo", "Esper Trio"}),
        ("c=azorius", {"Azorius Duo"}),
        ("c=esper", {"Esper Trio"}),
        ("c<=wu", {"Mono Blue", "Azorius Duo", "Sol Ring", "Eldrazi Devoid", "Red Land Pinger"}),
        ("c<wu", {"Mono Blue", "Sol Ring", "Eldrazi Devoid", "Red Land Pinger"}),
        ("c>u", {"Azorius Duo", "Esper Trio"}),
        ("c:c", {"Sol Ring", "Eldrazi Devoid", "Red Land Pinger"}),
        ("c:colorless", {"Sol Ring", "Eldrazi Devoid", "Red Land Pinger"}),
        ("-c:colorless", {"Mono Blue", "Mono Red", "Azorius Duo", "Esper Trio"}),
    ],
)
def test_color_semantics(query: str, expected: set[str]) -> None:
    assert set(_names(query)) == expected


@pytest.mark.parametrize(
    "query",
    [
        "c:m",
        "c:multicolor",
        "c:blueish",
        "c:bl",  # letters of the word blue, not color letters
        "c:wc",  # colorless mixed with a color
        "c:ux",
        "c>=colorless",
        "c<=c",
        "c!=u",
        "color:chaos",
        "id:esper",  # ':' for identity is not evaluated offline
        "id:wu",
        "id:m",
        "id:blue",
    ],
)
def test_unsupported_color_values_are_unknown(query: str) -> None:
    _unknown(query)


def test_identity_semantics() -> None:
    assert set(_names("id=esper")) == {"Esper Trio"}
    assert set(_names("id<=esper")) == {
        "Mono Blue",
        "Azorius Duo",
        "Esper Trio",
        "Sol Ring",
    }
    assert set(_names("id>=wu")) == {"Azorius Duo", "Esper Trio"}
    assert set(_names("identity=r")) == {"Mono Red", "Red Land Pinger", "Eldrazi Devoid"}
    assert set(_names("id:colorless")) == {"Sol Ring"}
    assert set(_names("id:c")) == {"Sol Ring"}
    assert set(_names("id=azorius")) == {"Azorius Duo"}


def test_color_of_a_card_without_certain_color_makes_the_count_unknown() -> None:
    indicator = _card("Indicator Card", "Creature — Kobold", "{0}", "", colors_known=False)
    _unknown("c:red", [*CARDS, indicator])
    _unknown("-c:blue", [*CARDS, indicator])
    # Identity and type queries do not depend on the card color.
    assert _names("t:kobold", [*CARDS, indicator]) == ["Indicator Card"]
    assert "Indicator Card" not in _names("id=esper", [*CARDS, indicator])


def test_colors_known_rule() -> None:
    assert combos._colors_known("{U}", "Creature") is True
    assert combos._colors_known("", "Basic Land — Island") is True
    assert combos._colors_known("", "Land Creature — Forest Dryad") is False
    assert combos._colors_known("", "Enchantment") is False
    assert combos._colors_known("{0}", "Artifact") is True
    assert combos._colors_known("{0}", "Legendary Creature — Kobold") is False
