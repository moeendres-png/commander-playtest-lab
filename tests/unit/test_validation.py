from __future__ import annotations

import json
from pathlib import Path

from commander_lab.analysis import DeckValidator, validate_collection_quantities
from commander_lab.cards.catalog import CardCatalog
from commander_lab.models import (
    CardIdentity,
    CardLegality,
    Collection,
    Color,
    CommanderConfiguration,
    Deck,
    DeckEntry,
    DeckZone,
    PhysicalCard,
)
from commander_lab.storage import load_model


def test_local_current_decks_validate(repo_root: Path, catalog) -> None:
    validator = DeckValidator(catalog)
    for filename in ("korvold_current.json", "rogshai_current.json"):
        deck = load_model(repo_root / "data/decks" / filename, Deck)
        report = validator.validate(deck)
        assert report.valid, report.model_dump()


def test_off_color_card_is_rejected() -> None:
    catalog = CardCatalog(
        [
            CardIdentity(
                oracle_name="Green Commander",
                color_identity=frozenset({Color.GREEN}),
                legalities={"commander": CardLegality.LEGAL},
            ),
            CardIdentity(
                oracle_name="Blue Spell",
                color_identity=frozenset({Color.BLUE}),
                legalities={"commander": CardLegality.LEGAL},
            ),
            CardIdentity(
                oracle_name="Forest",
                color_identity=frozenset({Color.GREEN}),
                legalities={"commander": CardLegality.LEGAL},
                is_basic_land=True,
                max_deck_copies=None,
            ),
        ]
    )
    deck = Deck(
        deck_id="bad",
        name="bad",
        commander=CommanderConfiguration(commanders=("Green Commander",)),
        cards=[
            DeckEntry(oracle_name="Green Commander", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Blue Spell", zone=DeckZone.MAIN),
            DeckEntry(oracle_name="Forest", quantity=98, zone=DeckZone.MAIN),
        ],
    )
    report = DeckValidator(catalog).validate(deck)
    assert not report.valid
    assert any(issue.code == "color_identity" for issue in report.issues)


def test_singleton_violation_is_rejected(catalog) -> None:
    deck = Deck(
        deck_id="bad-singleton",
        name="bad-singleton",
        commander=CommanderConfiguration(commanders=("Korvold, Fae-Cursed King",)),
        cards=[
            DeckEntry(oracle_name="Korvold, Fae-Cursed King", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Sol Ring", quantity=2),
            DeckEntry(oracle_name="Forest", quantity=97),
        ],
    )
    report = DeckValidator(catalog).validate(deck)
    assert any(issue.code == "singleton" for issue in report.issues)


def test_physical_quantity_conflict_is_rejected(catalog) -> None:
    deck_a = Deck(
        deck_id="a",
        name="a",
        commander=CommanderConfiguration(commanders=("Korvold, Fae-Cursed King",)),
        cards=[
            DeckEntry(oracle_name="Korvold, Fae-Cursed King", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Sol Ring"),
            DeckEntry(oracle_name="Forest", quantity=98),
        ],
    )
    deck_b = Deck(
        deck_id="b",
        name="b",
        commander=CommanderConfiguration(commanders=("Korvold, Fae-Cursed King",)),
        cards=[
            DeckEntry(oracle_name="Korvold, Fae-Cursed King", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Sol Ring"),
            DeckEntry(oracle_name="Forest", quantity=98),
        ],
    )
    collection = Collection(
        collection_id="tiny",
        name="tiny",
        cards=[
            PhysicalCard(copy_id="k", oracle_name="Korvold, Fae-Cursed King"),
            PhysicalCard(copy_id="s", oracle_name="Sol Ring"),
            PhysicalCard(copy_id="f", oracle_name="Forest", quantity=196),
        ],
    )
    report = validate_collection_quantities(collection, [deck_a, deck_b])
    assert not report.valid
    assert {issue.card_name for issue in report.issues} == {
        "Korvold, Fae-Cursed King",
        "Sol Ring",
    }


def test_partner_pairing_requires_partner_capability() -> None:
    catalog = CardCatalog(
        [
            CardIdentity(
                oracle_name="Commander A",
                color_identity=frozenset({Color.BLUE}),
                can_be_commander=True,
                legalities={"commander": CardLegality.LEGAL},
            ),
            CardIdentity(
                oracle_name="Commander B",
                color_identity=frozenset({Color.RED}),
                can_be_commander=True,
                legalities={"commander": CardLegality.LEGAL},
            ),
            CardIdentity(
                oracle_name="Island",
                color_identity=frozenset({Color.BLUE}),
                legalities={"commander": CardLegality.LEGAL},
                is_basic_land=True,
                max_deck_copies=None,
            ),
        ]
    )
    deck = Deck(
        deck_id="bad-partners",
        name="bad-partners",
        commander=CommanderConfiguration(
            commanders=("Commander A", "Commander B"),
            uses_partner=True,
        ),
        cards=[
            DeckEntry(oracle_name="Commander A", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Commander B", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Island", quantity=98),
        ],
    )
    report = DeckValidator(catalog).validate(deck)
    assert any(issue.code == "partner_pairing" for issue in report.issues)
