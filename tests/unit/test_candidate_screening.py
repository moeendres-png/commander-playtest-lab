from __future__ import annotations

from pathlib import Path

from commander_lab.candidate_screening import CandidateScreener, RogShaiCandidateScreener
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_current_rogshai_pool_screen_reduces_default_work_without_hiding_exploration() -> None:
    service = CommanderToolService(ROOT)
    screener = CandidateScreener(ROOT, service=service)
    result = screener.screen_pool("rogshai/current")
    assert result["deck_id"] == "rogshai/current"
    assert result["physical_legal_candidate_count"] > 0
    assert result["candidate_pool_after_default_screen"] <= result["physical_legal_candidate_count"]
    assert result["unusual_candidates_remain_explorable"] is True
    assert result["playstyle_policy"] == "post_build_review_only"
    assert result["playstyle_used_for_screening"] is False
    assert all("playstyle_fit" not in row for row in result["rows"])
    assert all("playstyle_confidence" not in row for row in result["rows"])
    assert sum(result["bucket_counts"].values()) == result["physical_legal_candidate_count"]
    assert (
        result["semantic_evidence"]["coverage_policy"]
        == "decision_weighted_not_full_pool_annotation"
    )
    assert result["semantic_evidence"]["llm_inferred_is_canonical"] is False


def test_historical_rogshai_challenge_set_remains_regression_only() -> None:
    service = CommanderToolService(ROOT)
    screener = RogShaiCandidateScreener(ROOT, service=service)
    result = screener.benchmark_challenge_set()
    assert result["historical_regression_only"] is True
    assert result["rogshai_variant_count"] == 6
    assert len(result["evaluated"]) == 6
    assert 0.0 < result["legal_candidate_recall"] <= 1.0
    assert result["evidence_boundary"] == "structural_model_estimates"
    assert all(row["decision"]["constraint_valid"] for row in result["evaluated"])
    assert result["known_good_candidate_recall"] == 1.0
    assert result["known_bad_candidate_rejection"] == 1.0
    assert {row["decision"]["bucket"] for row in result["evaluated"]} == {
        "advance",
        "explore",
        "deprioritize_static",
    }
    assert all(
        row["decision"]["playstyle_review_status"] == "deferred_until_post_build_review"
        for row in result["evaluated"]
    )


def test_current_rogshai_projection_count_remains_a_data_regression_not_core_contract() -> None:
    service = CommanderToolService(ROOT)
    result = CandidateScreener(ROOT, service=service).screen_pool("rogshai/current")
    lane = result["progressive_model_coverage"]

    assert len(lane["selected"]) <= 12
    assert lane["unmodeled_is_negative"] is False
    assert lane["profiling_required_before_simulation"] is True
    assert all(row["performance_assumption"] is None for row in lane["selected"])
    # Current projection regression only. Generic CandidateScreener has no fixed count.
    assert result["discoverable_candidate_count"] == 795
