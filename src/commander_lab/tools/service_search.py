from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

from commander_lab.models import (
    BeamSearchInput,
    CandidatePackage,
    CardAblationInput,
    LocalSearchInput,
    OptimizationVariant,
    PackageSearchInput,
    ParetoFrontInput,
    SearchVariantsInput,
    ShapleyInput,
    SwapMatrixInput,
    ToolResponse,
    ToolStatus,
    ValidateUpgradeInput,
    VariantSwap,
)
from commander_lab.optimization import (
    SearchCandidate,
    all_legal_single_swaps,
    approximate_shapley_profile,
    build_search_candidate,
    evaluate_constraints,
    pareto_front,
    profile_score,
)
from commander_lab.storage import (
    sha256_value,
)

if TYPE_CHECKING:
    pass

from .service_core import (
    ToolExecutionError,
)
from .service_simulation import ServiceSimulationMixin


class ServiceSearchMixin(ServiceSimulationMixin):
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
