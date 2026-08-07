from pathlib import Path

from commander_lab.models import (
    CompareVariantSensitivityInput,
    EvaluateRobustUpgradeInput,
    GenerateEnsembleReportInput,
    RunEnsembleMatchupsInput,
    ToolStatus,
    ValidateEnsembleInput,
)
from commander_lab.tools import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_opponent_ensemble_toolchain_reports_structural_uncertainty() -> None:
    service = CommanderToolService(ROOT)
    ensemble_id = "cosmic-spiderman-ensemble-v1"

    validation = service.validate_ensemble(ValidateEnsembleInput(ensemble_id=ensemble_id))
    assert validation.status == ToolStatus.COMPLETED
    assert validation.result["valid"] is True
    assert validation.result["automatic_profile_overwrite"] is False

    matchup = service.run_ensemble_matchups(
        RunEnsembleMatchupsInput(
            deck_id="rogshai/current",
            ensemble_id=ensemble_id,
            seed=20260806,
        )
    )
    assert matchup.status == ToolStatus.COMPLETED
    assert matchup.result["estimate_type"] == "structural_model_estimates"
    assert len(matchup.result["per_variant"]) == 4
    assert all("synthetic" in row for row in matchup.result["per_variant"])
    assert all(
        "known_cards" in row and "assumed_cards" in row
        for row in matchup.result["per_variant"]
    )

    sensitivity = service.compare_variant_sensitivity(
        CompareVariantSensitivityInput(
            deck_id="rogshai/current",
            ensemble_id=ensemble_id,
            seed=20260806,
        )
    )
    assert sensitivity.status == ToolStatus.COMPLETED
    assert sensitivity.result["most_sensitive_assumption"]

    robust = service.evaluate_robust_upgrade(
        EvaluateRobustUpgradeInput(
            baseline_deck_id="rogshai/current",
            candidate_deck_id="rogshai/current",
            ensemble_id=ensemble_id,
            seed=20260806,
        )
    )
    assert robust.status == ToolStatus.COMPLETED
    assert robust.result["automatic_deck_application"] is False
    assert robust.result["robust"] is False

    report_path: Path | None = None
    try:
        report = service.generate_ensemble_report(
            GenerateEnsembleReportInput(
                ensemble_id=ensemble_id,
                output_name="test-cosmic-ensemble-report.md",
            )
        )
        assert report.status == ToolStatus.COMPLETED
        report_path = ROOT / report.result["report_path"]
        text = report_path.read_text(encoding="utf-8")
        assert "Known cards and synthetic assumptions are stored separately" in text
        assert "Win axes:" in text
    finally:
        if report_path is not None:
            report_path.unlink(missing_ok=True)
