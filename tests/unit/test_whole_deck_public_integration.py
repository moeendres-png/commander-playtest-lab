from __future__ import annotations

from commander_lab.semantic_features import (
    graveyard_hate_semantics,
    produced_self_colors,
    protection_semantics,
    removal_semantics,
    self_mana_semantics,
)


def test_semantic_hardening_examples() -> None:
    offer = "Counter target spell. Its controller creates two Treasure tokens."
    assert self_mana_semantics(offer, "Instant") == (False, False)
    assert produced_self_colors(offer, "Instant") == frozenset()
    own_treasure = "Create two Treasure tokens."
    assert {color.value for color in produced_self_colors(own_treasure, "Sorcery")} == {
        "W",
        "U",
        "R",
    }
    assert not removal_semantics("Target player takes 5 damage.")
    assert not graveyard_hate_semantics("Flashback {2}{U}")
    assert not protection_semantics("This spell can't be countered.")
    assert protection_semantics("Target creature gains indestructible until end of turn.")
