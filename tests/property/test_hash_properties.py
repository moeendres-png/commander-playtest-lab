from __future__ import annotations

import random

import pytest

from commander_lab.models import CommanderConfiguration, Deck, DeckEntry, DeckZone
from commander_lab.storage import compute_deck_hash


@pytest.mark.property
def test_deck_hash_is_permutation_invariant_for_generated_entry_orders() -> None:
    rng = random.Random(20260804)
    base_entries = [
        DeckEntry(oracle_name="Korvold, Fae-Cursed King", zone=DeckZone.COMMANDER),
        DeckEntry(oracle_name="Sol Ring"),
        DeckEntry(oracle_name="Arcane Signet"),
        DeckEntry(oracle_name="Forest", quantity=97),
    ]
    baseline = Deck(
        deck_id="hash/property",
        name="hash/property",
        commander=CommanderConfiguration(commanders=("Korvold, Fae-Cursed King",)),
        cards=base_entries,
    )
    expected = compute_deck_hash(baseline)
    for _ in range(250):
        permuted = list(base_entries)
        rng.shuffle(permuted)
        candidate = baseline.model_copy(update={"cards": permuted, "deck_hash": None})
        assert compute_deck_hash(candidate) == expected
