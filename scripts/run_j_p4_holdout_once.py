from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from commander_lab.evals import load_golden_cases, run_golden_cases

ROOT = Path(__file__).resolve().parents[1]
SEAL_PATH = ROOT / "docs/J_P4_HOLDOUT_SEAL.json"
DEFAULT_RESULT = ROOT / "docs/J_P4_HOLDOUT_FIRST_EVALUATION.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    holdout = ROOT / seal["holdout_path"]
    actual_hash = sha256(holdout)
    if actual_hash != seal["sha256"]:
        raise SystemExit(
            f"FAIL-CLOSED: holdout hash mismatch: expected {seal['sha256']} got {actual_hash}"
        )
    if args.output.exists():
        if not args.verify_existing:
            raise SystemExit(
                "FAIL-CLOSED: first holdout result already exists; J-P4 forbids a second evaluation"
            )
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        if payload.get("holdout_sha256") != actual_hash:
            raise SystemExit("FAIL-CLOSED: existing result does not bind the sealed holdout hash")
        print(json.dumps({"verified_existing": True, "holdout_sha256": actual_hash}, indent=2))
        return 0

    cases = load_golden_cases(holdout)
    results = run_golden_cases(cases, source=str(holdout.relative_to(ROOT)))
    pilot_source = ROOT / "src/commander_lab/agents/pilots.py"
    model_source = ROOT / "src/commander_lab/models/pilots.py"
    eval_source = ROOT / "src/commander_lab/evals/golden.py"
    payload = {
        "schema_version": "1.0.0",
        "phase": "J-P4",
        "evaluation_ordinal": 1,
        "first_and_only_intended_evaluation": True,
        "evaluated_at_utc": datetime.now(UTC).isoformat(),
        "estimate_type": "structural_model_estimates",
        "holdout_id": seal["holdout_id"],
        "holdout_sha256": actual_hash,
        "holdout_case_count": len(results),
        "development_complete_before_evaluation": True,
        "post_holdout_pilot_tuning_permitted": False,
        "code_identity": {
            "pilots_py_sha256": sha256(pilot_source),
            "pilot_models_py_sha256": sha256(model_source),
            "golden_evaluator_py_sha256": sha256(eval_source),
        },
        "passed": sum(result.passed for result in results),
        "pass_rate": sum(result.passed for result in results) / len(results),
        "mean_action_class_score": sum(result.score for result in results) / len(results),
        "critical_failures": sum(
            isinstance(result.observed, dict)
            and result.observed.get("outcome_class") == "critical_failure"
            for result in results
        ),
        "bad_actions": sum(
            isinstance(result.observed, dict) and result.observed.get("outcome_class") == "bad"
            for result in results
        ),
        "results": [result.model_dump(mode="json") for result in results],
        "truth_boundary": "Modeled structural pilot decision quality; not empirical human skill or win rate.",
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "holdout_first_evaluation": True,
                "cases": len(results),
                "passed": payload["passed"],
                "pass_rate": payload["pass_rate"],
                "mean_action_class_score": payload["mean_action_class_score"],
                "critical_failures": payload["critical_failures"],
                "bad_actions": payload["bad_actions"],
            },
            indent=2,
        )
    )
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
