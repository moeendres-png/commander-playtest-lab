from __future__ import annotations

import sys
from pathlib import Path

from commander_lab.engine.rules import JsonLineBridgeClient, load_project_rules_decks


def test_persistent_jsonl_bridge_roundtrip(repo_root: Path) -> None:
    client = JsonLineBridgeClient(
        (sys.executable, str(repo_root / "scripts/tactical_rules_bridge.py")), cwd=repo_root
    )
    try:
        probe = client.request("probe")
        assert probe["availability"] == "available"
        deck = load_project_rules_decks(repo_root)["rogshai/current"]
        handle = client.request("load_deck", {"deck": deck.model_dump(mode="json")})
        assert handle["accepted_cards"] == 100
    finally:
        client.close()
