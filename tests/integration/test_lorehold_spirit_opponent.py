from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.structural.project import load_project_structural_decks

ROOT = Path(__file__).resolve().parents[2]


def test_lorehold_is_registered_without_touching_kaervek_hash() -> None:
    registry = json.loads(
        (ROOT / "data/opponents/opponent_registry.json").read_text(encoding="utf-8")
    )

    assert registry["current"]["lorehold_spirit/precon"] == "opponent/lorehold-spirit-precon"
    assert (
        registry["aliases"]["opponent/kundhort-geist"]["redirect"]
        == "opponent/lorehold-spirit-precon"
    )
    assert (
        registry["kaervek_deck_hash"]
        == "aa7a90a4e5cf32f40b1c9832d329aa03f6f7bf130f2d2e9c1e80d10e97c53c7a"
    )


def test_lorehold_is_available_to_current_structural_opponent_loader() -> None:
    decks = load_project_structural_decks(ROOT, include_current_opponents=True)

    assert "opponent/lorehold-spirit-precon" in decks
    lorehold = decks["opponent/lorehold-spirit-precon"]
    assert len(lorehold.cards) == 100
    assert lorehold.commander_names == ("Quintorius, History Chaser",)
    assert lorehold.commander_base_costs["Quintorius, History Chaser"] == 4.0
    assert lorehold.commander_base_power["Quintorius, History Chaser"] == 0.0
