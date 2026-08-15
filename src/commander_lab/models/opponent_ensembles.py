from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import FrozenModel, MutableModel, NumericRange


class ObservationStatus(StrEnum):
    """Source status for opponent-card assumptions, not empirical game evidence."""

    DIRECTLY_OBSERVED = "directly_observed"
    REPORTED_BY_PLAYER = "reported_by_player"
    INFERRED_ROLE = "inferred_role"
    UNKNOWN = "unknown"
    SYNTHETIC_ASSUMPTION = "synthetic_assumption"


OPPONENT_ENSEMBLE_SCHEMA_VERSION = "1.1.0"


class EnsembleWeightMode(StrEnum):
    UNWEIGHTED = "unweighted"
    EQUAL = "equal"
    OBSERVATION_BASED = "observation_based"
    MANUAL = "manual"
    WORST_CASE = "worst_case"


class OpponentCardAssumption(FrozenModel):
    card_name: str
    status: ObservationStatus
    color_identity: frozenset[str] = frozenset()
    source_ids: tuple[str, ...] = ()
    notes: str | None = None


class ObservedConstraint(FrozenModel):
    constraint_id: str
    kind: str
    value: str
    status: ObservationStatus = ObservationStatus.DIRECTLY_OBSERVED
    source_id: str | None = None
    required: bool = True


class UncertaintyDimension(FrozenModel):
    name: str
    minimum: float
    maximum: float
    assumed_value: float | None = None
    source_ids: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)


class VariantWeight(FrozenModel):
    mode: EnsembleWeightMode
    value: float | None = Field(default=None, ge=0, le=1)
    source_ids: tuple[str, ...] = ()
    rationale: str | None = None


class OpponentVariant(FrozenModel):
    variant_id: str
    name: str
    commander: str
    commander_color_identity: frozenset[str]
    known_cards: tuple[OpponentCardAssumption, ...] = ()
    assumed_cards: tuple[OpponentCardAssumption, ...] = ()
    role_distribution: dict[str, float] = Field(default_factory=dict)
    speed_turn_range: NumericRange | None = None
    interaction_density: NumericRange | None = None
    wipe_count_range: NumericRange | None = None
    win_axes: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    weight: VariantWeight = Field(
        default_factory=lambda: VariantWeight(mode=EnsembleWeightMode.UNWEIGHTED)
    )
    synthetic: bool = True
    deck_version: str = "unknown"
    assumptions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def colors_and_statuses(self) -> OpponentVariant:
        for card in (*self.known_cards, *self.assumed_cards):
            if not card.color_identity.issubset(self.commander_color_identity):
                raise ValueError(f"card {card.card_name} violates commander color identity")
        if any(c.status == ObservationStatus.SYNTHETIC_ASSUMPTION for c in self.known_cards):
            raise ValueError("known_cards cannot be synthetic assumptions")
        if any(c.status == ObservationStatus.DIRECTLY_OBSERVED for c in self.assumed_cards):
            raise ValueError("assumed_cards cannot be directly observed")
        overlap = {c.card_name for c in self.known_cards} & {
            c.card_name for c in self.assumed_cards
        }
        if overlap:
            raise ValueError(f"cards cannot be both known and assumed: {sorted(overlap)}")
        return self


class OpponentEnsemble(MutableModel):
    schema_version: str = OPPONENT_ENSEMBLE_SCHEMA_VERSION
    ensemble_id: str
    version: int = Field(default=1, ge=1)
    name: str
    commander: str
    commander_color_identity: frozenset[str]
    variants: list[OpponentVariant]
    observed_constraints: tuple[ObservedConstraint, ...] = ()
    weight_mode: EnsembleWeightMode = EnsembleWeightMode.UNWEIGHTED
    source_ids: tuple[str, ...] = ()
    supersedes_ensemble_id: str | None = None
    automatic_profile_overwrite: bool = False

    @model_validator(mode="after")
    def validate_ensemble(self) -> OpponentEnsemble:
        if not self.variants:
            raise ValueError("ensemble requires at least one variant")
        ids = [v.variant_id for v in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("variant IDs must be unique")
        if any(v.commander != self.commander for v in self.variants):
            raise ValueError("all variants require the ensemble commander")
        if any(v.commander_color_identity != self.commander_color_identity for v in self.variants):
            raise ValueError("variant commander color identity must match the ensemble")
        required_cards = {
            c.value for c in self.observed_constraints if c.kind == "card_present" and c.required
        }
        prohibited = {
            c.value for c in self.observed_constraints if c.kind == "card_absent" and c.required
        }
        for v in self.variants:
            known = {c.card_name for c in v.known_cards}
            assumed = {c.card_name for c in v.assumed_cards}
            if not required_cards.issubset(known):
                raise ValueError(f"variant {v.variant_id} misses observed known cards")
            if prohibited & (known | assumed):
                raise ValueError(f"variant {v.variant_id} contradicts observed absence")
        values = [v.weight.value for v in self.variants]
        if self.weight_mode in {
            EnsembleWeightMode.UNWEIGHTED,
            EnsembleWeightMode.EQUAL,
            EnsembleWeightMode.WORST_CASE,
        }:
            if any(x is not None for x in values):
                raise ValueError(
                    "unweighted, equal, and worst-case ensembles cannot contain numeric weights"
                )
        else:
            if any(x is None for x in values):
                raise ValueError("weighted ensemble requires every weight")
            if abs(sum(x or 0 for x in values) - 1.0) > 1e-6:
                raise ValueError("variant weights must sum to one")
        return self


class RobustnessScenario(FrozenModel):
    scenario_id: str
    ensemble_id: str
    variant_id: str
    assumption_dimension: str
    synthetic: bool
    confidence: float | None = Field(default=None, ge=0, le=1)


class EnsembleMatchupResult(FrozenModel):
    deck_id: str
    deck_hash: str
    ensemble_id: str
    per_variant: tuple[dict[str, Any], ...]
    average: float
    median: float
    worst: float
    best: float
    spread: float
    positive_variant_share: float
    most_sensitive_assumption: str | None = None
    weight_mode: EnsembleWeightMode = EnsembleWeightMode.UNWEIGHTED
    aggregate_interpretation: str = "equal_weight_reference"
    estimate_type: str = "structural_model_estimates"
