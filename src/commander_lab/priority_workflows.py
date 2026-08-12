from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from commander_lab.advancement import decide_advancement
from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.decision_bundle import DecisionBundle, write_decision_bundle
from commander_lab.decision_information import build_decision_information_state
from commander_lab.mana_analysis import ManaAnalyzer
from commander_lab.model_informativeness import assess_model_informativeness
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralDeckProfile,
    VariantSwap,
)
from commander_lab.mulligan import MulliganLab
from commander_lab.optimization import (
    build_search_candidate,
    derive_paired_seed,
    run_paired_structural_comparison,
)
from commander_lab.playstyle import PlaystyleAnalyzer
from commander_lab.project_context import ProjectContextSnapshot, load_project_context
from commander_lab.storage import ExactResultCache, build_exact_result_identity
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.current_candidates import canonical_feature_fusion_summary
from commander_lab.tools.service import CommanderToolService
from commander_lab.variant_identity import build_variant_identity
from commander_lab.workflow_identity import build_priority_comparison_identity


class PriorityWorkflowFacade:
    """Deterministic Build → Test → Diagnose facade for current RogShai decisions."""

    def __init__(
        self,
        root: str | Path,
        *,
        result_cache_path: str | Path | None = None,
        service: CommanderToolService | None = None,
        context: ProjectContextSnapshot | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.context = context or load_project_context(self.root)
        self.service = service or CommanderToolService(self.root)
        self.mulligan = MulliganLab(self.root)
        self.mana = ManaAnalyzer(self.root)
        self.playstyle = PlaystyleAnalyzer(self.root)
        self.screener = RogShaiCandidateScreener(self.root, service=self.service)
        cache_path = (
            Path(result_cache_path).resolve()
            if result_cache_path is not None
            else self.root / ".runtime/priority_result_cache.sqlite3"
        )
        self.result_cache = ExactResultCache(cache_path, root=self.root)

    def _deck(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self.service.decks[deck_id]
        except KeyError as exc:
            raise ValueError(f"unknown deck: {deck_id}") from exc

    @staticmethod
    def _context_payload(context: ProjectContextSnapshot) -> dict[str, Any]:
        return {
            "snapshot_hash": context.snapshot_hash,
            "engine_version": context.engine_version,
            "source_hashes": dict(context.source_hashes),
            "source_freshness": dict(context.source_freshness),
            "active_own_deck_ids": list(context.active_own_deck_ids),
            "historical_own_deck_ids": list(context.historical_own_deck_ids),
            "active_deck_hashes": dict(context.active_deck_hashes),
            "policy_config_hashes": dict(context.policy_config_hashes),
            "playstyle_preference_type": context.playstyle_preference_type,
            "playstyle_preference_hash": context.playstyle_preference_hash,
        }

    def build_screen(self, deck_id: str, *, limit: int = 25) -> dict[str, Any]:
        if deck_id != "rogshai/current":
            raise ValueError("priority build_screen is scoped to current RogShai")
        if limit < 1:
            raise ValueError("limit must be positive")
        baseline = self._deck(deck_id)
        screened = self.screener.screen_pool(deck_id)
        rows = screened["rows"]
        if not isinstance(rows, list):
            raise RuntimeError("candidate screen rows must be a list")
        return {
            "workflow": "build_screen",
            "evidence_class": "structural_candidate_screening",
            "deck_id": deck_id,
            "deck_hash": baseline.deck_hash,
            "context": self._context_payload(self.context),
            "eligible_candidate_count": screened["physical_legal_candidate_count"],
            "candidate_pool_after_default_screen": screened["candidate_pool_after_default_screen"],
            "bucket_counts": screened["bucket_counts"],
            "feature_fusion": canonical_feature_fusion_summary(self.root),
            "challenge_benchmark": self.screener.benchmark_challenge_set(),
            "mana": asdict(self.mana.analyze_deck(baseline)),
            "candidates": rows[:limit],
            "unusual_candidates_remain_explorable": True,
            "playstyle_policy": "post_build_review_only",
            "playstyle_review_status": "deferred_until_decision_bundle",
            "playstyle_used_for_screening_or_ranking": False,
            "ranking_claim": (
                "conservative static structural screen only; no empirical card-power ranking"
            ),
        }

    def compare_validate(
        self,
        *,
        deck_id: str,
        remove: str,
        add_candidate_id: str,
        iterations: int = 8,
        seed: int = 20260811,
        max_turns: int = 14,
        workers: int = 1,
    ) -> dict[str, Any]:
        if deck_id != "rogshai/current":
            raise ValueError("priority compare_validate is scoped to current RogShai")
        if iterations < 1:
            raise ValueError("iterations must be positive")
        if workers < 1:
            raise ValueError("workers must be positive")
        baseline = self._deck(deck_id)
        static_screen = self.screener.screen_swap(
            baseline=baseline,
            remove=remove,
            add_candidate_id=add_candidate_id,
        )
        swap = VariantSwap(remove=remove, add_candidate_id=add_candidate_id)
        built = build_search_candidate(
            baseline,
            (swap,),
            self.service.candidates,
            self.service._optimization_constraints(deck_id),
            inventory=self.service.candidate_inventory,
            verified_physical_names=self.service.verified_candidate_names,
        )
        if not built.constraint_report.valid:
            return {
                "workflow": "compare_validate",
                "status": "rejected_by_hard_constraints",
                "constraint_report": built.constraint_report.model_dump(mode="json"),
                "static_screen": static_screen.as_dict(),
                "context": self._context_payload(self.context),
            }

        opponents = tuple(
            self._deck(opponent_id)
            for opponent_id in self.context.primary_opponent_deck_ids(deck_id)
        )
        pilot_config = PilotConfig(
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
        pair_id = f"priority-{deck_id}-{built.variant.deck_hash[:12]}"
        paired_seeds = tuple(
            derive_paired_seed(seed, pair_id, index) for index in range(iterations)
        )
        analysis_seed = derive_paired_seed(seed, pair_id, iterations + 1)
        pilot_hash = sha256_run_value(pilot_config, root=self.root)
        optimizer_hash = sha256_run_value(
            self.service._optimization_constraints(deck_id), root=self.root
        )
        workflow_identity = build_priority_comparison_identity(self.context)
        cache_identity = build_exact_result_identity(
            engine_version=self.context.engine_version,
            deck_hashes=(baseline.deck_hash, built.variant.deck_hash),
            opponent_hashes=tuple(deck.deck_hash for deck in opponents),
            pilot_hashes=(pilot_hash,),
            canonical_context_snapshot=workflow_identity.identity_hash,
            scenario={
                "deck_id": deck_id,
                "opponent_deck_ids": [deck.deck_id for deck in opponents],
                "starting_player_seat": None,
            },
            simulation_config={
                "iterations": iterations,
                "master_seed": seed,
                "analysis_seed": analysis_seed,
                "max_turns": max_turns,
                "pair_id": pair_id,
                "workers": workers,
            },
            exact_seed_set=paired_seeds,
            policy_config_hashes={
                "pilot_config": pilot_hash,
                "optimization_constraints": optimizer_hash,
            },
        )

        def compute() -> dict[str, Any]:
            metrics, pairs = run_paired_structural_comparison(
                baseline=baseline,
                variant=built.variant,
                opponents=opponents,
                iterations=iterations,
                seed=seed,
                pilot_config=pilot_config,
                max_turns=max_turns,
                pair_id=pair_id,
                workers=workers,
            )
            return {"paired": metrics.as_dict(), "pairs": pairs}

        cached = self.result_cache.get_or_compute(
            cache_identity,
            evidence_class="structural_model_estimates",
            compute=compute,
        )
        paired = dict(cached.result["paired"])
        pairs = list(cached.result["pairs"])
        mana_before = self.mana.analyze_deck(baseline)
        mana_after = self.mana.analyze_deck(built.variant)
        mana_delta = self.mana.compare_decks(baseline, built.variant)
        removed_card = next(card for card in baseline.cards if card.oracle_name == remove)
        functional_groups = tuple(
            sorted(
                {
                    *(role.value for role in removed_card.roles),
                    *(role.value for role in built.additions[0].card.roles),
                }
            )
        )
        canonical_variant = build_variant_identity(
            baseline_deck_hash=baseline.deck_hash,
            variant_deck_hash=built.variant.deck_hash,
            context_snapshot_hash=self.context.snapshot_hash,
            deck_diff=((remove, built.additions[0].card.oracle_name),),
            package_diff=built.additions[0].card.package_ids,
            functional_replacement_groups=functional_groups,
        )
        return {
            "workflow": "compare_validate",
            "status": "completed",
            "evidence_class": "structural_model_estimates",
            "baseline_identity": {"deck_id": deck_id, "deck_hash": baseline.deck_hash},
            "variant_identity": {
                "deck_id": built.variant.deck_id,
                "deck_hash": built.variant.deck_hash,
                "remove": remove,
                "add_candidate_id": add_candidate_id,
                "add": built.additions[0].card.oracle_name,
                "canonical_variant": canonical_variant.as_dict(),
            },
            "context": self._context_payload(self.context),
            "workflow_semantic_identity": workflow_identity.as_dict(),
            "constraint_report": built.constraint_report.model_dump(mode="json"),
            "static_screen": static_screen.as_dict(),
            "playstyle_review_status": "deferred_until_decision_bundle",
            "screening_score": built.screening_score,
            "rationale": list(built.rationale),
            "paired": paired,
            "pair_count": len(pairs),
            "paired_observations": pairs,
            "mana_before": asdict(mana_before),
            "mana_after": asdict(mana_after),
            "mana_delta": asdict(mana_delta),
            "cache_provenance": {
                "cache_key": cached.cache_key,
                "cache_hit": cached.cache_hit,
                "evidence_class": cached.evidence_class,
                "governance_context_hash": self.context.snapshot_hash,
                "workflow_semantic_identity_hash": workflow_identity.identity_hash,
                "exact_seed_count": len(paired_seeds),
                "exact_seed_set_sha256": sha256_run_value(paired_seeds, root=self.root),
            },
            "truth_boundary": "model-internal paired structural comparison, not empirical gameplay",
        }

    def mulligan_mana(self, deck_id: str) -> dict[str, Any]:
        deck = self._deck(deck_id)
        return {
            "workflow": "mulligan_mana",
            "deck_id": deck_id,
            "deck_hash": deck.deck_hash,
            "context": self._context_payload(self.context),
            "primary_opponents": list(self.context.primary_opponent_deck_ids(deck_id)),
            "mana": asdict(self.mulligan.analyze_deck_mana(deck_id)),
            "evidence_class": "derived_structural_mana_analysis",
        }

    @staticmethod
    def diagnose_next_experiment(comparison: dict[str, Any]) -> dict[str, Any]:
        model_informativeness = comparison.get("model_informativeness")
        if not isinstance(model_informativeness, dict):
            model_informativeness = {}
        opponent_uncertainty = comparison.get("opponent_uncertainty")
        scenario_spread: float | None = None
        if isinstance(opponent_uncertainty, dict):
            raw_spread = opponent_uncertainty.get("scenario_spread")
            if isinstance(raw_spread, (int, float)) and not isinstance(raw_spread, bool):
                scenario_spread = float(raw_spread)
        raw_missing = comparison.get("missing_semantic_axes", ())
        missing_semantic_axes = (
            tuple(str(value) for value in raw_missing)
            if isinstance(raw_missing, (list, tuple))
            else ()
        )
        raw_failure = comparison.get("failure_mode_differences", ())
        failure_mode_differences = (
            tuple(str(value) for value in raw_failure)
            if isinstance(raw_failure, (list, tuple))
            else ()
        )
        state = build_decision_information_state(
            comparison,
            model_informativeness=model_informativeness,
            scenario_spread=scenario_spread,
            missing_semantic_axes=missing_semantic_axes,
            failure_mode_differences=failure_mode_differences,
            tactical_evidence_required=comparison.get("tactical_evidence_required") is True,
        )
        return {
            "workflow": "diagnose_next_experiment",
            "next_experiment": state.next_recommended_experiment,
            "reason": state.stop_reason,
            "decision_information_state": state.as_dict(),
        }

    @staticmethod
    def model_informativeness(
        *,
        baseline_place_1_share: float | None,
        seat_results: dict[str, Any] | None,
        variant_comparisons: tuple[dict[str, Any], ...] = (),
        opponent_evidence_quality: dict[str, int] | None = None,
        failure_mode_metrics: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return assess_model_informativeness(
            baseline_place_1_share=baseline_place_1_share,
            seat_results=seat_results,
            variant_comparisons=variant_comparisons,
            opponent_evidence_quality=opponent_evidence_quality,
            failure_mode_metrics=failure_mode_metrics,
        ).as_dict()

    @staticmethod
    def advancement_decision(
        comparison: dict[str, Any],
        *,
        model_informativeness: dict[str, Any] | None = None,
        profile_required: bool = False,
    ) -> dict[str, Any]:
        return decide_advancement(
            comparison,
            model_informativeness=model_informativeness,
            profile_required=profile_required,
        ).as_dict()

    def create_decision_bundle(
        self,
        comparison: dict[str, Any],
        output_directory: str | Path,
        *,
        worst_case_sensitivity_result: dict[str, Any] | None = None,
        commander_denial_result: dict[str, Any] | None = None,
        ablation_result: dict[str, Any] | None = None,
        recommendation_status: str = "structural_evidence_only",
    ) -> dict[str, str]:
        paired = dict(comparison.get("paired", {}))
        playstyle_review = self._post_build_playstyle_review(comparison)
        informativeness = comparison.get("model_informativeness", {})
        advancement = comparison.get("advancement_decision", {})
        decision_information = comparison.get("decision_information_state")
        if not isinstance(decision_information, dict):
            decision_information = self.diagnose_next_experiment(comparison)[
                "decision_information_state"
            ]
        bundle = DecisionBundle(
            bundle_version="1.3",
            baseline_identity=dict(comparison.get("baseline_identity", {})),
            variant_identity=dict(comparison.get("variant_identity", {})),
            context_snapshot=dict(comparison.get("context", self._context_payload(self.context))),
            physical_legal_validation=dict(comparison.get("constraint_report", {})),
            feature_confidence_summary=canonical_feature_fusion_summary(self.root),
            mana_impact={
                "before": comparison.get("mana_before", {}),
                "after": comparison.get("mana_after", {}),
                "delta": comparison.get("mana_delta", {}),
            },
            playstyle_fit_summary=playstyle_review,
            central_paired_result=paired,
            worst_case_sensitivity_result=worst_case_sensitivity_result or {},
            commander_denial_result=commander_denial_result or {},
            ablation_result=ablation_result or {},
            cache_provenance=dict(comparison.get("cache_provenance", {})),
            simulation_counts={
                "requested_runs": paired.get("requested_runs", 0),
                "valid_runs": paired.get("valid_runs", 0),
                "cache_hit": comparison.get("cache_provenance", {}).get("cache_hit", False),
            },
            stopping_reason="explicit workflow completion; adaptive racing evaluated separately",
            evidence_class="structural_model_estimates",
            known_limitations=(
                "Structural simulation is not an empirical Commander winrate.",
                "Tactical Oracle is not an external rules engine.",
                "Opponent uncertainty remains source-evidence dependent.",
                "Playstyle review is qualitative, post-build-only, and separate from recommendation status.",
                "Exact cache reuse is valid only for identical simulation identity inputs.",
                "Adaptive racing ships only after a frozen benchmark preserves decision quality.",
            ),
            recommendation_status=recommendation_status,
            extra={
                "model_informativeness": informativeness,
                "advancement_decision": advancement,
                "decision_information_state": decision_information,
                "workflow_semantic_identity": comparison.get("workflow_semantic_identity", {}),
                "opponent_uncertainty": comparison.get("opponent_uncertainty", {}),
                "next_best_experiment": self.diagnose_next_experiment(comparison),
                "executed_evidence": {
                    "commander_denial": bool(commander_denial_result),
                    "ablation": bool(ablation_result),
                    "sensitivity": bool(worst_case_sensitivity_result),
                },
            },
        )
        return write_decision_bundle(bundle, output_directory)

    def _post_build_playstyle_review(self, comparison: dict[str, Any]) -> dict[str, object]:
        variant = comparison.get("variant_identity")
        baseline = comparison.get("baseline_identity")
        if not isinstance(variant, dict) or not isinstance(baseline, dict):
            return {
                "preference_type": "post_build_review_only",
                "status": "not_available_without_variant_identity",
                "separate_from_recommendation_status": True,
            }
        deck_id = str(baseline.get("deck_id", ""))
        remove_name = str(variant.get("remove", ""))
        candidate_id = str(variant.get("add_candidate_id", ""))
        deck = self._deck(deck_id)
        removed = next((card for card in deck.cards if card.oracle_name == remove_name), None)
        candidate = self.service.candidates.get(candidate_id)
        if removed is None or candidate is None:
            return {
                "preference_type": "post_build_review_only",
                "status": "not_available_for_unresolved_variant_identity",
                "separate_from_recommendation_status": True,
            }
        review = self.playstyle.compare_cards(removed, candidate.card)
        review["status"] = "completed_after_objective_decision"
        review["separate_from_recommendation_status"] = True
        return review


__all__ = ["PriorityWorkflowFacade"]
