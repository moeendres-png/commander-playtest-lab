#!/usr/bin/env python3
"""Run the preregistered RogShai current-vs-final paired Whole-Deck campaign.

Evidence boundary: structural_model_estimates only. This script is read-only with respect to
canonical deck truth, inventory, allocations, reservations, and promotion decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Callable

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
CANDIDATE_RELATIVE_PATH = Path(
    "data/decks/candidates/rogshai_final_recommended_2026-08-20.json"
)
OUTPUT_RELATIVE_DIR = Path("artifacts/rogshai_whole_deck_comparison")
EXPECTED_COMMANDERS = {
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
}
MASTER_SEED = 20260820
ALLOWED_PRIMARY_GAMES = {32, 128, 256}
DEFAULT_HOLDOUT_GAMES = 16
EVIDENCE_CLASS = "structural_model_estimates"


def _json_dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_sha(root: Path) -> str:
    configured = os.environ.get("GITHUB_SHA", "").strip()
    if configured:
        return configured
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _expanded_mainboard(payload: dict[str, Any]) -> tuple[str, ...]:
    result: list[str] = []
    for row in payload.get("cards", []):
        if not isinstance(row, dict):
            raise ValueError("candidate card row must be an object")
        if row.get("zone") == "commander":
            continue
        quantity = int(row.get("quantity", 1))
        if quantity < 1:
            raise ValueError("candidate card quantity must be positive")
        result.extend([str(row["oracle_name"])] * quantity)
    return tuple(result)


def _validate_candidate_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    if payload.get("deck_id") != CANDIDATE_ID:
        raise ValueError(f"candidate deck_id must be {CANDIDATE_ID!r}")
    if payload.get("format") != "commander":
        raise ValueError("candidate format must be commander")
    commander_block = payload.get("commander")
    if not isinstance(commander_block, dict):
        raise ValueError("candidate commander block is missing")
    commanders = commander_block.get("commanders")
    if not isinstance(commanders, list) or set(map(str, commanders)) != EXPECTED_COMMANDERS:
        raise ValueError("candidate commanders must be exactly Ishai + Rograkh")
    if commander_block.get("uses_partner") is not True:
        raise ValueError("candidate must explicitly use partner commanders")

    card_rows = payload.get("cards")
    if not isinstance(card_rows, list):
        raise ValueError("candidate cards must be a list")
    total = 0
    commander_total = 0
    main_counts: Counter[str] = Counter()
    for row in card_rows:
        if not isinstance(row, dict):
            raise ValueError("candidate card row must be an object")
        name = str(row.get("oracle_name", "")).strip()
        if not name:
            raise ValueError("candidate card row has no oracle_name")
        quantity = int(row.get("quantity", 1))
        if quantity < 1:
            raise ValueError(f"candidate has invalid quantity for {name}")
        zone = str(row.get("zone", "main"))
        total += quantity
        if zone == "commander":
            commander_total += quantity
        elif zone == "main":
            main_counts[name] += quantity
        else:
            raise ValueError(f"candidate uses unsupported zone {zone!r}")
    if total != 100 or commander_total != 2 or sum(main_counts.values()) != 98:
        raise ValueError(
            f"candidate must be 2 commanders + 98 main cards = 100; got "
            f"commanders={commander_total}, main={sum(main_counts.values())}, total={total}"
        )
    for commander in EXPECTED_COMMANDERS:
        matching = sum(
            int(row.get("quantity", 1))
            for row in card_rows
            if row.get("zone") == "commander" and row.get("oracle_name") == commander
        )
        if matching != 1:
            raise ValueError(f"candidate commander {commander!r} must occur exactly once")
    return _expanded_mainboard(payload)


def _delta(row: dict[str, Any]) -> float:
    # Native Whole-Deck campaign semantics: positive means the variant/candidate places better.
    return float(row["baseline_placement"]) - float(row["variant_placement"])


def _group_deltas(
    observations: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], str]
) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in observations:
        grouped[key_fn(row)].append(_delta(row))
    return {key: fmean(values) for key, values in sorted(grouped.items())}


def _campaign_diagnostics(campaign: dict[str, Any], resolution: float) -> dict[str, Any]:
    observations = campaign.get("paired_observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("paired campaign has no observations")
    paired = campaign.get("paired")
    if not isinstance(paired, dict):
        raise ValueError("paired campaign has no paired summary")
    delta = float(paired["paired_placement_delta"])
    interval = paired.get("paired_bootstrap_interval")
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise ValueError("paired campaign has malformed bootstrap interval")
    seat_deltas = _group_deltas(observations, lambda row: str(row["own_seat"]))
    group_deltas = _group_deltas(
        observations,
        lambda row: "|".join(sorted(map(str, row["opponent_deck_ids"]))),
    )
    material_seat_conflicts = {
        key: value
        for key, value in seat_deltas.items()
        if abs(value) >= resolution and value * delta < 0
    }
    material_group_conflicts = {
        key: value
        for key, value in group_deltas.items()
        if abs(value) >= resolution and value * delta < 0
    }
    return {
        "paired_placement_delta": delta,
        "delta_semantics": "baseline_average_placement_minus_candidate_average_placement; positive=candidate_better",
        "paired_bootstrap_interval": [float(interval[0]), float(interval[1])],
        "effective_resolution": resolution,
        "above_resolution": abs(delta) >= resolution,
        "per_seat_paired_delta": seat_deltas,
        "per_opponent_group_paired_delta": group_deltas,
        "material_seat_conflicts": material_seat_conflicts,
        "material_opponent_group_conflicts": material_group_conflicts,
        "all_ties": all(abs(_delta(row)) < 1e-12 for row in observations),
    }


def _decision(
    primary: dict[str, Any], holdout: dict[str, Any] | None, resolution: float
) -> tuple[str, dict[str, Any]]:
    primary_diag = _campaign_diagnostics(primary, resolution)
    primary_delta = float(primary_diag["paired_placement_delta"])
    holdout_diag = _campaign_diagnostics(holdout, resolution) if holdout is not None else None

    if primary_diag["all_ties"]:
        return "MODEL_INFORMATION_LIMIT", {
            "reason": "all paired primary placement observations are ties",
            "primary": primary_diag,
            "holdout": holdout_diag,
        }
    if abs(primary_delta) < resolution:
        return "KEEP_OPEN_BELOW_RESOLUTION", {
            "reason": "primary paired placement delta is below live measured model resolution",
            "primary": primary_diag,
            "holdout": holdout_diag,
        }

    scenario_conflict = bool(primary_diag["material_seat_conflicts"]) or bool(
        primary_diag["material_opponent_group_conflicts"]
    )
    holdout_conflict = False
    if holdout_diag is not None:
        holdout_delta = float(holdout_diag["paired_placement_delta"])
        holdout_conflict = abs(holdout_delta) >= resolution and holdout_delta * primary_delta < 0
    if scenario_conflict or holdout_conflict:
        return "KEEP_OPEN_SCENARIO_DEPENDENT", {
            "reason": "material seat/opponent-group or holdout direction conflict",
            "primary": primary_diag,
            "holdout": holdout_diag,
            "holdout_direction_conflict": holdout_conflict,
        }

    interval = primary_diag["paired_bootstrap_interval"]
    interval_supports_direction = (primary_delta > 0 and interval[0] > 0) or (
        primary_delta < 0 and interval[1] < 0
    )
    if not interval_supports_direction:
        return "KEEP_OPEN_SCENARIO_DEPENDENT", {
            "reason": "primary effect exceeds resolution but model-internal paired interval crosses zero",
            "primary": primary_diag,
            "holdout": holdout_diag,
        }

    return (
        "CANDIDATE_ADVANCES" if primary_delta > 0 else "CURRENT_PREFERRED",
        {
            "reason": "primary effect exceeds live resolution with consistent paired direction",
            "primary": primary_diag,
            "holdout": holdout_diag,
        },
    )


def _write_summary(
    output_dir: Path,
    *,
    status: str,
    manifest: dict[str, Any],
    decision_detail: dict[str, Any] | None,
    error: str | None = None,
) -> None:
    lines = [
        "# RogShai Whole-Deck Paired Comparison",
        "",
        f"- Campaign: `{CAMPAIGN_ID}`",
        f"- Reference: `{BASELINE_ID}`",
        f"- Candidate: `{CANDIDATE_ID}`",
        f"- Decision: `{status}`",
        f"- Evidence: `{EVIDENCE_CLASS}`",
        "- Opponent frequency meaning: experimental equal coverage, not observed local meta frequency.",
        "- Canonical deck mutation: false",
        "",
    ]
    if error:
        lines.extend(["## Run error", "", f"`{error}`", ""])
    if decision_detail:
        primary = decision_detail.get("primary", {})
        lines.extend(
            [
                "## Primary decision metric",
                "",
                f"- Paired placement delta: `{primary.get('paired_placement_delta')}`",
                "- Delta semantics: baseline placement minus candidate placement; positive favors candidate.",
                f"- Live effective resolution: `{primary.get('effective_resolution')}`",
                f"- Above resolution: `{primary.get('above_resolution')}`",
                f"- Reason: {decision_detail.get('reason')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Evidence boundary",
            "",
            "These are structural model estimates, not empirical Commander win rates and not external rules-engine evidence.",
            "The balanced campaign currently exposes placement, structural place-1 share, total damage and cards drawn; unexposed diagnostics are not fabricated.",
            "Commander-denial, 3P and 5P robustness remain separate campaigns.",
            "",
            "## Reproducibility",
            "",
            f"- Commit: `{manifest.get('commit_sha')}`",
            f"- Master seed: `{manifest.get('master_seed')}`",
            f"- Primary paired scenarios: `{manifest.get('primary_games')}`",
            f"- Holdout paired scenarios: `{manifest.get('holdout_games')}`",
        ]
    )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checksums(output_dir: Path) -> None:
    checksum_path = output_dir / "sha256sums.txt"
    rows = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != checksum_path.name:
            rows.append(f"{_sha256_file(path)}  {path.name}")
    checksum_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = root / OUTPUT_RELATIVE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = root / CANDIDATE_RELATIVE_PATH
    manifest: dict[str, Any] = {
        "campaign_id": CAMPAIGN_ID,
        "baseline_id": BASELINE_ID,
        "candidate_id": CANDIDATE_ID,
        "commit_sha": _git_sha(root),
        "master_seed": args.seed,
        "primary_games": args.games,
        "holdout_games": args.holdout_games,
        "max_turns": args.max_turns,
        "workers": args.workers,
        "evidence_class": EVIDENCE_CLASS,
        "canonical_deck_mutated": False,
        "inventory_mutated": False,
        "allocation_mutated": False,
        "reservation_created": False,
        "automatic_candidate_promotion": False,
        "run_status": "RUN_INVALID",
    }
    try:
        if args.games not in ALLOWED_PRIMARY_GAMES:
            raise ValueError(f"--games must be one of {sorted(ALLOWED_PRIMARY_GAMES)}")
        if args.holdout_games < 1:
            raise ValueError("--holdout-games must be positive for this preregistered comparison")
        if not candidate_path.is_file():
            raise FileNotFoundError(candidate_path)

        candidate_bytes_sha = _sha256_file(candidate_path)
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("candidate payload must be a JSON object")
        candidate_mainboard = _validate_candidate_payload(payload)

        # Fail closed on stale model-resolution truth before spending simulation budget.
        resolution_payload = load_current_model_resolution(root)
        effective_resolution = float(resolution_payload["effective_resolution"])

        context, enrichment, _ = enriched_context(root)
        current_mainboard = current_control_mainboard(root)
        engine = WholeDeckSearchEngine(context, get_policy(PolicyId.OWNED_POOL_NEUTRAL))
        candidate_gate = engine.evaluate_mainboard(candidate_mainboard).hard_gate
        current_gate = engine.evaluate_mainboard(current_mainboard).hard_gate
        if not current_gate.valid:
            raise RuntimeError("current RogShai Whole-Deck hard gate failed: " + "; ".join(current_gate.issues))
        if not candidate_gate.valid:
            raise RuntimeError("candidate Whole-Deck hard gate failed: " + "; ".join(candidate_gate.issues))

        baseline = context.materialize(current_mainboard, label=BASELINE_ID).model_copy(
            update={"deck_id": BASELINE_ID}
        )
        candidate = context.materialize(candidate_mainboard, label=CANDIDATE_ID).model_copy(
            update={"deck_id": CANDIDATE_ID}
        )
        orchestrator = WholeDeckCampaignOrchestrator(root)
        spec = WholeDeckCampaignSpecification(
            primary_games=args.games,
            holdout_games=args.holdout_games,
            seed=args.seed,
            max_turns=args.max_turns,
            workers=args.workers,
        )
        result = orchestrator.run_pair(
            baseline=baseline,
            variant=candidate,
            specification=spec,
        )
        primary_bundle = result.get("primary")
        if not isinstance(primary_bundle, dict) or not isinstance(primary_bundle.get("campaign"), dict):
            raise RuntimeError("malformed primary campaign result")
        holdout_bundle = result.get("holdout")
        holdout_campaign = None
        if holdout_bundle is not None:
            if not isinstance(holdout_bundle, dict) or not isinstance(holdout_bundle.get("campaign"), dict):
                raise RuntimeError("malformed holdout campaign result")
            holdout_campaign = holdout_bundle["campaign"]

        primary_campaign = primary_bundle["campaign"]
        status, decision_detail = _decision(
            primary_campaign, holdout_campaign, effective_resolution
        )
        pairing = primary_campaign.get("pairing_conditions", {})
        required_pairing = {
            "same_scenarios": True,
            "same_match_seeds": True,
            "same_own_seats": True,
            "same_opponent_seat_assignments": True,
            "same_pilot_configuration": True,
            "same_turn_cap": True,
            "common_random_numbers": True,
        }
        if any(pairing.get(key) is not expected for key, expected in required_pairing.items()):
            raise RuntimeError("paired campaign conditions are not satisfied")
        if primary_campaign.get("evidence_class") != EVIDENCE_CLASS:
            raise RuntimeError("paired campaign lost structural evidence boundary")

        manifest.update(
            {
                "run_status": status,
                "candidate_file_sha256": candidate_bytes_sha,
                "candidate_declared_deck_hash": payload.get("deck_hash"),
                "candidate_source_sha256": payload.get("source", {}).get("sha256"),
                "candidate_source_drive_file_id": "1VK9kv8yhvorml0zyTKKiMV4sDUubhYtJ",
                "candidate_printings_drive_file_id": "1VXBzHEeCdM0DLUharh9DyiFeS_rbgw7R",
                "candidate_plaintext_drive_file_id": "19TZlBBcN5CQzOCdGWTNJ3C2AAIOQE2CY",
                "baseline_structural_deck_hash": baseline.deck_hash,
                "candidate_structural_deck_hash": candidate.deck_hash,
                "data_snapshot_hash": context.snapshot_hash,
                "opponent_registry_hash": result.get("opponent_registry_hash"),
                "opponent_deck_ids": result.get("opponent_deck_ids"),
                "frequency_interpretation": result.get("campaign_specification", {}).get(
                    "frequency_interpretation"
                ),
                "model_resolution": {
                    "effective_resolution": effective_resolution,
                    "metric": resolution_payload.get("metric"),
                    "status": resolution_payload.get("status"),
                    "freshness_validated": resolution_payload.get("freshness_validated"),
                    "measurement_artifact": resolution_payload.get("measurement_artifact"),
                },
                "candidate_hard_gate": candidate_gate.model_dump(mode="json"),
                "current_hard_gate": current_gate.model_dump(mode="json"),
                "pairing_conditions": pairing,
                "whole_deck_context_enrichment": enrichment,
                "decision_semantics": "paired_placement_delta = baseline placement - candidate placement; positive favors candidate",
            }
        )

        _json_dump(output_dir / "run_manifest.json", manifest)
        _json_dump(
            output_dir / "scenario_matrix.json",
            {
                "campaign_id": CAMPAIGN_ID,
                "primary": primary_bundle.get("scenarios"),
                "primary_coverage": primary_bundle.get("coverage_report"),
                "holdout": holdout_bundle.get("scenarios") if isinstance(holdout_bundle, dict) else [],
                "holdout_coverage": holdout_bundle.get("coverage_report") if isinstance(holdout_bundle, dict) else None,
                "frequency_interpretation": result.get("campaign_specification", {}).get(
                    "frequency_interpretation"
                ),
            },
        )
        _json_dump(
            output_dir / "paired_results.json",
            {
                "campaign_id": CAMPAIGN_ID,
                "decision": status,
                "decision_detail": decision_detail,
                "primary_campaign": primary_campaign,
                "secondary_metric_scope": {
                    "available_in_balanced_campaign": [
                        "average_placement",
                        "structural_model_estimated_place_1_share",
                        "damage",
                        "cards_drawn",
                    ],
                    "not_exposed_by_current_balanced_campaign": [
                        "life",
                        "commander_damage",
                        "ishai_peak_power",
                        "ramp_events",
                        "engine_value",
                        "removal_events",
                        "board_wipe_events",
                        "archenemy_frequency",
                    ],
                    "policy": "do_not_fabricate_unexposed_diagnostics",
                },
            },
        )
        _json_dump(
            output_dir / "holdout_results.json",
            {
                "campaign_id": CAMPAIGN_ID,
                "construction_use": False,
                "holdout": holdout_bundle,
            },
        )
        _write_summary(
            output_dir,
            status=status,
            manifest=manifest,
            decision_detail=decision_detail,
        )
        _write_checksums(output_dir)
        print(json.dumps({"status": status, "output_dir": str(output_dir)}, sort_keys=True))
        return 0
    except Exception as exc:
        manifest["run_status"] = "RUN_INVALID"
        manifest["error_type"] = type(exc).__name__
        manifest["error"] = str(exc)
        _json_dump(output_dir / "run_manifest.json", manifest)
        _write_summary(
            output_dir,
            status="RUN_INVALID",
            manifest=manifest,
            decision_detail=None,
            error=f"{type(exc).__name__}: {exc}",
        )
        _write_checksums(output_dir)
        print(f"RUN_INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--games", type=int, default=32, choices=sorted(ALLOWED_PRIMARY_GAMES))
    parser.add_argument("--holdout-games", type=int, default=DEFAULT_HOLDOUT_GAMES)
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    parser.add_argument("--max-turns", type=int, default=14)
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
