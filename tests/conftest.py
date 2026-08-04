from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.cards.catalog import CardCatalog


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def catalog(repo_root: Path) -> CardCatalog:
    return CardCatalog.from_json(repo_root / "data/cards/oracle_subset.json")
