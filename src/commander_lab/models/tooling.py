from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from .common import FrozenModel, MutableModel
from .pilots import PilotDecisionMode, PilotStrength
from .structural import StructuralCardProfile


class ToolStatus(StrEnum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    REQUIRES_APPROVAL = "requires_approval"


class CostLimits(FrozenModel):
    max_model_calls: int = Field(default=12, ge=1, le=1000)
    max_total_tokens: int = Field(default=120_000, ge=1_000)
    max_output_tokens_per_call: int = Field(default=8_000, ge=128, le=128_000)
    max_estimated_cost_usd: float = Field(default=5.0, gt=0.0, le=100_000.0)
    input_cost_per_million_usd: float = Field(default=0.0, ge=0.0)
    output_cost_per_million_usd: float = Field(default=0.0, ge=0.0)
    max_simulation_seconds: float = Field(default=120.0, gt=0.0, le=86_400.0)
    approval_threshold_iterations: int = Field(default=5_000, ge=1)
    hard_max_iterations: int = Field(default=100_000, ge=1)
    max_variants: int = Field(default=64, ge=1, le=10_000)
    max_swap_matrix_cells: int = Field(default=500, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_iteration_limits(self) -> CostLimits:
        if self.approval_threshold_iterations > self.hard_max_iterations:
            raise ValueError("approval threshold cannot exceed hard maximum")
        return self


class ToolExecutionMetadata(FrozenModel):
    tool_name: str
    invocation_id: str
    created_at: datetime
    git_commit: str | None = None
    engine_version: str
    data_snapshot_hash: str
    data_snapshot_hashes: dict[str, str]
    inventory_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    deck_hashes: dict[str, str] = Field(default_factory=dict)
    opponent_hashes: dict[str, str] = Field(default_factory=dict)
    opponent_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    pilot_hashes: dict[str, str]
    pilot_parameter_hashes: dict[str, str]
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    meta_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_hash: str
    configuration_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_identity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    pilot_version: str | None = None
    seed: int | None = None
    iterations: int | None = None
    estimate_type: Literal[
        "structural_model_estimates",
        "tactical_oracle_results",
        "external_rules_engine_results",
    ] = "structural_model_estimates"
    elapsed_seconds: float = Field(ge=0.0)
    deterministic_game_log_directory: str | None = None
    openai_trace_directory: str | None = None


class ToolResponse(MutableModel):
    status: ToolStatus
    metadata: ToolExecutionMetadata
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DeckRefInput(FrozenModel):
    deck_id: str


class ValidateDeckInput(DeckRefInput):
    include_physical_allocation: bool = True


class InspectDeckInput(DeckRefInput):
    include_cards: bool = False


class SimulationInput(FrozenModel):
    seed: int = Field(default=20260804, ge=0)
    iterations: int = Field(default=100, ge=1)
    workers: int = Field(default=1, ge=1, le=64)
    pilot_strength: PilotStrength = PilotStrength.STRONG
    pilot_mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC
    max_turns: int = Field(default=35, ge=1, le=500)
    approval_token: str | None = None


class GoldfishInput(SimulationInput):
    deck_id: str


class MatchupBatchInput(SimulationInput):
    deck_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_pod(self) -> MatchupBatchInput:
        if not 2 <= len(self.deck_ids) <= 10:
            raise ValueError("matchup requires two to ten decks")
        return self


class CompareDecksInput(SimulationInput):
    deck_ids: tuple[str, str]
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class CandidateProfile(FrozenModel):
    candidate_id: str
    card: StructuralCardProfile
    allowed_deck_ids: tuple[str, ...] = ()
    physical_status: str = "unverified_phase5"
    notes: str | None = None


class VariantSwap(FrozenModel):
    remove: str
    add_candidate_id: str


class PairedVariantInput(SimulationInput):
    deck_id: str
    swaps: tuple[VariantSwap, ...]
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class CardAblationInput(SimulationInput):
    deck_id: str
    card_name: str
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class PackageAblationInput(SimulationInput):
    deck_id: str
    card_names: tuple[str, ...] = ()
    package_id: str | None = None
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )

    @model_validator(mode="after")
    def select_package_or_cards(self) -> PackageAblationInput:
        if bool(self.package_id) == bool(self.card_names):
            raise ValueError("provide exactly one of package_id or card_names")
        return self


class CommanderDenialInput(SimulationInput):
    deck_id: str
    additional_commander_tax: int = Field(default=6, ge=2, le=30)
    suppress_commander_synergy: bool = True
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class SwapMatrixInput(SimulationInput):
    deck_id: str
    remove_cards: tuple[str, ...] = ()
    add_candidate_ids: tuple[str, ...] = ()
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )
    iterations_per_cell: int = Field(default=20, ge=1)
    simulate_valid_cells: bool = True


