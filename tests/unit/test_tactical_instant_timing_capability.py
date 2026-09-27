from __future__ import annotations

from commander_lab.engine.rules.tactical import TacticalRuleError, TacticalRuleOracle
from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.search import current_control_mainboard
from commander_lab.whole_deck.tactical_capabilities import assess_tactical_variant_capabilities


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


def test_preordain_to_opt_routes_to_tactical_available_without_structural_upgrade() -> None:
    lab = WholeDeckDesignLab(".")
    control = current_control_mainboard(".")
    candidate = list(control)
    candidate[candidate.index("Preordain")] = "Opt"
    result = assess_tactical_variant_capabilities(
        lab.context,
        control=control,
        candidate=tuple(candidate),
        deck_hash="opt-fixture",
    )
    assert result["structural_route"] == "TACTICAL_EVIDENCE_REQUIRED"
    assert result["required_next_evidence_layer"] == "TACTICAL_EVIDENCE_AVAILABLE"
    assert result["tactical_evaluable"] is True
    assert result["tactical_capabilities_covered"] == [
        {
            "oracle_name": "Opt",
            "direction": "added",
            "capability_id": "INSTANT_TIMING_BASIC_LITERAL_DRAW_SCRY",
        }
    ]


def test_external_candidate_with_opt_remains_external() -> None:
    lab = WholeDeckDesignLab(".")
    control = current_control_mainboard(".")
    candidate = list(control)
    candidate[candidate.index("Preordain")] = "Opt"
    candidate[candidate.index("Swords to Plowshares")] = "Disintegrate"
    result = assess_tactical_variant_capabilities(
        lab.context,
        control=control,
        candidate=tuple(candidate),
        deck_hash="mixed-fixture",
    )
    assert result["tactical_evaluable"] is False
    assert result["required_next_evidence_layer"] != "TACTICAL_EVIDENCE_AVAILABLE"
    assert result["remaining_blocked_cards"]
