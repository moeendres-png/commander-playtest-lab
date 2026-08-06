from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from commander_lab.models import (
    BeamSearchInput,
    CalibrateInput,
    CardAblationInput,
    CommanderDenialInput,
    CompareDecksInput,
    CreateReportInput,
    CompareDeckToMetaInput,
    CompareMetaPeriodsInput,
    CreateMetaSnapshotInput,
    GenerateMetaReportInput,
    ImportPrimerInput,
    ExtractPrimerRulesInput,
    ValidatePilotRulesInput,
    CompilePilotPolicyInput,
    ComparePolicyVersionsInput,
    RunPolicyEvalInput,
    GeneratePrimerConflictReportInput,
    ListPilotProfilesInput,
    InspectPilotInput,
    RunPilotBenchmarkInput,
    ComparePilotsInput,
    RunPilotEnsembleInput,
    TestVariantAcrossPilotsInput,
    GeneratePilotRobustnessReportInput,
    ExtractArchetypesInput,
    ExtractPackagesInput,
    InspectPackageInput,
    ComparePackageVersionsInput,
    EvaluatePackageDensityInput,
    DetectOrphanedCardsInput,
    GeneratePackageReportInput,
    TraceArtifactProvenanceInput, TraceRecommendationSourcesInput,
    ListSupersededSourcesInput, VerifySourceHashInput,
    GenerateProvenanceReportInput, AuditUnreferencedClaimsInput,
    GoldfishInput,
    HoldoutInput,
    ImportMetaDeckInput,
    ImportPrimerReferenceInput,
    ImportTournamentResultInput,
    IngestPlaytestInput,
    InspectDeckInput,
    LocalSearchInput,
    MatchupBatchInput,
    PackageSearchInput,
    ParetoFrontInput,
    QueryMetaCardsInput,
    QueryMetaPackagesInput,
    PackageAblationInput,
    PairedVariantInput,
    RecommendUpgradesInput,
    SearchVariantsInput,
    SensitivityInput,
    ShapleyInput,
    SwapMatrixInput,
    ToolResponse,
    ValidateDeckInput,
    ValidateUpgradeInput,
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
    ToolDefinition("validate_deck", "Validate Commander legality, size, singleton, color identity and local allocation.", ValidateDeckInput, "validate_deck"),
    ToolDefinition("inspect_deck", "Inspect role counts, structural weaknesses and optional card profiles.", InspectDeckInput, "inspect_deck"),
    ToolDefinition("run_goldfish", "Run a deterministic structural goldfish batch.", GoldfishInput, "run_goldfish"),
    ToolDefinition("run_matchup_batch", "Run a structural multiplayer matchup batch.", MatchupBatchInput, "run_matchup_batch"),
    ToolDefinition("compare_decks", "Compare two complete decks under paired random conditions.", CompareDecksInput, "compare_decks"),
    ToolDefinition("compare_variants_paired", "Compare a baseline and card-swap variant using identical seeds.", PairedVariantInput, "compare_variants_paired"),
    ToolDefinition("run_card_ablation", "Estimate a card contribution with role-neutral paired ablation.", CardAblationInput, "run_card_ablation"),
    ToolDefinition("run_package_ablation", "Estimate a package contribution with paired ablation.", PackageAblationInput, "run_package_ablation"),
    ToolDefinition("run_commander_denial", "Stress-test a deck with added commander tax and optional synergy suppression.", CommanderDenialInput, "run_commander_denial"),
    ToolDefinition("generate_swap_matrix", "Evaluate a matrix of cuts and candidate additions.", SwapMatrixInput, "generate_swap_matrix"),
    ToolDefinition("search_variants", "Search bounded one-card structural variants.", SearchVariantsInput, "search_variants"),
    ToolDefinition("run_local_search", "Run constrained iterative local search without applying changes.", LocalSearchInput, "run_local_search"),
    ToolDefinition("run_beam_search", "Run constrained multi-step beam search over deck variants.", BeamSearchInput, "run_beam_search"),
    ToolDefinition("run_package_search", "Search and evaluate multi-card packages under hard constraints.", PackageSearchInput, "run_package_search"),
    ToolDefinition("evaluate_pareto_front", "Evaluate variants on multiple objectives and return the non-dominated front.", ParetoFrontInput, "evaluate_pareto_front"),
    ToolDefinition("estimate_shapley", "Estimate card contributions using permutation Shapley approximation and paired ablation.", ShapleyInput, "estimate_shapley"),
    ToolDefinition("run_holdout", "Evaluate a proposed variant on unused holdout pods.", HoldoutInput, "run_holdout"),
    ToolDefinition("run_sensitivity", "Repeat scenarios across seeds and pilot strengths.", SensitivityInput, "run_sensitivity"),
    ToolDefinition("recommend_upgrades", "Screen role-profile upgrade candidates without claiming confirmation.", RecommendUpgradesInput, "recommend_upgrades"),
    ToolDefinition("validate_upgrade", "Confirm or reject a proposed upgrade using paired and holdout criteria.", ValidateUpgradeInput, "validate_upgrade"),
    ToolDefinition("ingest_playtest", "Import a local real-playtest CSV, XLSX or JSON file into an append-only versioned dataset.", IngestPlaytestInput, "ingest_playtest"),
    ToolDefinition("calibrate", "Compare sealed real train/validation evidence with structural references and write a non-applied calibration profile.", CalibrateInput, "calibrate"),
    ToolDefinition("create_report", "Create a local structured Markdown evidence report.", CreateReportInput, "create_report"),
    ToolDefinition("import_meta_deck", "Import a meta deck into the append-only Meta Knowledge Base staging layer without changing local decks.", ImportMetaDeckInput, "import_meta_deck"),
    ToolDefinition("import_tournament_result", "Import tournament metadata into the append-only Meta Knowledge Base staging layer.", ImportTournamentResultInput, "import_tournament_result"),
    ToolDefinition("import_primer_reference", "Import primer notes into the append-only Meta Knowledge Base staging layer.", ImportPrimerReferenceInput, "import_primer_reference"),
    ToolDefinition("create_meta_snapshot", "Create an immutable versioned Meta Knowledge Base snapshot from structured seed sources.", CreateMetaSnapshotInput, "create_meta_snapshot"),
    ToolDefinition("query_meta_cards", "Query card frequencies from the latest Meta Knowledge Base snapshot.", QueryMetaCardsInput, "query_meta_cards"),
    ToolDefinition("query_meta_packages", "Query package usage from the latest Meta Knowledge Base snapshot.", QueryMetaPackagesInput, "query_meta_packages"),
    ToolDefinition("compare_deck_to_meta", "Compare a local deck to external meta references without applying changes.", CompareDeckToMetaInput, "compare_deck_to_meta"),
    ToolDefinition("compare_meta_periods", "Compare two immutable meta snapshots to detect meta drift.", CompareMetaPeriodsInput, "compare_meta_periods"),
    ToolDefinition("generate_meta_report", "Generate a Markdown report summarizing the latest Meta Knowledge Base snapshot.", GenerateMetaReportInput, "generate_meta_report"),
    ToolDefinition("import_primer", "Import primer metadata and content hash without executing source text.", ImportPrimerInput, "import_primer"),
    ToolDefinition("extract_primer_rules", "Conservatively extract disabled rule candidates from a registered primer.", ExtractPrimerRulesInput, "extract_primer_rules"),
    ToolDefinition("validate_pilot_rules", "Validate pilot rules against the fixed safe DSL and optional deck scope.", ValidatePilotRulesInput, "validate_pilot_rules"),
    ToolDefinition("compile_pilot_policy", "Compile manually approved rules into an immutable reversible pilot policy overlay.", CompilePilotPolicyInput, "compile_pilot_policy"),
    ToolDefinition("compare_policy_versions", "Compare two immutable compiled pilot policy versions.", ComparePolicyVersionsInput, "compare_policy_versions"),
    ToolDefinition("run_policy_eval", "Evaluate a compiled pilot policy against controlled golden scenarios.", RunPolicyEvalInput, "run_policy_eval"),
    ToolDefinition("generate_primer_conflict_report", "Detect and report contradictory primer rules without silently merging them.", GeneratePrimerConflictReportInput, "generate_primer_conflict_report"),
    ToolDefinition("list_pilot_profiles", "List versioned non-omniscient pilot profiles and supported deck hashes.", ListPilotProfilesInput, "list_pilot_profiles"),
    ToolDefinition("inspect_pilot", "Inspect one pilot profile, weights, source rules and information boundary.", InspectPilotInput, "inspect_pilot"),
    ToolDefinition("run_pilot_benchmark", "Run paired structural benchmarks across realistic pilots for one deck.", RunPilotBenchmarkInput, "run_pilot_benchmark"),
    ToolDefinition("compare_pilots", "Compare selected pilot profiles under identical structural seeds and opponents.", ComparePilotsInput, "compare_pilots"),
    ToolDefinition("run_pilot_ensemble", "Evaluate an equal or custom weighted pilot ensemble, worst pilot and median pilot.", RunPilotEnsembleInput, "run_pilot_ensemble"),
    ToolDefinition("test_variant_across_pilots", "Test a deck variant across multiple pilots without applying the change.", TestVariantAcrossPilotsInput, "test_variant_across_pilots"),
    ToolDefinition("generate_pilot_robustness_report", "Generate a Markdown pilot robustness report from a structural result.", GeneratePilotRobustnessReportInput, "generate_pilot_robustness_report"),
    ToolDefinition("extract_archetypes", "Extract weighted explainable archetypes from roles and project evidence without changing the deck.", ExtractArchetypesInput, "extract_archetypes"),
    ToolDefinition("extract_packages", "Extract curated packages and conservative unconfirmed machine candidates for a deck.", ExtractPackagesInput, "extract_packages"),
    ToolDefinition("inspect_package", "Inspect one package definition and optionally evaluate it against a compatible deck.", InspectPackageInput, "inspect_package"),
    ToolDefinition("compare_package_versions", "Compare two immutable versions of one curated package.", ComparePackageVersionsInput, "compare_package_versions"),
    ToolDefinition("evaluate_package_density", "Evaluate package completeness, density, redundancy and failure modes.", EvaluatePackageDensityInput, "evaluate_package_density"),
    ToolDefinition("detect_orphaned_cards", "Detect support cards without payoffs and payoffs without enablers.", DetectOrphanedCardsInput, "detect_orphaned_cards"),
    ToolDefinition("generate_package_report", "Generate an explainable archetype/package Markdown report.", GeneratePackageReportInput, "generate_package_report"),
    ToolDefinition("trace_artifact_provenance", "Trace an artifact through sources, transformations and derived records.", TraceArtifactProvenanceInput, "trace_artifact_provenance"),
    ToolDefinition("trace_recommendation_sources", "Trace a recommendation to its deck, pilot, simulation and evidence sources.", TraceRecommendationSourcesInput, "trace_recommendation_sources"),
    ToolDefinition("list_superseded_sources", "List superseded sources while retaining historical records.", ListSupersededSourcesInput, "list_superseded_sources"),
    ToolDefinition("verify_source_hash", "Verify a source file against its registered content hash.", VerifySourceHashInput, "verify_source_hash"),
    ToolDefinition("generate_provenance_report", "Generate a complete provenance graph report.", GenerateProvenanceReportInput, "generate_provenance_report"),
    ToolDefinition("audit_unreferenced_claims", "Audit claims lacking sources, model labels or explicit inference labels.", AuditUnreferencedClaimsInput, "audit_unreferenced_claims"),
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
