from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import (
    CardAblationInput,
    CommanderDenialInput,
    CreateReportInput,
    GenerateCandidateSwapsInput,
    HoldoutInput,
    InspectDeckInput,
    MatchupBatchInput,
    PackageAblationInput,
    PairedVariantInput,
    PilotStrength,
    RecommendUpgradesInput,
    SearchVariantsInput,
    SensitivityInput,
    ToolStatus,
    ValidateDeckInput,
    VariantSwap,
)
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = (
    "opponent/morcant-elves",
    "opponent/doom-prevails-precon",
    "opponent/cosmic-spiderman-midbudget",
)
POD = ("rogshai/current", *PRIMARY)


def _completed(name: str, response: object) -> dict[str, object]:
    status = getattr(response, "status", None)
    if status != ToolStatus.COMPLETED:
        errors = getattr(response, "errors", None)
        raise SystemExit(f"{name} did not complete: {status}; errors={errors}")
    payload = response.model_dump(mode="json")  # type: ignore[attr-defined]
    return {
        "name": name,
        "status": str(status),
        "run_identity_hash": payload.get("metadata", {}).get("run_identity_hash"),
        "tool_name": payload.get("metadata", {}).get("tool_name"),
    }


def main() -> None:
    service = CommanderToolService(ROOT)
    results: list[dict[str, object]] = []

    validate = service.validate_deck(ValidateDeckInput(deck_id="rogshai/current"))
    results.append(_completed("validate deck", validate))
    inspect = service.inspect_deck(InspectDeckInput(deck_id="rogshai/current", include_cards=False))
    results.append(_completed("inspect deck", inspect))

    discovery = service.generate_candidate_swaps(
        GenerateCandidateSwapsInput(deck_id="rogshai/current", max_candidates=1)
    )
    results.append(_completed("discover candidate swap", discovery))
    if discovery.result.get("count") != 1:
        raise SystemExit("candidate discovery did not return one simulation-ready physical swap")
    discovered = discovery.result.get("candidates", [])
    if not isinstance(discovered, list) or len(discovered) != 1:
        raise SystemExit("candidate discovery payload shape changed")
    candidate = discovered[0]
    if (
        not isinstance(candidate, dict)
        or candidate.get("recommendation_status") != "candidate_swap"
    ):
        raise SystemExit("candidate discovery no longer returns a non-applied candidate swap")
    if candidate.get("automatic_application") is not False:
        raise SystemExit("candidate discovery attempted automatic deck mutation")
    remove = str(candidate.get("remove") or "")
    candidate_id = str(candidate.get("candidate_id") or "")
    if not remove or not candidate_id:
        raise SystemExit("candidate discovery omitted the remove or candidate_id link")
    swap = VariantSwap(remove=remove, add_candidate_id=candidate_id)

    matchup = service.run_matchup_batch(
        MatchupBatchInput(deck_ids=POD, iterations=1, workers=1, seed=20260811)
    )
    results.append(_completed("run matchup", matchup))

    paired = service.compare_variants_paired(
        PairedVariantInput(
            deck_id="rogshai/current",
            swaps=(swap,),
            opponent_deck_ids=PRIMARY,
            iterations=1,
            workers=1,
            seed=20260812,
        )
    )
    results.append(_completed("compare variants", paired))

    card = service.run_card_ablation(
        CardAblationInput(
            deck_id="rogshai/current",
            card_name="Flare of Duplication",
            opponent_deck_ids=PRIMARY,
            iterations=1,
            workers=1,
            seed=20260813,
        )
    )
    results.append(_completed("ablate card", card))

    package = service.run_package_ablation(
        PackageAblationInput(
            deck_id="rogshai/current",
            card_names=("Flare of Duplication", "Farewell"),
            opponent_deck_ids=PRIMARY,
            iterations=1,
            workers=1,
            seed=20260814,
        )
    )
    results.append(_completed("ablate package", package))

    denial = service.run_commander_denial(
        CommanderDenialInput(
            deck_id="rogshai/current",
            opponent_deck_ids=PRIMARY,
            iterations=1,
            workers=1,
            seed=20260815,
        )
    )
    results.append(_completed("run commander denial", denial))

    # This is a generic out-of-sample robustness exercise over caller-supplied pods. The public
    # service method retains its historical run_holdout/HoldoutInput names for compatibility, but
    # this smoke never resolves or consumes the sealed Optimizer-v2 holdout partition.
    generic_oos = service.run_holdout(
        HoldoutInput(
            deck_id="rogshai/current",
            swaps=(swap,),
            opponent_deck_ids=PRIMARY,
            holdout_pods=(PRIMARY,),
            iterations=1,
            workers=1,
            seed=20260816,
        )
    )
    results.append(_completed("run generic out-of-sample robustness", generic_oos))

    sensitivity = service.run_sensitivity(
        SensitivityInput(
            deck_ids=POD,
            seeds=(20260817,),
            pilot_strengths=(PilotStrength.STRONG,),
            iterations=1,
            workers=1,
        )
    )
    results.append(_completed("run sensitivity", sensitivity))

    search = service.search_variants(
        SearchVariantsInput(
            deck_id="rogshai/current",
            candidate_ids=(candidate_id,),
            max_cuts=1,
            max_results=1,
            opponent_deck_ids=PRIMARY,
            iterations=1,
            workers=1,
            seed=20260818,
        )
    )
    results.append(_completed("search variants", search))

    recommend = service.recommend_upgrades(
        RecommendUpgradesInput(
            deck_id="rogshai/current",
            candidate_ids=(candidate_id,),
            max_recommendations=1,
        )
    )
    results.append(_completed("recommend upgrades", recommend))

    report_name = "j_p6_workflow_smoke_report.md"
    report = service.create_report(
        CreateReportInput(
            title="Decision-quality workflow smoke",
            tool_responses=(validate.model_dump(mode="json"), inspect.model_dump(mode="json")),
            output_name=report_name,
        )
    )
    results.append(_completed("create report", report))
    report_path = Path(str(report.result["report_path"]))
    if not report_path.is_file():
        raise SystemExit("report output missing")
    report_path.unlink()

    # Historical sealed-holdout evidence is read-only regression evidence here.
    p5 = json.loads((ROOT / "docs/J_P5_HOLDOUT_SEAL.json").read_text(encoding="utf-8"))
    if p5.get("evaluation_count") != 1 or p5.get("post_holdout_tuning_performed") is not False:
        raise SystemExit("P5 consumed holdout integrity changed")

    output = ROOT / "artifacts/j_p6/J_P6_WORKFLOW_SMOKE.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "1.3.0",
                "evidence_class": "workflow_runtime_smoke",
                "runtime_scope": "rogshai/current",
                "global_active_own_decks": ["korvold/current", "rogshai/current"],
                "unresolved_operational_baselines": ["korvold/current"],
                "canonical_deck_mutations": 0,
                "generic_out_of_sample_robustness_executed": True,
                "sealed_optimizer_holdout_executed": False,
                "confirmatory_partition_executed": False,
                "p5_holdout_regression_only": True,
                "workflows": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
