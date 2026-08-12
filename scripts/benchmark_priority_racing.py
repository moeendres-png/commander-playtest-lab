from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from commander_lab.adaptive_budget import (
    build_conservative_adaptive_budget_plan,
    challenge_quality_metrics,
)
from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
FULL_BUDGET = 24
MINIMUM_REDUCTION = 0.30


def run_benchmark(root: Path) -> dict[str, object]:
    """Run the frozen quality/safety gate for the production adaptive budget policy.

    This gate deliberately does not rerun structural games. The production policy is allowed to
    eliminate only candidates already frozen as `deprioritize_static`; it never eliminates from
    noisy early paired means. Structural comparisons remain independently validated by the paired
    CRN regression suite and are scheduled after this gate.
    """

    service = CommanderToolService(root)
    screener = RogShaiCandidateScreener(root, service=service)
    baseline = service.decks["rogshai/current"]
    challenge = json.loads(
        (root / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json").read_text(
            encoding="utf-8"
        )
    )
    rows: list[dict[str, Any]] = [
        row for row in challenge["variants"] if row["deck_id"] == "rogshai/current"
    ]

    labels: dict[str, str] = {}
    screen_buckets: dict[str, str] = {}
    screening_scores: dict[str, float] = {}
    for row in rows:
        candidate_id = str(row["id"])
        labels[candidate_id] = str(row["class"])
        decision = screener.screen_swap(
            baseline=baseline,
            remove=str(row["remove"]),
            add_candidate_id=str(row["add_candidate_id"]),
        )
        if not decision.constraint_valid or decision.screening_delta is None:
            raise RuntimeError(f"challenge variant unexpectedly invalid: {candidate_id}")
        screen_buckets[candidate_id] = decision.bucket
        screening_scores[candidate_id] = float(decision.screening_delta)

    plan = build_conservative_adaptive_budget_plan(
        screen_buckets,
        full_budget_per_candidate=FULL_BUDGET,
    )
    quality = challenge_quality_metrics(plan, labels)
    full_static_ranking = tuple(
        sorted(
            screening_scores,
            key=lambda candidate_id: (-screening_scores[candidate_id], candidate_id),
        )
    )
    retained = set(plan.retained_candidate_ids)
    conservative_static_ranking = tuple(
        candidate_id for candidate_id in full_static_ranking if candidate_id in retained
    )
    decision_agreement = bool(conservative_static_ranking) and (
        conservative_static_ranking[0] == full_static_ranking[0]
    )
    shipped = bool(quality["quality_gate_pass"]) and decision_agreement and (
        plan.simulation_reduction >= MINIMUM_REDUCTION
    )

    trace = {
        "benchmark_id": "priority_adaptive_budget_v2",
        "labels": labels,
        "screen_buckets": screen_buckets,
        "screening_scores": screening_scores,
        "plan": plan.as_dict(),
        "full_static_ranking": list(full_static_ranking),
        "conservative_static_ranking": list(conservative_static_ranking),
    }
    trace_hash = sha256_run_value(trace, root=root)

    return {
        "benchmark_id": "priority_adaptive_budget_v2",
        "evidence_class": "frozen_structural_challenge_policy_gate",
        "decision": "PASS_SHIP" if shipped else "JUSTIFIED_NOT_SHIPPED",
        "production_scheduler_shipped": shipped,
        "production_policy": "conservative_static_gate_plus_decision_information_continuation",
        "execution_mode": "deterministic_policy_safety_gate_no_structural_game_rerun",
        "candidate_ids": [str(row["id"]) for row in rows],
        "screen_buckets": screen_buckets,
        "screening_scores": screening_scores,
        "full_control_static_ranking": list(full_static_ranking),
        "conservative_static_ranking": list(conservative_static_ranking),
        "conservative_finalist_ids": list(plan.retained_candidate_ids),
        "full_control_paired_iterations": plan.full_control_paired_comparisons,
        "conservative_paired_iterations": plan.planned_paired_comparisons,
        "simulation_reduction": plan.simulation_reduction,
        "decision_agreement": decision_agreement,
        "material_finalist_recall": quality["material_finalist_recall"],
        "false_elimination_rate_of_material_finalists": quality[
            "false_elimination_rate_of_material_finalists"
        ],
        "noisy_early_elimination_allowed": False,
        "aggressive_control": {
            "production_allowed": False,
            "current_execution_status": "NOT_RUN_BY_POLICY_SAFETY_GATE",
            "historical_uncommitted_reference_false_elimination_rate": 0.50,
            "historical_reference_is_current_measurement": False,
            "reason": (
                "The previously measured noisy racing control false-eliminated material finalists; "
                "production policy therefore forbids noisy early elimination."
            ),
        },
        "decision_trace_reproducibility": trace_hash == sha256_run_value(trace, root=root),
        "decision_trace_sha256": trace_hash,
        "limitations": [
            "Challenge labels are frozen structural expectations, not empirical card-quality truth.",
            "The 144→96 values are paired-comparison budget counts implied by the deterministic policy, not newly executed game counts in this safety gate.",
            "Paired CRN execution remains covered by separate simulation/integration regressions.",
            "The historical 50% aggressive-control false-elimination rate is provenance only and is not presented as a fresh measurement.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_benchmark(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
