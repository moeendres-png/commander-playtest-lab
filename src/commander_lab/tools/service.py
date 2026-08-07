from __future__ import annotations

import itertools
import json
import subprocess
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Callable

from commander_lab.analysis import DeckValidator, validate_collection_quantities
from commander_lab.cards.catalog import CardCatalog
from commander_lab.engine.structural import ENGINE_VERSION, load_project_structural_decks, run_structural_batch
from commander_lab.models import (
    BudgetBand,
    CompareDeckToMetaInput,
    CompareMetaPeriodsInput,
    CreateMetaSnapshotInput,
    FormatBand,
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
    CreateOpponentEnsembleInput, AddOpponentVariantInput, ValidateEnsembleInput,
    RunEnsembleMatchupsInput, CompareVariantSensitivityInput,
    EvaluateRobustUpgradeInput, GenerateEnsembleReportInput,
    PilotEnsembleDefinition,
    PilotEnsembleMember,
    CompiledPilotPolicy,
    PilotRule,
    PolicyEvalScenario,
    ImportMetaDeckInput,
    ImportPrimerReferenceInput,
    ImportTournamentResultInput,
    MetaCategory,
    MetaDeckSnapshot,
    MetaEvidenceRating,
    MetaKnowledgeBaseSnapshot,
    MetaSource,
    PrimerReference,
    QueryMetaCardsInput,
    QueryMetaPackagesInput,
    TournamentResult,
    CardAblationInput,
    Collection,
    CommanderDenialInput,
    CompareDecksInput,
    CostLimits,
    CreateReportInput,
    GoldfishInput,
    HoldoutInput,
    InspectDeckInput,
    MatchupBatchInput,
    BeamSearchInput,
    CandidatePackage,
    LocalSearchInput,
    OptimizationConstraints,
    OptimizationVariant,
    PackageSearchInput,
    ParetoFrontInput,
    ShapleyInput,
    PackageAblationInput,
    PairedVariantInput,
    PilotConfig,
    PilotStrength,
    RecommendUpgradesInput,
    SearchVariantsInput,
    SensitivityInput,
    StructuralBatchConfig,
    StructuralDeckProfile,
    SwapMatrixInput,
    ToolExecutionMetadata,
    ToolResponse,
    ToolStatus,
    ValidateDeckInput,
    ValidateUpgradeInput,
    VariantSwap,
    BuildOptimizationContextInput,
    GenerateCandidateSwapsInput,
    GenerateCandidatePackagesInput,
    OptimizeDeckAgainstMetaInput,
    OptimizeMultipleDecksWithAllocationInput,
    ValidateSwapInput,
    ValidatePackageChangeInput,
    ValidateLandChangeInput,
    ValidateMulliganPolicyInput,
    RunMultifidelityComparisonInput,
    RunEngineBackedMatchupInput,
    RunRobustnessSuiteInput,
    RunRulesCoverageGateInput,
    RankVariantsInput,
    ExplainRecommendationInput,
    ExportRecommendationEvidenceInput,
    CreateDeckImprovementReportInput,
)
from commander_lab.optimization import (
    DEFAULT_CONSTRAINTS,
    SearchCandidate,
    ablation_filler,
    all_legal_single_swaps,
    approximate_shapley_profile,
    build_search_candidate,
    default_constraints,
    evaluate_constraints,
    load_candidate_inventory,
    objective_vector,
    pareto_front,
    profile_score,
    role_summary,
    run_paired_structural_comparison,
    variant_deck,
)
from commander_lab.decision_statistics import holm_adjust
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
    load_model,
    sha256_value,
)
from commander_lab.models import Deck
from commander_lab.meta import MetaKnowledgeBase
from commander_lab.meta.store import stable_deck_hash
from commander_lab.primer import PrimerToPilotCompiler
from commander_lab.agents.pilots import build_pilot
from commander_lab.agents.ensemble import PilotEnsembleRunner, PilotRegistry
from commander_lab.packages import ArchetypePackageExtractor, PackageExtractionError
from commander_lab.provenance import ProvenanceStore
from commander_lab.robustness import POLITICS_REGIMES, pilot_config_for
from commander_lab.engine.rules import (
    RulesEngineManager, TacticalRuleOracle, load_interaction_catalog, load_project_rules_decks,
)
from commander_lab.models import ActionProposal, RulesGameRequest

from commander_lab.mulligan import MulliganLab
from commander_lab.models.mulligan import (
    GeneratedKeepRule, MulliganContext, MulliganGamePlan, MulliganLabResult,
    MulliganPolicyName, OpeningHandFeatures,
)
from commander_lab.models.tooling import (
    SampleOpeningHandsInput, EvaluateOpeningHandInput, CompareMulliganPoliciesInput,
    RunMulliganLabInput, GenerateKeepRulesInput, TestKeepRuleInput, CreateMulliganReportInput,
)
from commander_lab.opponent_ensembles import OpponentEnsembleStore
from commander_lab.models.opponent_ensembles import OpponentEnsemble, OpponentVariant

from .candidates import load_candidate_profiles, load_canonical_inventory_quantities


class ToolExecutionError(RuntimeError):
    pass


class ApprovalRequired(ToolExecutionError):
    pass


def _deterministic_structural_run_id(prefix: str, request: Any) -> str:
    """Separate deterministic simulation identity from unique artifact storage."""
    payload = (
        request.model_dump(mode="json", exclude={"approval_token"})
        if hasattr(request, "model_dump")
        else request
    )
    digest = sha256_value(
        {"engine_version": ENGINE_VERSION, "tool": prefix, "request": payload}
    )
    return f"{prefix}-{digest[:16]}"


