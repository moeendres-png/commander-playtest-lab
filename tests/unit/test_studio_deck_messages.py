"""The data check of the deck builder speaks plain German (#1404 D7). Synthetic rows only."""

from __future__ import annotations

import re

from commander_lab.studio.decks import validate_rows

ENGLISH = re.compile(
    r"\b(cards?|copies|needed|free|not|the|are|is|has|outside|colors?|collection|reserved|unknown)\b"
)


def _row(name: str, **fields: object) -> dict[str, object]:
    row: dict[str, object] = {
        "card_id": f"id-{name}",
        "oracle_name": name,
        "zone": "main",
        "quantity": 1,
        "color_identity": "G",
        "type_line": "Creature",
        "oracle_text": "",
        "is_basic_land": 0,
        "commander_legal": 1,
        "available_lower_bound": 1,
        "reserved": 0,
    }
    row.update(fields)
    return row


def _issues(rows: list[dict[str, object]]) -> dict[str, str]:
    return {issue.code: issue.message for issue in validate_rows(rows)}  # type: ignore[arg-type]


def test_the_deck_size_message_is_german() -> None:
    rows = [_row("Boss", zone="commander", type_line="Legendary Creature")]
    rows += [_row(f"Card {i}") for i in range(100)]  # 101 cards with the commander
    assert _issues(rows)["deck_size"] == "101 Karten (ein Commander-Deck hat 100)"


def test_every_message_of_the_data_check_is_german() -> None:
    rows = [
        _row("Plain Boss", zone="commander", type_line="Creature", color_identity="G"),
        _row("Red Card", color_identity="R"),  # outside the identity
        _row("Twice", quantity=2, available_lower_bound=3),  # two copies
        _row("Unsure", commander_legal=None),
        _row("Banned", commander_legal=0),
        _row("Missing", available_lower_bound=None),  # not in the collection
        _row("Short", quantity=1, available_lower_bound=0, reserved=1),  # not free
    ]
    found = _issues(rows)
    assert set(found) == {
        "deck_size",
        "commander_type",
        "color_identity",
        "singleton",
        "legality_unknown",
        "not_legal",
        "not_owned",
        "not_available",
    }
    for code, message in found.items():
        assert not ENGLISH.search(message), (code, message)
    assert found["not_available"] == "Short: 1 benötigt, 0 frei (1 reserviert)"
    assert found["commander_type"].endswith("entscheidet die Regel-Engine")  # as the page note
    nobody = _issues([_row("Alone")])
    assert nobody["commander_count"] == "1 oder 2 Commander sind erforderlich"
