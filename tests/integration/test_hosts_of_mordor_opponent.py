from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.structural.project import load_project_structural_decks

ROOT = Path(__file__).resolve().parents[2]


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