class CommanderToolService:
    """Deterministic local Function Tool service.

    The service is the sole mutation boundary for local artifacts. Agent code receives only these
    methods and cannot directly mutate game state. Simulation results remain structural estimates.
    """

    def __init__(self, root: str | Path, *, limits: CostLimits | None = None) -> None:
        self.root = Path(root).resolve()
        self.limits = limits or self._load_limits()
        self.decks = load_project_structural_decks(
            self.root,
            include_synthetic_fixtures=True,
            include_current_opponents=True,
        )
        self.candidates = load_candidate_profiles(self.root)
        canonical_inventory = load_canonical_inventory_quantities(self.root)
        if canonical_inventory:
            baseline_required: Counter[str] = Counter()
            for deck_id in ("korvold/current", "rogshai/current"):
                deck = self.decks.get(deck_id)
                if deck is None:
                    continue
                baseline_required.update(
                    card.oracle_name for card in deck.cards
                    if card.oracle_name not in {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
                )
            self.candidate_inventory = {
                name: max(0, quantity - baseline_required.get(name, 0))
                for name, quantity in canonical_inventory.items()
            }
        else:
            self.candidate_inventory = load_candidate_inventory(self.root)
        filtered_candidates = {}
        for candidate_id, candidate in self.candidates.items():
            if self.candidate_inventory.get(candidate.card.oracle_name, 0) <= 0:
                continue
            allowed = tuple(
                deck_id for deck_id in candidate.allowed_deck_ids
                if deck_id not in self.decks
                or candidate.card.oracle_name not in {card.oracle_name for card in self.decks[deck_id].cards}
            )
            if not allowed:
                continue
            filtered_candidates[candidate_id] = candidate.model_copy(update={"allowed_deck_ids": allowed})
        self.candidates = filtered_candidates
        self.verified_candidate_names = {
            candidate.card.oracle_name
            for candidate in self.candidates.values()
            if candidate.physical_status in {"local_project_verified_owned", "canonical_inventory_verified_owned"}
            and self.candidate_inventory.get(candidate.card.oracle_name, 0) > 0
        }
        protected_path = self.root / "config/protected_cards.json"
        self.protected_cards = json.loads(protected_path.read_text(encoding="utf-8")) if protected_path.exists() else {}
        self.manifest = json.loads((self.root / "data/decks/manifest.json").read_text(encoding="utf-8"))
        self.trace_dir = self.root / "data/runs/openai_traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.root / "data/runs/reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _provenance(self) -> ProvenanceStore:
        return ProvenanceStore(self.root)

    def _opponent_ensembles(self) -> OpponentEnsembleStore:
        return OpponentEnsembleStore(self.root)

    def _load_limits(self) -> CostLimits:
        path = self.root / "config/openai_workflow.json"
        if not path.exists():
            return CostLimits()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CostLimits.model_validate(payload.get("budgets", payload))

    @property
    def git_commit(self) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    def _check_iterations(self, iterations: int, approval_token: str | None) -> None:
        if iterations > self.limits.hard_max_iterations:
            raise ToolExecutionError(
                f"iterations {iterations} exceed hard maximum {self.limits.hard_max_iterations}"
            )
        if iterations > self.limits.approval_threshold_iterations and approval_token != "APPROVED_LARGE_RUN":
            raise ApprovalRequired(
                f"iterations {iterations} require approval token APPROVED_LARGE_RUN"
            )

    def _deck(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self.decks[deck_id]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown structural deck: {deck_id}") from exc


    def _is_protected(self, deck_id: str, card_name: str) -> bool:
        return card_name in set(self.protected_cards.get(deck_id, []))

    def _validate_swap_policy(self, deck_id: str, remove: str, candidate_card: Any) -> None:
        if not self._is_protected(deck_id, remove):
            return
        deck = self._deck(deck_id)
        original = next((card for card in deck.cards if card.oracle_name == remove), None)
        if original is None:
            raise ToolExecutionError(f"protected card not found in deck: {remove}")
        same_role_upgrade = original.roles.issubset(candidate_card.roles) and profile_score(candidate_card) > profile_score(original)
        if not same_role_upgrade:
            raise ToolExecutionError(
                f"{remove} is protected by current deckbuilding rules and may only be tested against "
                "a clear direct upgrade covering the same roles"
            )

    def _candidate(self, candidate_id: str, deck_id: str):
        try:
            candidate = self.candidates[candidate_id]
        except KeyError as exc:
            raise ToolExecutionError(f"unknown upgrade candidate: {candidate_id}") from exc
        if candidate.allowed_deck_ids and deck_id not in candidate.allowed_deck_ids:
            raise ToolExecutionError(f"candidate {candidate_id} is not allowed for {deck_id}")
        return candidate

    def _optimization_constraints(
        self, deck_id: str, supplied: OptimizationConstraints | None = None
    ) -> OptimizationConstraints:
        if supplied is not None:
            return supplied
        path = self.root / "config/phase7_optimization.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if deck_id in payload.get("constraints", {}):
                return OptimizationConstraints.model_validate(payload["constraints"][deck_id])
        return default_constraints(deck_id, None, DEFAULT_CONSTRAINTS)

    def _eligible_candidate_ids(
        self, deck_id: str, requested: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        ids = requested or tuple(self.candidates)
        return tuple(
            candidate_id for candidate_id in ids
            if candidate_id in self.candidates
            and (
                not self.candidates[candidate_id].allowed_deck_ids
                or deck_id in self.candidates[candidate_id].allowed_deck_ids
            )
        )

    def _paired_variant_metrics(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        opponent_deck_ids: tuple[str, ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
        pair_id: str,
    ):
        return run_paired_structural_comparison(
            baseline=baseline,
            variant=variant,
            opponents=tuple(self._deck(deck_id) for deck_id in opponent_deck_ids),
            iterations=iterations,
            seed=seed,
            pilot_config=PilotConfig(strength=pilot_strength, mode=pilot_mode),
            max_turns=max_turns,
            pair_id=pair_id,
        )

    @staticmethod
    def _commander_dependency_penalty(deck: StructuralDeckProfile) -> float:
        nonlands = [card for card in deck.cards if not card.is_land]
        if not nonlands:
            return 0.0
        synergy = fmean(card.commander_synergy for card in nonlands) / 2.0
        floor = fmean(card.floor_value for card in nonlands) / 2.0
        return max(0.0, min(1.0, synergy * (1.0 - 0.35 * floor)))

    def _holdout_improvements(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        holdout_pods: tuple[tuple[str, ...], ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, pod in enumerate(holdout_pods):
            metrics, pairs = self._paired_variant_metrics(
                baseline=baseline, variant=variant, opponent_deck_ids=pod,
                iterations=iterations, seed=seed + index + 1,
                pilot_strength=pilot_strength, pilot_mode=pilot_mode, max_turns=max_turns,
                pair_id=f"holdout-{variant.deck_hash[:10]}-{index}",
            )
            rows.append({
                "pod": pod,
                "comparison": metrics.as_dict(),
                "pair_count": len(pairs),
            })
        return rows

    def _red_team_review(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        swaps: tuple[Any, ...],
        constraint_report: Any,
        paired: dict[str, Any],
        holdouts: list[dict[str, Any]],
        sensitivity: list[dict[str, Any]],
    ) -> dict[str, Any]:
        concerns: list[str] = []
        alternatives: list[str] = []
        if not constraint_report.valid:
            concerns.append("The variant violates one or more hard deck constraints.")
        if paired.get("placement_improvement", 0.0) <= 0:
            concerns.append("The primary paired comparison does not improve average placement.")
        if paired.get("paired_win_count", 0) <= paired.get("paired_loss_count", 0):
            concerns.append("Paired game outcomes do not favor the variant over the baseline.")
        negative_holdouts = [
            row for row in holdouts
            if row["comparison"].get("placement_improvement", 0.0) < 0
        ]
        if negative_holdouts:
            concerns.append("At least one holdout matchup becomes worse.")
        sensitivity_values = [row["placement_improvement"] for row in sensitivity]
        if sensitivity_values and min(sensitivity_values) < 0:
            concerns.append("The result changes sign across sensitivity settings.")
        if len(sensitivity_values) >= 2 and max(sensitivity_values) - min(sensitivity_values) > 0.20:
            concerns.append("The estimated effect is highly sensitive to seed or pilot strength.")
        removed_roles = Counter()
        added_roles = Counter()
        for swap in swaps:
            original = next((c for c in baseline.cards if c.oracle_name == swap.remove), None)
            candidate = self.candidates.get(swap.add_candidate_id)
            if original:
                removed_roles.update(original.roles)
            if candidate:
                added_roles.update(candidate.card.roles)
        for role, count in removed_roles.items():
            if added_roles[role] < count:
                concerns.append(f"Net role loss detected: {role.value}.")
        if len(swaps) > 1:
            alternatives.append("Validate each swap separately to distinguish package synergy from a weak component.")
        alternatives.append("Retain the baseline when the effect is small relative to holdout or sensitivity variation.")
        passed = not concerns
        return {
            "passed": passed,
            "concerns": concerns,
            "alternative_explanations": alternatives,
            "automatic_application_allowed": False,
        }

    def _evaluate_search_candidate(
        self,
        *,
        baseline: StructuralDeckProfile,
        candidate: Any,
        opponent_deck_ids: tuple[str, ...],
        holdout_pods: tuple[tuple[str, ...], ...],
        iterations: int,
        seed: int,
        pilot_strength: Any,
        pilot_mode: Any,
        max_turns: int,
        search_method: str,
    ) -> tuple[OptimizationVariant, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        metrics, pairs = self._paired_variant_metrics(
            baseline=baseline, variant=candidate.variant, opponent_deck_ids=opponent_deck_ids,
            iterations=iterations, seed=seed, pilot_strength=pilot_strength,
            pilot_mode=pilot_mode, max_turns=max_turns,
            pair_id=f"phase7-{search_method}-{candidate.variant.deck_hash[:10]}",
        )
        holdouts = self._holdout_improvements(
            baseline=baseline, variant=candidate.variant, holdout_pods=holdout_pods,
            iterations=iterations, seed=seed, pilot_strength=pilot_strength,
            pilot_mode=pilot_mode, max_turns=max_turns,
        )
        holdout_values = [row["comparison"]["placement_improvement"] for row in holdouts]
        objectives = objective_vector(
            metrics=metrics, pairs=pairs, variant=candidate.variant,
            commander_dependency_penalty=self._commander_dependency_penalty(candidate.variant),
            holdout_improvements=holdout_values,
            physical_valid=candidate.constraint_report.valid,
        )
        result = OptimizationVariant(
            variant_id=candidate.variant.deck_id,
            deck_id=baseline.deck_id,
            deck_hash=candidate.variant.deck_hash,
            swaps=candidate.swaps,
            structural_rationale=candidate.rationale,
            affected_matchups=candidate.affected_matchups,
            constraint_report=candidate.constraint_report,
            objectives=objectives,
            screening_score=candidate.screening_score,
            search_method=search_method,
            parent_variant_id=candidate.parent_variant_id,
        )
        return result, {"comparison": metrics.as_dict(), "pairs": pairs}, holdouts, []

    def _metadata(
        self,
        *,
        tool_name: str,
        invocation_id: str,
        started: float,
        scenario: object,
        deck_ids: tuple[str, ...] = (),
        seed: int | None = None,
        iterations: int | None = None,
        log_dir: str | None = None,
        estimate_type: str = "structural_model_estimates",
    ) -> ToolExecutionMetadata:
        return ToolExecutionMetadata(
            tool_name=tool_name,
            invocation_id=invocation_id,
            created_at=datetime.now(UTC),
            git_commit=self.git_commit,
            engine_version=ENGINE_VERSION,
            data_snapshot_hash=str(self.manifest["data_snapshot_hash"]),
            deck_hashes={deck_id: self._deck(deck_id).deck_hash for deck_id in deck_ids if deck_id in self.decks},
            scenario_hash=sha256_value(scenario),
            configuration_hash=sha256_value(scenario),
            opponent_hashes={deck_id: self._deck(deck_id).deck_hash for deck_id in deck_ids[1:] if deck_id in self.decks},
            pilot_version=(scenario.get("pilot_version") if isinstance(scenario, dict) else None) or (str(scenario.get("pilot_strength")) if isinstance(scenario, dict) and scenario.get("pilot_strength") else "unspecified"),
            seed=seed,
            iterations=iterations,
            estimate_type=estimate_type,
            elapsed_seconds=time.monotonic() - started,
            deterministic_game_log_directory=log_dir,
            openai_trace_directory=str(self.trace_dir),
        )

    def _invoke(
        self,
        tool_name: str,
        request: Any,
        fn: Callable[[], dict[str, Any]],
        *,
        deck_ids: tuple[str, ...] = (),
        seed: int | None = None,
        iterations: int | None = None,
        log_dir: str | None = None,
        estimate_type: str = "structural_model_estimates",
    ) -> ToolResponse:
        started = time.monotonic()
        invocation_id = f"{tool_name}-{uuid.uuid4().hex[:12]}"
        try:
            result = fn()
            elapsed = time.monotonic() - started
            if elapsed > self.limits.max_simulation_seconds:
                raise ToolExecutionError(
                    f"tool exceeded simulation budget: {elapsed:.3f}s > {self.limits.max_simulation_seconds:.3f}s"
                )
            status = ToolStatus.COMPLETED
            warnings: list[str] = []
            errors: list[str] = []
        except ApprovalRequired as exc:
            result = {}
            status = ToolStatus.REQUIRES_APPROVAL
            warnings = [str(exc)]
            errors = []
        except Exception as exc:  # Tool boundary intentionally converts failures.
            result = {}
            status = ToolStatus.FAILED
            warnings = []
            errors = [f"{type(exc).__name__}: {exc}"]
        metadata = self._metadata(
            tool_name=tool_name,
            invocation_id=invocation_id,
            started=started,
            scenario=request.model_dump(mode="json") if hasattr(request, "model_dump") else request,
            deck_ids=deck_ids,
            seed=seed,
            iterations=iterations,
            log_dir=log_dir,
            estimate_type=estimate_type,
        )
        return ToolResponse(status=status, metadata=metadata, result=result, warnings=warnings, errors=errors)

    def validate_deck(self, request: ValidateDeckInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            spec = self.manifest["decks"].get(request.deck_id)
            if spec is None:
                raise ToolExecutionError(f"validation is available only for local current decks: {request.deck_id}")
            filename = spec["normalized_file"]
            deck = load_model(self.root / "data/decks" / filename, Deck)
            catalog = CardCatalog.from_json(self.root / "data/cards/oracle_subset.json")
            report = DeckValidator(catalog).validate(deck)
            allocation = None
            if request.include_physical_allocation:
                collection = Collection.model_validate_json(
                    (self.root / "data/collections/current_deck_allocations.json").read_text(encoding="utf-8")
                )
                allocation = validate_collection_quantities(collection, [deck]).model_dump(mode="json")
            return {
                "deck_id": request.deck_id,
                "deck_hash": deck.deck_hash,
                "validation": report.model_dump(mode="json"),
                "physical_allocation": allocation,
            }
        return self._invoke("validate_deck", request, work, deck_ids=(request.deck_id,))

    def inspect_deck(self, request: InspectDeckInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            scores = sorted(
                ((card.oracle_name, profile_score(card)) for card in deck.cards),
                key=lambda item: item[1],
            )
            payload: dict[str, Any] = {
                "deck_id": deck.deck_id,
                "deck_hash": deck.deck_hash,
                "commanders": deck.commander_names,
                "strategy": deck.commander_strategy,
                "card_count": len(deck.cards),
                "role_counts": role_summary(deck),
                "lowest_structural_floor": [
                    {"card": name, "profile_score": score} for name, score in scores[:10]
                ],
            }
            if request.deck_id in {"korvold/current", "rogshai/current"}:
                package_result = self._package_extractor().packages_for_deck(
                    request.deck_id, include_machine_candidates=False
                )
                payload["package_diagnostics"] = {
                    "archetype_profile": package_result["archetype_profile"],
                    "evaluations": package_result["evaluations"],
                    "automatic_deck_application": False,
                }
            if request.include_cards:
                payload["cards"] = [card.model_dump(mode="json") for card in deck.cards]
            return payload
        return self._invoke("inspect_deck", request, work, deck_ids=(request.deck_id,))

    def run_goldfish(self, request: GoldfishInput) -> ToolResponse:
        output = self.root / "data/runs/tool_runs" / f"goldfish-{uuid.uuid4().hex[:8]}"
        simulation_run_id = _deterministic_structural_run_id("goldfish", request)
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            config = StructuralBatchConfig(
                run_id=simulation_run_id,
                seed=request.seed,
                iterations=request.iterations,
                deck_ids=(request.deck_id,),
                workers=request.workers,
                pilot_configs=(PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),),
                output_directory=str(output),
            )
            return run_structural_batch(config, self.decks).aggregate
        return self._invoke(
            "run_goldfish", request, work, deck_ids=(request.deck_id,), seed=request.seed,
            iterations=request.iterations, log_dir=str(output / "events")
        )

    def run_matchup_batch(self, request: MatchupBatchInput) -> ToolResponse:
        output = self.root / "data/runs/tool_runs" / f"matchup-{uuid.uuid4().hex[:8]}"
        simulation_run_id = _deterministic_structural_run_id("matchup", request)
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            for deck_id in request.deck_ids:
                self._deck(deck_id)
            config = StructuralBatchConfig(
                run_id=simulation_run_id,
                seed=request.seed,
                iterations=request.iterations,
                deck_ids=request.deck_ids,
                workers=request.workers,
                pilot_configs=tuple(
                    PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode)
                    for _ in request.deck_ids
                ),
                output_directory=str(output),
            )
            batch = run_structural_batch(config, self.decks)
            return {"aggregate": batch.aggregate, "result_path": batch.result_path}
        return self._invoke(
            "run_matchup_batch", request, work, deck_ids=request.deck_ids, seed=request.seed,
            iterations=request.iterations, log_dir=str(output / "events")
        )

    def compare_decks(self, request: CompareDecksInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            opponents = tuple(self._deck(deck_id) for deck_id in request.opponent_deck_ids)
            baseline = self._deck(request.deck_ids[0])
            variant = self._deck(request.deck_ids[1])
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=opponents,
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"compare-{baseline.deck_id}-{variant.deck_id}",
            )
            return {"comparison": metrics.as_dict(), "pair_sample": pairs[:20]}
        ids = (*request.deck_ids, *request.opponent_deck_ids)
        return self._invoke("compare_decks", request, work, deck_ids=ids, seed=request.seed, iterations=request.iterations)

    def _build_variant(self, request: PairedVariantInput) -> tuple[StructuralDeckProfile, StructuralDeckProfile, list[dict[str, Any]]]:
        baseline = self._deck(request.deck_id)
        additions = []
        removals = []
        swap_rows = []
        for swap in request.swaps:
            candidate = self._candidate(swap.add_candidate_id, request.deck_id)
            self._validate_swap_policy(request.deck_id, swap.remove, candidate.card)
            removals.append(swap.remove)
            additions.append(candidate.card)
            swap_rows.append({
                "remove": swap.remove,
                "add": candidate.card.oracle_name,
                "candidate_id": candidate.candidate_id,
                "physical_status": candidate.physical_status,
            })
        variant = variant_deck(
            baseline,
            variant_id=f"{request.deck_id}/variant/{sha256_value(swap_rows)[:12]}",
            removals=removals,
            additions=additions,
        )
        return baseline, variant, swap_rows

    def compare_variants_paired(self, request: PairedVariantInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline, variant, swaps = self._build_variant(request)
            opponents = tuple(self._deck(deck_id) for deck_id in request.opponent_deck_ids)
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=opponents,
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"paired-{variant.deck_hash[:12]}",
            )
            return {
                "baseline_deck_hash": baseline.deck_hash,
                "variant_deck_hash": variant.deck_hash,
                "swaps": swaps,
                "comparison": metrics.as_dict(),
                "pair_sample": pairs[:20],
            }
        return self._invoke(
            "compare_variants_paired", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def run_card_ablation(self, request: CardAblationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            card = next((card for card in baseline.cards if card.oracle_name == request.card_name), None)
            if card is None:
                raise ToolExecutionError(f"card not found: {request.card_name}")
            variant = variant_deck(
                baseline,
                variant_id=f"{request.deck_id}/ablation/{sha256_value(request.card_name)[:12]}",
                removals=(request.card_name,),
                additions=(ablation_filler(card),),
            )
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations,
                seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns,
                pair_id=f"ablation-{request.card_name}",
            )
            contribution = -metrics.placement_improvement
            return {
                "card_name": request.card_name,
                "ablation_comparison": metrics.as_dict(),
                "estimated_card_contribution": {
                    "placement_value": contribution,
                    "interpretation": "positive means the original card improved average placement",
                },
                "pair_sample": pairs[:20],
            }
        return self._invoke("run_card_ablation", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def run_package_ablation(self, request: PackageAblationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            originals = []
            fillers = []
            selected_names = request.card_names
            if request.package_id:
                try:
                    selected_names = self._package_extractor().package_cards_for_ablation(request.deck_id, request.package_id)
                except PackageExtractionError as exc:
                    raise ToolExecutionError(str(exc)) from exc
            for name in selected_names:
                card = next((card for card in baseline.cards if card.oracle_name == name), None)
                if card is None:
                    raise ToolExecutionError(f"card not found: {name}")
                originals.append(name)
                fillers.append(ablation_filler(card, suffix="package ablation"))
            variant = variant_deck(
                baseline,
                variant_id=f"{request.deck_id}/package-ablation/{sha256_value(originals)[:12]}",
                removals=originals,
                additions=fillers,
            )
            metrics, _ = run_paired_structural_comparison(
                baseline=baseline, variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations, seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns, pair_id=f"package-{sha256_value(originals)[:12]}",
            )
            return {
                "package_id": request.package_id,
                "cards": originals,
                "ablation_comparison": metrics.as_dict(),
                "automatic_deck_application": False,
                "estimate_type": "structural_model_estimates",
            }
        return self._invoke("run_package_ablation", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def run_commander_denial(self, request: CommanderDenialInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            variant = variant_deck(
                baseline,
                variant_id=f"{request.deck_id}/commander-denial/{request.additional_commander_tax}",
                additional_commander_tax=request.additional_commander_tax,
                suppress_commander_synergy=request.suppress_commander_synergy,
            )
            metrics, _ = run_paired_structural_comparison(
                baseline=baseline, variant=variant,
                opponents=tuple(self._deck(x) for x in request.opponent_deck_ids),
                iterations=request.iterations, seed=request.seed,
                pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                max_turns=request.max_turns, pair_id=f"denial-{request.deck_id}",
            )
            return {
                "additional_commander_tax": request.additional_commander_tax,
                "commander_synergy_suppressed": request.suppress_commander_synergy,
                "comparison": metrics.as_dict(),
                "commander_dependency_penalty": -metrics.placement_improvement,
            }
        return self._invoke("run_commander_denial", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def run_holdout(self, request: HoldoutInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations * len(request.holdout_pods), request.approval_token)
            baseline, variant, swaps = self._build_variant(request)
            results = []
            for index, pod in enumerate(request.holdout_pods):
                opponents = tuple(self._deck(deck_id) for deck_id in pod)
                metrics, _ = run_paired_structural_comparison(
                    baseline=baseline, variant=variant, opponents=opponents,
                    iterations=request.iterations, seed=request.seed + index,
                    pilot_config=PilotConfig(strength=request.pilot_strength, mode=request.pilot_mode),
                    max_turns=request.max_turns, pair_id=f"holdout-{variant.deck_hash[:8]}-{index}",
                )
                results.append({"pod": pod, "comparison": metrics.as_dict()})
            improvements = [row["comparison"]["placement_improvement"] for row in results]
            return {
                "swaps": swaps,
                "holdouts": results,
                "mean_placement_improvement": fmean(improvements) if improvements else 0.0,
                "all_holdouts_nonnegative": all(value >= 0 for value in improvements),
            }
        return self._invoke("run_holdout", request, work, deck_ids=(request.deck_id,), seed=request.seed, iterations=request.iterations)

    def run_sensitivity(self, request: SensitivityInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            total = len(request.seeds) * len(request.pilot_strengths) * request.iterations
            self._check_iterations(total, request.approval_token)
            rows = []
            for seed in request.seeds:
                for strength in request.pilot_strengths:
                    match = MatchupBatchInput(
                        deck_ids=request.deck_ids,
                        seed=seed,
                        iterations=request.iterations,
                        workers=request.workers,
                        pilot_strength=strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                    )
                    response = self.run_matchup_batch(match)
                    rows.append({"seed": seed, "pilot_strength": strength.value, "aggregate": response.result.get("aggregate")})
            return {"runs": rows}
        return self._invoke("run_sensitivity", request, work, deck_ids=request.deck_ids, iterations=request.iterations)

    def recommend_upgrades(self, request: RecommendUpgradesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            cuts = [
                card for card in sorted(deck.cards, key=profile_score)
                if card.oracle_name not in deck.commander_names
                and not card.is_land
                and not self._is_protected(request.deck_id, card.oracle_name)
            ][: max(16, request.max_recommendations)]
            candidate_ids = request.candidate_ids or tuple(
                candidate_id for candidate_id, candidate in self.candidates.items()
                if not candidate.allowed_deck_ids or request.deck_id in candidate.allowed_deck_ids
            )
            recommendations = []
            for cut in cuts:
                for candidate_id in candidate_ids:
                    candidate = self._candidate(candidate_id, request.deck_id)
                    raw_delta = profile_score(candidate.card) - profile_score(cut)
                    overlap = candidate.card.roles & cut.roles
                    lost_roles = cut.roles - candidate.card.roles
                    critical_roles = {
                        "graveyard_hate", "removal", "counter", "protection", "wipe", "recursion"
                    }
                    critical_loss = sum(role.value in critical_roles for role in lost_roles)
                    compatibility_adjustment = (
                        1.5 * len(overlap)
                        - 0.5 * len(lost_roles)
                        - 3.0 * critical_loss
                        - (0.75 if not overlap else 0.0)
                    )
                    inference_penalty = 2.5 if candidate_id.startswith("inventory/") else 0.0
                    delta = raw_delta + compatibility_adjustment - inference_penalty
                    role_gain = sorted(role.value for role in candidate.card.roles - cut.roles)
                    role_loss = sorted(role.value for role in lost_roles)
                    recommendations.append({
                        "remove": cut.oracle_name,
                        "add": candidate.card.oracle_name,
                        "candidate_id": candidate_id,
                        "screening_delta": delta,
                        "raw_profile_delta": raw_delta,
                        "role_compatibility_adjustment": compatibility_adjustment,
                        "screening_uncertainty_penalty": inference_penalty,
                        "semantic_quality": ("keyword_inferred_structural_only" if inference_penalty else "curated_structural_profile"),
                        "role_gain": role_gain,
                        "role_loss": role_loss,
                        "physical_status": candidate.physical_status,
                        "requires_paired_validation": True,
                    })
            recommendations.sort(key=lambda row: row["screening_delta"], reverse=True)
            return {
                "method": "role_profile_screening_only",
                "recommendations": recommendations[: request.max_recommendations],
                "warning": "Candidates are not confirmed until paired and holdout validation pass.",
            }
        return self._invoke("recommend_upgrades", request, work, deck_ids=(request.deck_id,))


    def _meta_kb(self) -> MetaKnowledgeBase:
        return MetaKnowledgeBase(self.root)

    def _package_extractor(self) -> ArchetypePackageExtractor:
        return ArchetypePackageExtractor(self.root)

    def _stage_meta_record(self, filename: str, payload: dict[str, Any]) -> Path:
        target = self.root / "data/meta/provenance" / filename
        existing = []
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
        if not isinstance(existing, list):
            existing = [existing]
        existing.append(payload)
        atomic_write_json(target, existing)
        return target

    def _primer_compiler(self) -> PrimerToPilotCompiler:
        return PrimerToPilotCompiler(self.root)

    def _project_path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if self.root not in path.parents and path != self.root:
            raise ToolExecutionError("path escapes project root")
        return path

    def _load_primer_rules(self, relative: str) -> tuple[PilotRule, ...]:
        path = self._project_path(relative)
        if not path.exists():
            raise ToolExecutionError(f"pilot rule file missing: {relative}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rules", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ToolExecutionError(f"pilot rule file must contain a list: {relative}")
        return tuple(PilotRule.model_validate(row) for row in rows)

    def import_primer(self, request: ImportPrimerInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            document = self._primer_compiler().import_primer(
                source_path=request.source_path,
                primer_id=request.primer_id,
                source_id=request.source_id,
                title=request.title,
                commander=request.commander,
                deck_hash=request.deck_hash,
                format_band=request.format_band,
                primer_format=request.primer_format,
                license_notes=request.license_notes,
            )
            return {
                "primer": document.model_dump(mode="json"),
                "automatic_execution": False,
                "automatic_deck_application": False,
            }
        return self._invoke("import_primer", request, work)

    def extract_primer_rules(self, request: ExtractPrimerRulesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            compiler = self._primer_compiler()
            registry = compiler.load_registry()
            document = next((item for item in registry.primers if item.primer_id == request.primer_id), None)
            if document is None or document.source_path is None:
                raise ToolExecutionError(f"registered primer not found: {request.primer_id}")
            content = self._project_path(document.source_path).read_text(encoding="utf-8")
            rules = compiler.extract_rules(document, content=content)
            output_name = request.output_name or f"{request.primer_id}-automatic-candidates.json"
            target = self.root / "data/primer_rules/rules" / output_name
            atomic_write_json(target, {
                "rules": [rule.model_dump(mode="json") for rule in rules],
                "status": "needs_review",
                "automatic_deck_application": False,
            })
            return {
                "rules_path": str(target.relative_to(self.root)),
                "rule_count": len(rules),
                "active_rule_count": 0,
                "manual_review_required": True,
                "automatic_deck_application": False,
            }
        return self._invoke("extract_primer_rules", request, work)

    def validate_pilot_rules(self, request: ValidatePilotRulesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            rules = self._load_primer_rules(request.rules_path)
            report = self._primer_compiler().validate_rules(
                rules, commander=request.commander, deck_hash=request.deck_hash, format_band=request.format_band
            )
            return {"validation": report.model_dump(mode="json"), "automatic_deck_application": False}
        return self._invoke("validate_pilot_rules", request, work)

    def compile_pilot_policy(self, request: CompilePilotPolicyInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            rules = tuple(rule for path in request.rule_paths for rule in self._load_primer_rules(path))
            compiler = self._primer_compiler()
            policy = compiler.compile_policy(
                policy_id=request.policy_id, version=request.version, commander=request.commander,
                deck_hash=request.deck_hash, format_band=request.format_band,
                base_pilot_name=request.base_pilot_name, rules=rules,
                conflict_strategy=request.conflict_strategy,
            )
            path = compiler.write_policy(policy, request.output_name)
            return {
                "policy_path": str(path.relative_to(self.root)),
                "policy": policy.model_dump(mode="json"),
                "automatic_deck_application": False,
                "base_pilot_mutated": False,
            }
        return self._invoke("compile_pilot_policy", request, work)

    def compare_policy_versions(self, request: ComparePolicyVersionsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            older = CompiledPilotPolicy.model_validate_json(self._project_path(request.older_policy_path).read_text(encoding="utf-8"))
            newer = CompiledPilotPolicy.model_validate_json(self._project_path(request.newer_policy_path).read_text(encoding="utf-8"))
            return self._primer_compiler().compare_policy_versions(older, newer)
        return self._invoke("compare_policy_versions", request, work)

    def run_policy_eval(self, request: RunPolicyEvalInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            policy = CompiledPilotPolicy.model_validate_json(self._project_path(request.policy_path).read_text(encoding="utf-8"))
            payload = json.loads(self._project_path(request.scenario_path).read_text(encoding="utf-8"))
            rows = payload.get("scenarios", payload) if isinstance(payload, dict) else payload
            parsed_scenarios = tuple(PolicyEvalScenario.model_validate(row) for row in rows)
            scenarios = tuple(
                scenario for scenario in parsed_scenarios
                if scenario.commander == policy.commander
                and scenario.deck_hash == policy.deck_hash
                and scenario.format_band == policy.format_band
            )
            if not scenarios:
                raise ToolExecutionError("scenario file contains no entries compatible with the selected policy")
            deck = self._deck(request.deck_id)
            pilot = build_pilot(PilotConfig(pilot_name=policy.base_pilot_name), strategy=request.strategy)
            results = self._primer_compiler().evaluate_policy(
                base_pilot=pilot, policy=policy, scenarios=scenarios,
                deck_cards=tuple(card.oracle_name for card in deck.cards), seed=request.seed,
            )
            target = self.root / "data/primer_rules/evals" / request.output_name
            atomic_write_json(target, {
                "policy_id": policy.policy_id,
                "results": [result.model_dump(mode="json") for result in results],
                "improved_count": sum(result.improved for result in results),
                "overlay_correct_count": sum(result.overlay_correct for result in results),
                "scenario_count": len(results),
                "automatic_deck_application": False,
            })
            return {
                "eval_path": str(target.relative_to(self.root)),
                "scenario_count": len(results),
                "improved_count": sum(result.improved for result in results),
                "overlay_correct_count": sum(result.overlay_correct for result in results),
                "automatic_deck_application": False,
            }
        return self._invoke("run_policy_eval", request, work)

    def generate_primer_conflict_report(self, request: GeneratePrimerConflictReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            rules = tuple(rule for path in request.rule_paths for rule in self._load_primer_rules(path))
            conflicts = self._primer_compiler().detect_conflicts(rules)
            target = self.root / "data/primer_rules/conflicts" / request.output_name
            atomic_write_json(target, {
                "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
                "conflict_count": len(conflicts),
                "resolution": "manual_or_explicit_strategy_required",
                "automatic_deck_application": False,
            })
            return {
                "report_path": str(target.relative_to(self.root)),
                "conflict_count": len(conflicts),
                "automatic_merge": False,
            }
        return self._invoke("generate_primer_conflict_report", request, work)

    def import_meta_deck(self, request: ImportMetaDeckInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            # Validate via the production snapshot model; write only to data/meta/provenance.
            deck = MetaDeckSnapshot(
                source_id=request.source_id,
                commander=request.commander,
                deck_hash=stable_deck_hash(request.decklist),
                retrieved_at=datetime.now(UTC),
                format_band=request.format_band,
                categories=request.categories,
                pod_size=request.pod_size,
                budget_band=BudgetBand(request.budget_band),
                event_name=request.event_name,
                placement=request.placement,
                player_count=request.player_count,
                decklist=request.decklist,
                provenance={"imported_by_tool": True, "source_path": request.snapshot_path},
            )
            path = self._stage_meta_record("staged_meta_decks.json", deck.model_dump(mode="json"))
            return {"staged_path": str(path.relative_to(self.root)), "deck_hash": deck.deck_hash, "automatic_deck_application": False}
        return self._invoke("import_meta_deck", request, work, estimate_type="structural_model_estimates")

    def import_tournament_result(self, request: ImportTournamentResultInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = TournamentResult(
                source_id=request.source_id,
                event_name=request.event_name,
                format_band=request.format_band,
                pod_size=request.pod_size,
                placement=request.placement,
                player_count=request.player_count,
            )
            path = self._stage_meta_record("staged_tournament_results.json", result.model_dump(mode="json"))
            return {"staged_path": str(path.relative_to(self.root)), "automatic_deck_application": False}
        return self._invoke("import_tournament_result", request, work)

    def import_primer_reference(self, request: ImportPrimerReferenceInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            primer = PrimerReference(
                source_id=request.source_id,
                commander=request.commander,
                title=request.title,
                key_points=request.key_points,
                categories=request.categories,
                evidence_quality=MetaEvidenceRating.ESTABLISHED_PRIMER,
                transfer_limitations=("Primer notes are advisory only and never update decklists automatically.",),
            )
            path = self._stage_meta_record("staged_primer_references.json", primer.model_dump(mode="json"))
            return {"staged_path": str(path.relative_to(self.root)), "automatic_deck_application": False}
        return self._invoke("import_primer_reference", request, work)

    def create_meta_snapshot(self, request: CreateMetaSnapshotInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            kb = self._meta_kb()
            seed_path = self.root / request.seed_file
            if not seed_path.exists():
                raise ToolExecutionError(f"meta seed file missing: {request.seed_file}")
            out_path = kb.snapshot_path(request.snapshot_id)
            if out_path.exists() and not request.allow_overwrite:
                raise ToolExecutionError(f"immutable snapshot already exists: {request.snapshot_id}")
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
            sources = tuple(MetaSource.model_validate(x) for x in payload.get("sources", []))
            decks = tuple(MetaDeckSnapshot.model_validate(x) for x in payload.get("deck_snapshots", []))
            tournaments = tuple(TournamentResult.model_validate(x) for x in payload.get("tournament_results", []))
            primers = tuple(PrimerReference.model_validate(x) for x in payload.get("primer_references", []))
            from commander_lab.models import MetaArchetype, MetaPackage
            archetypes = tuple(MetaArchetype.model_validate(x) for x in payload.get("archetypes", []))
            packages = tuple(MetaPackage.model_validate(x) for x in payload.get("packages", []))
            snapshot = kb.create_snapshot(
                snapshot_id=request.snapshot_id,
                sources=sources,
                deck_snapshots=decks,
                tournament_results=tournaments,
                primer_references=primers,
                archetypes=archetypes,
                packages=packages,
                notes=payload.get("notes"),
            )
            if out_path.exists() and request.allow_overwrite:
                out_path.rename(out_path.with_suffix(".superseded-local.json"))
            path = kb.write_snapshot(snapshot)
            return {
                "snapshot_id": snapshot.manifest.snapshot_id,
                "path": str(path.relative_to(self.root)),
                "source_count": len(snapshot.sources),
                "deck_snapshot_count": len(snapshot.deck_snapshots),
                "primer_count": len(snapshot.primer_references),
                "archetype_count": len(snapshot.archetypes),
                "card_frequency_count": len(snapshot.card_frequencies),
                "automatic_deck_application": False,
            }
        return self._invoke("create_meta_snapshot", request, work)

    def query_meta_cards(self, request: QueryMetaCardsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._meta_kb().query_cards(request.commander, request.format_band, request.min_frequency)
        return self._invoke("query_meta_cards", request, work)

    def query_meta_packages(self, request: QueryMetaPackagesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._meta_kb().query_packages(request.commander, request.category)
        return self._invoke("query_meta_packages", request, work)

    def compare_deck_to_meta(self, request: CompareDeckToMetaInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            cards = tuple(card.oracle_name for card in deck.cards if card.oracle_name not in deck.commander_names)
            result = self._meta_kb().compare_deck_to_meta(cards, commander=request.commander, format_band=request.format_band)
            result["local_deck_id"] = request.deck_id
            result["local_deck_hash"] = deck.deck_hash
            if request.deck_id in {"korvold/current", "rogshai/current"}:
                package_result = self._package_extractor().packages_for_deck(
                    request.deck_id, include_machine_candidates=True
                )
                result["local_package_evaluations"] = package_result["evaluations"]
                result["machine_package_candidates"] = package_result["machine_candidates"]
            result["automatic_deck_application"] = False
            return result
        return self._invoke("compare_deck_to_meta", request, work, deck_ids=(request.deck_id,))

    def compare_meta_periods(self, request: CompareMetaPeriodsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._meta_kb().compare_periods(request.older_snapshot_id, request.newer_snapshot_id, commander=request.commander)
        return self._invoke("compare_meta_periods", request, work)

    def generate_meta_report(self, request: GenerateMetaReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            snapshot = self._meta_kb().load_snapshot()
            lines = [
                "# Meta Knowledge Base Report",
                "",
                f"Snapshot: `{snapshot.manifest.snapshot_id}`",
                f"Sources: {len(snapshot.sources)}",
                f"Deck snapshots: {len(snapshot.deck_snapshots)}",
                f"Primer references: {len(snapshot.primer_references)}",
                f"Archetypes: {len(snapshot.archetypes)}",
                "",
                "## Transfer policy",
                "",
                "Meta records are evidence only. They do not replace decklists, inventory, allocation, or local-opponent data.",
                "cEDH records are structure, package, sequencing and interaction benchmarks unless a matching local context is explicitly established.",
                "",
                "## Sources",
            ]
            for source in snapshot.sources:
                lines.append(f"- `{source.source_id}` — {source.title} ({source.evidence_quality})")
            lines.append("\n## Small-sample flags")
            for freq in snapshot.card_frequencies:
                if freq.small_sample:
                    lines.append(f"- {freq.commander} / {freq.format_band}: sample_size={freq.sample_size}")
            target = self.root / "data/runs/meta_reports" / request.output_name
            atomic_write_text(target, "\n".join(lines) + "\n")
            return {"report_path": str(target.relative_to(self.root)), "snapshot_id": snapshot.manifest.snapshot_id, "automatic_deck_application": False}
        return self._invoke("generate_meta_report", request, work)

    def extract_archetypes(self, request: ExtractArchetypesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._package_extractor().extract_archetypes(request.deck_id).model_dump(mode="json")
        return self._invoke("extract_archetypes", request, work, deck_ids=(request.deck_id,))

    def extract_packages(self, request: ExtractPackagesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._package_extractor().packages_for_deck(
                request.deck_id, include_machine_candidates=request.include_machine_candidates
            )
        return self._invoke("extract_packages", request, work, deck_ids=(request.deck_id,))

    def inspect_package(self, request: InspectPackageInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            extractor = self._package_extractor()
            package = extractor.inspect(request.package_id, request.version)
            payload = {"package": package.model_dump(mode="json"), "automatic_deck_application": False}
            if request.deck_id:
                payload["evaluation"] = extractor.evaluate(
                    request.deck_id, request.package_id, version=request.version
                ).model_dump(mode="json")
            return payload
        return self._invoke("inspect_package", request, work, deck_ids=((request.deck_id,) if request.deck_id else ()))

    def compare_package_versions(self, request: ComparePackageVersionsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._package_extractor().compare_versions(
                request.package_id, request.older_version, request.newer_version
            ).model_dump(mode="json")
        return self._invoke("compare_package_versions", request, work)

    def evaluate_package_density(self, request: EvaluatePackageDensityInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._package_extractor().evaluate(
                request.deck_id, request.package_id, version=request.version
            ).model_dump(mode="json")
        return self._invoke("evaluate_package_density", request, work, deck_ids=(request.deck_id,))

    def detect_orphaned_cards(self, request: DetectOrphanedCardsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            return self._package_extractor().detect_orphans(request.deck_id)
        return self._invoke("detect_orphaned_cards", request, work, deck_ids=(request.deck_id,))

    def generate_package_report(self, request: GeneratePackageReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            report = self._package_extractor().generate_report(request.deck_id)
            target = self.root / "data/runs/package_reports" / request.output_name
            atomic_write_text(target, report)
            return {
                "report_path": str(target.relative_to(self.root)),
                "automatic_deck_application": False,
                "estimate_type": "structural_model_estimates",
            }
        return self._invoke("generate_package_report", request, work, deck_ids=(request.deck_id,))




    def create_opponent_ensemble(self, request: CreateOpponentEnsembleInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            ensemble=OpponentEnsemble.model_validate_json(self._project_path(request.source_path).read_text(encoding="utf-8")); path=self._opponent_ensembles().save(ensemble)
            return {"ensemble_id":ensemble.ensemble_id,"path":str(path.relative_to(self.root)),"variant_count":len(ensemble.variants),"automatic_profile_overwrite":False}
        return self._invoke("create_opponent_ensemble", request, work)

    def add_opponent_variant(self, request: AddOpponentVariantInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            variant=OpponentVariant.model_validate_json(self._project_path(request.variant_path).read_text(encoding="utf-8")); e=self._opponent_ensembles().add_variant(request.ensemble_id,variant,request.new_ensemble_id)
            return {"ensemble_id":e.ensemble_id,"version":e.version,"variant_count":len(e.variants),"automatic_profile_overwrite":False}
        return self._invoke("add_opponent_variant", request, work)

    def validate_ensemble(self, request: ValidateEnsembleInput) -> ToolResponse:
        return self._invoke("validate_ensemble", request, lambda:self._opponent_ensembles().validate(request.ensemble_id))

    def run_ensemble_matchups(self, request: RunEnsembleMatchupsInput) -> ToolResponse:
        def work() -> dict[str, Any]: return self._opponent_ensembles().run_matchups(self._deck(request.deck_id),request.ensemble_id,request.seed).model_dump(mode="json")
        return self._invoke("run_ensemble_matchups",request,work,deck_ids=(request.deck_id,),seed=request.seed,estimate_type="structural_model_estimates")

    def compare_variant_sensitivity(self, request: CompareVariantSensitivityInput) -> ToolResponse:
        return self._invoke("compare_variant_sensitivity",request,lambda:self._opponent_ensembles().compare_sensitivity(self._deck(request.deck_id),request.ensemble_id,request.seed),deck_ids=(request.deck_id,),seed=request.seed)

    def evaluate_robust_upgrade(self, request: EvaluateRobustUpgradeInput) -> ToolResponse:
        def work() -> dict[str, Any]: return self._opponent_ensembles().evaluate_robust_upgrade(self._deck(request.baseline_deck_id),self._deck(request.candidate_deck_id),request.ensemble_id,request.seed)
        return self._invoke("evaluate_robust_upgrade",request,work,deck_ids=(request.baseline_deck_id,request.candidate_deck_id),seed=request.seed)

    def generate_ensemble_report(self, request: GenerateEnsembleReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            target=self.root/"data/opponent_ensembles"/Path(request.output_name).name; atomic_write_text(target,self._opponent_ensembles().report(request.ensemble_id)); return {"report_path":str(target.relative_to(self.root)),"ensemble_id":request.ensemble_id,"automatic_profile_overwrite":False}
        return self._invoke("generate_ensemble_report",request,work)

    def trace_artifact_provenance(self, request: TraceArtifactProvenanceInput) -> ToolResponse:
        return self._invoke("trace_artifact_provenance", request, lambda: self._provenance().trace(request.artifact_id))

    def trace_recommendation_sources(self, request: TraceRecommendationSourcesInput) -> ToolResponse:
        return self._invoke("trace_recommendation_sources", request, lambda: self._provenance().recommendation_sources(request.recommendation_id))

    def list_superseded_sources(self, request: ListSupersededSourcesInput) -> ToolResponse:
        return self._invoke("list_superseded_sources", request, lambda: {"supersessions": self._provenance().list_superseded(), "historical_sources_retained": True})

    def verify_source_hash(self, request: VerifySourceHashInput) -> ToolResponse:
        return self._invoke("verify_source_hash", request, lambda: self._provenance().verify_source_hash(request.source_id, request.candidate_path))

    def generate_provenance_report(self, request: GenerateProvenanceReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            store=self._provenance(); graph=store.load(); store.validate(graph); audit=store.audit_claims()
            target=self.root/"data/runs/provenance_reports"/Path(request.output_name).name
            lines=["# Provenance Report","",f"Graph: `{graph.graph_id}`",f"Sources: {len(graph.sources)}",f"Artifacts: {len(graph.artifacts)}",f"Derived records: {len(graph.derived_data)}",f"Transformations: {len(graph.transformations)}",f"Citations: {len(graph.citations)}",f"Supersessions: {len(graph.supersessions)}","",f"Unreferenced claims: {len(audit['unreferenced_claims'])}","","Historical sources are retained and superseded records remain traceable."]
            atomic_write_text(target,"\n".join(lines)+"\n")
            return {"report_path":str(target.relative_to(self.root)),"graph_hash":sha256_value(graph.model_dump(mode="json")),"audit":audit}
        return self._invoke("generate_provenance_report", request, work)

    def audit_unreferenced_claims(self, request: AuditUnreferencedClaimsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result=self._provenance().audit_claims()
            if request.fail_on_unreferenced and not result["passed"]:
                raise ToolExecutionError("unreferenced claims detected")
            return result
        return self._invoke("audit_unreferenced_claims", request, work)

    def generate_swap_matrix(self, request: SwapMatrixInput) -> ToolResponse:
        """Generate every requested cut/add cell, preserving invalid cells as evidence."""
        def work() -> dict[str, Any]:
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.add_candidate_ids)
            remove_cards = request.remove_cards or tuple(dict.fromkeys(
                card.oracle_name for card in baseline.cards
                if card.oracle_name not in baseline.commander_names
                and not self._is_protected(request.deck_id, card.oracle_name)
            ))
            cells = len(remove_cards) * len(candidate_ids)
            if cells > self.limits.max_swap_matrix_cells:
                raise ToolExecutionError(
                    f"swap matrix has {cells} cells; limit is {self.limits.max_swap_matrix_cells}"
                )
            if request.simulate_valid_cells:
                self._check_iterations(cells * request.iterations_per_cell, request.approval_token)
            rows: list[dict[str, Any]] = []
            valid_count = 0
            simulated_count = 0
            for remove in remove_cards:
                for candidate_id in candidate_ids:
                    row: dict[str, Any] = {
                        "remove": remove,
                        "candidate_id": candidate_id,
                        "status": "invalid",
                        "constraint_report": None,
                        "comparison": None,
                    }
                    try:
                        candidate = build_search_candidate(
                            baseline,
                            (self.models_variant_swap(remove, candidate_id),),
                            self.candidates,
                            constraints,
                            inventory=self.candidate_inventory,
                            verified_physical_names=self.verified_candidate_names,
                        )
                    except Exception as exc:
                        row["errors"] = [f"{type(exc).__name__}: {exc}"]
                        rows.append(row)
                        continue
                    row.update({
                        "add": candidate.additions[0].card.oracle_name,
                        "screening_score": candidate.screening_score,
                        "constraint_report": candidate.constraint_report.model_dump(mode="json"),
                        "structural_rationale": candidate.rationale,
                        "affected_matchups": candidate.affected_matchups,
                    })
                    if not candidate.constraint_report.valid:
                        rows.append(row)
                        continue
                    valid_count += 1
                    row["status"] = "screened_valid"
                    if request.simulate_valid_cells:
                        metrics, _ = self._paired_variant_metrics(
                            baseline=baseline,
                            variant=candidate.variant,
                            opponent_deck_ids=request.opponent_deck_ids,
                            iterations=request.iterations_per_cell,
                            seed=request.seed,
                            pilot_strength=request.pilot_strength,
                            pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            pair_id=f"matrix-{candidate.variant.deck_hash[:12]}",
                        )
                        row["comparison"] = metrics.as_dict()
                        row["status"] = "paired_screened"
                        simulated_count += 1
                    rows.append(row)
            rows.sort(
                key=lambda row: (
                    (row.get("comparison") or {}).get("placement_improvement", -99.0),
                    row.get("screening_score", -99.0),
                    row["remove"],
                    row["candidate_id"],
                ),
                reverse=True,
            )
            return {
                "matrix_complete": len(rows) == cells,
                "cells": cells,
                "valid_cells": valid_count,
                "simulated_cells": simulated_count,
                "rows": rows,
                "best_valid_cell": next((row for row in rows if row["status"] != "invalid"), None),
                "automatic_application": False,
            }
        return self._invoke(
            "generate_swap_matrix", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations_per_cell,
        )

    @staticmethod
    def models_variant_swap(remove: str, candidate_id: str):
        from commander_lab.models import VariantSwap
        return VariantSwap(remove=remove, add_candidate_id=candidate_id)

    def search_variants(self, request: SearchVariantsInput) -> ToolResponse:
        """Backward-compatible bounded local one-swap search with hard constraints."""
        local_request = LocalSearchInput(
            deck_id=request.deck_id,
            candidate_ids=request.candidate_ids,
            max_steps=1,
            cuts_per_step=request.max_cuts,
            opponent_deck_ids=request.opponent_deck_ids,
            seed=request.seed,
            iterations=request.iterations,
            workers=request.workers,
            pilot_strength=request.pilot_strength,
            pilot_mode=request.pilot_mode,
            max_turns=request.max_turns,
            approval_token=request.approval_token,
        )
        response = self.run_local_search(local_request)
        if response.status == ToolStatus.COMPLETED:
            path = response.result.get("path", [])
            response.result = {
                "searched": response.result.get("evaluated_neighbors", 0),
                "variants": path[: request.max_results],
                "search_method": "phase7_constrained_local_search",
                "automatic_application": False,
            }
        return response

    def run_local_search(self, request: LocalSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.max_steps * request.cuts_per_step * max(1, len(self._eligible_candidate_ids(request.deck_id, request.candidate_ids))) * request.iterations,
                request.approval_token,
            )
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            current = baseline
            cumulative_swaps: list[Any] = []
            used_candidates: set[str] = set()
            used_cuts: set[str] = set()
            path: list[dict[str, Any]] = []
            evaluated = 0
            for step in range(request.max_steps):
                cut_map = {
                    card.oracle_name: card for card in sorted(baseline.cards, key=profile_score)
                    if card.oracle_name not in baseline.commander_names
                    and card.oracle_name not in used_cuts
                    and not card.is_land
                    and not self._is_protected(request.deck_id, card.oracle_name)
                }
                cuts = list(cut_map.values())[: request.cuts_per_step]
                neighbors: list[tuple[float, SearchCandidate, dict[str, Any]]] = []
                for cut in cuts:
                    for candidate_id in candidate_ids:
                        if candidate_id in used_candidates:
                            continue
                        swaps = tuple(cumulative_swaps + [self.models_variant_swap(cut.oracle_name, candidate_id)])
                        try:
                            neighbor = build_search_candidate(
                                baseline, swaps, self.candidates, constraints,
                                inventory=self.candidate_inventory,
                                verified_physical_names=self.verified_candidate_names,
                                parent_variant_id=current.deck_id,
                            )
                        except Exception:
                            continue
                        if not neighbor.constraint_report.valid:
                            continue
                        metrics, _ = self._paired_variant_metrics(
                            baseline=current, variant=neighbor.variant,
                            opponent_deck_ids=request.opponent_deck_ids,
                            iterations=request.iterations, seed=request.seed + step,
                            pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            pair_id=f"local-{step}-{neighbor.variant.deck_hash[:10]}",
                        )
                        evaluated += 1
                        neighbors.append((metrics.placement_improvement, neighbor, metrics.as_dict()))
                if not neighbors:
                    break
                neighbors.sort(key=lambda row: (row[0], row[1].screening_score, row[1].variant.deck_hash), reverse=True)
                improvement, best, comparison = neighbors[0]
                if improvement <= 0:
                    break
                cumulative_swaps = list(best.swaps)
                used_candidates = {swap.add_candidate_id for swap in best.swaps}
                used_cuts = {swap.remove for swap in best.swaps}
                current = best.variant
                path.append({
                    "step": step + 1,
                    "swaps": [swap.model_dump(mode="json") for swap in best.swaps],
                    "comparison_to_parent": comparison,
                    "screening_score": best.screening_score,
                    "constraint_report": best.constraint_report.model_dump(mode="json"),
                    "structural_rationale": best.rationale,
                    "affected_matchups": best.affected_matchups,
                    "variant_deck_hash": best.variant.deck_hash,
                    "automatic_application": False,
                })
            return {
                "method": "constrained_local_search",
                "evaluated_neighbors": evaluated,
                "path": path,
                "best_variant": path[-1] if path else None,
                "automatic_application": False,
            }
        return self._invoke(
            "run_local_search", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def run_beam_search(self, request: BeamSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            estimated = request.depth * request.beam_width * request.max_cuts_per_node * max(1, len(candidate_ids))
            if estimated > self.limits.max_variants * 20:
                raise ToolExecutionError(f"beam expansion estimate {estimated} exceeds safety bound")
            self._check_iterations(min(estimated, self.limits.max_variants) * request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            beam: list[SearchCandidate] = []
            initial_swaps: tuple[Any, ...] = ()
            for depth in range(request.depth):
                parents: list[tuple[tuple[Any, ...], str | None]] = [
                    (node.swaps, node.variant.deck_id) for node in beam
                ] or [(initial_swaps, baseline.deck_id)]
                expanded: dict[str, SearchCandidate] = {}
                for parent_swaps, parent_id in parents:
                    used_cuts = {swap.remove for swap in parent_swaps}
                    used_candidates = {swap.add_candidate_id for swap in parent_swaps}
                    cut_map = {
                        card.oracle_name: card for card in sorted(baseline.cards, key=profile_score)
                        if card.oracle_name not in baseline.commander_names
                        and card.oracle_name not in used_cuts
                        and not card.is_land
                        and not self._is_protected(request.deck_id, card.oracle_name)
                    }
                    cuts = list(cut_map.values())[: request.max_cuts_per_node]
                    for cut in cuts:
                        for candidate_id in candidate_ids:
                            if candidate_id in used_candidates:
                                continue
                            swaps = tuple((*parent_swaps, self.models_variant_swap(cut.oracle_name, candidate_id)))
                            try:
                                node = build_search_candidate(
                                    baseline, swaps, self.candidates, constraints,
                                    inventory=self.candidate_inventory,
                                    verified_physical_names=self.verified_candidate_names,
                                    parent_variant_id=parent_id,
                                )
                            except Exception:
                                continue
                            if node.constraint_report.valid:
                                expanded[node.variant.deck_hash] = node
                candidates = sorted(
                    expanded.values(),
                    key=lambda node: (node.screening_score, node.variant.deck_hash),
                    reverse=True,
                )[: max(request.beam_width * 3, request.beam_width)]
                scored: list[tuple[float, SearchCandidate, dict[str, Any]]] = []
                for node in candidates:
                    metrics, _ = self._paired_variant_metrics(
                        baseline=baseline, variant=node.variant,
                        opponent_deck_ids=request.opponent_deck_ids,
                        iterations=request.iterations, seed=request.seed + depth,
                        pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        pair_id=f"beam-{depth}-{node.variant.deck_hash[:10]}",
                    )
                    scored.append((metrics.placement_improvement, node, metrics.as_dict()))
                scored.sort(key=lambda row: (row[0], row[1].screening_score, row[1].variant.deck_hash), reverse=True)
                beam = [row[1] for row in scored[: request.beam_width]]
                if not beam:
                    break
            final_rows = []
            for node in beam:
                metrics, pairs = self._paired_variant_metrics(
                    baseline=baseline, variant=node.variant,
                    opponent_deck_ids=request.opponent_deck_ids,
                    iterations=request.iterations, seed=request.seed,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    pair_id=f"beam-final-{node.variant.deck_hash[:10]}",
                )
                final_rows.append({
                    "swaps": [swap.model_dump(mode="json") for swap in node.swaps],
                    "comparison": metrics.as_dict(),
                    "worst_quartile_delta": self._worst_quartile(pairs),
                    "screening_score": node.screening_score,
                    "constraint_report": node.constraint_report.model_dump(mode="json"),
                    "structural_rationale": node.rationale,
                    "affected_matchups": node.affected_matchups,
                    "variant_deck_hash": node.variant.deck_hash,
                    "automatic_application": False,
                })
            final_rows.sort(key=lambda row: row["comparison"]["placement_improvement"], reverse=True)
            return {
                "method": "beam_search",
                "beam_width": request.beam_width,
                "depth": request.depth,
                "variants": final_rows,
                "automatic_application": False,
            }
        return self._invoke(
            "run_beam_search", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    @staticmethod
    def _worst_quartile(pairs: list[dict[str, Any]]) -> float:
        from commander_lab.optimization import worst_quartile_improvement
        return worst_quartile_improvement(pairs)

    def run_package_search(self, request: PackageSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            packages = list(request.packages)
            if request.registry_package_ids:
                from commander_lab.models import VariantSwap
                extractor = self._package_extractor()
                candidate_by_name = {
                    candidate.card.oracle_name: candidate_id
                    for candidate_id, candidate in self.candidates.items()
                    if candidate_id in candidate_ids
                }
                present_names = {card.oracle_name for card in baseline.cards}
                cuts = [
                    card for card in sorted(baseline.cards, key=profile_score)
                    if card.oracle_name not in baseline.commander_names
                    and not self._is_protected(request.deck_id, card.oracle_name)
                ]
                for package_id in request.registry_package_ids:
                    package_def = extractor.inspect(package_id)
                    if package_def.commander != extractor.commander_label(baseline):
                        raise ToolExecutionError(
                            f"registry package {package_id} is incompatible with {request.deck_id}"
                        )
                    missing = [
                        name for name in package_def.all_cards
                        if name not in present_names and name in candidate_by_name
                    ][: request.max_package_size]
                    if not missing:
                        continue
                    chosen_cuts = [card for card in cuts if card.oracle_name not in package_def.all_cards][:len(missing)]
                    if len(chosen_cuts) != len(missing):
                        continue
                    packages.append(CandidatePackage(
                        package_id=f"registry-{package_id}",
                        swaps=tuple(
                            VariantSwap(remove=cut.oracle_name, add_candidate_id=candidate_by_name[add])
                            for cut, add in zip(chosen_cuts, missing, strict=True)
                        ),
                        rationale=f"Package-aware completion candidate for {package_id}; not automatically applied.",
                    ))
            if not packages:
                singles = all_legal_single_swaps(
                    baseline, self.candidates, candidate_ids, constraints,
                    inventory=self.candidate_inventory,
                    verified_physical_names=self.verified_candidate_names,
                    protected=set(self.protected_cards.get(request.deck_id, [])),
                )[:12]
                seen: set[str] = set()
                for size in range(2, request.max_package_size + 1):
                    for combo in itertools.combinations(singles, size):
                        swaps = tuple(item.swaps[0] for item in combo)
                        if len({swap.remove for swap in swaps}) != size or len({swap.add_candidate_id for swap in swaps}) != size:
                            continue
                        key = sha256_value([swap.model_dump(mode="json") for swap in swaps])
                        if key in seen:
                            continue
                        seen.add(key)
                        packages.append(CandidatePackage(package_id=f"auto-{key[:10]}", swaps=swaps))
                        if len(packages) >= request.max_packages:
                            break
                    if len(packages) >= request.max_packages:
                        break
            self._check_iterations(len(packages) * request.iterations, request.approval_token)
            rows: list[dict[str, Any]] = []
            for package in packages[: request.max_packages]:
                try:
                    node = build_search_candidate(
                        baseline, package.swaps, self.candidates, constraints,
                        inventory=self.candidate_inventory,
                        verified_physical_names=self.verified_candidate_names,
                    )
                except Exception as exc:
                    rows.append({"package_id": package.package_id, "status": "invalid", "error": str(exc)})
                    continue
                if not node.constraint_report.valid:
                    rows.append({
                        "package_id": package.package_id,
                        "status": "constraint_failed",
                        "constraint_report": node.constraint_report.model_dump(mode="json"),
                    })
                    continue
                metrics, pairs = self._paired_variant_metrics(
                    baseline=baseline, variant=node.variant,
                    opponent_deck_ids=request.opponent_deck_ids,
                    iterations=request.iterations, seed=request.seed,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    pair_id=f"package-search-{node.variant.deck_hash[:10]}",
                )
                rows.append({
                    "package_id": package.package_id,
                    "package_rationale": package.rationale,
                    "status": "paired_screened",
                    "swaps": [swap.model_dump(mode="json") for swap in package.swaps],
                    "comparison": metrics.as_dict(),
                    "worst_quartile_delta": self._worst_quartile(pairs),
                    "constraint_report": node.constraint_report.model_dump(mode="json"),
                    "structural_rationale": node.rationale,
                    "affected_matchups": node.affected_matchups,
                    "automatic_application": False,
                })
            rows.sort(key=lambda row: (row.get("comparison") or {}).get("placement_improvement", -99), reverse=True)
            return {"method": "package_search", "packages": rows, "automatic_application": False}
        return self._invoke(
            "run_package_search", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def evaluate_pareto_front(self, request: ParetoFrontInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(len(request.variants) * (1 + len(request.holdout_pods)) * request.iterations, request.approval_token)
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            evaluated: list[OptimizationVariant] = []
            evidence: dict[str, Any] = {}
            for swaps in request.variants:
                node = build_search_candidate(
                    baseline, swaps, self.candidates, constraints,
                    inventory=self.candidate_inventory,
                    verified_physical_names=self.verified_candidate_names,
                )
                if not node.constraint_report.valid:
                    evaluated.append(OptimizationVariant(
                        variant_id=node.variant.deck_id, deck_id=baseline.deck_id,
                        deck_hash=node.variant.deck_hash, swaps=node.swaps,
                        structural_rationale=node.rationale,
                        affected_matchups=node.affected_matchups,
                        constraint_report=node.constraint_report,
                        screening_score=node.screening_score,
                        search_method="pareto_evaluation",
                    ))
                    continue
                variant, paired, holdouts, _ = self._evaluate_search_candidate(
                    baseline=baseline, candidate=node,
                    opponent_deck_ids=request.opponent_deck_ids,
                    holdout_pods=request.holdout_pods,
                    iterations=request.iterations, seed=request.seed,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns, search_method="pareto_evaluation",
                )
                evaluated.append(variant)
                evidence[variant.variant_id] = {"paired": paired, "holdouts": holdouts}
            front = pareto_front(evaluated)
            return {
                "objectives_are_maximized": True,
                "evaluated": [item.model_dump(mode="json") for item in evaluated],
                "pareto_front": [item.model_dump(mode="json") for item in front],
                "evidence": evidence,
                "automatic_application": False,
            }
        return self._invoke(
            "evaluate_pareto_front", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def estimate_shapley(self, request: ShapleyInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(len(request.card_names) * request.iterations, request.approval_token)
            deck = self._deck(request.deck_id)
            values = approximate_shapley_profile(
                deck, request.card_names, permutations=request.permutations, seed=request.seed
            )
            ablations: dict[str, Any] = {}
            for name in request.card_names:
                response = self.run_card_ablation(CardAblationInput(
                    deck_id=request.deck_id, card_name=name,
                    opponent_deck_ids=request.opponent_deck_ids,
                    seed=request.seed, iterations=request.iterations,
                    workers=1, pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode, max_turns=request.max_turns,
                    approval_token=request.approval_token,
                ))
                ablations[name] = response.result if response.status == ToolStatus.COMPLETED else {"errors": response.errors}
            return {
                "method": "permutation_profile_shapley_with_paired_single_card_ablation",
                "permutations": request.permutations,
                "contributions": values,
                "paired_ablation_evidence": ablations,
                "warning": "Shapley values are approximate structural contribution estimates, not causal real-game values.",
            }
        return self._invoke(
            "estimate_shapley", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def validate_upgrade(self, request: ValidateUpgradeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            sensitivity_runs = len(request.sensitivity_seeds) * len(request.sensitivity_strengths)
            total = request.iterations * (1 + len(request.holdout_pods) + sensitivity_runs)
            self._check_iterations(total, request.approval_token)
            baseline, variant, swap_rows = self._build_variant(request)
            constraints = self._optimization_constraints(request.deck_id)
            report = evaluate_constraints(
                variant, constraints,
                candidate_inventory=self.candidate_inventory,
                added_card_names=tuple(row["add"] for row in swap_rows),
                verified_physical_names=self.verified_candidate_names,
            )
            metrics, pairs = self._paired_variant_metrics(
                baseline=baseline, variant=variant,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations, seed=request.seed,
                pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                max_turns=request.max_turns,
                pair_id=f"validate-{variant.deck_hash[:10]}",
            )
            holdouts = self._holdout_improvements(
                baseline=baseline, variant=variant,
                holdout_pods=request.holdout_pods if request.require_holdout else (),
                iterations=request.iterations, seed=request.seed,
                pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                max_turns=request.max_turns,
            )
            sensitivity: list[dict[str, Any]] = []
            for seed in request.sensitivity_seeds:
                for strength in request.sensitivity_strengths:
                    sensitive_metrics, _ = self._paired_variant_metrics(
                        baseline=baseline, variant=variant,
                        opponent_deck_ids=request.opponent_deck_ids,
                        iterations=request.iterations, seed=seed,
                        pilot_strength=strength, pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        pair_id=f"sensitivity-{variant.deck_hash[:8]}-{seed}-{strength.value}",
                    )
                    sensitivity.append({
                        "seed": seed,
                        "pilot_strength": strength.value,
                        "placement_improvement": sensitive_metrics.placement_improvement,
                        "place_1_share_delta": sensitive_metrics.place_1_share_delta,
                    })
            red_team = self._red_team_review(
                baseline=baseline, variant=variant, swaps=request.swaps,
                constraint_report=report, paired=metrics.as_dict(),
                holdouts=holdouts, sensitivity=sensitivity,
            )
            holdout_passed = all(
                row["comparison"]["placement_improvement"] >= 0 for row in holdouts
            ) if request.require_holdout else True
            sensitivity_passed = all(
                row["placement_improvement"] >= 0 for row in sensitivity
            ) if request.require_sensitivity_nonnegative else True
            passed = (
                report.valid
                and metrics.placement_improvement >= request.minimum_place_delta
                and holdout_passed
                and sensitivity_passed
                and (red_team["passed"] or not request.require_red_team_pass)
            )
            removed_cards = [
                next(card for card in baseline.cards if card.oracle_name == swap.remove)
                for swap in request.swaps
            ]
            added_cards = [self._candidate(swap.add_candidate_id, request.deck_id).card for swap in request.swaps]
            rationale = []
            matchups: set[str] = set()
            from commander_lab.optimization import card_matchup_tags, structural_rationale
            for remove, add in zip(removed_cards, added_cards, strict=True):
                rationale.extend(structural_rationale(remove, add))
                matchups.update(card_matchup_tags(remove) | card_matchup_tags(add))
            return {
                "decision": "confirmed" if passed else "rejected",
                "proposal_status": "validated_not_applied" if passed else "rejected_not_applied",
                "swaps": swap_rows,
                "structural_rationale": rationale,
                "affected_matchups": sorted(matchups),
                "constraint_report": report.model_dump(mode="json"),
                "paired_comparison": metrics.as_dict(),
                "pair_sample": pairs[:20],
                "holdout_tests": holdouts,
                "sensitivity_tests": sensitivity,
                "red_team_review": red_team,
                "criteria": {
                    "minimum_place_delta": request.minimum_place_delta,
                    "paired_passed": metrics.placement_improvement >= request.minimum_place_delta,
                    "holdout_passed": holdout_passed,
                    "sensitivity_passed": sensitivity_passed,
                    "red_team_passed": red_team["passed"],
                    "constraints_passed": report.valid,
                },
                "automatic_application": False,
                "canonical_deck_files_modified": False,
            }
        return self._invoke(
            "validate_upgrade", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def _read_optional_json(self, relative: str, default: Any) -> Any:
        path = self.root / relative
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _opponent_pod_for_size(self, requested: tuple[str, ...], pod_size: int) -> tuple[str, ...]:
        needed = pod_size - 1
        if needed < 1:
            raise ToolExecutionError("Commander robustness pods require at least two players")
        ordered: list[str] = []
        for deck_id in (*requested,
                        "opponent/morcant-elves", "opponent/cosmic-spiderman-midbudget",
                        "opponent/blight-curse-precon", "opponent/kaervek-reference",
                        "opponent/doom-prevails-precon", "opponent/dance-elements-precon",
                        "opponent/wakanda-forever-precon",
                        "synthetic/aggro", "synthetic/control", "synthetic/engine"):
            if deck_id in self.decks and deck_id not in ordered:
                ordered.append(deck_id)
        if len(ordered) < needed:
            raise ToolExecutionError(f"not enough structural opponents for pod size {pod_size}")
        return tuple(ordered[:needed])

    def _politics_pod_sensitivity(
        self, *, baseline: StructuralDeckProfile, variant: StructuralDeckProfile,
        opponent_deck_ids: tuple[str, ...], pod_sizes: tuple[int, ...],
        seed: int, iterations: int, max_turns: int, profile_name: str,
        include_politics: bool = True,
    ) -> list[dict[str, Any]]:
        politics = POLITICS_REGIMES if include_politics else ("rational_threat_focus",)
        sample_iterations = max(1, min(3, iterations))
        rows: list[dict[str, Any]] = []
        for pod_size in pod_sizes:
            opponents = self._opponent_pod_for_size(opponent_deck_ids, pod_size)
            for regime in politics:
                config = pilot_config_for(profile_name, regime)
                metrics, _ = run_paired_structural_comparison(
                    baseline=baseline, variant=variant,
                    opponents=tuple(self._deck(deck_id) for deck_id in opponents),
                    iterations=sample_iterations,
                    seed=seed + pod_size * 1000 + list(POLITICS_REGIMES).index(regime),
                    pilot_config=config, max_turns=max_turns,
                    pair_id=f"robust-{variant.deck_hash[:8]}-{pod_size}-{regime}",
                )
                rows.append({
                    "politics": regime, "pod_size": pod_size, "opponents": list(opponents),
                    "iterations": sample_iterations,
                    "placement_improvement": metrics.placement_improvement,
                    "place_1_share_delta": metrics.place_1_share_delta,
                    "confidence_interval": metrics.confidence_interval,
                    "validation_level": "structural_only",
                })
        return rows

    def _tactical_interaction_evidence(self, card_names: tuple[str, ...]) -> dict[str, Any]:
        wanted = {name for name in card_names if name}
        catalog = load_interaction_catalog(self.root / "data/rules/project_critical_interactions.json")
        selected = [case for case in catalog if wanted.intersection(case.cards)]
        if not selected:
            return {
                "execution_status": "not_run_no_relevant_case",
                "validation_level": "structural_only",
                "cases_attempted": 0, "cases_passed": 0, "cases_failed": 0,
                "interaction_ids": [],
            }
        oracle = TacticalRuleOracle()
        results = [oracle.validate(case) for case in selected]
        failed = [result for result in results if not result.passed]
        return {
            "execution_status": "passed" if not failed else "failed",
            "validation_level": "tactical_oracle",
            "cases_attempted": len(results),
            "cases_passed": len(results) - len(failed),
            "cases_failed": len(failed),
            "interaction_ids": [result.interaction_id for result in results],
            "mismatches": [m for result in failed for m in result.mismatches],
            "external_engine_claimed": False,
        }

    def _external_probe_status(self, provider: str) -> dict[str, Any]:
        manager = RulesEngineManager(root=self.root)
        try:
            adapter = manager.xmage if provider == "xmage" else manager.forge
            probe = adapter.probe()
            external = (
                probe.availability.value == "available"
                and probe.capabilities.runtime_kind == "external_rules_engine"
            )
            return {
                "provider": provider,
                "execution_status": "ready_for_real_call" if external else "blocked",
                "availability": probe.availability.value,
                "runtime_kind": probe.capabilities.runtime_kind,
                "backend_version": probe.backend_version,
                "details": list(probe.details),
            }
        finally:
            manager.close()

    def build_optimization_context(self, request: BuildOptimizationContextInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            requested = list(request.deck_ids)
            if request.include_kaervek and "kaervek/current" not in requested:
                requested.append("kaervek/current")
            available = [deck_id for deck_id in requested if deck_id in self.decks]
            unavailable = [deck_id for deck_id in requested if deck_id not in self.decks]
            coverage = self._read_optional_json("data/rules/card_rules_coverage.json", {})
            robustness = self._read_optional_json("data/robustness/pilot_and_politics_registry.json", {})
            engine = self._read_optional_json("artifacts/phase12_13/PHASE12_13_RESULT.json", {})
            canonical = self._read_optional_json("data/canonical_import/2026-08-07/deck_lists.json", {})
            return {
                "execution_status": "passed_with_limitations" if unavailable else "passed",
                "validation_level": "structural_only",
                "deck_priority": ["korvold/current", "rogshai/current", "kaervek/current"],
                "available_decks": {
                    deck_id: {
                        "deck_hash": self._deck(deck_id).deck_hash,
                        "commander_names": list(self._deck(deck_id).commander_names),
                        "protected_cards": sorted(self.protected_cards.get(deck_id, [])),
                    }
                    for deck_id in available
                },
                "unavailable_structural_decks": unavailable,
                "canonical_snapshot": {
                    "path": "data/canonical_import/2026-08-07/deck_lists.json",
                    "read_only": True,
                    "source_workbook": canonical.get("source_file") or canonical.get("source_workbook"),
                    "source_drive_id": canonical.get("source_drive_file_id") or canonical.get("source_drive_id"),
                },
                "candidate_cards": [
                    {
                        "candidate_id": candidate_id,
                        "oracle_name": candidate.card.oracle_name,
                        "physical_status": candidate.physical_status,
                        "allowed_deck_ids": list(candidate.allowed_deck_ids),
                    }
                    for candidate_id, candidate in sorted(self.candidates.items())
                ],
                "rules_coverage": {
                    "external_engine_execution_status": coverage.get("external_engine_execution_status", "blocked"),
                    "deck_statistics": coverage.get("deck_statistics", {}),
                },
                "pilot_profiles": [row.get("pilot_id") for row in robustness.get("pilot_profiles", [])],
                "politics_regimes": [row.get("regime_id") for row in robustness.get("politics_regimes", [])],
                "external_engine": {
                    "execution_status": engine.get("execution_status", "blocked"),
                    "completion_status": engine.get("completion_status", "external_engine_blocked"),
                    "observations": engine.get("external_rules_engine_observations", 0),
                },
                "basic_land_policy": "at_least_50_each_basic_type; not scarce within normal deck limits",
                "automatic_application": False,
                "canonical_files_modified": False,
            }
        return self._invoke("build_optimization_context", request, work, deck_ids=request.deck_ids)

    def generate_candidate_swaps(self, request: GenerateCandidateSwapsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            screened = self.recommend_upgrades(RecommendUpgradesInput(
                deck_id=request.deck_id,
                candidate_ids=request.candidate_ids,
                max_recommendations=request.max_candidates,
            ))
            if screened.status != ToolStatus.COMPLETED:
                raise ToolExecutionError("candidate screening failed")
            rows = []
            for row in screened.result.get("recommendations", []):
                rows.append({
                    **row,
                    "recommendation_status": "candidate_swap",
                    "validation_level": "structural_only",
                    "candidate_source": "verified local candidate registry",
                    "automatic_application": False,
                })
            return {
                "deck_id": request.deck_id,
                "deck_hash": self._deck(request.deck_id).deck_hash,
                "method": "whole_deck_role_package_and_profile_screening",
                "candidates": rows,
                "count": len(rows),
                "automatic_application": False,
            }
        return self._invoke("generate_candidate_swaps", request, work, deck_ids=(request.deck_id,))

    def generate_candidate_packages(self, request: GenerateCandidatePackagesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = self._package_extractor().packages_for_deck(
                request.deck_id, include_machine_candidates=True
            )
            candidates = []
            evaluations = {row["package_id"]: row for row in result.get("evaluations", [])}
            for package in result.get("curated_packages", []):
                evaluation = evaluations.get(package["package_id"], {})
                candidates.append({
                    "package_id": package["package_id"],
                    "name": package["name"],
                    "status": "candidate_swap" if evaluation.get("missing_core_cards") else "formally_valid",
                    "missing_core_cards": evaluation.get("missing_core_cards", []),
                    "density": evaluation.get("density", 0),
                    "failure_modes": package.get("failure_modes", []),
                    "automatic_application": False,
                })
            return {
                "deck_id": request.deck_id,
                "archetype_profile": result.get("archetype_profile"),
                "candidate_packages": candidates,
                "machine_candidates": result.get("machine_candidates", []),
                "machine_candidates_confirmed": False,
                "automatic_application": False,
            }
        return self._invoke("generate_candidate_packages", request, work, deck_ids=(request.deck_id,))

    def optimize_deck_against_meta(self, request: OptimizeDeckAgainstMetaInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            generated = self.generate_candidate_swaps(GenerateCandidateSwapsInput(
                deck_id=request.deck_id, max_candidates=request.max_candidates
            ))
            if generated.status != ToolStatus.COMPLETED:
                raise ToolExecutionError("candidate generation failed")
            validated = []
            for row in generated.result.get("candidates", [])[: request.max_candidates]:
                validation = self.validate_swap(ValidateSwapInput(
                    deck_id=request.deck_id,
                    swaps=(VariantSwap(remove=row["remove"], add_candidate_id=row["candidate_id"]),),
                    opponent_deck_ids=request.opponent_deck_ids,
                    seed=request.seed,
                    iterations=request.iterations,
                    workers=request.workers,
                    pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    approval_token=request.approval_token,
                    minimum_place_delta=0.0,
                ))
                validated.append(validation.result if validation.status == ToolStatus.COMPLETED else {
                    "candidate": row, "recommendation_status": "insufficient_evidence", "errors": validation.errors
                })
            ranked = sorted(
                validated,
                key=lambda item: (
                    item.get("recommendation_status") == "robust_in_structural_holdout",
                    item.get("paired_structural_effect", {}).get("placement_improvement", -999),
                ),
                reverse=True,
            )
            return {
                "deck_id": request.deck_id,
                "validation_level": "structural_only",
                "ranked_candidates": ranked,
                "external_engine_status": "blocked",
                "automatic_application": False,
            }
        return self._invoke(
            "optimize_deck_against_meta", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed, iterations=request.iterations,
        )

    def optimize_multiple_decks_with_allocation(self, request: OptimizeMultipleDecksWithAllocationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            priority = {"korvold/current": 3, "rogshai/current": 2, "kaervek/current": 1}
            rows = []
            for deck_id in request.deck_ids:
                if deck_id not in self.decks:
                    rows.append({"deck_id": deck_id, "status": "missing", "candidates": []})
                    continue
                response = self.generate_candidate_swaps(GenerateCandidateSwapsInput(
                    deck_id=deck_id, max_candidates=request.max_candidates_per_deck
                ))
                rows.append({"deck_id": deck_id, "status": "complete", "candidates": response.result.get("candidates", [])})
            claims: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                for candidate in row["candidates"]:
                    claims.setdefault(candidate["add"], []).append({"deck_id": row["deck_id"], **candidate})
            conflicts = []
            allocation = []
            for card_name, candidates in sorted(claims.items()):
                candidates.sort(key=lambda x: (priority.get(x["deck_id"], 0), x.get("screening_delta", 0)), reverse=True)
                winner = candidates[0]
                allocation.append({"card": card_name, "allocated_to": winner["deck_id"], "reason": "deck priority then structural screening"})
                if len(candidates) > 1:
                    conflicts.append({"card": card_name, "claims": [c["deck_id"] for c in candidates], "allocated_to": winner["deck_id"]})
            return {
                "deck_priority": ["korvold/current", "rogshai/current", "kaervek/current"],
                "deck_results": rows,
                "candidate_allocation": allocation,
                "conflicts": conflicts,
                "ungrounded_double_allocation": False,
                "canonical_allocation_modified": False,
                "automatic_application": False,
            }
        return self._invoke("optimize_multiple_decks_with_allocation", request, work, deck_ids=request.deck_ids)

    def validate_swap(self, request: ValidateSwapInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = self.validate_upgrade(ValidateUpgradeInput.model_validate(request.model_dump())).result
            paired = result.get("paired_comparison", {})
            criteria = result.get("criteria", {})
            baseline, variant, swaps = self._build_variant(request)
            strength_profile = request.pilot_strength.value
            robustness_rows = self._politics_pod_sensitivity(
                baseline=baseline, variant=variant,
                opponent_deck_ids=request.opponent_deck_ids, pod_sizes=(3, 4, 5),
                seed=request.seed, iterations=request.iterations, max_turns=request.max_turns,
                profile_name=strength_profile, include_politics=True,
            )
            politics_rows = [row for row in robustness_rows if row["pod_size"] == 4]
            pod_rows = []
            for pod_size in (3, 4, 5):
                values = [row["placement_improvement"] for row in robustness_rows if row["pod_size"] == pod_size]
                pod_rows.append({
                    "pod_size": pod_size, "scenario_count": len(values),
                    "mean_placement_improvement": fmean(values) if values else None,
                    "worst_case_placement_improvement": min(values) if values else None,
                })
            robustness_nonnegative = all(row["placement_improvement"] >= 0 for row in robustness_rows)
            dependency = {
                "baseline_dependency_penalty": self._commander_dependency_penalty(baseline),
                "variant_dependency_penalty": self._commander_dependency_penalty(variant),
            }
            dependency["delta"] = dependency["variant_dependency_penalty"] - dependency["baseline_dependency_penalty"]
            card_names = tuple(
                name for row in swaps for name in (row.get("remove"), row.get("add")) if name
            )
            tactical = self._tactical_interaction_evidence(card_names)
            xmage = self._external_probe_status("xmage")
            forge = self._external_probe_status("forge")
            if not criteria.get("constraints_passed", False):
                status = "rejected"
            elif request.iterations < 100:
                status = "insufficient_evidence"
            elif (criteria.get("paired_passed") and criteria.get("holdout_passed")
                  and criteria.get("sensitivity_passed") and robustness_nonnegative):
                status = "robust_in_structural_holdout"
            elif criteria.get("paired_passed"):
                status = "structurally_supported"
            else:
                status = "insufficient_evidence"
            remaining = []
            if not robustness_nonnegative:
                remaining.append("at least one politics/pod-size structural sensitivity is negative")
            if tactical["execution_status"] != "passed":
                remaining.append("no passing relevant Tactical Oracle case for every changed interaction")
            if xmage["execution_status"] != "ready_for_real_call":
                remaining.append("XMage external rules engine unavailable")
            if forge["execution_status"] != "ready_for_real_call":
                remaining.append("Forge external rules engine unavailable")
            return {
                "current_card": swaps[0].get("remove") if swaps else None,
                "candidate_card": swaps[0].get("add") if swaps else None,
                "deck_version": self._deck(request.deck_id).deck_hash,
                "inventory_version": "read-only-canonical-2026-08-07",
                "allocation_effect": "no canonical allocation change",
                "role_changes": result.get("structural_rationale", []),
                "package_changes": [],
                "mana_effect": "structural role/profile estimate",
                "mulligan_effect": "separate mulligan-policy gate required for policy-changing swaps",
                "paired_structural_effect": paired,
                "confidence_interval": paired.get("confidence_interval"),
                "holdout_effect": result.get("holdout_tests", []),
                "worst_case_effect": min(
                    [row.get("comparison", {}).get("placement_improvement", 0.0) for row in result.get("holdout_tests", [])]
                    + [row["placement_improvement"] for row in robustness_rows], default=0.0
                ),
                "pilot_sensitivity": result.get("sensitivity_tests", []),
                "opponent_sensitivity": result.get("holdout_tests", []),
                "politics_sensitivity": politics_rows,
                "pod_size_sensitivity": pod_rows,
                "commander_denial_effect": dependency,
                "tactical_oracle_result": tactical,
                "xmage_result": xmage,
                "forge_result": forge,
                "provider_disagreement": False,
                "rules_coverage": tactical["validation_level"],
                "failure_diagnosis": result.get("red_team_review", {}),
                "recommendation_status": status,
                "remaining_uncertainty": remaining,
                "raw_validation": result,
                "automatic_application": False,
            }
        return self._invoke(
            "validate_swap", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations,
        )

    def validate_package_change(self, request: ValidatePackageChangeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            package = self._package_extractor().inspect(request.package_id)
            evaluation = self._package_extractor().evaluate(request.deck_id, request.package_id)
            swaps = tuple(
                VariantSwap(remove=remove, add_candidate_id=add)
                for remove, add in zip(request.remove_cards, request.add_candidate_ids, strict=False)
            )
            validation = None
            if swaps:
                validation = self.validate_swap(ValidateSwapInput(
                    deck_id=request.deck_id, swaps=swaps, opponent_deck_ids=request.opponent_deck_ids,
                    seed=request.seed, iterations=request.iterations, workers=request.workers,
                    pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns, approval_token=request.approval_token,
                    minimum_place_delta=0.0,
                )).result
            return {
                "package": package.model_dump(mode="json"),
                "baseline_evaluation": evaluation.model_dump(mode="json"),
                "swap_validation": validation,
                "recommendation_status": validation.get("recommendation_status", "candidate_swap") if validation else "candidate_swap",
                "automatic_application": False,
            }
        return self._invoke("validate_package_change", request, work, deck_ids=(request.deck_id,), seed=request.seed, iterations=request.iterations)

    def validate_land_change(self, request: ValidateLandChangeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            removed = [swap.remove for swap in request.swaps]
            if not all(any(card.oracle_name == name and card.is_land for card in deck.cards) for name in removed):
                raise ToolExecutionError("validate_land_change requires land cuts")
            result = self.validate_swap(ValidateSwapInput.model_validate(request.model_dump())).result
            result["land_change_gate"] = "passed"
            return result
        return self._invoke("validate_land_change", request, work, deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations)

    def validate_mulligan_policy(self, request: ValidateMulliganPolicyInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            aliases = {"balanced": "current_pilot", "commander_plan": "commander_oriented"}
            policies = (aliases.get(request.baseline_policy, request.baseline_policy), aliases.get(request.candidate_policy, request.candidate_policy))
            response = self.compare_mulligan_policies(CompareMulliganPoliciesInput(
                deck_id=request.deck_id, policies=policies, samples=request.samples,
                followup_samples=min(250, request.samples), seed=request.seed,
            ))
            if response.status != ToolStatus.COMPLETED:
                raise ToolExecutionError("mulligan comparison failed")
            return {
                "validation_level": "structural_only",
                "policies": policies,
                "comparison": response.result,
                "recommendation_status": "structurally_supported",
                "automatic_application": False,
            }
        return self._invoke("validate_mulligan_policy", request, work, deck_ids=(request.deck_id,), seed=request.seed, iterations=request.samples)

    def run_rules_coverage_gate(self, request: RunRulesCoverageGateInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            registry = self._read_optional_json("data/rules/card_rules_coverage.json", {})
            cards = registry.get("cards", [])
            deck_token = request.deck_id.split("/")[0]
            selected = [row for row in cards if any(deck_token in version for version in row.get("deck_versions", []))]
            if request.card_names:
                wanted = set(request.card_names)
                selected = [row for row in selected if row.get("oracle_name") in wanted]
            statuses = Counter(row.get("coverage_status", "unsupported") for row in selected)
            external = all(row.get("xmage_rules_verified") or row.get("forge_rules_verified") for row in selected) if selected else False
            return {
                "deck_id": request.deck_id,
                "cards_checked": len(selected),
                "coverage_counts": dict(statuses),
                "external_engine_execution_status": registry.get("external_engine_execution_status", "blocked"),
                "external_gate_passed": external,
                "gate_status": "passed" if (external or not request.require_external) else "blocked",
                "highest_validation_level": "external_rules_engine" if external else ("tactical_oracle" if statuses.get("tactical_only") else "structural_only"),
                "unsupported_cards": [row.get("oracle_name") for row in selected if row.get("coverage_status") == "unsupported"],
            }
        return self._invoke("run_rules_coverage_gate", request, work, deck_ids=(request.deck_id,))

    def run_multifidelity_comparison(self, request: RunMultifidelityComparisonInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            structural = self.validate_swap(ValidateSwapInput.model_validate(
                request.model_dump(exclude={"include_tactical_oracle", "request_external_engine"})
            )).result
            cards = tuple(card for card in (structural.get("current_card"), structural.get("candidate_card")) if card)
            coverage = self.run_rules_coverage_gate(RunRulesCoverageGateInput(
                deck_id=request.deck_id, card_names=cards, require_external=request.request_external_engine,
            )).result
            tactical = (
                self._tactical_interaction_evidence(cards)
                if request.include_tactical_oracle
                else {"execution_status": "not_run", "validation_level": "structural_only"}
            )
            external_results: dict[str, Any] = {}
            if request.request_external_engine:
                for provider in ("xmage", "forge"):
                    external_results[provider] = self.run_engine_backed_matchup(RunEngineBackedMatchupInput(
                        deck_ids=(request.deck_id, *request.opponent_deck_ids),
                        provider=provider, seed=request.seed, iterations=1, workers=1,
                        pilot_strength=request.pilot_strength, pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns, approval_token=request.approval_token,
                    )).result
            status = structural.get("recommendation_status", "insufficient_evidence")
            if status == "robust_in_structural_holdout" and tactical.get("execution_status") == "passed":
                status = "tactical_oracle_supported"
            passed_external = [p for p, row in external_results.items() if row.get("execution_status") == "passed"]
            if status == "tactical_oracle_supported" and coverage.get("external_gate_passed") and passed_external:
                status = "external_engine_supported"
            if status == "external_engine_supported" and set(passed_external) == {"xmage", "forge"}:
                status = "provider_cross_checked"
            if status == "provider_cross_checked":
                status = "recommended_upgrade"
            return {
                "formal_gate": "passed" if structural.get("recommendation_status") != "rejected" else "failed",
                "structural_result": structural,
                "tactical_oracle_result": tactical,
                "external_rules_result": external_results if request.request_external_engine else {"execution_status": "not_run"},
                "coverage_gate": coverage,
                "recommendation_status": status,
                "evidence_ladder": [
                    "candidate_swap", "formally_valid", "structurally_supported",
                    "robust_in_structural_holdout", "tactical_oracle_supported",
                    "external_engine_supported", "provider_cross_checked", "recommended_upgrade",
                ],
                "automatic_application": False,
            }
        return self._invoke(
            "run_multifidelity_comparison", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations,
        )

    def run_engine_backed_matchup(self, request: RunEngineBackedMatchupInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            manager = RulesEngineManager(root=self.root)
            try:
                adapter = manager.xmage if request.provider == "xmage" else manager.forge
                probe = adapter.probe()
                if probe.availability.value != "available" or probe.capabilities.runtime_kind != "external_rules_engine":
                    return {
                        "execution_status": "blocked", "validation_level": "structural_only",
                        "provider": request.provider, "provider_status": probe.availability.value,
                        "runtime_kind": probe.capabilities.runtime_kind,
                        "reason": "; ".join(probe.details) or "external provider handshake unavailable",
                        "external_rules_engine_observations": 0,
                        "synthetic_or_tactical_substitution": False,
                    }
                rules_decks = load_project_rules_decks(self.root)
                missing = [deck_id for deck_id in request.deck_ids if deck_id not in rules_decks]
                if missing:
                    return {
                        "execution_status": "blocked", "validation_level": "structural_only",
                        "provider": request.provider, "provider_status": "available",
                        "reason": f"rules-engine deck exports missing for: {missing}",
                        "external_rules_engine_observations": 0,
                        "synthetic_or_tactical_substitution": False,
                    }
                observations = []
                for index in range(request.iterations):
                    handles = [adapter.load_deck(rules_decks[deck_id]) for deck_id in request.deck_ids]
                    game = adapter.start_commander_game(RulesGameRequest(
                        game_id=f"engine-backed-{request.provider}-{request.seed}-{index}",
                        deck_handles=tuple(handle.handle_id for handle in handles),
                        seed=request.seed + index,
                        starting_player_seat=index % len(handles),
                    ))
                    actions = adapter.get_legal_actions(game.session_id)
                    submitted = False
                    if actions:
                        action = actions[0]
                        adapter.submit_action(game.session_id, ActionProposal(
                            proposal_id=f"engine-backed-action-{index}", actor_id=action.actor_id,
                            legal_action_id=action.action_id, action_type=action.action_type,
                            policy_name="external_engine_acceptance",
                        ))
                        submitted = True
                    logs = adapter.get_logs(game.session_id)
                    replay = adapter.export_replay(game.session_id) if probe.capabilities.replay_supported else None
                    observations.append({
                        "game_id": game.game_id, "legal_action_count": len(actions),
                        "action_submitted": submitted, "event_count": len(logs.events),
                        "replay_exported": replay is not None,
                    })
                full = all(
                    row["legal_action_count"] > 0 and row["action_submitted"] and row["event_count"] > 0 and row["replay_exported"]
                    for row in observations
                )
                return {
                    "execution_status": "passed" if full else "passed_with_limitations",
                    "validation_level": "external_rules_engine",
                    "provider": request.provider, "provider_status": "available",
                    "runtime_kind": "external_rules_engine",
                    "external_rules_engine_observations": len(observations),
                    "observations": observations,
                    "synthetic_or_tactical_substitution": False,
                }
            except Exception as exc:
                return {
                    "execution_status": "failed", "validation_level": "structural_only",
                    "provider": request.provider, "provider_status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "external_rules_engine_observations": 0,
                    "synthetic_or_tactical_substitution": False,
                }
            finally:
                manager.close()
        return self._invoke(
            "run_engine_backed_matchup", request, work,
            deck_ids=request.deck_ids, seed=request.seed, iterations=request.iterations,
        )

    def run_robustness_suite(self, request: RunRobustnessSuiteInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            baseline, variant, _ = self._build_variant(request)
            profile_name = request.pilot_strength.value
            rows = self._politics_pod_sensitivity(
                baseline=baseline, variant=variant, opponent_deck_ids=request.opponent_deck_ids,
                pod_sizes=request.include_pod_sizes, seed=request.seed, iterations=request.iterations,
                max_turns=request.max_turns, profile_name=profile_name, include_politics=request.include_politics,
            )
            worst = min((row["placement_improvement"] for row in rows), default=0.0)
            mean = fmean(row["placement_improvement"] for row in rows) if rows else 0.0
            status = "robust_in_structural_holdout" if rows and worst >= 0 else "insufficient_evidence"
            return {
                "validation_level": "structural_only",
                "execution_status": "passed",
                "scenario_count": len(rows),
                "pod_sizes": list(request.include_pod_sizes),
                "politics_included": request.include_politics,
                "politics_regimes": list(POLITICS_REGIMES) if request.include_politics else ["rational_threat_focus"],
                "scenario_results": rows,
                "mean_effect": mean, "worst_case_effect": worst,
                "recommendation_status": status,
                "automatic_application": False,
            }
        return self._invoke(
            "run_robustness_suite", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed, iterations=request.iterations,
        )

    def rank_variants(self, request: RankVariantsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            def score(row: dict[str, Any]) -> tuple[float, float, float]:
                worst = float(row.get("worst_case_effect", -999.0) or 0.0)
                paired = float((row.get("paired_structural_effect") or {}).get("placement_improvement", row.get("effect_size", 0.0)) or 0.0)
                coverage = {"external_rules_engine": 3, "tactical_oracle": 2, "structural_only": 1}.get(row.get("rules_coverage"), 0)
                return (worst if request.prefer_worst_case else paired, paired, float(coverage))
            ranked = sorted((dict(row) for row in request.variants), key=score, reverse=True)
            p_rows = [(index, row.get("p_value")) for index, row in enumerate(ranked) if row.get("p_value") is not None]
            if p_rows:
                adjusted = holm_adjust(float(value) for _, value in p_rows)
                for (index, _), value in zip(p_rows, adjusted, strict=True):
                    ranked[index]["holm_adjusted_p_value"] = value
            for index, row in enumerate(ranked, start=1):
                row["rank"] = index
            return {
                "ranked_variants": ranked,
                "method": "worst_case_then_paired_then_coverage",
                "multiple_testing_method": "Holm family-wise correction when p-values are supplied",
                "automatic_application": False,
            }
        return self._invoke("rank_variants", request, work)

    def explain_recommendation(self, request: ExplainRecommendationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            evidence = request.evidence
            return {
                "recommendation_status": evidence.get("recommendation_status", "insufficient_evidence"),
                "summary": f"{evidence.get('current_card', 'current card')} → {evidence.get('candidate_card', 'candidate card')}",
                "why": evidence.get("role_changes", []),
                "tradeoffs": {
                    "worst_case_effect": evidence.get("worst_case_effect"),
                    "remaining_uncertainty": evidence.get("remaining_uncertainty", []),
                    "provider_disagreement": evidence.get("provider_disagreement", False),
                },
                "truth_boundary": "Structural results are model estimates; Tactical Oracle is not an external rules engine.",
                "automatic_application": False,
            }
        return self._invoke("explain_recommendation", request, work)

    def export_recommendation_evidence(self, request: ExportRecommendationEvidenceInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            target_dir = self.root / "data/runs/recommendations"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / Path(request.output_name).name
            atomic_write_json(target, {"schema_version": 1, "automatic_application": False, "evidence": request.evidence})
            return {"path": str(target), "sha256": sha256_value(request.evidence), "canonical_files_modified": False}
        return self._invoke("export_recommendation_evidence", request, work)

    def create_deck_improvement_report(self, request: CreateDeckImprovementReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            target = self.report_dir / Path(request.output_name).name
            lines = [
                f"# Deck improvement report — {request.deck_id}", "",
                "Validation boundary: structural model estimates unless an individual evidence item explicitly records a higher executed level.", "",
                "No deck, inventory, or allocation change was applied.", "",
            ]
            for index, item in enumerate(request.evidence_items, start=1):
                lines += [f"## Candidate {index}", "", f"- Status: `{item.get('recommendation_status', 'insufficient_evidence')}`", f"- Swap: `{item.get('current_card')}` → `{item.get('candidate_card')}`", f"- Worst-case effect: `{item.get('worst_case_effect')}`", f"- Rules coverage: `{item.get('rules_coverage', 'structural_only')}`", ""]
            atomic_write_text(target, "\n".join(lines))
            return {"report_path": str(target), "evidence_items": len(request.evidence_items), "automatic_application": False}
        return self._invoke("create_deck_improvement_report", request, work, deck_ids=(request.deck_id,))

    def create_report(self, request: CreateReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            safe_name = Path(request.output_name).name
            output = self.report_dir / safe_name
            lines = [
                f"# {request.title}",
                "",
                "All numerical simulation outputs are `structural_model_estimates`.",
                "",
                "## Evidence summary",
                "",
                "| # | Tool | Status | Invocation |",
                "|---:|---|---|---|",
            ]
            for index, response in enumerate(request.tool_responses, start=1):
                metadata = response.get("metadata", {})
                lines.append(
                    f"| {index} | {metadata.get('tool_name', 'unknown')} | "
                    f"{response.get('status', 'unknown')} | {metadata.get('invocation_id', '')} |"
                )
            decisions = [
                response.get("result", {}).get("decision")
                for response in request.tool_responses
                if response.get("result", {}).get("decision")
            ]
            if decisions:
                lines.extend(["", "## Validation decision", "", f"**{decisions[-1]}**", ""])
            for index, response in enumerate(request.tool_responses, start=1):
                lines.extend([
                    f"## Evidence {index}",
                    "",
                    "```json",
                    json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True),
                    "```",
                    "",
                ])
            output.write_text("\n".join(lines), encoding="utf-8")
            return {
                "report_path": str(output),
                "evidence_items": len(request.tool_responses),
                "decisions": decisions,
            }
        return self._invoke("create_report", request, work)

    def list_pilot_profiles(self, request: ListPilotProfilesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            profiles = PilotRegistry(self.root).profiles()
            filtered = [
                profile for profile in profiles
                if (request.commander_family is None or profile.commander_family == request.commander_family)
                and (request.include_baselines or not profile.is_baseline)
            ]
            return {
                "profiles": [profile.model_dump(mode="json") for profile in filtered],
                "count": len(filtered),
                "legal_actions_only": True,
                "omniscient_information_used": False,
                "automatic_deck_changes": False,
            }
        return self._invoke("list_pilot_profiles", request, work)

    def inspect_pilot(self, request: InspectPilotInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            profile = PilotRegistry(self.root).profile(request.pilot_name)
            pilot = build_pilot(
                PilotConfig(
                    pilot_name=profile.pilot_name,
                    strength=PilotStrength.STRONG,
                    mode=profile.mode,
                ),
                strategy=profile.commander_family,
            )
            return {
                "profile": profile.model_dump(mode="json"),
                "runtime_weights": pilot.weights.model_dump(mode="json"),
                "parameter_hash_matches_registry": profile.parameter_hash == PilotRegistry(self.root).profile(profile.pilot_name).parameter_hash,
                "legal_actions_only": True,
                "omniscient_information_used": False,
            }
        return self._invoke("inspect_pilot", request, work)

    def run_pilot_benchmark(self, request: RunPilotBenchmarkInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.iterations, None)
            runner = PilotEnsembleRunner(self.root, self.decks)
            payload = runner.benchmark(
                deck_id=request.deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=Path(request.output_name).name,
            )
            payload["result_path"] = str(
                self.root / "data/runs/pilot_ensembles" / Path(request.output_name).name / "pilot_benchmark.json"
            )
            return payload
        return self._invoke(
            "run_pilot_benchmark", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def compare_pilots(self, request: ComparePilotsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            runner = PilotEnsembleRunner(self.root, self.decks)
            benchmark = runner.benchmark(
                deck_id=request.deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=Path(request.output_name).name,
            )
            return runner.compare(benchmark, request.pilot_names)
        return self._invoke(
            "compare_pilots", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def run_pilot_ensemble(self, request: RunPilotEnsembleInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            runner = PilotEnsembleRunner(self.root, self.decks)
            registry = runner.registry
            if request.ensemble_id:
                ensemble = registry.ensemble(request.ensemble_id)
            else:
                ensemble = PilotEnsembleDefinition(
                    ensemble_id=f"custom.{request.deck_id.replace('/', '.')}.{request.seed}",
                    version="1.0.0",
                    deck_id=request.deck_id,
                    members=tuple(
                        PilotEnsembleMember(pilot_name=item.pilot_name, weight=item.weight)
                        for item in request.custom_weights
                    ),
                )
            if ensemble.deck_id != request.deck_id:
                raise ToolExecutionError("ensemble deck_id does not match request deck_id")
            names = tuple(member.pilot_name for member in ensemble.members)
            baseline_name = "KorvoldPilot" if request.deck_id.startswith("korvold/") else "RogShaiPilot"
            benchmark_names = tuple(dict.fromkeys((baseline_name, *names)))
            benchmark = runner.benchmark(
                deck_id=request.deck_id,
                pilot_names=benchmark_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=Path(request.output_name).name,
            )
            summary = runner.ensemble_summary(benchmark, ensemble)
            output = self.root / "data/runs/pilot_ensembles" / Path(request.output_name).name / "ensemble_summary.json"
            atomic_write_json(output, summary)
            summary["result_path"] = str(output)
            return summary
        return self._invoke(
            "run_pilot_ensemble", request, work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids), seed=request.seed,
            iterations=request.iterations,
        )

    def test_variant_across_pilots(self, request: TestVariantAcrossPilotsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            if request.baseline_deck_id not in self.decks or request.variant_deck_id not in self.decks:
                raise ToolExecutionError("baseline and variant must be registered structural decks")
            runner = PilotEnsembleRunner(self.root, self.decks)
            baseline = runner.benchmark(
                deck_id=request.baseline_deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=f"{Path(request.output_name).name}-baseline",
            )
            variant = runner.benchmark(
                deck_id=request.variant_deck_id,
                pilot_names=request.pilot_names,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                output_name=f"{Path(request.output_name).name}-variant",
            )
            result = runner.variant_robustness(baseline, variant)
            output = self.root / "data/runs/pilot_ensembles" / f"{Path(request.output_name).name}.json"
            atomic_write_json(output, result)
            result["result_path"] = str(output)
            return result
        return self._invoke(
            "test_variant_across_pilots", request, work,
            deck_ids=(request.baseline_deck_id, request.variant_deck_id, *request.opponent_deck_ids),
            seed=request.seed, iterations=request.iterations,
        )

    def generate_pilot_robustness_report(self, request: GeneratePilotRobustnessReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            source = (self.root / request.result_path).resolve()
            if self.root not in source.parents:
                raise ToolExecutionError("result_path escapes project root")
            payload = json.loads(source.read_text(encoding="utf-8"))
            target = self.report_dir / Path(request.output_name).name
            text = PilotEnsembleRunner.markdown_report(payload)
            atomic_write_text(target, text)
            return {
                "report_path": str(target),
                "source_path": str(source),
                "estimate_type": "structural_model_estimates",
                "automatic_deck_changes": False,
            }
        return self._invoke("generate_pilot_robustness_report", request, work)


    def _mulligan_lab(self) -> MulliganLab:
        return MulliganLab(self.root)

    def _mulligan_context_from_request(self, request: Any) -> MulliganContext:
        deck = self._deck(request.deck_id)
        ensemble_hash = None
        ensemble_id = getattr(request, "opponent_ensemble_id", None)
        if ensemble_id:
            ensemble = self._opponent_ensembles().load(ensemble_id)
            ensemble_hash = sha256_value(ensemble.model_dump(mode="json"))
        return MulliganContext(
            deck_id=request.deck_id,
            deck_hash=deck.deck_hash,
            opponent_ensemble_id=ensemble_id,
            opponent_ensemble_hash=ensemble_hash,
            seat_position=getattr(request, "seat_position", 1),
            starting_player=getattr(request, "starting_player", False),
            pod_size=getattr(request, "pod_size", 4),
            pilot_profile_id=getattr(request, "pilot_profile_id", "baseline"),
            pilot_version=getattr(request, "pilot_version", "unspecified"),
            game_plan=MulliganGamePlan(getattr(request, "game_plan", "balanced")),
            seed=getattr(request, "seed", 20260806),
        )

    def sample_opening_hands(self, request: SampleOpeningHandsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.samples, None)
            lab = self._mulligan_lab()
            deck = self._deck(request.deck_id)
            target = self.root / "data/runs/mulligan_lab" / f"{request.deck_id.replace('/', '_')}-{request.seed}-hands.jsonl"
            target.parent.mkdir(parents=True, exist_ok=True)
            first_samples = []
            with target.open("w", encoding="utf-8") as handle:
                for index, attempts in enumerate(lab.iter_draw_sequences(
                    deck, samples=request.samples, seed=request.seed, max_mulligans=request.max_mulligans
                )):
                    serialized = [[card.oracle_name for card in hand] for hand in attempts]
                    if index < 10:
                        first_samples.append(serialized)
                    handle.write(json.dumps({
                        "sample_id": index,
                        "deck_id": request.deck_id,
                        "deck_hash": deck.deck_hash,
                        "attempts": serialized,
                        "seed": request.seed,
                        "common_random_numbers_ready": True,
                    }, sort_keys=True) + "\n")
            return {
                "dataset_path": str(target.relative_to(self.root)),
                "samples": request.samples,
                "attempts_per_sample": request.max_mulligans + 1,
                "first_samples": first_samples,
                "commander_in_command_zone": list(deck.commander_names),
                "estimate_type": "structural_model_estimates",
            }
        return self._invoke(
            "sample_opening_hands", request, work, deck_ids=(request.deck_id,),
            seed=request.seed, iterations=request.samples,
        )

    def evaluate_opening_hand(self, request: EvaluateOpeningHandInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            lab = self._mulligan_lab()
            deck = self._deck(request.deck_id)
            pool: dict[str, list[Any]] = {}
            for card in lab._library(deck):
                pool.setdefault(card.oracle_name, []).append(card)
            used: Counter[str] = Counter()
            selected = []
            for name in request.card_names:
                rows = pool.get(name, [])
                index = used[name]
                if index >= len(rows):
                    raise ToolExecutionError(f"card not available in current deck library: {name}")
                selected.append(rows[index]); used[name] += 1
            context = self._mulligan_context_from_request(request)
            evaluation = lab.evaluate(
                deck, selected, MulliganPolicyName(request.policy), context
            )
            return evaluation.model_dump(mode="json") | {
                "deck_hash": deck.deck_hash,
                "commander_in_command_zone": list(deck.commander_names),
                "absolute_rule": False,
            }
        return self._invoke("evaluate_opening_hand", request, work, deck_ids=(request.deck_id,), seed=request.seed)

    def compare_mulligan_policies(self, request: CompareMulliganPoliciesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.samples * max(1, len(request.policies)), request.approval_token)
            lab = self._mulligan_lab()
            context = self._mulligan_context_from_request(request)
            result = lab.run(
                context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                samples=request.samples,
                followup_samples=request.followup_samples,
            )
            return result.model_dump(mode="json")
        return self._invoke(
            "compare_mulligan_policies", request, work, deck_ids=(request.deck_id,),
            seed=request.seed, iterations=request.samples,
        )

    def run_mulligan_lab(self, request: RunMulliganLabInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(request.samples * max(1, len(request.policies)), request.approval_token)
            lab = self._mulligan_lab()
            context = self._mulligan_context_from_request(request)
            result = lab.run(
                context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                samples=request.samples,
                followup_samples=request.followup_samples,
            )
            target = self.root / "data/runs/mulligan_lab" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {"result_path": str(target.relative_to(self.root))}
        return self._invoke(
            "run_mulligan_lab", request, work, deck_ids=(request.deck_id,),
            seed=request.seed, iterations=request.samples,
        )

    def generate_keep_rules(self, request: GenerateKeepRulesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            source = self._project_path(request.result_path)
            result = MulliganLabResult.model_validate_json(source.read_text(encoding="utf-8"))
            payload = {
                "schema_version": result.schema_version,
                "deck_id": result.context.deck_id,
                "deck_hash": result.context.deck_hash,
                "rules": [rule.model_dump(mode="json") for rule in result.generated_rules],
                "model_based": True,
                "absolute_rules": False,
            }
            target = self.root / "data/mulligan_lab/policies" / Path(request.output_name).name
            atomic_write_json(target, payload)
            return payload | {"path": str(target.relative_to(self.root))}
        return self._invoke("generate_keep_rules", request, work)

    def test_keep_rule(self, request: TestKeepRuleInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            payload = json.loads(self._project_path(request.rule_path).read_text(encoding="utf-8"))
            rows = payload.get("rules", payload)
            if not rows:
                raise ToolExecutionError("no keep rules found")
            rule = GeneratedKeepRule.model_validate(rows[0])
            lab = self._mulligan_lab(); deck = self._deck(request.deck_id)
            if rule.deck_hash != deck.deck_hash:
                raise ToolExecutionError("keep rule deck hash does not match current deck")
            pool: dict[str, list[Any]] = {}
            for card in lab._library(deck): pool.setdefault(card.oracle_name, []).append(card)
            used: Counter[str] = Counter(); cards=[]
            for name in request.card_names:
                idx=used[name]; choices=pool.get(name, [])
                if idx >= len(choices): raise ToolExecutionError(f"card not available in deck: {name}")
                cards.append(choices[idx]); used[name]+=1
            features = lab.features(deck, cards)
            return lab.test_rule(rule, features) | {"features": features.model_dump(mode="json")}
        return self._invoke("test_keep_rule", request, work, deck_ids=(request.deck_id,))

    def create_mulligan_report(self, request: CreateMulliganReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = MulliganLabResult.model_validate_json(
                self._project_path(request.result_path).read_text(encoding="utf-8")
            )
            lines = [
                "# Mulligan Lab Report", "",
                f"Deck: `{result.context.deck_id}`", f"Deck hash: `{result.context.deck_hash}`",
                f"Samples: {result.sample_count}", "",
                "All keep rules and follow-up outcomes are model-based structural estimates.", "",
                "## Policy comparison", "",
                "| Policy | First-seven keep | Mulligan rate | Avg mulligans | Color issues | Structural placement |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for row in result.policies:
                placement = "n/a" if row.structural_placement_mean is None else f"{row.structural_placement_mean:.3f}"
                lines.append(
                    f"| {row.policy.value} | {row.keep_rate_first_seven:.3f} | {row.mulligan_rate:.3f} | "
                    f"{row.average_mulligans:.3f} | {row.color_problem_rate:.3f} | {placement} |"
                )
            lines.extend(["", "## Boundaries", "", "- Hand quality is separated from complete matchup performance.", "- No rule is universal or empirically proven.", "- No external rules engine was used."])
            target = self.root / "data/runs/mulligan_lab" / Path(request.output_name).name
            atomic_write_text(target, "\n".join(lines)+"\n")
            return {"report_path": str(target.relative_to(self.root)), "model_based": True, "automatic_deck_changes": False}
        return self._invoke("create_mulligan_report", request, work)

    def _counterfactual_lab(self):
        from commander_lab.counterfactual import CounterfactualReplayLab
        return CounterfactualReplayLab(self.root, external_engine_available=False)

    def find_counterfactual_branchpoints(self, request):
        def work() -> dict[str, Any]:
            rows = self._counterfactual_lab().find_branchpoints(
                request.source_path, actor_id=request.actor_id, phase=request.phase
            )
            return {
                "branchpoints": [row.model_dump(mode="json") for row in rows],
                "count": len(rows),
                "model_alternatives_only": True,
            }
        return self._invoke("find_counterfactual_branchpoints", request, work)

    def list_alternative_actions(self, request):
        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            lab.verify_branchpoint(branch, request.expected_state_hash)
            return {
                "branchpoint": branch.model_dump(mode="json"),
                "alternatives": [
                    row.model_dump(mode="json")
                    for row in branch.available_actions
                    if row.action_id != branch.chosen_action and row.legal
                ],
                "only_recorded_legal_candidates": True,
            }
        return self._invoke("list_alternative_actions", request, work)

    def run_counterfactual(self, request):
        from commander_lab.models import (
            CounterfactualEngineMode, HiddenInformationPolicy, SeedPolicy,
        )
        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            result = lab.run(
                branch,
                alternative_action=request.alternative_action,
                expected_state_hash=request.expected_state_hash,
                hidden_information_policy=HiddenInformationPolicy(request.hidden_information_policy),
                engine_mode=CounterfactualEngineMode(request.engine_mode),
                seed_policy=SeedPolicy(request.seed_policy),
                seed=request.seed,
                future_samples=request.future_samples,
                workers=request.workers,
            )
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {"result_path": str(target.relative_to(self.root))}
        return self._invoke(
            "run_counterfactual", request, work,
            seed=request.seed, iterations=request.future_samples,
        )

    def compare_counterfactuals(self, request):
        from commander_lab.counterfactual import CounterfactualReplayLab
        from commander_lab.models import CounterfactualResult
        def work() -> dict[str, Any]:
            rows = [
                CounterfactualResult.model_validate_json(
                    self._project_path(path).read_text(encoding="utf-8")
                )
                for path in request.result_paths
            ]
            result = CounterfactualReplayLab.compare(rows)
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {"result_path": str(target.relative_to(self.root))}
        return self._invoke("compare_counterfactuals", request, work)

    def generate_decision_regret_report(self, request):
        from commander_lab.counterfactual import CounterfactualReplayLab
        from commander_lab.models import CounterfactualResult
        def work() -> dict[str, Any]:
            result = CounterfactualResult.model_validate_json(
                self._project_path(request.result_path).read_text(encoding="utf-8")
            )
            regret = CounterfactualReplayLab.regret(result)
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            CounterfactualReplayLab.report(result, target)
            return {
                "regret": regret.model_dump(mode="json"),
                "report_path": str(target.relative_to(self.root)),
                "model_dependent": True,
            }
        return self._invoke("generate_decision_regret_report", request, work)

    def export_minimal_counterfactual_fixture(self, request):
        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            lab.verify_branchpoint(branch, request.expected_state_hash)
            target = self.root / "data/evals/golden" / Path(request.output_name).name
            payload = lab.export_fixture(branch, target)
            return payload | {"fixture_path": str(target.relative_to(self.root))}
        return self._invoke("export_minimal_counterfactual_fixture", request, work)

    def _diagnostic_engine(self):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        return DecisionDiagnosticEngine()

    def diagnose_card_performance(self, request):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.card_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {"diagnosis_path": str(target.relative_to(self.root))}
        return self._invoke("diagnose_card_performance", request, work)

    def diagnose_pilot_behavior(self, request):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.pilot_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {"diagnosis_path": str(target.relative_to(self.root))}
        return self._invoke("diagnose_pilot_behavior", request, work)

    def compare_deck_and_pilot_effects(self, request):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            result = self._diagnostic_engine().compare_effects(dataset)
            return result.model_dump(mode="json") | {"causal_identification": False}
        return self._invoke("compare_deck_and_pilot_effects", request, work)

    def classify_failure_cause(self, request):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.subject)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {"diagnosis_path": str(target.relative_to(self.root))}
        return self._invoke("classify_failure_cause", request, work)

    def recommend_next_experiment(self, request):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord
        def work() -> dict[str, Any]:
            diagnosis = DiagnosisRecord.model_validate_json(self._project_path(request.diagnosis_path).read_text(encoding="utf-8"))
            return DecisionDiagnosticEngine.next_experiment(diagnosis)
        return self._invoke("recommend_next_experiment", request, work)

    def generate_diagnostic_report(self, request):
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord
        def work() -> dict[str, Any]:
            diagnoses = [
                DiagnosisRecord.model_validate_json(self._project_path(path).read_text(encoding="utf-8"))
                for path in request.diagnosis_paths
            ]
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            DecisionDiagnosticEngine.report(diagnoses, target)
            return {
                "report_path": str(target.relative_to(self.root)),
                "diagnosis_count": len(diagnoses),
                "automatic_deck_changes": False,
                "empirical_proof_claimed": False,
            }
        return self._invoke("generate_diagnostic_report", request, work)
