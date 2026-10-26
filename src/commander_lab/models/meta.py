from __future__ import annotations

from calendar import monthrange
from collections import Counter
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .common import FrozenModel, MutableModel

META_SCHEMA_VERSION = "1.0.0"


class MetaTier(StrEnum):
    """Evidence tier of a meta source (Meta-Lane design §2.1).

    A: tracked/aggregated primary data with stated sample and date.
    B: established guide (primer/strategy article with decklist and reasoning).
    C: single opinion without a data basis — never a strength claim, never scored.
    """

    A = "A"
    B = "B"
    C = "C"


def expires_at_for(retrieved_at: datetime) -> datetime:
    """Stale boundary of a meta record: retrieval date + 12 calendar months.

    PR1 defines the field and this computation only. Enforcement (weight 0
    after expiry) belongs to PR6 and must not be added here.
    """

    month = retrieved_at.month + 12
    year = retrieved_at.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    last_day = monthrange(year, month)[1]
    return retrieved_at.replace(year=year, month=month, day=min(retrieved_at.day, last_day))


class MetaTargetDeckRef(FrozenModel):
    """Reference to a handover target deck (path + commit), never a list copy.

    PR1 defines only the reference. Populating it for RogShai/Chulane
    belongs to PR2/PR3.
    """

    path: str = Field(min_length=1)
    commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    branch: str | None = None


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
    # PR1 provenance fields (all optional; see docs/meta/PROVENANCE_HEADER.md).
    # Tier C never enters scoring (PR4 enforces the caps); band pins the single
    # band of this source when it has exactly one, otherwise it stays None.
    tier: MetaTier | None = None
    band: MetaCategory | None = None
    sample_size: int | None = Field(default=None, ge=1)
    small_sample: bool | None = None
    # Stale boundary (retrieved_at + 12 months). Defined here; enforcement
    # (weight 0 after expiry) belongs to PR6, not PR1.
    expires_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _derive_small_sample(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        sample = data.get("sample_size")
        if (
            isinstance(sample, int)
            and not isinstance(sample, bool)
            and data.get("small_sample") is None
        ):
            return {**data, "small_sample": sample < 5}
        return data

    @model_validator(mode="after")
    def validate_categories(self) -> MetaSource:
        if not self.categories:
            raise ValueError("at least one meta category is required")
        return self

    @model_validator(mode="after")
    def validate_provenance_fields(self) -> MetaSource:
        if self.band is not None and self.band not in self.categories:
            raise ValueError("source band must be one of its categories")
        if self.expires_at is not None and self.expires_at <= self.retrieved_at:
            raise ValueError("expires_at must be after retrieved_at")
        if (
            self.sample_size is not None
            and self.small_sample is not None
            and self.small_sample != (self.sample_size < 5)
        ):
            raise ValueError("small_sample must agree with sample_size (< 5)")
        return self


class MetaPackage(FrozenModel):
    package_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{1,127}$")
    name: str
    cards: tuple[str, ...]
    roles: tuple[str, ...]
    categories: tuple[MetaCategory, ...]
    description: str | None = None
    # PR1: veto note (design §5.3). True only when paired games overruled this
    # package; the contradiction itself is documented in the PR/artifact, not
    # silently overwritten. A card-level prior veto belongs to the profile
    # prior fields and is deliberately not modeled here.
    vetoed_by_games: bool = False


class MetaComboLine(FrozenModel):
    """One known combo line as metadata (Meta-Lane PR5, design §5.4).

    This is NOT rules knowledge: it records that a source (Commander
    Spellbook or a primer/article) lists these cards as a combo. Whether
    the line actually goes through in a concrete game is decided by the
    XMage engine alone. Containment in a deck never justifies an
    inclusion, and absence never justifies a cut.
    """

    combo_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{1,127}$")
    commander: str
    cards: tuple[str, ...] = Field(min_length=1)
    # Alternative slots: each group needs at least one card present
    # (e.g. a bounce creature that may be one of several cards).
    any_of: tuple[tuple[str, ...], ...] = ()
    bands: tuple[FormatBand, ...] = Field(min_length=1)
    tier: MetaTier | None = None
    source: str
    source_url: str | None = None
    edhrec_decks: int | None = Field(default=None, ge=0)
    result: str
    notes: str | None = None

    @model_validator(mode="after")
    def _nonempty_any_of_groups(self) -> MetaComboLine:
        if any(not group for group in self.any_of):
            raise ValueError("any_of groups must not be empty")
        return self


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
    # PR1 provenance fields (all optional; see docs/meta/PROVENANCE_HEADER.md).
    # band duplicates format_band as the single-band view; it must equal
    # format_band when set. target_deck_ref is a reference only, never a copy
    # of the target decklist; populating it belongs to PR2/PR3.
    band: FormatBand | None = None
    target_deck_ref: MetaTargetDeckRef | None = None

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
        if self.band is not None and self.band != self.format_band:
            raise ValueError("deck snapshot band must equal its format_band")
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
