"""Successor guard for the 2026-11-08 upstream-fixes repin (v15).

The live XMage pin is the head of the fork branch ``claude/trial-ue4-20261031``
(moeendres-png/mage, also the head of the candidate line): the v14 pin (2ec507b721, engine
1.4.62) plus twelve upstream XMage commits picked from the U-1 delta (ten engine and card fixes,
two Verify test fixes), the cancelled-payment fix (U-4), Guava 33.7.2-jre and jsoup 1.23.2, and
two adaptations of fork code to the picked fixes (Doomsday Confluence and Zinnia, the commander
plays-count restore test). Unlike v14 the pin changes two dependency versions in pom.xml; the
engine version stays 1.4.62.

Native qualification is bound to the fork ``maven.yml`` run on the exact commit: Mage.Tests and
Mage.Verify both pass there. The Lab ``bridge_suite`` is COMPLETE only with an Actions run, its
job and an artifact digest; a local run is LOCAL_OBSERVED and carries no CI-level credit.
NOT_RUN, PENDING or LOCAL_OBSERVED never counts as PASS.

The prior pins (769e6ebb, 456b0e22, 4da83f62, 90f5c4d3, 2ec507b7; successor locks v10 to v14)
stay historical. The Owner-signed Architecture Freeze stays bound to b479fe74;
current_qualification does not move with the pin: it moves only when PB-03 runs on the Lab main
merge commit of this repin, AF11 is re-adjudicated for the new pin and the epoch is sealed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "f4d12f6e8066203fba7aa38bd35ea3358117393d"
CURRENT_TREE = "a4e99a96c3da1bcaa3a7ff2ce33c576b9e3e4919"
PIN_PARENTS = [
    "dbafa37ab24b88114a9fd78a71d4903da7def5f8",  # Doomsday Confluence and Zinnia adaptation
]
PRIOR_PIN = "2ec507b721ac04834eaa4d553b494681c46d996f"
PRIOR_TREE = "35c73726235ddc9897b19fa7b28df038b7a5c196"
V12_PIN = "4da83f6267907798e5527c3e5f8a0bd3579ff993"
V12_TREE = "64106e3ce6f537bc0f3fda83910abb569b23e34b"
V13_PIN = "90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e"
V13_TREE = "9d6c810ab1266598fc436298f7caa49668c4b2bc"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
ENGINE_VERSION = "1.4.62"
SUCCESSOR_LOCK = "qualification/xmage-upstream-fixes-repin-v15-20261108/SUCCESSOR_SOURCE_LOCK.json"
PRIOR_LOCKS = (
    "qualification/xmage-determinism-line-repin-v10-20261020/SUCCESSOR_SOURCE_LOCK.json",
    "qualification/xmage-lazy-triggers-repin-v11-20261021/SUCCESSOR_SOURCE_LOCK.json",
    "qualification/xmage-order-collections-repin-v12-20261022/SUCCESSOR_SOURCE_LOCK.json",
    "qualification/xmage-precon-commander-cards-repin-v13-20261023/SUCCESSOR_SOURCE_LOCK.json",
    "qualification/xmage-precon-commander-cards-2-repin-v14-20261029/SUCCESSOR_SOURCE_LOCK.json",
)
PRIOR_LOCK_PINS = {
    PRIOR_LOCKS[0]: (
        "769e6ebbfdf1bd91eb357f63e0e6a3e848ed24b2",
        "93fc5e5dc26cb18027ea2185db75eca008160288",
    ),
    PRIOR_LOCKS[1]: (
        "456b0e227cc09a90e9d485b9d932f3717ef9e2be",
        "e111416966fa9a2acaf2902ff5ea3c9efad635e8",
    ),
    PRIOR_LOCKS[2]: (V12_PIN, V12_TREE),
    PRIOR_LOCKS[3]: (V13_PIN, V13_TREE),
    PRIOR_LOCKS[4]: (PRIOR_PIN, PRIOR_TREE),
}
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
PRIOR_EPOCH = "qualification/current-boundary-epochs/cd23d329ce5a-9490ba04fa16"
EPOCH_ROOT = "qualification/current-boundary-epochs"

ENGINE_COMMITS = (
    "895b462c7c3490a5448e1d09a41d4943ac50a084",  # tests: skip flagging BCHR set missing
    "15dd4eb62fba81d4f2ab91e698b82fbf33f1b6ed",  # tests: fixed verify
    "95e8846fc50eba611760f313da38ad3724fcd7d2",  # Ramses and Blood Tyrant loss triggers
    "6364225d6e664182b6bb71cfd0b2d8569936fde9",  # LKI of phased-out damage sources
    "37736cb1b32e3a0cd326cf386c983e3a3aef1590",  # LKI in the remaining battlefield lookups
    "d6395782d8eb6fd846ca9d9e512e4a9bca2885a4",  # redirect effects
    "24fdc41563ff50da6d2a8d3909af0d8a8747fe8b",  # "this spell can't be copied" never applying
    "b2fde46f78a7c21167ad5457706dafa374daa233",  # CantBeCopiedSourceEffect spell or LKI stack
    "57bd6e8385d6f42a12b801eeb3abfb6984d8071e",  # Irma copiable values
    "e75fb79ceefe8affe5eab05827699138a72ecef0",  # Dark Impostor zcc
    "c2c9cb8bf606da31ae54c7cd2fd050dc0cf4e6cd",  # Heart-Piercer Manticore reflexive trigger
    "d9fe8e85ddca5e83d6a7f590801c9bd20d0ce69e",  # commander damage info on double-faced permanents
    "f8db5f939478d26bd4b8fd7c5138d868fdf102e3",  # Guava 33.7.2-jre, jsoup 1.23.2
    "2db0c5e351bd321eeac9a23b71ae41c8333a9920",  # cancelled payment keeps activation status (U-4)
    "dbafa37ab24b88114a9fd78a71d4903da7def5f8",  # Doomsday Confluence and Zinnia adaptation
    CURRENT_PIN,  # CommanderPlaysCountStateRestoreTest adaptation
)

# Cards the picked fixes and the two adaptations touch.
CARDS = (
    "b/BloodTyrant",
    "c/CelestialReunion",
    "d/DarkImpostor",
    "d/DoomsdayConfluence",
    "h/HeartPiercerManticore",
    "i/IrmaPartTimeMutant",
    "r/RamsesAssassinLord",
    "z/ZinniaValleysVoice",
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


# This file proves the 2026-11-08 upstream-fixes repin EVENT. Its current-pin assertions hold
# only while this repin's pin is live; after a later forward repin they are superseded by that
# repin's successor guard (the successor guard of the next repin) and are skipped,
# never rewritten. Its historical assertions stay active.
superseded_by_later_repin = pytest.mark.skipif(
    _live_pin() != CURRENT_PIN,
    reason="superseded: live XMage pin moved forward (see the next repin's successor guard)",
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
def test_successor_lock_binds_the_candidate_its_line_and_the_prior_pin() -> None:
    lock = _lock()
    pin = lock["new_live_pin"]
    assert pin["commit"] == CURRENT_PIN
    assert pin["tree"] == CURRENT_TREE
    assert pin["parents"] == PIN_PARENTS
    assert pin["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["tree"] == PRIOR_TREE
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    lineage = lock["lineage"]
    assert lineage["prior_pin"] == {"commit": PRIOR_PIN, "tree": PRIOR_TREE}
    assert lineage["candidate_line_head"]["commit"] == CURRENT_PIN
    assert lineage["final_integrated_candidate"]["commit"] == CURRENT_PIN
    assert lineage["final_integrated_candidate"]["tree"] == CURRENT_TREE
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_owner_go_is_recorded_with_its_scope() -> None:
    go = _lock()["owner_go"]
    assert "100_EMPFEHLUNGEN" in go["decision"]
    assert "2026-10-31" in go["decision"]
    assert "no history rewrite" in go["scope"]
    assert "no JIT" in go["scope"]


def test_engine_delta_names_the_commits_and_the_dependency_change() -> None:
    delta = _lock()["engine_delta"]
    assert tuple(item["commit"] for item in delta["commits"]) == ENGINE_COMMITS
    assert delta["commit_count"] == len(ENGINE_COMMITS) == 16
    assert all(len(item["blob"]) == 40 for item in delta["post_pin_edits"])
    edited = {item["path"] for item in delta["post_pin_edits"]}
    for card in CARDS:
        assert f"Mage.Sets/src/mage/cards/{card}.java" in edited, card
    assert "Mage.Verify/src/test/java/mage/verify/VerifyCardDataTest.java" in edited
    # this pin changes framework classes and two dependency versions; the lock must say so
    assert delta["engine_classes_changed"] is True
    assert any(path.startswith("Mage/") for path in edited)
    assert delta["dependency_change"] is True
    assert delta["build_files_changed"] == ["pom.xml"]
    assert "pom.xml" in edited
    note = delta["dependency_change_note"]
    assert "33.4.8-jre -> 33.7.2-jre" in note
    assert "1.21.2 -> 1.23.2" in note
    assert "H2" in note
    assert delta["version_change"]["from"] == delta["version_change"]["to"] == ENGINE_VERSION


def test_unrelated_patch_sets_are_declared_out_of_the_pin() -> None:
    not_in_pin = _lock()["not_in_pin"]
    assert any("0c0132a2ef" in item and "Muse" in item for item in not_in_pin)
    assert any("JIT" in item and "H2" in item for item in not_in_pin)


def test_native_run_binds_the_exact_pin_and_both_suites_pass() -> None:
    native = _lock()["native_qualification"]
    full = native["full_mage_tests"]
    verify = native["mage_verify"]
    assert full["commit"] == CURRENT_PIN
    assert full["status"] == "COMPLETE"
    assert full["run_id"] and full["job"] and full["job_id"]
    assert full["failures"] == 0 and full["errors"] == 0
    # the v14 pin ran 7586 tests; the picked fixes add to them, never remove any
    assert full["run"] >= 7586
    # unlike v14 the Verify suite is green now: the BCHR set skip and the verify fix are picked
    assert verify["result"] == "PASS"
    assert verify["failures"] == 0 and verify["errors"] == 0


def test_local_observations_carry_no_ci_credit() -> None:
    local = _lock()["local_observed"]
    assert local["status"].startswith("LOCAL_OBSERVED")
    assert "no CI-level credit" in local["status"]
    # the measured jar carried an earlier pin literal; the lock says so instead of hiding it
    assert "f8db5f9394" in local["jar"]


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
    assert set(lab["installed_artifacts"]) == {
        f"org.mage:mage:{ENGINE_VERSION}",
        f"org.mage:mage-sets:{ENGINE_VERSION}",
    }
    for digest in lab["installed_artifacts"].values():
        assert len(digest.removeprefix("sha256 ")) == 64


def test_engine_version_does_not_move_with_this_pin() -> None:
    provider = (
        REPO_ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java"
    ).read_text()
    assert f'ENGINE_VERSION = "{ENGINE_VERSION}"' in provider
    pom = (REPO_ROOT / "engine-bridge/pom.xml").read_text()
    assert f"<xmage.version>{ENGINE_VERSION}</xmage.version>" in pom
    launcher = (
        REPO_ROOT / "src/commander_lab/qualification/current_boundary/bridge_launcher.py"
    ).read_text()
    assert f'"maven_coordinates": "org.mage:mage:{ENGINE_VERSION}"' in launcher
    twins = (REPO_ROOT / "scripts/run_replay_twin_campaign.py").read_text()
    assert f'XMAGE_MAGE_JAR_NAME = "mage-{ENGINE_VERSION}.jar"' in twins


@superseded_by_later_repin
def test_signed_freeze_and_current_qualification_do_not_move_with_the_pin() -> None:
    freeze = _manifest()["architecture_freeze"]
    assert freeze["status"] == "CLAIMED"
    assert freeze["engine_commit"] == FREEZE_PIN
    assert freeze["engine_artifact_sha256"] == FREEZE_ARTIFACT_SHA256
    assert freeze["evidence_epoch"] == FREEZE_EPOCH
    # current_qualification lags the live pin until PB-03 on the Lab main merge
    # commit of this repin is sealed and the freeze record is re-assembled.
    current = freeze["current_qualification"]
    assert current["engine_commit"] in (PRIOR_PIN, CURRENT_PIN)
    if current["engine_commit"] == CURRENT_PIN:
        # Moving current_qualification onto the new pin needs a sealed epoch for it.
        epoch = REPO_ROOT / current["evidence_epoch"]
        runtime = json.loads((epoch / "PB03_RUNTIME_EXECUTION.json").read_text())
        assert runtime["candidate_commit"] == CURRENT_PIN
        assert (epoch / "CURRENT_BOUNDARY_SHA256SUMS").is_file()
    else:
        assert current["evidence_epoch"] == PRIOR_EPOCH


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
        commit, tree = PRIOR_LOCK_PINS[rel]
        assert prior["new_live_pin"]["commit"] == commit, rel
        assert prior["new_live_pin"]["tree"] == tree, rel
    note = _manifest()["authority_note"]["known_stale_pointers"]
    assert f"Prior canonical xmage pin {PRIOR_PIN}" in note
    assert f"Canonical xmage pin is now {CURRENT_PIN}" in note
    assert SUCCESSOR_LOCK in note
