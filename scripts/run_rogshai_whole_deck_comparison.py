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
from commander_lab.whole_deck.lab_context import enriched_context
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.orchestrator import (
    WholeDeckCampaignOrchestrator,
    WholeDeckCampaignSpecification,
)
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from commander_lab.whole_deck.search_context import current_control_mainboard

CAMPAIGN_ID = "rogshai-current-vs-final-2026-08-20-v1"
BASELINE_ID = "rogshai/current"
CANDIDATE_ID = "rogshai/final_recommended_2026-08-20"
CANDIDATE_PATH = Path("data/decks/candidates/rogshai_final_recommended_2026-08-20.json")
OUTPUT_DIR = Path("artifacts/rogshai_whole_deck_comparison")
COMMANDERS = {"Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"}
MASTER_SEED = 20260820
ALLOWED_GAMES = {32, 128, 256}
EVIDENCE = "structural_model_estimates"


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def git_sha(root: Path) -> str:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def candidate_mainboard(payload: dict[str, Any]) -> tuple[str, ...]:
    if payload.get("deck_id") != CANDIDATE_ID or payload.get("format") != "commander":
        raise ValueError("candidate identity/format mismatch")
    block = payload.get("commander")
    if not isinstance(block, dict) or set(map(str, block.get("commanders", []))) != COMMANDERS:
        raise ValueError("candidate commanders must be exactly Ishai + Rograkh")
    if block.get("uses_partner") is not True:
        raise ValueError("candidate must explicitly use partner commanders")
    rows = payload.get("cards")
    if not isinstance(rows, list):
        raise ValueError("candidate cards must be a list")
    total = commander_total = 0
    main: list[str] = []
    commander_counts: dict[str, int] = defaultdict(int)
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
            commander_total += qty
            commander_counts[name] += qty
        else:
            main.extend([name] * qty)
    if total != 100 or commander_total != 2 or len(main) != 98:
        raise ValueError(f"candidate must be 2+98=100; got {commander_total}+{len(main)}={total}")
    if any(commander_counts.get(name) != 1 for name in COMMANDERS):
        raise ValueError("each candidate commander must occur exactly once")
    return tuple(main)


def delta(row: dict[str, Any]) -> float:
    # Native campaign semantics: positive means candidate/variant improves placement.
    return float(row["baseline_placement"]) - float(row["variant_placement"])


