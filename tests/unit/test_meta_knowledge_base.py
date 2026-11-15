"""Validation rules of the meta snapshot models (`commander_lab.models.meta`)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from commander_lab.models import (
    BudgetBand,
    FormatBand,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaSnapshotManifest,
    MetaSource,
    TournamentResult,
)
from commander_lab.storage import sha256_value


def _stable_deck_hash(cards: tuple[str, ...]) -> str:
    return sha256_value(sorted(card.strip().casefold() for card in cards))


def _source(source_id: str = "src-a", *, categories=(MetaCategory.CEDH_TOURNAMENT,)) -> MetaSource:
    return MetaSource(
        source_id=source_id,
        title="source",
        url="https://example.test/source",
        retrieved_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_type="tournament",
        categories=categories,
        evidence_quality=MetaEvidenceRating.AUTHORITATIVE_TOURNAMENT,
    )


def _deck(
    source_id: str = "src-a",
    cards=("Sol Ring", "Silence", "Brain Freeze"),
    *,
    fmt=FormatBand.CEDH_TOURNAMENT,
    categories=(MetaCategory.CEDH_TOURNAMENT,),
) -> MetaDeckSnapshot:
    return MetaDeckSnapshot(
        source_id=source_id,
        commander="Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh",
        deck_hash=_stable_deck_hash(tuple(cards)),
        retrieved_at=datetime(2026, 8, 5, tzinfo=UTC),
        format_band=fmt,
        categories=categories,
        budget_band=BudgetBand.CEDH,
        decklist=tuple(cards),
    )


def test_duplicate_sources_are_rejected() -> None:
    manifest = MetaSnapshotManifest(
        snapshot_id="meta-test",
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_ids=("src-a", "src-a"),
        deck_hashes=(_deck().deck_hash,),
        categories=(MetaCategory.CEDH_TOURNAMENT,),
    )
    with pytest.raises(ValueError, match="duplicate source_id"):
        MetaKnowledgeBaseSnapshot(
            manifest=manifest, sources=(_source(), _source()), deck_snapshots=(_deck(),)
        )


def test_missing_event_data_allowed_but_wrong_cedh_pod_rejected() -> None:
    _deck()  # missing event metadata is allowed for primer/aggregate snapshots.
    with pytest.raises(ValueError, match="cEDH tournament"):
        TournamentResult(
            source_id="src-a", event_name="bad", format_band=FormatBand.CEDH_TOURNAMENT, pod_size=5
        )


def test_cedh_and_local_meta_are_not_collapsed() -> None:
    with pytest.raises(ValueError, match="local meta"):
        _deck(
            fmt=FormatBand.CEDH_TOURNAMENT,
            categories=(MetaCategory.CEDH_TOURNAMENT, MetaCategory.LOCAL_META),
        )


def test_unknown_source_reference_is_rejected() -> None:
    manifest = MetaSnapshotManifest(
        snapshot_id="meta-test",
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_ids=("src-a",),
        deck_hashes=(_deck("src-missing").deck_hash,),
        categories=(MetaCategory.CEDH_TOURNAMENT,),
    )
    with pytest.raises(ValueError, match="unknown source_id"):
        MetaKnowledgeBaseSnapshot(
            manifest=manifest, sources=(_source(),), deck_snapshots=(_deck("src-missing"),)
        )
