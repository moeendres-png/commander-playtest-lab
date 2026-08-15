from __future__ import annotations

from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.counterfactual import CounterfactualReplayLab
from commander_lab.engine.structural import StructuralSimulator
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralAbortLimits,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.models.counterfactual import (
    CounterfactualEngineMode,
    HiddenInformationPolicy,
    SeedPolicy,
)
from commander_lab.storage import atomic_write_json, sha256_value

from .campaign import run_balanced_paired_campaign
from .optimizer_v2 import ExploratoryEvaluation, descriptor_for_variant
from .optimizer_v2_release_models import OptimizerV2Manifest
from .orchestrator import WholeDeckCampaignOrchestrator
from .search_models import WholeDeckVariant


def _near_frontier_hashes(
    elites: tuple[dict[str, Any], ...], *, sesoi: float, limit: int = 6
) -> tuple[str, ...]:
    rows = []
    for row in elites:
        evaluation = row.get("evaluation", {})
        if not isinstance(evaluation, dict):
            continue
        low = float(evaluation.get("interval_low", 0.0))
        high = float(evaluation.get("interval_high", 0.0))
        robust = float(evaluation.get("robust_lower_bound", -999.0))
        score = float(evaluation.get("score", -999.0))
        deck_hash = str(evaluation.get("deck_hash", ""))
        unresolved = low <= sesoi and high >= -sesoi
        rows.append((unresolved, robust, score, deck_hash))
    rows.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
    return tuple(item[3] for item in rows[:limit] if item[3])


def _denied_profile(candidate: StructuralDeckProfile) -> StructuralDeckProfile:
    costs = {name: 99.0 for name in candidate.commander_names}
    identity = sha256_value(
        {
            "source_deck_hash": candidate.deck_hash,
            "axis": "optimizer_v2_commander_denial",
            "commander_costs": costs,
        }
    )
    return candidate.model_copy(
        update={
            "deck_id": f"{candidate.deck_id}/commander-denied",
            "deck_hash": identity,
            "commander_base_costs": costs,
        }
    )


