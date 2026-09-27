from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .common import FrozenModel, MutableModel

META_SCHEMA_VERSION = "1.0.0"


class MetaCategory(StrEnum):
    LOCAL_META = "local_meta"
    NORMAL_FOUR_PLAYER = "normal_four_player"
    COMMANDER_THREE_PLAYER = "commander_3_player"
    COMMANDER_FIVE_PLAYER = "commander_5_player"
    HIGH_POWER = "high_power"
    CEDH_TOURNAMENT = "cedh_tournament"
    LARGE_POD = "large_pod"
    HISTORICAL_REFERENCE = "historical_reference"
    SYNTHETIC_ASSUMPTION = "synthetic_assumption"


class MetaEvidenceRating(StrEnum):
    AUTHORITATIVE_TOURNAMENT = "authoritative_tournament"
    VERIFIED_DECKLIST = "verified_decklist"
    ESTABLISHED_PRIMER = "established_primer"
    AGGREGATOR = "aggregator"
    LOCAL_PROJECT_CONTEXT = "local_project_context"
    PARTIAL_OR_SYNTHETIC = "partial_or_synthetic"


class FormatBand(StrEnum):
    LOCAL_META = "local_meta"
    NORMAL_FOUR_PLAYER = "normal_four_player"
    COMMANDER_THREE_PLAYER = "commander_3_player"
    COMMANDER_FIVE_PLAYER = "commander_5_player"
    HIGH_POWER = "high_power"
    CEDH_TOURNAMENT = "cedh_tournament"
    LARGE_POD = "large_pod"
    HISTORICAL_REFERENCE = "historical_reference"
    SYNTHETIC_ASSUMPTION = "synthetic_assumption"


class BudgetBand(StrEnum):
    UNKNOWN = "unknown"
    BUDGET = "budget"
    MID_BUDGET = "mid_budget"
    HIGH_POWER = "high_power"
    CEDH = "cedh"
    PROXY_FRIENDLY = "proxy_friendly"


class MetaSource(FrozenModel):
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    title: str
    url: str | None = None
    author: str | None = None
    retrieved_at: datetime
    published_at: datetime | None = None
    source_type: Literal[
        "tournament", "decklist", "primer", "aggregator", "local_context", "synthetic"
    ]
    categories: tuple[MetaCategory, ...]
    evidence_quality: MetaEvidenceRating
    license_notes: str = "reference metadata and short structured extraction only"
    notes: str | None = None

    @model_validator(mode="after")
    def validate_categories(self) -> MetaSource:
        if not self.categories:
            raise ValueError("at least one meta category is required")
        return self


class MetaPackage(FrozenModel):
    package_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{1,127}$")
    name: str
    cards: tuple[str, ...]
    roles: tuple[str, ...]
    categories: tuple[MetaCategory, ...]
    description: str | None = None


