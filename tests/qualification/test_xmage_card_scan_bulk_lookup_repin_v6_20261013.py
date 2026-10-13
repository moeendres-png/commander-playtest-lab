"""Successor guard for the 2026-10-13 XMage candidate repin (v6).

The live XMage pin is the multiplayer candidate branch advanced by the bulk card
scan (mage#58): CardScanner.scan tests which set cards are already stored with one
query for the set code and card number of every stored card instead of one query
per set card. That cost about 2 s of every bridge JVM start, and the Lab starts one
JVM per full game. No Rules behaviour changes: the stored-card test is the same.

Native qualification and the Lab bridge suite are bound to exact-commit runs on
e5030e84 in the successor lock once they have run; until then they are PENDING with
no result counts. NOT_RUN != PASS.

The prior pin (3cbf7741, successor lock v5) stays historical with its sealed
epochs. The Owner-signed Architecture Freeze stays bound to b479fe74 until PB-03
runs on the Lab main merge commit of this repin and the freeze record is re-bound.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "e5030e84687d612744ea413b522870cfb00f2f07"
CURRENT_TREE = "6686f951173905ba52199c02d81fba70764076fd"
DONOR_HEAD = "99b18b8f7281a1514ffab461d931a77bea7c7ba3"
PRIOR_PIN = "3cbf7741d29a2fe820725456b90f305f9f793ad1"
PRIOR_TREE = "94a9f78331cbb619fe1443ccf43088f7f193e120"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = (
    "qualification/xmage-card-scan-bulk-lookup-repin-v6-20261013/SUCCESSOR_SOURCE_LOCK.json"
)
PRIOR_LOCKS = (
    "qualification/xmage-commander-zone-order-repin-v5-20261011/SUCCESSOR_SOURCE_LOCK.json",
)
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
EPOCH_ROOT = "qualification/current-boundary-epochs"

DONOR_FILES = {
    "Mage/src/main/java/mage/cards/repository/CardRepository.java": (
        "0ef8d972040769ae0656020f0ac7ade2c8ee5383"
    ),
    "Mage/src/main/java/mage/cards/repository/CardScanner.java": (
        "e4ad727915a40b1a3e2cf8cafb1e91dad60b4987"
    ),
}

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
    assert donor["pr"] == "moeendres-png/mage#58"
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
    assert native["commit"] == CURRENT_PIN
    assert "workflow_dispatch" in native["command"]
    if native["status"] == "PENDING":
        # NOT_RUN != PASS: a pending run carries no result counts.
        assert not {"run", "failures", "errors", "skipped"} & set(native)
        return
    assert native["status"] == "COMPLETE"
    assert native["run_id"] == 38369967979
    assert native["failures"] == 0 and native["errors"] == 0
    assert (native["run"], native["skipped"]) == (7042, 125)
    verify = lock["native_qualification"]["mage_verify"]
    assert verify["result"].startswith("FAIL (pre-existing")
    assert "38136235677" in verify["detail"]


def test_lab_bridge_suite_binds_the_exact_pin() -> None:
    lab = _lock()["lab_runtime_qualification"]
    assert lab["installed_artifacts_commit"] == CURRENT_PIN
    suite = lab["bridge_suite"]
    assert f"XMAGE_COMMIT={CURRENT_PIN[:8]}" in suite["command"]
    if suite["status"] == "PENDING":
        assert not {"run", "failures", "errors", "skipped", "actions_run"} & set(suite)
        return
    assert suite["status"] == "COMPLETE"
    assert suite["failures"] == 0 and suite["errors"] == 0
    assert isinstance(suite["actions_run"], int)


def test_engine_identity_has_a_structural_signature() -> None:
    fingerprint = (
        REPO_ROOT / "engine-bridge/src/test/java/org/commanderlab/xmage/"
        "XmageCandidateEngineFingerprintTest.java"
    ).read_text()
    assert "findAllSetCodeAndCardNumberKeys" in fingerprint
    assert "loadedEngineCarriesTheBulkCardScan" in fingerprint


def test_signed_freeze_stays_bound_to_the_prior_pin_until_pb03() -> None:
    """The Freeze is Owner-signed against b479fe74; a repin cannot re-bind it."""
    freeze = _manifest()["architecture_freeze"]
    assert freeze["status"] == "CLAIMED"
    assert freeze["engine_commit"] == FREEZE_PIN
    assert freeze["engine_artifact_sha256"] == FREEZE_ARTIFACT_SHA256
    assert freeze["evidence_epoch"] == FREEZE_EPOCH
    # The live pin has moved forward and the Freeze record has not. They agree
    # again only when PB-03 runs on the Lab main merge commit of this repin and
    # the freeze record is re-bound to the new epoch.
    assert freeze["engine_commit"] != _manifest()["primary_engine"]["commit"]


def test_current_boundary_requires_requalification() -> None:
    lock = _lock()
    assert lock["current_boundary"]["status"] == "REQUALIFICATION_REQUIRED"
    # The lock itself never claims an epoch. An epoch for e5030e84 exists only as
    # a sealed PB-03 run, named after the Lab commit that ran it.
    root = REPO_ROOT / EPOCH_ROOT
    for path in sorted(root.glob("*/PB03_RUNTIME_EXECUTION.json")):
        runtime = json.loads(path.read_text())
        if runtime.get("candidate_commit") != CURRENT_PIN:
            continue
        assert (path.parent / "CURRENT_BOUNDARY_SHA256SUMS").is_file(), path.parent.name
        assert path.parent.name.startswith(runtime["runner_commit"][:12]), path.parent.name


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
