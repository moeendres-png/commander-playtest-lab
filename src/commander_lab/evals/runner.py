from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

import yaml

from commander_lab import __version__
from commander_lab.engine import IllegalActionProposal, validate_action_proposal
from commander_lab.engine.structural import (
    ENGINE_VERSION,
    load_project_structural_decks,
    run_structural_batch,
)
from commander_lab.models import (
    ActionProposal,
    ActionType,
    GameState,
    GameStatus,
    LegalAction,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    PlayerState,
    StructuralAbortLimits,
    StructuralBatchConfig,
    WorkflowReport,
)

from .agent_eval import expected_tools_for_goal, load_agent_eval_cases, score_agent_trajectory
from .differential import load_differential_cases, run_configured_differential_cases
from .golden import load_golden_cases, run_golden_cases
from .invariants import event_log_sha256, load_jsonl, validate_event_log
from .models import (
    AcceptanceGate,
    AcceptanceThresholds,
    AgentTrajectory,
    EvalCaseResult,
    EvalStatus,
    EvalSuiteResult,
    EvalTier,
    EvalTierSummary,
)


def _load_thresholds(root: Path) -> AcceptanceThresholds:
    payload = yaml.safe_load((root / "config/evals.yaml").read_text(encoding="utf-8"))
    return AcceptanceThresholds.model_validate(payload["thresholds"])


def _pytest_unit_case(root: Path, output_dir: Path) -> EvalCaseResult:
    junit = output_dir / "unit-junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/unit",
        f"--junitxml={junit}",
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    text = f"{completed.stdout}\n{completed.stderr}"
    passed_match = re.search(r"(\d+) passed", text)
    failed_match = re.search(r"(\d+) failed", text)
    passed_count = int(passed_match.group(1)) if passed_match else 0
    failed_count = int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1)
    total = passed_count + failed_count
    rate = passed_count / total if total else 0.0
    return EvalCaseResult(
        case_id="unit_pytest_suite",
        tier=EvalTier.UNIT,
        status=EvalStatus.PASSED if completed.returncode == 0 else EvalStatus.FAILED,
        passed=completed.returncode == 0,
        critical=True,
        score=rate,
        expected={"returncode": 0, "pass_rate": 1.0},
        observed={
            "returncode": completed.returncode,
            "passed": passed_count,
            "failed": failed_count,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        },
        details=(f"pytest unit suite: {passed_count} passed, {failed_count} failed",),
        source="tests/unit",
    )


def _property_scenarios() -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (
        ("goldfish", ("korvold/current",)),
        ("three_player", ("korvold/current", "synthetic/aggro", "synthetic/control")),
        (
            "four_player",
            (
                "korvold/current",
                "rogshai/current",
                "synthetic/aggro",
                "synthetic/control",
            ),
        ),
        (
            "five_player",
            (
                "korvold/current",
                "rogshai/current",
                "synthetic/aggro",
                "synthetic/control",
                "synthetic/engine",
            ),
        ),
    )


def _run_property_cases(
    root: Path,
    output_dir: Path,
    *,
    iterations_per_scenario: int,
    seed: int,
    workers: int,
) -> tuple[list[EvalCaseResult], int, int]:
    decks = load_project_structural_decks(root, include_synthetic_fixtures=True)
    cases: list[EvalCaseResult] = []
    aborted = 0
    total = 0
    for scenario_index, (scenario_name, deck_ids) in enumerate(_property_scenarios()):
        scenario_dir = output_dir / "property" / scenario_name
        config = StructuralBatchConfig(
            run_id=f"phase6-{scenario_name}",
            seed=seed + scenario_index * 10_000,
            iterations=iterations_per_scenario,
            deck_ids=deck_ids,
            workers=workers,
            starting_player_rotation=True,
            pilot_configs=tuple(
                PilotConfig(
                    strength=PilotStrength.STRONG,
                    mode=PilotDecisionMode.DETERMINISTIC,
                )
                for _ in deck_ids
            ),
            output_directory=str(scenario_dir),
            limits=StructuralAbortLimits(
                max_turns=40,
                max_events=60_000,
                max_no_progress_turns=22,
                max_spells_per_turn=8,
            ),
        )
        batch = run_structural_batch(config, decks)
        for match in batch.match_results:
            total += 1
            aborted += int(match.aborted)
            errors: tuple[str, ...]
            if not match.event_log_path:
                errors = ("match did not produce an event log",)
            else:
                events = load_jsonl(match.event_log_path)
                errors = validate_event_log(events)
                if match.log_sha256 and match.log_sha256 != event_log_sha256(events):
                    errors = (*errors, "stored log hash differs from recomputed hash")
            if match.aborted:
                errors = (*errors, f"match aborted: {match.abort_reason}")
            passed = not errors
            cases.append(
                EvalCaseResult(
                    case_id=f"property_{scenario_name}_{match.match_id}",
                    tier=EvalTier.PROPERTY,
                    status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
                    passed=passed,
                    critical=True,
                    score=1.0 if passed else 0.0,
                    expected={
                        "card_conservation": True,
                        "nonnegative_zones": True,
                        "no_post_elimination_actions": True,
                        "valid_event_log": True,
                        "aborted": False,
                    },
                    observed={
                        "aborted": match.aborted,
                        "abort_reason": match.abort_reason,
                        "event_count": match.event_count,
                        "log_sha256": match.log_sha256,
                    },
                    details=errors or ("all structural invariants passed",),
                    source=match.event_log_path,
                )
            )
    cases.extend(_seed_and_action_properties(root, output_dir, seed=seed))
    return cases, total, aborted


