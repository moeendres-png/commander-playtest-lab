"""Successor guard for the 2026-10-13 XMage candidate repin (v6).

The live XMage pin is the multiplayer candidate branch advanced by two fork
merges since repin v5 (3cbf7741):

* moeendres-png/mage#58 (merge e5030e84): the card scanner checks the stored set
  cards with one repository query instead of one query per card. Start-up only;
  no Rules behaviour changes.
* moeendres-png/mage#59 (merge 38cb21a8): precon card coverage. 62 cards
  the Owner's precons and collection need are added or enabled, each with its
  own Mage.Tests test, plus the engine hooks those cards need:
  ``RequirementEffect.mustAttackDefenders`` (a creature must attack one of
  several defenders), a per-effect ``Combat.checkAttackRequirements`` (a
  requirement naming a defender who has left the game no longer cancels the
  other creatures' requirements, CR 800.4a), a ``CONNIVED`` game event with the
  trigger that listens for it, and one new ``MageIdentifier`` value.

Native qualification is bound to the exact-commit ``maven.yml`` run on the new
pin; Mage.Verify carries the same pre-existing baseline failures as at
3cbf7741 and e5030e84. The Lab ``bridge_suite`` is bound to an XMage Full Game
Conformance run against XMage built from exactly the new pin. NOT_RUN != PASS.

The prior pin (3cbf7741, successor lock v5) stays historical: this repin opens
a new successor epoch, it does not relabel earlier evidence. The Owner-signed
Architecture Freeze stays bound to b479fe74; current_qualification stays on
3cbf7741 until PB-03 runs on the Lab main merge commit of this repin, AF11 is
re-adjudicated for the new pin and the freeze record is re-assembled.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "38cb21a85c4074b00ab226e625200a4feaf3462f"
CURRENT_TREE = "e6845ec795aeeae4ce5a229a9da6fb96bf51910a"
SCANNER_MERGE = "e5030e84687d612744ea413b522870cfb00f2f07"
SCANNER_TREE = "6686f951173905ba52199c02d81fba70764076fd"
DONOR_HEAD = "6cc9016757a7d07229e03b96f1a8b8d410729b17"
PRIOR_PIN = "3cbf7741d29a2fe820725456b90f305f9f793ad1"
PRIOR_TREE = "94a9f78331cbb619fe1443ccf43088f7f193e120"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
SUCCESSOR_LOCK = "qualification/xmage-precon-coverage-repin-v6-20261013/SUCCESSOR_SOURCE_LOCK.json"
PRIOR_LOCKS = (
    "qualification/xmage-commander-zone-order-repin-v5-20261011/SUCCESSOR_SOURCE_LOCK.json",
)
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
EPOCH_ROOT = "qualification/current-boundary-epochs"

ENGINE_FILES = (
    "Mage/src/main/java/mage/MageIdentifier.java",
    "Mage/src/main/java/mage/abilities/common/ConnivesCreatureYouControlTriggeredAbility.java",
    "Mage/src/main/java/mage/abilities/effects/RequirementEffect.java",
    "Mage/src/main/java/mage/abilities/effects/keyword/ConniveSourceEffect.java",
    "Mage/src/main/java/mage/cards/repository/CardRepository.java",
    "Mage/src/main/java/mage/cards/repository/CardScanner.java",
    "Mage/src/main/java/mage/game/combat/Combat.java",
    "Mage/src/main/java/mage/game/events/GameEvent.java",
)
NATIVE_REGRESSION_CLASSES = (
    "MustAttackLeftPlayerTest",
    "KangDynastyMultiplayerTest",
    "GalactusDevourerOfWorldsMultiplayerTest",
    "SilverSurferGalactussHeraldMultiplayerTest",
    "DurnanOfTheYawningPortalTest",
    "ShuriTheBlackPantherTest",
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


def _live_pin() -> str:
    manifest = json.loads((REPO_ROOT / "config/rules_engines.json").read_text())
    return manifest["primary_engine"]["commit"]


# This file proves the 2026-10-13 repin EVENT. Its current-pin assertions hold only while
# this repin's pin is live; after a later forward repin they are superseded by that repin's
# successor guard (tests/qualification/test_xmage_lazy_playable_copy_repin_v7_20261016.py)
# and are skipped, never rewritten. Its historical assertions stay active.
superseded_by_later_repin = pytest.mark.skipif(
    _live_pin() != CURRENT_PIN,
    reason=(
        "superseded: live XMage pin moved forward "
        "(see test_xmage_lazy_playable_copy_repin_v7_20261016.py)"
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
def test_successor_lock_binds_the_candidate_its_donors_and_the_prior_pin() -> None:
    lock = _lock()
    pin = lock["new_live_pin"]
    assert pin["commit"] == CURRENT_PIN
    assert pin["tree"] == CURRENT_TREE
    assert pin["parents"] == [SCANNER_MERGE, DONOR_HEAD]
    assert pin["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["tree"] == PRIOR_TREE
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    assert [d["pr"] for d in lock["donors"]] == ["moeendres-png/mage#58", "moeendres-png/mage#59"]
    lineage = lock["lineage"]
    assert lineage["prior_pin"]["commit"] == PRIOR_PIN
    assert lineage["scanner_merge"] == {
        "commit": SCANNER_MERGE,
        "tree": SCANNER_TREE,
        "parents": [PRIOR_PIN, "99b18b8f7281a1514ffab461d931a77bea7c7ba3"],
    }
    assert lineage["donor_head"]["commit"] == DONOR_HEAD
    # The donor head already carries the scanner merge, so the integrated merge
    # and the donor head share a tree: identity is the commit, never the tree.
    assert lineage["donor_head"]["tree"] == CURRENT_TREE
    assert lineage["final_integrated_candidate"]["commit"] == CURRENT_PIN
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_engine_delta_is_declared_file_by_file() -> None:
    delta = _lock()["engine_delta"]
    assert tuple(sorted(delta["engine_module_files"])) == ENGINE_FILES
    assert all(len(blob) == 40 for blob in delta["engine_module_files"].values())
    assert delta["dependency_change"] is False
    assert delta["build_files_changed"] == []


def test_native_run_binds_the_exact_pin() -> None:
    lock = _lock()
    native = lock["native_qualification"]["full_mage_tests"]
    assert native["status"] == "COMPLETE"
    assert native["commit"] == CURRENT_PIN
    assert native["failures"] == 0 and native["errors"] == 0
    assert native["run"] > 7042
    for cls in NATIVE_REGRESSION_CLASSES:
        assert cls in native["donor_regressions_in_run"], cls
    verify = lock["native_qualification"]["mage_verify"]
    assert verify["result"].startswith("FAIL (pre-existing")
    assert "38369967979" in verify["detail"]


def test_lab_bridge_suite_binds_the_exact_pin() -> None:
    lock = _lock()
    lab = lock["lab_runtime_qualification"]
    suite = lab["bridge_suite"]
    if suite["status"] == "PENDING":
        # PENDING carries no counts and no credit; NOT_RUN != PASS.
        assert lock["status"] == "PIN_MOVED_LAB_EVIDENCE_PENDING"
        assert lab["installed_artifacts_commit"] is None and not lab["installed_artifacts"]
        assert not {"run", "failures", "errors", "skipped", "actions_run"} & set(suite)
        return
    assert lock["status"] == "EVIDENCE_BOUND"
    assert lab["installed_artifacts_commit"] == CURRENT_PIN
    assert suite["status"] == "COMPLETE"
    assert suite["failures"] == 0 and suite["errors"] == 0
    assert f"XMAGE_COMMIT={CURRENT_PIN[:8]}" in suite["command"]
    assert len(suite["artifact"]["zip_sha256"]) == 64
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
