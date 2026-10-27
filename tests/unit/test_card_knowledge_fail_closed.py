"""Fail-closed card catalog and startup pool-coverage gate tests (#1037)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.agents import card_knowledge as ck
from commander_lab.agents.card_knowledge import (
    CardCatalogError,
    card_facts,
    verify_catalog_pool_coverage,
)


def _clear_caches() -> None:
    ck._catalog.cache_clear()
    ck._lookup.cache_clear()
    ck._split_card_names.cache_clear()
    ck._curated_profiles.cache_clear()
    ck._card_roles.cache_clear()


def test_missing_or_corrupt_or_empty_catalog_fails_closed(tmp_path: Path) -> None:
    _clear_caches()
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(CardCatalogError, match="failed to load card catalog"):
        card_facts("Sol Ring", missing)

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CardCatalogError, match="failed to load card catalog"):
        card_facts("Sol Ring", corrupt)

    non_object = tmp_path / "list.json"
    non_object.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(CardCatalogError, match="root must be a JSON object"):
        card_facts("Sol Ring", non_object)

    empty_cards = tmp_path / "empty.json"
    empty_cards.write_text('{"cards": {}}', encoding="utf-8")
    with pytest.raises(CardCatalogError, match="card catalog is empty"):
        card_facts("Sol Ring", empty_cards)


def test_missing_or_corrupt_or_empty_curated_profiles_fails_closed(tmp_path: Path) -> None:
    _clear_caches()
    missing = tmp_path / "missing_profiles.json"
    with pytest.raises(CardCatalogError, match="failed to load curated role profiles"):
        ck._curated_profiles(str(missing))

    corrupt = tmp_path / "corrupt_profiles.json"
    corrupt.write_text("{bad json", encoding="utf-8")
    with pytest.raises(CardCatalogError, match="failed to load curated role profiles"):
        ck._curated_profiles(str(corrupt))

    empty = tmp_path / "empty_profiles.json"
    empty.write_text('{"profiles": []}', encoding="utf-8")
    with pytest.raises(CardCatalogError, match="curated role profiles list is empty"):
        ck._curated_profiles(str(empty))


def test_valid_catalog_and_startup_pool_coverage_gate_succeed() -> None:
    _clear_caches()
    sol_ring = card_facts("Sol Ring")
    assert sol_ring is not None
    assert sol_ring.mana_value == 1.0
    ratio = verify_catalog_pool_coverage()
    assert ratio >= 0.50


def test_startup_pool_coverage_gate_fails_closed_below_threshold(tmp_path: Path) -> None:
    _clear_caches()
    tiny_catalog = tmp_path / "tiny_catalog.json"
    tiny_catalog.write_text(
        json.dumps(
            {
                "cards": {
                    "Sol Ring": {
                        "name": "Sol Ring",
                        "mana_value": 1.0,
                        "mana_cost": "{1}",
                        "type_line": "Artifact",
                        "oracle_text": "{T}: Add {C}{C}.",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    precons_dir = tmp_path / "precons"
    precons_dir.mkdir()
    (precons_dir / "deck1.json").write_text(
        json.dumps(
            {
                "cards": [
                    {"oracle_name": "Sol Ring"},
                    {"oracle_name": "Unknown Pool Card A"},
                    {"oracle_name": "Unknown Pool Card B"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CardCatalogError, match="below minimum threshold"):
        verify_catalog_pool_coverage(
            catalog_path=tiny_catalog,
            precons_dir=precons_dir,
            min_coverage_ratio=0.50,
        )
