from __future__ import annotations

from statistics import fmean
from typing import TYPE_CHECKING, Any

from commander_lab.cut_frontier import build_static_swap_rows, select_diverse_swap_frontier
from commander_lab.engine.rules import (
    RulesEngineManager,
    TacticalRuleOracle,
    load_interaction_catalog,
)
from commander_lab.models import (
    BuildOptimizationContextInput,
    GenerateCandidatePackagesInput,
    GenerateCandidateSwapsInput,
    OptimizeDeckAgainstMetaInput,
    OptimizeMultipleDecksWithAllocationInput,
    StructuralDeckProfile,
    ToolResponse,
    ToolStatus,
    ValidateLandChangeInput,
    ValidateMulliganPolicyInput,
    ValidatePackageChangeInput,
    ValidateSwapInput,
    ValidateUpgradeInput,
    VariantSwap,
)
from commander_lab.models.tooling import (
    CompareMulliganPoliciesInput,
)
from commander_lab.optimization import (
    build_recommendation_trace,
    build_robust_objective,
    build_search_candidate,
    recommendation_confidence,
    run_paired_structural_comparison,
    scenario_heterogeneity,
)
from commander_lab.robustness import POLITICS_REGIMES, pilot_config_for

if TYPE_CHECKING:
    pass

from .service_core import (
    ToolExecutionError,
)
from .service_mulligan import ServiceMulliganMixin
from .service_search import ServiceSearchMixin


class ServiceOptimizerMixin(ServiceSearchMixin, ServiceMulliganMixin):
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