class MetaArchetype(FrozenModel):
    archetype_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{1,127}$")
    name: str
    commanders: tuple[str, ...]
    categories: tuple[MetaCategory, ...]
    primary_plan: str
    secondary_plan: str | None = None
    win_conditions: tuple[str, ...] = ()
    interaction_profile: dict[str, float | int | str] = Field(default_factory=dict)
    packages: tuple[str, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None


class TournamentResult(FrozenModel):
    source_id: str
    event_name: str
    event_date: datetime | None = None
    pod_size: int = Field(default=4, ge=2, le=10)
    placement: str | None = None
    player_count: int | None = Field(default=None, ge=1)
    wins: int | None = Field(default=None, ge=0)
    losses: int | None = Field(default=None, ge=0)
    draws: int | None = Field(default=None, ge=0)
    format_band: FormatBand
    notes: str | None = None

    @model_validator(mode="after")
    def validate_pod_context(self) -> TournamentResult:
        if self.format_band == FormatBand.CEDH_TOURNAMENT and self.pod_size != 4:
            raise ValueError(
                "cEDH tournament results in this project must be modeled as 4-player pods"
            )
        return self


class PrimerReference(FrozenModel):
    source_id: str
    commander: str
    title: str
    key_points: tuple[str, ...]
    sequencing_notes: tuple[str, ...] = ()
    categories: tuple[MetaCategory, ...]
    evidence_quality: MetaEvidenceRating
    transfer_limitations: tuple[str, ...] = ()


class MetaDeckSnapshot(FrozenModel):
    source_id: str
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: datetime
    published_at: datetime | None = None
    format_band: FormatBand
    categories: tuple[MetaCategory, ...]
    pod_size: int | None = Field(default=4, ge=2, le=10)
    budget_band: BudgetBand = BudgetBand.UNKNOWN
    event_name: str | None = None
    placement: str | None = None
    player_count: int | None = Field(default=None, ge=1)
    decklist: tuple[str, ...]
    packages: tuple[str, ...] = ()
    primary_plan: str | None = None
    secondary_plan: str | None = None
    win_conditions: tuple[str, ...] = ()
    interaction_profile: dict[str, float | int | str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    license_notes: str = "reference metadata and card-name extraction only"

    @field_validator("decklist")
    @classmethod
    def no_empty_cards(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("decklist must contain at least one card name")
        normalized = tuple(card.strip() for card in value if card and card.strip())
        if len(normalized) != len(value):
            raise ValueError("decklist contains empty card names")
        return normalized

    @model_validator(mode="after")
    def validate_transfer_rules(self) -> MetaDeckSnapshot:
        if (
            self.format_band == FormatBand.CEDH_TOURNAMENT
            and MetaCategory.CEDH_TOURNAMENT not in self.categories
        ):
            raise ValueError(
                "cEDH tournament deck snapshots must include the cedh_tournament category"
            )
        if (
            MetaCategory.LOCAL_META in self.categories
            and self.format_band == FormatBand.CEDH_TOURNAMENT
        ):
            raise ValueError(
                "local meta and cEDH tournament must not be collapsed into one context"
            )
        return self


class MetaCardFrequency(FrozenModel):
    commander: str
    format_band: FormatBand
    sample_size: int = Field(ge=1)
    card_counts: dict[str, int]
    card_frequencies: dict[str, float]
    small_sample: bool


class MetaSnapshotManifest(FrozenModel):
    snapshot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    created_at: datetime
    schema_version: str = META_SCHEMA_VERSION
    source_ids: tuple[str, ...]
    deck_hashes: tuple[str, ...]
    categories: tuple[MetaCategory, ...]
    immutable: bool = True
    supersedes: tuple[str, ...] = ()
    notes: str | None = None


class MetaKnowledgeBaseSnapshot(MutableModel):
    manifest: MetaSnapshotManifest
    sources: tuple[MetaSource, ...]
    deck_snapshots: tuple[MetaDeckSnapshot, ...]
    tournament_results: tuple[TournamentResult, ...] = ()
    primer_references: tuple[PrimerReference, ...] = ()
    archetypes: tuple[MetaArchetype, ...] = ()
    packages: tuple[MetaPackage, ...] = ()
    card_frequencies: tuple[MetaCardFrequency, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> MetaKnowledgeBaseSnapshot:
        source_ids = {source.source_id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("duplicate source_id in snapshot")
        for deck in self.deck_snapshots:
            if deck.source_id not in source_ids:
                raise ValueError(f"deck references unknown source_id: {deck.source_id}")
        for result in self.tournament_results:
            if result.source_id not in source_ids:
                raise ValueError(
                    f"tournament result references unknown source_id: {result.source_id}"
                )
        for primer in self.primer_references:
            if primer.source_id not in source_ids:
                raise ValueError(f"primer references unknown source_id: {primer.source_id}")
        if not self.manifest.immutable:
            raise ValueError("meta snapshots must be immutable")
        return self


def card_frequency(
    commander: str, format_band: FormatBand, snapshots: tuple[MetaDeckSnapshot, ...]
) -> MetaCardFrequency:
    relevant = [
        snapshot
        for snapshot in snapshots
        if snapshot.commander == commander and snapshot.format_band == format_band
    ]
    if not relevant:
        raise ValueError("no matching snapshots for frequency calculation")
    counts: Counter[str] = Counter()
    for snapshot in relevant:
        counts.update(set(snapshot.decklist))
    sample_size = len(relevant)
    freqs = {card: count / sample_size for card, count in sorted(counts.items())}
    return MetaCardFrequency(
        commander=commander,
        format_band=format_band,
        sample_size=sample_size,
        card_counts=dict(sorted(counts.items())),
        card_frequencies=freqs,
        small_sample=sample_size < 5,
    )