class SearchVariantsInput(SimulationInput):
    deck_id: str
    candidate_ids: tuple[str, ...] = ()
    max_cuts: int = Field(default=6, ge=1, le=30)
    max_results: int = Field(default=8, ge=1, le=100)
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class HoldoutInput(PairedVariantInput):
    holdout_pods: tuple[tuple[str, ...], ...] = (
        ("synthetic/control", "synthetic/control", "synthetic/engine"),
        ("synthetic/aggro", "synthetic/aggro", "synthetic/control"),
    )


class SensitivityInput(SimulationInput):
    deck_ids: tuple[str, ...]
    seeds: tuple[int, ...] = (20260804, 20260805, 20260806)
    pilot_strengths: tuple[PilotStrength, ...] = (
        PilotStrength.AVERAGE,
        PilotStrength.STRONG,
        PilotStrength.NEAR_OPTIMAL_HEURISTIC,
    )


class RecommendUpgradesInput(FrozenModel):
    deck_id: str
    candidate_ids: tuple[str, ...] = ()
    max_recommendations: int = Field(default=6, ge=1, le=50)


class ValidateUpgradeInput(PairedVariantInput):
    minimum_place_delta: float = Field(default=0.01, ge=-3.0, le=3.0)
    require_holdout: bool = True
    holdout_pods: tuple[tuple[str, ...], ...] = (
        ("synthetic/control", "synthetic/control", "synthetic/engine"),
        ("synthetic/aggro", "synthetic/aggro", "synthetic/control"),
    )
    sensitivity_seeds: tuple[int, ...] = (20260804, 20260805, 20260806)
    sensitivity_strengths: tuple[PilotStrength, ...] = (
        PilotStrength.AVERAGE,
        PilotStrength.STRONG,
        PilotStrength.NEAR_OPTIMAL_HEURISTIC,
    )
    require_sensitivity_nonnegative: bool = True
    require_red_team_pass: bool = True


class BuildOptimizationContextInput(FrozenModel):
    deck_ids: tuple[str, ...] = ("korvold/current", "rogshai/current")
    include_kaervek: bool = False


class GenerateCandidateSwapsInput(FrozenModel):
    deck_id: str
    candidate_ids: tuple[str, ...] = ()
    max_candidates: int = Field(default=12, ge=1, le=50)


class GenerateCandidatePackagesInput(FrozenModel):
    deck_id: str
    include_optional_cards: bool = True


class OptimizeDeckAgainstMetaInput(SimulationInput):
    deck_id: str
    max_candidates: int = Field(default=5, ge=1, le=20)
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class OptimizeMultipleDecksWithAllocationInput(FrozenModel):
    deck_ids: tuple[str, ...] = ("korvold/current", "rogshai/current", "kaervek/current")
    max_candidates_per_deck: int = Field(default=5, ge=1, le=20)


class ValidateSwapInput(ValidateUpgradeInput):
    pass


