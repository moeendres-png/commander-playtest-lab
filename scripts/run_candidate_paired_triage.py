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
DEFAULT_ITERATIONS = 8
MASTER_SEED = 20260818
MAX_TURNS = 14


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


def _compact_result(
    frontier_row: dict[str, Any],
    comparison: dict[str, Any],
    *,
    advancement: dict[str, Any],
    next_experiment: dict[str, Any],
) -> dict[str, Any]:
    observations = comparison.get("paired_observations", ())
    if not isinstance(observations, list):
        observations = []
    return {
        "test_order": frontier_row["test_order"],
        "remove": frontier_row["remove"],
        "add": frontier_row["add"],
        "profile_candidate_id": frontier_row["profile_candidate_id"],
        "candidate_provenance": frontier_row["candidate_provenance"],
        "package_ids": frontier_row.get("package_ids", ()),
        "baseline_identity": comparison.get("baseline_identity", {}),
        "variant_identity": comparison.get("variant_identity", {}),
        "workflow_semantic_identity": comparison.get("workflow_semantic_identity", {}),
        "constraint_report": comparison.get("constraint_report", {}),
        "paired": comparison.get("paired", {}),
        "paired_observations_sha256": sha256_run_value(observations, root=ROOT),
        "mana_delta": comparison.get("mana_delta", {}),
        "cache_provenance": comparison.get("cache_provenance", {}),
        "incremental_execution": comparison.get("incremental_execution", {}),
        "advancement_decision": advancement,
        "next_experiment": next_experiment,
        "evidence_class": comparison.get("evidence_class"),
        "final_recommendation": False,
        "truth_boundary": (
            "within-variant paired structural triage only; not empirical gameplay and not a "
            "direct cross-variant ranking"
        ),
    }


def main() -> None:
    iterations = int(os.environ.get("CANDIDATE_TRIAGE_ITERATIONS", str(DEFAULT_ITERATIONS)))
    if iterations < 1:
        raise SystemExit("CANDIDATE_TRIAGE_ITERATIONS must be positive")

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
    skipped: list[dict[str, Any]] = []
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
            raise SystemExit(f"frontier candidate is missing from structural repository: {candidate_id}")
        if candidate.card.oracle_name != frontier_row.get("add"):
            raise SystemExit(f"frontier/profile candidate identity mismatch: {candidate_id}")

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
                f"paired triage comparison failed for {remove} -> {candidate.card.oracle_name}: "
                f"{comparison.get('status')}"
            )
        if comparison.get("evidence_class") != "structural_model_estimates":
            raise SystemExit("paired triage lost its structural evidence class")
        advancement = facade.advancement_decision(comparison)
        next_experiment = facade.diagnose_next_experiment(comparison)
        rows.append(
            _compact_result(
                frontier_row,
                comparison,
                advancement=advancement,
                next_experiment=next_experiment,
            )
        )

    after = _source_hashes()
    if before != after:
        raise SystemExit("paired candidate triage changed a configured source")

    advancement_counts = Counter(
        str(row["advancement_decision"].get("status", "unknown")) for row in rows
    )
    valid_runs = sum(int(row["paired"].get("valid_runs", 0)) for row in rows)
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "paired_candidate_triage",
        "evidence_class": "structural_model_estimates",
        "deck_id": deck_id,
        "deck_hash": plan["deck_hash"],
        "frontier_plan_hash": plan["plan_hash"],
        "frontier_candidate_count": len(frontier),
        "executed_variant_count": len(rows),
        "skipped_variant_count": len(skipped),
        "iterations_per_variant": iterations,
        "master_seed": MASTER_SEED,
        "max_turns": MAX_TURNS,
        "primary_opponent_ids": plan.get("suggested_opponent_ids", ()),
        "within_variant_pairing": True,
        "direct_cross_variant_pairing": False,
        "direct_cross_variant_ranking_allowed": False,
        "total_valid_paired_runs": valid_runs,
        "advancement_status_counts": dict(sorted(advancement_counts.items())),
        "results": rows,
        "skipped": skipped,
        "next_stage_policy": {
            "advance": "eligible_for_targeted_denial_ablation_and_sensitivity_followup",
            "diagnose": "collect_the_diagnosed_missing_information_before_finalist_work",
            "reject": "do_not_spend_finalist_only_budget_without_new_evidence",
            "profile_required": "complete_candidate_profile_before_model_dependent_testing",
        },
        "canonical_mutation_performed": False,
        "inventory_reservation_performed": False,
        "purchase_decision_performed": False,
        "final_recommendation": False,
        "known_limitations": [
            "Eight paired iterations are first-pass structural triage, not final precision.",
            "Pairing is baseline-versus-variant within each candidate, not across candidates.",
            "Structural placement/share outputs are model estimates, not empirical Commander winrates.",
            "Triage advancement is only permission for the next evidence stage, not a deck change.",
            "Hypothetical test cards are not executed by the physical-only priority adapter.",
        ],
        "truth_boundary": (
            "first-pass paired structural candidate triage; no empirical gameplay claim, no direct "
            "cross-variant ranking, no inventory mutation, and no final deck recommendation"
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
    print(f"TOTAL_VALID_PAIRED_RUNS={valid_runs}")
    print(f"ADVANCEMENT_STATUS_COUNTS={json.dumps(dict(sorted(advancement_counts.items())))}")
    print("PAIRED_TRIAGE_BOUNDARY=structural_first_pass_not_final_recommendation")


if __name__ == "__main__":
    main()
