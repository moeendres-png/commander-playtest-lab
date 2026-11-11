"""Tests for the Commander Studio evidence source registry (P0 Deliverable 1).

Verifies the systematic qualification of the 7 prioritized sources, schema integrity,
explicit null-timestamp preservation, and JSON inventory generation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio.sources import (
    QUALIFIED_SOURCES,
    get_source,
    list_sources,
    source_inventory_payload,
    write_source_inventory_json,
)

EXPECTED_PRIORITIES = (
    (1, "scryfall:bulk-oracle", "VERIFIED"),
    (2, "playgroup:card-atlas", "REVIEW"),
    (3, "playgroup:chulane", "REVIEW"),
    (4, "edhrec:chulane", "VERIFIED"),
    (5, "spellbook:variants-api", "VERIFIED"),
    (6, "active_drive:chulane-corpus-975", "VERIFIED"),
    (7, "tournament:cedh-meta", "REVIEW"),
)


def test_qualified_sources_covers_all_seven_priorities_in_exact_order() -> None:
    assert len(QUALIFIED_SOURCES) == 7
    priorities = [s.priority for s in QUALIFIED_SOURCES]
    assert priorities == list(range(1, 8))

    for (expected_prio, expected_id, expected_status), source in zip(
        EXPECTED_PRIORITIES, QUALIFIED_SOURCES, strict=True
    ):
        assert source.priority == expected_prio
        assert source.source_id == expected_id
        assert source.status == expected_status


def test_every_source_has_all_seventeen_dimensions_populated() -> None:
    allowed_statuses = {"VERIFIED", "REVIEW", "UNAVAILABLE"}
    allowed_layers = {
        "FACT",
        "DERIVED_MECHANICAL",
        "OBSERVED_DECK",
        "OBSERVED_GAME",
        "COMBO_VERIFIED",
        "SIMULATED_RESULT",
        "MODELED",
        "EXTERNAL_OPINION",
    }

    assert len(QUALIFIED_SOURCES) == 7
    for source in QUALIFIED_SOURCES:
        # Core identification & URL
        assert source.source_id.strip() != ""
        assert source.title.strip() != ""
        assert source.direct_url.startswith("https://") or source.direct_url.startswith("local:")
        assert source.publisher.strip() != ""
        assert isinstance(source.reference_urls, tuple)
        assert len(source.reference_urls) > 0

        # Technical format & identification
        assert source.schema_format.strip() != ""
        assert source.card_identifier.strip() != ""
        assert source.coverage_scope.strip() != ""
        assert source.evidence_layer in allowed_layers
        assert isinstance(source.has_exact_numerator_denominator, bool)
        assert isinstance(source.game_context, dict)
        assert len(source.game_context) > 0

        # Governance, licensing & reproducibility
        assert source.double_counting_risk.strip() != ""
        assert source.license_terms.strip() != ""
        assert source.allowed_retrieval_method.strip() != ""
        assert source.reproducibility in {
            "DETERMINISTIC_OFFLINE_SNAPSHOT",
            "REPRODUCIBLE_API",
            "DYNAMIC_EPHEMERAL_WEB",
            "MANUAL_ARCHIVE",
        }
        assert isinstance(source.bias_risks, tuple)
        assert len(source.bias_risks) > 0
        assert source.status in allowed_statuses
        assert source.status_rationale.strip() != ""


def test_missing_timestamps_remain_none_never_fabricated() -> None:
    # Sources without an exact verified HTTP capture must have retrieved_at_utc=None
    playgroup_atlas = get_source("playgroup:card-atlas")
    assert playgroup_atlas.retrieved_at_utc is None
    assert playgroup_atlas.snapshot_id is None

    playgroup_chulane = get_source("playgroup:chulane")
    assert playgroup_chulane.retrieved_at_utc is None
    assert playgroup_chulane.snapshot_id is None

    tournament = get_source("tournament:cedh-meta")
    assert tournament.retrieved_at_utc is None
    assert tournament.snapshot_id is None

    # Verified sources have explicit UTC timestamps and snapshot IDs
    scryfall = get_source("scryfall:bulk-oracle")
    assert scryfall.retrieved_at_utc == "2026-11-10T00:00:00Z"
    assert scryfall.snapshot_id == "scryfall-oracle-cards-20261110"


def test_get_source_and_list_sources() -> None:
    source = get_source("spellbook:variants-api")
    assert source.priority == 5
    assert source.evidence_layer == "COMBO_VERIFIED"
    assert "commanderspellbook.com" in source.direct_url

    with pytest.raises(KeyError, match="Unknown evidence source"):
        get_source("non-existent-source")

    verified = list_sources(status="VERIFIED")
    assert len(verified) == 4
    assert {s.source_id for s in verified} == {
        "scryfall:bulk-oracle",
        "edhrec:chulane",
        "spellbook:variants-api",
        "active_drive:chulane-corpus-975",
    }

    review = list_sources(status="REVIEW")
    assert len(review) == 3
    assert {s.source_id for s in review} == {
        "playgroup:card-atlas",
        "playgroup:chulane",
        "tournament:cedh-meta",
    }

    unavailable = list_sources(status="UNAVAILABLE")
    assert len(unavailable) == 0


def test_source_inventory_payload_matches_schema() -> None:
    payload = source_inventory_payload()
    assert payload["schema_version"] == "evidence-source-inventory-1.0.0"
    assert payload["total_sources"] == 7
    assert payload["status_counts"]["VERIFIED"] == 4
    assert payload["status_counts"]["REVIEW"] == 3
    assert payload["status_counts"]["UNAVAILABLE"] == 0
    assert len(payload["sources"]) == 7


def test_write_source_inventory_json_roundtrip(tmp_path: Path) -> None:
    target_file = tmp_path / "provenance" / "test_sources.json"
    written_path = write_source_inventory_json(target_file)
    assert written_path.is_file()

    loaded = json.loads(written_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "evidence-source-inventory-1.0.0"
    assert loaded["total_sources"] == 7
    assert len(loaded["sources"]) == 7
    first = loaded["sources"][0]
    assert first["source_id"] == "scryfall:bulk-oracle"
    assert first["priority"] == 1
