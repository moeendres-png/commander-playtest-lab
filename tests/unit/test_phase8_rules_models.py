from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.engine.rules import load_project_rules_decks
from commander_lab.models import RulesCardPrinting, RulesDeckInput, ValidationLevel


def test_project_rules_decks_are_exact_commander_decks(repo_root) -> None:
    decks = load_project_rules_decks(repo_root)
    assert set(decks) == {"rogshai/current"}

    rogshai = decks["rogshai/current"]
    assert len(rogshai.mainboard) == 98
    assert len(rogshai.commander_names) == 2
    assert len(rogshai.card_printings) == 100

    commander_printings = {
        printing.oracle_name: printing
        for printing in rogshai.card_printings
        if printing.zone == "commander"
    }
    assert set(commander_printings) == {
        "Ishai, Ojutai Dragonspeaker",
        "Rograkh, Son of Rohgahh",
    }

    ishai = commander_printings["Ishai, Ojutai Dragonspeaker"]
    assert (ishai.set_code, ishai.collector_number) == ("FCA", "53")

    rograkh = commander_printings["Rograkh, Son of Rohgahh"]
    assert (rograkh.set_code, rograkh.collector_number) == ("CMR", "197")


def test_rules_deck_input_rejects_non_100_card_deck() -> None:
    with pytest.raises(ValidationError):
        RulesDeckInput(
            deck_id="bad",
            name="Bad",
            commander_names=("Commander",),
            mainboard=("Card",) * 98,
        )


def test_rules_deck_input_accepts_exact_structured_printings() -> None:
    printings = (
        RulesCardPrinting(
            oracle_name="Commander",
            set_code="CMD",
            collector_number="1",
            zone="commander",
        ),
        *(
            RulesCardPrinting(
                oracle_name="Card",
                set_code="TST",
                collector_number=str(index),
                zone="main",
            )
            for index in range(1, 100)
        ),
    )

    deck = RulesDeckInput(
        deck_id="printed",
        name="Printed",
        commander_names=("Commander",),
        mainboard=("Card",) * 99,
        card_printings=printings,
    )

    assert len(deck.card_printings) == 100


def test_rules_deck_input_rejects_printing_multiset_mismatch() -> None:
    printings = (
        RulesCardPrinting(
            oracle_name="Commander",
            set_code="CMD",
            collector_number="1",
            zone="commander",
        ),
        *(
            RulesCardPrinting(
                oracle_name="Card",
                set_code="TST",
                collector_number=str(index),
                zone="main",
            )
            for index in range(1, 99)
        ),
        RulesCardPrinting(
            oracle_name="Wrong Card",
            set_code="TST",
            collector_number="99",
            zone="main",
        ),
    )

    with pytest.raises(ValidationError, match="card printings do not exactly match deck zones"):
        RulesDeckInput(
            deck_id="bad-printing",
            name="Bad Printing",
            commander_names=("Commander",),
            mainboard=("Card",) * 99,
            card_printings=printings,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("set_code", " "),
        ("collector_number", ""),
    ),
)
def test_rules_card_printing_rejects_blank_identity_fields(field: str, value: str) -> None:
    payload = {
        "oracle_name": "Card",
        "set_code": "TST",
        "collector_number": "1",
        "zone": "main",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        RulesCardPrinting(**payload)


def test_validation_levels_are_exactly_the_three_required_values() -> None:
    assert {item.value for item in ValidationLevel} == {
        "structural_only",
        "tactical_oracle",
        "external_rules_engine",
    }