class ValidatePackageChangeInput(SimulationInput):
    deck_id: str
    package_id: str
    remove_cards: tuple[str, ...] = ()
    add_candidate_ids: tuple[str, ...] = ()
    opponent_deck_ids: tuple[str, ...] = (
        "synthetic/aggro",
        "synthetic/control",
        "synthetic/engine",
    )


class ValidateLandChangeInput(ValidateUpgradeInput):
    pass


class ValidateMulliganPolicyInput(FrozenModel):
    deck_id: str
    baseline_policy: str = "balanced"
    candidate_policy: str = "commander_plan"
    samples: int = Field(default=500, ge=20, le=100000)
    seed: int = Field(default=20260804, ge=0)


class RunMultifidelityComparisonInput(ValidateUpgradeInput):
    include_tactical_oracle: bool = True
    request_external_engine: bool = True


class RunEngineBackedMatchupInput(SimulationInput):
    deck_ids: tuple[str, ...]
    provider: Literal["xmage", "forge"] = "xmage"


class RunRobustnessSuiteInput(ValidateUpgradeInput):
    include_politics: bool = True
    include_pod_sizes: tuple[int, ...] = (3, 4, 5)


class RunRulesCoverageGateInput(FrozenModel):
    deck_id: str
    card_names: tuple[str, ...] = ()
    require_external: bool = False


class RankVariantsInput(FrozenModel):
    variants: tuple[dict[str, Any], ...]
    prefer_worst_case: bool = True


class ExplainRecommendationInput(FrozenModel):
    evidence: dict[str, Any]


class ExportRecommendationEvidenceInput(FrozenModel):
    evidence: dict[str, Any]
    output_name: str = "recommendation-evidence.json"


class CreateDeckImprovementReportInput(FrozenModel):
    deck_id: str
    evidence_items: tuple[dict[str, Any], ...]
    output_name: str = "deck-improvement-report.md"


class CreateReportInput(FrozenModel):
    title: str
    tool_responses: tuple[dict[str, Any], ...]
    output_name: str = "report.md"


class WorkflowRequest(FrozenModel):
    user_goal: str
    session_id: str = "commander-lab-default"
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "high"
    budget: CostLimits = Field(default_factory=CostLimits)


class WorkflowReport(FrozenModel):
    workflow_id: str
    goal: str
    conclusion: str
    evidence: tuple[str, ...]
    caveats: tuple[str, ...]
    tool_invocations: tuple[str, ...]
    model_calls: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    estimate_type: Literal[
        "structural_model_estimates",
        "tactical_oracle_results",
        "external_rules_engine_results",
    ] = "structural_model_estimates"


# Meta Knowledge Base tool inputs (append-only reference/evidence layer)
from .meta import FormatBand, MetaCategory  # noqa: E402


class ImportMetaDeckInput(FrozenModel):
    snapshot_path: str | None = None
    source_id: str
    commander: str
    decklist: tuple[str, ...]
    format_band: FormatBand
    categories: tuple[MetaCategory, ...]
    event_name: str | None = None
    placement: str | None = None
    player_count: int | None = Field(default=None, ge=1)
    pod_size: int | None = Field(default=4, ge=2, le=10)
    budget_band: str = "unknown"


class ImportTournamentResultInput(FrozenModel):
    snapshot_path: str | None = None
    source_id: str
    event_name: str
    format_band: FormatBand
    pod_size: int = Field(default=4, ge=2, le=10)
    placement: str | None = None
    player_count: int | None = Field(default=None, ge=1)


class ImportPrimerReferenceInput(FrozenModel):
    snapshot_path: str | None = None
    source_id: str
    commander: str
    title: str
    key_points: tuple[str, ...]
    categories: tuple[MetaCategory, ...]


class CreateMetaSnapshotInput(FrozenModel):
    snapshot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    seed_file: str = "data/meta/provenance/meta_seed_sources.json"
    allow_overwrite: bool = False


class QueryMetaCardsInput(FrozenModel):
    commander: str | None = None
    format_band: FormatBand | None = None
    min_frequency: float = Field(default=0.0, ge=0.0, le=1.0)


