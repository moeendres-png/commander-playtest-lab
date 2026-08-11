from __future__ import annotations

import hashlib
import json
from pathlib import Path

from commander_lab.counterfactual import CounterfactualReplayLab
from commander_lab.decision_statistics import holm_adjust
from commander_lab.models import (
    BeamSearchInput,
    CardAblationInput,
    CommanderDenialInput,
    LocalSearchInput,
    PackageAblationInput,
    ParetoFrontInput,
    PilotConfig,
    ShapleyInput,
    SwapMatrixInput,
    VariantSwap,
)
from commander_lab.optimization import build_search_candidate, run_paired_structural_comparison
from commander_lab.optimization.jp5 import build_recommendation_trace, scenario_heterogeneity
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = (
    "opponent/morcant-elves",
    "opponent/doom-prevails-precon",
    "opponent/cosmic-spiderman-midbudget",
)
HOLDOUT_SHA = "b75e8622097221b00ad51322e2ad13fe5158cfd8647e92d2cb21a0d65b447203"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(response):
    return {"status": response.status.value, "errors": response.errors, "result": response.result}


def _variant(service: CommanderToolService, row: dict):
    baseline = service._deck(row["deck_id"])
    swap = VariantSwap(remove=row["remove"], add_candidate_id=row["add_candidate_id"])
    built = build_search_candidate(
        baseline,
        (swap,),
        service.candidates,
        service._optimization_constraints(row["deck_id"]),
        inventory=service.candidate_inventory,
        verified_physical_names=service.verified_candidate_names,
    )
    assert built.constraint_report.valid
    return baseline, built


def _paired(
    service,
    row,
    *,
    opponents=PRIMARY,
    strength="strong",
    iterations=12,
    seed=20260811,
    pair_suffix="primary",
):
    baseline, built = _variant(service, row)
    metrics, pairs = run_paired_structural_comparison(
        baseline=baseline,
        variant=built.variant,
        opponents=tuple(service._deck(x) for x in opponents),
        iterations=iterations,
        seed=seed,
        pilot_config=PilotConfig(strength=strength, mode="deterministic"),
        max_turns=14,
        pair_id=f"jp5-{row['id']}-{pair_suffix}",
    )
    return built, metrics, pairs


def _counterfactual_smoke() -> dict:
    target = ROOT / "data/runs/j_p5/counterfactual/source.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "event_type": "game_started",
            "game_id": "jp5",
            "sequence": 0,
            "actor_id": None,
            "payload": {"seed": 17},
        },
        {
            "event_type": "state_checkpoint",
            "game_id": "jp5",
            "sequence": 1,
            "actor_id": None,
            "payload": {"reason": "before_decision", "players": [{"player_id": "p1", "life": 40}]},
        },
        {
            "event_type": "pilot_decision",
            "game_id": "jp5",
            "sequence": 2,
            "actor_id": "p1",
            "payload": {
                "phase": "counter",
                "selected_action_id": "counter:Threat",
                "selected_utility": 2.0,
                "candidates": [["counter:Threat", 2.0], ["pass", 3.5], ["counter:Value", 1.0]],
            },
        },
    ]
    target.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8"
    )
    lab = CounterfactualReplayLab(ROOT)
    rel = target.relative_to(ROOT).as_posix()
    branch = lab.find_branchpoints(rel)[0]
    result = lab.run(branch, alternative_action="pass", future_samples=4, seed=20260811)
    return {
        "branchpoint_id": branch.branchpoint_id,
        "mean_improvement": result.mean_improvement,
        "historical_fact": result.historical_fact,
        "external_engine_used": result.external_engine_used,
        "truth_boundary": "model alternative, not historical fact",
    }


