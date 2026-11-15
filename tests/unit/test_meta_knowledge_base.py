from __future__ import annotations

from datetime import UTC, datetime

from commander_lab.models import (
    MetaCategory,
    MetaEvidenceRating,
    MetaSource,
)


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