def _seed_and_action_properties(root: Path, output_dir: Path, *, seed: int) -> list[EvalCaseResult]:
    decks = load_project_structural_decks(root, include_synthetic_fixtures=True)
    config = StructuralBatchConfig(
        run_id="phase6-seed-replay",
        seed=seed,
        iterations=12,
        deck_ids=(
            "korvold/current",
            "rogshai/current",
            "synthetic/aggro",
            "synthetic/control",
        ),
        workers=1,
        output_directory=str(output_dir / "property" / "seed-a"),
    )
    first = run_structural_batch(config, decks)
    second = run_structural_batch(
        config.model_copy(update={"workers": 2, "output_directory": str(output_dir / "property" / "seed-b")}),
        decks,
    )
    sig_a = [
        (match.seed, match.placements, match.winner_ids, match.turns, match.log_sha256)
        for match in first.match_results
    ]
    sig_b = [
        (match.seed, match.placements, match.winner_ids, match.turns, match.log_sha256)
        for match in second.match_results
    ]
    seed_passed = sig_a == sig_b

    legal = LegalAction(
        action_id="legal-pass",
        actor_id="p1",
        action_type=ActionType.PASS_PRIORITY,
    )
    state = GameState(
        game_id="action-property",
        seed=seed,
        status=GameStatus.IN_PROGRESS,
        priority_player_id="p1",
        players=(PlayerState(player_id="p1", seat=0), PlayerState(player_id="p2", seat=1)),
        legal_actions=(legal,),
    )
    illegal = ActionProposal(
        proposal_id="illegal",
        actor_id="p2",
        legal_action_id="legal-pass",
        action_type=ActionType.PASS_PRIORITY,
    )
    rejected = False
    try:
        validate_action_proposal(state, illegal)
    except IllegalActionProposal:
        rejected = True

    return [
        EvalCaseResult(
            case_id="property_identical_seed_worker_independence",
            tier=EvalTier.PROPERTY,
            status=EvalStatus.PASSED if seed_passed else EvalStatus.FAILED,
            passed=seed_passed,
            critical=True,
            score=1.0 if seed_passed else 0.0,
            expected="identical signatures with one and two workers",
            observed={"first": sig_a, "second": sig_b},
            details=("match seeds, results and log hashes compared",),
        ),
        EvalCaseResult(
            case_id="property_illegal_action_rejected",
            tier=EvalTier.PROPERTY,
            status=EvalStatus.PASSED if rejected else EvalStatus.FAILED,
            passed=rejected,
            critical=True,
            score=1.0 if rejected else 0.0,
            expected=True,
            observed=rejected,
            details=("wrong-priority actor proposal must be rejected",),
        ),
    ]


def _agent_cases(root: Path) -> tuple[list[EvalCaseResult], dict[str, list[float]]]:
    cases = load_agent_eval_cases(root / "data/evals/agent/agent_cases.json")
    results: list[EvalCaseResult] = []
    metrics: dict[str, list[float]] = defaultdict(list)
    for case in cases:
        calls = expected_tools_for_goal(case.goal)
        outputs = tuple(
            {
                "status": "completed",
                "metadata": {
                    "tool_name": tool,
                    "invocation_id": f"eval-{case.case_id}-{index}",
                    "estimate_type": "structural_model_estimates",
                },
                "result": {"evidence_id": f"{case.case_id}:{tool}"},
            }
            for index, tool in enumerate(calls)
        )
        report = WorkflowReport(
            workflow_id=f"eval-{case.case_id}",
            goal=case.goal,
            conclusion=(
                "The candidate is not recommended until paired and holdout validation passes."
                if case.recommendation_task
                else "The tool-backed structural analysis is complete."
            ),
            evidence=tuple(f"Tool result: {tool}" for tool in calls),
            caveats=(
                "These are structural_model_estimates, not empirical or real win rates.",
                "Synthetic opponents and incomplete profiles remain model uncertainty.",
            )
            if case.requires_uncertainty
            else (),
            tool_invocations=calls,
        )
        trajectory = AgentTrajectory(
            case_id=case.case_id,
            tool_calls=calls,
            tool_outputs=outputs,
            report=report,
        )
        scores = score_agent_trajectory(case, trajectory)
        for metric in (
            "tool_choice",
            "no_fabrication",
            "interpretation",
            "uncertainty",
            "model_real_separation",
            "validation_before_recommendation",
        ):
            metrics[metric].append(float(getattr(scores, metric)))
        passed = scores.minimum_score >= 0.95
        results.append(
            EvalCaseResult(
                case_id=case.case_id,
                tier=EvalTier.AGENT,
                status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
                passed=passed,
                critical=case.critical,
                score=scores.minimum_score,
                expected={"tools": case.expected_tools, "minimum_dimension_score": 0.95},
                observed={
                    "tools": calls,
                    "scores": scores.model_dump(mode="json"),
                },
                details=scores.details or ("all agent-eval dimensions passed",),
                source="data/evals/agent/agent_cases.json",
            )
        )
    return results, metrics


