"""Successor guard for the 2026-10-22 XMage order-collections repin (v12).

The live XMage pin is the merge head of the fork branch ``claude/project-thread-5hvqry``
(moeendres-png/mage): the v11 pin (456b0e22, engine 1.4.62) plus the creation of the tokens of
one event in the order they were given (mage#68), insertion-order collections where objects
without a hashCode decided an order a player sees (mage#70) and the fixed player order of 18
cards (mage#69). The same seed now replays the same game in pods that gave two or more hashes
on v11 (Wurmcoil Engine's Wurms in seed 22 pod 004, Wave of Vitriol and From the Ashes in plan
seeds 24, 27 and 30), while 46 of 46 precon pods and 36 of 36 real-pod seeds that were stable
keep their hashes. The perf port (0c0132a2ef) stays out of the pin because it changes option
text. The engine version stays 1.4.62.

Native qualification is bound to the fork ``maven.yml`` run on the exact commit. The Lab
``bridge_suite`` is COMPLETE only with an Actions run, its job and an artifact digest; a local
run is LOCAL_OBSERVED and carries no CI-level credit. NOT_RUN, PENDING or LOCAL_OBSERVED never
counts as PASS.

The prior pins (769e6ebb, successor lock v10; 456b0e22, successor lock v11) stay historical.
The Owner-signed Architecture Freeze stays bound to b479fe74; current_qualification does not
move with the pin: it moves only when PB-03 runs on the Lab main merge commit of this repin,
AF11 is re-adjudicated for the new pin and the epoch is sealed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "4da83f6267907798e5527c3e5f8a0bd3579ff993"
CURRENT_TREE = "64106e3ce6f537bc0f3fda83910abb569b23e34b"
PIN_PARENTS = [
    "4da49dc221679a2b2776df829bbd1c43e0af3bdd",  # mage#70 head (carries the token commit of mage#68)
    "dd71626b390f179cf392acc654470924de5e3b6b",  # mage#69 head (18 cards, player order)
]
PRIOR_PIN = "456b0e227cc09a90e9d485b9d932f3717ef9e2be"
PRIOR_TREE = "e111416966fa9a2acaf2902ff5ea3c9efad635e8"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
ENGINE_VERSION = "1.4.62"
SUCCESSOR_LOCK = (
    "qualification/xmage-order-collections-repin-v12-20261022/SUCCESSOR_SOURCE_LOCK.json"
)
PRIOR_LOCKS = (
    "qualification/xmage-determinism-line-repin-v10-20261020/SUCCESSOR_SOURCE_LOCK.json",
    "qualification/xmage-lazy-triggers-repin-v11-20261021/SUCCESSOR_SOURCE_LOCK.json",
)
PRIOR_LOCK_PINS = {
    PRIOR_LOCKS[0]: (
        "769e6ebbfdf1bd91eb357f63e0e6a3e848ed24b2",
        "93fc5e5dc26cb18027ea2185db75eca008160288",
    ),
    PRIOR_LOCKS[1]: (PRIOR_PIN, PRIOR_TREE),
}
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
PRIOR_EPOCH = "qualification/current-boundary-epochs/dac1ed64937a-187ab54c36bb"
EPOCH_ROOT = "qualification/current-boundary-epochs"

ENGINE_COMMITS = (
    "537ce62cc1d75486abfcda5e14b94117d0adec83",  # tokens of one event in the order given (mage#68)
    "4da49dc221679a2b2776df829bbd1c43e0af3bdd",  # insertion-order collections (mage#70)
    "dd71626b390f179cf392acc654470924de5e3b6b",  # player order in 18 cards (mage#69)
    CURRENT_PIN,  # merge of the player-order branch
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


# This file proves the 2026-10-22 order-collections repin EVENT. Its current-pin assertions hold
# only while this repin's pin is live; after a later forward repin they are superseded by that
# repin's successor guard (test_xmage_precon_commander_cards_repin_v13_20261023.py) and are skipped,
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
    assert lineage["candidate_line_head"]["commit"] == PRIOR_PIN
    assert lineage["final_integrated_candidate"]["commit"] == CURRENT_PIN
    assert lineage["final_integrated_candidate"]["tree"] == CURRENT_TREE
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_engine_delta_names_the_commits_and_no_dependency_change() -> None:
    delta = _lock()["engine_delta"]
    assert tuple(item["commit"] for item in delta["commits"]) == ENGINE_COMMITS
    assert delta["commit_count"] == 4
    assert all(len(item["blob"]) == 40 for item in delta["post_pin_edits"])
    edited = {item["path"] for item in delta["post_pin_edits"]}
    assert "Mage/src/main/java/mage/game/permanent/token/TokenImpl.java" in edited
    assert "Mage/src/main/java/mage/game/events/CreateTokenEvent.java" in edited
    assert "Mage/src/main/java/mage/abilities/effects/ContinuousEffects.java" in edited
    assert "Mage.Sets/src/mage/cards/w/WaveOfVitriol.java" in edited
    assert delta["dependency_change"] is False
    assert delta["version_change"]["from"] == delta["version_change"]["to"] == ENGINE_VERSION
    assert delta["build_files_changed"] == []


def test_perf_port_and_muse_patches_are_declared_out_of_the_pin() -> None:
    not_in_pin = _lock()["not_in_pin"]
    assert any("0c0132a2ef" in item and "option text" in item for item in not_in_pin)
    assert any("Muse" in item and "Turbulent" in item for item in not_in_pin)


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
    # the v11 pin ran 7467 tests; the engine commits add tests, never remove them
    assert native["run"] >= 7467
    assert verify["result"] in {"PASS", "FAIL (pre-existing, baseline-attributed)"}


def test_local_observations_carry_no_ci_credit() -> None:
    local = _lock()["local_observed"]
    assert local["status"].startswith("LOCAL_OBSERVED")
    assert "no CI-level credit" in local["status"]


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