def _commander_denial_axis(
    *,
    candidate: StructuralDeckProfile,
    orchestrator: WholeDeckCampaignOrchestrator,
    scenarios: tuple[Any, ...],
    max_turns: int,
) -> dict[str, object]:
    denied = _denied_profile(candidate)
    result = run_balanced_paired_campaign(
        baseline=candidate,
        variant=denied,
        opponent_profiles=orchestrator.opponents.profiles(),
        scenarios=scenarios,
        pilot_config=PilotConfig(
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        max_turns=max_turns,
        statistics_seed=scenarios[0].seed ^ 0x44E1_1A1,
        workers=1,
    )
    raw = result.get("paired_observations", [])
    rows = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    deltas = [float(row["variant_placement"]) - float(row["baseline_placement"]) for row in rows]
    return {
        "status": "executed",
        "games": len(rows),
        "denied_minus_normal_average_placement": fmean(deltas) if deltas else 0.0,
        "commander_denial_profile_hash": denied.deck_hash,
        "evidence_type": "structural_model_estimates",
        "interpretation": "positive values indicate worse placement when commander access is structurally suppressed",
    }


def _seated_decks(
    own: StructuralDeckProfile,
    opponents: dict[str, StructuralDeckProfile],
    scenario: Any,
) -> tuple[StructuralDeckProfile, ...]:
    seats: list[StructuralDeckProfile | None] = [None] * 4
    seats[scenario.own_seat - 1] = own
    for seat, deck_id in scenario.opponent_seat_assignment:
        seats[seat - 1] = opponents[deck_id]
    if any(row is None for row in seats):
        raise RuntimeError("diagnostic scenario did not fill all four seats")
    return tuple(row for row in seats if row is not None)


def _counterfactual_axis(
    *,
    root: Path,
    trace_directory: Path,
    candidate: StructuralDeckProfile,
    orchestrator: WholeDeckCampaignOrchestrator,
    scenario: Any,
    max_turns: int,
) -> dict[str, object]:
    opponents = orchestrator.opponents.profiles()
    seated = _seated_decks(candidate, opponents, scenario)
    decks = {deck.deck_id: deck for deck in seated}
    trace_directory.mkdir(parents=True, exist_ok=True)
    trace_path = trace_directory / f"{candidate.deck_hash[:16]}-{scenario.scenario_id}.jsonl"
    simulator = StructuralSimulator(decks)
    pilot = PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    simulator.simulate(
        StructuralMatchConfig(
            match_id=f"optimizer-v2-diagnostic-{candidate.deck_hash[:12]}",
            deck_ids=tuple(deck.deck_id for deck in seated),
            limits=StructuralAbortLimits(max_turns=max_turns),
            seed=scenario.seed,
            starting_player_seat=0,
            pilot_configs=(pilot,) * 4,
        ),
        run_id="optimizer-v2-diagnostic",
        event_log_path=trace_path,
        capture_events=True,
    )
    replay = CounterfactualReplayLab(root)
    relative = str(trace_path.relative_to(root))
    branches = replay.find_branchpoints(relative, actor_id=f"p{scenario.own_seat}")
    branch = next(
        (
            row
            for row in branches
            if any(
                action.legal and action.action_id != row.chosen_action
                for action in row.available_actions
            )
        ),
        None,
    )
    if branch is None:
        return {
            "status": "executed_no_informative_alternative_branchpoint",
            "trace_path": relative,
            "branchpoints": len(branches),
            "evidence_type": "structural_model_estimates",
            "external_engine_used": False,
        }
    alternative = next(
        action.action_id
        for action in branch.available_actions
        if action.legal and action.action_id != branch.chosen_action
    )
    result = replay.run(
        branch,
        alternative_action=alternative,
        hidden_information_policy=HiddenInformationPolicy.MULTIPLE_FUTURE_SAMPLES,
        engine_mode=CounterfactualEngineMode.STRUCTURAL,
        seed_policy=SeedPolicy.DERIVED_SEEDS,
        seed=scenario.seed ^ 0xC0F1_A11,
        future_samples=8,
        workers=1,
    )
    return {
        "status": "executed",
        "trace_path": relative,
        "branchpoint_id": branch.branchpoint_id,
        "chosen_action": branch.chosen_action,
        "alternative_action": alternative,
        "mean_improvement": result.mean_improvement,
        "positive_future_fraction": result.positive_future_fraction,
        "conclusion": result.conclusion,
        "evidence_type": "structural_model_estimates",
        "external_engine_used": result.external_engine_used,
        "tactical_oracle_used": result.tactical_oracle_used,
    }


def build_near_frontier_diagnostics(
    *,
    root: str | Path,
    run_directory: str | Path,
    manifest: OptimizerV2Manifest,
    orchestrator: WholeDeckCampaignOrchestrator,
    context: Any,
    elites: tuple[dict[str, Any], ...],
    variants_by_hash: dict[str, WholeDeckVariant],
    evaluations_by_hash: dict[str, ExploratoryEvaluation],
    cached_payload_by_hash: dict[str, dict[str, Any]],
    max_turns: int,
) -> dict[str, object]:
    project = Path(root).resolve()
    run_path = Path(run_directory).resolve()
    selected = _near_frontier_hashes(elites, sesoi=manifest.calibration.sesoi)
    scenarios = tuple(orchestrator.scheduler.schedule(16, seed=manifest.exploratory.master_seed))
    trace_directory = project / ".runtime" / "optimizer-v2-diagnostics" / manifest.manifest_hash
    rows: list[dict[str, object]] = []
    for deck_hash in selected:
        variant = variants_by_hash[deck_hash]
        evaluation = evaluations_by_hash[deck_hash]
        payload = cached_payload_by_hash.get(deck_hash, {})
        sensitivity = payload.get("sensitivity", {})
        sensitivity_map = sensitivity if isinstance(sensitivity, dict) else {}
        candidate = context.materialize(variant.mainboard, label=f"diag-{deck_hash[:10]}")
        parent_eval = (
            next(
                (
                    row
                    for row in evaluations_by_hash.values()
                    if row.candidate_id == variant.parent_variant_id
                ),
                None,
            )
            if variant.parent_variant_id
            else None
        )
        descriptor = descriptor_for_variant(variant)
        commander = _commander_denial_axis(
            candidate=candidate,
            orchestrator=orchestrator,
            scenarios=scenarios,
            max_turns=max_turns,
        )
        counterfactual = _counterfactual_axis(
            root=project,
            trace_directory=trace_directory,
            candidate=candidate,
            orchestrator=orchestrator,
            scenario=scenarios[0],
            max_turns=max_turns,
        )
        rows.append(
            {
                "deck_hash": deck_hash,
                "candidate_id": variant.variant_id,
                "selection_reason": "unresolved_or_near_frontier_exploratory",
                "primary_evaluation": evaluation.model_dump(mode="json"),
                "commander_denial": commander,
                "pilot_sensitivity": sensitivity_map.get("pilot", {"status": "not_available"}),
                "mulligan_sensitivity": sensitivity_map.get(
                    "mulligan", {"status": "not_available"}
                ),
                "matchup_decomposition": sensitivity_map.get("matchup_decomposition", {}),
                "ablation_parent_child": {
                    "status": "executed" if parent_eval is not None else "no_parent_evaluation",
                    "parent_candidate_id": variant.parent_variant_id,
                    "robust_lower_bound_delta": (
                        evaluation.robust_lower_bound - parent_eval.robust_lower_bound
                        if parent_eval is not None
                        else None
                    ),
                    "score_delta": (
                        evaluation.score - parent_eval.score if parent_eval is not None else None
                    ),
                    "mutation": (
                        variant.mutation.model_dump(mode="json")
                        if variant.mutation is not None
                        else None
                    ),
                },
                "mana_curve": {
                    "land_count": descriptor.land_count,
                    "average_nonland_mv": descriptor.average_nonland_mv,
                    "mana_analysis": variant.mana,
                },
                "finish_axis": {
                    "finish_strength": descriptor.finish_strength,
                    "protection_strength": descriptor.protection_strength,
                    "velocity_strength": descriptor.velocity_strength,
                },
                "counterfactual_replay": counterfactual,
                "evidence_boundary": "exploratory_structural_model_estimates_not_empirical_gameplay",
                "automatic_deck_change": False,
            }
        )
    report: dict[str, object] = {
        "schema_version": "1.0.0",
        "manifest_hash": manifest.manifest_hash,
        "evidence_context": "exploratory",
        "evidence_type": "structural_model_estimates",
        "selected_candidate_count": len(rows),
        "axes": (
            "commander_denial",
            "pilot_sensitivity",
            "mulligan_sensitivity",
            "matchup_decomposition",
            "ablation_parent_child",
            "mana_curve",
            "finish_axis",
            "counterfactual_replay",
        ),
        "candidates": rows,
        "holdout_used": False,
        "automatic_deck_change": False,
    }
    atomic_write_json(run_path / "near-frontier-diagnostics.json", report)
    return report
