from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from commander_lab.models.meta import (
    FormatBand,
    MetaCardFrequency,
    MetaCategory,
    MetaDeckSnapshot,
    MetaKnowledgeBaseSnapshot,
    MetaSnapshotManifest,
    MetaSource,
    PrimerReference,
    TournamentResult,
    card_frequency,
)
from commander_lab.storage import atomic_write_json, sha256_value

META_ROOT = Path("data/meta")


def stable_deck_hash(cards: tuple[str, ...]) -> str:
    normalized = [card.strip().casefold() for card in cards]
    return sha256_value(sorted(normalized))


def _now() -> datetime:
    return datetime.now(UTC)


class _DriftRow(TypedDict):
    card: str
    frequency_delta: float
    old_count: int
    new_count: int


class MetaKnowledgeBase:
    """Append-only versioned meta reference store.

    The store never writes to canonical deck, inventory or allocation files. It only writes under
    data/meta and data/runs/meta_reports.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.meta_root = self.root / META_ROOT
        for subdir in (
            "snapshots",
            "tournament_results",
            "primers",
            "archetypes",
            "packages",
            "card_frequencies",
            "provenance",
            "manifests",
        ):
            (self.meta_root / subdir).mkdir(parents=True, exist_ok=True)

    def snapshot_path(self, snapshot_id: str) -> Path:
        return self.meta_root / "snapshots" / f"{snapshot_id}.json"

    def load_snapshot(self, snapshot_id: str = "latest") -> MetaKnowledgeBaseSnapshot:
        if snapshot_id == "latest":
            pointer = self.meta_root / "manifests" / "latest.json"
            if not pointer.exists():
                raise FileNotFoundError("no meta latest pointer exists")
            payload = json.loads(pointer.read_text(encoding="utf-8"))
            snapshot_id = payload["snapshot_id"]
        return MetaKnowledgeBaseSnapshot.model_validate_json(
            self.snapshot_path(snapshot_id).read_text(encoding="utf-8")
        )

    def write_snapshot(self, snapshot: MetaKnowledgeBaseSnapshot) -> Path:
        path = self.snapshot_path(snapshot.manifest.snapshot_id)
        if path.exists():
            raise FileExistsError(
                f"immutable snapshot already exists: {snapshot.manifest.snapshot_id}"
            )
        atomic_write_json(path, snapshot.model_dump(mode="json"))
        atomic_write_json(
            self.meta_root / "manifests" / "latest.json",
            {
                "snapshot_id": snapshot.manifest.snapshot_id,
                "created_at": snapshot.manifest.created_at.isoformat(),
                "path": str(path.relative_to(self.root)),
            },
        )
        for frequency in snapshot.card_frequencies:
            safe_commander = (
                frequency.commander.lower().replace(" ", "_").replace("/", "-").replace(",", "")
            )
            atomic_write_json(
                self.meta_root
                / "card_frequencies"
                / f"{safe_commander}-{frequency.format_band}.json",
                frequency.model_dump(mode="json"),
            )
        atomic_write_json(
            self.meta_root / "provenance" / f"{snapshot.manifest.snapshot_id}-sources.json",
            {
                "snapshot_id": snapshot.manifest.snapshot_id,
                "sources": [source.model_dump(mode="json") for source in snapshot.sources],
            },
        )
        return path

    def create_snapshot(
        self,
        *,
        snapshot_id: str,
        sources: tuple[MetaSource, ...],
        deck_snapshots: tuple[MetaDeckSnapshot, ...],
        tournament_results: tuple[TournamentResult, ...] = (),
        primer_references: tuple[PrimerReference, ...] = (),
        archetypes: tuple[Any, ...] = (),
        packages: tuple[Any, ...] = (),
        notes: str | None = None,
    ) -> MetaKnowledgeBaseSnapshot:
        categories = tuple(
            sorted({cat for source in sources for cat in source.categories}, key=str)
        )
        frequencies: list[MetaCardFrequency] = []
        seen_pairs: set[tuple[str, FormatBand]] = set()
        for deck in deck_snapshots:
            pair = (deck.commander, deck.format_band)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                frequencies.append(card_frequency(deck.commander, deck.format_band, deck_snapshots))
        manifest = MetaSnapshotManifest(
            snapshot_id=snapshot_id,
            created_at=_now(),
            source_ids=tuple(source.source_id for source in sources),
            deck_hashes=tuple(deck.deck_hash for deck in deck_snapshots),
            categories=categories,
            notes=notes,
        )
        return MetaKnowledgeBaseSnapshot(
            manifest=manifest,
            sources=sources,
            deck_snapshots=deck_snapshots,
            tournament_results=tournament_results,
            primer_references=primer_references,
            archetypes=archetypes,
            packages=packages,
            card_frequencies=tuple(frequencies),
        )

    def query_cards(
        self,
        commander: str | None = None,
        format_band: FormatBand | None = None,
        min_frequency: float = 0.0,
    ) -> dict[str, Any]:
        snapshot = self.load_snapshot()
        rows: list[dict[str, Any]] = []
        for freq in snapshot.card_frequencies:
            if commander and freq.commander != commander:
                continue
            if format_band and freq.format_band != format_band:
                continue
            for card, value in freq.card_frequencies.items():
                if value >= min_frequency:
                    rows.append(
                        {
                            "commander": freq.commander,
                            "format_band": freq.format_band,
                            "card": card,
                            "frequency": value,
                            "sample_size": freq.sample_size,
                            "small_sample": freq.small_sample,
                        }
                    )
        rows.sort(key=lambda r: (r["frequency"], r["card"]), reverse=True)
        return {"cards": rows, "snapshot_id": snapshot.manifest.snapshot_id}

    def query_packages(
        self, commander: str | None = None, category: MetaCategory | None = None
    ) -> dict[str, Any]:
        snapshot = self.load_snapshot()
        package_map = {pkg.package_id: pkg for pkg in snapshot.packages}
        observed: Counter[str] = Counter()
        for deck in snapshot.deck_snapshots:
            if commander and deck.commander != commander:
                continue
            if category and category not in deck.categories:
                continue
            observed.update(deck.packages)
        rows = []
        for package_id, count in sorted(observed.items()):
            package = package_map.get(package_id)
            rows.append(
                {
                    "package_id": package_id,
                    "count": count,
                    "name": package.name if package else package_id,
                    "cards": list(package.cards) if package else [],
                    "roles": list(package.roles) if package else [],
                }
            )
        return {"packages": rows, "snapshot_id": snapshot.manifest.snapshot_id}

    def compare_deck_to_meta(
        self, deck_cards: tuple[str, ...], *, commander: str, format_band: FormatBand | None = None
    ) -> dict[str, Any]:
        snapshot = self.load_snapshot()
        own = set(deck_cards)
        refs = [
            d
            for d in snapshot.deck_snapshots
            if d.commander == commander and (format_band is None or d.format_band == format_band)
        ]
        if not refs:
            raise ValueError("no matching meta snapshots")
        meta_cards = set().union(*(set(d.decklist) for d in refs))
        meta_counter: Counter[str] = Counter()
        for d in refs:
            meta_counter.update(set(d.decklist))
        common = sorted(own & meta_cards)
        only_own = sorted(own - meta_cards)
        only_meta = sorted(meta_cards - own)
        role_estimate = self._role_density(deck_cards)
        meta_role_estimate = self._role_density(tuple(meta_cards))
        return {
            "snapshot_id": snapshot.manifest.snapshot_id,
            "commander": commander,
            "format_band": str(format_band) if format_band else "any",
            "reference_snapshot_count": len(refs),
            "common_cards": common,
            "own_only_cards": only_own,
            "meta_only_cards": only_meta,
            "meta_top_cards_not_in_own": [
                card for card, _ in meta_counter.most_common() if card not in own
            ][:25],
            "own_role_density": role_estimate,
            "meta_role_density": meta_role_estimate,
            "context_warning": (
                "Meta overlap is evidence only; it must not automatically "
                "change the current deck, inventory or allocation."
            ),
        }

    def compare_periods(
        self, older_snapshot_id: str, newer_snapshot_id: str, *, commander: str | None = None
    ) -> dict[str, Any]:
        older = self.load_snapshot(older_snapshot_id)
        newer = self.load_snapshot(newer_snapshot_id)

        def counts(snapshot: MetaKnowledgeBaseSnapshot) -> Counter[str]:
            c: Counter[str] = Counter()
            for deck in snapshot.deck_snapshots:
                if commander and deck.commander != commander:
                    continue
                c.update(set(deck.decklist))
            return c

        old_counts, new_counts = counts(older), counts(newer)
        all_cards = set(old_counts) | set(new_counts)
        old_n = max(
            1, sum(1 for d in older.deck_snapshots if not commander or d.commander == commander)
        )
        new_n = max(
            1, sum(1 for d in newer.deck_snapshots if not commander or d.commander == commander)
        )
        drift = []
        for card in all_cards:
            delta = new_counts[card] / new_n - old_counts[card] / old_n
            if abs(delta) > 0:
                drift.append(
                    {
                        "card": card,
                        "frequency_delta": delta,
                        "old_count": old_counts[card],
                        "new_count": new_counts[card],
                    }
                )
        drift.sort(key=lambda r: abs(r["frequency_delta"]), reverse=True)
        return {
            "older_snapshot_id": older_snapshot_id,
            "newer_snapshot_id": newer_snapshot_id,
            "commander": commander,
            "sample_warning": "small sample" if min(old_n, new_n) < 5 else None,
            "rising_cards": [r for r in drift if r["frequency_delta"] > 0][:25],
            "falling_cards": [r for r in drift if r["frequency_delta"] < 0][:25],
            "new_packages": sorted(
                set(p for d in newer.deck_snapshots for p in d.packages)
                - set(p for d in older.deck_snapshots for p in d.packages)
            ),
            "disappeared_packages": sorted(
                set(p for d in older.deck_snapshots for p in d.packages)
                - set(p for d in newer.deck_snapshots for p in d.packages)
            ),
        }

    @staticmethod
    def _role_density(cards: tuple[str, ...]) -> dict[str, int]:
        names = {c.lower() for c in cards}
        return {
            "ramp_proxy": sum(
                any(
                    k in n
                    for k in (
                        "sol ring",
                        "mox",
                        "signet",
                        "ritual",
                        "lotus",
                        "talisman",
                        "birds",
                        "hierarch",
                        "treasure",
                    )
                )
                for n in names
            ),
            "draw_proxy": sum(
                any(
                    k in n
                    for k in (
                        "study",
                        "remora",
                        "necropotence",
                        "draw",
                        "clamp",
                        "curiosity",
                        "insight",
                    )
                )
                for n in names
            ),
            "interaction_proxy": sum(
                any(
                    k in n
                    for k in (
                        "counter",
                        "force",
                        "blast",
                        "swords",
                        "decay",
                        "claim",
                        "silence",
                        "vigor",
                        "bolt",
                    )
                )
                for n in names
            ),
            "protection_proxy": sum(
                any(
                    k in n
                    for k in (
                        "veil",
                        "swat",
                        "silence",
                        "boots",
                        "greaves",
                        "safekeeper",
                        "deflecting",
                    )
                )
                for n in names
            ),
            "finisher_proxy": sum(
                any(
                    k in n
                    for k in (
                        "breach",
                        "oracle",
                        "brain freeze",
                        "food chain",
                        "ad nauseam",
                        "exsanguinate",
                        "bats",
                    )
                )
                for n in names
            ),
        }


def load_latest_meta_snapshot(root: str | Path) -> MetaKnowledgeBaseSnapshot:
    return MetaKnowledgeBase(root).load_snapshot()
