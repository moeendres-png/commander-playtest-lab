"""Successor guard for the 2026-10-11 XMage candidate repin (v5).

The live XMage pin is the multiplayer candidate branch advanced by the
deterministic commander-zone ask order (mage#57): when one owner has more than
one commander and they die in the same state-based-action check (Commander's
Rules 704.3 / 903.9a), the "move to the command zone?" questions are asked in
graveyard order and then, for the exile path, in name order, instead of the
identity-hash order a plain ``HashSet`` produced (Lab #720). The answers and
the game are unchanged; only the order of the questions was, and that order
made twin replay of an otherwise identical game produce two different semantic
transcripts.

Native qualification is bound to the exact-commit ``maven.yml`` run 38136235677
on 3cbf7741 (Mage.Tests 7042 run, 0 failures, 0 errors; Mage.Verify the same
pre-existing baseline FAIL as at b479fe74). The Lab ``bridge_suite`` is
bound to the XMage Full Game Conformance run 38142486874 against XMage built from
exactly 3cbf7741 (1067 run, 0 failures, 0 errors, 1 skipped). NOT_RUN != PASS.

The prior pin (b479fe74, successor lock v4) stays historical: this repin opens
a new successor epoch, it does not relabel earlier evidence. The Owner-signed
Architecture Freeze also stays bound to b479fe74 until PB-03 runs on the Lab
main merge commit of this repin and the freeze record is re-bound to the new
epoch.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "3cbf7741d29a2fe820725456b90f305f9f793ad1"
CURRENT_TREE = "94a9f78331cbb619fe1443ccf43088f7f193e120"
DONOR_HEAD = "69b33b3b80084e04f63323e7d4518117f1f71048"
PRIOR_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
PRIOR_TREE = "1ff64c794b1f992a8596c0b1b9952055520ccd10"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = (
    "qualification/xmage-commander-zone-order-repin-v5-20261011/SUCCESSOR_SOURCE_LOCK.json"
)
PRIOR_LOCKS = ("qualification/xmage-sba-priority-repin-v4-20261003/SUCCESSOR_SOURCE_LOCK.json",)
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
EPOCH_ROOT = "qualification/current-boundary-epochs"

DONOR_FILES = {
    "Mage/src/main/java/mage/game/GameImpl.java": "dbcfb71584f1c5a5c2b1941340eb8879b96fec5f",
    "Mage.Tests/src/test/java/org/mage/test/commander/multiplayer/"
    "CommanderZoneApnapTestBase.java": "9aee21c6e2977c2fb635b8bfd672099bcf5a29eb",
}
NATIVE_REGRESSION_CLASSES = (
    "CommanderZoneApnap3PTest",
    "CommanderZoneApnap4PTest",
    "CommanderZoneApnap5PTest",
    "CommanderZoneApnap6PTest",
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
    # The repin never changed selection; the Owner-signed Freeze and D5 did.
    assert cfg["provider_decision"] == "XMAGE_SELECTED"
    assert cfg["current_runtime"]["provider_selected"] is True
    assert cfg["current_runtime"]["production_provider"] == "xmage"


def test_successor_lock_binds_the_candidate_its_donor_and_the_prior_pin() -> None:
    lock = _lock()
    assert lock["new_live_pin"]["commit"] == CURRENT_PIN
    assert lock["new_live_pin"]["tree"] == CURRENT_TREE
    assert lock["new_live_pin"]["parents"] == [PRIOR_PIN, DONOR_HEAD]
    assert lock["new_live_pin"]["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["tree"] == PRIOR_TREE
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    (donor,) = lock["donors"]
    assert donor["pr"] == "moeendres-png/mage#57"
    assert donor["head"] == DONOR_HEAD
    assert donor["git_hash_object"] == DONOR_FILES
    assert all(len(blob) == 40 for blob in donor["git_hash_object"].values())
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}
    # The donor head and the integrated merge carry the same tree here: identity
    # is the commit, never the tree.
    assert lock["lineage"]["donor_head"]["tree"] == CURRENT_TREE
    assert lock["lineage"]["donor_head"]["commit"] == DONOR_HEAD
    assert lock["lineage"]["final_integrated_candidate"]["commit"] == CURRENT_PIN


def test_native_run_binds_the_exact_pin() -> None:
    lock = _lock()
    native = lock["native_qualification"]["full_mage_tests"]
    assert native["status"] == "COMPLETE"
    assert native["commit"] == CURRENT_PIN
    assert native["run_id"] == 38136235677
    assert native["failures"] == 0 and native["errors"] == 0
    assert (native["run"], native["skipped"]) == (7042, 125)
    for cls in NATIVE_REGRESSION_CLASSES:
        assert cls in native["donor_regressions_in_run"], cls
    verify = lock["native_qualification"]["mage_verify"]
    assert verify["result"].startswith("FAIL (pre-existing")
    assert "37141776698" in verify["detail"]


def test_lab_bridge_suite_binds_the_exact_pin() -> None:
    lab = _lock()["lab_runtime_qualification"]
    assert lab["installed_artifacts_commit"] == CURRENT_PIN
    suite = lab["bridge_suite"]
    assert suite["status"] == "COMPLETE"
    assert suite["failures"] == 0 and suite["errors"] == 0
    assert (suite["run"], suite["skipped"]) == (1067, 1)
    assert suite["actions_run"] == 38142486874
    assert suite["job"] == 114479045714
    assert f"XMAGE_COMMIT={CURRENT_PIN[:8]}" in suite["command"]
    assert len(suite["artifact"]["zip_sha256"]) == 64
    assert set(lab["installed_artifacts"]) == {"org.mage:mage:1.4.61", "org.mage:mage-sets:1.4.61"}
    for digest in lab["installed_artifacts"].values():
        assert len(digest.removeprefix("sha256 ")) == 64


def test_signed_freeze_stays_bound_to_the_prior_pin_until_pb03() -> None:
    """The Freeze is Owner-signed against b479fe74; a repin cannot re-bind it."""
    freeze = _manifest()["architecture_freeze"]
    assert freeze["status"] == "CLAIMED"
    assert freeze["engine_commit"] == PRIOR_PIN
    assert freeze["engine_artifact_sha256"] == FREEZE_ARTIFACT_SHA256
    assert freeze["evidence_epoch"] == FREEZE_EPOCH
    # The live pin has moved forward and the Freeze record has not. They agree
    # again only when PB-03 runs on the Lab main merge commit of this repin and
    # the freeze record is re-bound to the new epoch.
    assert freeze["engine_commit"] != _manifest()["primary_engine"]["commit"]


def test_current_boundary_requires_requalification() -> None:
    lock = _lock()
    assert lock["current_boundary"]["status"] == "REQUALIFICATION_REQUIRED"
    # No current-boundary epoch is bound to the new pin, and none may be
    # invented here: qualification credit for 3cbf7741 requires a PB-03 run.
    root = REPO_ROOT / EPOCH_ROOT
    bound = [
        path.parent.name
        for path in sorted(root.glob("*/PB03_RUNTIME_EXECUTION.json"))
        if json.loads(path.read_text()).get("candidate_commit") == CURRENT_PIN
    ]
    assert bound == []


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
        assert prior["new_live_pin"]["tree"] == PRIOR_TREE, rel
    note = _manifest()["authority_note"]["known_stale_pointers"]
    assert f"Prior canonical xmage pin {PRIOR_PIN}" in note
    assert f"Canonical xmage pin is now {CURRENT_PIN}" in note
    assert SUCCESSOR_LOCK in note
