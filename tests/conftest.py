from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.cards.catalog import CardCatalog
from commander_lab.engine.structural import (
    StructuralProfileCatalog,
    load_project_structural_decks,
)
from commander_lab.models import CardIdentity


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
    result = CardCatalog.from_json(repo_root / "data/cards/oracle_subset.json")
    overlay = json.loads(
        (repo_root / "data/decks/rogshai_current_card_catalog_overrides.json").read_text(
            encoding="utf-8"
        )
    )
    for row in overlay["cards"]:
        result.add(CardIdentity.model_validate(row))
    return result


@pytest.fixture(scope="session")
def structural_profiles(repo_root: Path) -> StructuralProfileCatalog:
    return StructuralProfileCatalog.from_json(
        repo_root / "data/cards/structural_role_profiles.json"
    )


@pytest.fixture(scope="session")
def structural_decks(repo_root: Path):
    return load_project_structural_decks(repo_root, include_synthetic_fixtures=True)
