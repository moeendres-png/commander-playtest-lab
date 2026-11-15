from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from commander_lab.engine.structural.project import load_project_structural_decks
from commander_lab.models import OpponentProfile

ROOT = Path(__file__).resolve().parents[2]


def _import_profiles(path: Path) -> list[OpponentProfile]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "profiles" in payload:
        payload = payload["profiles"]
    if isinstance(payload, dict):
        payload = [payload]
    return [OpponentProfile.model_validate(item) for item in payload]


EXPECTED_IDS = {
    "opponent/scions-spellcraft-precon",
    "opponent/counter-intelligence-precon",
    "opponent/turtle-power-precon",
    "opponent/silverquill-influence-precon",
    "opponent/fantastic-four-precon",
    "opponent/avengers-assemble-precon",
    "opponent/doom-prevails-precon",
}
# Current opponents that are unchanged official precons with an exact packaged list; Blight
# Curse also carries an observed commander preference, so it is not a pure benchmark.
EXACT_LIST_IDS = EXPECTED_IDS | {
    "opponent/blight-curse-precon",
    "opponent/dance-elements-precon",
    "opponent/wakanda-forever-precon",
}


def test_official_precon_benchmarks_are_exact_known_100_card_lists() -> None:
    profiles = _import_profiles(ROOT / "data/opponents/official_precon_profiles.json")

    assert {profile.profile_id for profile in profiles} == EXACT_LIST_IDS
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
        for profile in _import_profiles(ROOT / "data/opponents/official_precon_profiles.json")
    }
    structural = load_project_structural_decks(ROOT, include_current_opponents=True)

    checked = list(EXACT_LIST_IDS)
    assert checked, "nothing was checked: EXACT_LIST_IDS is empty"
    for deck_id in checked:
        exact = profiles[deck_id].deck
        assert exact is not None
        expected = exact.quantities()
        actual = Counter(card.oracle_name for card in structural[deck_id].cards)
        assert actual == expected
        assert len(structural[deck_id].cards) == 100
