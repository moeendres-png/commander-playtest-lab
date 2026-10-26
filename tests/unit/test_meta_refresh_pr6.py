"""Meta-Lane PR6: stale enforcement and the refresh report (design §5.6).

A meta source is valid for 12 months from retrieved_at (PR1
expires_at_for). After that boundary it contributes nothing: refs
backed by a stale source are excluded from functional profiles, a
fully stale package file attaches nothing, and the refresh script
reports freshness without refetching anything. No test here uses
games, collection data, or the network.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from commander_lab.models import (
    FormatBand,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaSnapshotManifest,
    MetaSource,
)
from commander_lab.models.meta import expires_at_for
from commander_lab.whole_deck.meta import (
    all_sources_stale,
    build_meta_functional_profile,
    is_source_stale,
    load_snapshot,
    stale_source_ids,
)

ROOT = Path(__file__).resolve().parents[2]
ROGSHAI_PACKAGES = ROOT / "data/meta/packages/rogshai-2026-10-25.json"
SNAPSHOT_08_05 = "meta-2026-08-05-phase12-1.json"
SNAPSHOT_08_13 = "meta-2026-08-13-whole-deck-phase2-1.json"
SNAPSHOT_ROGSHAI_10_25 = "meta-2026-10-25-rogshai-refresh-1.json"


def _source(source_id: str, retrieved_at: datetime) -> MetaSource:
    return MetaSource(
        source_id=source_id,
        title=f"Source {source_id}",
        retrieved_at=retrieved_at,
        source_type="aggregator",
        categories=(MetaCategory.HIGH_POWER,),
        evidence_quality=MetaEvidenceRating.AGGREGATOR,
    )


def _snapshot(
    triples: tuple[tuple[str, datetime, tuple[str, ...]], ...],
) -> MetaKnowledgeBaseSnapshot:
    """Minimal snapshot: one deck per (source_id, retrieved_at, decklist)."""
    sources = tuple(_source(source_id, retrieved_at) for source_id, retrieved_at, _ in triples)
    decks = tuple(
        MetaDeckSnapshot(
            source_id=source_id,
            commander="Test Commander",
            deck_hash=f"{index + 1:064x}",
            retrieved_at=retrieved_at,
            format_band=FormatBand.HIGH_POWER,
            categories=(MetaCategory.HIGH_POWER,),
            decklist=decklist,
        )
        for index, (source_id, retrieved_at, decklist) in enumerate(triples)
    )
    return MetaKnowledgeBaseSnapshot(
        manifest=MetaSnapshotManifest(
            snapshot_id="test-pr6-1",
            created_at=datetime(2026, 10, 25, tzinfo=UTC),
            source_ids=tuple(source_id for source_id, _, _ in triples),
            deck_hashes=tuple(deck.deck_hash for deck in decks),
            categories=(MetaCategory.HIGH_POWER,),
        ),
        sources=sources,
        deck_snapshots=decks,
    )


def test_expires_at_for_twelve_months() -> None:
    assert expires_at_for(datetime(2026, 10, 25, tzinfo=UTC)) == datetime(2027, 10, 25, tzinfo=UTC)
    assert expires_at_for(datetime(2026, 8, 5, tzinfo=UTC)) == datetime(2027, 8, 5, tzinfo=UTC)
    # Month-end clamp: 2024-02-29 + 12 months is 2025-02-28, not 2025-02-29.
    assert expires_at_for(datetime(2024, 2, 29, tzinfo=UTC)) == datetime(2025, 2, 28, tzinfo=UTC)


def test_is_source_stale_boundary() -> None:
    source = _source("src-a", datetime(2026, 10, 25, tzinfo=UTC))
    assert not is_source_stale(source, datetime(2027, 10, 24, tzinfo=UTC))
    # Stale from the boundary instant on: the 12 months are over then.
    assert is_source_stale(source, datetime(2027, 10, 25, tzinfo=UTC))
    assert is_source_stale(source, datetime(2027, 10, 26, tzinfo=UTC))


def test_is_source_stale_set_expires_at_wins() -> None:
    source = _source("src-a", datetime(2026, 10, 25, tzinfo=UTC)).model_copy(
        update={"expires_at": datetime(2027, 1, 1, tzinfo=UTC)}
    )
    assert is_source_stale(source, datetime(2027, 1, 1, tzinfo=UTC))
    assert not is_source_stale(source, datetime(2026, 12, 31, tzinfo=UTC))


def test_stale_source_ids_mixed() -> None:
    snapshot = _snapshot(
        (
            ("src-stale", datetime(2026, 1, 1, tzinfo=UTC), ("Lightning Bolt",)),
            ("src-fresh", datetime(2026, 10, 25, tzinfo=UTC), ("Counterspell",)),
        )
    )
    assert stale_source_ids(snapshot, datetime(2027, 1, 15, tzinfo=UTC)) == {"src-stale"}


def test_all_sources_stale() -> None:
    stale_only = _snapshot((("src-a", datetime(2026, 1, 1, tzinfo=UTC), ("A",)),))
    assert all_sources_stale(stale_only, datetime(2027, 1, 15, tzinfo=UTC))
    mixed = _snapshot(
        (
            ("src-a", datetime(2026, 1, 1, tzinfo=UTC), ("A",)),
            ("src-b", datetime(2026, 10, 25, tzinfo=UTC), ("B",)),
        )
    )
    assert not all_sources_stale(mixed, datetime(2027, 1, 15, tzinfo=UTC))
    fresh_only = _snapshot((("src-b", datetime(2026, 10, 25, tzinfo=UTC), ("B",)),))
    assert not all_sources_stale(fresh_only, datetime(2027, 1, 15, tzinfo=UTC))
    sourceless = _snapshot(())
    assert all_sources_stale(sourceless, datetime(2027, 1, 15, tzinfo=UTC))


def test_build_profile_excludes_stale_ref() -> None:
    snapshot = _snapshot(
        (
            ("src-fresh", datetime(2026, 10, 25, tzinfo=UTC), ("Lightning Bolt",)),
            ("src-stale", datetime(2026, 1, 1, tzinfo=UTC), ("Counterspell",)),
        )
    )
    profile = build_meta_functional_profile(
        snapshot,
        commander="Test Commander",
        format_band=FormatBand.HIGH_POWER,
        profiles={},
        now=datetime(2027, 1, 15, tzinfo=UTC),
    )
    assert profile.reference_deck_count == 1
    # The surviving ref is the fresh one: its card is the missing card.
    assert profile.missing_profile_cards == ("Lightning Bolt",)


def test_build_profile_all_stale_raises() -> None:
    snapshot = _snapshot(
        (
            ("src-a", datetime(2026, 1, 1, tzinfo=UTC), ("A",)),
            ("src-b", datetime(2026, 1, 2, tzinfo=UTC), ("B",)),
        )
    )
    with pytest.raises(ValueError, match="all matching meta snapshots stale"):
        build_meta_functional_profile(
            snapshot,
            commander="Test Commander",
            format_band=FormatBand.HIGH_POWER,
            profiles={},
            now=datetime(2027, 1, 15, tzinfo=UTC),
        )


def test_build_profile_no_match_message_unchanged() -> None:
    snapshot = _snapshot((("src-a", datetime(2026, 10, 25, tzinfo=UTC), ("A",)),))
    with pytest.raises(ValueError, match="no matching meta snapshots"):
        build_meta_functional_profile(
            snapshot,
            commander="Other Commander",
            format_band=FormatBand.HIGH_POWER,
            profiles={},
        )


def test_package_file_fresh_now_stale_later() -> None:
    snapshot = load_snapshot(ROGSHAI_PACKAGES)
    assert snapshot.sources
    assert not all_sources_stale(snapshot, datetime(2026, 10, 26, tzinfo=UTC))
    assert all_sources_stale(snapshot, datetime(2028, 1, 1, tzinfo=UTC))


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/refresh_meta.py"), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def _file_by_name(report: dict[str, object], name: str) -> dict[str, object]:
    entries = report["snapshots"]
    assert isinstance(entries, list)
    assert entries
    for entry in entries:
        assert isinstance(entry, dict)
        if str(entry["path"]).endswith(name):
            return entry
    raise AssertionError(f"snapshot not in report: {name}")


def test_refresh_script_dry_run_on_real_files() -> None:
    result = _run_script(["--root", str(ROOT), "--as-of", "2027-09-01", "--json"])
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert isinstance(report, dict)
    # At 2027-09-01 the 2026-08-05 snapshot is fully stale, the
    # 2026-10-25 refresh is fresh, and the combos file is fresh.
    assert _file_by_name(report, SNAPSHOT_08_05)["status"] == "stale"
    assert _file_by_name(report, SNAPSHOT_ROGSHAI_10_25)["status"] == "fresh"
    combos = report["combos"]
    assert isinstance(combos, dict)
    assert combos["status"] == "fresh"
    # --fail-on-stale turns the stale snapshot into exit 2.
    failed = _run_script(
        ["--root", str(ROOT), "--as-of", "2027-09-01", "--json", "--fail-on-stale"]
    )
    assert failed.returncode == 2
    # At 2027-08-10 the 08-13 snapshot is partial: its 08-05 sources
    # are stale, its 08-13 sources are fresh until 2027-08-13.
    partial = _run_script(["--root", str(ROOT), "--as-of", "2027-08-10", "--json"])
    assert partial.returncode == 0, partial.stderr
    partial_report = json.loads(partial.stdout)
    assert isinstance(partial_report, dict)
    assert _file_by_name(partial_report, SNAPSHOT_08_13)["status"] == "partial"
    # The human rendering must not crash on the same input.
    human = _run_script(["--root", str(ROOT), "--as-of", "2027-09-01"])
    assert human.returncode == 0, human.stderr
    assert "stale" in human.stdout
