from __future__ import annotations

from commander_lab.evals import EvalStatus, load_golden_cases, run_golden_cases


def _assert_corpus(repo_root, relative_path: str, expected_count: int, group: str) -> None:
    path = repo_root / relative_path
    cases = load_golden_cases(path)
    assert len(cases) == expected_count
    assert {case.scenario_group for case in cases} == {group}
    for case in cases:
        assert case.accepted_actions
        assert not (case.accepted_actions & frozenset(case.bad_action_ids))
        assert 1 <= case.seat <= case.state.pod_size
    results = run_golden_cases(cases, source=relative_path)
    assert all(result.status == EvalStatus.PASSED for result in results), [
        result.model_dump(mode="json") for result in results if not result.passed
    ]


def test_g_development_decision_corpus(repo_root) -> None:
    _assert_corpus(
        repo_root,
        "data/evals/golden/pilot_decisions_g.json",
        24,
        "development",
    )


def test_g_holdout_decision_corpus(repo_root) -> None:
    _assert_corpus(
        repo_root,
        "data/evals/holdout/pilot_decisions_g.json",
        12,
        "holdout",
    )


def test_g_corpora_cover_both_pilots_and_all_pod_sizes(repo_root) -> None:
    cases = (
        *load_golden_cases(repo_root / "data/evals/golden/pilot_decisions_g.json"),
        *load_golden_cases(repo_root / "data/evals/holdout/pilot_decisions_g.json"),
    )
    assert {case.strategy for case in cases} == {"korvold", "rogshai"}
    assert {case.state.pod_size for case in cases} >= {3, 4, 5}
    assert any("archenemy" in case.case_id for case in cases)
    assert any(case.stack_state_if_relevant for case in cases)
    assert any(case.uncertainty for case in cases)
