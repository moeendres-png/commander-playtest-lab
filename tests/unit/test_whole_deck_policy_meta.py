from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.structural.profiles import StructuralProfileCatalog
from commander_lab.models import StructuralCardProfile

ROGSHAI = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"
WHOLE_DECK_META_SNAPSHOT_ID = "meta-2026-08-13-whole-deck-phase2-1"
GENERIC_META_LATEST_ID = "meta-2026-08-05-phase12-1"


def _profiles(repo_root: Path) -> dict[str, StructuralCardProfile]:
    catalog = StructuralProfileCatalog.from_json(
        repo_root / "data/cards/structural_role_profiles.json"
    )
    return {profile.oracle_name: profile for profile in catalog.profiles}


def test_whole_deck_research_does_not_replace_generic_meta_latest(repo_root: Path) -> None:
    pointer = json.loads(
        (repo_root / "data/meta/manifests/latest.json").read_text(encoding="utf-8")
    )
    assert pointer["snapshot_id"] == GENERIC_META_LATEST_ID


def test_current_meta_snapshot_is_immutable_and_provenanced(repo_root: Path) -> None:
    pointer = json.loads(
        (repo_root / "data/meta/manifests/latest.json").read_text(encoding="utf-8")
    )
    payload = json.loads((repo_root / pointer["path"]).read_text(encoding="utf-8"))
    assert payload["manifest"]["immutable"] is True
    assert all(source["retrieved_at"] for source in payload["sources"])
