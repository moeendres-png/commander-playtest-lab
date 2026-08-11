from __future__ import annotations

import json
from pathlib import Path


def test_local_manifest_has_exactly_one_current_baseline(repo_root: Path) -> None:
    manifest = json.loads((repo_root / "data/decks/manifest.json").read_text(encoding="utf-8"))
    assert manifest["google_drive_modified"] is False
    assert manifest["active_own_decks"] == ["rogshai/current"]
    assert set(manifest["decks"]) == {"rogshai/current"}
    assert manifest["decks"]["rogshai/current"]["total_cards"] == 100
    assert manifest["decks"]["rogshai/current"]["library_cards"] == 98
    assert manifest["decks"]["rogshai/current"]["land_count"] == 36
    assert manifest["allocation_validation"]["valid"] is True
    assert manifest["decks"]["rogshai/current"]["deck_hash"] == (
        "7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126"
    )
    assert manifest["removed_operational_decks"] == ["korvold/current"]
