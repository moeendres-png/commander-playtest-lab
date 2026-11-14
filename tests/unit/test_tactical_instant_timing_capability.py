from __future__ import annotations

from commander_lab.engine.rules.tactical import TacticalRuleError, TacticalRuleOracle


def test_basic_spell_timing_is_4p_and_distinguishes_instant_from_sorcery() -> None:
    oracle = TacticalRuleOracle()
    instant = oracle.evaluate(
        "basic_spell_timing",
        {
            "spell_speed": "instant",
            "player_count": 4,
            "phase": "postcombat_main",
            "actor_is_active": False,
            "has_priority": True,
            "stack_empty": False,
            "can_pay_cost": True,
        },
    )
    sorcery = oracle.evaluate(
        "basic_spell_timing",
        {
            "spell_speed": "sorcery",
            "player_count": 4,
            "phase": "postcombat_main",
            "actor_is_active": False,
            "has_priority": True,
            "stack_empty": False,
            "can_pay_cost": True,
        },
    )
    assert instant["can_cast"] is True
    assert sorcery["can_cast"] is False


def test_basic_spell_timing_requires_priority_and_exactly_four_players() -> None:
    oracle = TacticalRuleOracle()
    no_priority = oracle.evaluate(
        "basic_spell_timing",
        {
            "spell_speed": "instant",
            "player_count": 4,
            "phase": "precombat_main",
            "actor_is_active": True,
            "has_priority": False,
            "stack_empty": True,
            "can_pay_cost": True,
        },
    )
    assert no_priority["can_cast"] is False

    try:
        oracle.evaluate(
            "basic_spell_timing",
            {
                "spell_speed": "instant",
                "player_count": 3,
                "phase": "precombat_main",
                "actor_is_active": True,
                "has_priority": True,
            },
        )
    except TacticalRuleError:
        pass
    else:
        raise AssertionError("3-player decision fixture must fail closed")
