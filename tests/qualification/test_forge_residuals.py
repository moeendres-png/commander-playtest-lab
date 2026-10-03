"""Forge AF06/AF08 residuals (#459): the first missing mechanism, never credit."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import forge_residuals as fr
from commander_lab.qualification.current_boundary import forge_scenario_lane as lane
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "docs" / "forge_af06_af08_residuals_20261003" / "FORGE_RESIDUAL_MATRIX.json"


@pytest.fixture(scope="module")
def records() -> dict[str, dict]:
    materialization = load_effective_materialization(REPO_ROOT)
    return {record["fixture_id"]: record for record in materialization.denominator_records()}


@pytest.fixture(scope="module")
def scope(records) -> list[str]:
    return sorted(fixture for fixture in records if fr.in_scope(fixture))


def test_every_in_scope_row_is_classified(records, scope) -> None:
    """Every MICRO, PILOT and WS05 row maps fully: no unmapped dimension or token."""
    assert len(scope) == 70
    for fixture in scope:
        row = fr.classify_row(records[fixture])
        assert row.classification in {
            fr.LAB_EXECUTION_GAP,
            fr.PROVIDER_ADAPTER_GAP,
            fr.SCENARIO_LANE_EXECUTABLE,
        }
        assert "PASS" not in row.reason()


def test_every_obligation_token_has_one_observation_basis(records, scope) -> None:
    families = {
        str(token).split(":", 1)[0]
        for fixture in scope
        for token in (records[fixture].get("expected_events") or {}).get("required_events") or []
    }
    assert families <= set(fr.OBSERVATION)
    assert set(fr.OBSERVATION.values()) == {fr.READBACK, fr.DECISION_FRAME, fr.EVENT_LOG}


def test_out_of_scope_rows_are_refused(records) -> None:
    for fixture in ("HIDDEN_01", "CARD_02", "REPLAY_EVENT_TAPE", "PLAYER_COUNT_3P"):
        with pytest.raises(ValueError, match="not a Forge AF06/AF08"):
            fr.classify_row(records[fixture])


def test_an_unmapped_dimension_fails_closed(records, monkeypatch) -> None:
    monkeypatch.delitem(fr._CONSTRUCTION, "combat_state")
    with pytest.raises(ValueError, match="unmapped Forge lane construction"):
        fr.classify_row(records["MICRO_COMBAT"])
    monkeypatch.undo()
    monkeypatch.delitem(fr._UNOBSERVABLE, "owner_controller_divergence")
    with pytest.raises(ValueError, match="unmapped Forge readback"):
        fr.classify_row(records["WS05-MP-ELIM-CONTROL-3"])


def test_an_unmapped_obligation_token_fails_closed(records) -> None:
    record = copy.deepcopy(records["WS05-CMD-START-3"])
    record["expected_events"]["required_events"] = ["invented_family:P1"]
    with pytest.raises(ValueError, match="unmapped obligation token family"):
        fr.classify_row(record)


def test_provider_construction_gaps_come_before_lab_work(records) -> None:
    """MICRO_RULES_RANDOMNESS needs a cast too, but no Lab work reaches past its draws."""
    row = fr.classify_row(records["MICRO_RULES_RANDOMNESS"])
    assert row.first_missing["dimension"] == "rules_randomness.predetermined_semantic_draws"
    assert row.classification == fr.PROVIDER_ADAPTER_GAP
    assert any(item["class"] == fr.LAB_EXECUTION_GAP for item in row.mechanisms)


def test_event_only_tokens_are_named(records) -> None:
    row = fr.classify_row(records["MICRO_PREVENTION"])
    assert row.needs_event_log
    assert row.observation[fr.EVENT_LOG] == [
        "combat_damage_would_be:P2:2",
        "prevention_applied",
        "combat_damage_prevented:P2:2",
    ]
    assert "EVENT_LOG_UNSUPPORTED" in json.dumps(row.mechanisms)
    assert "prevention_applied" in row.reason()
    # A readback-only row needs no event log.
    assert not fr.classify_row(records["WS05-CMD-DMG-SAME-21"]).needs_event_log


def test_the_class_follows_the_record_not_the_row_id(records) -> None:
    """Wrong-reason control: removing the requested combat moves the first gap."""
    record = copy.deepcopy(records["WS05-CMD-DMG-SAME-21"])
    assert fr.classify_row(record).first_missing["dimension"] == "combat_state"
    record["combat_state"] = {}
    assert fr.classify_row(record).first_missing["dimension"] != "combat_state"


def test_a_lane_executable_row_is_never_called_a_pass(records) -> None:
    row = fr.classify_row(records["WS05-CMD-START-3"])
    assert row.classification == fr.SCENARIO_LANE_EXECUTABLE
    assert row.lane_obligation_kind == "starting_player_first_turn_draw"
    assert "only through that lane's runner-bound receipt" in row.reason()
    assert "PASS" not in row.reason()


def test_lane_obligation_kinds_match_the_lane(records, scope) -> None:
    """Every kind the lane evaluates is one this module treats as observed."""
    kinds = {lane._obligation_kind(lane.model_requested_state(records[f])) for f in scope}
    assert kinds - {None} <= fr._LANE_OBLIGATION_KINDS


def test_the_committed_matrix_is_current(records, scope) -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    identity = load_effective_materialization(REPO_ROOT).receipt()
    assert matrix["contract_id"] == identity["contract_id"]
    assert matrix["canonical_bundle_digest"] == identity["canonical_bundle_digest"]
    fresh = fr.build_matrix(records, scope)
    assert matrix["rows"] == fresh["rows"]
    assert matrix["summary"] == fresh["summary"]
    assert matrix["summary"]["pass"] == 0


def _runner(monkeypatch):
    monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    path = REPO_ROOT / "scripts" / "run_current_boundary_qualification.py"
    spec = importlib.util.spec_from_file_location("fr_runner_under_test", path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, runner)
    spec.loader.exec_module(runner)
    return runner


def test_the_runner_reason_is_exact_for_forge_only(records, monkeypatch) -> None:
    """Forge in-scope rows keep their outcome and gain the exact reason; XMage is unchanged."""
    runner = _runner(monkeypatch)
    materialization = runner.load_effective_materialization(REPO_ROOT)
    identity = {"starting_state_injection_supported": True}
    rows = {
        candidate: {
            row.fixture_id: row
            for row in runner.classify_remaining(
                materialization, set(), candidate=candidate, identity=identity
            )
        }
        for candidate in ("forge", "xmage")
    }
    for fixture, forge in rows["forge"].items():
        xmage = rows["xmage"][fixture]
        assert forge.outcome == xmage.outcome, fixture
        if fr.in_scope(fixture):
            assert forge.reason.endswith(fr.row_reason(records[fixture])), fixture
        else:
            assert "first missing mechanism" not in forge.reason, fixture
    assert all("first missing mechanism" not in row.reason for row in rows["xmage"].values())


@pytest.mark.parametrize("fixture", ["PILOT_MULLIGAN", "WS05-CMD-MULL-2", "WS05-CMD-MULL-4"])
def test_a_mulligan_is_a_provider_gap(records, fixture) -> None:
    """Taking a mulligan calls tuckCardsViaMulligan, which the pinned bridge rejects."""
    row = fr.classify_row(records[fixture])
    assert row.classification == fr.PROVIDER_ADAPTER_GAP
    assert row.first_missing["dimension"].startswith("decision_execution.mulligan")
    assert "tuckCardsViaMulligan" in row.first_missing["detail"]


def test_an_unmapped_decision_family_fails_closed(records, monkeypatch) -> None:
    monkeypatch.delitem(fr._DECISION_FAMILIES, "declare_attacker")
    with pytest.raises(ValueError, match="unmapped Forge decision family"):
        fr.classify_row(records["PILOT_DECLARE_ATTACKER"])


def test_a_provider_gap_anywhere_names_the_class(records) -> None:
    """A Lab gap earlier in the pipeline does not hide a provider gap later in it."""
    row = fr.classify_row(records["MICRO_PREVENTION"])
    assert row.mechanisms[0]["class"] == fr.LAB_EXECUTION_GAP
    assert row.classification == fr.PROVIDER_ADAPTER_GAP
    assert row.first_missing["dimension"] == "event_log"


def test_a_classification_error_keeps_the_outcome(monkeypatch) -> None:
    """A contract change the table does not know fails the reason closed, not the run."""
    runner = _runner(monkeypatch)
    materialization = runner.load_effective_materialization(REPO_ROOT)
    identity = {"starting_state_injection_supported": True}
    before = {
        row.fixture_id: row.outcome
        for row in runner.classify_remaining(
            materialization, set(), candidate="forge", identity=identity
        )
    }

    def broken(record):
        raise ValueError("unmapped obligation token family 'new'")

    monkeypatch.setattr(runner.forge_residuals_mod, "row_reason", broken)
    rows = runner.classify_remaining(materialization, set(), candidate="forge", identity=identity)
    for row in rows:
        assert row.outcome == before[row.fixture_id]
        if fr.in_scope(row.fixture_id):
            assert "classification failed closed" in row.reason
