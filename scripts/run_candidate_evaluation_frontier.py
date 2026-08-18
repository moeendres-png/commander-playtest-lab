from __future__ import annotations

import json
from pathlib import Path

from commander_lab.candidate_evaluation import build_candidate_evaluation_plan
from commander_lab.deck_registry import load_deck_policy_registry
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/candidate_evaluation/CURRENT_CANDIDATE_EVALUATION_PLAN.json"


def _source_hashes() -> dict[str, str | None]:
    registry = load_deck_policy_registry(ROOT)
    names = (
        "active_scope",
        "deck_manifest",
        "inventory_snapshot",
        "candidate_eligibility",
        "optimization_availability",
        "inactive_release_delta",
    )
    return {name: registry.source_hash(name, required=False) for name in names}


def main() -> None:
    before = _source_hashes()
    registry = load_deck_policy_registry(ROOT)
    service = CommanderToolService(ROOT)
    plan = build_candidate_evaluation_plan(
        ROOT,
        service=service,
        registry=registry,
        deck_id=registry.primary_deck_id,
        max_pairs=16,
        max_pairs_per_candidate=2,
        max_cut_hypotheses=24,
        max_candidate_queue=64,
    )
    after = _source_hashes()
    if before != after:
        raise SystemExit("candidate evaluation mutated or changed a configured source")
    if plan.get("canonical_mutation_performed") is not False:
        raise SystemExit("candidate evaluation lost its non-mutation boundary")
    if plan.get("final_recommendation") is not False:
        raise SystemExit("candidate evaluation incorrectly emitted a final recommendation")
    frontier = plan.get("variant_frontier")
    if not isinstance(frontier, list) or not frontier:
        raise SystemExit("candidate evaluation produced no constraint-valid variant frontier")
    if any(row.get("requires_paired_validation") is not True for row in frontier):
        raise SystemExit("candidate frontier contains a row without paired-validation requirement")

    metrics = plan.get("frontier_metrics")
    if not isinstance(metrics, dict):
        raise SystemExit("candidate evaluation produced no frontier metrics")
    configured_cap = metrics.get("max_pairs_per_candidate")
    observed_cap = metrics.get("observed_max_pairs_for_one_candidate")
    if not isinstance(configured_cap, int) or not isinstance(observed_cap, int):
        raise SystemExit("candidate frontier diversity metrics are malformed")
    if observed_cap > configured_cap:
        raise SystemExit("candidate frontier exceeded its per-candidate experiment cap")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"CANDIDATE_EVALUATION_PLAN_HASH={plan['plan_hash']}")
    print(f"CANDIDATE_EVALUATION_DECK={plan['deck_id']}")
    print(f"DISCOVERABLE_CANDIDATES={plan['candidate_discovery']['discoverable_candidate_count']}")
    print(f"PROFILE_REQUIRED={plan['candidate_discovery']['profile_required_count']}")
    print(f"VALIDATED_VARIANT_POOL={plan['validated_structural_variant_pool_count']}")
    print(f"VARIANT_FRONTIER={len(frontier)}")
    print(f"UNIQUE_FRONTIER_CANDIDATES={metrics['unique_candidate_count']}")
    print(f"MAX_PAIRS_FOR_ONE_CANDIDATE={observed_cap}")
    print("CANDIDATE_EVALUATION_BOUNDARY=structural_plan_not_final_recommendation")


if __name__ == "__main__":
    main()
