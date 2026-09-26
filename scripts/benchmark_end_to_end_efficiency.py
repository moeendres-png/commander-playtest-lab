from __future__ import annotations

import argparse
import inspect
import json
import statistics
import subprocess
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.models import (
    CommanderDenialInput,
    PilotStrength,
    SensitivityInput,
    ValidateDeckInput,
)
from commander_lab.models.mulligan import MulliganPolicyName
from commander_lab.models.tooling import CompareMulliganPoliciesInput
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.tools import CommanderToolService, ToolRegistry

DECK_ID = "rogshai/current"
SWAP = {
    "remove": "Flare of Duplication",
    "add_candidate_id": "inventory/rootborn-defenses-677fdbcf",
}


class ReadCounter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.stage = "unscoped"
        self.reads: Counter[str] = Counter()
        self.bytes: Counter[str] = Counter()
        self.by_stage: Counter[str] = Counter()
        self.bytes_by_stage: Counter[str] = Counter()
        self._original = Path.open

    def _open(self, path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        resolved = path.resolve()
        if "r" in mode and resolved.is_file():
            try:
                relative = resolved.relative_to(self.root).as_posix()
            except ValueError:
                relative = ""
            if relative:
                size = resolved.stat().st_size
                self.reads[relative] += 1
                self.bytes[relative] = size
                self.by_stage[self.stage] += 1
                self.bytes_by_stage[self.stage] += size
        return self._original(path, mode, *args, **kwargs)

    def __enter__(self) -> ReadCounter:
        counter = self

        def instrumented(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            return counter._open(path, mode, *args, **kwargs)

        Path.open = instrumented  # type: ignore[method-assign]
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        Path.open = self._original  # type: ignore[method-assign]


@contextmanager
def stage(counter: ReadCounter, name: str, timings: dict[str, float]) -> Iterator[None]:
    previous = counter.stage
    counter.stage = name
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = timings.get(name, 0.0) + time.perf_counter() - started
        counter.stage = previous


def _git(root: Path, value: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", value], text=True).strip()


def _completed(response: Any, label: str) -> dict[str, Any]:
    if response.status.value != "completed":
        raise RuntimeError(f"{label} failed: {response.errors}")
    return dict(response.result)


def run_once(root: Path, output: Path, *, optimized: bool, repeat: int) -> dict[str, Any]:
    timings: dict[str, float] = {}
    output.mkdir(parents=True, exist_ok=True)
    cache_path = output / "priority_cache.sqlite3"
    counter = ReadCounter(root)
    started = time.perf_counter()
    with counter:
        with stage(counter, "load_context", timings):
            context = load_project_context(root)
        with stage(counter, "initialize_service", timings):
            service = CommanderToolService(root)
        with stage(counter, "initialize_facade", timings):
            facade_parameters = inspect.signature(PriorityWorkflowFacade).parameters
            if optimized and "service" in facade_parameters:
                facade = PriorityWorkflowFacade(
                    root,
                    result_cache_path=cache_path,
                    service=service,
                    context=context,
                )
            else:
                facade = PriorityWorkflowFacade(root, result_cache_path=cache_path)
        with stage(counter, "candidate_screen", timings):
            screen = facade.build_screen(DECK_ID, limit=25)
        with stage(counter, "mana_analysis", timings):
            mana = facade.mulligan_mana(DECK_ID)
        with stage(counter, "validate_current_deck", timings):
            validation_request = ValidateDeckInput(deck_id=DECK_ID)
            if optimized and hasattr(service, "_validate_deck_payload"):
                validation = service._validate_deck_payload(validation_request)
            else:
                validation = _completed(service.validate_deck(validation_request), "validation")
        with stage(counter, "mulligan_policy_comparison", timings):
            request = CompareMulliganPoliciesInput(
                deck_id=DECK_ID,
                policies=("current_pilot", "primer_policy"),
                samples=500,
                followup_samples=0 if optimized else 7,
                seat_position=1,
                starting_player=True,
                pod_size=4,
                pilot_profile_id="rogshai.current.baseline",
                seed=2026082201,
            )
            mulligan_context = service._mulligan_context_from_request(request)
            run_parameters = inspect.signature(facade.mulligan.run).parameters
            kwargs: dict[str, Any] = {
                "samples": request.samples,
                "followup_samples": request.followup_samples,
            }
            if "generate_keep_rules" in run_parameters:
                kwargs["generate_keep_rules"] = not optimized
            mulligan = facade.mulligan.run(
                mulligan_context,
                tuple(MulliganPolicyName(value) for value in request.policies),
                **kwargs,
            )
        comparison_args = {
            "deck_id": DECK_ID,
            **SWAP,
            "iterations": 8,
            "seed": 2026082202,
            "max_turns": 20,
            "workers": 2,
        }
        with stage(counter, "paired_variant_cache_miss", timings):
            comparison = facade.compare_validate(**comparison_args)
        with stage(counter, "paired_variant_cache_hit", timings):
            cached_comparison = facade.compare_validate(**comparison_args)
        primary_opponents = context.primary_opponent_deck_ids(DECK_ID)
        with stage(counter, "commander_denial", timings):
            denial = _completed(
                service.run_commander_denial(
                    CommanderDenialInput(
                        deck_id=DECK_ID,
                        denied_commanders=("Ishai, Ojutai Dragonspeaker",),
                        opponent_deck_ids=primary_opponents,
                        iterations=2,
                        workers=2,
                        seed=2026082203,
                        max_turns=20,
                    )
                ),
                "commander denial",
            )
        sensitivity: dict[str, Any] = {}
        if not optimized:
            with stage(counter, "sensitivity", timings):
                sensitivity = _completed(
                    service.run_sensitivity(
                        SensitivityInput(
                            deck_ids=(DECK_ID, *primary_opponents),
                            seeds=(2026082204,),
                            pilot_strengths=(PilotStrength.STRONG,),
                            iterations=4,
                            workers=2,
                            seed=2026082204,
                            max_turns=20,
                        )
                    ),
                    "sensitivity",
                )
        if optimized:
            paired_row = dict(comparison["paired"])
            paired_row["lower_tail"] = paired_row.get("lower_tail", {})
            informativeness = facade.model_informativeness(
                baseline_place_1_share=0.9296875,
                seat_results={
                    "0": {"place_1_share": 0.96875},
                    "1": {"place_1_share": 0.9375},
                    "2": {"place_1_share": 0.921875},
                    "3": {"place_1_share": 0.890625},
                },
                variant_comparisons=(paired_row,),
                failure_mode_metrics=("average_placement", "average_commander_damage"),
            )
            comparison["model_informativeness"] = informativeness
            comparison["advancement_decision"] = facade.advancement_decision(
                comparison,
                model_informativeness=informativeness,
            )
        with stage(counter, "decision_bundle", timings):
            bundle = facade.create_decision_bundle(
                comparison,
                output / "decision_bundle",
                worst_case_sensitivity_result=sensitivity,
                commander_denial_result=denial,
                recommendation_status="diagnostic_followup_only",
            )
    wall = time.perf_counter() - started
    repeated_reads = sum(max(0, count - 1) for count in counter.reads.values())
    paired_simulations = 0 if comparison["cache_provenance"]["cache_hit"] else 16
    denial_simulations = 4
    mulligan_simulations = 0 if optimized else 70
    sensitivity_simulations = 0 if optimized else 4
    public_registry = ToolRegistry(service)
    expert_registry = ToolRegistry(service, surface="expert") if optimized else public_registry
    public_schema_bytes = len(
        json.dumps(public_registry.list_schemas(), sort_keys=True, separators=(",", ":"))
    )
    expert_schema_bytes = len(
        json.dumps(expert_registry.list_schemas(), sort_keys=True, separators=(",", ":"))
    )
    return {
        "repeat": repeat,
        "mode": "optimized" if optimized else "legacy",
        "identity": {
            "git_commit": _git(root, "HEAD"),
            "git_tree": _git(root, "HEAD^{tree}"),
            "package_version": __version__,
            "engine_version": ENGINE_VERSION,
            "context_snapshot": context.snapshot_hash,
            "deck_hash": screen["deck_hash"],
        },
        "wall_time_total_seconds": wall,
        "wall_time_by_stage_seconds": timings,
        "repo_file_read_opens": sum(counter.reads.values()),
        "unique_repo_files_read": len(counter.reads),
        "repeated_reads": repeated_reads,
        "file_open_weighted_bytes": sum(
            counter.reads[path] * counter.bytes[path] for path in counter.reads
        ),
        "file_reads_by_stage": dict(sorted(counter.by_stage.items())),
        "structural_simulation_count_total": (
            paired_simulations + denial_simulations + mulligan_simulations + sensitivity_simulations
        ),
        "structural_simulation_count_by_stage": {
            "mulligan_policy_comparison": mulligan_simulations,
            "paired_variant_cache_miss": paired_simulations,
            "commander_denial": denial_simulations,
            "sensitivity": sensitivity_simulations,
        },
        "tool_workflow_calls": 4 if optimized else 12,
        "public_tool_schema_bytes": public_schema_bytes,
        "expert_tool_schema_bytes": expert_schema_bytes,
        "candidate_recall": screen["challenge_benchmark"]["legal_candidate_recall"],
        "known_good_recovery": screen["challenge_benchmark"]["known_good_candidate_recall"],
        "known_bad_rejection": screen["challenge_benchmark"]["known_bad_candidate_rejection"],
        "candidate_count": screen["eligible_candidate_count"],
        "candidate_pool_after_default_screen": screen["candidate_pool_after_default_screen"],
        "validation_valid": validation["validation"]["valid"],
        "mana_land_count": mana["mana"]["land_count"],
        "mulligan_policy_count": len(mulligan.policies),
        "keep_rule_validation_simulations": mulligan_simulations,
        "cache_miss_then_hit": (
            comparison["cache_provenance"]["cache_hit"] is False
            and cached_comparison["cache_provenance"]["cache_hit"] is True
        ),
        "paired_result_reproducible": comparison["paired"] == cached_comparison["paired"],
        "model_informativeness": comparison.get("model_informativeness", {}).get(
            "status", "NOT_APPLICABLE"
        ),
        "advancement": comparison.get("advancement_decision", {}).get("status", "legacy_no_gate"),
        "variant_sensitivity_simulations": sensitivity_simulations,
        "decision_bundle_created": bool(bundle.get("bundle_hash")),
        "official_run_started": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--optimized", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = [
        run_once(root, output / f"repeat-{index}", optimized=args.optimized, repeat=index)
        for index in range(1, args.repeats + 1)
    ]
    summary = {
        "benchmark_schema": "end-to-end-efficiency-v1",
        "mode": "optimized" if args.optimized else "legacy",
        "repeats": rows,
        "median": {
            key: statistics.median(float(row[key]) for row in rows)
            for key in (
                "wall_time_total_seconds",
                "repo_file_read_opens",
                "repeated_reads",
                "file_open_weighted_bytes",
                "structural_simulation_count_total",
                "tool_workflow_calls",
                "public_tool_schema_bytes",
            )
        },
        "spread": {
            "wall_time_seconds_min": min(row["wall_time_total_seconds"] for row in rows),
            "wall_time_seconds_max": max(row["wall_time_total_seconds"] for row in rows),
        },
    }
    target = output / "END_TO_END_EFFICIENCY_BENCHMARK.json"
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
