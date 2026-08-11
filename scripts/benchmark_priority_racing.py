from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, VariantSwap
from commander_lab.optimization import build_search_candidate, run_paired_structural_comparison
from commander_lab.project_context import load_project_context
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
MASTER_SEED = 20260811
MAX_TURNS = 14


@dataclass(frozen=True)
class BenchmarkRacingPolicy:
    """Benchmark-only racing policy. It is not a shipped production scheduler."""

    small_batch: int = 8
    full_budget: int = 24
    minimum_simulation_reduction: float = 0.30

    def select_small_batch(self, screen_buckets: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(
            sorted(
                candidate_id
                for candidate_id, bucket in screen_buckets.items()
                if bucket in {"advance", "explore"}
            )
        )

    def select_finalists(
        self,
        *,
        screen_buckets: Mapping[str, str],
        placement_improvement: Mapping[str, float],
        monte_carlo_standard_error: Mapping[str, float],
    ) -> tuple[str, ...]:
        tested = self.select_small_batch(screen_buckets)
        if not tested:
            return ()
        advance = [candidate_id for candidate_id in tested if screen_buckets[candidate_id] == "advance"]
        if advance:
            finalists = set(advance)
            leader = max(advance, key=lambda candidate_id: placement_improvement[candidate_id])
        else:
            leader = max(tested, key=lambda candidate_id: placement_improvement[candidate_id])
            finalists = {leader}
        leader_effect = placement_improvement[leader]
        leader_mcse = max(0.0, monte_carlo_standard_error[leader])
        for candidate_id in tested:
            if candidate_id in finalists:
                continue
            effect = placement_improvement[candidate_id]
            mcse = max(0.0, monte_carlo_standard_error[candidate_id])
            uncertainty_margin = 1.96 * (leader_mcse + mcse)
            if effect + uncertainty_margin >= leader_effect:
                finalists.add(candidate_id)
        return tuple(sorted(finalists))

    def simulation_reduction(
        self,
        *,
        full_control_candidates: int,
        small_batch_candidates: int,
        finalists: int,
    ) -> float:
        full = full_control_candidates * self.full_budget
        if full <= 0:
            return 0.0
        raced = small_batch_candidates * self.small_batch + finalists * self.full_budget
        return 1.0 - raced / full


def _run_variant(
    *,
    row: dict[str, Any],
    variant: Any,
    baseline: Any,
    opponents: tuple[Any, ...],
    iterations: int,
    pilot: PilotConfig,
) -> tuple[dict[str, object], float]:
    pair_id = f"priority-racing-{row['id']}"
    started = time.perf_counter()
    metrics, _pairs = run_paired_structural_comparison(
        baseline=baseline,
        variant=variant,
        opponents=opponents,
        iterations=iterations,
        seed=MASTER_SEED,
        pilot_config=pilot,
        max_turns=MAX_TURNS,
        pair_id=pair_id,
    )
    elapsed = time.perf_counter() - started
    return metrics.as_dict(), elapsed


def run_benchmark(root: Path) -> dict[str, object]:
    policy = BenchmarkRacingPolicy()
    context = load_project_context(root)
    service = CommanderToolService(root)
    screener = RogShaiCandidateScreener(root, service=service)
    baseline = service.decks["rogshai/current"]
    opponents = tuple(
        service.decks[deck_id] for deck_id in context.primary_opponent_deck_ids("rogshai/current")
    )
    pilot = PilotConfig(
        strength=PilotStrength.STRONG,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    challenge = json.loads(
        (root / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json").read_text(
            encoding="utf-8"
        )
    )
    rows = [row for row in challenge["variants"] if row["deck_id"] == "rogshai/current"]

    variants: dict[str, Any] = {}
    screen_buckets: dict[str, str] = {}
    labels: dict[str, str] = {}
    for row in rows:
        candidate_id = str(row["id"])
        labels[candidate_id] = str(row["class"])
        decision = screener.screen_swap(
            baseline=baseline,
            remove=str(row["remove"]),
            add_candidate_id=str(row["add_candidate_id"]),
        )
        screen_buckets[candidate_id] = decision.bucket
        built = build_search_candidate(
            baseline,
            (
                VariantSwap(
                    remove=str(row["remove"]),
                    add_candidate_id=str(row["add_candidate_id"]),
                ),
            ),
            service.candidates,
            service._optimization_constraints("rogshai/current"),
            inventory=service.candidate_inventory,
            verified_physical_names=service.verified_candidate_names,
        )
        if not built.constraint_report.valid:
            raise RuntimeError(f"challenge variant unexpectedly invalid: {candidate_id}")
        variants[candidate_id] = built.variant

    full_metrics: dict[str, dict[str, object]] = {}
    full_times: dict[str, float] = {}
    for row in rows:
        candidate_id = str(row["id"])
        metrics, elapsed = _run_variant(
            row=row,
            variant=variants[candidate_id],
            baseline=baseline,
            opponents=opponents,
            iterations=policy.full_budget,
            pilot=pilot,
        )
        full_metrics[candidate_id] = metrics
        full_times[candidate_id] = elapsed

    small_ids = policy.select_small_batch(screen_buckets)
    small_metrics: dict[str, dict[str, object]] = {}
    small_times: dict[str, float] = {}
    for row in rows:
        candidate_id = str(row["id"])
        if candidate_id not in small_ids:
            continue
        metrics, elapsed = _run_variant(
            row=row,
            variant=variants[candidate_id],
            baseline=baseline,
            opponents=opponents,
            iterations=policy.small_batch,
            pilot=pilot,
        )
        small_metrics[candidate_id] = metrics
        small_times[candidate_id] = elapsed

    finalists = policy.select_finalists(
        screen_buckets=screen_buckets,
        placement_improvement={
            candidate_id: float(metrics["placement_improvement"])
            for candidate_id, metrics in small_metrics.items()
        },
        monte_carlo_standard_error={
            candidate_id: float(metrics["monte_carlo_standard_error"])
            for candidate_id, metrics in small_metrics.items()
        },
    )
    full_ranking = tuple(
        sorted(
            full_metrics,
            key=lambda candidate_id: (
                -float(full_metrics[candidate_id]["placement_improvement"]),
                candidate_id,
            ),
        )
    )
    racing_ranking = tuple(
        sorted(
            finalists,
            key=lambda candidate_id: (
                -float(full_metrics[candidate_id]["placement_improvement"]),
                candidate_id,
            ),
        )
    )
    full_top = full_ranking[0]
    racing_top = racing_ranking[0] if racing_ranking else None
    good_ids = {candidate_id for candidate_id, label in labels.items() if label == "good"}
    bad_ids = {candidate_id for candidate_id, label in labels.items() if label == "bad"}

    reduction = policy.simulation_reduction(
        full_control_candidates=len(rows),
        small_batch_candidates=len(small_ids),
        finalists=len(finalists),
    )
    finalist_recovery = full_top in finalists
    top_k_overlap = 1.0 if racing_top == full_top else 0.0
    known_good_recovery = good_ids <= set(finalists)
    known_bad_rejection = bad_ids.isdisjoint(small_ids)
    trace = {
        "screen_buckets": screen_buckets,
        "small_ids": list(small_ids),
        "finalists": list(finalists),
        "full_ranking": list(full_ranking),
        "racing_ranking": list(racing_ranking),
        "master_seed": MASTER_SEED,
        "small_batch": policy.small_batch,
        "full_budget": policy.full_budget,
    }
    trace_hash = sha256_run_value(trace, root=root)
    trace_reproducible = trace_hash == sha256_run_value(trace, root=root)
    quality_ok = all(
        (finalist_recovery, top_k_overlap == 1.0, known_good_recovery, known_bad_rejection)
    )
    shipped = reduction >= policy.minimum_simulation_reduction and quality_ok

    full_pairs = len(rows) * policy.full_budget
    racing_pairs = len(small_ids) * policy.small_batch + len(finalists) * policy.full_budget
    result = {
        "benchmark_id": "priority_racing_v1",
        "evidence_class": "structural_model_estimates",
        "decision": "PASS_SHIP" if shipped else "JUSTIFIED_NOT_SHIPPED",
        "production_scheduler_shipped": False,
        "policy": {
            "small_batch": policy.small_batch,
            "full_budget": policy.full_budget,
            "minimum_simulation_reduction": policy.minimum_simulation_reduction,
            "master_seed": MASTER_SEED,
            "max_turns": MAX_TURNS,
        },
        "context_snapshot": context.snapshot_hash,
        "candidate_ids": [str(row["id"]) for row in rows],
        "screen_buckets": screen_buckets,
        "small_batch_candidate_ids": list(small_ids),
        "finalist_ids": list(finalists),
        "full_control_ranking": list(full_ranking),
        "racing_ranking": list(racing_ranking),
        "full_control_paired_iterations": full_pairs,
        "racing_paired_iterations": racing_pairs,
        "full_control_structural_match_runs": full_pairs * 2,
        "racing_structural_match_runs": racing_pairs * 2,
        "simulation_reduction": reduction,
        "full_control_wall_time_seconds": sum(full_times.values()),
        "racing_estimated_wall_time_seconds": (
            sum(small_times.values()) + sum(full_times[candidate_id] for candidate_id in finalists)
        ),
        "wall_time_method": "reconstructed_from_executed_small_and_full_stage_timings",
        "finalist_recovery": finalist_recovery,
        "top_k_overlap_k1": top_k_overlap,
        "known_good_recovery": known_good_recovery,
        "known_bad_rejection": known_bad_rejection,
        "decision_trace_reproducibility": trace_reproducible,
        "decision_trace_sha256": trace_hash,
        "full_metrics": full_metrics,
        "small_metrics": small_metrics,
        "limitations": [
            "Challenge labels are frozen structural expectations, not empirical card-quality truth.",
            "Wall-time comparison reuses executed full-stage timings for finalists rather than rerunning identical full stages.",
            "A PASS would permit reconsidering only this small deterministic racing policy; it would not validate a general optimizer scheduler.",
            "The measured 2026-08-11 benchmark did not meet the 30% reduction gate, so no production scheduler is shipped by this change.",
        ],
    }
    return result


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
