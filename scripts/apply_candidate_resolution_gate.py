from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from commander_lab.current_model_resolution import load_current_model_resolution
from commander_lab.decision_information import build_decision_information_state
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.storage.run_identity import sha256_run_value

ROOT = Path(__file__).resolve().parents[1]
TRIAGE_PATH = ROOT / "artifacts/candidate_evaluation/CURRENT_PAIRED_CANDIDATE_TRIAGE.json"


def _final_stage(row: dict[str, Any]) -> dict[str, Any]:
    stage_name = row.get("final_stage")
    raw = row.get("refined_stage") if stage_name == "refined" else row.get("initial_stage")
    if not isinstance(raw, dict):
        raise SystemExit("paired triage row has no final stage")
    return raw


def _comparison_from_stage(stage: dict[str, Any]) -> dict[str, Any]:
    constraint_report = stage.get("constraint_report")
    paired = stage.get("paired")
    precision_context = stage.get("precision_context")
    if not isinstance(constraint_report, dict) or not isinstance(paired, dict):
        raise SystemExit("paired triage final stage lost comparison evidence")
    return {
        "status": "completed",
        "constraint_report": constraint_report,
        "paired": paired,
        "precision_context": precision_context if isinstance(precision_context, dict) else {},
    }


def main() -> None:
    if not TRIAGE_PATH.is_file():
        raise SystemExit(f"paired triage artifact is missing: {TRIAGE_PATH}")
    payload = json.loads(TRIAGE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("paired triage artifact must be an object")
    rows = payload.get("results")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("paired triage artifact has no candidate results")

    resolution = load_current_model_resolution(ROOT)
    effective_resolution = resolution.get("effective_resolution")
    if isinstance(effective_resolution, bool) or not isinstance(effective_resolution, int | float):
        raise SystemExit("validated current model resolution has no numeric threshold")
    cohort_model = payload.get("cohort_model_informativeness")
    if not isinstance(cohort_model, dict):
        raise SystemExit("paired triage artifact has no cohort model diagnostic")

    facade = PriorityWorkflowFacade(ROOT)
    resolution_only_counts: Counter[str] = Counter()
    governed_counts: Counter[str] = Counter()
    advancement_counts: Counter[str] = Counter()
    materially_separated_count = 0
    finalist_count = 0

    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise SystemExit("paired triage result row is malformed")
        stage = _final_stage(raw_row)
        comparison = _comparison_from_stage(stage)

        resolution_only_state = build_decision_information_state(
            comparison,
            model_resolution=resolution,
        ).as_dict()
        governed_state = build_decision_information_state(
            comparison,
            model_resolution=resolution,
            model_informativeness=cohort_model,
        ).as_dict()
        advancement = facade.advancement_decision(
            comparison,
            model_informativeness=cohort_model,
            model_resolution=resolution,
        )

        resolution_only_status = str(resolution_only_state.get("status", "UNKNOWN"))
        governed_status = str(governed_state.get("status", "UNKNOWN"))
        advancement_status = str(advancement.get("status", "UNKNOWN"))
        resolution_only_counts[resolution_only_status] += 1
        governed_counts[governed_status] += 1
        advancement_counts[advancement_status] += 1

        materially_separated = resolution_only_status in {"STOP_WITH_PREFERENCE", "STOP"}
        if materially_separated:
            materially_separated_count += 1
        eligible = governed_status == "STOP_WITH_PREFERENCE" and advancement_status == "advance"
        if eligible:
            finalist_count += 1

        raw_row["validated_model_resolution"] = {
            "status": resolution.get("status"),
            "effective_resolution": float(effective_resolution),
            "freshness_validated": resolution.get("freshness_validated"),
            "freshness_inputs": resolution.get("freshness_inputs"),
            "measurement_artifact": resolution.get("measurement_artifact"),
            "decision_use": resolution.get("decision_use"),
            "evidence_class": resolution.get("evidence_class"),
        }
        raw_row["resolution_only_decision_information_state"] = resolution_only_state
        raw_row["governed_decision_information_state"] = governed_state
        raw_row["resolution_aware_advancement_decision"] = advancement
        raw_row["materially_separated_beyond_resolution"] = materially_separated
        raw_row["eligible_for_finalist_followup"] = eligible
        raw_row["final_recommendation"] = False

    payload["model_resolution_gate"] = {
        "status": resolution.get("status"),
        "effective_resolution": float(effective_resolution),
        "freshness_validated": resolution.get("freshness_validated"),
        "freshness_inputs": resolution.get("freshness_inputs"),
        "measurement_artifact": resolution.get("measurement_artifact"),
        "decision_use": resolution.get("decision_use"),
        "resolution_only_status_counts": dict(sorted(resolution_only_counts.items())),
        "governed_status_counts": dict(sorted(governed_counts.items())),
        "advancement_status_counts": dict(sorted(advancement_counts.items())),
        "materially_separated_candidate_count": materially_separated_count,
        "eligible_for_finalist_followup_count": finalist_count,
        "evidence_class": "structural_model_estimates",
        "truth_boundary": (
            "measured Structural decision-resolution gate only; it does not convert model output "
            "into empirical gameplay evidence or authorize a deck change"
        ),
    }
    payload["eligible_for_finalist_followup_count"] = finalist_count
    payload["final_recommendation"] = False
    payload["resolution_gate_applied"] = True
    payload["triage_hash_before_resolution_gate"] = payload.get("triage_hash")
    payload.pop("triage_hash", None)
    payload["triage_hash"] = sha256_run_value(payload, root=ROOT)

    TRIAGE_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"VALIDATED_EFFECTIVE_RESOLUTION={float(effective_resolution)}")
    print(
        "RESOLUTION_ONLY_STATUS_COUNTS=" + json.dumps(dict(sorted(resolution_only_counts.items())))
    )
    print("GOVERNED_STATUS_COUNTS=" + json.dumps(dict(sorted(governed_counts.items()))))
    print("ADVANCEMENT_STATUS_COUNTS=" + json.dumps(dict(sorted(advancement_counts.items()))))
    print(f"MATERIALLY_SEPARATED_CANDIDATES={materially_separated_count}")
    print(f"ELIGIBLE_FOR_FINALIST_FOLLOWUP={finalist_count}")
    print("MODEL_RESOLUTION_GATE=PASS")
    print("MODEL_RESOLUTION_BOUNDARY=structural_resolution_not_empirical_deck_power")


if __name__ == "__main__":
    main()
