"""Successor guard for the 2026-10-17 XMage candidate repin (v8).

The live XMage pin is the head commit of moeendres-png/mage#61 (348b37db), two
commits on the v7 pin (16e57239). It enables seven Secrets of Strixhaven prepare
creatures, gives Coercive Impetus +1/+1 and fixes the lifetime of the prepare
spell copy of a creature that enters prepared (``BecomePreparedSourceEffect``
linked the copy with a zone change counter one too low). No other Rules
behaviour and no other card data change.

The pin is a real commit that stays reachable as the second parent of the
mage#61 merge, so it does not change when that pull request merges.

Native qualification is bound to the fork ``maven.yml`` run on the exact
commit. The Lab ``bridge_suite`` is COMPLETE only with an Actions run, its job
and an artifact digest; a local run is LOCAL_OBSERVED and carries no CI-level
credit. NOT_RUN, PENDING or LOCAL_OBSERVED never counts as PASS.

The prior pin (16e57239, successor lock v7) stays historical. The Owner-signed
Architecture Freeze stays bound to b479fe74; current_qualification does not
move with the pin: it moves only when PB-03 runs on the Lab main merge commit
of this repin, AF11 is re-adjudicated for the new pin and the freeze record is
re-assembled.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "348b37db5cf64f4ed503e8d37b776d5edc70e6d5"
CURRENT_TREE = "f62bfea3d215441c568baa8ff9878597a60979bc"
PRIOR_PIN = "16e57239e0738925369b704fd7fdd083b7d5024b"
PRIOR_TREE = "7f751d05b0e8351d7cf8bd45f362c8e621c961ef"
PIN_PARENT = "d809b5a0f6c0121c84a487e959730209276b3243"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = "qualification/xmage-sos-prepare-repin-v8-20261017/SUCCESSOR_SOURCE_LOCK.json"
PRIOR_LOCKS = (
    "qualification/xmage-lazy-playable-copy-repin-v7-20261016/SUCCESSOR_SOURCE_LOCK.json",
)
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
EPOCH_ROOT = "qualification/current-boundary-epochs"

ENGINE_FILES = (
    "Mage.Sets/src/mage/cards/c/CoerciveImpetus.java",
    "Mage.Sets/src/mage/sets/SecretsOfStrixhaven.java",
    "Mage/src/main/java/mage/abilities/effects/common/BecomePreparedSourceEffect.java",
)

# Consumers that cannot read the manifest (workflow YAML env, Java constants)
# or are the deliberate pin-authority guards. A repin edits only these.
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


def _live_pin() -> str:
    manifest = json.loads((REPO_ROOT / "config/rules_engines.json").read_text())
    return manifest["primary_engine"]["commit"]


# This file proves the 2026-10-17 repin EVENT. Its current-pin assertions hold only while
# this repin's pin is live; after a later forward repin they are superseded by that repin's
# successor guard (tests/qualification/test_xmage_upstream_update_repin_v9_20261020.py)
# and are skipped, never rewritten. Its historical assertions stay active.
superseded_by_later_repin = pytest.mark.skipif(
    _live_pin() != CURRENT_PIN,
    reason=(
        "superseded: live XMage pin moved forward "
        "(see test_xmage_upstream_update_repin_v9_20261020.py)"
    ),
)


def _manifest() -> dict:
    return json.loads((REPO_ROOT / "config/rules_engines.json").read_text())


def _lock() -> dict:
    return json.loads((REPO_ROOT / SUCCESSOR_LOCK).read_text())


@superseded_by_later_repin
def test_live_pin_is_the_successor_candidate() -> None:
    primary = _manifest()["primary_engine"]
    assert primary["commit"] == CURRENT_PIN
    assert primary["source_archive"].endswith(f"/{CURRENT_PIN}.tar.gz")
    assert primary["provider"] == "xmage"


def test_selection_truth_unchanged() -> None:
    cfg = _manifest()
    assert cfg["provider_decision"] == "XMAGE_SELECTED"
    assert cfg["current_runtime"]["provider_selected"] is True
    assert cfg["current_runtime"]["production_provider"] == "xmage"


@superseded_by_later_repin
def test_successor_lock_binds_the_candidate_its_donor_and_the_prior_pin() -> None:
    lock = _lock()
    pin = lock["new_live_pin"]
    assert pin["commit"] == CURRENT_PIN
    assert pin["tree"] == CURRENT_TREE
    assert pin["parents"] == [PIN_PARENT]
    assert pin["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["tree"] == PRIOR_TREE
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    assert [d["pr"] for d in lock["donors"]] == ["moeendres-png/mage#61"]
    assert lock["donors"][0]["head"] == CURRENT_PIN
    lineage = lock["lineage"]
    assert lineage["prior_pin"] == {"commit": PRIOR_PIN, "tree": PRIOR_TREE}
    assert lineage["final_integrated_candidate"]["commit"] == CURRENT_PIN
    assert lineage["final_integrated_candidate"]["tree"] == CURRENT_TREE
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_engine_delta_is_the_declared_files() -> None:
    delta = _lock()["engine_delta"]
    # A list of path/blob objects, not a path -> blob map: a "SecretsOf..." key next to a
    # 40-hex value is flagged by the broad secret scan as a generic API key.
    files = delta["engine_module_files"]
    assert tuple(sorted(item["path"] for item in files)) == tuple(sorted(ENGINE_FILES))
    assert all(len(item["blob"]) == 40 for item in files)
    assert delta["dependency_change"] is False
    assert delta["build_files_changed"] == []


def test_native_run_is_pending_or_binds_the_exact_pin() -> None:
    lock = _lock()
    native = lock["native_qualification"]["full_mage_tests"]
    verify = lock["native_qualification"]["mage_verify"]
    assert native["commit"] == CURRENT_PIN
    if native["status"] == "PENDING":
        # PENDING carries no counts and no credit; NOT_RUN != PASS.
        assert not {"run", "run_id", "job", "failures", "errors", "skipped"} & set(native)
        assert verify["result"] == "PENDING"
        return
    assert native["status"] == "COMPLETE"
    assert native["run_id"] and native["job"]
    assert native["failures"] == 0 and native["errors"] == 0
    assert native["run"] >= 7189
    assert verify["result"].startswith("FAIL (pre-existing")
    assert "15 errors" in verify["detail"] and "set errors: 3" in verify["detail"]


def test_lab_bridge_suite_status_is_honest() -> None:
    lock = _lock()
    lab = lock["lab_runtime_qualification"]
    suite = lab["bridge_suite"]
    assert suite["status"] in {"PENDING", "LOCAL_OBSERVED", "COMPLETE"}
    if suite["status"] != "COMPLETE":
        # No Actions run, no CI-level credit: the lock stays PIN_MOVED_LAB_EVIDENCE_PENDING.
        assert lock["status"] == "PIN_MOVED_LAB_EVIDENCE_PENDING"
        assert lab["installed_artifacts_commit"] is None and not lab["installed_artifacts"]
        assert not {"actions_run", "job", "artifact"} & set(suite)
        return
    assert lock["status"] == "EVIDENCE_BOUND"
    assert suite["actions_run"] and suite["job"]
    assert len(suite["artifact"]["zip_sha256"]) == 64
    assert lab["installed_artifacts_commit"] == CURRENT_PIN
    assert suite["failures"] == 0 and suite["errors"] == 0
    assert f"XMAGE_COMMIT={CURRENT_PIN[:8]}" in suite["command"]
    assert set(lab["installed_artifacts"]) == {"org.mage:mage:1.4.61", "org.mage:mage-sets:1.4.61"}
    for digest in lab["installed_artifacts"].values():
        assert len(digest.removeprefix("sha256 ")) == 64


@superseded_by_later_repin
def test_signed_freeze_and_current_qualification_do_not_move_with_the_pin() -> None:
    freeze = _manifest()["architecture_freeze"]
    assert freeze["status"] == "CLAIMED"
    assert freeze["engine_commit"] == FREEZE_PIN
    assert freeze["engine_artifact_sha256"] == FREEZE_ARTIFACT_SHA256
    assert freeze["evidence_epoch"] == FREEZE_EPOCH
    # current_qualification lags the live pin until PB-03 on the Lab main merge
    # commit of this repin is sealed and the freeze record is re-assembled.
    assert freeze["current_qualification"]["engine_commit"] in (PRIOR_PIN, CURRENT_PIN)


def test_current_boundary_requires_requalification() -> None:
    lock = _lock()
    assert lock["current_boundary"]["status"] == "REQUALIFICATION_REQUIRED"
    root = REPO_ROOT / EPOCH_ROOT
    for path in sorted(root.glob("*/PB03_RUNTIME_EXECUTION.json")):
        runtime = json.loads(path.read_text())
        if runtime.get("candidate_commit") != CURRENT_PIN:
            continue
        assert (path.parent / "CURRENT_BOUNDARY_SHA256SUMS").is_file(), path.parent.name
        assert path.parent.name.startswith(runtime["runner_commit"][:12]), path.parent.name


@superseded_by_later_repin
def test_all_active_literal_pin_consumers_migrated() -> None:
    for rel in ACTIVE_LITERAL_CONSUMERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN in text, rel
        assert PRIOR_PIN not in text, rel


@superseded_by_later_repin
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
