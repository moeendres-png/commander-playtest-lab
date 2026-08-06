from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import FrozenModel


MULLIGAN_LAB_SCHEMA_VERSION = "1.0.0"


class MulliganPolicyName(StrEnum):
    CONSERVATIVE = "conservative"
    CURVE_ORIENTED = "curve_oriented"
    COMMANDER_ORIENTED = "commander_oriented"
    INTERACTION_ORIENTED = "interaction_oriented"
    MATCHUP_ORIENTED = "matchup_oriented"
    PRIMER_POLICY = "primer_policy"
    CURRENT_PILOT = "current_pilot"
    LEARNED_POLICY = "learned_policy"


class MulliganGamePlan(StrEnum):
    BALANCED = "balanced"
    COMMANDER_VALUE = "commander_value"
    PROTECTED_COMMANDER = "protected_commander"
    INDEPENDENT_ENGINE = "independent_engine"
    CONTROL = "control"
    FAST_PRESSURE = "fast_pressure"
    REBUILD = "rebuild"


class MulliganEstimateLevel(StrEnum):
    EXACT_HYPERGEOMETRIC = "exact_hypergeometric"
    MONTE_CARLO_HAND_QUALITY = "monte_carlo_hand_quality"
    STRUCTURAL_FOLLOWUP = "structural_followup"


class MulliganContext(FrozenModel):
    deck_id: str
    deck_hash: str
    opponent_ensemble_id: str | None = None
    opponent_ensemble_hash: str | None = None
    seat_position: int = Field(default=1, ge=1, le=10)
    starting_player: bool = False
    pod_size: int = Field(default=4, ge=2, le=10)
    pilot_profile_id: str = "baseline"
    pilot_version: str = "unspecified"
    game_plan: MulliganGamePlan = MulliganGamePlan.BALANCED
    seed: int = Field(default=20260806, ge=0)


class OpeningHandFeatures(FrozenModel):
    hand_size: int = Field(ge=0, le=7)
    land_count: int = Field(ge=0, le=7)
    colored_sources: dict[str, int] = Field(default_factory=dict)
    tapped_source_count: int = Field(default=0, ge=0, le=7)
    ramp_count: int = Field(default=0, ge=0, le=7)
    draw_count: int = Field(default=0, ge=0, le=7)
    selection_count: int = Field(default=0, ge=0, le=7)
    interaction_count: int = Field(default=0, ge=0, le=7)
    protection_count: int = Field(default=0, ge=0, le=7)
    commander_synergy_count: int = Field(default=0, ge=0, le=7)
    independent_engine_count: int = Field(default=0, ge=0, le=7)
    dead_high_cost_count: int = Field(default=0, ge=0, le=7)
    graveyard_hate_count: int = Field(default=0, ge=0, le=7)
    boardwipe_count: int = Field(default=0, ge=0, le=7)
    wincondition_without_setup_count: int = Field(default=0, ge=0, le=7)
    sacrifice_resource_count: int = Field(default=0, ge=0, le=7)
    commander_immediate_value: bool = False
    early_blue_source_count: int = Field(default=0, ge=0, le=7)
    cheap_noncreature_count: int = Field(default=0, ge=0, le=7)
    combat_draw_count: int = Field(default=0, ge=0, le=7)
    offensive_payoff_without_window_count: int = Field(default=0, ge=0, le=7)
    color_stability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    only_graveyard_plan_without_setup: bool = False


class OpeningHandEvaluation(FrozenModel):
    cards: tuple[str, ...]
    features: OpeningHandFeatures
    policy: MulliganPolicyName
    keep: bool
    score: float
    threshold: float
    reasons: tuple[str, ...] = ()
    model_based: bool = True
    estimate_level: MulliganEstimateLevel = MulliganEstimateLevel.MONTE_CARLO_HAND_QUALITY


class LondonMulliganResult(FrozenModel):
    initial_draws: tuple[tuple[str, ...], ...]
    kept_cards: tuple[str, ...]
    bottomed_cards: tuple[str, ...]
    mulligans_taken: int = Field(ge=0, le=7)
    effective_bottom_count: int = Field(ge=0, le=7)
    free_multiplayer_mulligan_used: bool
    evaluation: OpeningHandEvaluation
    commander_names: tuple[str, ...]


class HypergeometricBaseline(FrozenModel):
    population_size: int
    category_size: int
    draws: int
    probability_at_least: dict[int, float]
    category: str


class MulliganPolicySummary(FrozenModel):
    policy: MulliganPolicyName
    samples: int = Field(ge=1)
    keep_rate_first_seven: float = Field(ge=0.0, le=1.0)
    final_keep_rate: float = Field(ge=0.0, le=1.0)
    mulligan_rate: float = Field(ge=0.0, le=1.0)
    average_mulligans: float = Field(ge=0.0)
    color_problem_rate: float = Field(ge=0.0, le=1.0)
    average_dead_cards: float = Field(ge=0.0)
    median_hand_score: float
    first_ramp_turn_mean: float | None = None
    commander_cast_turn_mean: float | None = None
    first_draw_engine_turn_mean: float | None = None
    structural_placement_mean: float | None = None
    uncertainty_half_width_95: float = Field(ge=0.0)
    estimate_level: MulliganEstimateLevel = MulliganEstimateLevel.MONTE_CARLO_HAND_QUALITY


class KeepRuleClause(FrozenModel):
    feature: str
    operator: Literal["ge", "le", "eq", "between", "true", "false"]
    value: float | tuple[float, float] | bool
    rationale: str


class GeneratedKeepRule(FrozenModel):
    rule_id: str
    deck_id: str
    deck_hash: str
    policy: MulliganPolicyName
    clauses: tuple[KeepRuleClause, ...]
    exceptions: tuple[str, ...] = ()
    source_run_hash: str
    validation_contexts: tuple[str, ...] = ()
    validation_status: Literal["candidate", "holdout_checked", "rejected"] = "candidate"
    model_based: bool = True
    absolute_rule: bool = False

    @model_validator(mode="after")
    def forbid_absolute_model_claim(self) -> "GeneratedKeepRule":
        if self.model_based and self.absolute_rule:
            raise ValueError("model-based keep rules cannot be marked absolute")
        return self


class MulliganLabResult(FrozenModel):
    schema_version: str = MULLIGAN_LAB_SCHEMA_VERSION
    context: MulliganContext
    sample_count: int
    policies: tuple[MulliganPolicySummary, ...]
    hypergeometric_baselines: tuple[HypergeometricBaseline, ...]
    common_random_numbers: bool = True
    full_matchup_performance_separate: bool = True
    generated_rules: tuple[GeneratedKeepRule, ...] = ()
    warnings: tuple[str, ...] = ()
    estimate_type: str = "structural_model_estimates"
