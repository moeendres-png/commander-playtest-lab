from __future__ import annotations

import json
from pathlib import Path


def test_local_manifest_has_expected_current_baselines(repo_root: Path) -> None:
    manifest = json.loads((repo_root / "data/decks/manifest.json").read_text(encoding="utf-8"))
    assert manifest["google_drive_modified"] is False
    assert manifest["decks"]["korvold/current"]["total_cards"] == 100
    assert manifest["decks"]["korvold/current"]["library_cards"] == 99
    assert manifest["decks"]["rogshai/current"]["total_cards"] == 100
    assert manifest["decks"]["rogshai/current"]["library_cards"] == 98
    assert manifest["allocation_validation"]["valid"] is True
    assert manifest["decks"]["korvold/current"]["deck_hash"] == (
        "72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f"
    )
    assert manifest["decks"]["rogshai/current"]["deck_hash"] == (
        "3827c35995e280753c4e714e391b9baf0a34e2c019e9df519ea1db0260ff9932"
    )
