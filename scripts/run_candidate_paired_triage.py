from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from commander_lab.candidate_evaluation import build_candidate_evaluation_plan
from commander_lab.deck_registry import load_deck_policy_registry
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/candidate_evaluation/CURRENT_PAIRED_CANDIDATE_TRIAGE.json"
DEFAULT_INITIAL_ITERATIONS = 8
DEFAULT_REFINED_ITERATIONS = 32
MASTER_SEED = 20260818
MAX_TURNS = 14
MORE_SIMULATIONS_USEFUL = "MORE_SIMULATIONS_USEFUL"
STOP_WITH_PREFERENCE = "STOP_WITH_PREFERENCE"
MODEL_NEEDS_DIFFERENT_METRIC = "MODEL_NEEDS_DIFFERENT_METRIC"
MODEL_INFORMATION_LIMIT = "MODEL_INFORMATION_LIMIT"


def _source_hashes() -> dict[str, str | None]:
    registry = load_deck_policy_registry(ROOT)
    source_names = (
        "active_scope",
        "deck_manifest",
        "inventory_snapshot",
        "candidate_eligibility",
        "optimization_availability",
        "inactive_release_delta",
    )
    return {name: registry.source_hash(name, required=False) for name in source_names}


def _decision_information_status(next_experiment: dict[str, Any]) -> str:
    state = next_experiment.get("decision_information_state")
    if not isinstance(state, dict):
        return "UNKNOWN"
    return str(state.get("status", "UNKNOWN"))


def _compact_stage(
    comparison: dict[str, Any],
    *,
    advancement: dict[str, Any],
    next_experiment: dict[str, Any],
) -> dict[str, Any]:
    observations = comparison.get("paired_observations", ())
    if not isinstance(observations, list):
        observations = []
    return {
        "baseline_identity": comparison.get("baseline_identity", {}),
        "variant_identity": comparison.get("variant_identity", {}),
        "workflow_semantic_identity": comparison.get("workflow_semantic_identity", {}),
        "constraint_report": comparison.get("constraint_report", {}),
        "paired": comparison.get("paired", {}),
        "paired_observations_sha256": sha256_run_value(observations, root=ROOT),
        "mana_delta": comparison.get("mana_delta", {}),
        "cache_provenance": comparison.get("cache_provenance", {}),
        "incremental_execution": comparison.get("incremental_execution", {}),
        "precision_context": comparison.get("precision_context", {}),
        "advancement_decision": advancement,
        "next_experiment": next_experiment,
        "decision_information_status": _decision_information_status(next_experiment),
        "evidence_class": comparison.get("evidence_class"),
        "final_recommendation": False,
        "truth_boundary": (
            "within-variant paired structural precision evidence only; not empirical gameplay "
            "and not a direct cross-variant ranking"
        ),
    }


