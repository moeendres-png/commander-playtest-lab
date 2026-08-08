from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import FrozenModel

COUNTERFACTUAL_SCHEMA_VERSION = "1.0.0"


class CounterfactualEngineMode(StrEnum):
    STRUCTURAL = "structural"
    TACTICAL_ORACLE = "tactical_oracle"
    EXTERNAL_ENGINE = "external_engine"


class HiddenInformationPolicy(StrEnum):
    SAME_REALIZED_FUTURE = "same_realized_future"
    RESAMPLED_UNKNOWN_FUTURE = "resampled_unknown_future"
    MULTIPLE_FUTURE_SAMPLES = "multiple_future_samples"
    PUBLIC_INFORMATION_ONLY = "public_information_only"


class SeedPolicy(StrEnum):
    SAME_SEED = "same_seed"
    DERIVED_SEEDS = "derived_seeds"
    EXPLICIT_SEEDS = "explicit_seeds"


class CounterfactualAction(FrozenModel):
    action_id: str
    utility: float | None = None
    legal: bool = True
    action_kind: str = "structural_action"
    target_ids: tuple[str, ...] = ()
    public_description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tactical_rule: str | None = None
    tactical_input: dict[str, Any] = Field(default_factory=dict)


class CounterfactualBranchpoint(FrozenModel):
    schema_version: str = COUNTERFACTUAL_SCHEMA_VERSION
    branchpoint_id: str
    source_run_id: str
    source_path: str
    game_id: str
    event_offset: int = Field(ge=0)
    actor_id: str
    state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_prefix_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    available_actions: tuple[CounterfactualAction, ...]
    chosen_action: str
    alternative_action: str | None = None
    engine_mode: CounterfactualEngineMode = CounterfactualEngineMode.STRUCTURAL
    seed_policy: SeedPolicy = SeedPolicy.SAME_SEED
    hidden_information_policy: HiddenInformationPolicy = HiddenInformationPolicy.PUBLIC_INFORMATION_ONLY
    event_type: str = "pilot_decision"
    phase: str | None = None
    player_eliminated: bool = False
    public_state_before: dict[str, Any] = Field(default_factory=dict)
    realized_future_summary: dict[str, float] = Field(default_factory=dict)
    validation_level: Literal[
        "structural_model_estimates",
        "tactical_oracle",
        "external_rules_engine",
    ] = "structural_model_estimates"

    @model_validator(mode="after")
    def validate_actions(self) -> "CounterfactualBranchpoint":
        ids = [row.action_id for row in self.available_actions]
        if len(ids) != len(set(ids)):
            raise ValueError("available action ids must be unique")
        if self.chosen_action not in ids:
            raise ValueError("chosen action must be available")
        if self.alternative_action is not None and self.alternative_action not in ids:
            raise ValueError("alternative action must be available")
        expected = {
            CounterfactualEngineMode.STRUCTURAL: "structural_model_estimates",
            CounterfactualEngineMode.TACTICAL_ORACLE: "tactical_oracle",
            CounterfactualEngineMode.EXTERNAL_ENGINE: "external_rules_engine",
        }[self.engine_mode]
        if self.validation_level != expected:
            raise ValueError(
                f"engine mode {self.engine_mode} requires validation_level={expected}"
            )
        return self


class CounterfactualStateDiff(FrozenModel):
    immediate_utility_delta: float
    card_advantage_delta: float = 0.0
    mana_delta: float = 0.0
    life_delta: float = 0.0
    commander_damage_delta: float = 0.0
    board_delta: float = 0.0
    hand_delta: float = 0.0
    interaction_reserve_delta: float = 0.0
    threat_delta: float = 0.0
    win_progress_delta: float = 0.0
    placement_delta: float | None = None


class CounterfactualFutureSample(FrozenModel):
    sample_index: int = Field(ge=0)
    seed: int = Field(ge=0)
    chosen_score: float
    alternative_score: float
    improvement: float
    estimated_placement_delta: float


class CounterfactualResult(FrozenModel):
    schema_version: str = COUNTERFACTUAL_SCHEMA_VERSION
    counterfactual_id: str
    branchpoint: CounterfactualBranchpoint
    alternative_action: str
    state_diff: CounterfactualStateDiff
    future_samples: tuple[CounterfactualFutureSample, ...]
    mean_improvement: float
    median_improvement: float
    improvement_variance: float = Field(ge=0.0)
    positive_future_fraction: float = Field(ge=0.0, le=1.0)
    conclusion: str
    model_alternative: bool = True
    historical_fact: bool = False
    external_engine_used: bool = False
    tactical_oracle_used: bool = False
    tactical_observations: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_evidence_truth_boundary(self) -> "CounterfactualResult":
        if not self.model_alternative or self.historical_fact:
            raise ValueError(
                "counterfactual results must remain model alternatives, not historical facts"
            )
        level = self.provenance.get("validation_level", self.branchpoint.validation_level)
        if level != self.branchpoint.validation_level:
            raise ValueError(
                "counterfactual provenance and branchpoint validation levels must match"
            )
        if self.external_engine_used:
            if level != "external_rules_engine":
                raise ValueError(
                    "external_engine_used requires external_rules_engine validation level"
                )
            if not self.provenance.get("external_engine_evidence"):
                raise ValueError(
                    "external engine claims require explicit external_engine_evidence"
                )
        elif level == "external_rules_engine":
            raise ValueError(
                "external_rules_engine validation requires external_engine_used=true"
            )
        if self.tactical_oracle_used != (level == "tactical_oracle"):
            raise ValueError(
                "tactical_oracle_used must match tactical validation level"
            )
        return self


class DecisionRegretRecord(FrozenModel):
    branchpoint_id: str
    chosen_action: str
    best_tested_alternative: str | None = None
    decision_regret: float = Field(ge=0.0)
    evidence_samples: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    contradictory_futures: bool
    recommended_interpretation: str


class CounterfactualComparison(FrozenModel):
    comparison_id: str
    result_ids: tuple[str, ...]
    best_alternative: str | None
    mean_improvements: dict[str, float]
    worst_case_improvements: dict[str, float]
    ranking: tuple[str, ...]
    model_dependent: bool = True
