from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import dimension_admission as A
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def materialization():
    return load_effective_materialization(ROOT)


@pytest.fixture()
def manifest() -> dict:
    return {
        "schema_version": "native-state-restoration-dimensions-1.1.0",
        "starting_state_injection_supported": False,
        "supported_dimensions": [
            "commanders with prior cast counts (native game-load restore path)",
            "commander damage matrices through exact live CommanderInfoWatcher bindings",
            "battlefield/graveyard/exile placement of real cards",
            "hand identity via the same setup primitive",
            "owner-equals-controller attribution with 1:1 readback",
            "life totals (pre-start assembly; state-based actions stay authoritative)",
            "qualified turn-1 temporal targets: upkeep, draw, precombat main, declare attackers, "
            "declare blockers, combat damage, postcombat main",
            "explicit Rules-seed binding with replay determinism",
            "strict native readback with field-level compare and digests",
        ],
        "unsupported_dimensions": [
            "stack spells (casting requires real costs/timing: executor scope)",
            "legacy/frozen partial library identity: no complete permutation, fail closed",
            "legacy/frozen face_down=true without explicit native type: fail closed",
            "revealed-zone restoration",
            "controller/owner divergence (engine layers re-derive control)",
            "attachments and counters",
            "tapped permanents (unqualified dimension)",
            "commander relations other than validated Partner linkage",
            "poison counters",
            "temporal points outside the qualified RG-03 turn-1 checkpoint allow-list",
            "zero-life pre-start state: full-game initialization re-derives starting life",
        ],
    }


def test_combat_row_is_admitted_by_semantics_not_name(materialization, manifest) -> None:
    record = materialization.record("WS05-MP-COMBAT-4")
    result = A.admit_record(record, manifest)
    assert result["verdict"] == A.ADMITTED
    assert "qualified turn-1" in result["required_tokens"]


def test_renaming_a_supported_record_does_not_change_admission(
    materialization, manifest
) -> None:
    record = dict(materialization.record("WS05-MP-COMBAT-4"))
    original = A.admit_record(record, manifest)
    record["fixture_id"] = "THIS_NAME_HAS_NO_ROUTING_MEANING"
    renamed = A.admit_record(record, manifest)
    assert renamed == original


def test_stack_object_blocks_even_when_event_name_looks_unrelated(manifest) -> None:
    record = {
        "fixture_id": "arbitrary",
        "expected_events": {"required_events": ["attacker_declared:obj:a->P2"]},
        "players": [{"player_id": "P1", "life": 40}],
        "semantic_objects": [
            {
                "semantic_id": "obj:s",
                "zone": "stack",
                "owner": "P1",
                "controller": "P1",
                "tapped": False,
            }
        ],
        "temporal_state": {"turn_number": 1},
        "commander_state": {},
    }
    result = A.admit_record(record, manifest)
    assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
    assert "stack spells" in result["missing_tokens"]


def test_current_main_control_divergence_row_fails_closed(
    materialization, manifest
) -> None:
    result = A.admit_record(
        materialization.record("WS05-MP-ELIM-CONTROL-3"), manifest
    )
    assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
    assert "controller/owner divergence" in result["missing_tokens"]


@pytest.mark.parametrize(
    "fixture_id",
    [
        "WS05-MP-ELIM-5",
        "WS05-MP-ELIM-OWNED-3",
        "WS05-MP-ELIM-PRIO-3",
        "WS05-MP-ELIM-TURN-3",
    ],
)
def test_current_main_zero_life_rows_fail_closed(
    fixture_id: str, materialization, manifest
) -> None:
    result = A.admit_record(materialization.record(fixture_id), manifest)
    assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
    assert "zero-life pre-start" in result["missing_tokens"]


def test_unreadable_or_empty_manifest_never_falls_back_to_global_flag(
    materialization,
) -> None:
    record = materialization.record("WS05-MP-COMBAT-4")
    for manifest in (
        None,
        {},
        {
            "starting_state_injection_supported": True,
            "supported_dimensions": [],
            "unsupported_dimensions": [],
        },
    ):
        result = A.admit_record(record, manifest)
        assert result["verdict"] == A.BLOCKED_MANIFEST_UNAVAILABLE


def test_unknown_required_event_fails_closed(manifest) -> None:
    result = A.admit_row(["new_magic_mechanism:v99"], manifest, [])
    assert result["verdict"] == A.BLOCKED_UNKNOWN_DIMENSION
    assert "<unmapped-required-event>" in result["unknown_tokens"]


def test_empty_declaration_is_not_admitted(manifest) -> None:
    result = A.admit_row([], manifest, [])
    assert result["verdict"] == A.BLOCKED_UNKNOWN_DIMENSION


def test_partial_library_identity_stays_blocked(materialization, manifest) -> None:
    result = A.admit_record(
        materialization.record("WS05-CMD-ZONE-LIB-YES"), manifest
    )
    assert result["verdict"] == A.BLOCKED_MISSING_DIMENSION
    assert "partial library identity" in result["missing_tokens"]


def test_admission_manifest_is_accounting_complete_for_selected_rows(
    materialization, manifest
) -> None:
    records = [
        materialization.record("WS05-MP-COMBAT-4"),
        materialization.record("WS05-MP-ELIM-CONTROL-3"),
        materialization.record("WS05-MP-ELIM-5"),
    ]
    doc = A.admit_manifest(records, manifest)
    assert doc["rows_total"] == 3
    assert doc["counts"]["admitted"] + doc["counts"]["blocked"] == 3
    assert doc["admitted"] == ["WS05-MP-COMBAT-4"]
    assert set(doc["blocked"]) == {
        "WS05-MP-ELIM-CONTROL-3",
        "WS05-MP-ELIM-5",
    }
    assert "runtime execution" in doc["projection_note"]
