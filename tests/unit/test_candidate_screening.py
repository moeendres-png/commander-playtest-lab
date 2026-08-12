from __future__ import annotations

from pathlib import Path

from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_rogshai_pool_screen_reduces_default_work_without_hiding_exploration() -> None:
    service = CommanderToolService(ROOT)
    screener = RogShaiCandidateScreener(ROOT, service=service)
    result = screener.screen_pool()
    assert result["physical_legal_candidate_count"] > 0
    assert result["candidate_pool_after_default_screen"] <= result["physical_legal_candidate_count"]
    assert result["unusual_candidates_remain_explorable"] is True
    assert result["playstyle_policy"] == "post_build_review_only"
    assert result["playstyle_used_for_screening"] is False
    assert all("playstyle_fit" not in row for row in result["rows"])
    assert all("playstyle_confidence" not in row for row in result["rows"])
    assert sum(result["bucket_counts"].values()) == result["physical_legal_candidate_count"]


def test_current_rogshai_challenge_set_covers_valid_static_buckets() -> None:
    service = CommanderToolService(ROOT)
    screener = RogShaiCandidateScreener(ROOT, service=service)
    result = screener.benchmark_challenge_set()
    assert result["rogshai_variant_count"] == 3
    assert len(result["evaluated"]) == 3
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