def grouped(observations: list[dict[str, Any]], key: Callable[[dict[str, Any]], str]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in observations:
        values[key(row)].append(delta(row))
    return {name: fmean(rows) for name, rows in sorted(values.items())}


def diagnostics(campaign: dict[str, Any], resolution: float) -> dict[str, Any]:
    observations = campaign.get("paired_observations")
    paired = campaign.get("paired")
    if not isinstance(observations, list) or not observations or not isinstance(paired, dict):
        raise ValueError("malformed paired campaign")
    mean_delta = float(paired["paired_placement_delta"])
    interval = list(paired["paired_bootstrap_interval"])
    seat = grouped(observations, lambda row: str(row["own_seat"]))
    groups = grouped(observations, lambda row: "|".join(sorted(map(str, row["opponent_deck_ids"]))))
    return {
        "paired_placement_delta": mean_delta,
        "delta_semantics": "baseline_placement-candidate_placement; positive=candidate_better",
        "paired_bootstrap_interval": [float(interval[0]), float(interval[1])],
        "effective_resolution": resolution,
        "above_resolution": abs(mean_delta) >= resolution,
        "per_seat_paired_delta": seat,
        "per_opponent_group_paired_delta": groups,
        "material_seat_conflicts": {k: v for k, v in seat.items() if abs(v) >= resolution and v * mean_delta < 0},
        "material_opponent_group_conflicts": {k: v for k, v in groups.items() if abs(v) >= resolution and v * mean_delta < 0},
        "all_ties": all(abs(delta(row)) < 1e-12 for row in observations),
    }


def decide(primary: dict[str, Any], holdout: dict[str, Any] | None, resolution: float) -> tuple[str, dict[str, Any]]:
    p = diagnostics(primary, resolution)
    h = diagnostics(holdout, resolution) if holdout is not None else None
    value = float(p["paired_placement_delta"])
    detail: dict[str, Any] = {"primary": p, "holdout": h}
    if p["all_ties"]:
        detail["reason"] = "all paired primary placement observations are ties"
        return "MODEL_INFORMATION_LIMIT", detail
    if abs(value) < resolution:
        detail["reason"] = "primary paired placement delta is below live model resolution"
        return "KEEP_OPEN_BELOW_RESOLUTION", detail
    holdout_conflict = h is not None and abs(float(h["paired_placement_delta"])) >= resolution and float(h["paired_placement_delta"]) * value < 0
    if p["material_seat_conflicts"] or p["material_opponent_group_conflicts"] or holdout_conflict:
        detail["reason"] = "material seat/opponent-group or holdout direction conflict"
        detail["holdout_direction_conflict"] = holdout_conflict
        return "KEEP_OPEN_SCENARIO_DEPENDENT", detail
    low, high = p["paired_bootstrap_interval"]
    if not ((value > 0 and low > 0) or (value < 0 and high < 0)):
        detail["reason"] = "effect exceeds resolution but model-internal paired interval crosses zero"
        return "KEEP_OPEN_SCENARIO_DEPENDENT", detail
    detail["reason"] = "effect exceeds live resolution with consistent paired direction"
    return ("CANDIDATE_ADVANCES" if value > 0 else "CURRENT_PREFERRED"), detail


def summary(path: Path, manifest: dict[str, Any], status: str, detail: dict[str, Any] | None, error: str | None = None) -> None:
    lines = [
        "# RogShai Whole-Deck Paired Comparison", "",
        f"- Campaign: `{CAMPAIGN_ID}`", f"- Reference: `{BASELINE_ID}`", f"- Candidate: `{CANDIDATE_ID}`",
        f"- Decision: `{status}`", f"- Evidence: `{EVIDENCE}`",
        "- Opponent frequencies: experimental equal coverage, not observed local meta frequency.",
        "- Canonical deck mutation: false", "",
    ]
    if error:
        lines += ["## Run error", "", f"`{error}`", ""]
    if detail:
        p = detail["primary"]
        lines += [
            "## Primary metric", "",
            f"- Paired placement delta: `{p['paired_placement_delta']}` (positive favors candidate)",
            f"- Live effective resolution: `{p['effective_resolution']}`",
            f"- Above resolution: `{p['above_resolution']}`",
            f"- Reason: {detail['reason']}", "",
        ]
    lines += [
        "## Evidence boundary", "",
        "Structural model estimates only; not empirical Commander win-rate or external rules-engine evidence.",
        "The balanced campaign exposes placement, structural place-1 share, total damage and cards drawn; unexposed diagnostics are not fabricated.",
        "Commander-denial, 3P and 5P robustness remain separate campaigns.", "",
        "## Reproducibility", "",
        f"- Commit: `{manifest.get('commit_sha')}`", f"- Master seed: `{manifest.get('master_seed')}`",
        f"- Primary paired scenarios: `{manifest.get('primary_games')}`", f"- Holdout paired scenarios: `{manifest.get('holdout_games')}`", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def checksums(output: Path) -> None:
    target = output / "sha256sums.txt"
    target.write_text("\n".join(f"{file_sha256(p)}  {p.name}" for p in sorted(output.iterdir()) if p.is_file() and p != target) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "campaign_id": CAMPAIGN_ID, "baseline_id": BASELINE_ID, "candidate_id": CANDIDATE_ID,
        "commit_sha": git_sha(root), "master_seed": args.seed, "primary_games": args.games,
        "holdout_games": args.holdout_games, "max_turns": args.max_turns, "workers": args.workers,
        "evidence_class": EVIDENCE, "run_status": "RUN_INVALID", "canonical_deck_mutated": False,
        "inventory_mutated": False, "allocation_mutated": False, "reservation_created": False,
        "automatic_candidate_promotion": False,
    }
    try:
        if args.games not in ALLOWED_GAMES or args.holdout_games < 1:
            raise ValueError("invalid preregistered campaign budget")
        path = root / CANDIDATE_PATH
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("candidate payload must be an object")
        candidate_board = candidate_mainboard(payload)

        # This live validation fails closed if current deck/data/opponents/software make the stored threshold stale.
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
        orchestrator = WholeDeckCampaignOrchestrator(root)
        result = orchestrator.run_pair(
            baseline=baseline, variant=candidate,
            specification=WholeDeckCampaignSpecification(
                primary_games=args.games, holdout_games=args.holdout_games, seed=args.seed,
                max_turns=args.max_turns, workers=args.workers,
            ),
        )
        primary_bundle = result["primary"]
        holdout_bundle = result["holdout"]
        primary = primary_bundle["campaign"]
        holdout = holdout_bundle["campaign"] if isinstance(holdout_bundle, dict) else None
        if primary.get("evidence_class") != EVIDENCE:
            raise RuntimeError("paired campaign lost structural evidence boundary")
        pairing = primary.get("pairing_conditions", {})
        for key in ("same_scenarios", "same_match_seeds", "same_own_seats", "same_opponent_seat_assignments", "same_pilot_configuration", "same_turn_cap", "common_random_numbers"):
            if pairing.get(key) is not True:
                raise RuntimeError(f"paired campaign condition failed: {key}")

        status, detail = decide(primary, holdout, resolution)
        manifest.update({
            "run_status": status, "candidate_file_sha256": file_sha256(path),
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
            "frequency_interpretation": result["campaign_specification"]["frequency_interpretation"],
            "model_resolution": {"effective_resolution": resolution, "metric": resolution_payload.get("metric"), "status": resolution_payload.get("status"), "freshness_validated": resolution_payload.get("freshness_validated"), "measurement_artifact": resolution_payload.get("measurement_artifact")},
            "candidate_hard_gate": candidate_gate.model_dump(mode="json"),
            "current_hard_gate": current_gate.model_dump(mode="json"), "pairing_conditions": pairing,
            "decision_semantics": "paired_placement_delta=baseline placement-candidate placement; positive favors candidate",
        })
        dump(output / "run_manifest.json", manifest)
        dump(output / "scenario_matrix.json", {
            "campaign_id": CAMPAIGN_ID, "primary": primary_bundle["scenarios"],
            "primary_coverage": primary_bundle["coverage_report"],
            "holdout": holdout_bundle["scenarios"] if isinstance(holdout_bundle, dict) else [],
            "holdout_coverage": holdout_bundle["coverage_report"] if isinstance(holdout_bundle, dict) else None,
            "frequency_interpretation": result["campaign_specification"]["frequency_interpretation"],
        })
        dump(output / "paired_results.json", {
            "campaign_id": CAMPAIGN_ID, "decision": status, "decision_detail": detail, "primary_campaign": primary,
            "secondary_metric_scope": {
                "available": ["average_placement", "structural_model_estimated_place_1_share", "damage", "cards_drawn"],
                "not_exposed": ["life", "commander_damage", "ishai_peak_power", "ramp_events", "engine_value", "removal_events", "board_wipe_events", "archenemy_frequency"],
                "policy": "do_not_fabricate_unexposed_diagnostics",
            },
        })
        dump(output / "holdout_results.json", {"campaign_id": CAMPAIGN_ID, "construction_use": False, "holdout": holdout_bundle})
        summary(output / "summary.md", manifest, status, detail)
        checksums(output)
        print(json.dumps({"status": status, "output_dir": str(output)}, sort_keys=True))
        return 0
    except Exception as exc:
        manifest.update({"run_status": "RUN_INVALID", "error_type": type(exc).__name__, "error": str(exc)})
        dump(output / "run_manifest.json", manifest)
        summary(output / "summary.md", manifest, "RUN_INVALID", None, f"{type(exc).__name__}: {exc}")
        checksums(output)
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