def run() -> dict:
    holdout_path = ROOT / "data/evals/holdout/J_P5_OPTIMIZER_HOLDOUT_v1.json"
    assert _sha(holdout_path) == HOLDOUT_SHA
    seal = json.loads((ROOT / "docs/J_P5_HOLDOUT_SEAL.json").read_text())
    assert seal["outcomes_evaluated"] is False and seal["first_evaluation_status"] == "not_run"
    challenge = json.loads(
        (ROOT / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json").read_text()
    )
    policy = json.loads((ROOT / "config/J_P5_SEARCH_POLICY_v1.json").read_text())
    service = CommanderToolService(ROOT)

    primary_rows = []
    by_deck: dict[str, list[dict]] = {"korvold/current": [], "rogshai/current": []}
    for row in challenge["variants"]:
        built, metrics, pairs = _paired(service, row)
        record = {
            **row,
            "variant_hash": built.variant.deck_hash,
            "constraint_valid": built.constraint_report.valid,
            "paired": metrics.as_dict(),
            "pair_count": len(pairs),
            "preselection_pass": row["static_screening_delta"]
            >= policy["preselection"]["minimum_static_screening_delta"],
        }
        primary_rows.append(record)
        by_deck[row["deck_id"]].append(record)

    finalists = []
    challenge_checks = {}
    for deck_id, rows in by_deck.items():
        advanced = [row for row in rows if row["preselection_pass"]]
        adjusted = holm_adjust(row["paired"]["paired_randomization_p_value"] for row in advanced)
        for row, p_adj in zip(advanced, adjusted, strict=True):
            row["holm_adjusted_model_internal_p_value"] = p_adj
            row["development_recommendation_gate_pass"] = (
                row["paired"]["distributionally_robust_lower_bound"] > 0 and p_adj <= 0.05
            )
        advanced.sort(
            key=lambda row: (
                row["paired"]["distributionally_robust_lower_bound"],
                row["paired"]["placement_improvement"],
                row["static_screening_delta"],
            ),
            reverse=True,
        )
        finalist = advanced[0]
        finalists.append(
            {
                k: finalist[k]
                for k in (
                    "id",
                    "deck_id",
                    "class",
                    "remove",
                    "add_candidate_id",
                    "variant_hash",
                    "static_screening_delta",
                )
            }
        )
        classes = {row["class"]: row for row in rows}
        challenge_checks[deck_id] = {
            "good_preselected": classes["good"]["preselection_pass"],
            "neutral_preselected": classes["neutral"]["preselection_pass"],
            "bad_preselected": classes["bad"]["preselection_pass"],
            "bad_not_recommended_from_noisy_mean": not classes["bad"].get(
                "development_recommendation_gate_pass", False
            ),
            "finalist_class": finalist["class"],
            "strict_good_over_neutral_observed": finalist["class"] == "good",
            "safety_discrimination_pass": classes["good"]["preselection_pass"]
            and classes["neutral"]["preselection_pass"]
            and not classes["bad"]["preselection_pass"]
            and not classes["bad"].get("development_recommendation_gate_pass", False),
            "pass": classes["good"]["preselection_pass"]
            and classes["neutral"]["preselection_pass"]
            and not classes["bad"]["preselection_pass"]
            and not classes["bad"].get("development_recommendation_gate_pass", False),
        }

    # sensitivity uses development-only opponents; never loads the sealed optimizer holdout scenarios.
    sensitivity = {}
    for finalist in finalists:
        rows = []
        for pod_size, opponents in (
            (3, PRIMARY[:2]),
            (4, PRIMARY),
            (5, (*PRIMARY, "synthetic/control")),
        ):
            for strength in ("average", "strong", "near_optimal_heuristic"):
                _, metrics, _ = _paired(
                    service,
                    finalist,
                    opponents=opponents,
                    strength=strength,
                    iterations=3,
                    seed=20260821 + pod_size,
                    pair_suffix=f"sens-{pod_size}-{strength}",
                )
                rows.append(
                    {
                        "pod_size": pod_size,
                        "pilot_strength": strength,
                        "opponents": list(opponents),
                        "effect": metrics.placement_improvement,
                        "robust_lower_bound": metrics.distributionally_robust_lower_bound,
                    }
                )
        sensitivity[finalist["deck_id"]] = {
            "rows": rows,
            "heterogeneity": scenario_heterogeneity(row["effect"] for row in rows),
            "worst_effect": min(row["effect"] for row in rows),
            "worst_robust_lower_bound": min(row["robust_lower_bound"] for row in rows),
        }

    kg = next(r for r in challenge["variants"] if r["id"] == "korvold_good_static")
    kn = next(r for r in challenge["variants"] if r["id"] == "korvold_neutral_static")
    rg = next(r for r in challenge["variants"] if r["id"] == "rogshai_good_static")
    rn = next(r for r in challenge["variants"] if r["id"] == "rogshai_neutral_static")
    matrices = {
        "korvold": _result(
            service.generate_swap_matrix(
                SwapMatrixInput(
                    deck_id="korvold/current",
                    remove_cards=(kg["remove"], kn["remove"]),
                    add_candidate_ids=(kg["add_candidate_id"], kn["add_candidate_id"]),
                    opponent_deck_ids=PRIMARY,
                    iterations_per_cell=1,
                    simulate_valid_cells=True,
                    seed=20260831,
                )
            )
        ),
        "rogshai": _result(
            service.generate_swap_matrix(
                SwapMatrixInput(
                    deck_id="rogshai/current",
                    remove_cards=(rg["remove"], rn["remove"]),
                    add_candidate_ids=(rg["add_candidate_id"], rn["add_candidate_id"]),
                    opponent_deck_ids=PRIMARY,
                    iterations_per_cell=1,
                    simulate_valid_cells=True,
                    seed=20260832,
                )
            )
        ),
    }
    local = _result(
        service.run_local_search(
            LocalSearchInput(
                deck_id="korvold/current",
                candidate_ids=(kg["add_candidate_id"], kn["add_candidate_id"]),
                max_steps=1,
                cuts_per_step=4,
                opponent_deck_ids=PRIMARY,
                iterations=2,
                seed=20260833,
            )
        )
    )
    beam = _result(
        service.run_beam_search(
            BeamSearchInput(
                deck_id="rogshai/current",
                candidate_ids=(rg["add_candidate_id"], rn["add_candidate_id"]),
                beam_width=2,
                depth=1,
                max_cuts_per_node=4,
                opponent_deck_ids=PRIMARY,
                iterations=2,
                seed=20260834,
            )
        )
    )
    pareto = {
        "korvold": _result(
            service.evaluate_pareto_front(
                ParetoFrontInput(
                    deck_id="korvold/current",
                    variants=tuple(
                        (VariantSwap(remove=r["remove"], add_candidate_id=r["add_candidate_id"]),)
                        for r in challenge["variants"]
                        if r["deck_id"] == "korvold/current"
                    ),
                    opponent_deck_ids=PRIMARY,
                    holdout_pods=(),
                    iterations=2,
                    seed=20260835,
                )
            )
        ),
        "rogshai": _result(
            service.evaluate_pareto_front(
                ParetoFrontInput(
                    deck_id="rogshai/current",
                    variants=tuple(
                        (VariantSwap(remove=r["remove"], add_candidate_id=r["add_candidate_id"]),)
                        for r in challenge["variants"]
                        if r["deck_id"] == "rogshai/current"
                    ),
                    opponent_deck_ids=PRIMARY,
                    holdout_pods=(),
                    iterations=2,
                    seed=20260836,
                )
            )
        ),
    }
    ablation = {
        "card": _result(
            service.run_card_ablation(
                CardAblationInput(
                    deck_id="korvold/current",
                    card_name="Mirkwood Bats",
                    opponent_deck_ids=PRIMARY,
                    iterations=3,
                    seed=20260837,
                )
            )
        ),
        "package": _result(
            service.run_package_ablation(
                PackageAblationInput(
                    deck_id="korvold/current",
                    card_names=("Mayhem Devil", "Mirkwood Bats"),
                    opponent_deck_ids=PRIMARY,
                    iterations=3,
                    seed=20260838,
                )
            )
        ),
    }
    denial = {
        deck_id: _result(
            service.run_commander_denial(
                CommanderDenialInput(
                    deck_id=deck_id, opponent_deck_ids=PRIMARY, iterations=3, seed=20260839
                )
            )
        )
        for deck_id in ("korvold/current", "rogshai/current")
    }
    shapley = _result(
        service.estimate_shapley(
            ShapleyInput(
                deck_id="korvold/current",
                card_names=("Mayhem Devil", "Mirkwood Bats"),
                opponent_deck_ids=PRIMARY,
                permutations=16,
                iterations=2,
                seed=20260840,
            )
        )
    )
    counterfactual = _counterfactual_smoke()

    traces = []
    for finalist in finalists:
        row = next(item for item in primary_rows if item["id"] == finalist["id"])
        trace = build_recommendation_trace(
            candidate_change=(
                {"remove": row["remove"], "add_candidate_id": row["add_candidate_id"]},
            ),
            constraint_status={"valid": row["constraint_valid"]},
            baseline_identity={
                "deck_id": row["deck_id"],
                "deck_hash": service._deck(row["deck_id"]).deck_hash,
            },
            variant_identity={"variant_id": row["id"], "deck_hash": row["variant_hash"]},
            paired_seeds=tuple(row["paired"]["seeds"]),
            affected_roles=(),
            central_effect={
                k: row["paired"][k]
                for k in (
                    "placement_improvement",
                    "effect_size",
                    "monte_carlo_standard_error",
                    "confidence_interval",
                    "confidence_interval_interpretation",
                    "paired_randomization_p_value",
                )
            },
            worst_case_effect=sensitivity[row["deck_id"]]["worst_effect"],
            sensitivity=sensitivity[row["deck_id"]],
            holdout_status="sealed_not_yet_evaluated",
            recommendation_confidence_value="development_candidate_only",
        )
        traces.append(trace)

    output = {
        "schema_version": "1.0",
        "phase": "J-P5-development",
        "evidence_type": "structural_model_estimates",
        "truth_boundary": "simulation/model evidence only; not empirical Commander winrate evidence",
        "holdout_identity": {"id": seal["holdout_id"], "sha256": HOLDOUT_SHA, "evaluated": False},
        "source_deck_hashes": {d: service._deck(d).deck_hash for d in service.ACTIVE_OWN_DECK_IDS},
        "challenge_primary": primary_rows,
        "challenge_checks": challenge_checks,
        "challenge_set_pass": all(x["pass"] for x in challenge_checks.values()),
        "finalists": finalists,
        "sensitivity": sensitivity,
        "constraint_enforcement": {
            "current_candidate_count": len(service.candidates),
            "current_free_inventory_entries": len(service.candidate_inventory),
            "hard_locked_cards": {
                d: list(service._optimization_constraints(d).locked_cards)
                for d in service.ACTIVE_OWN_DECK_IDS
            },
            "pass": True,
        },
        "paired_comparison": {
            "pass": all(
                r["paired"]["pairing_conditions"]["common_random_numbers"] for r in primary_rows
            ),
            "families": "Holm per deck",
            "model_internal_CI_only": True,
        },
        "ablation": ablation,
        "commander_denial": denial,
        "swap_matrix": matrices,
        "search": {"local": local, "beam": beam, "policy": policy},
        "pareto": pareto,
        "multiple_comparisons": {"method": "Holm FWER per deck family", "pass": True},
        "recommendation_traces": traces,
        "counterfactual_replay": counterfactual,
        "shapley": shapley,
        "shapley_method_judgment": "useful as secondary explanatory/triage evidence only; not a primary winner-selection method",
        "automatic_canonical_mutation": False,
    }
    target = ROOT / "docs/J_P5_DEVELOPMENT_EVIDENCE.json"
    target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finalist_target = ROOT / "docs/J_P5_FROZEN_FINALISTS.json"
    finalist_target.write_text(
        json.dumps(
            {"status": "development_selected_pending_freeze", "finalists": finalists},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "challenge_set_pass": output["challenge_set_pass"],
                "finalists": finalists,
                "matrix_status": {k: v["status"] for k, v in matrices.items()},
                "search_status": {"local": local["status"], "beam": beam["status"]},
                "pareto_status": {k: v["status"] for k, v in pareto.items()},
                "holdout_evaluated": False,
            },
            indent=2,
        )
    )
    return output


if __name__ == "__main__":
    run()
