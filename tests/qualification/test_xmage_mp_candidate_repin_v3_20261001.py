"""Successor guard for the 2026-10-01 XMage multiplayer-candidate repin (v3).

The live XMage pin is the candidate branch advanced by the Rules-Core fixes for
F-43 (a departed combat-damage assigner must not deal cached damage, mage#29) and
F-44 (a player who leaves while ordering its triggers puts none on the stack,
mage#33), both CR 800.4a, and F-45 (copied spell moved to its owner's library, mage#35). The prior pin (9375f35a, successor lock v2) and the
frozen WSR22 current-boundary identity stay historical: this repin opens a new
successor epoch, it does not relabel earlier evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "37e4df6c914f1e189e24f0ef59fa91734c922436"
CURRENT_TREE = "dac695ab2862e965cdaa30b0ce67052840dc7a5e"
PRIOR_PIN = "9375f35ac7c9a540ebcb8b262b8645b8c6b1b326"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = "qualification/xmage-mp-candidate-repin-v3-20261001/SUCCESSOR_SOURCE_LOCK.json"

ACTIVE_LITERAL_CONSUMERS = (
    "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java",
    "engine-bridge/src/test/java/org/commanderlab/xmage/JsonlBridgeTest.java",
    "engine-bridge/src/test/java/org/commanderlab/xmage/XmageCandidateEngineFingerprintTest.java",
    "tests/unit/test_ws_a1r_pin_authority.py",
    "tests/unit/test_ws_arclose_d1_authority_drift.py",
    "tests/unit/test_ws_a1d_docker_pin_authority.py",
    ".github/workflows/external-engine-integration.yml",
    ".github/workflows/meta-qualification.yml",
    ".github/workflows/xmage-full-game-conformance.yml",
    ".github/workflows/xmage-real-4p-smoke.yml",
)

# G1: these resolve the live pin from the manifest and must not restate it.
MANIFEST_PIN_READERS = (
    "scripts/bootstrap_engine_linux.sh",
    "scripts/bootstrap_engine_windows.ps1",
    "scripts/run_external_full_game_conformance.py",
    "scripts/run_real_deck_gate.py",
    "scripts/run_real_4p_full_game_smoke.py",
    "tests/unit/test_xmage_full_game.py",
    "tests/unit/test_xmage_compatibility_provider.py",
    "tests/unit/test_xmage_variable_player.py",
    "tests/unit/test_ws223_cardinality_regression.py",
)


def _manifest() -> dict:
    return json.loads((REPO_ROOT / "config/rules_engines.json").read_text())


def _lock() -> dict:
    return json.loads((REPO_ROOT / SUCCESSOR_LOCK).read_text())


def test_live_pin_is_the_successor_candidate() -> None:
    primary = _manifest()["primary_engine"]
    assert primary["commit"] == CURRENT_PIN
    assert primary["source_archive"].endswith(f"/{CURRENT_PIN}.tar.gz")
    assert primary["provider"] == "xmage"


def test_selection_truth_unchanged() -> None:
    cfg = _manifest()
    assert cfg["provider_decision"] == "NO_PROVIDER_READY"
    assert cfg["current_runtime"]["provider_selected"] is False
    assert cfg["current_runtime"]["production_provider"] is None


def test_successor_lock_binds_the_candidate_its_donors_and_the_prior_pin() -> None:
    lock = _lock()
    assert lock["new_live_pin"]["commit"] == CURRENT_PIN
    assert lock["new_live_pin"]["tree"] == CURRENT_TREE
    assert lock["new_live_pin"]["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert {donor["finding"] for donor in lock["donors"]} == {"F-43", "F-44", "F-45"}
    for donor in lock["donors"]:
        assert len(donor["head"]) == 40, donor
    assert lock["native_qualification"]["full_mage_tests"]["failures"] == 0
    assert lock["native_qualification"]["full_mage_tests"]["errors"] == 0
    assert lock["native_qualification"]["full_mage_tests"]["commit"] == CURRENT_PIN
    assert lock["rules_core_change_against_prior_pin"]["main_source_files"] == [
        "Mage/src/main/java/mage/game/GameImpl.java",
        "Mage/src/main/java/mage/game/combat/CombatGroup.java",
        "Mage/src/main/java/mage/players/PlayerImpl.java",
    ]
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_all_active_literal_pin_consumers_migrated() -> None:
    for rel in ACTIVE_LITERAL_CONSUMERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN in text, rel
        assert PRIOR_PIN not in text, rel


def test_manifest_pin_readers_restate_no_pin() -> None:
    for rel in MANIFEST_PIN_READERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN not in text, rel
        assert PRIOR_PIN not in text, rel
        assert "canonical_xmage_engine_pin" in text or "--provider xmage" in text, rel


def test_prior_locks_and_wsr22_boundary_stay_historical() -> None:
    from commander_lab.qualification.current_boundary import source_lock

    assert source_lock.XMAGE_CANDIDATE_COMMIT == WSR22_PIN
    prior = json.loads(
        (
            REPO_ROOT
            / "qualification/xmage-mp-candidate-repin-v2-20260930/SUCCESSOR_SOURCE_LOCK.json"
        ).read_text()
    )
    assert prior["new_live_pin"]["commit"] == PRIOR_PIN
    note = _manifest()["authority_note"]["known_stale_pointers"]
    assert f"Prior canonical xmage pin {PRIOR_PIN}" in note
    assert f"Canonical xmage pin is now {CURRENT_PIN}" in note
