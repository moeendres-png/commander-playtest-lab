from __future__ import annotations

import hashlib
import json

from commander_lab.evals import load_golden_cases, run_golden_cases

REQUIRED_DIMENSIONS = {
    "survival",
    "mana_efficiency",
    "card_advantage",
    "tempo",
    "engine_development",
    "interaction_reserve",
    "commander_value",
    "threat_reduction",
    "win_progress",
    "political_visibility",
    "rebuild_capacity",
}


def test_j_p4_development_action_class_corpus(repo_root) -> None:
    path = repo_root / "data/evals/golden/pilot_decisions_j_p4_v1.json"
    cases = load_golden_cases(path)
    assert len(cases) == 37
    assert {case.strategy for case in cases} == {"korvold", "rogshai"}
    assert {case.state.pod_size for case in cases} >= {3, 4, 5}
    assert all(case.preferred_action_classes for case in cases)
    assert all(
        case.bad_action_classes or case.critical_failure_actions or case.acceptable_action_classes
        for case in cases
    )
    results = run_golden_cases(cases, source=str(path.relative_to(repo_root)))
    assert all(result.passed for result in results), [
        result.model_dump(mode="json") for result in results if not result.passed
    ]
    assert sum(result.score for result in results) / len(results) >= 0.98
    assert not any(
        isinstance(result.observed, dict)
        and result.observed.get("outcome_class") in {"bad", "critical_failure"}
        for result in results
    )


def test_j_p4_required_dimensions_and_adversarial_context_are_covered(repo_root) -> None:
    cases = load_golden_cases(repo_root / "data/evals/golden/pilot_decisions_j_p4_v1.json")
    for strategy in ("korvold", "rogshai"):
        strategy_cases = [case for case in cases if case.strategy == strategy]
        covered = {
            dimension for case in strategy_cases for dimension in case.expected_utility_dimensions
        }
        assert covered >= REQUIRED_DIMENSIONS
    assert any(case.state.hidden_information_uncertainty >= 0.8 for case in cases)
    assert any(case.state.opponent_intent_uncertainty >= 0.8 for case in cases)
    assert any(case.state.archenemy_player_id for case in cases)
    assert any(case.state.boardwipe_risk >= 0.8 for case in cases)
    assert any(case.state.commander_denial_risk >= 0.9 for case in cases)
    assert any(case.stack_state_if_relevant for case in cases)
    assert any(case.state.exposure_before_next_turn >= 4 for case in cases)


def test_j_p4_holdout_bytes_match_pre_tuning_seal_without_evaluating(repo_root) -> None:
    seal = json.loads((repo_root / "docs/J_P4_HOLDOUT_SEAL.json").read_text(encoding="utf-8"))
    holdout = repo_root / seal["holdout_path"]
    assert hashlib.sha256(holdout.read_bytes()).hexdigest() == seal["sha256"]
    payload = json.loads(holdout.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == seal["case_count"] == 24
    assert seal["outcomes_evaluated_at_seal"] is False
    assert seal["immutable_after_seal"] is True
    # This test intentionally does not call run_golden_cases on the holdout.
