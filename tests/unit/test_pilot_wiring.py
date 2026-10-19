"""Changed-line tests for pilot wiring (tempo/desperation/synergy/bread).

These tests verify that the wiring in full_game_pilot_views.py is executed.
They fail if the wiring is removed (dead code again).
"""

from __future__ import annotations

from unittest.mock import patch

from commander_lab.engine.rules import full_game_pilot_views as v


def _spell_option(name: str) -> dict:
    return {
        "option_type": "play",
        "label": name,
        "metadata": {"ability_type": "spell", "source_name": name},
    }


def _state(actor_battlefield: list[dict]) -> dict:
    return {
        "actor_id": "p1",
        "players": [
            {"player_id": "p1", "life": 40, "battlefield": actor_battlefield},
            {"player_id": "p2", "life": 40, "battlefield": []},
        ],
    }


def test_synergy_wiring_executes():
    """synergy_bonus is called and its result appears in metadata."""
    option = _spell_option("Llanowar Elves")
    state = _state([{"name": "Wood Elves"}])  # tribal Elf match
    fields, _ = v.priority_view_fields(option, state)
    meta = fields.get("metadata", {})
    # Without the wiring, these keys would not exist.
    assert "synergy_bonus" in meta, "synergy wiring not executed"
    assert meta["synergy_bonus"] == 0.3  # one tribal match
    assert "bread_weight" in meta, "bread wiring not executed"


def test_bread_wiring_executes():
    """bread_weight modifies immediate_impact based on card role."""
    option = _spell_option("Sol Ring")  # artifact, no synergy
    state = _state([])
    fields, _ = v.priority_view_fields(option, state)
    meta = fields.get("metadata", {})
    assert "bread_weight" in meta, "bread wiring not executed"
    # Sol Ring is not a bomb/removal/dud; weight should be 1.0 (baseline)
    assert meta["bread_weight"] == 1.0


def test_desperation_wiring_executes():
    """desperation_score is called in attack_score and boosts when desperate."""
    option = {
        "option_type": "attack",
        "label": "x attacks p2",
        "metadata": {"object_id": "perm1", "defender_id": "p2"},
    }
    state = {
        "actor_id": "p1",
        "players": [
            {
                "player_id": "p1",
                "life": 40,
                "battlefield": [
                    {
                        "object_id": "perm1",
                        "name": "Llanowar Elves",
                        "power": 2,
                        "toughness": 2,
                        "abilities": [],
                    }
                ],
            },
            {"player_id": "p2", "life": 40, "battlefield": []},
        ],
    }
    # Baseline: no desperation
    with patch.object(v, "desperation_score", return_value=0.0):
        score_calm, _ = v.attack_score(option, state)
    # Desperate: should boost the score
    with patch.object(v, "desperation_score", return_value=0.8):
        score_desp, _ = v.attack_score(option, state)
    # Without the wiring, both scores would be identical.
    assert score_desp > score_calm, (
        f"desperation wiring not executed: {score_desp} <= {score_calm}"
    )
    assert abs((score_desp - score_calm) - 0.8) < 0.01
