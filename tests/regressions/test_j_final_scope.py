from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.engine.structural.project import _validate_structural_profile_ids
from commander_lab.tools.candidates import load_current_optimization_availability
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_active_own_deck_scope_is_rogshai_only_and_korvold_release_is_available() -> None:
    service = CommanderToolService(ROOT)
    assert service.ACTIVE_OWN_DECK_IDS == ("rogshai/current",)
    assert frozenset({"kaervek/current"}) == service.FROZEN_OPPONENT_ONLY_DECK_IDS
    current = load_current_optimization_availability(ROOT)
    assert current.get("Lightning Greaves", 0) >= 1


def test_fresh_rebuild_discovers_complete_current_rogshai_universe() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    assert result["physical_legal_candidate_count"] > 0
    assert result["physical_legal_candidate_count"] == result["discoverable_candidate_count"]
    assert result["candidate_recall"] == 1.0
    assert result["excluded_candidate_count_by_reason"] == {}
    assert sum(result["bucket_counts"].values()) == result["discoverable_candidate_count"]
    assert result["structurally_unmodeled"] > 0
    assert result["unmodeled_candidate_discoverability"] is True
    assert all(row["explorable"] is True for row in result["rows"])


def test_current_deck_membership_is_neutral_in_fresh_rebuild_discovery() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    discovered = {row["oracle_name"] for row in result["rows"]}
    eligibility = json.loads(
        (ROOT / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json").read_text(
            encoding="utf-8"
        )
    )["eligible_by_deck"]["rogshai/current"]
    current_names = {card.oracle_name for card in service.decks["rogshai/current"].cards}
    eligible_current_names = current_names.intersection(eligibility)
    assert eligible_current_names
    assert eligible_current_names <= discovered


def test_unmodeled_candidates_are_discovery_only_until_profiled() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    unmodeled = [
        row
        for row in result["rows"]
        if row["bucket"] == "requires_profile_before_model_dependent_recommendation"
    ]
    assert unmodeled
    assert all(row["model_dependent_recommendation_ready"] is False for row in unmodeled)
    assert all(row["explorable"] is True for row in unmodeled)


def test_structural_profile_duplicate_ids_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"profiles": [{"deck_id": "duplicate"}, {"deck_id": "duplicate"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate structural deck_id"):
        _validate_structural_profile_ids(path)
