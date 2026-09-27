from __future__ import annotations

from commander_lab.evals import EvalStatus, load_golden_cases, run_golden_cases


def test_all_phase6_golden_decisions(repo_root) -> None:
    cases = load_golden_cases(repo_root / "data/evals/golden/pilot_decisions.json")
    results = run_golden_cases(cases)
    assert len(results) >= 8
    assert all(result.status == EvalStatus.PASSED for result in results), [
        result.model_dump(mode="json") for result in results if not result.passed
    ]
    assert all(result.critical for result in results)
