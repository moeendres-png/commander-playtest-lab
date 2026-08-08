#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def serialized(response):
    return response.model_dump(mode="json")


def main() -> int:
    from commander_lab.agents.demo import run_phase5_demo
    from commander_lab.engine.rules import run_phase8_validation
    from commander_lab.models import (
        CardAblationInput,
        CreateReportInput,
        HoldoutInput,
        MatchupBatchInput,
        PairedVariantInput,
        ValidateDeckInput,
        VariantSwap,
    )
    from commander_lab.storage.atomic import atomic_write_json
    from commander_lab.tools import CommanderToolService
    from commander_lab.tools.local_snapshots import build_local_snapshots

    output = ROOT / "artifacts" / "audit" / "acceptance"
    output.mkdir(parents=True, exist_ok=True)
    steps = []
    manifest = build_local_snapshots(ROOT)
    steps.append({"step": "local_snapshots", "status": "passed", "result": manifest})

    service = CommanderToolService(ROOT)
    for deck_id in ("korvold/current", "rogshai/current"):
        response = service.validate_deck(ValidateDeckInput(deck_id=deck_id))
        steps.append(
            {
                "step": f"validate_{deck_id}",
                "status": response.status.value,
                "result": serialized(response),
            }
        )

    matchup = service.run_matchup_batch(
        MatchupBatchInput(
            deck_ids=(
                "korvold/current",
                "synthetic/aggro",
                "synthetic/control",
                "synthetic/engine",
            ),
            iterations=4,
            workers=1,
            seed=20260805,
            max_turns=20,
        )
    )
    steps.append(
        {
            "step": "structural_matchup",
            "status": matchup.status.value,
            "result": serialized(matchup),
        }
    )

    tactical = run_phase8_validation(ROOT, output_directory=output / "tactical", seed=20260805)
    steps.append(
        {
            "step": "tactical_validation",
            "status": "passed" if tactical["local_acceptance_passed"] else "failed",
            "result": tactical,
        }
    )

    ablation = service.run_card_ablation(
        CardAblationInput(
            deck_id="korvold/current",
            card_name="Scouring Swarm",
            iterations=4,
            seed=20260805,
            max_turns=20,
        )
    )
    steps.append(
        {"step": "card_ablation", "status": ablation.status.value, "result": serialized(ablation)}
    )

    swap = VariantSwap(remove="Scouring Swarm", add_candidate_id="korvold/idol-of-oblivion")
    paired = service.compare_variants_paired(
        PairedVariantInput(
            deck_id="korvold/current", swaps=(swap,), iterations=4, seed=20260805, max_turns=20
        )
    )
    steps.append(
        {"step": "paired_comparison", "status": paired.status.value, "result": serialized(paired)}
    )

    holdout = service.run_holdout(
        HoldoutInput(
            deck_id="korvold/current", swaps=(swap,), iterations=4, seed=20260805, max_turns=20
        )
    )
    steps.append({"step": "holdout", "status": holdout.status.value, "result": serialized(holdout)})

    report = service.create_report(
        CreateReportInput(
            title="Phase 8.6 local acceptance",
            tool_responses=(
                serialized(matchup),
                serialized(ablation),
                serialized(paired),
                serialized(holdout),
            ),
            output_name="phase86_acceptance.md",
        )
    )
    steps.append({"step": "report", "status": report.status.value, "result": serialized(report)})

    demo = run_phase5_demo(ROOT, iterations=4, seed=20260805)
    steps.append({"step": "offline_agent_workflow", "status": "passed", "result": demo})

    guardrail_response = service.run_matchup_batch(
        MatchupBatchInput(
            deck_ids=(
                "korvold/current",
                "synthetic/aggro",
                "synthetic/control",
                "synthetic/engine",
            ),
            iterations=service.limits.approval_threshold_iterations + 1,
            seed=20260805,
        )
    )
    guardrail = "passed" if guardrail_response.status.value == "requires_approval" else "failed"
    steps.append({"step": "large_run_guardrail", "status": guardrail})

    result = {
        "schema_version": 1,
        "validation_level": "tactical_oracle_and_structural_only",
        "external_engine_used": False,
        "external_engine_validation_pending": True,
        "steps": steps,
        "passed": all(item["status"] in {"passed", "completed", "success"} for item in steps),
    }
    atomic_write_json(output / "phase86_acceptance.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
