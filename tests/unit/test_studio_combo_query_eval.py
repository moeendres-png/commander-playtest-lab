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


def _unknown(query: str, cards: list[dict[str, object]] | None = None) -> str:
    status, reason, hits = combos.evaluate_scryfall_query(query, cards or CARDS)
    assert status == "UNKNOWN", query
    assert reason
    assert hits == []
    return reason


def test_type_is_case_insensitive_substring_of_the_type_line() -> None:
    assert _names("t:legend") == ["Azorius Duo", "Esper Trio"]
    assert _names('t:"legendary creature"') == ["Azorius Duo"]  # phrase = substring
    assert set(_names("t:ARTIFACT")) == {"Sol Ring", "Esper Trio"}
    assert _names('t:"artifact creature"') == ["Esper Trio"]
    assert _names("t:elemental") == []  # a real zero, not UNKNOWN
    assert "Mono Red" not in _names("-t:instant")


@pytest.mark.parametrize(
    "query",
    [
        "c:blue", "c:u", "color:red", "c:wu", "c>=wu", "c:azorius", "c=esper", "c<=wu",
        "c<wu", "c>u", "c:c", "c:colorless", "-c:colorless", "c:m", "c:multicolor",
        "c:blueish", "c:bl", "c:wc", "c>=colorless", "c!=u", "color:chaos", "c=r",
        "t:creature c:b",
        "id:esper", "id:wu", "id:m", "id:blue", "id:wc", "id>=colorless", "id!=u",
    ],
)  # fmt: skip
def test_card_color_and_unsupported_identity_values_are_unknown(query: str) -> None:
    # Card color is not exact from the mana cost (indicator, Prepare, DFC faces).
    assert _unknown(query).startswith("UNSUPPORTED_QUERY")


def test_prepare_and_dfc_color_cases_are_unknown_never_a_hit() -> None:
    prepare = _card(
        "Hallway Heckler // Vicious Verse", "Creature // Sorcery", "{2}{R} // {B/R}", "BR"
    )
    brigid = _card(
        "Brigid, Clachan's Heart // Brigid, Doun's Grace", "Legendary Creature", "{2}{W}", "W"
    )
    reasons = [
        _unknown(query, [prepare, brigid])
        for query in ("c:b", "c=r", "c>r", "c:g", "c=g", "c<=quandrix")
    ]
    assert len(reasons) == 6


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


def test_type_phrase_whitespace_is_normalized() -> None:
    cards = [
        _card("Forest", "Basic  Land — Forest", "", ""),
        _card("Sol Ring", "Artifact", "{1}", ""),
    ]
    assert _names('t:"basic  land"', cards) == ["Forest"]
    assert _names('t:"basic land"', cards) == ["Forest"]
    assert _names('t:" basic"', cards) == ["Forest"]
    assert _names('t:"land "', cards) == _names("t:land", cards) == ["Forest"]
    _unknown('t:" "', cards)
