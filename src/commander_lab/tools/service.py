from __future__ import annotations

import itertools
import json
import subprocess
from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING, Any

from commander_lab.agents.ensemble import PilotEnsembleRunner, PilotRegistry
from commander_lab.agents.pilots import build_pilot
from commander_lab.cut_frontier import build_static_swap_rows, select_diverse_swap_frontier
from commander_lab.decision_statistics import holm_adjust
from commander_lab.engine.rules import (
    RulesEngineManager,
    TacticalRuleOracle,
    load_interaction_catalog,
    load_project_rules_decks,
)
from commander_lab.models import (
    ActionProposal,
    BeamSearchInput,
    BuildOptimizationContextInput,
    CandidatePackage,
    CardAblationInput,
    ComparePilotsInput,
    CreateDeckImprovementReportInput,
    CreateReportInput,
    ExplainRecommendationInput,
    ExportRecommendationEvidenceInput,
    GenerateCandidatePackagesInput,
    GenerateCandidateSwapsInput,
    GeneratePilotRobustnessReportInput,
    InspectPilotInput,
    ListPilotProfilesInput,
    LocalSearchInput,
    OptimizationVariant,
    OptimizeDeckAgainstMetaInput,
    OptimizeMultipleDecksWithAllocationInput,
    PackageSearchInput,
    ParetoFrontInput,
    PilotConfig,
    PilotEnsembleDefinition,
    PilotEnsembleMember,
    PilotStrength,
    RankVariantsInput,
    RulesGameRequest,
    RunEngineBackedMatchupInput,
    RunMultifidelityComparisonInput,
    RunPilotBenchmarkInput,
    RunPilotEnsembleInput,
    RunRobustnessSuiteInput,
    RunRulesCoverageGateInput,
    SearchVariantsInput,
    ShapleyInput,
    StructuralDeckProfile,
    SwapMatrixInput,
    TestVariantAcrossPilotsInput,
    ToolResponse,
    ToolStatus,
    ValidateDeckInput,
    ValidateLandChangeInput,
    ValidateMulliganPolicyInput,
    ValidatePackageChangeInput,
    ValidateSwapInput,
    ValidateUpgradeInput,
    VariantSwap,
)
from commander_lab.models.mulligan import (
    GeneratedKeepRule,
    MulliganContext,
    MulliganGamePlan,
    MulliganLabResult,
    MulliganPolicyName,
)
from commander_lab.models.tooling import (
    CompareMulliganPoliciesInput,
    CreateMulliganReportInput,
    EvaluateOpeningHandInput,
    GenerateKeepRulesInput,
    RunMulliganLabInput,
    SampleOpeningHandsInput,
    TestKeepRuleInput,
)
from commander_lab.mulligan import MulliganLab
from commander_lab.optimization import (
    SearchCandidate,
    all_legal_single_swaps,
    approximate_shapley_profile,
    build_recommendation_trace,
    build_robust_objective,
    build_search_candidate,
    evaluate_constraints,
    pareto_front,
    profile_score,
    recommendation_confidence,
    run_paired_structural_comparison,
    scenario_heterogeneity,
)
from commander_lab.robustness import POLITICS_REGIMES, pilot_config_for
from commander_lab.storage import (
    atomic_write_json,
    atomic_write_text,
    sha256_value,
)

if TYPE_CHECKING:
    from commander_lab.counterfactual import CounterfactualReplayLab
    from commander_lab.diagnostics import DecisionDiagnosticEngine

from .service_core import ApprovalRequired as ApprovalRequired
from .service_core import EstimateType as EstimateType
from .service_core import ServiceCore
from .service_core import ToolExecutionError as ToolExecutionError
from .service_core import _deterministic_structural_run_id as _deterministic_structural_run_id
from .service_knowledge import ServiceKnowledgeMixin
from .service_simulation import ServiceSimulationMixin


