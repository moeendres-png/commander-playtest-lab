"""Meta-Lane PR1: snapshot schema extension (all new fields optional).

Covers docs/meta/PROVENANCE_HEADER.md and src/commander_lab/models/meta.py:
new provenance fields validate, old snapshots still validate unchanged, and
the new fields do not change the functional meta profile (no scoring change).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab.meta.store import stable_deck_hash
from commander_lab.models import (
    BudgetBand,
    FormatBand,
    MetaCardFrequency,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaPackage,
    MetaSnapshotManifest,
    MetaSource,
    MetaTargetDeckRef,
    MetaTier,
)
from commander_lab.models.meta import META_SCHEMA_VERSION, expires_at_for
from commander_lab.whole_deck.meta import build_meta_functional_profile

COMMANDER = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"


def _source(**overrides: object) -> MetaSource:
    fields: dict[str, object] = {
        "source_id": "src-a",
        "title": "source",
        "url": "https://example.test/source",
        "retrieved_at": datetime(2026, 8, 5, tzinfo=UTC),
        "source_type": "aggregator",
        "categories": (MetaCategory.HIGH_POWER,),
        "evidence_quality": MetaEvidenceRating.AGGREGATOR,
    }
    fields.update(overrides)
    return MetaSource(**fields)  # type: ignore[arg-type]


def _deck(**overrides: object) -> MetaDeckSnapshot:
    cards = ("Sol Ring", "Silence", "Brain Freeze")
    fields: dict[str, object] = {
        "source_id": "src-a",
        "commander": COMMANDER,
        "deck_hash": stable_deck_hash(cards),
        "retrieved_at": datetime(2026, 8, 5, tzinfo=UTC),
        "format_band": FormatBand.HIGH_POWER,
        "categories": (MetaCategory.HIGH_POWER,),
        "budget_band": BudgetBand.HIGH_POWER,
        "decklist": cards,
    }
    fields.update(overrides)
    return MetaDeckSnapshot(**fields)  # type: ignore[arg-type]


def _snapshot(
    source: MetaSource, deck: MetaDeckSnapshot, *, snapshot_id: str = "meta-test-pr1"
) -> MetaKnowledgeBaseSnapshot:
    manifest = MetaSnapshotManifest(
        snapshot_id=snapshot_id,
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_ids=(source.source_id,),
        deck_hashes=(deck.deck_hash,),
        categories=(MetaCategory.HIGH_POWER,),
    )
    return MetaKnowledgeBaseSnapshot(manifest=manifest, sources=(source,), deck_snapshots=(deck,))


def test_schema_version_stays_1_0_0() -> None:
    # PR1 is purely additive and optional, so the version does not bump.
    assert META_SCHEMA_VERSION == "1.0.0"


def test_old_snapshot_files_still_validate(repo_root: Path) -> None:
    cases = [
        ("meta-2026-08-05-phase12-1", 9, 8),
        ("meta-2026-08-13-whole-deck-phase2-1", 5, 4),
    ]
    assert cases
    for snapshot_id, source_count, deck_count in cases:
        path = repo_root / "data" / "meta" / "snapshots" / f"{snapshot_id}.json"
        snapshot = MetaKnowledgeBaseSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        assert snapshot.manifest.snapshot_id == snapshot_id
        assert snapshot.manifest.schema_version == "1.0.0"
        assert len(snapshot.sources) == source_count
        assert len(snapshot.deck_snapshots) == deck_count


def test_new_fields_roundtrip() -> None:
    source = _source(
        tier=MetaTier.A,
        band=MetaCategory.HIGH_POWER,
        sample_size=53,
        expires_at=datetime(2027, 8, 5, tzinfo=UTC),
    )
    assert source.small_sample is False  # derived from sample_size
    deck = _deck(
        band=FormatBand.HIGH_POWER,
        target_deck_ref=MetaTargetDeckRef(
            path="handover/2026-10-22/example-deck/",
            commit="0123456789abcdef0123456789abcdef01234567",
            branch="muse/claude-handover",
        ),
    )
    package = MetaPackage(
        package_id="example-package",
        name="Example package",
        cards=("Sol Ring",),
        roles=("ramp",),
        categories=(MetaCategory.HIGH_POWER,),
        vetoed_by_games=True,
    )
    snapshot = _snapshot(source, deck)
    restored = MetaKnowledgeBaseSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored.sources[0].tier == MetaTier.A
    assert restored.sources[0].band == MetaCategory.HIGH_POWER
    assert restored.sources[0].sample_size == 53
    assert restored.sources[0].small_sample is False
    assert restored.sources[0].expires_at == datetime(2027, 8, 5, tzinfo=UTC)
    assert restored.deck_snapshots[0].band == FormatBand.HIGH_POWER
    assert restored.deck_snapshots[0].target_deck_ref is not None
    assert restored.deck_snapshots[0].target_deck_ref.path.startswith("handover/")
    assert package.vetoed_by_games is True
    assert MetaPackage.model_validate_json(package.model_dump_json()).vetoed_by_games is True


def test_source_band_must_be_in_categories() -> None:
    with pytest.raises(ValidationError, match="band must be one of its categories"):
        _source(band=MetaCategory.CEDH_TOURNAMENT)


def test_deck_band_must_equal_format_band() -> None:
    with pytest.raises(ValidationError, match="band must equal its format_band"):
        _deck(band=FormatBand.CEDH_TOURNAMENT)


def test_expires_at_must_follow_retrieved_at() -> None:
    with pytest.raises(ValidationError, match="expires_at must be after retrieved_at"):
        _source(expires_at=datetime(2026, 8, 5, tzinfo=UTC))


def test_invalid_tier_rejected() -> None:
    with pytest.raises(ValidationError):
        _source(tier="D")  # type: ignore[arg-type]


def test_small_sample_derived_and_consistent() -> None:
    assert _source(sample_size=3).small_sample is True
    assert _source(sample_size=400).small_sample is False
    assert _source(sample_size=53, small_sample=False).small_sample is False
    with pytest.raises(ValidationError, match="small_sample must agree"):
        _source(sample_size=400, small_sample=True)


def test_target_deck_ref_requires_valid_commit() -> None:
    with pytest.raises(ValidationError):
        MetaTargetDeckRef(path="handover/example/", commit="not-a-sha")
    with pytest.raises(ValidationError):
        MetaTargetDeckRef(path="", commit="0123456789abcdef")


def test_expires_at_for_adds_twelve_months() -> None:
    assert expires_at_for(datetime(2026, 8, 5, tzinfo=UTC)) == datetime(2027, 8, 5, tzinfo=UTC)
    # Month-end clamp: 2024 was a leap year, 2025 is not.
    assert expires_at_for(datetime(2024, 2, 29, tzinfo=UTC)) == datetime(2025, 2, 28, tzinfo=UTC)
    result = expires_at_for(datetime(2026, 12, 31, tzinfo=UTC))
    assert (result.year, result.month, result.day) == (2027, 12, 31)
    assert result.tzinfo is UTC


def test_package_veto_defaults_to_false() -> None:
    package = MetaPackage(
        package_id="example-package",
        name="Example package",
        cards=("Sol Ring",),
        roles=("ramp",),
        categories=(MetaCategory.HIGH_POWER,),
    )
    assert package.vetoed_by_games is False


def test_new_fields_do_not_change_functional_profile() -> None:
    """PR1 promises no scoring change: profiles built from a snapshot with
    all new fields populated must equal profiles from the same snapshot
    without them (only new fields differ).

    PR4 keeps that promise for every new field except tier, which now
    rides the profile so the guardrail caps can apply; the profile hash
    and all dimensions stay identical.
    """

    plain = _snapshot(_source(), _deck())
    enriched = _snapshot(
        _source(
            tier=MetaTier.A,
            band=MetaCategory.HIGH_POWER,
            sample_size=53,
            expires_at=datetime(2027, 8, 5, tzinfo=UTC),
        ),
        _deck(
            band=FormatBand.HIGH_POWER,
            target_deck_ref=MetaTargetDeckRef(
                path="handover/2026-10-22/example-deck/",
                commit="0123456789abcdef0123456789abcdef01234567",
            ),
        ),
    )
    plain_profile = build_meta_functional_profile(
        plain, commander=COMMANDER, format_band=FormatBand.HIGH_POWER, profiles={}
    )
    enriched_profile = build_meta_functional_profile(
        enriched, commander=COMMANDER, format_band=FormatBand.HIGH_POWER, profiles={}
    )
    plain_dump = plain_profile.model_dump(mode="json")
    enriched_dump = enriched_profile.model_dump(mode="json")
    assert plain_dump.pop("source_tier") is None
    assert enriched_dump.pop("source_tier") == "A"
    assert plain_dump == enriched_dump
    assert plain_profile.profile_hash == enriched_profile.profile_hash


def test_card_frequency_fields_unchanged() -> None:
    frequency = MetaCardFrequency(
        commander=COMMANDER,
        format_band=FormatBand.HIGH_POWER,
        sample_size=3,
        card_counts={"Sol Ring": 3},
        card_frequencies={"Sol Ring": 1.0},
        small_sample=True,
    )
    assert frequency.sample_size == 3
    assert frequency.small_sample is True
    assert json.loads(frequency.model_dump_json())["format_band"] == "high_power"
