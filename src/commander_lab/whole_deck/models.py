from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from commander_lab.models import DataQuality, FormatBand, FrozenModel

POLICY_SCHEMA_VERSION = "1.0.0"
POLICY_SET_VERSION = "2026-08-13.1"


class PolicyId(StrEnum):
    CURRENT_CONTROL = "CURRENT_CONTROL"
    OWNED_POOL_NEUTRAL = "OWNED_POOL_NEUTRAL"
    META_LIGHT = "META_LIGHT"
    META_MEDIUM = "META_MEDIUM"
    META_HIGH = "META_HIGH"
    MAX_FEASIBLE_META_SHAPE = "MAX_FEASIBLE_META_SHAPE"
    LOW_LAND_HIGH_VELOCITY = "LOW_LAND_HIGH_VELOCITY"
    RESILIENT_COMMANDER_INDEPENDENT = "RESILIENT_COMMANDER_INDEPENDENT"
    INTERACTION_HEAVY_LOCAL_META = "INTERACTION_HEAVY_LOCAL_META"


class TargetCorridor(FrozenModel):
    preferred_minimum: float
    preferred_maximum: float
    weight: float = Field(default=1.0, ge=0.0)
    hard_minimum: float | None = None
    hard_maximum: float | None = None

    @model_validator(mode="after")
    def ordered(self) -> TargetCorridor:
        if self.preferred_minimum > self.preferred_maximum:
            raise ValueError("preferred corridor minimum exceeds maximum")
        if self.hard_minimum is not None and self.hard_minimum > self.preferred_minimum:
            raise ValueError("hard minimum must not exceed preferred minimum")
        if self.hard_maximum is not None and self.hard_maximum < self.preferred_maximum:
            raise ValueError("hard maximum must not be below preferred maximum")
        if (
            self.hard_minimum is not None
            and self.hard_maximum is not None
            and self.hard_minimum > self.hard_maximum
        ):
            raise ValueError("hard corridor minimum exceeds maximum")
        return self


class DeckDesignPolicy(FrozenModel):
    policy_id: PolicyId
    policy_version: str = POLICY_SET_VERSION
    schema_version: str = POLICY_SCHEMA_VERSION
    target_corridors: dict[str, TargetCorridor] = Field(default_factory=dict)
    contextual_weights: dict[str, float] = Field(default_factory=dict)
    meta_band_weights: dict[FormatBand, float] = Field(default_factory=dict)
    functional_meta_weight: float = Field(default=0.0, ge=0.0)
    notes: str | None = None

    @model_validator(mode="after")
    def valid_weights(self) -> DeckDesignPolicy:
        if any(value < 0.0 for value in self.contextual_weights.values()):
            raise ValueError("contextual weights must be non-negative")
        if any(value < 0.0 for value in self.meta_band_weights.values()):
            raise ValueError("meta band weights must be non-negative")
        return self


class CardFeatureVector(FrozenModel):
    oracle_name: str
    mana_value: float
    roles: tuple[str, ...]
    role_strengths: dict[str, float]
    mechanic_tags: tuple[str, ...]
    color_requirements: dict[str, int]
    color_identity: tuple[str, ...]
    produces_colors: tuple[str, ...]
    is_land: bool
    is_permanent: bool
    is_creature: bool
    commander_synergy: float
    floor_value: float
    immediate_impact: float
    turn_cycle_risk: float
    multiplayer_scaling: float
    package_ids: tuple[str, ...]
    feature_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CardFeatureConfidence(FrozenModel):
    oracle_name: str
    source_quality: DataQuality
    source_count: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_label: Literal[
        "authoritative_or_verified_structural_profile",
        "project_inferred_structural_profile",
        "synthetic_or_unknown_structural_profile",
    ]


class ContextualCardUtility(FrozenModel):
    oracle_name: str
    policy_id: PolicyId
    policy_version: str
    components: dict[str, float]
    search_utility: float
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_type: Literal["search_heuristic_not_empirical_or_causal"] = (
        "search_heuristic_not_empirical_or_causal"
    )


class FunctionalEvidenceQuality(StrEnum):
    STRUCTURAL = "structural_profile"
    PARTIAL_STRUCTURAL = "partial_structural_coverage"
    MIXED = "mixed_structural_and_low_evidence_fallback"
    LOW_EVIDENCE_FALLBACK = "low_evidence_name_fallback"
    UNKNOWN = "unknown"


class FunctionalDimension(FrozenModel):
    value: float | None = None
    support_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_quality: FunctionalEvidenceQuality = FunctionalEvidenceQuality.UNKNOWN


class MetaFunctionalProfile(FrozenModel):
    profile_id: str
    format_band: FormatBand
    source_snapshot_id: str
    reference_deck_count: int = Field(ge=1)
    dimensions: dict[str, FunctionalDimension]
    package_density: dict[str, FunctionalDimension] = Field(default_factory=dict)
    profiled_card_count: int = Field(ge=0)
    missing_profile_cards: tuple[str, ...] = ()
    name_fallback_cards: tuple[str, ...] = ()
    profile_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FunctionalMetaDistance(FrozenModel):
    format_band: FormatBand
    raw_distance: float | None = Field(default=None, ge=0.0)
    policy_weighted_distance: float | None = Field(default=None, ge=0.0)
    compared_dimensions: tuple[str, ...] = ()
    unknown_dimensions: tuple[str, ...] = ()
    component_distances: dict[str, float] = Field(default_factory=dict)
    evidence_quality: FunctionalEvidenceQuality = FunctionalEvidenceQuality.UNKNOWN
    evidence_type: Literal["structural_reference_distance_not_performance"] = (
        "structural_reference_distance_not_performance"
    )
