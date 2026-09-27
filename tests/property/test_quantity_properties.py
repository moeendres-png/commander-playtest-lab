from __future__ import annotations

import random

import pytest

from commander_lab.analysis import validate_collection_quantities
from commander_lab.models import (
    Collection,
    CommanderConfiguration,
    Deck,
    DeckEntry,
    DeckZone,
    PhysicalCard,
)


@pytest.mark.property
def test_quantity_validation_matches_arithmetic_for_generated_cases() -> None:
    rng = random.Random(20260804)
    for case in range(200):
        owned = rng.randint(1, 5)
        required_a = rng.randint(0, 3)
        required_b = rng.randint(0, 3)
        commander = f"Commander {case}"
        collection = Collection(
            collection_id=f"c-{case}",
            name="generated",
            cards=[
                PhysicalCard(copy_id=f"cmd-{case}", oracle_name=commander, quantity=2),
                PhysicalCard(copy_id=f"card-{case}", oracle_name="Shared Card", quantity=owned),
                PhysicalCard(copy_id=f"land-{case}", oracle_name="Forest", quantity=198),
            ],
        )

        def make_deck(deck_id: str, required: int, *, commander_name: str = commander) -> Deck:
            filler = 99 - required
            entries = [DeckEntry(oracle_name=commander_name, zone=DeckZone.COMMANDER)]
            if required:
                entries.append(DeckEntry(oracle_name="Shared Card", quantity=required))
            if filler:
                entries.append(DeckEntry(oracle_name="Forest", quantity=filler))
            return Deck(
                deck_id=deck_id,
                name=deck_id,
                commander=CommanderConfiguration(commanders=(commander_name,)),
                cards=entries,
            )

        report = validate_collection_quantities(
            collection,
            [make_deck("a", required_a), make_deck("b", required_b)],
        )
        assert report.valid is ((required_a + required_b) <= owned)
