"""Residual Mage candidate forward-repin impact guards.

Current runtime/CI consumers must bind to the cumulative M1-M4 Mage candidate.
Sealed historical evidence remains byte/provenance-bound to the prior pin and
must not be silently relabeled as current evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
HISTORICAL_PIN = "db134b9737e951367d65ef5806ad986319cc73ab"

ACTIVE_LITERAL_CONSUMERS = (
    "scripts/bootstrap_engine_linux.sh",
    "scripts/bootstrap_engine_windows.ps1",
    "scripts/run_external_full_game_conformance.py",
    "scripts/run_real_deck_gate.py",
    "scripts/run_real_4p_full_game_smoke.py",
    "tests/unit/test_xmage_full_game.py",
    "tests/unit/test_xmage_compatibility_provider.py",
    "tests/unit/test_xmage_variable_player.py",
    "tests/unit/test_ws_a1r_pin_authority.py",
    "tests/unit/test_ws_arclose_d1_authority_drift.py",
    "tests/unit/test_ws223_cardinality_regression.py",
    "tests/unit/test_ws_a1d_docker_pin_authority.py",
    ".github/workflows/external-engine-integration.yml",
    ".github/workflows/xmage-full-game-conformance.yml",
    ".github/workflows/xmage-real-4p-smoke.yml",
)

SEALED_HISTORICAL_EVIDENCE = (
    "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-3p.json",
    "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json",
    "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-5p.json",
    "qualification/ws232-retention-nscoped-requalification/RETENTION_PREDICATES.json",
    "qualification/ws232-retention-nscoped-requalification/RETENTION_PREDICATE_RESULTS.json",
    "docs/workstream_deep_research_closure_20260923/HANDOFF.md",
)


def test_current_machine_authority_is_residual_candidate() -> None:
    cfg = json.loads((REPO_ROOT / "config/rules_engines.json").read_text())
    primary = cfg["primary_engine"]
    assert primary["commit"] == CURRENT_PIN
    assert primary["source_archive"].endswith(f"/{CURRENT_PIN}.tar.gz")
    assert cfg["provider_decision"] == "NO_PROVIDER_READY"
    assert cfg["current_runtime"]["provider_selected"] is False
    assert cfg["current_runtime"]["production_provider"] is None


def test_bridge_identity_and_phase6_use_current_native_restore() -> None:
    provider = (
        REPO_ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java"
    ).read_text()
    assert CURRENT_PIN in provider
    assert HISTORICAL_PIN not in provider

    phase6 = (
        REPO_ROOT
        / "engine-bridge/src/main/java/org/commanderlab/xmage/Phase6DifferentialAdapter.java"
    ).read_text()
    assert "XmageProvider.ENGINE_COMMIT" in phase6
    assert "restoreDamageStateForGameLoad" in phase6
    assert "getDamageToPlayer().put" not in phase6
    assert HISTORICAL_PIN not in phase6


def test_all_active_literal_pin_consumers_migrated() -> None:
    for rel in ACTIVE_LITERAL_CONSUMERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN in text, rel
        assert HISTORICAL_PIN not in text, rel


def test_ws232_and_prior_replay_evidence_remain_historical() -> None:
    for rel in SEALED_HISTORICAL_EVIDENCE:
        text = (REPO_ROOT / rel).read_text()
        assert HISTORICAL_PIN in text, rel
        assert CURRENT_PIN not in text, rel


def test_ws232_predicates_are_invalidated_not_rewritten() -> None:
    predicates = json.loads(
        (
            REPO_ROOT
            / "qualification/ws232-retention-nscoped-requalification/RETENTION_PREDICATES.json"
        ).read_text()
    )
    engine_binds = [
        bind
        for predicate in predicates["predicates"]
        for bind in predicate["binds"]
        if bind["path"] == "config/rules_engines.json#primary_engine.commit"
    ]
    assert engine_binds
    assert all(bind["expected_value"] == HISTORICAL_PIN for bind in engine_binds)
    assert all(bind["expected_value"] != CURRENT_PIN for bind in engine_binds)
