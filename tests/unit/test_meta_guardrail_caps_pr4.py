"""Meta-Lane PR4: guardrail caps, meta floor, and game veto (design §5.1-§5.3).

Caps bound the weight of an external meta signal by source tier; the floor
bounds how far the meta deduction may push an objective; the veto records
that paired games overruled a package. No test here uses snapshots, games,
or collection data.
"""

from datetime import UTC, datetime

from commander_lab.models import (
    FormatBand,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaPackage,
    MetaSnapshotManifest,
    MetaSource,
    MetaTier,
)

ROGSHAI = "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh"
WHOLE_DECK_META_SNAPSHOT_ID = "meta-2026-08-13-whole-deck-phase2-1"


def _snapshot_with_tiers(pairs: tuple[tuple[str, MetaTier | None], ...]):
    """Minimal snapshot with one deck per (source_id, tier) pair."""
    sources = tuple(
        MetaSource(
            source_id=source_id,
            title=f"Source {source_id}",
            retrieved_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_type="aggregator",
            categories=(MetaCategory.HIGH_POWER,),
            evidence_quality=MetaEvidenceRating.AGGREGATOR,
            tier=tier,
        )
        for source_id, tier in pairs
    )
    decks = tuple(
        MetaDeckSnapshot(
            source_id=source_id,
            commander="Test Commander",
            deck_hash=f"{index + 1:064x}",
            retrieved_at=datetime(2026, 10, 25, tzinfo=UTC),
            format_band=FormatBand.HIGH_POWER,
            categories=(MetaCategory.HIGH_POWER,),
            decklist=("Lightning Bolt",),
        )
        for index, (source_id, _tier) in enumerate(pairs)
    )
    return MetaKnowledgeBaseSnapshot(
        manifest=MetaSnapshotManifest(
            snapshot_id="test-pr4-1",
            created_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_ids=tuple(source_id for source_id, _ in pairs),
            deck_hashes=tuple(deck.deck_hash for deck in decks),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        sources=sources,
        deck_snapshots=decks,
    )


def _veto_snapshot() -> MetaKnowledgeBaseSnapshot:
    packages = (
        MetaPackage(
            package_id="pkg-a",
            name="A",
            cards=("Lightning Bolt",),
            roles=("removal",),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        MetaPackage(
            package_id="pkg-b",
            name="B",
            cards=("Counterspell",),
            roles=("counter",),
            categories=(MetaCategory.HIGH_POWER,),
            vetoed_by_games=True,
        ),
    )
    return MetaKnowledgeBaseSnapshot(
        manifest=MetaSnapshotManifest(
            snapshot_id="test-pr4-veto",
            created_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_ids=(),
            deck_hashes=(),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        sources=(),
        deck_snapshots=(),
        packages=packages,
    )
