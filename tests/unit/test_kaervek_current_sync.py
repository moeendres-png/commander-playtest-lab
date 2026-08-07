from __future__ import annotations

import json
from pathlib import Path

from commander_lab.agents.pilots import KaervekOpponentPilot, auto_pilot_name
from commander_lab.engine.structural.project import load_project_structural_decks

EXPECTED_HASH = "c2ff0589415b90c8d1f60b948230b271ec3cede697119ff6ef3ed7fea0765dcd"


def test_kaervek_current_is_exact_verified_snapshot(repo_root: Path) -> None:
    decks = load_project_structural_decks(repo_root, include_current_opponents=True)
    deck = decks["kaervek/current"]
    assert deck.deck_hash == EXPECTED_HASH
    assert len(deck.cards) == 100
    assert len({card.oracle_name for card in deck.cards}) == 77
    assert sum(card.oracle_name == "Swamp" for card in deck.cards) == 13
    assert sum(card.oracle_name == "Mountain" for card in deck.cards) == 12
    assert "opponent/kaervek-reference" not in decks
    assert {"Sorin Markov", "Chandra Nalaar", "Butcher of Malakir", "Chain Reaction", "Tor Wauki the Younger", "Terminate"} <= {card.oracle_name for card in deck.cards}


def test_kaervek_current_provenance_and_alias_are_explicit(repo_root: Path) -> None:
    provenance = json.loads((repo_root / "data/decks/opponents/kaervek/current/provenance.json").read_text())
    registry = json.loads((repo_root / "data/opponents/opponent_registry.json").read_text())
    assert provenance["verified_full_list"] is True
    assert provenance["deck_hash"] == EXPECTED_HASH
    assert provenance["derived_from"]["source_type"] == "owned_verified_deck"
    assert registry["current"]["kaervek/current"] == "kaervek/current"
    assert registry["aliases"]["opponent/kaervek-reference"]["redirect"] == "kaervek/current"


def test_kaervek_uses_specialized_visible_state_pilot() -> None:
    assert auto_pilot_name("kaervek") == "KaervekOpponentPilot"
    assert KaervekOpponentPilot.pilot_name == "KaervekOpponentPilot"