class CommanderToolService(ServiceKnowledgeMixin, ServiceSimulationMixin, ServiceCore):
    """Deterministic local Function Tool service.

    The service is the sole mutation boundary for local artifacts. Agent code receives only these
    methods and cannot directly mutate game state. Simulation results remain structural estimates.
    """

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

    @property
    def git_tree(self) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD^{tree}"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    @property
    def tracked_worktree_dirty(self) -> bool:
        try:
            output = subprocess.check_output(
                ["git", "-C", str(self.root), "status", "--porcelain", "--untracked-files=no"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return bool(output.strip())
        except (OSError, subprocess.CalledProcessError):
            return False

    def generate_swap_matrix(self, request: SwapMatrixInput) -> ToolResponse:
        """Generate every requested cut/add cell, preserving invalid cells as evidence."""

        def work() -> dict[str, Any]:
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id)
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.add_candidate_ids)
            remove_cards = request.remove_cards or tuple(
                dict.fromkeys(
                    card.oracle_name
                    for card in baseline.cards
                    if card.oracle_name not in baseline.commander_names
                    and not self._is_protected(request.deck_id, card.oracle_name)
                )
            )
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
                    row.update(
                        {
                            "add": candidate.additions[0].card.oracle_name,
                            "screening_score": candidate.screening_score,
                            "constraint_report": candidate.constraint_report.model_dump(
                                mode="json"
                            ),
                            "structural_rationale": candidate.rationale,
                            "affected_matchups": candidate.affected_matchups,
                        }
                    )
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
            "generate_swap_matrix",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations_per_cell,
        )

    @staticmethod
    def models_variant_swap(remove: str, candidate_id: str) -> VariantSwap:
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
                request.max_steps
                * request.cuts_per_step
                * max(1, len(self._eligible_candidate_ids(request.deck_id, request.candidate_ids)))
                * request.iterations,
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
                    card.oracle_name: card
                    for card in sorted(baseline.cards, key=profile_score)
                    if card.oracle_name not in baseline.commander_names
                    and card.oracle_name not in used_cuts
                    and not card.is_land
                    and not self._is_protected(request.deck_id, card.oracle_name)
                }
                cuts = list(cut_map.values())[: request.cuts_per_step]
                neighbors: list[tuple[float, float, SearchCandidate, dict[str, Any]]] = []
                for cut in cuts:
                    for candidate_id in candidate_ids:
                        if candidate_id in used_candidates:
                            continue
                        swaps = tuple(
                            [
                                *cumulative_swaps,
                                self.models_variant_swap(cut.oracle_name, candidate_id),
                            ]
                        )
                        try:
                            neighbor = build_search_candidate(
                                baseline,
                                swaps,
                                self.candidates,
                                constraints,
                                inventory=self.candidate_inventory,
                                verified_physical_names=self.verified_candidate_names,
                                parent_variant_id=current.deck_id,
                            )
                        except Exception:
                            continue
                        if not neighbor.constraint_report.valid:
                            continue
                        metrics, _ = self._paired_variant_metrics(
                            baseline=current,
                            variant=neighbor.variant,
                            opponent_deck_ids=request.opponent_deck_ids,
                            iterations=request.iterations,
                            seed=request.seed + step,
                            pilot_strength=request.pilot_strength,
                            pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            pair_id=f"local-{step}-{neighbor.variant.deck_hash[:10]}",
                        )
                        evaluated += 1
                        neighbors.append(
                            (
                                metrics.distributionally_robust_lower_bound,
                                metrics.placement_improvement,
                                neighbor,
                                metrics.as_dict(),
                            )
                        )
                if not neighbors:
                    break
                neighbors.sort(
                    key=lambda row: (
                        row[0],
                        row[1],
                        row[2].screening_score,
                        row[2].variant.deck_hash,
                    ),
                    reverse=True,
                )
                robust_lower_bound, _improvement, best, comparison = neighbors[0]
                if robust_lower_bound <= 0:
                    break
                cumulative_swaps = list(best.swaps)
                used_candidates = {swap.add_candidate_id for swap in best.swaps}
                used_cuts = {swap.remove for swap in best.swaps}
                current = best.variant
                path.append(
                    {
                        "step": step + 1,
                        "swaps": [swap.model_dump(mode="json") for swap in best.swaps],
                        "comparison_to_parent": comparison,
                        "screening_score": best.screening_score,
                        "robust_lower_bound": robust_lower_bound,
                        "ranking_policy": "distributionally_robust_lower_bound_then_mean_then_static_screen",
                        "constraint_report": best.constraint_report.model_dump(mode="json"),
                        "structural_rationale": best.rationale,
                        "affected_matchups": best.affected_matchups,
                        "variant_deck_hash": best.variant.deck_hash,
                        "automatic_application": False,
                    }
                )
            return {
                "method": "staged_constrained_local_search",
                "ranking_policy": "hard_constraints_then_static_preselection_then_paired_distributionally_robust_lower_bound",
                "evaluated_neighbors": evaluated,
                "path": path,
                "best_variant": path[-1] if path else None,
                "automatic_application": False,
            }

        return self._invoke(
            "run_local_search",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_beam_search(self, request: BeamSearchInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            candidate_ids = self._eligible_candidate_ids(request.deck_id, request.candidate_ids)
            estimated = (
                request.depth
                * request.beam_width
                * request.max_cuts_per_node
                * max(1, len(candidate_ids))
            )
            if estimated > self.limits.max_variants * 20:
                raise ToolExecutionError(
                    f"beam expansion estimate {estimated} exceeds safety bound"
                )
            self._check_iterations(
                min(estimated, self.limits.max_variants) * request.iterations,
                request.approval_token,
            )
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
                        card.oracle_name: card
                        for card in sorted(baseline.cards, key=profile_score)
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
                            swaps = tuple(
                                (
                                    *parent_swaps,
                                    self.models_variant_swap(cut.oracle_name, candidate_id),
                                )
                            )
                            try:
                                node = build_search_candidate(
                                    baseline,
                                    swaps,
                                    self.candidates,
                                    constraints,
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
                scored: list[tuple[float, float, SearchCandidate, dict[str, Any]]] = []
                for node in candidates:
                    metrics, _ = self._paired_variant_metrics(
                        baseline=baseline,
                        variant=node.variant,
                        opponent_deck_ids=request.opponent_deck_ids,
                        iterations=request.iterations,
                        seed=request.seed + depth,
                        pilot_strength=request.pilot_strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        pair_id=f"beam-{depth}-{node.variant.deck_hash[:10]}",
                    )
                    scored.append(
                        (
                            metrics.distributionally_robust_lower_bound,
                            metrics.placement_improvement,
                            node,
                            metrics.as_dict(),
                        )
                    )
                scored.sort(
                    key=lambda row: (
                        row[0],
                        row[1],
                        row[2].screening_score,
                        row[2].variant.deck_hash,
                    ),
                    reverse=True,
                )
                beam = [row[2] for row in scored[: request.beam_width]]
                if not beam:
                    break
            final_rows: list[dict[str, Any]] = []
            for node in beam:
                metrics, pairs = self._paired_variant_metrics(
                    baseline=baseline,
                    variant=node.variant,
                    opponent_deck_ids=request.opponent_deck_ids,
                    iterations=request.iterations,
                    seed=request.seed,
                    pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    pair_id=f"beam-final-{node.variant.deck_hash[:10]}",
                )
                final_rows.append(
                    {
                        "swaps": [swap.model_dump(mode="json") for swap in node.swaps],
                        "comparison": metrics.as_dict(),
                        "worst_quartile_delta": self._worst_quartile(pairs),
                        "screening_score": node.screening_score,
                        "robust_lower_bound": metrics.distributionally_robust_lower_bound,
                        "constraint_report": node.constraint_report.model_dump(mode="json"),
                        "structural_rationale": node.rationale,
                        "affected_matchups": node.affected_matchups,
                        "variant_deck_hash": node.variant.deck_hash,
                        "automatic_application": False,
                    }
                )
            final_rows.sort(
                key=lambda row: (
                    row["comparison"]["distributionally_robust_lower_bound"],
                    row["comparison"]["placement_improvement"],
                    row["screening_score"],
                ),
                reverse=True,
            )
            return {
                "method": "staged_beam_search",
                "ranking_policy": "hard_constraints_then_static_beam_preselection_then_paired_distributionally_robust_lower_bound",
                "beam_width": request.beam_width,
                "depth": request.depth,
                "variants": final_rows,
                "automatic_application": False,
            }

        return self._invoke(
            "run_beam_search",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
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
                    card
                    for card in sorted(baseline.cards, key=profile_score)
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
                        name
                        for name in package_def.all_cards
                        if name not in present_names and name in candidate_by_name
                    ][: request.max_package_size]
                    if not missing:
                        continue
                    chosen_cuts = [
                        card for card in cuts if card.oracle_name not in package_def.all_cards
                    ][: len(missing)]
                    if len(chosen_cuts) != len(missing):
                        continue
                    packages.append(
                        CandidatePackage(
                            package_id=f"registry-{package_id}",
                            swaps=tuple(
                                VariantSwap(
                                    remove=cut.oracle_name, add_candidate_id=candidate_by_name[add]
                                )
                                for cut, add in zip(chosen_cuts, missing, strict=True)
                            ),
                            rationale=(
                                f"Package-aware completion candidate for {package_id}; "
                                "not automatically applied."
                            ),
                        )
                    )
            if not packages:
                singles = all_legal_single_swaps(
                    baseline,
                    self.candidates,
                    candidate_ids,
                    constraints,
                    inventory=self.candidate_inventory,
                    verified_physical_names=self.verified_candidate_names,
                    protected=set(self.protected_cards.get(request.deck_id, [])),
                )[:12]
                seen: set[str] = set()
                for size in range(2, request.max_package_size + 1):
                    for combo in itertools.combinations(singles, size):
                        swaps = tuple(item.swaps[0] for item in combo)
                        if (
                            len({swap.remove for swap in swaps}) != size
                            or len({swap.add_candidate_id for swap in swaps}) != size
                        ):
                            continue
                        key = sha256_value([swap.model_dump(mode="json") for swap in swaps])
                        if key in seen:
                            continue
                        seen.add(key)
                        packages.append(
                            CandidatePackage(package_id=f"auto-{key[:10]}", swaps=swaps)
                        )
                        if len(packages) >= request.max_packages:
                            break
                    if len(packages) >= request.max_packages:
                        break
            self._check_iterations(len(packages) * request.iterations, request.approval_token)
            rows: list[dict[str, Any]] = []
            for package in packages[: request.max_packages]:
                try:
                    node = build_search_candidate(
                        baseline,
                        package.swaps,
                        self.candidates,
                        constraints,
                        inventory=self.candidate_inventory,
                        verified_physical_names=self.verified_candidate_names,
                    )
                except Exception as exc:
                    rows.append(
                        {"package_id": package.package_id, "status": "invalid", "error": str(exc)}
                    )
                    continue
                if not node.constraint_report.valid:
                    rows.append(
                        {
                            "package_id": package.package_id,
                            "status": "constraint_failed",
                            "constraint_report": node.constraint_report.model_dump(mode="json"),
                        }
                    )
                    continue
                metrics, pairs = self._paired_variant_metrics(
                    baseline=baseline,
                    variant=node.variant,
                    opponent_deck_ids=request.opponent_deck_ids,
                    iterations=request.iterations,
                    seed=request.seed,
                    pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    pair_id=f"package-search-{node.variant.deck_hash[:10]}",
                )
                rows.append(
                    {
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
                    }
                )
            rows.sort(
                key=lambda row: (row.get("comparison") or {}).get("placement_improvement", -99),
                reverse=True,
            )
            return {"method": "package_search", "packages": rows, "automatic_application": False}

        return self._invoke(
            "run_package_search",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def evaluate_pareto_front(self, request: ParetoFrontInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                len(request.variants) * (1 + len(request.holdout_pods)) * request.iterations,
                request.approval_token,
            )
            baseline = self._deck(request.deck_id)
            constraints = self._optimization_constraints(request.deck_id, request.constraints)
            evaluated: list[OptimizationVariant] = []
            evidence: dict[str, Any] = {}
            for swaps in request.variants:
                node = build_search_candidate(
                    baseline,
                    swaps,
                    self.candidates,
                    constraints,
                    inventory=self.candidate_inventory,
                    verified_physical_names=self.verified_candidate_names,
                )
                if not node.constraint_report.valid:
                    evaluated.append(
                        OptimizationVariant(
                            variant_id=node.variant.deck_id,
                            deck_id=baseline.deck_id,
                            deck_hash=node.variant.deck_hash,
                            swaps=node.swaps,
                            structural_rationale=node.rationale,
                            affected_matchups=node.affected_matchups,
                            constraint_report=node.constraint_report,
                            screening_score=node.screening_score,
                            search_method="pareto_evaluation",
                        )
                    )
                    continue
                variant, paired, holdouts, _ = self._evaluate_search_candidate(
                    baseline=baseline,
                    candidate=node,
                    opponent_deck_ids=request.opponent_deck_ids,
                    holdout_pods=request.holdout_pods,
                    iterations=request.iterations,
                    seed=request.seed,
                    pilot_strength=request.pilot_strength,
                    pilot_mode=request.pilot_mode,
                    max_turns=request.max_turns,
                    search_method="pareto_evaluation",
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
            "evaluate_pareto_front",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def estimate_shapley(self, request: ShapleyInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                len(request.card_names) * request.iterations, request.approval_token
            )
            deck = self._deck(request.deck_id)
            values = approximate_shapley_profile(
                deck, request.card_names, permutations=request.permutations, seed=request.seed
            )
            ablations: dict[str, Any] = {}
            for name in request.card_names:
                response = self.run_card_ablation(
                    CardAblationInput(
                        deck_id=request.deck_id,
                        card_name=name,
                        opponent_deck_ids=request.opponent_deck_ids,
                        seed=request.seed,
                        iterations=request.iterations,
                        workers=1,
                        pilot_strength=request.pilot_strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                    )
                )
                ablations[name] = (
                    response.result
                    if response.status == ToolStatus.COMPLETED
                    else {"errors": response.errors}
                )
            return {
                "method": "permutation_profile_shapley_with_paired_single_card_ablation",
                "permutations": request.permutations,
                "contributions": values,
                "paired_ablation_evidence": ablations,
                "selection_role": "secondary_explanatory_triage_only",
                "primary_optimizer_ranking_allowed": False,
                "warning": (
                    "Shapley values use a profile-surrogate coalition value with paired single-card ablation; "
                    "they are approximate structural contribution estimates, not causal real-game values and "
                    "must not select the final optimizer winner by themselves."
                ),
            }

        return self._invoke(
            "estimate_shapley",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
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
                variant,
                constraints,
                candidate_inventory=self.candidate_inventory,
                added_card_names=tuple(row["add"] for row in swap_rows),
                verified_physical_names=self.verified_candidate_names,
            )
            metrics, pairs = self._paired_variant_metrics(
                baseline=baseline,
                variant=variant,
                opponent_deck_ids=request.opponent_deck_ids,
                iterations=request.iterations,
                seed=request.seed,
                pilot_strength=request.pilot_strength,
                pilot_mode=request.pilot_mode,
                max_turns=request.max_turns,
                pair_id=f"validate-{variant.deck_hash[:10]}",
            )
            holdouts = self._holdout_improvements(
                baseline=baseline,
                variant=variant,
                holdout_pods=request.holdout_pods if request.require_holdout else (),
                iterations=request.iterations,
                seed=request.seed,
                pilot_strength=request.pilot_strength,
                pilot_mode=request.pilot_mode,
                max_turns=request.max_turns,
            )
            sensitivity: list[dict[str, Any]] = []
            for seed in request.sensitivity_seeds:
                for strength in request.sensitivity_strengths:
                    sensitive_metrics, _ = self._paired_variant_metrics(
                        baseline=baseline,
                        variant=variant,
                        opponent_deck_ids=request.opponent_deck_ids,
                        iterations=request.iterations,
                        seed=seed,
                        pilot_strength=strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        pair_id=f"sensitivity-{variant.deck_hash[:8]}-{seed}-{strength.value}",
                    )
                    sensitivity.append(
                        {
                            "seed": seed,
                            "pilot_strength": strength.value,
                            "placement_improvement": sensitive_metrics.placement_improvement,
                            "place_1_share_delta": sensitive_metrics.place_1_share_delta,
                        }
                    )
            red_team = self._red_team_review(
                baseline=baseline,
                variant=variant,
                swaps=request.swaps,
                constraint_report=report,
                paired=metrics.as_dict(),
                holdouts=holdouts,
                sensitivity=sensitivity,
            )
            holdout_passed = (
                all(row["comparison"]["placement_improvement"] >= 0 for row in holdouts)
                if request.require_holdout
                else True
            )
            sensitivity_passed = (
                all(row["placement_improvement"] >= 0 for row in sensitivity)
                if request.require_sensitivity_nonnegative
                else True
            )
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
            added_cards = [
                self._candidate(swap.add_candidate_id, request.deck_id).card
                for swap in request.swaps
            ]
            rationale: list[str] = []
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
            "validate_upgrade",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def _opponent_pod_for_size(self, requested: tuple[str, ...], pod_size: int) -> tuple[str, ...]:
        needed = pod_size - 1
        if needed < 1:
            raise ToolExecutionError("Commander robustness pods require at least two players")
        ordered: list[str] = []
        for deck_id in (
            *requested,
            "opponent/morcant-elves",
            "opponent/cosmic-spiderman-midbudget",
            "opponent/blight-curse-precon",
            "kaervek/current",
            "opponent/doom-prevails-precon",
            "opponent/dance-elements-precon",
            "opponent/wakanda-forever-precon",
            *sorted(
                deck_id
                for deck_id in self.decks
                if (deck_id.startswith("opponent/") or deck_id == "kaervek/current")
            ),
            "synthetic/aggro",
            "synthetic/control",
            "synthetic/engine",
        ):
            if deck_id in self.decks and deck_id not in ordered:
                ordered.append(deck_id)
        if len(ordered) < needed:
            raise ToolExecutionError(f"not enough structural opponents for pod size {pod_size}")
        return tuple(ordered[:needed])

    def _politics_pod_sensitivity(
        self,
        *,
        baseline: StructuralDeckProfile,
        variant: StructuralDeckProfile,
        opponent_deck_ids: tuple[str, ...],
        pod_sizes: tuple[int, ...],
        seed: int,
        iterations: int,
        max_turns: int,
        profile_name: str,
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
                    baseline=baseline,
                    variant=variant,
                    opponents=tuple(self._deck(deck_id) for deck_id in opponents),
                    iterations=sample_iterations,
                    seed=seed + pod_size * 1000 + list(POLITICS_REGIMES).index(regime),
                    pilot_config=config,
                    max_turns=max_turns,
                    pair_id=f"robust-{variant.deck_hash[:8]}-{pod_size}-{regime}",
                )
                rows.append(
                    {
                        "politics": regime,
                        "pod_size": pod_size,
                        "opponents": list(opponents),
                        "iterations": sample_iterations,
                        "placement_improvement": metrics.placement_improvement,
                        "place_1_share_delta": metrics.place_1_share_delta,
                        "confidence_interval": metrics.confidence_interval,
                        "validation_level": "structural_only",
                    }
                )
        return rows

    def _tactical_interaction_evidence(self, card_names: tuple[str, ...]) -> dict[str, Any]:
        wanted = {name for name in card_names if name}
        catalog = load_interaction_catalog(
            self.root / "data/rules/project_critical_interactions.json"
        )
        selected = [case for case in catalog if wanted.intersection(case.cards)]
        if not selected:
            return {
                "execution_status": "not_run_no_relevant_case",
                "validation_level": "structural_only",
                "cases_attempted": 0,
                "cases_passed": 0,
                "cases_failed": 0,
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
            adapter = manager.xmage
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
            if request.include_kaervek:
                raise ToolExecutionError(
                    "kaervek/current is frozen opponent-only; include_kaervek cannot make it an optimization target"
                )
            frozen_requested = [
                deck_id for deck_id in requested if deck_id in self.FROZEN_OPPONENT_ONLY_DECK_IDS
            ]
            if frozen_requested:
                raise ToolExecutionError(
                    f"frozen opponent-only optimization target requested: {frozen_requested[0]}"
                )
            available = [deck_id for deck_id in requested if deck_id in self.decks]
            unavailable = [deck_id for deck_id in requested if deck_id not in self.decks]
            coverage = self._read_optional_json("data/rules/card_rules_coverage.json", {})
            robustness = self._read_optional_json(
                "data/robustness/pilot_and_politics_registry.json", {}
            )
            engine = self._read_optional_json("artifacts/phase12_13/PHASE12_13_RESULT.json", {})
            canonical = self._read_optional_json(
                "data/canonical_import/2026-08-07/deck_lists.json", {}
            )
            return {
                "execution_status": "passed_with_limitations" if unavailable else "passed",
                "validation_level": "structural_only",
                "deck_priority": list(self.ACTIVE_OWN_DECK_IDS),
                "frozen_opponent_only_decks": sorted(self.FROZEN_OPPONENT_ONLY_DECK_IDS),
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
                    "source_workbook": canonical.get("source_file")
                    or canonical.get("source_workbook"),
                    "source_drive_id": canonical.get("source_drive_file_id")
                    or canonical.get("source_drive_id"),
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
                    "external_engine_execution_status": coverage.get(
                        "external_engine_execution_status", "blocked"
                    ),
                    "deck_statistics": coverage.get("deck_statistics", {}),
                },
                "pilot_profiles": [
                    row.get("pilot_id") for row in robustness.get("pilot_profiles", [])
                ],
                "politics_regimes": [
                    row.get("regime_id") for row in robustness.get("politics_regimes", [])
                ],
                "external_engine": {
                    "execution_status": engine.get("execution_status", "blocked"),
                    "completion_status": engine.get("completion_status", "external_engine_blocked"),
                    "observations": engine.get("external_rules_engine_observations", 0),
                },
                "basic_land_policy": (
                    "at_least_50_each_basic_type; not scarce within normal deck limits"
                ),
                "automatic_application": False,
                "canonical_files_modified": False,
            }

        return self._invoke("build_optimization_context", request, work, deck_ids=request.deck_ids)

    def generate_candidate_swaps(self, request: GenerateCandidateSwapsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            from commander_lab.candidate_screening import RogShaiCandidateScreener

            deck = self._deck(request.deck_id)
            semantic_screen = RogShaiCandidateScreener(self.root, service=self).screen_pool(
                request.deck_id
            )
            raw_screen_rows = semantic_screen.get("rows", [])
            screen_rows: list[Any] = raw_screen_rows if isinstance(raw_screen_rows, list) else []
            by_id = {
                str(item["candidate_id"]): item
                for item in screen_rows
                if isinstance(item, dict) and item.get("candidate_id")
            }
            by_name = {
                str(item["oracle_name"]): item
                for item in screen_rows
                if isinstance(item, dict) and item.get("oracle_name")
            }
            requested_ids = set(request.candidate_ids) if request.candidate_ids else None
            candidate_map = {
                candidate_id: candidate
                for candidate_id, candidate in self.candidates.items()
                if requested_ids is None or candidate_id in requested_ids
            }
            raw_pairs = build_static_swap_rows(
                deck,
                candidate_map,
                protected=set(self.protected_cards.get(request.deck_id, [])),
                max_cut_hypotheses=32,
            )
            semantically_ready: list[dict[str, Any]] = []
            semantic_deferred: list[dict[str, Any]] = []
            for raw in raw_pairs:
                row = dict(raw)
                screen_row = by_id.get(str(row.get("candidate_id"))) or by_name.get(
                    str(row.get("add"))
                )
                evidence = (
                    dict(screen_row.get("semantic_evidence", {}))
                    if isinstance(screen_row, dict)
                    and isinstance(screen_row.get("semantic_evidence"), dict)
                    else {}
                )
                bucket = (
                    str(screen_row.get("bucket")) if isinstance(screen_row, dict) else "missing"
                )
                model_ready = bool(
                    isinstance(screen_row, dict)
                    and screen_row.get("model_dependent_recommendation_ready") is True
                )
                needs_adjudication = bool(
                    evidence.get("needs_targeted_adjudication") is True or not model_ready
                )
                legacy_quality = str(row.get("semantic_quality", "unknown"))
                evidence_type = str(evidence.get("evidence_type", "UNKNOWN"))
                provenance_disagreement = (
                    legacy_quality == "keyword_inferred_structural_only"
                    and evidence_type not in {"PROJECT_HEURISTIC", "UNKNOWN"}
                )
                if screen_row is None:
                    frontier_status = "deferred_missing_current_semantic_screen"
                    needs_adjudication = True
                elif not model_ready:
                    frontier_status = "deferred_requires_profile"
                elif evidence.get("needs_targeted_adjudication") is True:
                    frontier_status = "deferred_requires_semantic_adjudication"
                elif bucket in {"defer_clear_static_dominance", "defer_low_confidence_default"}:
                    frontier_status = "deferred_static"
                else:
                    frontier_status = "preconstraint_ready"
                enriched = {
                    **row,
                    "legacy_semantic_quality": legacy_quality,
                    "semantic_authority": "semantic_evidence_summary",
                    "semantic_evidence": evidence,
                    "semantic_evidence_hash": str(evidence.get("semantic_evidence_hash", "")),
                    "semantic_screen_bucket": bucket,
                    "semantic_provenance_disagreement": provenance_disagreement,
                    "material_semantic_conflict": bool(
                        evidence.get("needs_targeted_adjudication") is True
                    ),
                    "requires_semantic_adjudication": needs_adjudication,
                    "frontier_status": frontier_status,
                    "recommendation_status": "candidate_swap",
                    "validation_level": "structural_only",
                    "candidate_source": "verified local candidate registry",
                    "automatic_application": False,
                }
                if frontier_status == "preconstraint_ready":
                    semantically_ready.append(enriched)
                elif needs_adjudication:
                    semantic_deferred.append(enriched)
            # Select extra capacity so hard-constraint failures can be replaced without changing the policy.
            selected_pool, selection_metrics = select_diverse_swap_frontier(
                semantically_ready,
                max_pairs=min(len(semantically_ready), request.max_candidates * 2),
            )
            ready_rows: list[dict[str, Any]] = []
            constraint_deferred: list[dict[str, Any]] = []
            constraints = self._optimization_constraints(request.deck_id)
            for row in selected_pool:
                try:
                    built = build_search_candidate(
                        deck,
                        (
                            VariantSwap(
                                remove=str(row["remove"]), add_candidate_id=str(row["candidate_id"])
                            ),
                        ),
                        self.candidates,
                        constraints,
                        inventory=self.candidate_inventory,
                        verified_physical_names=self.verified_candidate_names,
                    )
                except (KeyError, ValueError) as exc:
                    constraint_deferred.append(
                        {
                            **row,
                            "frontier_status": "deferred_hard_constraint",
                            "constraint_error": str(exc),
                        }
                    )
                    continue
                if not built.constraint_report.valid:
                    constraint_deferred.append(
                        {
                            **row,
                            "frontier_status": "deferred_hard_constraint",
                            "constraint_report": built.constraint_report.model_dump(mode="json"),
                        }
                    )
                    continue
                ready_rows.append(
                    {
                        **row,
                        "frontier_status": "simulation_ready",
                        "whole_deck_constraint_report": built.constraint_report.model_dump(
                            mode="json"
                        ),
                        "variant_deck_hash": built.variant.deck_hash,
                    }
                )
                if len(ready_rows) >= request.max_candidates:
                    break
            _, final_metrics = (
                select_diverse_swap_frontier(ready_rows, max_pairs=max(1, len(ready_rows)))
                if ready_rows
                else (
                    [],
                    {
                        "unique_cut_count": 0,
                        "top_cut_pair_share": 0.0,
                        "cut_concentration_metric": 0.0,
                        "cut_pair_distribution": {},
                        "cut_lane_distribution": {},
                        "pair_count": 0,
                        "selection_policy": "no_ready_pairs",
                        "truth_boundary": "frontier composition metric, not empirical card weakness",
                    },
                )
            )
            bucket_counts = semantic_screen.get("bucket_counts", {})
            static_count = (
                sum(
                    int(bucket_counts.get(name, 0))
                    for name in ("defer_clear_static_dominance", "defer_low_confidence_default")
                )
                if isinstance(bucket_counts, dict)
                else 0
            )
            return {
                "deck_id": request.deck_id,
                "deck_hash": deck.deck_hash,
                "method": "candidate_semantic_gate_x_diverse_cut_hypothesis_frontier",
                "candidates": ready_rows,
                "all_screened_candidates": [*semantically_ready, *semantic_deferred],
                "count": len(ready_rows),
                "pair_pool_count": len(raw_pairs),
                "preconstraint_pair_count": len(semantically_ready),
                "deferred_semantic_candidates": semantic_deferred,
                "semantic_deferred_count": len(semantic_deferred),
                "constraint_deferred_candidates": constraint_deferred,
                "constraint_deferred_count": len(constraint_deferred),
                "static_deprioritized_count": static_count,
                "candidate_recall": semantic_screen.get("candidate_recall"),
                "candidate_discoverable_count": semantic_screen.get("discoverable_candidate_count"),
                "frontier_composition": final_metrics,
                "selection_preview": selection_metrics,
                "semantic_frontier_gate": {
                    "authority": "semantic_evidence_summary",
                    "legacy_semantic_quality_is_authoritative": False,
                    "unmodeled_is_negative_evidence": False,
                    "noisy_early_simulation_elimination": False,
                },
                "cut_frontier_gate": {
                    "scalar_profile_score_is_sole_authority": False,
                    "package_axis_loss_considered": True,
                    "unique_role_loss_considered": True,
                    "commander_dependence_challenge_considered": True,
                    "whole_deck_constraints_checked_before_simulation": True,
                },
                "automatic_application": False,
            }

        return self._invoke("generate_candidate_swaps", request, work, deck_ids=(request.deck_id,))

    def generate_candidate_packages(self, request: GenerateCandidatePackagesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            result = self._package_extractor().packages_for_deck(
                request.deck_id, include_machine_candidates=True
            )
            candidates = []
            evaluations = {row["package_id"]: row for row in result.get("evaluations", [])}
            for package in result.get("curated_packages", []):
                evaluation = evaluations.get(package["package_id"], {})
                candidates.append(
                    {
                        "package_id": package["package_id"],
                        "name": package["name"],
                        "status": "candidate_swap"
                        if evaluation.get("missing_core_cards")
                        else "formally_valid",
                        "missing_core_cards": evaluation.get("missing_core_cards", []),
                        "density": evaluation.get("density", 0),
                        "failure_modes": package.get("failure_modes", []),
                        "automatic_application": False,
                    }
                )
            return {
                "deck_id": request.deck_id,
                "archetype_profile": result.get("archetype_profile"),
                "candidate_packages": candidates,
                "machine_candidates": result.get("machine_candidates", []),
                "machine_candidates_confirmed": False,
                "automatic_application": False,
            }

        return self._invoke(
            "generate_candidate_packages", request, work, deck_ids=(request.deck_id,)
        )

    def optimize_deck_against_meta(self, request: OptimizeDeckAgainstMetaInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            generated = self.generate_candidate_swaps(
                GenerateCandidateSwapsInput(
                    deck_id=request.deck_id, max_candidates=request.max_candidates
                )
            )
            if generated.status != ToolStatus.COMPLETED:
                raise ToolExecutionError("candidate generation failed")
            validated = []
            for row in generated.result.get("candidates", [])[: request.max_candidates]:
                validation = self.validate_swap(
                    ValidateSwapInput(
                        deck_id=request.deck_id,
                        swaps=(
                            VariantSwap(remove=row["remove"], add_candidate_id=row["candidate_id"]),
                        ),
                        opponent_deck_ids=request.opponent_deck_ids,
                        seed=request.seed,
                        iterations=request.iterations,
                        workers=request.workers,
                        pilot_strength=request.pilot_strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                        minimum_place_delta=0.0,
                    )
                )
                validated.append(
                    validation.result
                    if validation.status == ToolStatus.COMPLETED
                    else {
                        "candidate": row,
                        "recommendation_status": "insufficient_evidence",
                        "errors": validation.errors,
                    }
                )
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
            "optimize_deck_against_meta",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def optimize_multiple_decks_with_allocation(
        self, request: OptimizeMultipleDecksWithAllocationInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            for deck_id in request.deck_ids:
                self._require_active_optimization_target(deck_id)
            rows: list[dict[str, Any]] = []
            for deck_id in request.deck_ids:
                if deck_id not in self.decks:
                    rows.append({"deck_id": deck_id, "status": "missing", "candidates": []})
                    continue
                response = self.generate_candidate_swaps(
                    GenerateCandidateSwapsInput(
                        deck_id=deck_id, max_candidates=request.max_candidates_per_deck
                    )
                )
                rows.append(
                    {
                        "deck_id": deck_id,
                        "status": "complete",
                        "candidates": response.result.get("candidates", []),
                    }
                )
            claims: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                for candidate in row["candidates"]:
                    claims.setdefault(candidate["add"], []).append(
                        {"deck_id": row["deck_id"], **candidate}
                    )
            conflicts: list[dict[str, Any]] = []
            allocation: list[dict[str, Any]] = []
            for card_name, candidates in sorted(claims.items()):
                candidates.sort(
                    key=lambda x: (x.get("screening_delta", 0), x["deck_id"]), reverse=True
                )
                capacity = max(0, int(self.candidate_inventory.get(card_name, 0)))
                winners = candidates[:capacity]
                rejected = candidates[capacity:]
                allocation.append(
                    {
                        "card": card_name,
                        "available_free_copies": capacity,
                        "allocated_to": [row["deck_id"] for row in winners],
                        "reason": "free physical capacity then structural screening; no persistent reservation",
                    }
                )
                if rejected:
                    conflicts.append(
                        {
                            "card": card_name,
                            "available_free_copies": capacity,
                            "claims": [c["deck_id"] for c in candidates],
                            "temporarily_selected": [c["deck_id"] for c in winners],
                            "rejected_claims": [c["deck_id"] for c in rejected],
                        }
                    )
            return {
                "deck_priority": list(self.ACTIVE_OWN_DECK_IDS),
                "frozen_opponent_only_decks": sorted(self.FROZEN_OPPONENT_ONLY_DECK_IDS),
                "deck_results": rows,
                "candidate_allocation": allocation,
                "conflicts": conflicts,
                "ungrounded_double_allocation": False,
                "canonical_allocation_modified": False,
                "automatic_application": False,
            }

        return self._invoke(
            "optimize_multiple_decks_with_allocation", request, work, deck_ids=request.deck_ids
        )

    def validate_swap(self, request: ValidateSwapInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = self.validate_upgrade(
                ValidateUpgradeInput.model_validate(request.model_dump())
            ).result
            paired = result.get("paired_comparison", {})
            criteria = result.get("criteria", {})
            baseline, variant, swaps = self._build_variant(request)
            strength_profile = request.pilot_strength.value
            robustness_rows = self._politics_pod_sensitivity(
                baseline=baseline,
                variant=variant,
                opponent_deck_ids=request.opponent_deck_ids,
                pod_sizes=(3, 4, 5),
                seed=request.seed,
                iterations=request.iterations,
                max_turns=request.max_turns,
                profile_name=strength_profile,
                include_politics=True,
            )
            politics_rows = [row for row in robustness_rows if row["pod_size"] == 4]
            pod_rows = []
            for pod_size in (3, 4, 5):
                values = [
                    row["placement_improvement"]
                    for row in robustness_rows
                    if row["pod_size"] == pod_size
                ]
                pod_rows.append(
                    {
                        "pod_size": pod_size,
                        "scenario_count": len(values),
                        "mean_placement_improvement": fmean(values) if values else None,
                        "worst_case_placement_improvement": min(values) if values else None,
                    }
                )
            robustness_nonnegative = all(
                row["placement_improvement"] >= 0 for row in robustness_rows
            )
            dependency = {
                "baseline_dependency_penalty": self._commander_dependency_penalty(baseline),
                "variant_dependency_penalty": self._commander_dependency_penalty(variant),
            }
            dependency["delta"] = (
                dependency["variant_dependency_penalty"] - dependency["baseline_dependency_penalty"]
            )
            card_names = tuple(
                name for row in swaps for name in (row.get("remove"), row.get("add")) if name
            )
            tactical = self._tactical_interaction_evidence(card_names)
            xmage = self._external_probe_status("xmage")
            if not criteria.get("constraints_passed", False):
                status = "rejected"
            elif request.iterations < 100:
                status = "insufficient_evidence"
            elif (
                criteria.get("paired_passed")
                and criteria.get("holdout_passed")
                and criteria.get("sensitivity_passed")
                and robustness_nonnegative
            ):
                status = "robust_in_structural_holdout"
            elif criteria.get("paired_passed"):
                status = "structurally_supported"
            else:
                status = "insufficient_evidence"
            affected_roles = sorted(
                {
                    role.value
                    for swap in request.swaps
                    for card in (
                        next((c for c in baseline.cards if c.oracle_name == swap.remove), None),
                        self._candidate(swap.add_candidate_id, request.deck_id).card,
                    )
                    if card is not None
                    for role in card.roles
                }
            )
            holdout_values = [
                float(row.get("comparison", {}).get("placement_improvement", 0.0))
                for row in result.get("holdout_tests", [])
            ]
            pod_effects = [
                (int(row["pod_size"] or 0), float(row["mean_placement_improvement"] or 0.0))
                for row in pod_rows
                if row.get("mean_placement_improvement") is not None
            ]
            robust_objective = build_robust_objective(
                baseline=baseline,
                variant=variant,
                central_effect=float(paired.get("placement_improvement", 0.0) or 0.0),
                worst_quartile_effect=float((paired.get("quantiles") or {}).get("q25", 0.0) or 0.0),
                pair_rows=result.get("pair_sample", []),
                commander_dependency_baseline=float(dependency["baseline_dependency_penalty"]),
                commander_dependency_variant=float(dependency["variant_dependency_penalty"]),
                matchup_effects=tuple(holdout_values)
                + tuple(float(row["placement_improvement"]) for row in robustness_rows),
                pod_effects=pod_effects,
                opponent_uncertainty_effects=holdout_values,
                physical_allocation_valid=bool(criteria.get("constraints_passed", False)),
            )
            remaining = []
            if not robustness_nonnegative:
                remaining.append(
                    "at least one politics/pod-size structural sensitivity is negative"
                )
            if tactical["execution_status"] != "passed":
                remaining.append(
                    "no passing relevant Tactical Oracle case for every changed interaction"
                )
            if xmage["execution_status"] != "ready_for_real_call":
                remaining.append("XMage external rules engine unavailable")
            return {
                "current_card": swaps[0].get("remove") if swaps else None,
                "candidate_card": swaps[0].get("add") if swaps else None,
                "deck_version": self._deck(request.deck_id).deck_hash,
                "inventory_version": "read-only-canonical-2026-08-07",
                "allocation_effect": "no canonical allocation change",
                "role_changes": result.get("structural_rationale", []),
                "package_changes": [],
                "mana_effect": "structural role/profile estimate",
                "mulligan_effect": (
                    "separate mulligan-policy gate required for policy-changing swaps"
                ),
                "paired_structural_effect": paired,
                "confidence_interval": paired.get("confidence_interval"),
                "holdout_effect": result.get("holdout_tests", []),
                "worst_case_effect": min(
                    [
                        row.get("comparison", {}).get("placement_improvement", 0.0)
                        for row in result.get("holdout_tests", [])
                    ]
                    + [row["placement_improvement"] for row in robustness_rows],
                    default=0.0,
                ),
                "pilot_sensitivity": result.get("sensitivity_tests", []),
                "opponent_sensitivity": result.get("holdout_tests", []),
                "politics_sensitivity": politics_rows,
                "pod_size_sensitivity": pod_rows,
                "commander_denial_effect": dependency,
                "tactical_oracle_result": tactical,
                "xmage_result": xmage,
                "provider_disagreement": False,
                "rules_coverage": tactical["validation_level"],
                "failure_diagnosis": result.get("red_team_review", {}),
                "recommendation_status": status,
                "remaining_uncertainty": remaining,
                "robust_objective": {
                    **robust_objective.model_dump(mode="json"),
                    "equal_weight_score": robust_objective.equal_weight_score(),
                    "objective_id": "J_P5_ROBUST_OBJECTIVE_v1",
                },
                "scenario_heterogeneity": scenario_heterogeneity(
                    [float(row["placement_improvement"]) for row in robustness_rows]
                ),
                "recommendation_trace": build_recommendation_trace(
                    candidate_change=swaps,
                    constraint_status=result.get("constraint_report", {}),
                    baseline_identity={"deck_id": request.deck_id, "deck_hash": baseline.deck_hash},
                    variant_identity={"deck_id": variant.deck_id, "deck_hash": variant.deck_hash},
                    paired_seeds=tuple(int(seed) for seed in paired.get("seeds", [])),
                    affected_roles=affected_roles,
                    central_effect={
                        "placement_improvement": paired.get("placement_improvement"),
                        "effect_size": paired.get("effect_size"),
                        "monte_carlo_standard_error": paired.get("monte_carlo_standard_error"),
                        "confidence_interval": paired.get("confidence_interval"),
                        "confidence_interval_interpretation": paired.get(
                            "confidence_interval_interpretation"
                        ),
                        "raw_model_internal_p_value": paired.get("paired_randomization_p_value"),
                    },
                    worst_case_effect=min(
                        [float(row["placement_improvement"]) for row in robustness_rows]
                        + holdout_values,
                        default=float(paired.get("worst_case_result", 0.0)),
                    ),
                    sensitivity={
                        "pilot": result.get("sensitivity_tests", []),
                        "opponent": result.get("holdout_tests", []),
                        "pod_size": pod_rows,
                        "politics_visibility_heuristic": politics_rows,
                        "scenario_heterogeneity": scenario_heterogeneity(
                            [float(row["placement_improvement"]) for row in robustness_rows]
                        ),
                    },
                    holdout_status="development_only_not_J_P5_optimizer_holdout",
                    recommendation_confidence_value=recommendation_confidence(
                        constraint_valid=bool(criteria.get("constraints_passed", False)),
                        adjusted_p_value=None,
                        worst_case_effect=min(
                            [float(row["placement_improvement"]) for row in robustness_rows]
                            + holdout_values,
                            default=float(paired.get("worst_case_result", 0.0)),
                        ),
                        holdout_status="development_only_not_J_P5_optimizer_holdout",
                    ),
                ),
                "raw_validation": result,
                "automatic_application": False,
            }

        return self._invoke(
            "validate_swap",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def validate_package_change(self, request: ValidatePackageChangeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            package = self._package_extractor().inspect(request.package_id)
            evaluation = self._package_extractor().evaluate(request.deck_id, request.package_id)
            swaps = tuple(
                VariantSwap(remove=remove, add_candidate_id=add)
                for remove, add in zip(
                    request.remove_cards, request.add_candidate_ids, strict=False
                )
            )
            validation = None
            if swaps:
                validation = self.validate_swap(
                    ValidateSwapInput(
                        deck_id=request.deck_id,
                        swaps=swaps,
                        opponent_deck_ids=request.opponent_deck_ids,
                        seed=request.seed,
                        iterations=request.iterations,
                        workers=request.workers,
                        pilot_strength=request.pilot_strength,
                        pilot_mode=request.pilot_mode,
                        max_turns=request.max_turns,
                        approval_token=request.approval_token,
                        minimum_place_delta=0.0,
                    )
                ).result
            return {
                "package": package.model_dump(mode="json"),
                "baseline_evaluation": evaluation.model_dump(mode="json"),
                "swap_validation": validation,
                "recommendation_status": validation.get("recommendation_status", "candidate_swap")
                if validation
                else "candidate_swap",
                "automatic_application": False,
            }

        return self._invoke(
            "validate_package_change",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
        )

    def validate_land_change(self, request: ValidateLandChangeInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            deck = self._deck(request.deck_id)
            removed = [swap.remove for swap in request.swaps]
            if not all(
                any(card.oracle_name == name and card.is_land for card in deck.cards)
                for name in removed
            ):
                raise ToolExecutionError("validate_land_change requires land cuts")
            result = self.validate_swap(
                ValidateSwapInput.model_validate(request.model_dump())
            ).result
            result["land_change_gate"] = "passed"
            return result

        return self._invoke(
            "validate_land_change",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def validate_mulligan_policy(self, request: ValidateMulliganPolicyInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._require_active_optimization_target(request.deck_id)
            aliases = {"balanced": "current_pilot", "commander_plan": "commander_oriented"}
            policies = (
                aliases.get(request.baseline_policy, request.baseline_policy),
                aliases.get(request.candidate_policy, request.candidate_policy),
            )
            response = self.compare_mulligan_policies(
                CompareMulliganPoliciesInput(
                    deck_id=request.deck_id,
                    policies=policies,
                    samples=request.samples,
                    followup_samples=min(250, request.samples),
                    seed=request.seed,
                )
            )
            if response.status != ToolStatus.COMPLETED:
                raise ToolExecutionError("mulligan comparison failed")
            return {
                "validation_level": "structural_only",
                "policies": policies,
                "comparison": response.result,
                "recommendation_status": "structurally_supported",
                "automatic_application": False,
            }

        return self._invoke(
            "validate_mulligan_policy",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
        )

    def run_rules_coverage_gate(self, request: RunRulesCoverageGateInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            registry = self._read_optional_json("data/rules/card_rules_coverage.json", {})
            cards = registry.get("cards", [])
            prefixes = self._coverage_version_prefixes(request.deck_id)
            selected = [
                row
                for row in cards
                if any(
                    version.startswith(prefix)
                    for version in row.get("deck_versions", [])
                    for prefix in prefixes
                )
            ]
            if request.card_names:
                wanted = set(request.card_names)
                selected = [row for row in selected if row.get("oracle_name") in wanted]
            statuses = Counter(row.get("coverage_status", "unsupported") for row in selected)
            external = (
                all(row.get("xmage_rules_verified") for row in selected) if selected else False
            )
            return {
                "deck_id": request.deck_id,
                "cards_checked": len(selected),
                "coverage_version_prefixes": list(prefixes),
                "coverage_counts": dict(statuses),
                "external_engine_execution_status": registry.get(
                    "external_engine_execution_status", "blocked"
                ),
                "external_gate_passed": external,
                "gate_status": "passed"
                if (external or not request.require_external)
                else "blocked",
                "highest_validation_level": "external_rules_engine"
                if external
                else ("tactical_oracle" if statuses.get("tactical_only") else "structural_only"),
                "unsupported_cards": [
                    row.get("oracle_name")
                    for row in selected
                    if row.get("coverage_status") == "unsupported"
                ],
            }

        return self._invoke("run_rules_coverage_gate", request, work, deck_ids=(request.deck_id,))

    def run_multifidelity_comparison(
        self, request: RunMultifidelityComparisonInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            structural = self.validate_swap(
                ValidateSwapInput.model_validate(
                    request.model_dump(
                        exclude={"include_tactical_oracle", "request_external_engine"}
                    )
                )
            ).result
            cards = tuple(
                card
                for card in (structural.get("current_card"), structural.get("candidate_card"))
                if card
            )
            coverage = self.run_rules_coverage_gate(
                RunRulesCoverageGateInput(
                    deck_id=request.deck_id,
                    card_names=cards,
                    require_external=request.request_external_engine,
                )
            ).result
            tactical = (
                self._tactical_interaction_evidence(cards)
                if request.include_tactical_oracle
                else {"execution_status": "not_run", "validation_level": "structural_only"}
            )
            external_results: dict[str, Any] = {}
            if request.request_external_engine:
                for provider in ("xmage",):
                    external_results[provider] = self.run_engine_backed_matchup(
                        RunEngineBackedMatchupInput(
                            deck_ids=(request.deck_id, *request.opponent_deck_ids),
                            provider=provider,
                            seed=request.seed,
                            iterations=1,
                            workers=1,
                            pilot_strength=request.pilot_strength,
                            pilot_mode=request.pilot_mode,
                            max_turns=request.max_turns,
                            approval_token=request.approval_token,
                        )
                    ).result
            status = structural.get("recommendation_status", "insufficient_evidence")
            if (
                status == "robust_in_structural_holdout"
                and tactical.get("execution_status") == "passed"
            ):
                status = "tactical_oracle_supported"
            passed_external = [
                p for p, row in external_results.items() if row.get("execution_status") == "passed"
            ]
            if (
                status == "tactical_oracle_supported"
                and coverage.get("external_gate_passed")
                and passed_external
            ):
                status = "external_engine_supported"
            return {
                "formal_gate": "passed"
                if structural.get("recommendation_status") != "rejected"
                else "failed",
                "structural_result": structural,
                "tactical_oracle_result": tactical,
                "external_rules_result": external_results
                if request.request_external_engine
                else {"execution_status": "not_run"},
                "coverage_gate": coverage,
                "recommendation_status": status,
                "evidence_ladder": [
                    "candidate_swap",
                    "formally_valid",
                    "structurally_supported",
                    "robust_in_structural_holdout",
                    "tactical_oracle_supported",
                    "external_engine_supported",
                ],
                "automatic_application": False,
            }

        return self._invoke(
            "run_multifidelity_comparison",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def run_engine_backed_matchup(self, request: RunEngineBackedMatchupInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            manager = RulesEngineManager(root=self.root)
            try:
                adapter = manager.xmage
                probe = adapter.probe()
                if (
                    probe.availability.value != "available"
                    or probe.capabilities.runtime_kind != "external_rules_engine"
                ):
                    return {
                        "execution_status": "blocked",
                        "validation_level": "structural_only",
                        "provider": request.provider,
                        "provider_status": probe.availability.value,
                        "runtime_kind": probe.capabilities.runtime_kind,
                        "reason": "; ".join(probe.details)
                        or "external provider handshake unavailable",
                        "external_rules_engine_observations": 0,
                        "synthetic_or_tactical_substitution": False,
                    }
                rules_decks = load_project_rules_decks(self.root)
                missing = [deck_id for deck_id in request.deck_ids if deck_id not in rules_decks]
                if missing:
                    return {
                        "execution_status": "blocked",
                        "validation_level": "structural_only",
                        "provider": request.provider,
                        "provider_status": "available",
                        "reason": f"rules-engine deck exports missing for: {missing}",
                        "external_rules_engine_observations": 0,
                        "synthetic_or_tactical_substitution": False,
                    }
                observations: list[dict[str, Any]] = []
                for index in range(request.iterations):
                    handles = [
                        adapter.load_deck(rules_decks[deck_id]) for deck_id in request.deck_ids
                    ]
                    game = adapter.start_commander_game(
                        RulesGameRequest(
                            game_id=f"engine-backed-{request.provider}-{request.seed}-{index}",
                            deck_handles=tuple(handle.handle_id for handle in handles),
                            seed=request.seed + index,
                            starting_player_seat=index % len(handles),
                        )
                    )
                    actions = adapter.get_legal_actions(game.session_id)
                    submitted = False
                    if actions:
                        action = actions[0]
                        adapter.submit_action(
                            game.session_id,
                            ActionProposal(
                                proposal_id=f"engine-backed-action-{index}",
                                actor_id=action.actor_id,
                                legal_action_id=action.action_id,
                                action_type=action.action_type,
                                policy_name="external_engine_acceptance",
                            ),
                        )
                        submitted = True
                    logs = adapter.get_logs(game.session_id)
                    replay = (
                        adapter.export_replay(game.session_id)
                        if probe.capabilities.replay_supported
                        else None
                    )
                    observations.append(
                        {
                            "game_id": game.game_id,
                            "legal_action_count": len(actions),
                            "action_submitted": submitted,
                            "event_count": len(logs.events),
                            "replay_exported": replay is not None,
                        }
                    )
                full = all(
                    row["legal_action_count"] > 0
                    and row["action_submitted"]
                    and row["event_count"] > 0
                    and row["replay_exported"]
                    for row in observations
                )
                return {
                    "execution_status": "passed" if full else "passed_with_limitations",
                    "validation_level": "external_rules_engine",
                    "provider": request.provider,
                    "provider_status": "available",
                    "runtime_kind": "external_rules_engine",
                    "external_rules_engine_observations": len(observations),
                    "observations": observations,
                    "synthetic_or_tactical_substitution": False,
                }
            except Exception as exc:
                return {
                    "execution_status": "failed",
                    "validation_level": "structural_only",
                    "provider": request.provider,
                    "provider_status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "external_rules_engine_observations": 0,
                    "synthetic_or_tactical_substitution": False,
                }
            finally:
                manager.close()

        return self._invoke(
            "run_engine_backed_matchup",
            request,
            work,
            deck_ids=request.deck_ids,
            seed=request.seed,
            iterations=request.iterations,
            estimate_type="external_rules_engine_results",
        )

    def run_robustness_suite(self, request: RunRobustnessSuiteInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            baseline, variant, _ = self._build_variant(request)
            profile_name = request.pilot_strength.value
            rows = self._politics_pod_sensitivity(
                baseline=baseline,
                variant=variant,
                opponent_deck_ids=request.opponent_deck_ids,
                pod_sizes=request.include_pod_sizes,
                seed=request.seed,
                iterations=request.iterations,
                max_turns=request.max_turns,
                profile_name=profile_name,
                include_politics=request.include_politics,
            )
            worst = min((row["placement_improvement"] for row in rows), default=0.0)
            mean = fmean(row["placement_improvement"] for row in rows) if rows else 0.0
            status = (
                "robust_in_structural_holdout" if rows and worst >= 0 else "insufficient_evidence"
            )
            return {
                "validation_level": "structural_only",
                "execution_status": "passed",
                "scenario_count": len(rows),
                "pod_sizes": list(request.include_pod_sizes),
                "politics_included": request.include_politics,
                "politics_regimes": list(POLITICS_REGIMES)
                if request.include_politics
                else ["rational_threat_focus"],
                "scenario_results": rows,
                "mean_effect": mean,
                "worst_case_effect": worst,
                "recommendation_status": status,
                "automatic_application": False,
            }

        return self._invoke(
            "run_robustness_suite",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def rank_variants(self, request: RankVariantsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            def score(row: dict[str, Any]) -> tuple[float, float, float]:
                worst = float(row.get("worst_case_effect", -999.0) or 0.0)
                paired = float(
                    (row.get("paired_structural_effect") or {}).get(
                        "placement_improvement", row.get("effect_size", 0.0)
                    )
                    or 0.0
                )
                coverage_key = str(row.get("rules_coverage") or "")
                coverage = {
                    "external_rules_engine": 3,
                    "tactical_oracle": 2,
                    "structural_only": 1,
                }.get(coverage_key, 0)
                return (worst if request.prefer_worst_case else paired, paired, float(coverage))

            ranked = sorted((dict(row) for row in request.variants), key=score, reverse=True)
            p_rows: list[tuple[int, float]] = []
            for index, row in enumerate(ranked):
                raw_p = row.get("p_value")
                if raw_p is None:
                    raw_p = (row.get("paired_structural_effect") or {}).get(
                        "paired_randomization_p_value"
                    )
                if isinstance(raw_p, (int, float)) and not isinstance(raw_p, bool):
                    row["raw_model_internal_p_value"] = float(raw_p)
                    p_rows.append((index, float(raw_p)))
            if p_rows:
                adjusted = holm_adjust(value for _, value in p_rows)
                for (index, _), value in zip(p_rows, adjusted, strict=True):
                    ranked[index]["holm_adjusted_p_value"] = value
            for index, row in enumerate(ranked, start=1):
                row["rank"] = index
            return {
                "ranked_variants": ranked,
                "method": "worst_case_then_paired_then_coverage",
                "multiple_testing_method": "Holm family-wise correction over the ranked variant family using paired model-internal randomization p-values when available",
                "selection_policy": "constraint gate -> staged structural preselection -> robust/worst-case ranking -> Holm-adjusted family -> independent optimizer holdout",
                "automatic_application": False,
            }

        return self._invoke("rank_variants", request, work)

    def explain_recommendation(self, request: ExplainRecommendationInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            evidence = request.evidence
            return {
                "recommendation_status": evidence.get(
                    "recommendation_status", "insufficient_evidence"
                ),
                "summary": (
                    f"{evidence.get('current_card', 'current card')} → "
                    f"{evidence.get('candidate_card', 'candidate card')}"
                ),
                "why": evidence.get("role_changes", []),
                "tradeoffs": {
                    "worst_case_effect": evidence.get("worst_case_effect"),
                    "remaining_uncertainty": evidence.get("remaining_uncertainty", []),
                    "provider_disagreement": evidence.get("provider_disagreement", False),
                },
                "truth_boundary": (
                    "Structural results are model estimates; Tactical Oracle is not an external "
                    "rules engine."
                ),
                "automatic_application": False,
            }

        return self._invoke("explain_recommendation", request, work)

    def export_recommendation_evidence(
        self, request: ExportRecommendationEvidenceInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            target_dir = self.root / "data/runs/recommendations"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / Path(request.output_name).name
            atomic_write_json(
                target,
                {"schema_version": 1, "automatic_application": False, "evidence": request.evidence},
            )
            return {
                "path": str(target),
                "sha256": sha256_value(request.evidence),
                "canonical_files_modified": False,
            }

        return self._invoke("export_recommendation_evidence", request, work)

    def create_deck_improvement_report(
        self, request: CreateDeckImprovementReportInput
    ) -> ToolResponse:
        def work() -> dict[str, Any]:
            target = self.report_dir / Path(request.output_name).name
            lines = [
                f"# Deck improvement report — {request.deck_id}",
                "",
                "Validation boundary: structural model estimates unless an individual "
                "evidence item explicitly records a higher executed level.",
                "",
                "No deck, inventory, or allocation change was applied.",
                "",
            ]
            for index, item in enumerate(request.evidence_items, start=1):
                lines += [
                    f"## Candidate {index}",
                    "",
                    f"- Status: `{item.get('recommendation_status', 'insufficient_evidence')}`",
                    f"- Swap: `{item.get('current_card')}` → `{item.get('candidate_card')}`",
                    f"- Worst-case effect: `{item.get('worst_case_effect')}`",
                    f"- Rules coverage: `{item.get('rules_coverage', 'structural_only')}`",
                    "",
                ]
            atomic_write_text(target, "\n".join(lines))
            return {
                "report_path": str(target),
                "evidence_items": len(request.evidence_items),
                "automatic_application": False,
            }

        return self._invoke(
            "create_deck_improvement_report", request, work, deck_ids=(request.deck_id,)
        )

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
                lines.extend(
                    [
                        f"## Evidence {index}",
                        "",
                        "```json",
                        json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True),
                        "```",
                        "",
                    ]
                )
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
                profile
                for profile in profiles
                if (
                    request.commander_family is None
                    or profile.commander_family == request.commander_family
                )
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
                "parameter_hash_matches_registry": profile.parameter_hash
                == PilotRegistry(self.root).profile(profile.pilot_name).parameter_hash,
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
                self.root
                / "data/runs/pilot_ensembles"
                / Path(request.output_name).name
                / "pilot_benchmark.json"
            )
            return payload

        return self._invoke(
            "run_pilot_benchmark",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
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
            "compare_pilots",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
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
            baseline_name = (
                "KorvoldPilot" if request.deck_id.startswith("korvold/") else "RogShaiPilot"
            )
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
            output = (
                self.root
                / "data/runs/pilot_ensembles"
                / Path(request.output_name).name
                / "ensemble_summary.json"
            )
            atomic_write_json(output, summary)
            summary["result_path"] = str(output)
            return summary

        return self._invoke(
            "run_pilot_ensemble",
            request,
            work,
            deck_ids=(request.deck_id, *request.opponent_deck_ids),
            seed=request.seed,
            iterations=request.iterations,
        )

    def test_variant_across_pilots(self, request: TestVariantAcrossPilotsInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            if (
                request.baseline_deck_id not in self.decks
                or request.variant_deck_id not in self.decks
            ):
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
            output = (
                self.root / "data/runs/pilot_ensembles" / f"{Path(request.output_name).name}.json"
            )
            atomic_write_json(output, result)
            result["result_path"] = str(output)
            return result

        return self._invoke(
            "test_variant_across_pilots",
            request,
            work,
            deck_ids=(
                request.baseline_deck_id,
                request.variant_deck_id,
                *request.opponent_deck_ids,
            ),
            seed=request.seed,
            iterations=request.iterations,
        )

    def generate_pilot_robustness_report(
        self, request: GeneratePilotRobustnessReportInput
    ) -> ToolResponse:
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
            target = (
                self.root
                / "data/runs/mulligan_lab"
                / f"{request.deck_id.replace('/', '_')}-{request.seed}-hands.jsonl"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            first_samples = []
            with target.open("w", encoding="utf-8") as handle:
                for index, attempts in enumerate(
                    lab.iter_draw_sequences(
                        deck,
                        samples=request.samples,
                        seed=request.seed,
                        max_mulligans=request.max_mulligans,
                    )
                ):
                    serialized = [[card.oracle_name for card in hand] for hand in attempts]
                    if index < 10:
                        first_samples.append(serialized)
                    handle.write(
                        json.dumps(
                            {
                                "sample_id": index,
                                "deck_id": request.deck_id,
                                "deck_hash": deck.deck_hash,
                                "attempts": serialized,
                                "seed": request.seed,
                                "common_random_numbers_ready": True,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
            return {
                "dataset_path": str(target.relative_to(self.root)),
                "samples": request.samples,
                "attempts_per_sample": request.max_mulligans + 1,
                "first_samples": first_samples,
                "commander_in_command_zone": list(deck.commander_names),
                "estimate_type": "structural_model_estimates",
            }

        return self._invoke(
            "sample_opening_hands",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
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
                selected.append(rows[index])
                used[name] += 1
            context = self._mulligan_context_from_request(request)
            evaluation = lab.evaluate(deck, selected, MulliganPolicyName(request.policy), context)
            return evaluation.model_dump(mode="json") | {
                "deck_hash": deck.deck_hash,
                "commander_in_command_zone": list(deck.commander_names),
                "absolute_rule": False,
            }

        return self._invoke(
            "evaluate_opening_hand", request, work, deck_ids=(request.deck_id,), seed=request.seed
        )

    def compare_mulligan_policies(self, request: CompareMulliganPoliciesInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.samples * max(1, len(request.policies)), request.approval_token
            )
            lab = self._mulligan_lab()
            context = self._mulligan_context_from_request(request)
            result = lab.run(
                context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                samples=request.samples,
                followup_samples=request.followup_samples,
                generate_keep_rules=request.generate_keep_rules,
            )
            return result.model_dump(mode="json")

        return self._invoke(
            "compare_mulligan_policies",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
        )

    def run_mulligan_lab(self, request: RunMulliganLabInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            self._check_iterations(
                request.samples * max(1, len(request.policies)), request.approval_token
            )
            lab = self._mulligan_lab()
            context = self._mulligan_context_from_request(request)
            result = lab.run(
                context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                samples=request.samples,
                followup_samples=request.followup_samples,
                generate_keep_rules=request.generate_keep_rules,
            )
            target = self.root / "data/runs/mulligan_lab" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {
                "result_path": str(target.relative_to(self.root))
            }

        return self._invoke(
            "run_mulligan_lab",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.samples,
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
            lab = self._mulligan_lab()
            deck = self._deck(request.deck_id)
            if rule.deck_hash != deck.deck_hash:
                raise ToolExecutionError("keep rule deck hash does not match current deck")
            pool: dict[str, list[Any]] = {}
            for card in lab._library(deck):
                pool.setdefault(card.oracle_name, []).append(card)
            used: Counter[str] = Counter()
            cards = []
            for name in request.card_names:
                idx = used[name]
                choices = pool.get(name, [])
                if idx >= len(choices):
                    raise ToolExecutionError(f"card not available in deck: {name}")
                cards.append(choices[idx])
                used[name] += 1
            features = lab.features(deck, cards)
            return lab.test_rule(rule, features) | {"features": features.model_dump(mode="json")}

        return self._invoke("test_keep_rule", request, work, deck_ids=(request.deck_id,))

    def create_mulligan_report(self, request: CreateMulliganReportInput) -> ToolResponse:
        def work() -> dict[str, Any]:
            result = MulliganLabResult.model_validate_json(
                self._project_path(request.result_path).read_text(encoding="utf-8")
            )
            lines = [
                "# Mulligan Lab Report",
                "",
                f"Deck: `{result.context.deck_id}`",
                f"Deck hash: `{result.context.deck_hash}`",
                f"Samples: {result.sample_count}",
                "",
                "All keep rules and follow-up outcomes are model-based structural estimates.",
                "",
                "## Policy comparison",
                "",
                "| Policy | First-seven keep | Mulligan rate | Avg mulligans | "
                "Color issues | Structural placement |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for row in result.policies:
                placement = (
                    "n/a"
                    if row.structural_placement_mean is None
                    else f"{row.structural_placement_mean:.3f}"
                )
                lines.append(
                    f"| {row.policy.value} | {row.keep_rate_first_seven:.3f} | "
                    f"{row.mulligan_rate:.3f} | "
                    f"{row.average_mulligans:.3f} | {row.color_problem_rate:.3f} | {placement} |"
                )
            lines.extend(
                [
                    "",
                    "## Boundaries",
                    "",
                    "- Hand quality is separated from complete matchup performance.",
                    "- No rule is universal or empirically proven.",
                    "- No external rules engine was used.",
                ]
            )
            target = self.root / "data/runs/mulligan_lab" / Path(request.output_name).name
            atomic_write_text(target, "\n".join(lines) + "\n")
            return {
                "report_path": str(target.relative_to(self.root)),
                "model_based": True,
                "automatic_deck_changes": False,
            }

        return self._invoke("create_mulligan_report", request, work)

    def _counterfactual_lab(self) -> CounterfactualReplayLab:
        from commander_lab.counterfactual import CounterfactualReplayLab

        return CounterfactualReplayLab(self.root, external_engine_available=False)

    def find_counterfactual_branchpoints(self, request: Any) -> ToolResponse:
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

    def list_alternative_actions(self, request: Any) -> ToolResponse:
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

    def run_counterfactual(self, request: Any) -> ToolResponse:
        from commander_lab.models import (
            CounterfactualEngineMode,
            HiddenInformationPolicy,
            SeedPolicy,
        )

        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            result = lab.run(
                branch,
                alternative_action=request.alternative_action,
                expected_state_hash=request.expected_state_hash,
                hidden_information_policy=HiddenInformationPolicy(
                    request.hidden_information_policy
                ),
                engine_mode=CounterfactualEngineMode(request.engine_mode),
                seed_policy=SeedPolicy(request.seed_policy),
                seed=request.seed,
                future_samples=request.future_samples,
                workers=request.workers,
            )
            target = self.root / "data/runs/counterfactual" / Path(request.output_name).name
            atomic_write_json(target, result.model_dump(mode="json"))
            return result.model_dump(mode="json") | {
                "result_path": str(target.relative_to(self.root))
            }

        return self._invoke(
            "run_counterfactual",
            request,
            work,
            seed=request.seed,
            iterations=request.future_samples,
        )

    def compare_counterfactuals(self, request: Any) -> ToolResponse:
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
            return result.model_dump(mode="json") | {
                "result_path": str(target.relative_to(self.root))
            }

        return self._invoke("compare_counterfactuals", request, work)

    def generate_decision_regret_report(self, request: Any) -> ToolResponse:
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

    def export_minimal_counterfactual_fixture(self, request: Any) -> ToolResponse:
        def work() -> dict[str, Any]:
            lab = self._counterfactual_lab()
            branch = lab.branchpoint_at(request.source_path, request.event_offset)
            lab.verify_branchpoint(branch, request.expected_state_hash)
            target = self.root / "data/evals/golden" / Path(request.output_name).name
            payload = lab.export_fixture(branch, target)
            return payload | {"fixture_path": str(target.relative_to(self.root))}

        return self._invoke("export_minimal_counterfactual_fixture", request, work)

    def _diagnostic_engine(self) -> DecisionDiagnosticEngine:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        return DecisionDiagnosticEngine()

    def diagnose_card_performance(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.card_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("diagnose_card_performance", request, work)

    def diagnose_pilot_behavior(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.pilot_name)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("diagnose_pilot_behavior", request, work)

    def compare_deck_and_pilot_effects(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            result = self._diagnostic_engine().compare_effects(dataset)
            return result.model_dump(mode="json") | {"causal_identification": False}

        return self._invoke("compare_deck_and_pilot_effects", request, work)

    def classify_failure_cause(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine

        def work() -> dict[str, Any]:
            dataset = DecisionDiagnosticEngine.load(self._project_path(request.dataset_path))
            diagnosis = self._diagnostic_engine().classify(dataset, request.subject)
            target = self.root / "data/runs/diagnostics" / Path(request.output_name).name
            atomic_write_json(target, diagnosis.model_dump(mode="json"))
            return diagnosis.model_dump(mode="json") | {
                "diagnosis_path": str(target.relative_to(self.root))
            }

        return self._invoke("classify_failure_cause", request, work)

    def recommend_next_experiment(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord

        def work() -> dict[str, Any]:
            diagnosis = DiagnosisRecord.model_validate_json(
                self._project_path(request.diagnosis_path).read_text(encoding="utf-8")
            )
            return DecisionDiagnosticEngine.next_experiment(diagnosis)

        return self._invoke("recommend_next_experiment", request, work)

    def generate_diagnostic_report(self, request: Any) -> ToolResponse:
        from commander_lab.diagnostics import DecisionDiagnosticEngine
        from commander_lab.models import DiagnosisRecord

        def work() -> dict[str, Any]:
            diagnoses = [
                DiagnosisRecord.model_validate_json(
                    self._project_path(path).read_text(encoding="utf-8")
                )
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

    def deck_decision_prepare(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                facade = PriorityWorkflowFacade(
                    self.root,
                    service=self,
                    context=session.context,
                )
                screen = facade.build_screen(request.deck_id, limit=request.candidate_limit)
                mana = facade.mulligan_mana(request.deck_id)
                validation = self._validate_deck_payload(
                    ValidateDeckInput(deck_id=request.deck_id, include_physical_allocation=True)
                )
                mulligan_request = CompareMulliganPoliciesInput(
                    deck_id=request.deck_id,
                    policies=request.mulligan_policies,
                    samples=request.mulligan_samples,
                    followup_samples=0,
                    seat_position=request.seat_position,
                    starting_player=request.seat_position == 1,
                    pod_size=4,
                    pilot_profile_id="rogshai.current.baseline",
                    pilot_version="current",
                    game_plan="balanced",
                    seed=request.mulligan_seed,
                    generate_keep_rules=False,
                )
                mulligan_context = self._mulligan_context_from_request(mulligan_request)
                mulligan_baseline = facade.mulligan.run(
                    mulligan_context,
                    tuple(MulliganPolicyName(value) for value in request.mulligan_policies),
                    samples=request.mulligan_samples,
                    followup_samples=0,
                    generate_keep_rules=False,
                ).model_dump(mode="json")
            session_identity = session.identity()
            return {
                "workflow": "deck_decision_prepare",
                "context": screen["context"],
                "deck_id": request.deck_id,
                "deck_hash": screen["deck_hash"],
                "validation": {
                    "active_deck": request.deck_id in facade.context.active_own_deck_ids,
                    "physical_legal_candidates": screen["eligible_candidate_count"],
                    "candidate_recall": screen["challenge_benchmark"]["legal_candidate_recall"],
                    "deck": validation,
                },
                "candidate_coverage": screen,
                "mana_mulligan_baseline": mana,
                "mulligan_policy_baseline": mulligan_baseline,
                "keep_rule_research_executed": False,
                "model_informativeness_status": "requires_structural_baseline_before_search",
                "next_call": "deck_decision_run",
                "workflow_session": session_identity,
                "automatic_deck_mutation": False,
            }

        return self._invoke(
            "deck_decision_prepare",
            request,
            work,
            deck_ids=(request.deck_id,),
        )

    def deck_decision_run(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                facade = PriorityWorkflowFacade(
                    self.root,
                    service=self,
                    context=session.context,
                )
                result = facade.compare_validate(
                    deck_id=request.deck_id,
                    remove=request.remove,
                    add_candidate_id=request.add_candidate_id,
                    iterations=request.iterations,
                    seed=request.seed,
                    max_turns=request.max_turns,
                    workers=request.workers,
                )
            result["workflow_session"] = session.identity()
            result["execution_envelope"] = {
                "requested_workers": request.workers,
                "effective_workers": 1,
                "worker_fallback_applied": request.workers != 1,
                "default_max_simulation_seconds": float(self.limits.max_simulation_seconds),
                "requested_max_simulation_seconds": request.max_simulation_seconds,
                "effective_max_simulation_seconds": (
                    float(request.max_simulation_seconds)
                    if request.max_simulation_seconds is not None
                    else float(self.limits.max_simulation_seconds)
                ),
                "classification": "execution_envelope_only_not_deck_quality_evidence",
            }
            return result

        return self._invoke(
            "deck_decision_run",
            request,
            work,
            deck_ids=(request.deck_id,),
            seed=request.seed,
            iterations=request.iterations,
        )

    def deck_decision_diagnose(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                result: dict[str, Any] = dict(
                    PriorityWorkflowFacade.diagnose_next_experiment(
                        request.comparison,
                        cohort_comparisons=tuple(request.cohort_comparisons),
                        opponent_evidence_quality=dict(request.opponent_evidence_quality),
                        failure_mode_metrics=tuple(request.failure_mode_metrics),
                    )
                )
            result["workflow_session"] = session.identity()
            return result

        return self._invoke("deck_decision_diagnose", request, work)

    def deck_decision_bundle(self, request: Any) -> ToolResponse:
        from commander_lab.priority_workflows import PriorityWorkflowFacade
        from commander_lab.workflow_session import WorkflowSession

        def work() -> dict[str, Any]:
            with WorkflowSession.open(self.root, service=self) as session:
                facade = PriorityWorkflowFacade(
                    self.root,
                    service=self,
                    context=session.context,
                )
                result: dict[str, Any] = dict(
                    facade.create_decision_bundle(
                        request.comparison,
                        self._project_path(request.output_directory),
                        worst_case_sensitivity_result=request.worst_case_sensitivity_result,
                        commander_denial_result=request.commander_denial_result,
                        ablation_result=request.ablation_result,
                        recommendation_status=request.recommendation_status,
                    )
                )
            result["workflow_session"] = session.identity()
            return result

        return self._invoke("deck_decision_bundle", request, work)
