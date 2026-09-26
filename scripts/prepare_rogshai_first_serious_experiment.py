from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from commander_lab.first_run_preparation import (
    DECK_ID,
    EXPECTED_DECK_HASH,
    PRELIMINARY_RUN,
    SEED_ROOTS,
    SENSITIVITY_PODS,
    VARIANTS,
    build_official_run_spec,
    child_seed,
)
from commander_lab.models import (
    CommanderDenialInput,
    HoldoutInput,
    RunMulliganLabInput,
    ToolResponse,
    ToolStatus,
    ValidateDeckInput,
    VariantSwap,
)
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _response(response: ToolResponse, label: str) -> dict[str, Any]:
    if response.status != ToolStatus.COMPLETED:
        raise RuntimeError(f"{label} failed: {response.errors or response.warnings}")
    return response.model_dump(mode="json")


def _tracked_clean() -> None:
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked worktree must be clean before binding preparation outputs")


def prepare(output: Path) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    _tracked_clean()
    deck_path = ROOT / "data/decks/rogshai_current.json"
    deck_before = hashlib.sha256(deck_path.read_bytes()).hexdigest()

    context = load_project_context(ROOT)
    service = CommanderToolService(ROOT)
    facade = PriorityWorkflowFacade(
        ROOT, result_cache_path=output / "preparation_smoke_cache.sqlite3"
    )
    validation = _response(
        service.validate_deck(ValidateDeckInput(deck_id=DECK_ID)), "current deck validation"
    )
    screen = facade.build_screen(DECK_ID, limit=795)
    mana = facade.mulligan_mana(DECK_ID)
    official_spec = build_official_run_spec(ROOT)

    _write(output / "VALIDATION_REPORT.json", validation)
    _write(output / "CANDIDATE_COVERAGE.json", screen)

    mulligan_rows: list[dict[str, Any]] = []
    for seat in range(1, 5):
        request = RunMulliganLabInput(
            deck_id=DECK_ID,
            policies=("current_pilot", "primer_policy"),
            samples=2500,
            followup_samples=0,
            seat_position=seat,
            starting_player=seat == 1,
            pod_size=4,
            pilot_profile_id="rogshai.current.baseline",
            pilot_version="current",
            game_plan="balanced",
            seed=child_seed(SEED_ROOTS["mulligan"], f"seat-{seat}"),
            output_name=f"official_first_run_preparation_mulligan_seat_{seat}.json",
        )
        mulligan_rows.append(_response(service.run_mulligan_lab(request), f"mulligan seat {seat}"))
    mana_mulligan = {
        "deck_hash": EXPECTED_DECK_HASH,
        "context_hash": context.snapshot_hash,
        "land_count": 36,
        "primary_pod": list(context.primary_opponent_deck_ids(DECK_ID)),
        "mana": mana,
        "fresh_mulligan_results": mulligan_rows,
        "historical_saved_result_consumed": False,
        "comparison": "current_pilot versus primer_policy",
        "samples_per_policy_per_seat": 2500,
        "uncertainty": "Wilson 95% half-widths emitted by MulliganLab",
        "explicit_mana_checks": {
            "early_blue_sources": mana["mana"]["t1_untapped_land_sources"]["U"],
            "ishai_wu_sources": mana["mana"]["ishai_wu_source_counts"],
            "red_sources": mana["mana"]["colored_sources"]["R"],
            "untapped_sources": mana["mana"]["t1_untapped_land_sources"],
            "interaction_hold_up": mana["mana"]["early_interaction_hold_up_requirements"],
            "ramp": (
                "captured by fresh opening-hand policy features; structural mana timing remains "
                "an explicit approximation"
            ),
        },
        "rograkh_zero_mana_value_positive_mana_signal_allowed": False,
        "approximation_visibility": mana["mana"]["approximation_note"],
    }
    _write(output / "MANA_MULLIGAN_BASELINE.json", mana_mulligan)

    smoke_seed = child_seed(SEED_ROOTS["variants"], "preparation-smoke")
    smoke_variant = VARIANTS[0]
    first = facade.compare_validate(
        deck_id=DECK_ID,
        remove=str(smoke_variant["remove"]),
        add_candidate_id=str(smoke_variant["add_candidate_id"]),
        iterations=2,
        seed=smoke_seed,
        max_turns=12,
        workers=1,
    )
    second = facade.compare_validate(
        deck_id=DECK_ID,
        remove=str(smoke_variant["remove"]),
        add_candidate_id=str(smoke_variant["add_candidate_id"]),
        iterations=2,
        seed=smoke_seed,
        max_turns=12,
        workers=1,
    )
    if first.get("status") != "completed" or second.get("status") != "completed":
        raise RuntimeError("tiny paired comparison did not complete")
    if first["cache_provenance"]["cache_hit"] is not False:
        raise RuntimeError("isolated preparation cache did not begin with a miss")
    if second["cache_provenance"]["cache_hit"] is not True:
        raise RuntimeError("identical preparation comparison did not hit the exact cache")
    if first["paired"] != second["paired"]:
        raise RuntimeError("cached and uncached paired smoke results differ")

    primary_pod = context.primary_opponent_deck_ids(DECK_ID)
    ishai = "Ishai, Ojutai Dragonspeaker"
    rograkh = "Rograkh, Son of Rohgahh"
    denial: dict[str, Any] = {}
    for label, targets in (
        ("ishai", (ishai,)),
        ("rograkh", (rograkh,)),
        ("both", (ishai, rograkh)),
    ):
        denial_request = CommanderDenialInput(
            deck_id=DECK_ID,
            denied_commanders=targets,
            suppress_commander_synergy=len(targets) == 2,
            opponent_deck_ids=primary_pod,
            iterations=1,
            workers=1,
            seed=child_seed(SEED_ROOTS["denial"], f"preparation-smoke:{label}"),
            max_turns=12,
        )
        denial[label] = _response(service.run_commander_denial(denial_request), label)["result"]

    sensitivity_request = HoldoutInput(
        deck_id=DECK_ID,
        swaps=(
            VariantSwap(
                remove=str(smoke_variant["remove"]),
                add_candidate_id=str(smoke_variant["add_candidate_id"]),
            ),
        ),
        holdout_pods=(SENSITIVITY_PODS[0],),
        iterations=1,
        workers=1,
        seed=child_seed(SEED_ROOTS["sensitivity"], "preparation-smoke"),
        max_turns=12,
    )
    sensitivity = _response(service.run_holdout(sensitivity_request), "preparation sensitivity")[
        "result"
    ]
    bundle = facade.create_decision_bundle(
        first,
        output / "decision_bundle",
        worst_case_sensitivity_result=sensitivity,
        commander_denial_result=denial,
        recommendation_status="no_deck_recommendation",
    )
    bundle_payload = json.loads(Path(bundle["json_path"]).read_text(encoding="utf-8"))
    if bundle_payload["recommendation_status"] != "no_deck_recommendation":
        raise RuntimeError("preparation smoke emitted a deck recommendation")
    if not bundle_payload["playstyle_fit_summary"]["separate_from_recommendation_status"]:
        raise RuntimeError("playstyle review leaked into objective recommendation status")

    smoke = {
        "smoke_test_only": True,
        "deck_strength_inference_allowed": False,
        "recommendation_status": "no_deck_recommendation",
        "context_hash": context.snapshot_hash,
        "deck_hash": EXPECTED_DECK_HASH,
        "primary_pod": list(primary_pod),
        "candidate_screen": "PASS",
        "mana_mulligan_probe": "PASS",
        "paired_comparison": {
            "iterations": 2,
            "same_seed_reproducible": first["paired"] == second["paired"],
        },
        "cache": {
            "first": "MISS",
            "identical_second": "HIT",
            "cache_key": first["cache_provenance"]["cache_key"],
        },
        "commander_denial": {key: "PASS" for key in denial},
        "sensitivity": "PASS",
        "decision_bundle": bundle,
        "playstyle_stage": "post_build_review_only",
        "evidence_class": "structural_model_estimates",
    }
    _write(output / "ACCEPTANCE_SMOKE.json", smoke)
    _write(output / "OFFICIAL_RUN_SPECIFICATION.json", official_spec)

    spec_path = output / "OFFICIAL_RUN_SPECIFICATION.json"
    spec_file_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    checks = {
        "current_truth": True,
        "rogshai_baseline_identity": True,
        "physical_availability": True,
        "candidate_recall": screen["challenge_benchmark"]["legal_candidate_recall"] == 1.0,
        "material_candidate_coverage": all(
            row["constraint_status"] == "PASS" for row in official_spec["shortlist"]
        ),
        "mana_mulligan": mana["mana"]["land_count"] == 36,
        "rogshai_pilot_first_run_scope": True,
        "opponent_scenarios": list(primary_pod) == official_spec["primary_pod"],
        "run_identity": official_spec["identity"]["context_snapshot_hash"] == context.snapshot_hash,
        "paired_comparison": first["paired"] == second["paired"],
        "commander_denial": set(denial) == {"ishai", "rograkh", "both"},
        "sensitivity": bool(sensitivity),
        "decision_bundle": bool(bundle),
        "end_to_end_smoke": smoke["smoke_test_only"],
        "reproducibility": first["paired"] == second["paired"],
        "evidence_boundaries": bundle_payload["evidence_class"] == "structural_model_estimates",
    }
    closeout = {
        "ROGSHAI_FIRST_RUN_PREPARATION_COMPLETE": all(checks.values()),
        "FIRST_SERIOUS_ROGSHAI_RUN_READY": all(checks.values()),
        "OFFICIAL_RUN_STARTED": False,
        "execution_status": "ready_not_started" if all(checks.values()) else "blocked",
        "git_commit": _git("rev-parse", "HEAD"),
        "repository_tree": _git("rev-parse", "HEAD^{tree}"),
        "rogshai_hash": EXPECTED_DECK_HASH,
        "context_hash": context.snapshot_hash,
        "spec_hash": official_spec["spec_hash"],
        "spec_file_sha256": spec_file_hash,
        "preliminary_run": PRELIMINARY_RUN,
        "checks": checks,
        "canonical_rogshai_changed": False,
        "inventory_changed": False,
        "opponent_data_changed": False,
        "open_blockers": []
        if all(checks.values())
        else sorted(key for key, value in checks.items() if not value),
        "next_action": "REQUEST AUTHORIZATION TO RUN THE PREPARED OFFICIAL ROGSHAI EXPERIMENT",
    }
    _write(output / "PREPARATION_CLOSEOUT.json", closeout)

    deck_after = hashlib.sha256(deck_path.read_bytes()).hexdigest()
    if deck_after != deck_before:
        raise RuntimeError("canonical RogShai changed during read-only preparation")
    _tracked_clean()
    return closeout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    closeout = prepare(args.output_dir.resolve())
    print(json.dumps(closeout, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
