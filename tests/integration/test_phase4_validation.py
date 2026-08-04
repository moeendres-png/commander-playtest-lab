from __future__ import annotations

from commander_lab.agents.validation import run_phase4_validation


def test_phase4_validation_is_reproducible_and_audited(tmp_path, repo_root) -> None:
    summary = run_phase4_validation(
        repo_root,
        iterations=2,
        workers=1,
        seed=707,
        output_directory=tmp_path / "phase4",
    )
    assert summary["estimate_type"] == "structural_model_estimates"
    assert summary["stochastic_replay_identical_across_worker_counts"]
    audit = summary["decision_log_audit"]
    assert audit["match_completed"]
    assert audit["decision_events"] > 0
    assert audit["required_utility_dimensions_present"]
    benchmark = summary["strength_decision_benchmark"]
    assert benchmark["monotonic_non_decreasing"]
    rates = benchmark["by_strength"]
    assert rates["weak"]["expected_choice_rate"] < rates["average"]["expected_choice_rate"]
    assert rates["average"]["expected_choice_rate"] <= rates["strong"]["expected_choice_rate"]
    assert rates["strong"]["expected_choice_rate"] <= rates["near_optimal_heuristic"]["expected_choice_rate"]