class QueryMetaPackagesInput(FrozenModel):
    commander: str | None = None
    category: MetaCategory | None = None


class CompareDeckToMetaInput(FrozenModel):
    deck_id: str
    commander: str
    format_band: FormatBand | None = None


class CompareMetaPeriodsInput(FrozenModel):
    older_snapshot_id: str
    newer_snapshot_id: str
    commander: str | None = None


class GenerateMetaReportInput(FrozenModel):
    output_name: str = "meta_report.md"
    commander: str | None = None


# Primer-to-Pilot Compiler inputs. All source content is parsed as data; never executed.
from .primer import PrimerFormat  # noqa: E402


class ImportPrimerInput(FrozenModel):
    source_path: str
    primer_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    source_id: str
    title: str
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand
    primer_format: PrimerFormat | None = None
    license_notes: str = "structured extraction only unless the source is user-provided"


class ExtractPrimerRulesInput(FrozenModel):
    primer_id: str
    output_name: str | None = None


class ValidatePilotRulesInput(FrozenModel):
    rules_path: str
    commander: str | None = None
    deck_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand | None = None


class CompilePilotPolicyInput(FrozenModel):
    rule_paths: tuple[str, ...]
    policy_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    format_band: FormatBand
    base_pilot_name: str
    conflict_strategy: Literal["reject", "prefer_priority", "prefer_confidence"] = "reject"
    output_name: str | None = None


class ComparePolicyVersionsInput(FrozenModel):
    older_policy_path: str
    newer_policy_path: str


class RunPolicyEvalInput(FrozenModel):
    policy_path: str
    scenario_path: str
    deck_id: str
    strategy: str
    seed: int = Field(default=20260806, ge=0)
    output_name: str = "latest_policy_eval.json"


class GeneratePrimerConflictReportInput(FrozenModel):
    rule_paths: tuple[str, ...]
    output_name: str = "primer_conflict_report.json"


class ListPilotProfilesInput(FrozenModel):
    commander_family: Literal["korvold", "rogshai", "generic"] | None = None
    include_baselines: bool = True


class InspectPilotInput(FrozenModel):
    pilot_name: str


class RunPilotBenchmarkInput(FrozenModel):
    deck_id: str
    pilot_names: tuple[str, ...] = ()
    opponent_deck_ids: tuple[str, ...] = (
        "opponent/morcant-elves",
        "opponent/blight-curse-precon",
        "opponent/doom-prevails-precon",
    )
    iterations: int = Field(default=8, ge=1, le=500)
    seed: int = Field(default=20260806, ge=0)
    max_turns: int = Field(default=24, ge=5, le=100)
    output_name: str = "latest_pilot_benchmark"


class ComparePilotsInput(RunPilotBenchmarkInput):
    pilot_names: tuple[str, ...] = Field(min_length=2)


class PilotWeightInput(FrozenModel):
    pilot_name: str
    weight: float = Field(gt=0.0, le=1.0)


class RunPilotEnsembleInput(FrozenModel):
    deck_id: str
    ensemble_id: str | None = None
    custom_weights: tuple[PilotWeightInput, ...] = ()
    opponent_deck_ids: tuple[str, ...] = (
        "opponent/morcant-elves",
        "opponent/blight-curse-precon",
        "opponent/doom-prevails-precon",
    )
    iterations: int = Field(default=8, ge=1, le=500)
    seed: int = Field(default=20260806, ge=0)
    max_turns: int = Field(default=24, ge=5, le=100)
    output_name: str = "latest_pilot_ensemble"

    @model_validator(mode="after")
    def require_one_weight_source(self) -> RunPilotEnsembleInput:
        if bool(self.ensemble_id) == bool(self.custom_weights):
            raise ValueError("provide exactly one of ensemble_id or custom_weights")
        if (
            self.custom_weights
            and abs(sum(item.weight for item in self.custom_weights) - 1.0) > 1e-9
        ):
            raise ValueError("custom pilot weights must sum to 1.0")
        return self


