from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from commander_lab.evals import load_golden_cases, run_golden_cases

ROOT = Path(__file__).resolve().parents[1]
DEV_PATH = ROOT / "data/evals/golden/pilot_decisions_j_p4_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    cases = load_golden_cases(DEV_PATH)
    results = run_golden_cases(cases, source=str(DEV_PATH.relative_to(ROOT)))
    by_strategy: dict[str, list[tuple[object, object]]] = defaultdict(list)
    for case, result in zip(cases, results, strict=True):
        by_strategy[case.strategy].append((case, result))
    strategies: dict[str, object] = {}
    for strategy, rows in sorted(by_strategy.items()):
        rs = [row[1] for row in rows]
        strategies[strategy] = {
            "cases": len(rs),
            "passed": sum(result.passed for result in rs),
            "pass_rate": sum(result.passed for result in rs) / len(rs),
            "mean_action_class_score": sum(result.score for result in rs) / len(rs),
            "preferred": sum(
                isinstance(result.observed, dict)
                and result.observed.get("outcome_class") == "preferred"
                for result in rs
            ),
            "acceptable": sum(
                isinstance(result.observed, dict)
                and result.observed.get("outcome_class") == "acceptable"
                for result in rs
            ),
            "bad": sum(
                isinstance(result.observed, dict) and result.observed.get("outcome_class") == "bad"
                for result in rs
            ),
            "critical_failures": sum(
                isinstance(result.observed, dict)
                and result.observed.get("outcome_class") == "critical_failure"
                for result in rs
            ),
        }
    payload = {
        "schema_version": "1.0.0",
        "phase": "J-P4",
        "evaluated_at_utc": datetime.now(UTC).isoformat(),
        "estimate_type": "structural_model_estimates",
        "corpus": str(DEV_PATH.relative_to(ROOT)),
        "corpus_sha256": sha256(DEV_PATH),
        "holdout_loaded": False,
        "case_count": len(results),
        "passed": sum(result.passed for result in results),
        "pass_rate": sum(result.passed for result in results) / len(results),
        "mean_action_class_score": sum(result.score for result in results) / len(results),
        "strategies": strategies,
        "results": [result.model_dump(mode="json") for result in results],
        "truth_boundary": "Modeled structural pilot decision quality; not empirical human skill or win rate.",
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
