"""Successor guard for the 2026-10-16 XMage candidate repin (v7).

The live XMage pin is the head commit of moeendres-png/mage#60 (16e57239), one
commit on the v6 pin (38cb21a8). It changes only ``GameImpl.java``: a playable
calculation copy (``createSimulationForPlayableCalc``) shares the parent's game
cards and copies a card on its first read instead of copying every card up
front. No Rules behaviour and no card data change.

The pin is a real commit that stays reachable as the parent of the mage#60
merge, so it does not change when that pull request merges.

Native qualification (the fork ``maven.yml`` run on the exact commit) is
PENDING until its run is bound; NOT_RUN or PENDING never counts as PASS. The
Lab ``bridge_suite`` is bound only to a measured run against XMage built from
exactly the new pin.

The prior pin (38cb21a8, successor lock v6) stays historical. The Owner-signed
Architecture Freeze stays bound to b479fe74; current_qualification does not
move with the pin: it moves only when PB-03 runs on the Lab main merge commit
of this repin, AF11 is re-adjudicated for the new pin and the freeze record is
re-assembled.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "16e57239e0738925369b704fd7fdd083b7d5024b"
CURRENT_TREE = "7f751d05b0e8351d7cf8bd45f362c8e621c961ef"
PRIOR_PIN = "38cb21a85c4074b00ab226e625200a4feaf3462f"
PRIOR_TREE = "e6845ec795aeeae4ce5a229a9da6fb96bf51910a"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = (
    "qualification/xmage-lazy-playable-copy-repin-v7-20261016/SUCCESSOR_SOURCE_LOCK.json"
)
PRIOR_LOCKS = ("qualification/xmage-precon-coverage-repin-v6-20261013/SUCCESSOR_SOURCE_LOCK.json",)
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
EPOCH_ROOT = "qualification/current-boundary-epochs"

ENGINE_FILES = ("Mage/src/main/java/mage/game/GameImpl.java",)

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
    assert cfg["provider_decision"] == "XMAGE_SELECTED"
    assert cfg["current_runtime"]["provider_selected"] is True
    assert cfg["current_runtime"]["production_provider"] == "xmage"


def test_successor_lock_binds_the_candidate_its_donor_and_the_prior_pin() -> None:
    lock = _lock()
    pin = lock["new_live_pin"]
    assert pin["commit"] == CURRENT_PIN
    assert pin["tree"] == CURRENT_TREE
    assert pin["parents"] == [PRIOR_PIN]
    assert pin["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["tree"] == PRIOR_TREE
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    assert [d["pr"] for d in lock["donors"]] == ["moeendres-png/mage#60"]
    assert lock["donors"][0]["head"] == CURRENT_PIN
    lineage = lock["lineage"]
    assert lineage["prior_pin"] == {"commit": PRIOR_PIN, "tree": PRIOR_TREE}
    assert lineage["final_integrated_candidate"]["commit"] == CURRENT_PIN
    assert lineage["final_integrated_candidate"]["tree"] == CURRENT_TREE
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_engine_delta_is_one_declared_file() -> None:
    delta = _lock()["engine_delta"]
    assert tuple(sorted(delta["engine_module_files"])) == ENGINE_FILES
    assert all(len(blob) == 40 for blob in delta["engine_module_files"].values())
    assert delta["dependency_change"] is False
    assert delta["build_files_changed"] == []


def test_native_run_is_pending_or_binds_the_exact_pin() -> None:
    lock = _lock()
    native = lock["native_qualification"]["full_mage_tests"]
    assert native["commit"] == CURRENT_PIN
    if native["status"] == "PENDING":
        # PENDING carries no counts and no credit; NOT_RUN != PASS.
        assert not {"run", "run_id", "job", "failures", "errors", "skipped"} & set(native)
        assert lock["status"] == "PIN_MOVED_LAB_EVIDENCE_PENDING"
        assert lock["native_qualification"]["mage_verify"]["result"] == "PENDING"
        return
    assert native["status"] == "COMPLETE"
    assert native["failures"] == 0 and native["errors"] == 0
    assert native["run"] > 7042


def test_lab_bridge_suite_is_pending_or_binds_the_exact_pin() -> None:
    lock = _lock()
    lab = lock["lab_runtime_qualification"]
    suite = lab["bridge_suite"]
    if suite["status"] == "PENDING":
        assert lock["status"] == "PIN_MOVED_LAB_EVIDENCE_PENDING"
        assert lab["installed_artifacts_commit"] is None and not lab["installed_artifacts"]
        assert not {"run", "failures", "errors", "skipped", "actions_run"} & set(suite)
        return
    assert suite["status"] == "COMPLETE"
    assert lab["installed_artifacts_commit"] == CURRENT_PIN
    assert suite["failures"] == 0 and suite["errors"] == 0
    assert CURRENT_PIN in suite["command"]
    assert set(lab["installed_artifacts"]) == {"org.mage:mage:1.4.61", "org.mage:mage-sets:1.4.61"}
    for digest in lab["installed_artifacts"].values():
        assert len(digest.removeprefix("sha256 ")) == 64


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
