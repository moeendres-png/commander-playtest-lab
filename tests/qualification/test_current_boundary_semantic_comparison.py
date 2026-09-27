"""SAME_SEMANTICS must be a comparison, not a label match.

The defect: ``if xr["exit_state"] == fr["exit_state"] == "PASS"`` produced
SAME_SEMANTICS. Two engines that each report PASS while observing a different
turn number, a different library count, or an extra event were labelled
semantically equal, and the historical ``25/107 SAME_SEMANTICS`` figure counted
those labels rather than any semantics.
"""

from __future__ import annotations

import ast
from pathlib import Path

from commander_lab.qualification.current_boundary.semantic import (
    compare_semantics,
    semantic_signature,
)

REPO = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO / "scripts/assemble_current_boundary_evidence.py"


def _row(evidence: dict) -> dict:
    return {"fixture_id": "F1", "exit_state": "PASS", "evidence": evidence}


BASE = {
    "semantic_events": ["draw_step_exposed:P1", "priority:P1"],
    "observed_decision_kinds": ["PRIORITY", "PRIORITY"],
    "observed_actor_zone_counts": [{"hand_count": 8, "library_count": 91}],
    "priority_reached": True,
    "player_count": 2,
}


def test_identical_observations_are_same_semantics() -> None:
    result = compare_semantics(_row(dict(BASE)), _row(dict(BASE)))
    assert result["disposition"] == "SAME_SEMANTICS"
    assert result["equal"] is True


def test_a_different_event_sequence_is_a_difference_not_an_equality() -> None:
    other = dict(BASE)
    other["semantic_events"] = ["draw_step_exposed:P1"]
    result = compare_semantics(_row(BASE), _row(other))
    assert result["disposition"] == "SEMANTIC_DIFFERENCE"
    assert result["equal"] is False
    assert "semantic_events" in result["differing_keys"]


def test_a_different_zone_count_is_a_difference() -> None:
    other = dict(BASE)
    other["observed_actor_zone_counts"] = [{"hand_count": 7, "library_count": 91}]
    result = compare_semantics(_row(BASE), _row(other))
    assert result["disposition"] == "SEMANTIC_DIFFERENCE"
    assert "observed_actor_zone_counts" in result["differing_keys"]


def test_a_missing_event_on_one_side_is_a_difference() -> None:
    other = {k: v for k, v in BASE.items() if k != "priority_reached"}
    result = compare_semantics(_row(BASE), _row(other))
    assert result["disposition"] == "SEMANTIC_DIFFERENCE"


def test_no_semantic_evidence_yields_unknown_not_equality() -> None:
    """PASS with nothing observed cannot establish semantic equality."""
    result = compare_semantics(_row({}), _row(dict(BASE)))
    assert result["disposition"] == "UNKNOWN_NO_COMPARABLE_EVIDENCE"
    assert result["equal"] is None
    assert "left" in result["reason"]


def test_both_sides_empty_yields_unknown() -> None:
    result = compare_semantics(_row({}), _row({}))
    assert result["disposition"] == "UNKNOWN_NO_COMPARABLE_EVIDENCE"
    assert "evidence" in result["reason"]


def test_candidate_specific_identity_is_removed() -> None:
    """A different engine commit or session id must not create a difference."""
    left = dict(BASE)
    left["runtime_identity"] = {"engine_candidate_commit": "a" * 40, "runner_tree": "b" * 40}
    right = dict(BASE)
    right["runtime_identity"] = {"engine_candidate_commit": "c" * 40, "runner_tree": "d" * 40}
    left["game_id"] = "game-left"
    right["game_id"] = "game-right"
    result = compare_semantics(_row(left), _row(right))
    assert result["disposition"] == "SAME_SEMANTICS", result["reason"]


def test_a_32_char_hash_value_is_treated_as_identity() -> None:
    left = dict(BASE)
    left["object_id"] = "a" * 40
    right = dict(BASE)
    right["object_id"] = "b" * 40
    assert compare_semantics(_row(left), _row(right))["disposition"] == "SAME_SEMANTICS"


def test_signature_is_stable_under_key_order() -> None:
    one = _row({"semantic_events": ["a"], "priority_reached": True})
    two = _row({"priority_reached": True, "semantic_events": ["a"]})
    assert semantic_signature(one)["digest"] == semantic_signature(two)["digest"]


def test_absent_signature_reports_what_it_looked_for() -> None:
    signature = semantic_signature(_row({"unrelated": 1}))
    assert signature["present"] is False
    assert "semantic_events" in signature["searched"]


def test_non_mapping_evidence_is_handled() -> None:
    assert semantic_signature({"fixture_id": "F1", "evidence": "oops"})["present"] is False
    assert semantic_signature({"fixture_id": "F1"})["present"] is False


def test_assembler_calls_the_semantic_comparison() -> None:
    source = ASSEMBLER.read_text(encoding="utf-8")
    assert "compare_semantics" in source
    assert "SEMANTIC_DIFFERENCE" in source
    # And the old label-only branch must be gone.
    assert (
        'if xr["exit_state"] == fr["exit_state"] == "PASS":\n            disposition = "SAME_SEMANTICS"'
        not in source
    )


def test_same_semantics_literal_is_not_assigned_in_the_comparison_loop() -> None:
    """A literal SAME_SEMANTICS assignment would reintroduce the defect."""
    tree = ast.parse(ASSEMBLER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            assert node.value.value != "SAME_SEMANTICS", "SAME_SEMANTICS must be derived"
