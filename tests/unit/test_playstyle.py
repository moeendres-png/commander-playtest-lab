from __future__ import annotations

from pathlib import Path

from commander_lab.models import CardRole, StructuralCardProfile
from commander_lab.playstyle import PlaystyleAnalyzer

ROOT = Path(__file__).resolve().parents[2]


def test_explicit_repetitive_oracle_text_is_flagged_without_becoming_a_ban() -> None:
    analyzer = PlaystyleAnalyzer(ROOT)
    analyzer.inventory["Synthetic Playstyle Fixture"] = {
        "oracle_text": (
            "Whenever a creature enters, create a token. Sacrifice a creature: you may repeat "
            "this process any number of times. Put a +1/+1 counter on target creature."
        )
    }
    card = StructuralCardProfile(
        oracle_name="Synthetic Playstyle Fixture",
        mana_value=3.0,
        roles=frozenset(
            {
                CardRole.ENGINE,
                CardRole.TOKEN_SOURCE,
                CardRole.SACRIFICE_OUTLET,
            }
        ),
        is_permanent=True,
    )
    result = analyzer.analyze_card(card)
    assert result.normal_turn_action_load == "high_risk"
    assert result.repetitive_action_load == "high_risk"
    assert result.loop_dependency == "explicit_repeat_text_present"
    assert result.playstyle_fit == "caution"
    assert result.confidence == "medium"
    assert "not a power score" in result.boundary


def test_playstyle_comparison_never_auto_rejects_a_card() -> None:
    analyzer = PlaystyleAnalyzer(ROOT)
    remove = StructuralCardProfile(
        oracle_name="Low Admin Fixture",
        mana_value=1.0,
        roles=frozenset({CardRole.ENABLER}),
    )
    add = StructuralCardProfile(
        oracle_name="Engine Fixture",
        mana_value=2.0,
        roles=frozenset({CardRole.ENGINE}),
        is_permanent=True,
    )
    result = analyzer.compare_cards(remove, add)
    assert result["automatic_rejection"] is False
    assert result["preference_type"] == "post_build_review_only"
    assert result["review_stage"] == "after_objective_build_and_comparison_decision"