class TestVariantAcrossPilotsInput(FrozenModel):
    __test__: ClassVar[bool] = False
    baseline_deck_id: str
    variant_deck_id: str
    pilot_names: tuple[str, ...]
    opponent_deck_ids: tuple[str, ...] = (
        "opponent/morcant-elves",
        "opponent/blight-curse-precon",
        "opponent/doom-prevails-precon",
    )
    iterations: int = Field(default=8, ge=1, le=500)
    seed: int = Field(default=20260806, ge=0)
    max_turns: int = Field(default=24, ge=5, le=100)
    output_name: str = "latest_variant_across_pilots"


class GeneratePilotRobustnessReportInput(FrozenModel):
    result_path: str
    output_name: str = "pilot_robustness_report.md"


class ExtractArchetypesInput(FrozenModel):
    deck_id: str


class ExtractPackagesInput(FrozenModel):
    deck_id: str
    include_machine_candidates: bool = True


class InspectPackageInput(FrozenModel):
    package_id: str
    version: str | None = None
    deck_id: str | None = None


class ComparePackageVersionsInput(FrozenModel):
    package_id: str
    older_version: str
    newer_version: str


class EvaluatePackageDensityInput(FrozenModel):
    deck_id: str
    package_id: str
    version: str | None = None


class DetectOrphanedCardsInput(FrozenModel):
    deck_id: str


class GeneratePackageReportInput(FrozenModel):
    deck_id: str
    output_name: str = "package_report.md"


# Full provenance tool inputs
class TraceArtifactProvenanceInput(FrozenModel):
    artifact_id: str


class TraceRecommendationSourcesInput(FrozenModel):
    recommendation_id: str


class ListSupersededSourcesInput(FrozenModel):
    include_historical: bool = True


class VerifySourceHashInput(FrozenModel):
    source_id: str
    candidate_path: str | None = None


class GenerateProvenanceReportInput(FrozenModel):
    output_name: str = "provenance_report.md"


class AuditUnreferencedClaimsInput(FrozenModel):
    fail_on_unreferenced: bool = False


# Local meta learning tool inputs


class CreateOpponentEnsembleInput(FrozenModel):
    source_path: str


class AddOpponentVariantInput(FrozenModel):
    ensemble_id: str
    variant_path: str
    new_ensemble_id: str


class ValidateEnsembleInput(FrozenModel):
    ensemble_id: str


class RunEnsembleMatchupsInput(FrozenModel):
    deck_id: str
    ensemble_id: str
    seed: int = Field(default=20260806, ge=0)


class CompareVariantSensitivityInput(FrozenModel):
    deck_id: str
    ensemble_id: str
    seed: int = Field(default=20260806, ge=0)


class EvaluateRobustUpgradeInput(FrozenModel):
    baseline_deck_id: str
    candidate_deck_id: str
    ensemble_id: str
    seed: int = Field(default=20260806, ge=0)


class GenerateEnsembleReportInput(FrozenModel):
    ensemble_id: str
    output_name: str = "opponent_ensemble_report.md"


class SampleOpeningHandsInput(FrozenModel):
    deck_id: str
    samples: int = Field(default=1000, ge=1, le=5_000_000)
    seed: int = Field(default=20260806, ge=0)
    max_mulligans: int = Field(default=6, ge=0, le=7)


class EvaluateOpeningHandInput(FrozenModel):
    deck_id: str
    card_names: tuple[str, ...]
    policy: str = "current_pilot"
    opponent_ensemble_id: str | None = None
    seat_position: int = Field(default=1, ge=1, le=10)
    starting_player: bool = False
    pod_size: int = Field(default=4, ge=2, le=10)
    pilot_profile_id: str = "baseline"
    pilot_version: str = "unspecified"
    game_plan: str = "balanced"
    seed: int = Field(default=20260806, ge=0)

    @model_validator(mode="after")
    def validate_hand_size(self) -> EvaluateOpeningHandInput:
        if not 1 <= len(self.card_names) <= 7:
            raise ValueError("opening hand must contain one to seven cards")
        return self


