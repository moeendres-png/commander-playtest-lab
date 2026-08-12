from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.models import (
    CardAblationInput,
    CommanderDenialInput,
    HoldoutInput,
    InspectDeckInput,
    MatchupBatchInput,
    PackageAblationInput,
    RunMulliganLabInput,
    ToolResponse,
    ToolStatus,
    ValidateDeckInput,
    VariantSwap,
)
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
DECK_ID = "rogshai/current"
EXPECTED_DECK_HASH = "7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126"
PRIMARY_ROOT = 2026082102
SEED_ROOTS = {
    "mulligan": 2026082101,
    "baseline": PRIMARY_ROOT,
    "variants": 2026082103,
    "denial": 2026082104,
    "ablation": 2026082105,
    "sensitivity": 2026082106,
}
VARIANTS = (
    {
        "label": "rootborn_for_flare",
        "remove": "Flare of Duplication",
        "add_candidate_id": "inventory/rootborn-defenses-677fdbcf",
    },
    {
        "label": "opt_for_preordain",
        "remove": "Preordain",
        "add_candidate_id": "rogshai/opt-smoke",
    },
    {
        "label": "into_the_roil_for_prismari_charm",
        "remove": "Prismari Charm",
        "add_candidate_id": "rogshai/into-the-roil-smoke",
    },
)
CARD_ABLATIONS = ("Flare of Duplication", "Boros Charm", "Whirlwind of Thought")
PACKAGE_ABLATIONS = (
    "rogshai-protection-counter",
    "rogshai-independent-spellslinger",
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def _response(response: ToolResponse, label: str) -> dict[str, Any]:
    if response.status != ToolStatus.COMPLETED:
        raise RuntimeError(f"{label} failed: {response.errors or response.warnings}")
    return response.model_dump(mode="json")


def _child_seed(root: int, label: str) -> int:
    digest = hashlib.sha256(f"{root}|{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _holm_adjust(rows: list[dict[str, Any]]) -> None:
    indexed = sorted(
        enumerate(rows), key=lambda item: float(item[1]["paired_randomization_p_value"])
    )
    running = 0.0
    count = len(indexed)
    for rank, (original_index, row) in enumerate(indexed):
        adjusted = min(1.0, float(row["paired_randomization_p_value"]) * (count - rank))
        running = max(running, adjusted)
        rows[original_index]["holm_adjusted_p_value"] = running


def _seat_summary(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for pair in pairs:
        buckets[int(pair["starting_player_seat"])].append(
            float(pair["baseline_placement"]) - float(pair["variant_placement"])
        )
    return {
        str(seat): {
            "paired_games": len(values),
            "mean_placement_improvement": fmean(values),
            "worst_case": min(values),
        }
        for seat, values in sorted(buckets.items())
    }


def _baseline_seats(raw: dict[str, Any]) -> dict[str, Any]:
    buckets: dict[int, list[dict[str, float]]] = defaultdict(list)
    for index, match in enumerate(raw["match_results"]):
        metrics = match["player_metrics"]["p1"]
        buckets[index % 4].append(
            {
                "placement": float(metrics["placement"]),
                "win": float(metrics["placement"] == 1),
                "commander_damage": float(metrics["commander_damage_dealt"]),
                "ishai_peak_power": float(metrics["ishai_peak_power"]),
            }
        )
    return {
        str(seat): {
            "games": len(rows),
            "average_placement": fmean(row["placement"] for row in rows),
            "place_1_share": fmean(row["win"] for row in rows),
            "average_commander_damage": fmean(row["commander_damage"] for row in rows),
            "average_ishai_peak_power": fmean(row["ishai_peak_power"] for row in rows),
        }
        for seat, rows in sorted(buckets.items())
    }


def _comparison_row(label: str, result: dict[str, Any]) -> dict[str, Any]:
    paired = result["paired"]
    return {
        "label": label,
        "variant_identity": result["variant_identity"],
        "iterations": paired["actual_sample_size"],
        "placement_improvement": paired["placement_improvement"],
        "confidence_interval": paired["confidence_interval"],
        "distributionally_robust_lower_bound": paired["distributionally_robust_lower_bound"],
        "worst_case": paired["worst_case_result"],
        "lower_tail": paired["quantiles"],
        "paired_randomization_p_value": paired["paired_randomization_p_value"],
        "seat_stability": _seat_summary(result["paired_observations"]),
        "cache_provenance": result["cache_provenance"],
    }


def _meaningful_git_clean() -> None:
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError("tracked worktree must be clean before binding the serious run")


def run(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    _meaningful_git_clean()
    deck_path = ROOT / "data/decks/rogshai_current.json"
    deck_file_before = hashlib.sha256(deck_path.read_bytes()).hexdigest()
    commit = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    context = load_project_context(ROOT)
    if dict(context.active_deck_hashes) != {DECK_ID: EXPECTED_DECK_HASH}:
        raise RuntimeError("RogShai identity is not the approved unchanged control")
    if context.active_own_deck_ids != (DECK_ID,):
        raise RuntimeError("RogShai is not the sole active own deck")

    service = CommanderToolService(ROOT)
    facade = PriorityWorkflowFacade(ROOT)
    primary_pod = context.primary_opponent_deck_ids(DECK_ID)
    sensitivity_pods = (
        (
            "opponent/blight-curse-precon",
            "kaervek/current",
            "opponent/dance-elements-precon",
        ),
        (
            "opponent/wakanda-forever-precon",
            "opponent/lorehold-spirit-precon",
            "opponent/blight-curse-precon",
        ),
    )
    if not set(deck for pod in sensitivity_pods for deck in pod).issubset(
        set(context.holdout_deck_ids)
    ):
        raise RuntimeError("sensitivity composition escaped the canonical sensitivity pool")

    validation = _response(service.validate_deck(ValidateDeckInput(deck_id=DECK_ID)), "validation")
    inspection = _response(
        service.inspect_deck(InspectDeckInput(deck_id=DECK_ID, include_cards=False)),
        "inspection",
    )
    screen = facade.build_screen(DECK_ID, limit=795)
    mana = facade.mulligan_mana(DECK_ID)
    _write(output / "VALIDATION_REPORT.json", validation)
    _write(output / "STRUCTURAL_FAILURE_MODE_SNAPSHOT.json", inspection)
    _write(output / "CANDIDATE_COVERAGE.json", screen)

    mulligan_rows: list[dict[str, Any]] = []
    for seat in range(1, 5):
        mulligan_request = RunMulliganLabInput(
            deck_id=DECK_ID,
            policies=("current_pilot", "primer_policy"),
            samples=2500,
            followup_samples=16,
            seat_position=seat,
            starting_player=seat == 1,
            pod_size=4,
            pilot_profile_id="rogshai.current.baseline",
            pilot_version="current",
            game_plan="balanced",
            seed=_child_seed(SEED_ROOTS["mulligan"], f"seat-{seat}"),
            output_name=f"first_serious_run_mulligan_seat_{seat}.json",
        )
        mulligan_rows.append(
            _response(service.run_mulligan_lab(mulligan_request), f"mulligan seat {seat}")
        )
    mana_mulligan = {
        "mana": mana,
        "fresh_mulligan_results": mulligan_rows,
        "historical_saved_result_consumed": False,
        "comparison": "current_pilot versus canonical primer_policy",
        "uncertainty": "Wilson 95% half-widths emitted by MulliganLab",
    }
    _write(output / "MANA_MULLIGAN_REPORT.json", mana_mulligan)

    primary_request = MatchupBatchInput(
        deck_ids=(DECK_ID, *primary_pod),
        iterations=256,
        workers=2,
        seed=SEED_ROOTS["baseline"],
        max_turns=35,
    )
    primary_response = _response(service.run_matchup_batch(primary_request), "primary baseline")
    primary_raw_path = ROOT / primary_response["result"]["result_path"]
    primary_raw = json.loads(primary_raw_path.read_text(encoding="utf-8"))
    baseline_report = {
        "request": primary_request.model_dump(mode="json"),
        "tool_response": primary_response,
        "seat_results": _baseline_seats(primary_raw),
        "raw_result": primary_raw,
    }
    _write(output / "BASELINE_SEAT_RESULTS.json", baseline_report)

    sensitivity_baselines: list[dict[str, Any]] = []
    for index, pod in enumerate(sensitivity_pods, start=1):
        sensitivity_baseline_request = MatchupBatchInput(
            deck_ids=(DECK_ID, *pod),
            iterations=128,
            workers=2,
            seed=_child_seed(SEED_ROOTS["sensitivity"], f"baseline-pod-{index}"),
            max_turns=35,
        )
        response = _response(
            service.run_matchup_batch(sensitivity_baseline_request),
            f"sensitivity baseline {index}",
        )
        raw_path = ROOT / response["result"]["result_path"]
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        sensitivity_baselines.append(
            {
                "label": f"explicit_sensitivity_pod_{index}_no_frequency_weight",
                "pod": list(pod),
                "request": sensitivity_baseline_request.model_dump(mode="json"),
                "seat_results": _baseline_seats(raw),
                "aggregate": raw["aggregate"],
                "seeds": [row["seed"] for row in raw["match_results"]],
            }
        )
    _write(output / "SENSITIVITY_BASELINES.json", sensitivity_baselines)

    denial_rows: list[dict[str, Any]] = []
    ishai = "Ishai, Ojutai Dragonspeaker"
    rograkh = "Rograkh, Son of Rohgahh"
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
            iterations=32,
            workers=2,
            seed=_child_seed(SEED_ROOTS["denial"], label),
            max_turns=35,
        )
        denial_rows.append(
            {
                "label": label,
                **_response(service.run_commander_denial(denial_request), label),
            }
        )
    _write(output / "COMMANDER_DENIAL.json", denial_rows)

    variant_results: list[dict[str, Any]] = []
    variant_rows: list[dict[str, Any]] = []
    for spec in VARIANTS:
        iterations = 64
        result = facade.compare_validate(
            deck_id=DECK_ID,
            remove=spec["remove"],
            add_candidate_id=spec["add_candidate_id"],
            iterations=iterations,
            seed=_child_seed(SEED_ROOTS["variants"], spec["label"]),
            max_turns=35,
            workers=2,
        )
        if result.get("status") != "completed":
            raise RuntimeError(f"pre-registered variant failed constraints: {spec}: {result}")
        low, high = result["paired"]["confidence_interval"]
        if float(low) <= 0.0 <= float(high):
            iterations = 128
            result = facade.compare_validate(
                deck_id=DECK_ID,
                remove=spec["remove"],
                add_candidate_id=spec["add_candidate_id"],
                iterations=iterations,
                seed=_child_seed(SEED_ROOTS["variants"], spec["label"]),
                max_turns=35,
                workers=2,
            )
        variant_results.append(result)
        variant_rows.append(_comparison_row(spec["label"], result))
    _holm_adjust(variant_rows)
    for row in variant_rows:
        row["status"] = (
            "advance_for_sensitivity"
            if float(row["distributionally_robust_lower_bound"]) >= 0.0
            else "diagnose_not_recommend"
        )
    _write(
        output / "VARIANT_COMPARISONS.json",
        {
            "family_multiple_testing_method": "Holm",
            "comparisons": variant_rows,
            "raw_workflow_results": variant_results,
        },
    )

    card_rows: list[dict[str, Any]] = []
    for card in CARD_ABLATIONS:
        card_request = CardAblationInput(
            deck_id=DECK_ID,
            card_name=card,
            opponent_deck_ids=primary_pod,
            iterations=32,
            workers=2,
            seed=_child_seed(SEED_ROOTS["ablation"], f"card:{card}"),
            max_turns=35,
        )
        card_rows.append(
            _response(service.run_card_ablation(card_request), f"card ablation {card}")
        )
    _write(output / "CARD_ABLATIONS.json", card_rows)

    package_rows: list[dict[str, Any]] = []
    for package_id in PACKAGE_ABLATIONS:
        package_request = PackageAblationInput(
            deck_id=DECK_ID,
            package_id=package_id,
            opponent_deck_ids=primary_pod,
            iterations=32,
            workers=2,
            seed=_child_seed(SEED_ROOTS["ablation"], f"package:{package_id}"),
            max_turns=35,
        )
        package_rows.append(
            _response(
                service.run_package_ablation(package_request),
                f"package ablation {package_id}",
            )
        )
    _write(output / "PACKAGE_ABLATIONS.json", package_rows)

    ranked = sorted(
        zip(variant_rows, variant_results, strict=True),
        key=lambda pair: (
            float(pair[0]["distributionally_robust_lower_bound"]),
            float(pair[0]["placement_improvement"]),
        ),
        reverse=True,
    )[:2]
    sensitivity_rows: list[dict[str, Any]] = []
    for summary, result in ranked:
        variant = result["variant_identity"]
        sensitivity_request = HoldoutInput(
            deck_id=DECK_ID,
            swaps=(
                VariantSwap(
                    remove=variant["remove"],
                    add_candidate_id=variant["add_candidate_id"],
                ),
            ),
            holdout_pods=sensitivity_pods,
            iterations=32,
            workers=2,
            seed=_child_seed(SEED_ROOTS["sensitivity"], summary["label"]),
            max_turns=35,
        )
        sensitivity_rows.append(
            {
                "label": summary["label"],
                "interpretation": "explicit sensitivity only; no frequency or blind-holdout claim",
                **_response(
                    service.run_holdout(sensitivity_request),
                    f"sensitivity {summary['label']}",
                ),
            }
        )
    _write(output / "SENSITIVITY.json", sensitivity_rows)

    denial_for_bundle = {row["label"]: row["result"] for row in denial_rows}
    ablation_for_bundle = {
        "cards": [row["result"] for row in card_rows],
        "packages": [row["result"] for row in package_rows],
    }
    bundles: list[dict[str, Any]] = []
    sensitivity_by_label = {row["label"]: row["result"] for row in sensitivity_rows}
    for summary, comparison in ranked:
        status = (
            "prioritized_for_further_investigation"
            if summary["status"] == "advance_for_sensitivity"
            else "diagnostic_followup_only"
        )
        written = facade.create_decision_bundle(
            comparison,
            output / "decision_bundles" / summary["label"],
            worst_case_sensitivity_result=sensitivity_by_label.get(summary["label"], {}),
            commander_denial_result=denial_for_bundle,
            ablation_result=ablation_for_bundle,
            recommendation_status=status,
        )
        bundles.append({"label": summary["label"], **written})
    _write(output / "DECISION_BUNDLES.json", bundles)

    seed_evidence: dict[str, Any] = {
        "roots": SEED_ROOTS,
        "mulligan": [row["metadata"]["seed"] for row in mulligan_rows],
        "primary_baseline": [row["seed"] for row in primary_raw["match_results"]],
        "sensitivity_baselines": [row["seeds"] for row in sensitivity_baselines],
        "variants": [row["paired"]["seeds"] for row in variant_results],
        "denial": [row["result"]["comparison"]["seeds"] for row in denial_rows],
        "card_ablations": [row["result"]["ablation_comparison"]["seeds"] for row in card_rows],
        "package_ablations": [
            row["result"]["ablation_comparison"]["seeds"] for row in package_rows
        ],
        "sensitivity": [
            [holdout["comparison"]["seeds"] for holdout in row["result"]["holdouts"]]
            for row in sensitivity_rows
        ],
    }
    seed_set_hash = sha256_run_value(seed_evidence, root=ROOT)
    run_spec = {
        "schema_version": "1.0.0",
        "run_type": "first_serious_rogshai_structural_decision_baseline",
        "git_commit": commit,
        "git_tree": tree,
        "package_version": __version__,
        "engine_version": ENGINE_VERSION,
        "deck_id": DECK_ID,
        "deck_hash": EXPECTED_DECK_HASH,
        "project_context_hash": context.snapshot_hash,
        "seed_set_hash": seed_set_hash,
        "seed_evidence": seed_evidence,
        "primary_pod": list(primary_pod),
        "sensitivity_pods": [list(pod) for pod in sensitivity_pods],
        "sensitivity_frequency_weights": None,
        "workers": 2,
        "pilot_policy": "same current deterministic strong RogShai structural pilot for control and variants",
        "deck_mutation_allowed": False,
        "truth_boundary": "structural_model_estimates != empirical_winrates",
    }
    _write(output / "RUN_SPECIFICATION.json", run_spec)
    _write(
        output / "CONTEXT_SNAPSHOT.json",
        facade._context_payload(context) | {"root": str(context.root)},
    )
    _write(
        output / "CACHE_PROVENANCE.json",
        [result["cache_provenance"] for result in variant_results],
    )

    prioritized = [
        {
            "label": row["label"],
            "status": row["status"],
            "placement_improvement": row["placement_improvement"],
            "robust_lower_bound": row["distributionally_robust_lower_bound"],
            "holm_adjusted_p_value": row["holm_adjusted_p_value"],
        }
        for row in variant_rows
    ]
    report = [
        "# RogShai - First Serious Structural Decision Baseline",
        "",
        f"- Git commit: `{commit}`",
        f"- Package / engine: `{__version__}` / `{ENGINE_VERSION}`",
        f"- RogShai hash: `{EXPECTED_DECK_HASH}`",
        f"- Live context hash: `{context.snapshot_hash}`",
        f"- Seed-set hash: `{seed_set_hash}`",
        "- Control: unchanged 100 cards / 36 lands",
        "- Primary pod: High Perfect Morcant + Doom Prevails + Cosmic Spider-Man",
        "- Evidence boundary: structural model estimates, not empirical winrates",
        "",
        "## Prioritized follow-up investigations",
        "",
    ]
    report.extend(
        f"- {row['label']}: {row['status']}; mean placement delta "
        f"{row['placement_improvement']:.4f}; robust lower bound "
        f"{row['distributionally_robust_lower_bound']:.4f}; Holm p "
        f"{row['holm_adjusted_p_value']:.4f}"
        for row in variant_rows
    )
    report.extend(
        [
            "",
            "No card was changed automatically. Unmodeled cards remained discoverable and were "
            "not assigned a negative performance assumption.",
        ]
    )
    (output / "ROGSHAI_FIRST_SERIOUS_RUN_REPORT.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    _write(output / "PRIORITIZED_FOLLOWUP.json", prioritized)

    deck_file_after = hashlib.sha256(deck_path.read_bytes()).hexdigest()
    if deck_file_after != deck_file_before:
        raise RuntimeError("canonical RogShai deck file changed during a read-only experiment")
    _meaningful_git_clean()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
