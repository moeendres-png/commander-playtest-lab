from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.cards.catalog import CardCatalog
from commander_lab.engine.structural import (
    StructuralProfileCatalog,
    build_structural_deck_profile,
    build_synthetic_deck_profile,
)
from commander_lab.models import Deck
from commander_lab.storage import load_model


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def cleanup_generated_test_outputs(repo_root: Path):
    """Keep test-only generated reports out of the repository checkout."""
    targets = (
        repo_root / "data/opponent_ensembles/test-cosmic-ensemble-report.md",
        repo_root / "data/primer_rules/evals/test_policy_eval.json",
    )
    for target in targets:
        target.unlink(missing_ok=True)
    try:
        yield
    finally:
        for target in targets:
            target.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def catalog(repo_root: Path) -> CardCatalog:
    return CardCatalog.from_json(repo_root / "data/cards/oracle_subset.json")


@pytest.fixture(scope="session")
def structural_profiles(repo_root: Path) -> StructuralProfileCatalog:
    return StructuralProfileCatalog.from_json(
        repo_root / "data/cards/structural_role_profiles.json"
    )


@pytest.fixture(scope="session")
def structural_decks(repo_root: Path, structural_profiles: StructuralProfileCatalog):
    manifest = json.loads((repo_root / "data/decks/manifest.json").read_text(encoding="utf-8"))
    snapshot_hash = manifest["data_snapshot_hash"]
    result = {}
    for filename in ("korvold_current.json", "rogshai_current.json"):
        deck = load_model(repo_root / "data/decks" / filename, Deck)
        profile = build_structural_deck_profile(
            deck,
            structural_profiles,
            data_snapshot_hash=snapshot_hash,
        )
        result[profile.deck_id] = profile
    for archetype in ("aggro", "control", "engine"):
        profile = build_synthetic_deck_profile(archetype, data_snapshot_hash=snapshot_hash)
        result[profile.deck_id] = profile
    return result
