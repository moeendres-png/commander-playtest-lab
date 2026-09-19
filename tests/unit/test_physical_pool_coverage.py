"""Unit tests for the per-card source/rule-path coverage matrix."""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.physical_pool.coverage import build_source_matrix

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "physical_pool_prepare_sos.json"


def test_build_source_matrix_separates_import_from_behavior() -> None:
    identities = [
        {
            "card_id": "card:with-everything",
            "oracle_name": "Complete Card",
            "oracle_text": "Flying.",
            "card_faces_if_relevant": [{"name": "Complete Card"}],
        },
        {"card_id": "card:textless", "oracle_name": "Textless", "oracle_text": None},
    ]
    knowledge = {"card:with-everything": {"functional_semantics": {"roles": ["evasion"]}}}
    semantics = {"card:with-everything": {"roles": ["evasion", "flying"]}}
    matrix = build_source_matrix(
        identities, knowledge, semantics, {"card:with-everything": "uuid-1"},
        population="unit-probe",
    )
    assert matrix.population_size == 2
    full = matrix.rows[0]
    assert full.has_oracle_text == "PRESENT"
    assert full.has_faces == "PRESENT"
    assert full.has_structural_roles == "PRESENT"
    assert full.has_structural_semantics == "PRESENT"
    assert full.oracle_identity == "PRESENT"
    # Import never proves behavior.
    assert full.engine_behavior == "UNKNOWN"
    thin = matrix.rows[1]
    assert thin.has_oracle_text == "ABSENT"
    assert thin.oracle_identity == "UNKNOWN"
    summary = matrix.source_summary()
    assert summary["has_oracle_text"] == {"PRESENT": 1, "ABSENT": 1, "UNKNOWN": 0}
    assert matrix.behavior_summary() == {
        "FULL": 0, "CONDITIONAL_FULL": 0, "PARTIAL": 0, "UNSUPPORTED": 0, "UNKNOWN": 2,
    }


def test_prepare_fixture_is_patch_ready_and_unclaimed() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["engine_pin"] == "xmage-1.4.61"
    assert fixture["production_provider"] == "NOT_SELECTED"
    assert len(fixture["cards"]) == 11
    for card in fixture["cards"]:
        assert card["card_id"].startswith("card:project:")
        # True card objects: multi-face cards carry faces; single-faced cards
        # carry complete identity oracle data instead.
        if card["single_faced"]:
            assert card["oracle_text"] and card["type_line"], card["oracle_name"]
        else:
            assert card["faces"], card["oracle_name"]
        assert card["observed_output"] == "NOT_RUN"
        assert card["verdict"] == "UNKNOWN"
        assert len(card["required_rule_paths"]) >= 10
