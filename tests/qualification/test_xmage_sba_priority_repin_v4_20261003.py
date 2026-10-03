"""Successor guard for the 2026-10-03 XMage candidate repin (v4).

The live XMage pin is the multiplayer candidate branch advanced by the CR 117.5 /
800.4a priority repair: a player eliminated by the state-based actions checked
just before it would receive priority no longer receives it, and priority moves
on to the next player still in the game (mage#41, a patch-identical port of the
master fix mage#40; Lab #507). The prior pin (37e4df6c, successor locks v3) stays
historical: this repin opens a new successor epoch, it does not relabel earlier
evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
CURRENT_TREE = "1ff64c794b1f992a8596c0b1b9952055520ccd10"
DONOR_HEAD = "8af3d6181ac0050002c65fa3f84997c786c5cb34"
MASTER_FIX = "6a2422d77a"
PRIOR_PIN = "37e4df6c914f1e189e24f0ef59fa91734c922436"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = "qualification/xmage-sba-priority-repin-v4-20261003/SUCCESSOR_SOURCE_LOCK.json"
PRIOR_LOCKS = (
    "qualification/xmage-mp-candidate-repin-v3-20261001/SUCCESSOR_SOURCE_LOCK.json",
    "qualification/xmage-f43-f44-f45-repin-v3-20261001/SUCCESSOR_SOURCE_LOCK.json",
)

# Consumers that cannot read the manifest (workflow YAML env, Java constants)
# or are the deliberate pin-authority guards (G1). A repin edits only these.
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


def test_successor_lock_binds_the_candidate_its_donor_and_the_prior_pin() -> None:
    lock = _lock()
    assert lock["new_live_pin"]["commit"] == CURRENT_PIN
    assert lock["new_live_pin"]["tree"] == CURRENT_TREE
    assert lock["new_live_pin"]["parents"] == [PRIOR_PIN, DONOR_HEAD]
    assert lock["new_live_pin"]["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    (donor,) = lock["donors"]
    assert donor["pr"] == "moeendres-png/mage#41"
    assert donor["head"] == DONOR_HEAD
    assert donor["master_fix"]["merge_commit"].startswith(MASTER_FIX)
    assert set(donor["patch_identity"]) == {
        "Mage/src/main/java/mage/game/GameImpl.java",
        "Mage.Tests/src/test/java/org/mage/test/cards/designations/MonarchTest.java",
        "Mage.Tests/src/test/java/org/mage/test/multiplayer/PriorityEliminationTest.java",
    }
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_native_and_lab_runs_bind_the_exact_pin() -> None:
    lock = _lock()
    native = lock["native_qualification"]["full_mage_tests"]
    assert native["commit"] == CURRENT_PIN
    assert native["failures"] == 0 and native["errors"] == 0
    assert native["run"] > 0
    assert "PriorityEliminationTest" in native["donor_regressions_in_run"]
    verify = lock["native_qualification"]["mage_verify"]
    assert verify["result"].startswith("FAIL (pre-existing")
    lab = lock["lab_runtime_qualification"]
    assert lab["installed_artifacts_commit"] == CURRENT_PIN
    assert lab["bridge_suite"]["failures"] == 0 and lab["bridge_suite"]["errors"] == 0
    # Tree identity is not commit identity: the donor head's runs are supporting
    # evidence under the donor's own commit, never the pin's.
    assert lock["lineage"]["donor_head"]["tree"] == CURRENT_TREE
    assert lock["lineage"]["donor_head"]["commit"] == DONOR_HEAD


def test_all_active_literal_pin_consumers_migrated() -> None:
    for rel in ACTIVE_LITERAL_CONSUMERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN in text, rel
        assert PRIOR_PIN not in text, rel


def test_prior_pin_stays_historical() -> None:
    from commander_lab.qualification.current_boundary import source_lock

    assert source_lock.XMAGE_CANDIDATE_COMMIT == WSR22_PIN
    for rel in PRIOR_LOCKS:
        prior = json.loads((REPO_ROOT / rel).read_text())
        assert prior["new_live_pin"]["commit"] == PRIOR_PIN, rel
    note = _manifest()["authority_note"]["known_stale_pointers"]
    assert f"Prior canonical xmage pin {PRIOR_PIN}" in note
    assert f"Canonical xmage pin is now {CURRENT_PIN}" in note
    assert SUCCESSOR_LOCK in note
