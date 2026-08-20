#!/usr/bin/env python3
"""Preregistered RogShai current-vs-final paired Whole-Deck campaign.

Evidence: structural_model_estimates only. Canonical deck/inventory/allocation state is read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.current_model_resolution import load_current_model_resolution
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.whole_deck.campaign import run_balanced_paired_campaign
from commander_lab.whole_deck.lab_context import enriched_context
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from commander_lab.whole_deck.search_context import current_control_mainboard

CAMPAIGN_ID = "rogshai-current-vs-final-2026-08-20-v1"
BASELINE_ID = "rogshai/current"
CANDIDATE_ID = "rogshai/final_recommended_2026-08-20"
CANDIDATE_PATH = Path("data/decks/candidates/rogshai_final_recommended_2026-08-20.json")
OUTPUT_DIR = Path("artifacts/rogshai_whole_deck_comparison")
COMMANDERS = {"Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"}
OPPONENT_IDS = (
    "opponent/blight-curse-precon",
    "opponent/cosmic-spiderman-midbudget",
    "opponent/dance-elements-precon",
    "opponent/doom-prevails-precon",
    "kaervek/current",
    "opponent/morcant-elves",
    "opponent/wakanda-forever-precon",
)
EVIDENCE = "structural_model_estimates"
MASTER_SEED = 20260820
HOLDOUT_SEED_XOR = 0x5F37_9A21
ALLOWED_GAMES = {32, 128, 256}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commit_sha(root: Path) -> str:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_candidate(path: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("deck_id") != CANDIDATE_ID or raw.get("format") != "commander":
        raise ValueError("candidate identity/format mismatch")
    commander = raw.get("commander")
    if not isinstance(commander, dict) or set(map(str, commander.get("commanders", []))) != COMMANDERS:
        raise ValueError("candidate commanders must be exactly Ishai + Rograkh")
    if commander.get("uses_partner") is not True:
        raise ValueError("candidate must explicitly use partner commanders")
    rows = raw.get("cards")
    if not isinstance(rows, list):
        raise ValueError("candidate cards must be a list")
    main: list[str] = []
    commander_counts: dict[str, int] = defaultdict(int)
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("candidate card row must be an object")
        name = str(row.get("oracle_name", "")).strip()
        qty = int(row.get("quantity", 1))
        zone = str(row.get("zone", "main"))
        if not name or qty < 1 or zone not in {"main", "commander"}:
            raise ValueError(f"invalid candidate row: {row!r}")
        total += qty
        if zone == "commander":
            commander_counts[name] += qty
        else:
            main.extend([name] * qty)
    if total != 100 or len(main) != 98 or any(commander_counts.get(name) != 1 for name in COMMANDERS):
        raise ValueError("candidate must contain exactly two partner commanders and 98 main cards")
    return raw, tuple(main)


def paired_delta(row: dict[str, Any]) -> float:
    return float(row["baseline_placement"]) - float(row["variant_placement"])


def grouped_delta(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], str]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(paired_delta(row))
    return {name: fmean(values) for name, values in sorted(grouped.items())}


def diagnostic(campaign: dict[str, Any], resolution: float) -> dict[str, Any]:
    rows = campaign["paired_observations"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("paired campaign has no observations")
    value = float(campaign["paired"]["paired_placement_delta"])
    interval = [float(v) for v in campaign["paired"]["paired_bootstrap_interval"]]
    seat = grouped_delta(rows, lambda row: str(row["own_seat"]))
    pods = grouped_delta(rows, lambda row: "|".join(sorted(map(str, row["opponent_deck_ids"]))))
    return {
        "paired_placement_delta": value,
        "delta_semantics": "baseline_placement-candidate_placement; positive=candidate_better",
        "paired_bootstrap_interval": interval,
        "effective_resolution": resolution,
        "above_resolution": abs(value) >= resolution,
        "all_ties": all(abs(paired_delta(row)) < 1e-12 for row in rows),
        "per_seat_paired_delta": seat,
        "per_opponent_group_paired_delta": pods,
        "material_seat_conflicts": {k: v for k, v in seat.items() if abs(v) >= resolution and v * value < 0},
        "material_opponent_group_conflicts": {k: v for k, v in pods.items() if abs(v) >= resolution and v * value < 0},
    }


def decide(primary: dict[str, Any], holdout: dict[str, Any], resolution: float) -> tuple[str, dict[str, Any]]:
    p = diagnostic(primary, resolution)
    h = diagnostic(holdout, resolution)
    value = float(p["paired_placement_delta"])
    detail: dict[str, Any] = {"primary": p, "holdout": h}
    if p["all_ties"]:
        detail["reason"] = "all paired primary placement observations are ties"
        return "MODEL_INFORMATION_LIMIT", detail
    if abs(value) < resolution:
        detail["reason"] = "primary paired placement delta is below live model resolution"
        return "KEEP_OPEN_BELOW_RESOLUTION", detail
    holdout_value = float(h["paired_placement_delta"])
    conflict = (
        bool(p["material_seat_conflicts"])
        or bool(p["material_opponent_group_conflicts"])
        or (abs(holdout_value) >= resolution and holdout_value * value < 0)
    )
    if conflict:
        detail["reason"] = "material seat/opponent-group or holdout direction conflict"
        return "KEEP_OPEN_SCENARIO_DEPENDENT", detail
    low, high = p["paired_bootstrap_interval"]
    if not ((value > 0 and low > 0) or (value < 0 and high < 0)):
        detail["reason"] = "effect exceeds resolution but model-internal paired interval crosses zero"
        return "KEEP_OPEN_SCENARIO_DEPENDENT", detail
    detail["reason"] = "effect exceeds live resolution with consistent paired direction"
    return ("CANDIDATE_ADVANCES" if value > 0 else "CURRENT_PREFERRED"), detail


def run_pair(root: Path, baseline: Any, candidate: Any, args: argparse.Namespace) -> dict[str, Any]:
    repo = CurrentOpponentRepository(root)
    record_map = {record.deck_id: record for record in repo.records()}
    missing = sorted(set(OPPONENT_IDS) - set(record_map))
    if missing:
        raise RuntimeError(f"preregistered current opponents are missing: {missing}")
    records = tuple(record_map[deck_id] for deck_id in OPPONENT_IDS)
    profiles = {deck_id: repo.profile(deck_id) for deck_id in OPPONENT_IDS}
    scheduler = BalancedPodScenarioScheduler(records, opponent_registry_hash=repo.registry_hash)
    pilot = PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)

    primary_scenarios = scheduler.schedule(args.games, seed=args.seed)
    holdout_seed = args.seed ^ HOLDOUT_SEED_XOR
    holdout_scenarios = scheduler.schedule(args.holdout_games, seed=holdout_seed)
    if {s.seed for s in primary_scenarios} & {s.seed for s in holdout_scenarios}:
        raise RuntimeError("primary and holdout scenario seeds overlap")

    def campaign(scenarios: Any, seed: int) -> dict[str, Any]:
        return run_balanced_paired_campaign(
            baseline=baseline,
            variant=candidate,
            opponent_profiles=profiles,
            scenarios=scenarios,
            pilot_config=pilot,
            max_turns=args.max_turns,
            statistics_seed=seed,
            workers=args.workers,
        )

    return {
        "campaign_specification": {
            "primary_games": args.games,
            "holdout_games": args.holdout_games,
            "seed": args.seed,
            "max_turns": args.max_turns,
            "workers": args.workers,
            "pod_size": 4,
            "frequency_interpretation": "experimental_equal_coverage_not_real_meta_frequency",
            "opponent_scope": "preregistered_seven_current_local_opponents",
        },
        "opponent_registry_hash": repo.registry_hash,
        "opponent_deck_ids": list(OPPONENT_IDS),
        "opponent_evidence": {deck_id: list(repo.evidence_by_deck_id().get(deck_id, ("unknown",))) for deck_id in OPPONENT_IDS},
        "primary": {
            "scenarios": [row.as_dict() for row in primary_scenarios],
            "coverage_report": scheduler.coverage_report(primary_scenarios),
            "campaign": campaign(primary_scenarios, args.seed),
        },
        "holdout": {
            "construction_use": False,
            "master_seed": holdout_seed,
            "scenarios": [row.as_dict() for row in holdout_scenarios],
            "coverage_report": scheduler.coverage_report(holdout_scenarios),
            "campaign": campaign(holdout_scenarios, holdout_seed),
        },
    }


def write_summary(path: Path, manifest: dict[str, Any], detail: dict[str, Any] | None, error: str | None = None) -> None:
    status = manifest["run_status"]
    lines = [
        "# RogShai Whole-Deck Paired Comparison", "",
        f"- Campaign: `{CAMPAIGN_ID}`", f"- Reference: `{BASELINE_ID}`", f"- Candidate: `{CANDIDATE_ID}`",
        f"- Decision: `{status}`", f"- Evidence: `{EVIDENCE}`",
        "- Opponent scope: preregistered seven current local opponents.",
        "- Opponent frequencies: experimental equal coverage, not observed local meta frequency.",
        "- Canonical deck mutation: false", "",
    ]
    if error:
        lines += ["## Run error", "", f"`{error}`", ""]
    if detail:
        p = detail["primary"]
        lines += ["## Primary metric", "", f"- Paired placement delta: `{p['paired_placement_delta']}` (positive favors candidate)", f"- Live effective resolution: `{p['effective_resolution']}`", f"- Above resolution: `{p['above_resolution']}`", f"- Reason: {detail['reason']}", ""]
    lines += ["## Evidence boundary", "", "Structural model estimates only; not empirical Commander win-rate or external rules-engine evidence.", "Commander-denial, 3P and 5P robustness remain separate campaigns.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_checksums(output: Path) -> None:
    target = output / "sha256sums.txt"
    target.write_text("\n".join(f"{sha256(path)}  {path.name}" for path in sorted(output.iterdir()) if path.is_file() and path != target) + "\n", encoding="utf-8")


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
        "primary_games": args.games,
        "holdout_games": args.holdout_games,
        "max_turns": args.max_turns,
        "workers": args.workers,
        "evidence_class": EVIDENCE,
        "run_status": "RUN_INVALID",
        "canonical_deck_mutated": False,
        "inventory_mutated": False,
        "allocation_mutated": False,
        "reservation_created": False,
        "automatic_candidate_promotion": False,
    }
    try:
        if args.games not in ALLOWED_GAMES or args.holdout_games < 1:
            raise ValueError("invalid preregistered campaign budget")
        candidate_path = root / CANDIDATE_PATH
        payload, candidate_board = load_candidate(candidate_path)

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

        baseline = context.materialize(current_board, label=BASELINE_ID).model_copy(update={"deck_id": BASELINE_ID})
        candidate = context.materialize(candidate_board, label=CANDIDATE_ID).model_copy(update={"deck_id": CANDIDATE_ID})
        result = run_pair(root, baseline, candidate, args)
        primary = result["primary"]["campaign"]
        holdout = result["holdout"]["campaign"]
        if primary.get("evidence_class") != EVIDENCE:
            raise RuntimeError("paired campaign lost structural evidence boundary")
        pairing = primary.get("pairing_conditions", {})
        for key in ("same_scenarios", "same_match_seeds", "same_own_seats", "same_opponent_seat_assignments", "same_pilot_configuration", "same_turn_cap", "common_random_numbers"):
            if pairing.get(key) is not True:
                raise RuntimeError(f"paired campaign condition failed: {key}")

        status, detail = decide(primary, holdout, resolution)
        manifest.update({
            "run_status": status,
            "candidate_file_sha256": sha256(candidate_path),
            "candidate_declared_deck_hash": payload.get("deck_hash"),
            "candidate_source_sha256": payload.get("source", {}).get("sha256"),
            "candidate_source_drive_file_id": "1VK9kv8yhvorml0zyTKKiMV4sDUubhYtJ",
            "candidate_printings_drive_file_id": "1VXBzHEeCdM0DLUharh9DyiFeS_rbgw7R",
            "candidate_plaintext_drive_file_id": "19TZlBBcN5CQzOCdGWTNJ3C2AAIOQE2CY",
            "baseline_structural_deck_hash": baseline.deck_hash,
            "candidate_structural_deck_hash": candidate.deck_hash,
            "data_snapshot_hash": context.snapshot_hash,
            "whole_deck_enrichment_snapshot_hash": enrichment.snapshot_hash,
            "opponent_registry_hash": result["opponent_registry_hash"],
            "opponent_deck_ids": result["opponent_deck_ids"],
            "opponent_evidence": result["opponent_evidence"],
            "opponent_scope": result["campaign_specification"]["opponent_scope"],
            "frequency_interpretation": result["campaign_specification"]["frequency_interpretation"],
            "model_resolution": {"effective_resolution": resolution, "metric": resolution_payload.get("metric"), "status": resolution_payload.get("status"), "freshness_validated": resolution_payload.get("freshness_validated"), "measurement_artifact": resolution_payload.get("measurement_artifact")},
            "candidate_hard_gate": candidate_gate.model_dump(mode="json"),
            "current_hard_gate": current_gate.model_dump(mode="json"),
            "pairing_conditions": pairing,
        })
        write_json(output / "run_manifest.json", manifest)
        write_json(output / "scenario_matrix.json", {
            "campaign_id": CAMPAIGN_ID,
            "primary": result["primary"]["scenarios"],
            "primary_coverage": result["primary"]["coverage_report"],
            "holdout": result["holdout"]["scenarios"],
            "holdout_coverage": result["holdout"]["coverage_report"],
            "opponent_deck_ids": result["opponent_deck_ids"],
            "frequency_interpretation": result["campaign_specification"]["frequency_interpretation"],
        })
        write_json(output / "paired_results.json", {"campaign_id": CAMPAIGN_ID, "decision": status, "decision_detail": detail, "primary_campaign": primary})
        write_json(output / "holdout_results.json", {"campaign_id": CAMPAIGN_ID, "construction_use": False, "holdout": result["holdout"]})
        write_summary(output / "summary.md", manifest, detail)
        write_checksums(output)
        print(json.dumps({"status": status, "output_dir": str(output)}, sort_keys=True))
        return 0
    except Exception as exc:
        manifest.update({"run_status": "RUN_INVALID", "error_type": type(exc).__name__, "error": str(exc)})
        write_json(output / "run_manifest.json", manifest)
        write_summary(output / "summary.md", manifest, None, f"{type(exc).__name__}: {exc}")
        write_checksums(output)
        print(f"RUN_INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--games", type=int, choices=sorted(ALLOWED_GAMES), default=32)
    parser.add_argument("--holdout-games", type=int, default=16)
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    parser.add_argument("--max-turns", type=int, default=35)
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
