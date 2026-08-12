from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from commander_lab import __version__
from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.models import CardAblationInput, CommanderDenialInput, SensitivityInput
from commander_lab.models.pilots import PilotStrength
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/j_final/J_FINAL_ACCEPTANCE_EVIDENCE.json"
OPPONENTS = (
    "opponent/morcant-elves",
    "opponent/doom-prevails-precon",
    "opponent/cosmic-spiderman-midbudget",
)


def response_summary(response: object) -> dict[str, object]:
    payload = response.model_dump(mode="json")  # type: ignore[attr-defined]
    return {
        "status": payload["status"],
        "estimate_type": payload["metadata"]["estimate_type"],
        "run_identity_hash": payload["metadata"]["run_identity_hash"],
        "result": payload["result"],
        "warnings": payload["warnings"],
        "errors": payload["errors"],
    }


def main() -> None:
    context = load_project_context(ROOT)
    service = CommanderToolService(ROOT)
    facade = PriorityWorkflowFacade(ROOT)
    screener = RogShaiCandidateScreener(ROOT, service=service)

    screen = screener.screen_pool()
    assert context.active_own_deck_ids == ("rogshai/current",)
    assert context.historical_own_deck_ids == ("korvold/current",)
    assert service.ACTIVE_OWN_DECK_IDS == ("rogshai/current",)
    assert screen["physical_legal_candidate_count"] == 795
    assert screen["discoverable_candidate_count"] == 795
    assert screen["candidate_recall"] == 1.0
    assert screen["excluded_candidate_count_by_reason"] == {}
    assert screen["structurally_unmodeled"] > 0

    build_screen = facade.build_screen("rogshai/current", limit=12)
    mana = facade.mulligan_mana("rogshai/current")
    assert build_screen["context"]["snapshot_hash"] == context.snapshot_hash
    assert mana["context"]["snapshot_hash"] == context.snapshot_hash

    challenge = screener.benchmark_challenge_set()
    challenge_rows: list[dict[str, object]] = []
    for row in challenge["evaluated"]:  # type: ignore[index]
        decision = row["decision"]
        if not decision["constraint_valid"]:
            challenge_rows.append(
                {
                    "class": row["class"],
                    "remove": row["remove"],
                    "add_candidate_id": row["add_candidate_id"],
                    "screen_decision": decision,
                    "status": "historical_variant_not_currently_legal",
                    "truth_boundary": "historical structural regression evidence only",
                }
            )
            continue
        comparison = facade.compare_validate(
            deck_id="rogshai/current",
            remove=str(row["remove"]),
            add_candidate_id=str(row["add_candidate_id"]),
            iterations=2,
            seed=20260811,
        )
        assert comparison["status"] == "completed"
        assert comparison["evidence_class"] == "structural_model_estimates"
        assert comparison["constraint_report"]["valid"] is True
        diagnosis = facade.diagnose_next_experiment(comparison)
        challenge_rows.append(
            {
                "class": row["class"],
                "remove": row["remove"],
                "add_candidate_id": row["add_candidate_id"],
                "screen_decision": decision,
                "paired": comparison["paired"],
                "mana_delta": comparison["mana_delta"],
                "playstyle_review_status": comparison["playstyle_review_status"],
                "diagnosis": diagnosis,
                "truth_boundary": comparison["truth_boundary"],
            }
        )

    representative = facade.compare_validate(
        deck_id="rogshai/current",
        remove="Kykar, Wind's Fury",
        add_candidate_id="inventory/disorder-in-the-court-f673274a",
        iterations=4,
        seed=20260811,
    )
    assert representative["status"] == "completed"
    bundle_dir = ROOT / "artifacts/j_final/decision_bundle"
    bundle = facade.create_decision_bundle(representative, bundle_dir)

    denial = service.run_commander_denial(
        CommanderDenialInput(
            deck_id="rogshai/current",
            opponent_deck_ids=OPPONENTS,
            iterations=2,
            seed=20260811,
        )
    )
    ablation = service.run_card_ablation(
        CardAblationInput(
            deck_id="rogshai/current",
            card_name="Kykar, Wind's Fury",
            opponent_deck_ids=OPPONENTS,
            iterations=2,
            seed=20260811,
        )
    )
    sensitivity = service.run_sensitivity(
        SensitivityInput(
            deck_ids=("rogshai/current", *OPPONENTS),
            seeds=(20260811,),
            pilot_strengths=(PilotStrength.STRONG,),
            iterations=2,
        )
    )
    for label, response in (
        ("commander_denial", denial),
        ("card_ablation", ablation),
        ("sensitivity", sensitivity),
    ):
        assert str(response.status) == "completed", (
            f"{label} failed: status={response.status}; errors={response.errors}; "
            f"warnings={response.warnings}"
        )
        assert response.metadata.estimate_type == "structural_model_estimates"

    context_payload = asdict(context)
    context_payload["root"] = str(context_payload["root"])
    evidence = {
        "schema_version": "1.1",
        "purpose": "J-FINAL historical acceptance against current RogShai structural/decision-support scope",
        "truth_boundaries": {
            "structural_model_estimates": "not empirical winrate",
            "tactical_oracle": "not external_rules_engine",
            "challenge": "historical structural regression evidence; current legality may differ",
            "historical_membership": "not a card-quality prior",
        },
        "software": {"package_version": __version__, "engine_version": ENGINE_VERSION},
        "context": context_payload,
        "candidate_universe": {
            key: screen[key]
            for key in (
                "physical_legal_candidate_count",
                "discoverable_candidate_count",
                "candidate_recall",
                "excluded_candidate_count_by_reason",
                "fully_high_confidence_modeled",
                "partially_modeled",
                "structurally_unmodeled",
                "canonical_feature_coverage",
                "heuristic_fallback_count",
                "unmodeled_candidate_discoverability",
                "fresh_rebuild_current_deck_neutrality",
                "historical_allocation_neutrality",
            )
        },
        "build_screen": build_screen,
        "mana_mulligan": mana,
        "challenge": {
            "summary": {
                key: challenge[key]
                for key in (
                    "challenge_set_id",
                    "rogshai_variant_count",
                    "legal_candidate_recall",
                    "known_good_candidate_recall",
                    "known_bad_candidate_rejection",
                    "evidence_boundary",
                )
            },
            "paired_rows": challenge_rows,
        },
        "representative_variant": {
            "comparison": representative,
            "decision_bundle": bundle,
        },
        "commander_denial": response_summary(denial),
        "card_ablation": response_summary(ablation),
        "sensitivity": response_summary(sensitivity),
        "holdout_governance": {
            "J_HOLDOUT_v1": "consumed_historical_P2_evidence_not_reused",
            "claim": "no retroactive blind-holdout claim in J-FINAL acceptance",
        },
        "final_gate": "PASS",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence["candidate_universe"], sort_keys=True))
    print(json.dumps(evidence["challenge"]["summary"], sort_keys=True))
    print(f"J_FINAL_ACCEPTANCE_EVIDENCE={OUT}")


if __name__ == "__main__":
    main()
