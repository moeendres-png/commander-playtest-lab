from __future__ import annotations

from pathlib import Path

from commander_lab.mana_analysis import ManaAnalyzer
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


def test_current_rogshai_mana_report_covers_colors_and_commanders() -> None:
    lab = MulliganLab(ROOT)
    report = lab.analyze_deck_mana("rogshai/current")
    assert report.deck_hash == lab.deck("rogshai/current").deck_hash
    assert report.land_count == 37
    assert report.colored_sources["W"] > 0
    assert report.colored_sources["U"] > 0
    assert report.colored_sources["R"] > 0
    assert "Ishai, Ojutai Dragonspeaker" in report.commander_color_requirements
    assert report.evidence_class == "derived_structural_mana_analysis"


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
