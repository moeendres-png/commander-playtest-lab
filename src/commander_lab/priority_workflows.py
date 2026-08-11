from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from commander_lab.decision_bundle import DecisionBundle, write_decision_bundle
from commander_lab.mana_analysis import ManaAnalyzer
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, VariantSwap
from commander_lab.mulligan import MulliganLab
from commander_lab.optimization import build_search_candidate, run_paired_structural_comparison
from commander_lab.project_context import ProjectContextSnapshot, load_project_context
from commander_lab.tools.current_candidates import canonical_feature_fusion_summary
from commander_lab.tools.service import CommanderToolService


class PriorityWorkflowFacade:
    """Small deterministic facade for the common Build → Test → Diagnose workflow.

    Low-level tools remain available. This facade only composes them in a safe order and never
    changes canonical deck, inventory, allocation, purchase, or opponent-frequency data.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.context = load_project_context(self.root)
        self.service = CommanderToolService(self.root)
        self.mulligan = MulliganLab(self.root)
        self.mana = ManaAnalyzer(self.root)

    def _deck(self, deck_id: str):
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
        }

    def build_screen(self, deck_id: str, *, limit: int = 25) -> dict[str, Any]:
        """Return physical/current candidate coverage without pretending it is a final ranking."""
        if limit < 1:
            raise ValueError("limit must be positive")
        baseline = self._deck(deck_id)
        candidates = [
            candidate
            for candidate in self.service.candidates.values()
            if deck_id in candidate.allowed_deck_ids
            and self.service.candidate_inventory.get(candidate.card.oracle_name, 0) > 0
        ]
        candidates.sort(
            key=lambda candidate: (
                -int(
                    any(
                        source.source_type == "canonical_drive_derived_projection"
                        for source in candidate.card.sources
                    )
                ),
                candidate.card.oracle_name.casefold(),
            )
        )
        rows = [
            {
                "candidate_id": candidate.candidate_id,
                "oracle_name": candidate.card.oracle_name,
                "roles": sorted(role.value for role in candidate.card.roles),
                "package_ids": sorted(candidate.card.package_ids),
                "source_quality": candidate.card.source_quality.value,
                "canonical_feature_overlay": any(
                    source.source_type == "canonical_drive_derived_projection"
                    for source in candidate.card.sources
                ),
                "physical_status": candidate.physical_status,
            }
            for candidate in candidates[:limit]
        ]
        return {
            "workflow": "build_screen",
            "evidence_class": "structural_candidate_screening",
            "deck_id": deck_id,
            "deck_hash": baseline.deck_hash,
            "context": self._context_payload(self.context),
            "eligible_candidate_count": len(candidates),
            "feature_fusion": canonical_feature_fusion_summary(self.root),
            "mana": asdict(self.mana.analyze_deck(baseline)),
            "candidates": rows,
            "ranking_claim": "none; ordering prefers current canonical feature coverage, then name",
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
    ) -> dict[str, Any]:
        """Build one legal swap and run the existing J-P5 paired CRN comparison."""
        if iterations < 1:
            raise ValueError("iterations must be positive")
        baseline = self._deck(deck_id)
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
                "context": self._context_payload(self.context),
            }
        opponents = tuple(
            self._deck(opponent_id)
            for opponent_id in self.context.primary_opponent_deck_ids(deck_id)
        )
        metrics, pairs = run_paired_structural_comparison(
            baseline=baseline,
            variant=built.variant,
            opponents=opponents,
            iterations=iterations,
            seed=seed,
            pilot_config=PilotConfig(
                strength=PilotStrength.STRONG,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            max_turns=max_turns,
            pair_id=f"priority-{deck_id}-{built.variant.deck_hash[:12]}",
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
            },
            "context": self._context_payload(self.context),
            "constraint_report": built.constraint_report.model_dump(mode="json"),
            "screening_score": built.screening_score,
            "rationale": list(built.rationale),
            "paired": metrics.as_dict(),
            "pair_count": len(pairs),
            "mana_before": asdict(self.mana.analyze_deck(baseline)),
            "mana_after": asdict(self.mana.analyze_deck(built.variant)),
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
    def diagnose_next_experiment(comparison: dict[str, Any]) -> dict[str, str]:
        if comparison.get("status") != "completed":
            return {
                "workflow": "diagnose_next_experiment",
                "next_experiment": "repair_constraints_or_choose_another_candidate",
                "reason": "the candidate did not pass the hard-constraint gate",
            }
        paired = comparison.get("paired", {})
        lower = float(paired.get("distributionally_robust_lower_bound", 0.0))
        interval = paired.get("confidence_interval", (0.0, 0.0))
        low = float(interval[0]) if isinstance(interval, (list, tuple)) and interval else 0.0
        high = float(interval[1]) if isinstance(interval, (list, tuple)) and len(interval) > 1 else 0.0
        if lower > 0.0 and low > 0.0:
            next_experiment = "run_sensitivity_then_commander_denial"
            reason = "central paired structural evidence is directionally positive and separated"
        elif low <= 0.0 <= high:
            next_experiment = "run_more_paired_seeds_or_sensitivity"
            reason = "the current model-internal interval crosses zero"
        else:
            next_experiment = "stop_or_return_to_candidate_screening"
            reason = "current paired structural evidence does not support advancing this variant"
        return {
            "workflow": "diagnose_next_experiment",
            "next_experiment": next_experiment,
            "reason": reason,
        }

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
        bundle = DecisionBundle(
            bundle_version="1.0",
            baseline_identity=dict(comparison.get("baseline_identity", {})),
            variant_identity=dict(comparison.get("variant_identity", {})),
            context_snapshot=dict(comparison.get("context", self._context_payload(self.context))),
            physical_legal_validation=dict(comparison.get("constraint_report", {})),
            feature_confidence_summary=canonical_feature_fusion_summary(self.root),
            mana_impact={
                "before": comparison.get("mana_before", {}),
                "after": comparison.get("mana_after", {}),
            },
            central_paired_result=paired,
            worst_case_sensitivity_result=worst_case_sensitivity_result or {},
            commander_denial_result=commander_denial_result or {},
            ablation_result=ablation_result or {},
            cache_provenance={
                "status": "not_implemented_due_active_J_P6_concurrency_guard",
                "cache_hit": False,
            },
            simulation_counts={
                "requested_runs": paired.get("requested_runs", 0),
                "valid_runs": paired.get("valid_runs", 0),
            },
            stopping_reason="explicit workflow completion; no adaptive racing applied",
            evidence_class="structural_model_estimates",
            known_limitations=(
                "Structural simulation is not an empirical Commander winrate.",
                "Tactical Oracle is not an external rules engine.",
                "Opponent uncertainty remains source-evidence dependent.",
                "No adaptive scheduler/result cache was added while J-P6 owns performance hardening.",
            ),
            recommendation_status=recommendation_status,
        )
        return write_decision_bundle(bundle, output_directory)


__all__ = ["PriorityWorkflowFacade"]