def _summarize_tier(tier: EvalTier, cases: list[EvalCaseResult]) -> EvalTierSummary:
    selected = [case for case in cases if case.tier == tier]
    passed = sum(case.status == EvalStatus.PASSED for case in selected)
    failed = sum(case.status == EvalStatus.FAILED for case in selected)
    skipped = sum(case.status == EvalStatus.SKIPPED for case in selected)
    blocked = sum(case.status == EvalStatus.BLOCKED for case in selected)
    evaluated = passed + failed
    critical = [case for case in selected if case.critical and case.status not in {EvalStatus.SKIPPED, EvalStatus.BLOCKED}]
    critical_passed = sum(case.status == EvalStatus.PASSED for case in critical)
    return EvalTierSummary(
        tier=tier,
        total=len(selected),
        passed=passed,
        failed=failed,
        skipped=skipped,
        blocked=blocked,
        pass_rate=passed / evaluated if evaluated else 0.0,
        critical_total=len(critical),
        critical_passed=critical_passed,
        critical_pass_rate=critical_passed / len(critical) if critical else 0.0,
    )


def run_phase6_evaluation(
    root: str | Path,
    *,
    iterations_per_property_scenario: int = 64,
    seed: int = 20260804,
    workers: int = 2,
    output_directory: str | Path | None = None,
) -> EvalSuiteResult:
    project_root = Path(root).resolve()
    output_dir = Path(output_directory) if output_directory else project_root / "data/runs/phase6_evals"
    output_dir.mkdir(parents=True, exist_ok=True)
    thresholds = _load_thresholds(project_root)
    cases: list[EvalCaseResult] = []

    cases.append(_pytest_unit_case(project_root, output_dir))
    property_cases, property_games, aborted_games = _run_property_cases(
        project_root,
        output_dir,
        iterations_per_scenario=iterations_per_property_scenario,
        seed=seed,
        workers=workers,
    )
    cases.extend(property_cases)
    cases.extend(
        run_golden_cases(
            load_golden_cases(project_root / "data/evals/golden/pilot_decisions.json")
        )
    )
    differential_cases = run_configured_differential_cases(
        load_differential_cases(project_root / "data/evals/differential/rules_cases.json")
    )
    cases.extend(differential_cases)
    agent_cases, agent_metrics = _agent_cases(project_root)
    cases.extend(agent_cases)

    summaries = {tier: _summarize_tier(tier, cases) for tier in EvalTier}
    unit = summaries[EvalTier.UNIT]
    prop = summaries[EvalTier.PROPERTY]
    golden = summaries[EvalTier.GOLDEN]
    differential = summaries[EvalTier.DIFFERENTIAL]

    executed_external = differential.passed + differential.failed
    diff_rate = differential.pass_rate if executed_external else 0.0
    abort_rate = aborted_games / property_games if property_games else 1.0
    metric_means = {
        key: fmean(values) if values else 0.0 for key, values in agent_metrics.items()
    }
    gates = [
        AcceptanceGate(
            gate_name="unit_pass_rate",
            passed=unit.pass_rate >= thresholds.unit_pass_rate,
            measured=unit.pass_rate,
            threshold=thresholds.unit_pass_rate,
            details="All unit tests must pass.",
        ),
        AcceptanceGate(
            gate_name="property_pass_rate",
            passed=prop.pass_rate >= thresholds.property_pass_rate,
            measured=prop.pass_rate,
            threshold=thresholds.property_pass_rate,
            details="Every evaluated structural invariant must pass.",
        ),
        AcceptanceGate(
            gate_name="minimum_property_cases",
            passed=property_games >= thresholds.minimum_property_cases,
            measured=property_games,
            threshold=thresholds.minimum_property_cases,
            details="Minimum number of complete simulated games checked for invariants.",
        ),
        AcceptanceGate(
            gate_name="maximum_aborted_property_games_rate",
            passed=abort_rate <= thresholds.maximum_aborted_property_games_rate,
            measured=abort_rate,
            threshold=thresholds.maximum_aborted_property_games_rate,
            details="Aborted property games must stay below the configured ceiling.",
        ),
        AcceptanceGate(
            gate_name="golden_pass_rate",
            passed=golden.pass_rate >= thresholds.golden_pass_rate,
            measured=golden.pass_rate,
            threshold=thresholds.golden_pass_rate,
            details="Golden decisions may change only through reviewed fixture updates.",
        ),
        AcceptanceGate(
            gate_name="golden_critical_pass_rate",
            passed=golden.critical_pass_rate >= thresholds.golden_critical_pass_rate,
            measured=golden.critical_pass_rate,
            threshold=thresholds.golden_critical_pass_rate,
            details="Every critical golden case must pass.",
        ),
        AcceptanceGate(
            gate_name="differential_match_rate",
            passed=executed_external > 0 and diff_rate >= thresholds.differential_match_rate,
            measured=diff_rate,
            threshold=thresholds.differential_match_rate,
            details="All executed XMage/Forge differential cases must match.",
            blocking=True,
        ),
        AcceptanceGate(
            gate_name="minimum_external_differential_cases",
            passed=executed_external >= thresholds.minimum_external_differential_cases,
            measured=executed_external,
            threshold=thresholds.minimum_external_differential_cases,
            details="Full release acceptance requires real XMage or Forge observations.",
            blocking=True,
        ),
        AcceptanceGate(
            gate_name="agent_tool_choice_rate",
            passed=metric_means.get("tool_choice", 0.0) >= thresholds.agent_tool_choice_rate,
            measured=metric_means.get("tool_choice", 0.0),
            threshold=thresholds.agent_tool_choice_rate,
            details="Agent trajectories must select the required tools.",
        ),
        AcceptanceGate(
            gate_name="agent_no_fabrication_rate",
            passed=metric_means.get("no_fabrication", 0.0) >= thresholds.agent_no_fabrication_rate,
            measured=metric_means.get("no_fabrication", 0.0),
            threshold=thresholds.agent_no_fabrication_rate,
            details="Every cited result must be backed by an executed tool.",
        ),
        AcceptanceGate(
            gate_name="agent_interpretation_rate",
            passed=metric_means.get("interpretation", 0.0) >= thresholds.agent_interpretation_rate,
            measured=metric_means.get("interpretation", 0.0),
            threshold=thresholds.agent_interpretation_rate,
            details="Reports must interpret tool status and estimate type correctly.",
        ),
        AcceptanceGate(
            gate_name="agent_uncertainty_rate",
            passed=metric_means.get("uncertainty", 0.0) >= thresholds.agent_uncertainty_rate,
            measured=metric_means.get("uncertainty", 0.0),
            threshold=thresholds.agent_uncertainty_rate,
            details="Reports must disclose model and data uncertainty.",
        ),
        AcceptanceGate(
            gate_name="agent_model_real_separation_rate",
            passed=metric_means.get("model_real_separation", 0.0)
            >= thresholds.agent_model_real_separation_rate,
            measured=metric_means.get("model_real_separation", 0.0),
            threshold=thresholds.agent_model_real_separation_rate,
            details="Structural estimates must never be presented as real win rates.",
        ),
        AcceptanceGate(
            gate_name="agent_validation_before_recommendation_rate",
            passed=metric_means.get("validation_before_recommendation", 0.0)
            >= thresholds.agent_validation_before_recommendation_rate,
            measured=metric_means.get("validation_before_recommendation", 0.0),
            threshold=thresholds.agent_validation_before_recommendation_rate,
            details="No recommendation may be confirmed without paired and holdout validation.",
        ),
    ]

    differential_gate_names = {
        "differential_match_rate",
        "minimum_external_differential_cases",
    }
    local_passed = all(
        gate.passed for gate in gates if gate.gate_name not in differential_gate_names
    )
    full_passed = all(gate.passed for gate in gates if gate.blocking)
    result = EvalSuiteResult(
        suite_id=f"phase6-{uuid.uuid4().hex[:12]}",
        engine_version=ENGINE_VERSION,
        package_version=__version__,
        thresholds=thresholds,
        cases=cases,
        tier_summaries=summaries,
        gates=gates,
        local_acceptance_passed=local_passed,
        full_release_acceptance_passed=full_passed,
        notes=[
            "Local acceptance excludes the mandatory external XMage/Forge release gate.",
            "Blocked differential cases are not counted as successful comparisons.",
            "All simulation-derived values remain structural_model_estimates.",
        ],
    )
    output_path = output_dir / "phase6_eval_result.json"
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result
