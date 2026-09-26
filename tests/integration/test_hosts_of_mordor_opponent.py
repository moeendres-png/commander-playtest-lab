from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.structural.project import load_project_structural_decks
from commander_lab.importers.opponents import OpponentProfileImporter

ROOT = Path(__file__).resolve().parents[2]


def test_hosts_of_mordor_official_precon_imports_as_exact_100() -> None:
    path = ROOT / "data/opponents/hosts_of_mordor_precon.json"
    profiles = OpponentProfileImporter().import_file(path)

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.profile_id == "opponent/hosts-of-mordor-precon"
    assert profile.list_status.value == "official_precon"
    assert profile.commander.commanders == ("Sauron, Lord of the Rings",)
    assert profile.deck is not None
    assert profile.deck.total_cards == 100
    assert profile.deck.library_cards == 99
    assert profile.deck.quantities()["Island"] == 6
    assert profile.deck.quantities()["Swamp"] == 6
    assert profile.deck.quantities()["Mountain"] == 7
    assert "Saruman, the White Hand" in profile.deck.quantities()
    assert profile.uncertainty.known_card_count == 100
    assert profile.uncertainty.synthetic_card_count == 0
    assert profile.sources[0].source_type == "official_precon"


def test_hosts_of_mordor_is_registered_without_touching_kaervek_hash() -> None:
    registry = json.loads(
        (ROOT / "data/opponents/opponent_registry.json").read_text(encoding="utf-8")
    )

    assert registry["current"]["hosts_of_mordor/precon"] == "opponent/hosts-of-mordor-precon"
    assert (
        registry["kaervek_deck_hash"]
        == "aa7a90a4e5cf32f40b1c9832d329aa03f6f7bf130f2d2e9c1e80d10e97c53c7a"
    )


def test_hosts_of_mordor_is_available_to_current_structural_opponent_loader() -> None:
    decks = load_project_structural_decks(ROOT, include_current_opponents=True)

    assert "opponent/hosts-of-mordor-precon" in decks
    mordor = decks["opponent/hosts-of-mordor-precon"]
    assert len(mordor.cards) == 100
    assert mordor.commander_names == ("Sauron, Lord of the Rings",)
    assert mordor.commander_base_costs["Sauron, Lord of the Rings"] == 8.0
    assert mordor.commander_base_power["Sauron, Lord of the Rings"] == 9.0
