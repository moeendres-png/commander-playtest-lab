from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import dimension_admission as A
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_ADMITTED = {
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
    "WS05-CMD-ELIM-4",
    "WS05-MP-BLOCK-4",
    "WS05-MP-COMBAT-4",
    "WS05-MP-COMBAT-5",
    "WS05-CMD-DMG-CONTROL",
    "WS05-CMD-DMG-SAME-21",
    "WS05-CMD-DMG-SPLIT",
    "WS05-MP-ELIM-5",
    "WS05-MP-ELIM-CONTROL-3",
    "WS05-MP-ELIM-OWNED-3",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-ELIM-TURN-3",
}
EXPECTED_BLOCKED = set(A.PB03_FIXTURE_IDS) - EXPECTED_ADMITTED


@pytest.fixture(scope="module")
def materialization():
    return load_effective_materialization(ROOT)


@pytest.fixture()
def manifest() -> dict:
    return {
        "schema_version": "native-state-restoration-dimensions-1.1.0",
        "starting_state_injection_supported": False,
        "supported_dimensions": [
            "commander damage matrices through exact live CommanderInfoWatcher bindings",
            "battlefield/graveyard/exile placement of real cards",
            "hand identity via the same setup primitive",
            "life totals (pre-start assembly; state-based actions stay authoritative)",
            "qualified turn-1 temporal targets: upkeep, draw, precombat main, declare attackers, "
            "declare blockers, combat damage, postcombat main",
        ],
        "unsupported_dimensions": [
            "stack spells (casting requires real costs/timing: executor scope)",
            "legacy/frozen partial library identity: no complete permutation, fail closed",
            "temporal points outside the qualified RG-03 turn-1 checkpoint allow-list",
        ],
    }


def test_pb03_scope_is_exactly_thirty_unique_rows() -> None:
    assert len(A.PB03_FIXTURE_IDS) == 30
    assert len(set(A.PB03_FIXTURE_IDS)) == 30


def test_current_boundary_projection_is_exact_14_admitted_16_blocked(
    materialization, manifest
) -> None:
    doc = A.admit_manifest(materialization.denominator_records(), manifest)
    assert doc["rows_total"] == 30
    assert doc["counts"] == {"admitted": 14, "blocked": 16}
    assert set(doc["admitted"]) == EXPECTED_ADMITTED
    assert set(doc["blocked"]) == EXPECTED_BLOCKED
    assert doc["derivation"] == "required_events + semantic_objects[].zone only"


def test_control_divergence_and_zero_life_do_not_decide_admission(
    materialization, manifest
) -> None:
    for fixture_id in (
        "WS05-MP-ELIM-CONTROL-3",
        "WS05-MP-ELIM-5",
        "WS05-MP-ELIM-OWNED-3",
        "WS05-MP-ELIM-PRIO-3",
        "WS05-MP-ELIM-TURN-3",
    ):
        assert A.admit_record(materialization.record(fixture_id), manifest)["verdict"] == A.ADMITTED


def test_stack_zone_blocks_even_when_runtime_can_reconstruct_cause(
    materialization, manifest
) -> None:
    result = A.admit_record(materialization.record("WS05-MP-ELIM-STACK-3"), manifest)
    assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
    assert "stack spells" in result["missing_tokens"]


def test_trigger_events_require_stack_dimension(materialization, manifest) -> None:
    for fixture_id in ("WS05-MP-TRIG-3", "WS05-MP-TRIG-5"):
        result = A.admit_record(materialization.record(fixture_id), manifest)
        assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
        assert "stack spells" in result["missing_tokens"]


def test_library_rows_name_both_missing_dimensions(materialization, manifest) -> None:
    for fixture_id in ("WS05-CMD-ZONE-LIB-YES", "WS05-CMD-ZONE-LIB-NO"):
        result = A.admit_record(materialization.record(fixture_id), manifest)
        assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
        assert "stack spells" in result["missing_tokens"]
        assert "partial library identity" in result["missing_tokens"]


def test_extra_turn_rows_block_on_temporal_dimension(materialization, manifest) -> None:
    for fixture_id in ("WS05-MP-TURN-3", "WS05-MP-TURN-5"):
        result = A.admit_record(materialization.record(fixture_id), manifest)
        assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
        assert "temporal points outside the qualified" in result["missing_tokens"]


def test_rules_randomness_unknown_token_fails_closed(materialization, manifest) -> None:
    result = A.admit_record(materialization.record("MICRO_RULES_RANDOMNESS"), manifest)
    assert result["verdict"] == A.BLOCKED_UNKNOWN_DIMENSION
    assert "<unmapped-required-event>" in result["unknown_tokens"]


def test_fixture_name_never_decides_verdict(materialization, manifest) -> None:
    record = dict(materialization.record("WS05-MP-COMBAT-4"))
    original = A.admit_record(record, manifest)
    record["fixture_id"] = "NAME_MUST_HAVE_ZERO_ROUTING_POWER"
    assert A.admit_record(record, manifest) == original


@pytest.mark.parametrize(
    "bad_manifest",
    [
        None,
        {},
        {"supported_dimensions": [], "unsupported_dimensions": []},
        {
            "starting_state_injection_supported": True,
            "supported_dimensions": [],
            "unsupported_dimensions": [],
        },
    ],
)
def test_missing_or_empty_manifest_fails_closed_without_global_flag_fallback(
    materialization, bad_manifest
) -> None:
    result = A.admit_record(materialization.record("WS05-MP-COMBAT-4"), bad_manifest)
    assert result["verdict"] == A.BLOCKED_MANIFEST_UNAVAILABLE


def test_global_capability_flag_does_not_change_row_admission(materialization, manifest) -> None:
    record = materialization.record("WS05-MP-COMBAT-4")
    false_flag = A.admit_record(record, manifest)
    true_manifest = dict(manifest)
    true_manifest["starting_state_injection_supported"] = True
    true_flag = A.admit_record(record, true_manifest)
    assert false_flag == true_flag
    assert true_flag["verdict"] == A.ADMITTED
