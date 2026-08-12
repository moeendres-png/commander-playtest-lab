from __future__ import annotations

from commander_lab.models.tooling import GenerateCandidateSwapsInput
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.tools import CommanderToolService


def test_frontier_reports_cut_composition_and_preserves_candidate_recall(repo_root):
    service = CommanderToolService(repo_root)
    response = service.generate_candidate_swaps(
        GenerateCandidateSwapsInput(deck_id="rogshai/current", max_candidates=50)
    )
    assert response.status.value == "completed"
    result = response.result
    assert result["candidate_recall"] == 1.0
    assert result["cut_frontier_gate"]["scalar_profile_score_is_sole_authority"] is False
    assert result["cut_frontier_gate"]["whole_deck_constraints_checked_before_simulation"] is True
    composition = result["frontier_composition"]
    assert composition["pair_count"] == result["count"]
    assert composition["unique_cut_count"] > 1
    assert 0.0 < composition["top_cut_pair_share"] <= 1.0
    assert all(row["semantic_evidence_hash"] for row in result["candidates"])


def test_prefix_reuse_is_exactly_equivalent_to_monolithic(repo_root, tmp_path):
    pair = {
        "deck_id": "rogshai/current",
        "remove": "Preordain",
        "add_candidate_id": "rogshai/opt-smoke",
    }
    staged = PriorityWorkflowFacade(repo_root, result_cache_path=tmp_path / "staged.sqlite3")
    first = staged.compare_validate(**pair, iterations=8, seed=2026081203, max_turns=20, workers=1)
    assert first["status"] == "completed"
    second = staged.compare_validate(
        **pair, iterations=16, seed=2026081203, max_turns=20, workers=1
    )
    assert second["incremental_execution"]["reused_prefix_count"] == 8
    assert second["incremental_execution"]["incremental_simulated_count"] == 8

    clean = PriorityWorkflowFacade(repo_root, result_cache_path=tmp_path / "clean.sqlite3")
    monolithic = clean.compare_validate(
        **pair, iterations=16, seed=2026081203, max_turns=20, workers=1
    )
    assert monolithic["incremental_execution"]["reused_prefix_count"] == 0
    assert second["paired"] == monolithic["paired"]
    assert second["paired_observations"] == monolithic["paired_observations"]
    assert (
        second["cache_provenance"]["exact_seed_set_sha256"]
        == monolithic["cache_provenance"]["exact_seed_set_sha256"]
    )
