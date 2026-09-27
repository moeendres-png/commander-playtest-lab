from __future__ import annotations

from collections import Counter
from pathlib import Path

from commander_lab.engine.structural.project import load_project_structural_decks
from commander_lab.importers.opponents import OpponentProfileImporter
from commander_lab.repositories.opponents import CurrentOpponentRepository

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_IDS = {
    "opponent/scions-spellcraft-precon",
    "opponent/counter-intelligence-precon",
    "opponent/turtle-power-precon",
    "opponent/silverquill-influence-precon",
    "opponent/fantastic-four-precon",
    "opponent/avengers-assemble-precon",
    "opponent/doom-prevails-precon",
}


def test_official_precon_benchmarks_are_exact_known_100_card_lists() -> None:
    profiles = OpponentProfileImporter().import_file(
        ROOT / "data/opponents/official_precon_profiles.json"
    )

    assert {profile.profile_id for profile in profiles} == EXPECTED_IDS
    for profile in profiles:
        assert profile.list_status.value == "official_precon"
        assert profile.deck is not None
        assert profile.deck.total_cards == 100
        assert profile.deck.library_cards == 99
        assert profile.uncertainty.known_card_count == 100
        assert profile.uncertainty.synthetic_card_count == 0
        assert profile.sources[0].source_type == "official_precon"


def test_structural_runtime_preserves_every_official_card_identity_and_quantity() -> None:
    profiles = {
        profile.profile_id: profile
        for profile in OpponentProfileImporter().import_file(
            ROOT / "data/opponents/official_precon_profiles.json"
        )
    }
    structural = load_project_structural_decks(ROOT, include_current_opponents=True)

    for deck_id in EXPECTED_IDS:
        exact = profiles[deck_id].deck
        assert exact is not None
        expected = exact.quantities()
        actual = Counter(card.oracle_name for card in structural[deck_id].cards)
        assert actual == expected
        assert len(structural[deck_id].cards) == 100


def test_benchmarks_are_official_precon_evidence_only() -> None:
    records = {record.deck_id: record for record in CurrentOpponentRepository(ROOT).records()}

    for deck_id in EXPECTED_IDS:
        assert tuple(kind.value for kind in records[deck_id].evidence_kinds) == ("official_precon",)
