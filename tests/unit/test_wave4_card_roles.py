"""Public precon card-role regressions and neighboring text controls."""

from dataclasses import replace

import pytest

from commander_lab.agents.card_knowledge import card_facts, card_roles
from commander_lab.engine.rules.full_game_pilot_views import priority_view_fields
from commander_lab.models import CardRole


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("Fact or Fiction", CardRole.SELECTION),
        ("Windfall", CardRole.DRAW),
        ("Overwhelming Stampede", CardRole.COMBAT_PAYOFF),
    ],
)
def test_public_precon_roles(name: str, role: CardRole) -> None:
    facts = card_facts(name)
    assert facts is not None
    assert role in card_roles(facts)


@pytest.mark.parametrize(
    ("base", "text", "role"),
    [
        (
            "Fact or Fiction",
            "Reveal the top five cards of your library. An opponent separates those cards into two piles. Put one pile into your graveyard.",
            CardRole.SELECTION,
        ),
        (
            "Windfall",
            "Each player discards their hand, then loses life equal to the greatest number of cards discarded this way.",
            CardRole.DRAW,
        ),
        (
            "Overwhelming Stampede",
            "Until end of turn, creatures your opponents control gain trample and get +X/+X.",
            CardRole.COMBAT_PAYOFF,
        ),
        (
            "Overwhelming Stampede",
            "Until end of turn, target creature you control gains trample and gets +X/+X.",
            CardRole.COMBAT_PAYOFF,
        ),
    ],
)
def test_neighboring_text_is_not_misclassified(base: str, text: str, role: CardRole) -> None:
    facts = card_facts(base)
    assert facts is not None
    assert role not in card_roles(replace(facts, name="Synthetic role control", oracle_text=text))


def _option(name: str) -> dict:
    return {
        "option_type": "play",
        "label": name,
        "metadata": {"ability_type": "spell", "source_name": name},
    }


def test_priority_fields_use_new_roles() -> None:
    state = {
        "actor_id": "p1",
        "active_player_id": "p1",
        "phase": "main",
        "players": [{"player_id": "p1", "battlefield": []}, {"player_id": "p2", "battlefield": []}],
    }
    fact, _ = priority_view_fields(_option("Fact or Fiction"), state)
    assert CardRole.SELECTION in fact["roles"]
    assert fact["metadata"]["instant_timing"] == -0.5
    state.update(active_player_id="p2", phase="end")
    fact, _ = priority_view_fields(_option("Fact or Fiction"), state)
    assert fact["metadata"]["instant_timing"] == 0.6
    windfall, _ = priority_view_fields(_option("Windfall"), state)
    assert CardRole.DRAW in windfall["roles"]
    assert windfall["immediate_impact"] >= 0.7
    stampede, _ = priority_view_fields(_option("Overwhelming Stampede"), state)
    assert CardRole.COMBAT_PAYOFF in stampede["roles"]
