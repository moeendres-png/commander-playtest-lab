from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import Deck, StructuralDeckProfile
from commander_lab.storage import load_model

from .fixtures import build_current_opponent_profiles, build_synthetic_deck_profile
from .profiles import StructuralProfileCatalog, build_structural_deck_profile


def load_project_structural_decks(
    root: str | Path,
    *,
    include_synthetic_fixtures: bool = False,
    include_current_opponents: bool = False,
) -> dict[str, StructuralDeckProfile]:
    root_path = Path(root)
    manifest = json.loads((root_path / "data/decks/manifest.json").read_text(encoding="utf-8"))
    snapshot_hash = str(manifest["data_snapshot_hash"])
    profiles = StructuralProfileCatalog.from_json(root_path / "data/cards/structural_role_profiles.json")
    decks: dict[str, StructuralDeckProfile] = {}
    for filename in ("korvold_current.json", "rogshai_current.json"):
        deck = load_model(root_path / "data/decks" / filename, Deck)
        profile = build_structural_deck_profile(deck, profiles, data_snapshot_hash=snapshot_hash)
        decks[profile.deck_id] = profile
    if include_synthetic_fixtures:
        for archetype in ("aggro", "control", "engine"):
            profile = build_synthetic_deck_profile(archetype, data_snapshot_hash=snapshot_hash)
            decks[profile.deck_id] = profile
    if include_current_opponents:
        opponent_path = root_path / "data/opponents/current_structural_profiles.json"
        if opponent_path.exists():
            decks.update(build_current_opponent_profiles(opponent_path, data_snapshot_hash=snapshot_hash))
    return decks
