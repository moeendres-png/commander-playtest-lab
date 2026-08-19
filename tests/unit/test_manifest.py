from __future__ import annotations

import json
from pathlib import Path


def test_local_manifest_has_exactly_one_current_baseline(repo_root: Path) -> None:
    manifest = json.loads((repo_root / "data/decks/manifest.json").read_text(encoding="utf-8"))
    assert manifest["google_drive_modified"] is False
    assert manifest["global_active_own_decks"] == ["rogshai/current"]
    assert manifest["current_optimization_target"] == "rogshai/current"
    assert manifest["runtime_loaded_decks"] == ["rogshai/current"]
    assert manifest["frozen_opponent_decks"] == ["kaervek/current"]
    assert manifest["active_own_decks"] == ["rogshai/current"]
    assert set(manifest["decks"]) == {"rogshai/current"}
    assert manifest["decks"]["rogshai/current"]["total_cards"] == 100
    assert manifest["decks"]["rogshai/current"]["library_cards"] == 98
    assert manifest["decks"]["rogshai/current"]["land_count"] == 36
    assert manifest["allocation_validation"]["valid"] is True
    assert manifest["decks"]["rogshai/current"]["deck_hash"] == (
        "1704b6f1574e4d3152f08cf9936c389683f0ae6efa98a8a277a64daa37f583e3"
    )
    assert manifest["decks"]["rogshai/current"]["source_file_sha256"] == (
        "2b6258ae1c778784ed252bb46ff828343055177146634c77847506d33f4a4362"
    )
    assert len(manifest["data_snapshot_hash"]) == 64
