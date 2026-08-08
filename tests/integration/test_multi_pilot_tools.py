from __future__ import annotations

from pathlib import Path

from commander_lab.models import (
    ComparePilotsInput,
    GeneratePilotRobustnessReportInput,
    ListPilotProfilesInput,
    RunPilotBenchmarkInput,
    RunPilotEnsembleInput,
    ToolStatus,
)
from commander_lab.models import (
    TestVariantAcrossPilotsInput as VariantAcrossPilotsInput,
)
from commander_lab.tools import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_pilot_toolchain_smoke_and_reproducibility() -> None:
    service = CommanderToolService(ROOT)
    listed = service.list_pilot_profiles(ListPilotProfilesInput(commander_family="korvold"))
    assert listed.status == ToolStatus.COMPLETED
    assert listed.result["count"] == 6

    request = RunPilotBenchmarkInput(
        deck_id="korvold/current",
        pilot_names=("KorvoldPilot", "KorvoldSacrificePilot"),
        iterations=1,
        seed=9123,
        max_turns=8,
        output_name="test-pilot-benchmark-a",
    )
    first = service.run_pilot_benchmark(request)
    second = service.run_pilot_benchmark(
        request.model_copy(update={"output_name": "test-pilot-benchmark-b"})
    )
    assert first.status == second.status == ToolStatus.COMPLETED
    assert first.result["results"] == second.result["results"]
    assert first.result["legal_actions_only"] is True
    assert first.result["omniscient_information_used"] is False

    compared = service.compare_pilots(
        ComparePilotsInput.model_validate(
            {**request.model_dump(), "output_name": "test-pilot-compare"}
        )
    )
    assert compared.status == ToolStatus.COMPLETED
    assert len(compared.result["pairwise"]) == 1


def test_ensemble_variant_and_report_tools_do_not_apply_deck_changes() -> None:
    service = CommanderToolService(ROOT)
    ensemble = service.run_pilot_ensemble(
        RunPilotEnsembleInput(
            deck_id="rogshai/current",
            ensemble_id="rogshai.equal.v1",
            iterations=1,
            seed=731,
            max_turns=8,
            output_name="test-rogshai-ensemble",
        )
    )
    assert ensemble.status == ToolStatus.COMPLETED
    assert ensemble.result["automatic_deck_changes"] is False
    assert "worst_pilot" in ensemble.result and "median_pilot" in ensemble.result

    variant = service.test_variant_across_pilots(
        VariantAcrossPilotsInput(
            baseline_deck_id="korvold/current",
            variant_deck_id="korvold/current",
            pilot_names=("KorvoldValuePilot", "KorvoldConservativePilot"),
            iterations=1,
            seed=93,
            max_turns=8,
            output_name="test-identical-variant-pilots",
        )
    )
    assert variant.status == ToolStatus.COMPLETED
    assert variant.result["automatic_deck_changes"] is False
    assert variant.result["median_placement_improvement"] == 0.0

    relative = Path(ensemble.result["result_path"]).relative_to(ROOT)
    report = service.generate_pilot_robustness_report(
        GeneratePilotRobustnessReportInput(
            result_path=str(relative),
            output_name="test-pilot-robustness.md",
        )
    )
    assert report.status == ToolStatus.COMPLETED
    text = Path(report.result["report_path"]).read_text(encoding="utf-8")
    assert "Structural Estimates" in text
    assert "No deck change" in text
