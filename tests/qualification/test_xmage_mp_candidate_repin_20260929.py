"""Successor guard for the 2026-09-29 XMage multiplayer-candidate repin.

The live XMage pin is the integrated candidate (Mage PR #24). The frozen WSR22
current-boundary identity stays on the prior pin and is historical: this repin
opens a successor epoch, it does not relabel WSR22 evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "f79e4168902e65063034b21be6f4585397fd43b3"
CURRENT_TREE = "18c3e8e7588627b22accc08a644729399d702ee3"
PRIOR_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = "qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json"

ACTIVE_LITERAL_CONSUMERS = (
    "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java",
    "engine-bridge/src/test/java/org/commanderlab/xmage/JsonlBridgeTest.java",
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageCandidateEngineFingerprintTest.java",
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
    ".github/workflows/meta-qualification.yml",
    ".github/workflows/xmage-full-game-conformance.yml",
    ".github/workflows/xmage-real-4p-smoke.yml",
)


def _manifest() -> dict:
    return json.loads((REPO_ROOT / "config/rules_engines.json").read_text())


def _lock() -> dict:
    return json.loads((REPO_ROOT / SUCCESSOR_LOCK).read_text())


def test_live_pin_is_the_integrated_candidate() -> None:
    primary = _manifest()["primary_engine"]
    assert primary["commit"] == CURRENT_PIN
    assert primary["source_archive"].endswith(f"/{CURRENT_PIN}.tar.gz")
    assert primary["provider"] == "xmage"


def test_selection_truth_unchanged() -> None:
    cfg = _manifest()
    assert cfg["provider_decision"] == "NO_PROVIDER_READY"
    assert cfg["current_runtime"]["provider_selected"] is False
    assert cfg["current_runtime"]["production_provider"] is None


def test_successor_lock_binds_the_same_candidate_and_the_prior_pin() -> None:
    lock = _lock()
    assert lock["new_live_pin"]["commit"] == CURRENT_PIN
    assert lock["new_live_pin"]["tree"] == CURRENT_TREE
    assert lock["new_live_pin"]["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    donors = {donor["finding"]: donor for donor in lock["donors"]}
    assert donors["F-18"]["head"] == "6044132ecde384997d23121a8622ed308f68ae5d"
    assert donors["F-19"]["head"] == "0962f0b5d5147f606b517501b384a225af9f646a"
    assert donors["F-20"]["head"] == "9ec76cc6a9833d739fa83675b3b38e780f72dd7c"
    assert donors["F-21"]["head"] == "0082ad2983fc6d1b26f1d217e749cfc3a58d6c0b"
    assert "NOT merged" in donors["F-21"]["integration"]
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_provider_reports_the_candidate() -> None:
    provider = (REPO_ROOT / ACTIVE_LITERAL_CONSUMERS[0]).read_text()
    assert CURRENT_PIN in provider
    assert PRIOR_PIN not in provider


def test_all_active_literal_pin_consumers_migrated() -> None:
    for rel in ACTIVE_LITERAL_CONSUMERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN in text, rel
        assert PRIOR_PIN not in text, rel


def test_wsr22_boundary_stays_explicitly_historical_on_the_prior_pin() -> None:
    from commander_lab.qualification.current_boundary import source_lock

    # Answers "what was the WSR22 candidate?" only, never "what is pinned now?".
    assert source_lock.XMAGE_CANDIDATE_COMMIT == PRIOR_PIN
    assert source_lock.XMAGE_CANDIDATE_COMMIT != _manifest()["primary_engine"]["commit"]
    assert "not repinned" in _lock()["prior_live_pin"]["wsr22_source_lock"].lower()