class CompareMulliganPoliciesInput(FrozenModel):
    deck_id: str
    policies: tuple[str, ...] = (
        "conservative",
        "curve_oriented",
        "commander_oriented",
        "interaction_oriented",
        "matchup_oriented",
        "primer_policy",
        "current_pilot",
        "learned_policy",
    )
    samples: int = Field(default=5000, ge=1, le=5_000_000)
    followup_samples: int = Field(default=250, ge=0, le=100_000)
    opponent_ensemble_id: str | None = None
    seat_position: int = Field(default=1, ge=1, le=10)
    starting_player: bool = False
    pod_size: int = Field(default=4, ge=2, le=10)
    pilot_profile_id: str = "baseline"
    pilot_version: str = "unspecified"
    game_plan: str = "balanced"
    seed: int = Field(default=20260806, ge=0)
    approval_token: str | None = None


class RunMulliganLabInput(CompareMulliganPoliciesInput):
    output_name: str = "mulligan_lab_result.json"


class GenerateKeepRulesInput(FrozenModel):
    result_path: str
    output_name: str = "generated_keep_rules.json"


class TestKeepRuleInput(FrozenModel):
    __test__: ClassVar[bool] = False
    rule_path: str
    deck_id: str
    card_names: tuple[str, ...]


class CreateMulliganReportInput(FrozenModel):
    result_path: str
    output_name: str = "MULLIGAN_LAB_REPORT.md"


# Counterfactual replay tool inputs
class FindCounterfactualBranchpointsInput(FrozenModel):
    source_path: str
    actor_id: str | None = None
    phase: str | None = None


class ListAlternativeActionsInput(FrozenModel):
    source_path: str
    event_offset: int = Field(ge=0)
    expected_state_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RunCounterfactualInput(FrozenModel):
    source_path: str
    event_offset: int = Field(ge=0)
    alternative_action: str
    expected_state_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    engine_mode: str = "structural"
    seed_policy: str = "same_seed"
    hidden_information_policy: str = "public_information_only"
    seed: int = Field(default=20260806, ge=0)
    future_samples: int = Field(default=1, ge=1, le=10_000)
    workers: int = Field(default=1, ge=1, le=64)
    output_name: str = "counterfactual_result.json"


class CompareCounterfactualsInput(FrozenModel):
    result_paths: tuple[str, ...] = Field(min_length=1)
    output_name: str = "counterfactual_comparison.json"


class GenerateDecisionRegretReportInput(FrozenModel):
    result_path: str
    output_name: str = "DECISION_REGRET_REPORT.md"


class ExportMinimalCounterfactualFixtureInput(FrozenModel):
    source_path: str
    event_offset: int = Field(ge=0)
    expected_state_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_name: str = "counterfactual_golden_fixture.json"


# Deck / pilot / model diagnostic tool inputs
class DiagnoseCardPerformanceInput(FrozenModel):
    dataset_path: str
    card_name: str
    output_name: str = "card_diagnosis.json"


class DiagnosePilotBehaviorInput(FrozenModel):
    dataset_path: str
    pilot_name: str
    output_name: str = "pilot_diagnosis.json"


class CompareDeckAndPilotEffectsInput(FrozenModel):
    dataset_path: str


class ClassifyFailureCauseInput(FrozenModel):
    dataset_path: str
    subject: str
    output_name: str = "failure_cause_diagnosis.json"


class RecommendNextExperimentInput(FrozenModel):
    diagnosis_path: str


class GenerateDiagnosticReportInput(FrozenModel):
    diagnosis_paths: tuple[str, ...] = Field(min_length=1)
    output_name: str = "DECISION_DIAGNOSTIC_REPORT.md"
