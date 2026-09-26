from __future__ import annotations

from pathlib import Path

from commander_lab.mana_analysis import ManaAnalyzer
from commander_lab.models import CardRole, Color, StructuralCardProfile
from commander_lab.mulligan import MulliganLab
from commander_lab.tools.current_candidates import load_candidate_profiles

ROOT = Path(__file__).resolve().parents[2]


def _candidate_by_name(name: str):
    for candidate in load_candidate_profiles(ROOT).values():
        if candidate.card.oracle_name == name:
            return candidate.card
    raise AssertionError(f"missing candidate fixture: {name}")


def test_tapped_land_classifier_distinguishes_definite_and_conditional() -> None:
    analyzer = ManaAnalyzer(ROOT)
    temple = analyzer.classify_source(_candidate_by_name("Temple of Epiphany"))
    fortress = analyzer.classify_source(_candidate_by_name("Glacial Fortress"))
    assert temple.definitely_enters_tapped is True
    assert temple.conditionally_enters_tapped is False
    assert fortress.definitely_enters_tapped is False
    assert fortress.conditionally_enters_tapped is True


def test_current_rogshai_mana_report_covers_colors_commanders_and_early_signals() -> None:
    lab = MulliganLab(ROOT)
    report = lab.analyze_deck_mana("rogshai/current")
    assert report.deck_hash == lab.deck("rogshai/current").deck_hash
    assert report.land_count == 36
    assert report.colored_sources["W"] > 0
    assert report.colored_sources["U"] > 0
    assert report.colored_sources["R"] > 0
    assert report.ishai_wu_source_counts["W"] > 0
    assert report.ishai_wu_source_counts["U"] > 0
    assert "Ishai, Ojutai Dragonspeaker" in report.commander_color_requirements
    assert set(report.turn_castability_support) == {1, 2, 3}
    assert all(
        0.0 <= float(row["source_supported_share"]) <= 1.0
        for row in report.turn_castability_support.values()
    )
    assert report.evidence_class == "derived_structural_mana_analysis"
    assert "not a rules-exact" in report.approximation_note


def test_opening_hand_reports_approximate_castability_ishai_and_hold_up() -> None:
    lab = MulliganLab(ROOT)
    deck = lab.deck("rogshai/current")
    by_name = {card.oracle_name: card for card in deck.cards}
    test_counter = StructuralCardProfile(
        oracle_name="Deterministic Test Counter",
        mana_value=2.0,
        roles=frozenset({CardRole.COUNTER}),
        color_requirements={Color.BLUE: 1},
        is_permanent=False,
    )
    hand = (
        by_name["Island"],
        by_name["Mountain"],
        by_name["Plains"],
        test_counter,
    )
    report = lab.mana_analyzer.analyze_opening_hand(deck, hand)
    assert report.ishai_wu_color_ready is True
    assert report.t2_interaction_hold_up_ready is True
    assert report.approximate_castable_card_count_by_turn[1] == 0
    assert report.approximate_castable_card_count_by_turn[2] >= 1
    assert "does not solve" in report.approximation_note


def test_mana_delta_is_deterministic_and_zero_for_same_deck() -> None:
    lab = MulliganLab(ROOT)
    deck = lab.deck("rogshai/current")
    delta = lab.mana_analyzer.compare_decks(deck, deck)
    assert delta.colored_source_delta == {}
    assert delta.flexible_source_delta == 0
    assert delta.definitely_tapped_land_delta == 0
    assert delta.conditionally_tapped_land_delta == 0
    assert delta.t1_untapped_source_delta == {}
    assert delta.ishai_wu_source_delta == {"W": 0, "U": 0}


def test_mulligan_features_use_oracle_tapped_source_classification() -> None:
    lab = MulliganLab(ROOT)
    deck = lab.deck("rogshai/current")
    by_name = {card.oracle_name: card for card in deck.cards}
    hand = (
        by_name["Island"],
        by_name["Mountain"],
        by_name["Plains"],
        _candidate_by_name("Temple of Epiphany"),
    )
    features = lab.features(deck, hand)
    assert features.colored_sources["W"] >= 1
    assert features.colored_sources["U"] >= 1
    assert features.colored_sources["R"] >= 1
    assert features.color_stability_score == 1.0
    assert features.tapped_source_count >= 1
