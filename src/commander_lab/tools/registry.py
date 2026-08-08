from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from commander_lab.models import (
    AddOpponentVariantInput,
    AuditUnreferencedClaimsInput,
    BeamSearchInput,
    BuildOptimizationContextInput,
    CardAblationInput,
    ClassifyFailureCauseInput,
    CommanderDenialInput,
    CompareCounterfactualsInput,
    CompareDeckAndPilotEffectsInput,
    CompareDecksInput,
    CompareDeckToMetaInput,
    CompareMetaPeriodsInput,
    CompareMulliganPoliciesInput,
    ComparePackageVersionsInput,
    ComparePilotsInput,
    ComparePolicyVersionsInput,
    CompareVariantSensitivityInput,
    CompilePilotPolicyInput,
    CreateDeckImprovementReportInput,
    CreateMetaSnapshotInput,
    CreateMulliganReportInput,
    CreateOpponentEnsembleInput,
    CreateReportInput,
    DetectOrphanedCardsInput,
    DiagnoseCardPerformanceInput,
    DiagnosePilotBehaviorInput,
    EvaluateOpeningHandInput,
    EvaluatePackageDensityInput,
    EvaluateRobustUpgradeInput,
    ExplainRecommendationInput,
    ExportMinimalCounterfactualFixtureInput,
    ExportRecommendationEvidenceInput,
    ExtractArchetypesInput,
    ExtractPackagesInput,
    ExtractPrimerRulesInput,
    FindCounterfactualBranchpointsInput,
    GenerateCandidatePackagesInput,
    GenerateCandidateSwapsInput,
    GenerateDecisionRegretReportInput,
    GenerateDiagnosticReportInput,
    GenerateEnsembleReportInput,
    GenerateKeepRulesInput,
    GenerateMetaReportInput,
    GeneratePackageReportInput,
    GeneratePilotRobustnessReportInput,
    GeneratePrimerConflictReportInput,
    GenerateProvenanceReportInput,
    GoldfishInput,
    HoldoutInput,
    ImportMetaDeckInput,
    ImportPrimerInput,
    ImportPrimerReferenceInput,
    ImportTournamentResultInput,
    InspectDeckInput,
    InspectPackageInput,
    InspectPilotInput,
    ListAlternativeActionsInput,
    ListPilotProfilesInput,
    ListSupersededSourcesInput,
    LocalSearchInput,
    MatchupBatchInput,
    OptimizeDeckAgainstMetaInput,
    OptimizeMultipleDecksWithAllocationInput,
    PackageAblationInput,
    PackageSearchInput,
    PairedVariantInput,
    ParetoFrontInput,
    QueryMetaCardsInput,
    QueryMetaPackagesInput,
    RankVariantsInput,
    RecommendNextExperimentInput,
    RecommendUpgradesInput,
    RunCounterfactualInput,
    RunEngineBackedMatchupInput,
    RunEnsembleMatchupsInput,
    RunMulliganLabInput,
    RunMultifidelityComparisonInput,
    RunPilotBenchmarkInput,
    RunPilotEnsembleInput,
    RunPolicyEvalInput,
    RunRobustnessSuiteInput,
    RunRulesCoverageGateInput,
    SampleOpeningHandsInput,
    SearchVariantsInput,
    SensitivityInput,
    ShapleyInput,
    SwapMatrixInput,
    TestKeepRuleInput,
    TestVariantAcrossPilotsInput,
    ToolResponse,
    TraceArtifactProvenanceInput,
    TraceRecommendationSourcesInput,
    ValidateDeckInput,
    ValidateEnsembleInput,
    ValidateLandChangeInput,
    ValidateMulliganPolicyInput,
    ValidatePackageChangeInput,
    ValidatePilotRulesInput,
    ValidateSwapInput,
    ValidateUpgradeInput,
    VerifySourceHashInput,
)

