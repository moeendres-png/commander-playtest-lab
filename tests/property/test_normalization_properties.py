from __future__ import annotations

import random

import pytest

from commander_lab.cards.normalize import normalize_oracle_name, oracle_lookup_key


@pytest.mark.property
def test_name_normalization_is_idempotent_for_generated_variants() -> None:
    rng = random.Random(20260804)
    base_names = [
        "Nature's Claim",
        "An Offer You Can't Refuse",
        "Wear // Tear",
        "Korvold, Fae-Cursed King",
    ]
    for _ in range(500):
        base = rng.choice(base_names)
        variant = base.replace("'", rng.choice(["'", "\u2019", "\u2018", "`"])).replace(
            " // ", rng.choice(["//", " / / ", "  //  "])
        )
        variant = (" " * rng.randint(0, 3)) + variant + (" " * rng.randint(0, 3))
        once = normalize_oracle_name(variant)
        twice = normalize_oracle_name(once)
        assert once == twice
        assert oracle_lookup_key(once) == oracle_lookup_key(twice)