def _run_stage(
    facade: PriorityWorkflowFacade,
    *,
    deck_id: str,
    remove: str,
    candidate_id: str,
    iterations: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    comparison = facade.compare_validate(
        deck_id=deck_id,
        remove=remove,
        add_candidate_id=candidate_id,
        iterations=iterations,
        seed=MASTER_SEED,
        max_turns=MAX_TURNS,
        workers=1,
    )
    if comparison.get("status") != "completed":
        raise SystemExit(
            f"paired triage comparison failed for {remove} -> {candidate_id}: "
            f"{comparison.get('status')}"
        )
    if comparison.get("evidence_class") != "structural_model_estimates":
        raise SystemExit("paired triage lost its structural evidence class")
    advancement = facade.advancement_decision(comparison)
    next_experiment = facade.diagnose_next_experiment(comparison)
    return (
        _compact_stage(
            comparison,
            advancement=advancement,
            next_experiment=next_experiment,
        ),
        comparison,
    )


def main() -> None:
    initial_iterations = int(
        os.environ.get("CANDIDATE_TRIAGE_INITIAL_ITERATIONS", str(DEFAULT_INITIAL_ITERATIONS))
    )
    refined_iterations = int(
        os.environ.get("CANDIDATE_TRIAGE_REFINED_ITERATIONS", str(DEFAULT_REFINED_ITERATIONS))
    )
    if initial_iterations < 1:
        raise SystemExit("CANDIDATE_TRIAGE_INITIAL_ITERATIONS must be positive")
    if refined_iterations <= initial_iterations:
        raise SystemExit(
            "CANDIDATE_TRIAGE_REFINED_ITERATIONS must exceed the initial iteration count"
        )

    before = _source_hashes()
    registry = load_deck_policy_registry(ROOT)
    deck_id = registry.primary_deck_id
    service = CommanderToolService(ROOT)
    plan = build_candidate_evaluation_plan(
        ROOT,
        service=service,
        registry=registry,
        deck_id=deck_id,
        max_pairs=16,
        max_pairs_per_candidate=2,
        max_cut_hypotheses=24,
        max_candidate_queue=64,
    )
    frontier = plan.get("variant_frontier")
    if not isinstance(frontier, list) or not frontier:
        raise SystemExit("candidate evaluation produced no variant frontier")

    facade = PriorityWorkflowFacade(
        ROOT,
        result_cache_path=ROOT / ".runtime/candidate_paired_triage.sqlite3",
        service=service,
    )
    rows: list[dict[str, Any]] = []
    final_comparisons: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    initial_status_counts: Counter[str] = Counter()
    pairwise_final_status_counts: Counter[str] = Counter()
    pairwise_final_advancement_counts: Counter[str] = Counter()
    total_newly_simulated_pairs = 0
    total_reused_prefix_pairs = 0
    refinement_count = 0

    for frontier_row in frontier:
        provenance = frontier_row.get("candidate_provenance")
        if not isinstance(provenance, dict):
            raise SystemExit("frontier row has no candidate provenance")
        availability = provenance.get("availability")
        if availability != "physical_free":
            skipped.append(
                {
                    "test_order": frontier_row.get("test_order"),
                    "remove": frontier_row.get("remove"),
                    "add": frontier_row.get("add"),
                    "availability": availability,
                    "reason": (
                        "current PriorityWorkflowFacade enforces physical inventory; "
                        "hypothetical paired execution requires an explicit simulation-only adapter"
                    ),
                    "final_recommendation": False,
                }
            )
            continue

        candidate_id = frontier_row.get("profile_candidate_id")
        remove = frontier_row.get("remove")
        if not isinstance(candidate_id, str) or not isinstance(remove, str):
            raise SystemExit("frontier row has unresolved physical candidate identity")
        candidate = service.candidates.get(candidate_id)
        if candidate is None:
            raise SystemExit(
                f"frontier candidate is missing from structural repository: {candidate_id}"
            )
        if candidate.card.oracle_name != frontier_row.get("add"):
            raise SystemExit(f"frontier/profile candidate identity mismatch: {candidate_id}")

        initial, initial_comparison = _run_stage(
            facade,
            deck_id=deck_id,
            remove=remove,
            candidate_id=candidate_id,
            iterations=initial_iterations,
        )
        initial_status = str(initial["decision_information_status"])
        initial_status_counts[initial_status] += 1
        initial_incremental = initial.get("incremental_execution")
        if isinstance(initial_incremental, dict):
            total_newly_simulated_pairs += int(
                initial_incremental.get("incremental_simulated_count", 0)
            )

        refined: dict[str, Any] | None = None
        final_stage = initial
        final_comparison = initial_comparison
        if initial_status == MORE_SIMULATIONS_USEFUL:
            next_experiment = initial.get("next_experiment")
            if not isinstance(next_experiment, dict):
                raise SystemExit("MORE_SIMULATIONS_USEFUL row has no next-experiment contract")
            state = next_experiment.get("decision_information_state")
            if not isinstance(state, dict):
                raise SystemExit("MORE_SIMULATIONS_USEFUL row has no decision-information state")
            current_iterations = state.get("current_iterations")
            precision_ceiling = state.get("precision_ceiling")
            if current_iterations != initial_iterations:
                raise SystemExit("decision-information state does not match initial paired budget")
            if not isinstance(precision_ceiling, int) or refined_iterations > precision_ceiling:
                raise SystemExit("requested refined precision exceeds preregistered ceiling")
            if next_experiment.get("next_experiment") != "run_next_paired_micro_batch":
                raise SystemExit("precision refinement was not the recommended next experiment")

            refined, refined_comparison = _run_stage(
                facade,
                deck_id=deck_id,
                remove=remove,
                candidate_id=candidate_id,
                iterations=refined_iterations,
            )
            refinement_count += 1
            incremental = refined.get("incremental_execution")
            if not isinstance(incremental, dict):
                raise SystemExit("refined paired stage lost incremental execution provenance")
            reused_prefix = incremental.get("reused_prefix_count")
            simulated_suffix = incremental.get("incremental_simulated_count")
            if reused_prefix != initial_iterations:
                raise SystemExit(
                    "refined paired stage did not reuse the exact initial paired prefix: "
                    f"expected={initial_iterations} actual={reused_prefix}"
                )
            expected_suffix = refined_iterations - initial_iterations
            if simulated_suffix != expected_suffix:
                raise SystemExit(
                    "refined paired stage simulated an unexpected suffix: "
                    f"expected={expected_suffix} actual={simulated_suffix}"
                )
            total_reused_prefix_pairs += int(reused_prefix)
            total_newly_simulated_pairs += int(simulated_suffix)
            final_stage = refined
            final_comparison = refined_comparison

        pairwise_final_status = str(final_stage["decision_information_status"])
        pairwise_final_status_counts[pairwise_final_status] += 1
        advancement = final_stage.get("advancement_decision")
        advancement_status = (
            str(advancement.get("status", "unknown"))
            if isinstance(advancement, dict)
            else "unknown"
        )
        pairwise_final_advancement_counts[advancement_status] += 1

        rows.append(
            {
                "test_order": frontier_row["test_order"],
                "remove": frontier_row["remove"],
                "add": frontier_row["add"],
                "profile_candidate_id": frontier_row["profile_candidate_id"],
                "candidate_provenance": frontier_row["candidate_provenance"],
                "package_ids": frontier_row.get("package_ids", ()),
                "initial_stage": initial,
                "refined_stage": refined,
                "final_stage": "refined" if refined is not None else "initial",
                "pairwise_final_decision_information_status": pairwise_final_status,
                "pairwise_final_advancement_status": advancement_status,
                "eligible_for_finalist_followup": False,
                "final_recommendation": False,
                "truth_boundary": (
                    "adaptive within-candidate structural precision triage only; not empirical "
                    "gameplay and not a direct cross-candidate ranking"
                ),
            }
        )
        final_comparisons.append(final_comparison)

    if len(rows) != len(final_comparisons):
        raise SystemExit("paired triage lost row/comparison alignment")

    cohort = tuple(final_comparisons)
    cohort_status_counts: Counter[str] = Counter()
    cohort_model_reports: list[dict[str, Any]] = []
    for row, comparison in zip(rows, final_comparisons, strict=True):
        cohort_diagnosis = facade.diagnose_next_experiment(
            comparison,
            cohort_comparisons=cohort,
            failure_mode_metrics=(),
        )
        cohort_status = _decision_information_status(cohort_diagnosis)
        cohort_status_counts[cohort_status] += 1
        model_informativeness = cohort_diagnosis.get("model_informativeness")
        if not isinstance(model_informativeness, dict):
            raise SystemExit("cohort diagnosis lost model-informativeness evidence")
        cohort_model_reports.append(model_informativeness)
        row["cohort_diagnosis"] = cohort_diagnosis
        row["cohort_decision_information_status"] = cohort_status
        row["eligible_for_finalist_followup"] = (
            cohort_status == STOP_WITH_PREFERENCE
            and row["pairwise_final_advancement_status"] == "advance"
        )

    model_report_hashes = {
        str(report.get("report_hash"))
        for report in cohort_model_reports
        if report.get("report_hash")
    }
    if len(model_report_hashes) > 1:
        raise SystemExit("cohort diagnosis produced inconsistent model-informativeness reports")
    cohort_model_informativeness = cohort_model_reports[0] if cohort_model_reports else {}

    after = _source_hashes()
    if before != after:
        raise SystemExit("paired candidate triage changed a configured source")

    final_valid_runs = 0
    finalist_count = 0
    for row in rows:
        stage_name = row["final_stage"]
        stage = row["refined_stage"] if stage_name == "refined" else row["initial_stage"]
        if isinstance(stage, dict):
            paired = stage.get("paired")
            if isinstance(paired, dict):
                final_valid_runs += int(paired.get("valid_runs", 0))
        if row["eligible_for_finalist_followup"] is True:
            finalist_count += 1

    model_limit = cohort_model_informativeness.get("status") == MODEL_INFORMATION_LIMIT
    if model_limit and finalist_count:
        raise SystemExit(
            "model-information limit cannot simultaneously authorize finalist followup"
        )

    payload: dict[str, Any] = {
        "schema_version": "1.2.0",
        "artifact_type": "adaptive_paired_candidate_triage",
        "evidence_class": "structural_model_estimates",
        "cohort_diagnostic_evidence_class": "structural_model_diagnostic",
        "deck_id": deck_id,
        "deck_hash": plan["deck_hash"],
        "frontier_plan_hash": plan["plan_hash"],
        "frontier_candidate_count": len(frontier),
        "executed_variant_count": len(rows),
        "skipped_variant_count": len(skipped),
        "initial_iterations_per_variant": initial_iterations,
        "refined_iterations_per_open_variant": refined_iterations,
        "refinement_candidate_count": refinement_count,
        "master_seed": MASTER_SEED,
        "max_turns": MAX_TURNS,
        "primary_opponent_ids": plan.get("suggested_opponent_ids", ()),
        "within_variant_pairing": True,
        "direct_cross_variant_pairing": False,
        "direct_cross_variant_ranking_allowed": False,
        "total_newly_simulated_pairs": total_newly_simulated_pairs,
        "total_reused_prefix_pairs": total_reused_prefix_pairs,
        "total_final_valid_paired_runs": final_valid_runs,
        "initial_decision_information_status_counts": dict(sorted(initial_status_counts.items())),
        "final_decision_information_status_counts": dict(
            sorted(pairwise_final_status_counts.items())
        ),
        "final_advancement_status_counts": dict(sorted(pairwise_final_advancement_counts.items())),
        "cohort_decision_information_status_counts": dict(sorted(cohort_status_counts.items())),
        "cohort_model_informativeness": cohort_model_informativeness,
        "cohort_diagnostic_inputs": {
            "failure_mode_metrics": [],
            "opponent_evidence_quality": {},
            "note": (
                "No synthetic opponent-frequency weights or unsupported failure metrics were "
                "invented for this diagnostic."
            ),
        },
        "model_information_limit_detected": model_limit,
        "eligible_for_finalist_followup_count": finalist_count,
        "results": rows,
        "skipped": skipped,
        "next_stage_policy": {
            "MODEL_INFORMATION_LIMIT": (
                "use existing continuous failure-mode metrics and narrower preregistered "
                "hypotheses before adding more same-model seeds"
            ),
            "eligible_for_finalist_followup": (
                "only cohort STOP_WITH_PREFERENCE plus advancement=advance may receive targeted "
                "denial/ablation/sensitivity budget"
            ),
            "MORE_SIMULATIONS_USEFUL": (
                "additional same-model precision is subordinate to the cohort model-information "
                "diagnostic"
            ),
            "NO_MATERIAL_DECISION_DIFFERENCE": "stop_without_material_structural_preference",
            "STOP": "stop_or_return_to_candidate_screening",
            "MODEL_NEEDS_DIFFERENT_METRIC": "resolve_model_or_semantic_limit_before_more_seeds",
            "OPPONENT_UNCERTAINTY_DOMINATES": "test_declared_opponent_uncertainty_not_more_seeds",
        },
        "canonical_mutation_performed": False,
        "inventory_reservation_performed": False,
        "purchase_decision_performed": False,
        "final_recommendation": False,
        "known_limitations": [
            "Thirty-two paired iterations remain structural precision evidence, not final truth.",
            "Pairing is baseline-versus-variant within each candidate, not across candidates.",
            "Structural placement/share outputs are model estimates, not empirical Commander winrates.",
            "Cohort informativeness is a model diagnostic, not a card-strength ranking.",
            "No explicit failure-mode metric is supplied in this first cohort diagnostic.",
            "Hypothetical test cards are not executed by the physical-only priority adapter.",
        ],
        "truth_boundary": (
            "adaptive paired structural candidate triage plus cohort model diagnostic; no empirical "
            "gameplay claim, no direct cross-variant ranking, no inventory mutation, and no final "
            "deck recommendation"
        ),
    }
    payload["triage_hash"] = sha256_run_value(payload, root=ROOT)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"PAIRED_TRIAGE_HASH={payload['triage_hash']}")
    print(f"PAIRED_TRIAGE_DECK={deck_id}")
    print(f"FRONTIER_CANDIDATES={len(frontier)}")
    print(f"EXECUTED_VARIANTS={len(rows)}")
    print(f"SKIPPED_VARIANTS={len(skipped)}")
    print(f"REFINEMENT_CANDIDATES={refinement_count}")
    print(f"TOTAL_NEWLY_SIMULATED_PAIRS={total_newly_simulated_pairs}")
    print(f"TOTAL_REUSED_PREFIX_PAIRS={total_reused_prefix_pairs}")
    print(f"TOTAL_FINAL_VALID_PAIRED_RUNS={final_valid_runs}")
    print(
        "INITIAL_DECISION_INFORMATION_STATUS_COUNTS="
        + json.dumps(dict(sorted(initial_status_counts.items())))
    )
    print(
        "PAIRWISE_FINAL_DECISION_INFORMATION_STATUS_COUNTS="
        + json.dumps(dict(sorted(pairwise_final_status_counts.items())))
    )
    print(
        "COHORT_DECISION_INFORMATION_STATUS_COUNTS="
        + json.dumps(dict(sorted(cohort_status_counts.items())))
    )
    print(f"COHORT_MODEL_INFORMATION_STATUS={cohort_model_informativeness.get('status')}")
    print(f"MODEL_INFORMATION_LIMIT_DETECTED={str(model_limit).lower()}")
    print(f"ELIGIBLE_FOR_FINALIST_FOLLOWUP={finalist_count}")
    print(
        "PAIRED_TRIAGE_BOUNDARY=structural_precision_plus_model_diagnostic_not_final_recommendation"
    )


if __name__ == "__main__":
    main()
