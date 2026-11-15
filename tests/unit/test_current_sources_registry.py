"""The source registry in data/sync/current_sources.json agrees with the prepared imports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), path
    return payload


def _sources(repo_root: Path) -> dict[str, dict[str, Any]]:
    registry = _load(repo_root / "data/sync/current_sources.json")
    return dict(registry["sources"])


def test_registry_lists_the_expected_sources(repo_root: Path) -> None:
    assert set(_sources(repo_root)) == {
        "current_rogshai_deck",
        "inventory",
        "korvold_rogshai_decks",
        "opponent_baselines",
    }


@pytest.mark.parametrize(
    "key",
    ["current_rogshai_deck", "inventory", "korvold_rogshai_decks", "opponent_baselines"],
)
def test_registry_hash_and_drive_id_match_the_prepared_import(repo_root: Path, key: str) -> None:
    spec = _sources(repo_root)[key]
    prepared = _load(repo_root / spec["import_path"])
    assert prepared.get("source_sha256") == spec["sha256"]
    assert prepared.get("source_drive_file_id") == spec["drive_file_id"]


def test_registry_deck_hashes_match_the_deck_manifest(repo_root: Path) -> None:
    manifest = _load(repo_root / "data/decks/manifest.json")["decks"]
    checked = 0
    for key, spec in _sources(repo_root).items():
        for deck_id, digest in spec.get("deck_hashes", {}).items():
            assert deck_id in manifest, (key, deck_id)
            assert manifest[deck_id].get("deck_hash") == digest, (key, deck_id)
            checked += 1
    assert checked > 0