from .service import CommanderToolService


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler_name: str

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "parameters": self.input_model.model_json_schema(),
        }


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "validate_deck",
        "Validate Commander legality, size, singleton, color identity and local allocation.",
        ValidateDeckInput,
        "validate_deck",
    ),
    ToolDefinition(
        "inspect_deck",
        "Inspect role counts, structural weaknesses and optional card profiles.",
        InspectDeckInput,
        "inspect_deck",
    ),
    ToolDefinition(
        "run_goldfish",
        "Run a deterministic structural goldfish batch.",
        GoldfishInput,
        "run_goldfish",
    ),
    ToolDefinition(
        "run_matchup_batch",
        "Run a structural multiplayer matchup batch.",
        MatchupBatchInput,
        "run_matchup_batch",
    ),
    ToolDefinition(
        "compare_decks",
        "Compare two complete decks under paired random conditions.",
        CompareDecksInput,
        "compare_decks",
    ),
    ToolDefinition(
        "compare_variants_paired",
        "Compare a baseline and card-swap variant using identical seeds.",
        PairedVariantInput,
        "compare_variants_paired",
    ),
    ToolDefinition(
        "run_card_ablation",
        "Estimate a card contribution with role-neutral paired ablation.",
        CardAblationInput,
        "run_card_ablation",
    ),
    ToolDefinition(
        "run_package_ablation",
        "Estimate a package contribution with paired ablation.",
        PackageAblationInput,
        "run_package_ablation",
    ),
    ToolDefinition(
        "run_commander_denial",
        "Stress-test a deck with added commander tax and optional synergy suppression.",
        CommanderDenialInput,
        "run_commander_denial",
    ),
    ToolDefinition(
        "generate_swap_matrix",
        "Evaluate a matrix of cuts and candidate additions.",
        SwapMatrixInput,
        "generate_swap_matrix",
    ),
    ToolDefinition(
        "search_variants",
        "Search bounded one-card structural variants.",
        SearchVariantsInput,
        "search_variants",
    ),
    ToolDefinition(
        "run_local_search",
        "Run constrained iterative local search without applying changes.",
        LocalSearchInput,
        "run_local_search",
    ),
    ToolDefinition(
        "run_beam_search",
        "Run constrained multi-step beam search over deck variants.",
        BeamSearchInput,
        "run_beam_search",
    ),
    ToolDefinition(
        "run_package_search",
        "Search and evaluate multi-card packages under hard constraints.",
        PackageSearchInput,
        "run_package_search",
    ),
    ToolDefinition(
        "evaluate_pareto_front",
        "Evaluate variants on multiple objectives and return the non-dominated front.",
        ParetoFrontInput,
        "evaluate_pareto_front",
    ),
    ToolDefinition(
        "estimate_shapley",
        "Estimate card contributions using permutation Shapley approximation and paired ablation.",
        ShapleyInput,
        "estimate_shapley",
    ),
    ToolDefinition(
        "run_holdout",
        "Evaluate a proposed variant on unused holdout pods.",
        HoldoutInput,
        "run_holdout",
    ),
    ToolDefinition(
        "run_sensitivity",
        "Repeat scenarios across seeds and pilot strengths.",
        SensitivityInput,
        "run_sensitivity",
    ),
    ToolDefinition(
        "recommend_upgrades",
        "Screen role-profile upgrade candidates without claiming confirmation.",
        RecommendUpgradesInput,
        "recommend_upgrades",
    ),
    ToolDefinition(
        "validate_upgrade",
        "Confirm or reject a proposed upgrade using paired and holdout criteria.",
        ValidateUpgradeInput,
        "validate_upgrade",
    ),
    ToolDefinition(
        "build_optimization_context",
        "Load the current read-only deck, inventory, allocation, "
        "opponent, pilot, politics, coverage and engine context.",
        BuildOptimizationContextInput,
        "build_optimization_context",
    ),
    ToolDefinition(
        "generate_candidate_swaps",
        "Generate whole-deck candidate swaps without applying changes.",
        GenerateCandidateSwapsInput,
        "generate_candidate_swaps",
    ),
    ToolDefinition(
        "generate_candidate_packages",
        "Generate and diagnose candidate package changes without applying them.",
        GenerateCandidatePackagesInput,
        "generate_candidate_packages",
    ),
    ToolDefinition(
        "optimize_deck_against_meta",
        "Screen and structurally validate deck candidates against the configured opponent meta.",
        OptimizeDeckAgainstMetaInput,
        "optimize_deck_against_meta",
    ),
    ToolDefinition(
        "optimize_multiple_decks_with_allocation",
        "Optimize multiple decks while resolving singleton allocation conflicts by user priority.",
        OptimizeMultipleDecksWithAllocationInput,
        "optimize_multiple_decks_with_allocation",
    ),
    ToolDefinition(
        "validate_swap",
        "Validate one or more swaps through formal, paired "
        "structural, holdout, sensitivity and red-team gates.",
        ValidateSwapInput,
        "validate_swap",
    ),
    ToolDefinition(
        "validate_package_change",
        "Validate a package change and its density, failure modes and structural swap evidence.",
        ValidatePackageChangeInput,
        "validate_package_change",
    ),
    ToolDefinition(
        "validate_land_change",
        "Validate a land change with land-specific and structural gates.",
        ValidateLandChangeInput,
        "validate_land_change",
    ),
    ToolDefinition(
        "validate_mulligan_policy",
        "Compare two mulligan policies with common random numbers and model labels.",
        ValidateMulliganPolicyInput,
        "validate_mulligan_policy",
    ),
    ToolDefinition(
        "run_multifidelity_comparison",
        "Run the available formal, structural, Tactical Oracle "
        "coverage and external-engine gates without overstating "
        "evidence.",
        RunMultifidelityComparisonInput,
        "run_multifidelity_comparison",
    ),
    ToolDefinition(
        "run_engine_backed_matchup",
        "Run a real XMage or Forge matchup only when a provider "
        "process is available; otherwise return blocked evidence.",
        RunEngineBackedMatchupInput,
        "run_engine_backed_matchup",
    ),
    ToolDefinition(
        "run_robustness_suite",
        "Run structural holdout, pilot, politics and pod-size robustness diagnostics.",
        RunRobustnessSuiteInput,
        "run_robustness_suite",
    ),
    ToolDefinition(
        "run_rules_coverage_gate",
        "Check card and interaction coverage and the highest actually executed validation level.",
        RunRulesCoverageGateInput,
        "run_rules_coverage_gate",
    ),
    ToolDefinition(
        "rank_variants",
        "Rank variants by worst-case, paired effect and executed rules coverage.",
        RankVariantsInput,
        "rank_variants",
    ),
    ToolDefinition(
        "explain_recommendation",
        "Explain a recommendation, tradeoffs, truth boundary and remaining uncertainty.",
        ExplainRecommendationInput,
        "explain_recommendation",
    ),
    ToolDefinition(
        "export_recommendation_evidence",
        "Export recommendation evidence without modifying canonical data.",
        ExportRecommendationEvidenceInput,
        "export_recommendation_evidence",
    ),
    ToolDefinition(
        "create_deck_improvement_report",
        "Create a complete model-labeled deck-improvement report without applying changes.",
        CreateDeckImprovementReportInput,
        "create_deck_improvement_report",
    ),
    ToolDefinition(
        "create_report",
        "Create a local structured Markdown evidence report.",
        CreateReportInput,
        "create_report",
    ),
    ToolDefinition(
        "import_meta_deck",
        "Import a meta deck into the append-only Meta Knowledge "
        "Base staging layer without changing local decks.",
        ImportMetaDeckInput,
        "import_meta_deck",
    ),
    ToolDefinition(
        "import_tournament_result",
        "Import tournament metadata into the append-only Meta Knowledge Base staging layer.",
        ImportTournamentResultInput,
        "import_tournament_result",
    ),
    ToolDefinition(
        "import_primer_reference",
        "Import primer notes into the append-only Meta Knowledge Base staging layer.",
        ImportPrimerReferenceInput,
        "import_primer_reference",
    ),
    ToolDefinition(
        "create_meta_snapshot",
        "Create an immutable versioned Meta Knowledge Base snapshot from structured seed sources.",
        CreateMetaSnapshotInput,
        "create_meta_snapshot",
    ),
    ToolDefinition(
        "query_meta_cards",
        "Query card frequencies from the latest Meta Knowledge Base snapshot.",
        QueryMetaCardsInput,
        "query_meta_cards",
    ),
    ToolDefinition(
        "query_meta_packages",
        "Query package usage from the latest Meta Knowledge Base snapshot.",
        QueryMetaPackagesInput,
        "query_meta_packages",
    ),
    ToolDefinition(
        "compare_deck_to_meta",
        "Compare a local deck to external meta references without applying changes.",
        CompareDeckToMetaInput,
        "compare_deck_to_meta",
    ),
    ToolDefinition(
        "compare_meta_periods",
        "Compare two immutable meta snapshots to detect meta drift.",
        CompareMetaPeriodsInput,
        "compare_meta_periods",
    ),
    ToolDefinition(
        "generate_meta_report",
        "Generate a Markdown report summarizing the latest Meta Knowledge Base snapshot.",
        GenerateMetaReportInput,
        "generate_meta_report",
    ),
    ToolDefinition(
        "import_primer",
        "Import primer metadata and content hash without executing source text.",
        ImportPrimerInput,
        "import_primer",
    ),
    ToolDefinition(
        "extract_primer_rules",
        "Conservatively extract disabled rule candidates from a registered primer.",
        ExtractPrimerRulesInput,
        "extract_primer_rules",
    ),
    ToolDefinition(
        "validate_pilot_rules",
        "Validate pilot rules against the fixed safe DSL and optional deck scope.",
        ValidatePilotRulesInput,
        "validate_pilot_rules",
    ),
    ToolDefinition(
        "compile_pilot_policy",
        "Compile manually approved rules into an immutable reversible pilot policy overlay.",
        CompilePilotPolicyInput,
        "compile_pilot_policy",
    ),
    ToolDefinition(
        "compare_policy_versions",
        "Compare two immutable compiled pilot policy versions.",
        ComparePolicyVersionsInput,
        "compare_policy_versions",
    ),
    ToolDefinition(
        "run_policy_eval",
        "Evaluate a compiled pilot policy against controlled golden scenarios.",
        RunPolicyEvalInput,
        "run_policy_eval",
    ),
    ToolDefinition(
        "generate_primer_conflict_report",
        "Detect and report contradictory primer rules without silently merging them.",
        GeneratePrimerConflictReportInput,
        "generate_primer_conflict_report",
    ),
    ToolDefinition(
        "list_pilot_profiles",
        "List versioned non-omniscient pilot profiles and supported deck hashes.",
        ListPilotProfilesInput,
        "list_pilot_profiles",
    ),
    ToolDefinition(
        "inspect_pilot",
        "Inspect one pilot profile, weights, source rules and information boundary.",
        InspectPilotInput,
        "inspect_pilot",
    ),
    ToolDefinition(
        "run_pilot_benchmark",
        "Run paired structural benchmarks across realistic pilots for one deck.",
        RunPilotBenchmarkInput,
        "run_pilot_benchmark",
    ),
    ToolDefinition(
        "compare_pilots",
        "Compare selected pilot profiles under identical structural seeds and opponents.",
        ComparePilotsInput,
        "compare_pilots",
    ),
    ToolDefinition(
        "run_pilot_ensemble",
        "Evaluate an equal or custom weighted pilot ensemble, worst pilot and median pilot.",
        RunPilotEnsembleInput,
        "run_pilot_ensemble",
    ),
    ToolDefinition(
        "test_variant_across_pilots",
        "Test a deck variant across multiple pilots without applying the change.",
        TestVariantAcrossPilotsInput,
        "test_variant_across_pilots",
    ),
    ToolDefinition(
        "generate_pilot_robustness_report",
        "Generate a Markdown pilot robustness report from a structural result.",
        GeneratePilotRobustnessReportInput,
        "generate_pilot_robustness_report",
    ),
    ToolDefinition(
        "extract_archetypes",
        "Extract weighted explainable archetypes from roles and "
        "project evidence without changing the deck.",
        ExtractArchetypesInput,
        "extract_archetypes",
    ),
    ToolDefinition(
        "extract_packages",
        "Extract curated packages and conservative unconfirmed machine candidates for a deck.",
        ExtractPackagesInput,
        "extract_packages",
    ),
    ToolDefinition(
        "inspect_package",
        "Inspect one package definition and optionally evaluate it against a compatible deck.",
        InspectPackageInput,
        "inspect_package",
    ),
    ToolDefinition(
        "compare_package_versions",
        "Compare two immutable versions of one curated package.",
        ComparePackageVersionsInput,
        "compare_package_versions",
    ),
    ToolDefinition(
        "evaluate_package_density",
        "Evaluate package completeness, density, redundancy and failure modes.",
        EvaluatePackageDensityInput,
        "evaluate_package_density",
    ),
    ToolDefinition(
        "detect_orphaned_cards",
        "Detect support cards without payoffs and payoffs without enablers.",
        DetectOrphanedCardsInput,
        "detect_orphaned_cards",
    ),
    ToolDefinition(
        "generate_package_report",
        "Generate an explainable archetype/package Markdown report.",
        GeneratePackageReportInput,
        "generate_package_report",
    ),
    ToolDefinition(
        "trace_artifact_provenance",
        "Trace an artifact through sources, transformations and derived records.",
        TraceArtifactProvenanceInput,
        "trace_artifact_provenance",
    ),
    ToolDefinition(
        "trace_recommendation_sources",
        "Trace a recommendation to its deck, pilot, simulation and evidence sources.",
        TraceRecommendationSourcesInput,
        "trace_recommendation_sources",
    ),
    ToolDefinition(
        "list_superseded_sources",
        "List superseded sources while retaining historical records.",
        ListSupersededSourcesInput,
        "list_superseded_sources",
    ),
    ToolDefinition(
        "verify_source_hash",
        "Verify a source file against its registered content hash.",
        VerifySourceHashInput,
        "verify_source_hash",
    ),
    ToolDefinition(
        "generate_provenance_report",
        "Generate a complete provenance graph report.",
        GenerateProvenanceReportInput,
        "generate_provenance_report",
    ),
    ToolDefinition(
        "audit_unreferenced_claims",
        "Audit claims lacking sources, model labels or explicit inference labels.",
        AuditUnreferencedClaimsInput,
        "audit_unreferenced_claims",
    ),
    ToolDefinition(
        "create_opponent_ensemble",
        "Create a versioned opponent ensemble from structured variants.",
        CreateOpponentEnsembleInput,
        "create_opponent_ensemble",
    ),
    ToolDefinition(
        "add_opponent_variant",
        "Add a variant by creating a new ensemble version.",
        AddOpponentVariantInput,
        "add_opponent_variant",
    ),
    ToolDefinition(
        "validate_ensemble",
        "Validate observed constraints, color identity and weights.",
        ValidateEnsembleInput,
        "validate_ensemble",
    ),
    ToolDefinition(
        "run_ensemble_matchups",
        "Run structural matchup estimates across every opponent variant.",
        RunEnsembleMatchupsInput,
        "run_ensemble_matchups",
    ),
    ToolDefinition(
        "compare_variant_sensitivity",
        "Report average, median, worst, spread and sensitive assumptions.",
        CompareVariantSensitivityInput,
        "compare_variant_sensitivity",
    ),
    ToolDefinition(
        "evaluate_robust_upgrade",
        "Evaluate whether an upgrade is nonnegative across opponent variants.",
        EvaluateRobustUpgradeInput,
        "evaluate_robust_upgrade",
    ),
    ToolDefinition(
        "generate_ensemble_report",
        "Generate a report separating known cards and synthetic assumptions.",
        GenerateEnsembleReportInput,
        "generate_ensemble_report",
    ),
    ToolDefinition(
        "sample_opening_hands",
        "Sample deterministic London-mulligan opening-hand "
        "sequences without commanders in the library.",
        SampleOpeningHandsInput,
        "sample_opening_hands",
    ),
    ToolDefinition(
        "evaluate_opening_hand",
        "Evaluate one current-deck opening hand under a versioned model-based mulligan policy.",
        EvaluateOpeningHandInput,
        "evaluate_opening_hand",
    ),
    ToolDefinition(
        "compare_mulligan_policies",
        "Compare mulligan policies using common random numbers and "
        "separate hand/follow-up estimates.",
        CompareMulliganPoliciesInput,
        "compare_mulligan_policies",
    ),
    ToolDefinition(
        "run_mulligan_lab",
        "Run and persist the deckhash-bound Mulligan Lab.",
        RunMulliganLabInput,
        "run_mulligan_lab",
    ),
    ToolDefinition(
        "generate_keep_rules",
        "Generate candidate model-based keep rules from a Mulligan Lab result.",
        GenerateKeepRulesInput,
        "generate_keep_rules",
    ),
    ToolDefinition(
        "test_keep_rule",
        "Test a generated keep-rule candidate against one explicit hand.",
        TestKeepRuleInput,
        "test_keep_rule",
    ),
    ToolDefinition(
        "create_mulligan_report",
        "Create a Mulligan Lab report with uncertainty and truth-boundary labels.",
        CreateMulliganReportInput,
        "create_mulligan_report",
    ),
    ToolDefinition(
        "find_counterfactual_branchpoints",
        "Find replay decision branchpoints with hashes and recorded legal candidates.",
        FindCounterfactualBranchpointsInput,
        "find_counterfactual_branchpoints",
    ),
    ToolDefinition(
        "list_alternative_actions",
        "List only recorded legal alternatives at a verified replay branchpoint.",
        ListAlternativeActionsInput,
        "list_alternative_actions",
    ),
    ToolDefinition(
        "run_counterfactual",
        "Run a structural or tactical counterfactual model "
        "alternative with explicit hidden-information policy.",
        RunCounterfactualInput,
        "run_counterfactual",
    ),
    ToolDefinition(
        "compare_counterfactuals",
        "Compare multiple model-dependent counterfactual alternatives.",
        CompareCounterfactualsInput,
        "compare_counterfactuals",
    ),
    ToolDefinition(
        "generate_decision_regret_report",
        "Generate a decision-regret report without claiming historical certainty.",
        GenerateDecisionRegretReportInput,
        "generate_decision_regret_report",
    ),
    ToolDefinition(
        "export_minimal_counterfactual_fixture",
        "Export a verified branchpoint as a minimal Golden Scenario fixture.",
        ExportMinimalCounterfactualFixtureInput,
        "export_minimal_counterfactual_fixture",
    ),
    ToolDefinition(
        "diagnose_card_performance",
        "Diagnose card weakness versus misuse, package, pilot, opponent, model or variance causes.",
        DiagnoseCardPerformanceInput,
        "diagnose_card_performance",
    ),
    ToolDefinition(
        "diagnose_pilot_behavior",
        "Diagnose missed lines, timing errors and pilot-style mismatch.",
        DiagnosePilotBehaviorInput,
        "diagnose_pilot_behavior",
    ),
    ToolDefinition(
        "compare_deck_and_pilot_effects",
        "Compare deck, pilot, opponent, action and seed effects without claiming causality.",
        CompareDeckAndPilotEffectsInput,
        "compare_deck_and_pilot_effects",
    ),
    ToolDefinition(
        "classify_failure_cause",
        "Classify the most supported failure cause with counterevidence and uncertainty.",
        ClassifyFailureCauseInput,
        "classify_failure_cause",
    ),
    ToolDefinition(
        "recommend_next_experiment",
        "Recommend the next discriminating experiment from a diagnosis.",
        RecommendNextExperimentInput,
        "recommend_next_experiment",
    ),
    ToolDefinition(
        "generate_diagnostic_report",
        "Generate a model-labeled diagnostic report and cut release gates.",
        GenerateDiagnosticReportInput,
        "generate_diagnostic_report",
    ),
)


class ToolRegistry:
    def __init__(self, service: CommanderToolService) -> None:
        self.service = service
        self._definitions = {definition.name: definition for definition in TOOL_DEFINITIONS}

    def list_schemas(self) -> list[dict[str, Any]]:
        return [definition.schema() for definition in TOOL_DEFINITIONS]

    def input_model(self, name: str) -> type[BaseModel]:
        try:
            return self._definitions[name].input_model
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def invoke(self, name: str, payload: dict[str, Any]) -> ToolResponse:
        try:
            definition = self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc
        request = definition.input_model.model_validate(payload)
        handler: Callable[[Any], ToolResponse] = getattr(self.service, definition.handler_name)
        return handler(request)
