from __future__ import annotations

from tests.unit.whole_deck_profile_fixtures import card, profile


def commander_fixture_cards():
    return [
        card("Ishai, Ojutai Dragonspeaker", profile=profile("Ishai, Ojutai Dragonspeaker", mv=4.0)),
        card("Rograkh, Son of Rohgahh", profile=profile("Rograkh, Son of Rohgahh", mv=0.0)),
    ]
