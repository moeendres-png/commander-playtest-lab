from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import FrozenModel

DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"


class FailureCause(StrEnum):
    CARD_IS_WEAK = "card_is_weak"
    CARD_IS_MISPLAYED = "card_is_misplayed"
    PACKAGE_IS_INCOMPLETE = "package_is_incomplete"
    PILOT_DOES_NOT_RECOGNIZE_LINE = "pilot_does_not_recognize_line"
    PILOT_STYLE_MISMATCH = "pilot_style_mismatch"
    OPPONENT_MODEL_IS_WRONG = "opponent_model_is_wrong"
    SIMULATION_ABSTRACTION_IS_WRONG = "simulation_abstraction_is_wrong"
    RANDOM_VARIANCE = "random_variance"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    GENUINE_DECK_CONSTRUCTION_ISSUE = "genuine_deck_construction_issue"


class CardPerformanceInstrumentation(FrozenModel):
    card_name: str
    sample_size: int = Field(ge=0)
    drawn: int = Field(default=0, ge=0)
    opening_hand: int = Field(default=0, ge=0)
    mulliganed: int = Field(default=0, ge=0)
    kept: int = Field(default=0, ge=0)
    played: int = Field(default=0, ge=0)
    unplayable: int = Field(default=0, ge=0)
    discarded: int = Field(default=0, ge=0)
    removed: int = Field(default=0, ge=0)
    successful: int = Field(default=0, ge=0)
    without_value: int = Field(default=0, ge=0)
    dead_in_hand: int = Field(default=0, ge=0)
    average_turn_played: float | None = Field(default=None, ge=0.0)
    mana_efficiency: float | None = None
    synergy_partner_present: int = Field(default=0, ge=0)
    pilot_decisions: tuple[str, ...] = ()
    alternative_lines: tuple[str, ...] = ()
    counterfactual_outcome_delta: float | None = None

    @model_validator(mode="after")
    def counts_do_not_exceed_samples(self) -> "CardPerformanceInstrumentation":
        for field in (
            "drawn", "opening_hand", "mulliganed", "kept", "played", "unplayable",
            "discarded", "removed", "successful", "without_value", "dead_in_hand",
            "synergy_partner_present",
        ):
            if getattr(self, field) > self.sample_size:
                raise ValueError(f"{field} cannot exceed sample_size")
        return self


class PilotDiagnosticEvidence(FrozenModel):
    pilot_name: str
    sample_size: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    dead_card_rate: float = Field(ge=0.0, le=1.0)
    unplayable_rate: float = Field(ge=0.0, le=1.0)
    decision_regret: float = Field(ge=0.0)
    missed_line_count: int = Field(ge=0)
    primer_rule_miss_count: int = Field(default=0, ge=0)
    average_placement: float | None = Field(default=None, ge=1.0)


class DiagnosticDataset(FrozenModel):
    schema_version: str = DIAGNOSTIC_SCHEMA_VERSION
    dataset_id: str
    deck_id: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    card_metrics: tuple[CardPerformanceInstrumentation, ...] = ()
    pilot_metrics: tuple[PilotDiagnosticEvidence, ...] = ()
    package_checked: bool = False
    package_id: str | None = None
    package_completeness: float | None = Field(default=None, ge=0.0, le=1.0)
    package_minimum_met: bool | None = None
    opponent_ensemble_count: int = Field(default=0, ge=0)
    opponent_sensitivity: float = Field(default=0.0, ge=0.0, le=1.0)
    opponent_observation_conflict: bool = False
    seed_sensitivity: float = Field(default=0.0, ge=0.0, le=1.0)
    pilot_disagreement: float = Field(default=0.0, ge=0.0, le=1.0)
    counterfactual_improvement: float | None = None
    counterfactual_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    deck_variant_effect: float | None = None
    holdout_confirms_problem: bool = False
    tactical_structural_disagreement: float = Field(default=0.0, ge=0.0, le=1.0)
    external_rules_structural_disagreement: float = Field(default=0.0, ge=0.0, le=1.0)
    multiple_pods_confirm: bool = False
    source_ids: tuple[str, ...] = ()
    validation_levels: tuple[str, ...] = ("structural_model_estimates",)
    notes: tuple[str, ...] = ()


class DiagnosticMetrics(FrozenModel):
    dead_card_rate: float = Field(ge=0.0, le=1.0)
    unplayable_rate: float = Field(ge=0.0, le=1.0)
    package_failure_rate: float = Field(ge=0.0, le=1.0)
    pilot_disagreement: float = Field(ge=0.0, le=1.0)
    decision_regret: float = Field(ge=0.0)
    missed_line_count: int = Field(ge=0)
    counterfactual_improvement: float
    evidence_strength: float = Field(ge=0.0, le=1.0)


class DiagnosisRecord(FrozenModel):
    schema_version: str = DIAGNOSTIC_SCHEMA_VERSION
    diagnosis_id: str
    subject: str
    hypothesis: FailureCause
    evidence: tuple[str, ...]
    counterevidence: tuple[str, ...]
    pilot_sensitivity: float = Field(ge=0.0, le=1.0)
    opponent_sensitivity: float = Field(ge=0.0, le=1.0)
    seed_sensitivity: float = Field(ge=0.0, le=1.0)
    package_dependency: dict[str, Any]
    counterfactual_result: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_next_test: str
    metrics: DiagnosticMetrics
    cut_release_gate: str
    model_dependent: bool = True
    empirically_proven: bool = False
    automatic_deck_change: bool = False
    source_ids: tuple[str, ...] = ()
    validation_levels: tuple[str, ...] = ()


class FactorEffectComparison(FrozenModel):
    deck_effect: float
    pilot_effect: float
    opponent_effect: float
    action_effect: float
    seed_effect: float
    dominant_factor: str
    interpretation: str


class IntegratedSmokeStep(FrozenModel):
    step: int = Field(ge=1, le=10)
    name: str
    status: str
    source_paths: tuple[str, ...]
    source_hashes: tuple[str, ...]
    validation_level: str
    result_summary: str


class IntegratedExtensionSmokeReport(FrozenModel):
    schema_version: str = DIAGNOSTIC_SCHEMA_VERSION
    report_id: str
    steps: tuple[IntegratedSmokeStep, ...]
    passed_steps: int = Field(ge=0, le=10)
    status: str
    external_engine_used: bool = False
    canonical_deck_changes: bool = False
    inventory_changes: bool = False
    allocation_changes: bool = False
