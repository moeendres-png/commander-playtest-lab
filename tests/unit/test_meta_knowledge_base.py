from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from commander_lab.meta.store import MetaKnowledgeBase, stable_deck_hash
from commander_lab.models import (
    BudgetBand,
    CompareDeckToMetaInput,
    CreateMetaSnapshotInput,
    FormatBand,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaSnapshotManifest,
    MetaSource,
    QueryMetaCardsInput,
    QueryMetaPackagesInput,
)
from commander_lab.tools import CommanderToolService


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


def _deck(source_id: str = "src-a", cards=("Sol Ring", "Silence", "Brain Freeze"), *, fmt=FormatBand.CEDH_TOURNAMENT, categories=(MetaCategory.CEDH_TOURNAMENT,)) -> MetaDeckSnapshot:
    return MetaDeckSnapshot(
        source_id=source_id,
        commander="Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh",
        deck_hash=stable_deck_hash(tuple(cards)),
        retrieved_at=datetime(2026, 8, 5, tzinfo=UTC),
        format_band=fmt,
        categories=categories,
        budget_band=BudgetBand.CEDH,
        decklist=tuple(cards),
    )


def test_stable_deck_hash_ignores_order_and_case() -> None:
    assert stable_deck_hash(("Sol Ring", "Silence")) == stable_deck_hash(("silence", "SOL RING"))


def test_duplicate_sources_are_rejected() -> None:
    manifest = MetaSnapshotManifest(
        snapshot_id="meta-test",
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_ids=("src-a", "src-a"),
        deck_hashes=(_deck().deck_hash,),
        categories=(MetaCategory.CEDH_TOURNAMENT,),
    )
    with pytest.raises(ValueError, match="duplicate source_id"):
        MetaKnowledgeBaseSnapshot(manifest=manifest, sources=(_source(), _source()), deck_snapshots=(_deck(),))


def test_same_decklist_from_multiple_sources_keeps_same_hash() -> None:
    cards = ("Sol Ring", "Silence", "Brain Freeze")
    assert _deck("src-a", cards).deck_hash == _deck("src-b", tuple(reversed(cards))).deck_hash


def test_different_version_of_same_list_changes_hash() -> None:
    assert _deck(cards=("Sol Ring", "Silence")).deck_hash != _deck(cards=("Sol Ring", "Silence", "Brain Freeze")).deck_hash


def test_missing_event_data_allowed_but_wrong_cedh_pod_rejected() -> None:
    _deck()  # missing event metadata is allowed for primer/aggregate snapshots.
    with pytest.raises(ValueError, match="cEDH tournament"):
        from commander_lab.models import TournamentResult

        TournamentResult(source_id="src-a", event_name="bad", format_band=FormatBand.CEDH_TOURNAMENT, pod_size=5)


def test_cedh_and_local_meta_are_not_collapsed() -> None:
    with pytest.raises(ValueError, match="local meta"):
        _deck(fmt=FormatBand.CEDH_TOURNAMENT, categories=(MetaCategory.CEDH_TOURNAMENT, MetaCategory.LOCAL_META))


def test_snapshot_is_immutable_on_write(tmp_path: Path) -> None:
    kb = MetaKnowledgeBase(tmp_path)
    snapshot = kb.create_snapshot(snapshot_id="meta-test", sources=(_source(),), deck_snapshots=(_deck(),))
    kb.write_snapshot(snapshot)
    with pytest.raises(FileExistsError):
        kb.write_snapshot(snapshot)


def test_unknown_source_reference_is_rejected() -> None:
    manifest = MetaSnapshotManifest(
        snapshot_id="meta-test",
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_ids=("src-a",),
        deck_hashes=(_deck("src-missing").deck_hash,),
        categories=(MetaCategory.CEDH_TOURNAMENT,),
    )
    with pytest.raises(ValueError, match="unknown source_id"):
        MetaKnowledgeBaseSnapshot(manifest=manifest, sources=(_source(),), deck_snapshots=(_deck("src-missing"),))


def test_tool_queries_do_not_mutate_local_decks() -> None:
    service = CommanderToolService(Path.cwd())
    before = json.loads((Path("data/decks/manifest.json")).read_text(encoding="utf-8"))
    cards = service.query_meta_cards(QueryMetaCardsInput(min_frequency=0.0))
    packages = service.query_meta_packages(QueryMetaPackagesInput())
    comparison = service.compare_deck_to_meta(
        CompareDeckToMetaInput(
            deck_id="rogshai/current",
            commander="Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh",
            format_band=FormatBand.LOCAL_META,
        )
    )
    after = json.loads((Path("data/decks/manifest.json")).read_text(encoding="utf-8"))
    assert cards.status == "completed"
    assert packages.status == "completed"
    assert comparison.status == "completed"
    assert before == after
    assert comparison.result["automatic_deck_application"] is False


def test_create_meta_snapshot_rejects_existing_snapshot() -> None:
    service = CommanderToolService(Path.cwd())
    response = service.create_meta_snapshot(CreateMetaSnapshotInput(snapshot_id="meta-2026-08-05-phase12-1"))
    assert response.status == "failed"
    assert "immutable snapshot already exists" in response.errors[0]
