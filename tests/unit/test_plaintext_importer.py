from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter


def test_import_current_rogshai(repo_root: Path, catalog) -> None:
    deck = PlaintextDeckImporter(catalog).import_file(
        repo_root / "data/decks/rogshai_current.txt",
        DeckImportOptions(
            deck_id="rogshai/current",
            name="RogShai current",
            commander_names=("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
            uses_partner=True,
        ),
    )
    assert deck.total_cards == 100
    assert deck.library_cards == 98
    assert deck.commander.commanders == (
        "Ishai, Ojutai Dragonspeaker",
        "Rograkh, Son of Rohgahh",
    )


def test_curly_apostrophe_normalizes_to_oracle_name(catalog) -> None:
    text = """
[Commander]
1 Korvold, Fae-Cursed King
[Mainboard]
1 Nature’s Claim
98 Forest
"""
    deck = PlaintextDeckImporter(catalog).import_text(
        text,
        DeckImportOptions(
            deck_id="test",
            name="test",
            commander_names=("Korvold, Fae-Cursed King",),
        ),
    )
    assert "Nature's Claim" in deck.quantities()


def test_unknown_card_is_rejected(catalog) -> None:
    text = """
[Commander]
1 Korvold, Fae-Cursed King
[Mainboard]
99 Totally Invented Card
"""
    with pytest.raises(Exception, match="unknown Oracle card name"):
        PlaintextDeckImporter(catalog).import_text(
            text,
            DeckImportOptions(
                deck_id="test",
                name="test",
                commander_names=("Korvold, Fae-Cursed King",),
            ),
        )
