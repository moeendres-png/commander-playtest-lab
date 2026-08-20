#!/usr/bin/env python3
"""Preregistered RogShai commander-denial Whole-Deck robustness campaign.

Evidence boundary: structural_model_estimates plus an explicit synthetic commander-denial
assumption. Canonical deck, inventory, allocation, reservation and promotion state stay read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.current_model_resolution import load_current_model_resolution
from commander_lab.decision_statistics import paired_bootstrap_interval
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralDeckProfile,
)
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.storage import sha256_value
from commander_lab.whole_deck.campaign import run_balanced_paired_campaign
from commander_lab.whole_deck.lab_context import enriched_context
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from commander_lab.whole_deck.search_context import current_control_mainboard
from run_rogshai_whole_deck_comparison import (
    CANDIDATE_ID,
    CANDIDATE_PATH,
    COMMANDERS,
    OPPONENT_IDS,
    commit_sha,
    load_candidate,
    sha256,
    write_checksums,
    write_json,
)

CAMPAIGN_ID = "rogshai-commander-denial-robustness-2026-08-20-v1"
BASELINE_ID = "rogshai/current"
OUTPUT_DIR = Path("artifacts/rogshai_commander_denial_robustness")
EVIDENCE = "structural_model_estimates"
SYNTHETIC_ASSUMPTION = "commander_unavailable_full_game_via_unreachable_command_zone_cost"
MASTER_SEED = 2026082061
ALLOWED_GAMES = {32, 64, 128}
DENIAL_COST = 1_000_000.0
ISHAI = "Ishai, Ojutai Dragonspeaker"
ROGRAKH = "Rograkh, Son of Rohgahh"
STRESS_STATES: dict[str, tuple[str, ...]] = {
    "normal": (),
    "rograkh_denied": (ROGRAKH,),
    "ishai_denied": (ISHAI,),
    "both_denied": (ISHAI, ROGRAKH),
}


def denial_profile(
    deck: StructuralDeckProfile,
    *,
    state: str,
    denied_commanders: tuple[str, ...],
) -> StructuralDeckProfile:
    if state not in STRESS_STATES or STRESS_STATES[state] != denied_commanders:
        raise ValueError(f"unregistered denial state: {state}")
    missing = sorted(set(denied_commanders) - set(deck.commander_names))
    if missing:
        raise ValueError(f"denial state references non-commanders: {missing}")
    costs = dict(deck.commander_base_costs)
    for name in denied_commanders:
        costs[name] = DENIAL_COST
    state_hash = sha256_value(
        {
            "source_deck_hash": deck.deck_hash,
            "stress_state": state,
            "denied_commanders": denied_commanders,
            "denial_cost_proxy": DENIAL_COST,
            "synthetic_assumption": SYNTHETIC_ASSUMPTION,
        }
    )
    return deck.model_copy(
        update={
            "deck_id": f"{deck.deck_id}@{state}",
            "deck_hash": state_hash,
            "commander_base_costs": costs,
        }
    )


def paired_delta(row: dict[str, Any]) -> float:
    return float(row["baseline_placement"]) - float(row["variant_placement"])


def campaign_diagnostic(campaign: dict[str, Any], resolution: float) -> dict[str, Any]:
    paired = campaign["paired"]
    value = float(paired["paired_placement_delta"])
    interval = tuple(float(value) for value in paired["paired_bootstrap_interval"])
    return {
        "candidate_vs_current_paired_placement_delta": value,
        "delta_semantics": "current_placement-candidate_placement; positive=candidate_better",
        "paired_bootstrap_interval": interval,
        "above_resolution_reference": abs(value) >= resolution,
        "interval_excludes_zero": interval[0] > 0 or interval[1] < 0,
        "current_average_placement": float(campaign["baseline"]["average_placement"]),
        "candidate_average_placement": float(campaign["variant"]["average_placement"]),
        "current_place_1_share": float(
            campaign["baseline"]["structural_model_estimated_place_1_share"]
        ),
        "candidate_place_1_share": float(
            campaign["variant"]["structural_model_estimated_place_1_share"]
        ),
        "candidate_better_count": int(paired["paired_variant_better_count"]),
        "candidate_worse_count": int(paired["paired_variant_worse_count"]),
        "tie_count": int(paired["paired_tie_count"]),
    }


def rows_by_scenario(campaign: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = campaign.get("paired_observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("campaign has no paired observations")
    result = {str(row["scenario_id"]): row for row in rows if isinstance(row, dict)}
    if len(result) != len(rows):
        raise ValueError("campaign scenario ids are not unique")
    return result


def degradation_summary(
    normal: dict[str, Any],
    denied: dict[str, Any],
    *,
    prefix: str,
    seed: int,
) -> dict[str, Any]:
    normal_rows = rows_by_scenario(normal)
    denied_rows = rows_by_scenario(denied)
    if set(normal_rows) != set(denied_rows):
        raise RuntimeError("normal and denial campaigns do not share the same scenarios")
    key = f"{prefix}_placement"
    differences = tuple(
        float(denied_rows[scenario][key]) - float(normal_rows[scenario][key])
        for scenario in sorted(normal_rows)
    )
    interval = paired_bootstrap_interval(differences, seed=seed)
    return {
        "games": len(differences),
        "mean_placement_degradation": fmean(differences),
        "degradation_semantics": "denied_placement-normal_placement; positive=denial_hurts",
        "paired_bootstrap_interval": interval,
        "denial_worse_count": sum(value > 0 for value in differences),
        "denial_better_count": sum(value < 0 for value in differences),
        "tie_count": sum(abs(value) < 1e-12 for value in differences),
        "paired_differences": list(differences),
    }


def resilience_summary(
    normal: dict[str, Any],
    denied: dict[str, Any],
    *,
    resolution: float,
    seed: int,
) -> dict[str, Any]:
    current = degradation_summary(normal, denied, prefix="baseline", seed=seed + 11)
    candidate = degradation_summary(normal, denied, prefix="variant", seed=seed + 17)
    current_diffs = tuple(float(value) for value in current["paired_differences"])
    candidate_diffs = tuple(float(value) for value in candidate["paired_differences"])
    advantage = tuple(c - v for c, v in zip(current_diffs, candidate_diffs, strict=True))
    interval = paired_bootstrap_interval(advantage, seed=seed + 23)
    mean_advantage = fmean(advantage)
    return {
        "current": {key: value for key, value in current.items() if key != "paired_differences"},
        "candidate": {
            key: value for key, value in candidate.items() if key != "paired_differences"
        },
        "candidate_resilience_advantage": mean_advantage,
        "advantage_semantics": (
            "current_degradation-candidate_degradation; positive=candidate_degrades_less"
        ),
        "paired_bootstrap_interval": interval,
        "above_resolution_reference": abs(mean_advantage) >= resolution,
        "interval_excludes_zero": interval[0] > 0 or interval[1] < 0,
    }


def clear_signal(value: float, interval: tuple[float, float], resolution: float) -> int:
    if abs(value) < resolution:
        return 0
    if value > 0 and interval[0] > 0:
        return 1
    if value < 0 and interval[1] < 0:
        return -1
    return 0


def classify(
    diagnostics: dict[str, dict[str, Any]],
    resilience: dict[str, dict[str, Any]],
    resolution: float,
) -> tuple[str, dict[str, Any]]:
    signals: list[tuple[str, int, str]] = []
    for state in ("rograkh_denied", "ishai_denied", "both_denied"):
        diag = diagnostics[state]
        cross_interval = tuple(float(value) for value in diag["paired_bootstrap_interval"])
        cross = clear_signal(
            float(diag["candidate_vs_current_paired_placement_delta"]),
            cross_interval,
            resolution,
        )
        if cross:
            signals.append((state, cross, "candidate_vs_current_under_denial"))
        robustness = resilience[state]
        resilience_interval = tuple(
            float(value) for value in robustness["paired_bootstrap_interval"]
        )
        resilience_signal = clear_signal(
            float(robustness["candidate_resilience_advantage"]),
            resilience_interval,
            resolution,
        )
        if resilience_signal:
            signals.append((state, resilience_signal, "relative_degradation"))
    directions = {signal for _, signal, _ in signals}
    detail = {
        "clear_material_signals": [
            {"state": state, "direction": direction, "axis": axis}
            for state, direction, axis in signals
        ],
        "effective_resolution_reference": resolution,
        "resolution_use_boundary": (
            "reference only: MODEL_RESOLUTION_CURRENT was calibrated on paired Structural placement "
            "comparisons, not specifically on synthetic full-game commander-denial states"
        ),
    }
    if not signals:
        return "NO_CLEAR_DENIAL_ROBUSTNESS_EDGE", detail
    if directions == {1}:
        return "CANDIDATE_DENIAL_EDGE", detail
    if directions == {-1}:
        return "CURRENT_DENIAL_EDGE", detail
    return "MIXED_DENIAL_EFFECTS", detail


def run_campaigns(
    root: Path,
    decks: dict[str, dict[str, StructuralDeckProfile]],
    args: argparse.Namespace,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    repo = CurrentOpponentRepository(root)
    record_map = {record.deck_id: record for record in repo.records()}
    missing = sorted(set(OPPONENT_IDS) - set(record_map))
    if missing:
        raise RuntimeError(f"preregistered current opponents are missing: {missing}")
    records = tuple(record_map[deck_id] for deck_id in OPPONENT_IDS)
    profiles = {deck_id: repo.profile(deck_id) for deck_id in OPPONENT_IDS}
    scheduler = BalancedPodScenarioScheduler(records, opponent_registry_hash=repo.registry_hash)
    scenarios = scheduler.schedule(args.games, seed=args.seed)
    pilot = PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)

    campaigns: dict[str, dict[str, Any]] = {}
    for index, state in enumerate(STRESS_STATES):
        pair = decks[state]
        campaign = run_balanced_paired_campaign(
            baseline=pair["current"],
            variant=pair["candidate"],
            opponent_profiles=profiles,
            scenarios=scenarios,
            pilot_config=pilot,
            max_turns=args.max_turns,
            statistics_seed=args.seed + index * 101,
            workers=args.workers,
        )
        if campaign.get("evidence_class") != EVIDENCE:
            raise RuntimeError(f"{state} campaign lost structural evidence boundary")
        pairing = campaign.get("pairing_conditions", {})
        for key in (
            "same_scenarios",
            "same_match_seeds",
            "same_own_seats",
            "same_opponent_seat_assignments",
            "same_pilot_configuration",
            "same_turn_cap",
            "common_random_numbers",
        ):
            if pairing.get(key) is not True:
                raise RuntimeError(f"{state} paired campaign condition failed: {key}")
        campaigns[state] = campaign

    metadata = {
        "opponent_registry_hash": repo.registry_hash,
        "opponent_deck_ids": list(OPPONENT_IDS),
        "opponent_evidence": {
            deck_id: list(repo.evidence_by_deck_id().get(deck_id, ("unknown",)))
            for deck_id in OPPONENT_IDS
        },
        "scenarios": [row.as_dict() for row in scenarios],
        "coverage_report": scheduler.coverage_report(scenarios),
        "frequency_interpretation": "experimental_equal_coverage_not_real_meta_frequency",
    }
    return campaigns, metadata


def write_summary(
    path: Path,
    manifest: dict[str, Any],
    diagnostics: dict[str, dict[str, Any]] | None,
    resilience: dict[str, dict[str, Any]] | None,
    error: str | None = None,
) -> None:
    lines = [
        "# RogShai Commander-Denial Robustness",
        "",
        f"- Campaign: `{CAMPAIGN_ID}`",
        f"- Reference: `{BASELINE_ID}`",
        f"- Candidate: `{CANDIDATE_ID}`",
        f"- Status: `{manifest['run_status']}`",
        f"- Evidence: `{EVIDENCE}`",
        f"- Synthetic assumption: `{SYNTHETIC_ASSUMPTION}`",
        f"- Denial-cost proxy: `{DENIAL_COST}`",
        "- Opponent scope: preregistered seven current local opponents.",
        "- Opponent frequencies: experimental equal coverage, not observed local meta frequency.",
        "- Canonical deck mutation: false",
        "- Automatic candidate promotion: false",
        "",
    ]
    if error:
        lines += ["## Run error", "", f"`{error}`", ""]
    if diagnostics and resilience:
        lines += ["## State results", ""]
        for state in STRESS_STATES:
            row = diagnostics[state]
            lines += [
                f"### {state}",
                "",
                (
                    "- Candidate-vs-current paired placement delta: "
                    f"`{row['candidate_vs_current_paired_placement_delta']}` "
                    "(positive favors candidate)"
                ),
                f"- Paired interval: `{row['paired_bootstrap_interval']}`",
            ]
            if state != "normal":
                robust = resilience[state]
                lines += [
                    (
                        "- Candidate resilience advantage: "
                        f"`{robust['candidate_resilience_advantage']}` "
                        "(positive means candidate degrades less than current)"
                    ),
                    f"- Resilience interval: `{robust['paired_bootstrap_interval']}`",
                ]
            lines.append("")
    lines += [
        "## Evidence boundary",
        "",
        "This is a Structural stress test, not empirical Commander win-rate evidence and not an external rules-engine run.",
        "The denial proxy means the named commander is effectively unavailable for the full game; it does not model exact removal, recast, tax, bounce or protection sequencing.",
        "MODEL_RESOLUTION_CURRENT is reported only as a reference threshold because its calibration domain is not the synthetic denial intervention itself.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "campaign_id": CAMPAIGN_ID,
        "baseline_id": BASELINE_ID,
        "candidate_id": CANDIDATE_ID,
        "commit_sha": commit_sha(root),
        "master_seed": args.seed,
        "games_per_state": args.games,
        "stress_states": {key: list(value) for key, value in STRESS_STATES.items()},
        "total_structural_games": args.games * len(STRESS_STATES) * 2,
        "max_turns": args.max_turns,
        "workers": args.workers,
        "evidence_class": EVIDENCE,
        "synthetic_assumption": SYNTHETIC_ASSUMPTION,
        "denial_cost_proxy": DENIAL_COST,
        "run_status": "RUN_INVALID",
        "canonical_deck_mutated": False,
        "inventory_mutated": False,
        "allocation_mutated": False,
        "reservation_created": False,
        "automatic_candidate_promotion": False,
    }
    try:
        if args.games not in ALLOWED_GAMES:
            raise ValueError("invalid preregistered campaign budget")
        candidate_path = root / CANDIDATE_PATH
        payload, candidate_board = load_candidate(candidate_path)
        if set(COMMANDERS) != {ISHAI, ROGRAKH}:
            raise RuntimeError("commander identity contract changed")

        resolution_payload = load_current_model_resolution(root)
        resolution = float(resolution_payload["effective_resolution"])
        context, enrichment, _ = enriched_context(root)
        current_board = current_control_mainboard(root)
        engine = WholeDeckSearchEngine(context, get_policy(PolicyId.OWNED_POOL_NEUTRAL))
        current_gate = engine.evaluate_mainboard(current_board).hard_gate
        candidate_gate = engine.evaluate_mainboard(candidate_board).hard_gate
        if not current_gate.valid:
            raise RuntimeError("current hard gate failed: " + "; ".join(current_gate.issues))
        if not candidate_gate.valid:
            raise RuntimeError("candidate hard gate failed: " + "; ".join(candidate_gate.issues))

        current = context.materialize(current_board, label=BASELINE_ID).model_copy(
            update={"deck_id": BASELINE_ID}
        )
        candidate = context.materialize(candidate_board, label=CANDIDATE_ID).model_copy(
            update={"deck_id": CANDIDATE_ID}
        )
        decks: dict[str, dict[str, StructuralDeckProfile]] = {}
        for state, denied in STRESS_STATES.items():
            decks[state] = {
                "current": denial_profile(current, state=state, denied_commanders=denied),
                "candidate": denial_profile(candidate, state=state, denied_commanders=denied),
            }

        campaigns, metadata = run_campaigns(root, decks, args)
        diagnostics = {
            state: campaign_diagnostic(campaign, resolution)
            for state, campaign in campaigns.items()
        }
        resilience = {
            state: resilience_summary(
                campaigns["normal"],
                campaigns[state],
                resolution=resolution,
                seed=args.seed + 1000 + index * 101,
            )
            for index, state in enumerate(("rograkh_denied", "ishai_denied", "both_denied"))
        }
        status, classification = classify(diagnostics, resilience, resolution)
        manifest.update(
            {
                "run_status": status,
                "candidate_file_sha256": sha256(candidate_path),
                "candidate_declared_deck_hash": payload.get("deck_hash"),
                "baseline_structural_deck_hash": current.deck_hash,
                "candidate_structural_deck_hash": candidate.deck_hash,
                "stress_profile_hashes": {
                    state: {
                        key: deck.deck_hash for key, deck in pair.items()
                    }
                    for state, pair in decks.items()
                },
                "data_snapshot_hash": context.snapshot_hash,
                "whole_deck_enrichment_snapshot_hash": enrichment.snapshot_hash,
                "opponent_registry_hash": metadata["opponent_registry_hash"],
                "opponent_deck_ids": metadata["opponent_deck_ids"],
                "opponent_evidence": metadata["opponent_evidence"],
                "frequency_interpretation": metadata["frequency_interpretation"],
                "model_resolution_reference": {
                    "effective_resolution": resolution,
                    "metric": resolution_payload.get("metric"),
                    "status": resolution_payload.get("status"),
                    "freshness_validated": resolution_payload.get("freshness_validated"),
                    "use_boundary": classification["resolution_use_boundary"],
                },
                "candidate_hard_gate": candidate_gate.model_dump(mode="json"),
                "current_hard_gate": current_gate.model_dump(mode="json"),
                "classification": classification,
            }
        )
        write_json(output / "run_manifest.json", manifest)
        write_json(
            output / "scenario_matrix.json",
            {
                "campaign_id": CAMPAIGN_ID,
                "scenarios": metadata["scenarios"],
                "coverage_report": metadata["coverage_report"],
                "opponent_deck_ids": metadata["opponent_deck_ids"],
                "frequency_interpretation": metadata["frequency_interpretation"],
                "same_scenarios_reused_across_all_stress_states": True,
            },
        )
        write_json(
            output / "denial_results.json",
            {
                "campaign_id": CAMPAIGN_ID,
                "diagnostics": diagnostics,
                "resilience": resilience,
                "classification": classification,
                "campaigns": campaigns,
            },
        )
        write_summary(output / "summary.md", manifest, diagnostics, resilience)
        write_checksums(output)
        print(json.dumps({"status": status, "output_dir": str(output)}, sort_keys=True))
        return 0
    except Exception as exc:
        manifest.update(
            {
                "run_status": "RUN_INVALID",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        write_json(output / "run_manifest.json", manifest)
        write_summary(
            output / "summary.md",
            manifest,
            None,
            None,
            f"{type(exc).__name__}: {exc}",
        )
        write_checksums(output)
        print(f"RUN_INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--games", type=int, choices=sorted(ALLOWED_GAMES), default=32)
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    parser.add_argument("--max-turns", type=int, default=35)
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
