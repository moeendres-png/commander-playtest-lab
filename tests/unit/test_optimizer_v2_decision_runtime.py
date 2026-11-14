from __future__ import annotations

import json
from pathlib import Path

from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.search_context import SEMANTIC_UNKNOWN

ROOT = Path(__file__).resolve().parents[2]


def test_full_physical_semantic_projection_covers_current_rogshai_pool() -> None:
    manifest = json.loads(
        (ROOT / "data/cards/FULL_PHYSICAL_CARD_KNOWLEDGE_MANIFEST_CURRENT.json").read_text()
    )
    expected = int(manifest["source_bindings"]["rogshai_context"]["rows"])
    lab = WholeDeckDesignLab(ROOT)

    assert len(lab.context.cards) == expected == 795
    assert "Alandra, Sky Dreamer" in lab.context.cards
    assert "Alandra5 Sky Dreamer" not in lab.context.cards
    assert all(
        card.effective_semantic_state != SEMANTIC_UNKNOWN for card in lab.context.cards.values()
    )
