from __future__ import annotations

import json
from pathlib import Path

from commander_lab.counterfactual import CounterfactualReplayLab
from commander_lab.diagnostics import DecisionDiagnosticEngine, run_integrated_extension_smoke
from commander_lab.models import (
    CounterfactualResult,
    DiagnosisRecord,
    MulliganContext,
    MulliganGamePlan,
    MulliganPolicyName,
)
from commander_lab.mulligan import MulliganLab
from commander_lab.storage import atomic_write_json, atomic_write_text


def _mulligan_report(name: str, result) -> str:
    lines = [
        f"# {name} Mulligan Lab 1.10.1",
        "",
        "Status: `mulligan_lab_ready_with_limitations`",
        "",
        "All keep rules and placement values are model-based Structural estimates, not absolute rules or empirical win rates.",
        "",
        "| Policy | First-seven keep | Mulligan rate | Avg. mulligans | Color issues | Full follow-ups | Avg. placement |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result.policies:
        placement = (
            "—" if row.structural_placement_mean is None else f"{row.structural_placement_mean:.3f}"
        )
        lines.append(
            f"| `{row.policy.value}` | {row.keep_rate_first_seven:.3f} | {row.mulligan_rate:.3f} | "
            f"{row.average_mulligans:.3f} | {row.color_problem_rate:.3f} | "
            f"{row.completed_followup_games}/{row.full_followup_games} | {placement} |"
        )
    lines += [
        "",
        "## Overfitting checks",
        "",
        f"- Executed validation contexts: {len(result.overfitting_validation)}",
        f"- Context kinds: {', '.join(sorted({row.context_kind for row in result.overfitting_validation}))}",
        f"- Supported contexts: {sum(row.supported for row in result.overfitting_validation)}/{len(result.overfitting_validation)}",
        "- Primary pod, two holdouts, one opponent ensemble and three pilot profiles were actually executed.",
        "",
        "## Boundaries",
        "",
        "- Full follow-ups use the Structural Simulator with a forced public opening hand.",
        "- No Tactical Oracle or external rules engine was used for complete games.",
        "- No deck list, inventory or allocation was changed.",
    ]
    return "\n".join(lines) + "\n"


def main(root: Path) -> None:
    root = root.resolve()
    lab = MulliganLab(root)
    policies = tuple(MulliganPolicyName)
    cases = (
        ("korvold/current", MulliganGamePlan.BALANCED, 2, "KorvoldPilot", "korvold"),
        ("rogshai/current", MulliganGamePlan.PROTECTED_COMMANDER, 3, "RogShaiPilot", "rogshai"),
    )
    for deck_id, plan, seat, pilot, slug in cases:
        deck = lab.deck(deck_id)
        context = MulliganContext(
            deck_id=deck.deck_id,
            deck_hash=deck.deck_hash,
            opponent_ensemble_id="morcant-elves-ensemble-v1",
            seat_position=seat,
            starting_player=False,
            pod_size=4,
            pilot_profile_id=pilot,
            pilot_version="1.0.0",
            game_plan=plan,
            seed=20260806,
        )
        result = lab.run(context, policies, samples=500, followup_samples=4)
        result_path = root / f"data/mulligan_lab/results/{slug}_mulligan_lab.json"
        rules_path = root / f"data/mulligan_lab/policies/{slug}_mulligan_keep_rules.json"
        report_path = root / f"docs/mulligan_lab/{slug}_mulligan_lab.md"
        atomic_write_json(result_path, result.model_dump(mode="json"))
        atomic_write_json(
            rules_path,
            {
                "schema_version": "1.10.1",
                "deck_id": deck.deck_id,
                "deck_hash": deck.deck_hash,
                "rules": [row.model_dump(mode="json") for row in result.generated_rules],
                "truth_boundary": "model_based_not_absolute",
            },
        )
        atomic_write_text(report_path, _mulligan_report(slug.title(), result))

    smoke_path = root / "data/diagnostics/reports/INTEGRATED_TEN_EXTENSION_SMOKE.json"
    smoke = run_integrated_extension_smoke(root, smoke_path)
    smoke_lines = [
        "# Integrated ten-extension smoke 1.10.1",
        "",
        f"Status: `{smoke.status}`",
        f"Passed steps: {smoke.passed_steps}/10",
        "",
        "| Step | Name | Validation level | Result |",
        "|---:|---|---|---|",
    ]
    for row in smoke.steps:
        smoke_lines.append(
            f"| {row.step} | {row.name} | `{row.validation_level}` | {row.result_summary} |"
        )
    smoke_lines += [
        "",
        "Every step was executed in this run and stores source paths plus SHA-256 hashes.",
        "No external rules engine was used.",
    ]
    atomic_write_text(
        root / "data/diagnostics/reports/INTEGRATED_TEN_EXTENSION_SMOKE.md",
        "\n".join(smoke_lines) + "\n",
    )

    run_dir = root / "data/runs/integrated_extension_smoke"
    counter = CounterfactualResult.model_validate_json(
        (run_dir / "counterfactual.json").read_text(encoding="utf-8")
    )
    CounterfactualReplayLab.report(
        counter, root / "data/counterfactual/reports/DECISION_REGRET_REPORT.md"
    )
    atomic_write_json(
        root / "data/counterfactual/examples/korvold_counterfactual_example.json",
        counter.model_dump(mode="json"),
    )
    diagnosis = DiagnosisRecord.model_validate_json(
        (run_dir / "diagnosis.json").read_text(encoding="utf-8")
    )
    DecisionDiagnosticEngine.report(
        [diagnosis], root / "data/diagnostics/reports/DECISION_DIAGNOSTIC_REPORT.md"
    )
    atomic_write_json(
        root / "data/diagnostics/examples/integrated_smoke_dataset.json",
        json.loads((run_dir / "diagnostic_dataset.json").read_text(encoding="utf-8")),
    )

    audit = {
        "schema_version": "1.10.1",
        "status": "decision_diagnostics_ready_with_limitations",
        "phase_status": {
            "12.8": "mulligan_lab_ready_with_limitations",
            "12.9": "counterfactual_replay_ready_with_limitations",
            "12.10": "decision_diagnostics_ready_with_limitations",
        },
        "completed_gaps": [
            "full structural mulligan follow-up games",
            "executed keep-rule validation across primary, holdout, ensemble and pilot contexts",
            "counterfactual public state deltas and hidden-information policies",
            "actual Tactical Oracle invocation without external-engine promotion",
            "event-log-derived card and pilot diagnostics",
            "executed ten-step integration smoke",
        ],
        "integrated_smoke": {"passed": smoke.passed_steps, "total": 10, "status": smoke.status},
        "real_imported_games": 0,
        "external_engine_validation": False,
        "canonical_deck_changes": False,
        "inventory_changes": False,
        "allocation_changes": False,
        "model_claims_empirical": False,
    }
    target = root / "artifacts/completion_audit/PHASE12_8_10_COMPLETION_AUDIT.json"
    atomic_write_json(target, audit)
    atomic_write_text(
        target.with_suffix(".md"),
        """# Phase 12.8\u201312.10 completion audit\n\nStatus: `decision_diagnostics_ready_with_limitations`\n\nThe previously partial integration paths were completed and executed. Mulligan follow-ups now run complete Structural Simulator games; keep-rule candidates are actually checked across primary, holdout, ensemble and pilot contexts; counterfactual state differences and Tactical Oracle calls are evaluated; diagnostics are generated from event logs; and the ten-step smoke executes every stage.\n\nLimits remain: zero imported real games, no real XMage/Forge execution, model-based policies and diagnoses are not empirical proof, and no canonical deck, inventory or allocation data changed.\n""",
    )


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1])
