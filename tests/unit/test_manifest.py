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
        "4af053a36d9cf4e84ff5ac2c2e5372daba5336c3cdfb48914ea4d72ea495677d"
    )
    assert manifest["decks"]["rogshai/current"]["deck_hash"] == (
        "2f2dab2a26e3889aa5399504295d2c6e485c8922397c6736bd4e6fa72f6b6656"
    )
