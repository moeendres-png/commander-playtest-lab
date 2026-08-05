from __future__ import annotations

from commander_lab.models import CalibrationReport, EvidenceSplit


def calibration_report_markdown(report: CalibrationReport) -> str:
    lines = [
        "# Real Playtest Calibration Report",
        "",
        f"- Calibration ID: `{report.calibration_id}`",
        f"- Dataset: `{report.dataset_id}`",
        f"- Dataset hash: `{report.dataset_hash}`",
        f"- Calibration policy: `{report.policy_version}` (`{report.policy_hash}`)",
        f"- Target deck versions: `{report.target_deck_versions}`",
        f"- Status: **{report.status.value}**",
        f"- Train games: {len(report.train_game_ids)}",
        f"- Validation games: {len(report.validation_game_ids)}",
        f"- Excluded games: {len(report.excluded_game_ids)}",
        f"- Confidence level: {report.confidence_level:.1%}",
        f"- Bootstrap samples: {report.bootstrap_samples}",
        f"- Structural run IDs: `{report.simulation_run_ids}`",
        f"- Structural master seeds: `{report.simulation_master_seeds}`",
        f"- Structural matches used: {report.simulated_matches_used}/{report.simulated_matches_total}",
        f"- Structural matches excluded: {report.simulated_matches_excluded}",
        "- Independent confirmation: **no**",
        "- Engine defaults modified: **no**",
        "- External engine validation pending: **yes**",
        "",
        "## Evidence separation",
        "",
        "Training games are used only to estimate candidate calibration factors. Validation games are",
        "a sealed internal holdout. They are not independent external confirmation and are never used",
        "to fit the accepted factors.",
        "",
        "## Real versus structural distributions",
        "",
        "| Deck | Metric | Split | Real n | Real mean | Sim n | Sim mean | Delta | Status |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in report.comparisons:
        real_mean = "—" if item.real.mean is None else f"{item.real.mean:.3f}"
        sim_mean = "—" if item.simulated.mean is None else f"{item.simulated.mean:.3f}"
        delta = (
            "—"
            if item.mean_delta_real_minus_simulated is None
            else f"{item.mean_delta_real_minus_simulated:+.3f}"
        )
        lines.append(
            f"| {item.deck_key} | {item.metric} | {item.split.value} | "
            f"{item.real.observations} | {real_mean} | {item.simulated.observations} | "
            f"{sim_mean} | {delta} | {item.comparison_status} |"
        )
    lines.extend(
        [
            "",
            "## Parameter decisions",
            "",
            "| Deck | Metric | Parameter | Decision | Proposed | Accepted | Validation improvement |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for item in report.parameter_results:
        proposed = "—" if item.proposed_value is None else f"{item.proposed_value:.4f}"
        accepted = "—" if item.accepted_value is None else f"{item.accepted_value:.4f}"
        improvement = (
            "—"
            if item.validation_improvement_fraction is None
            else f"{item.validation_improvement_fraction:.1%}"
        )
        lines.append(
            f"| {item.deck_key} | {item.metric} | {item.parameter_name} | "
            f"{item.decision.value} | {proposed} | {accepted} | {improvement} |"
        )
    lines.extend(["", "## Accepted calibration profile", ""])
    if report.accepted_parameters:
        for key, value in report.accepted_parameters.items():
            lines.append(f"- `{key}` = `{value:.6f}`")
    else:
        lines.append("No parameter met the evidence and internal-validation thresholds.")
    if report.version_conflicts:
        lines.extend(["", "## Deck-version conflicts", ""])
        for key, versions in report.version_conflicts.items():
            lines.append(f"- `{key}`: {', '.join(versions)}")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(["", "## Methodology", ""])
    lines.extend(f"- {item}" for item in report.methodology)
    lines.extend(
        [
            "",
            "## Validation labels",
            "",
            "Real playtests are empirical observations. Structural comparisons remain",
            "`structural_model_estimates`. Neither source is relabelled as `external_rules_engine`.",
            "",
        ]
    )
    return "\n".join(lines)
