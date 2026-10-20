"""Successor guard for the 2026-10-20 XMage upstream-update repin (v9).

The live XMage pin is the head of the fork branch ``update-upstream-2026-10``
(moeendres-png/mage#64): magefree/mage master (fab0f23b, version 1.4.62, 688 commits
the v8 pin lacked) merged into the candidate line (c39ab8a9), with the fork APIs kept,
18 conflicted files resolved, the duplicated set registrations that the merge produced
dropped and three fork tests adapted to upstream behavior. The engine version moves
from 1.4.61 to 1.4.62.

Native qualification is bound to the fork ``maven.yml`` run on the exact commit. The
Lab ``bridge_suite`` is COMPLETE only with an Actions run, its job and an artifact
digest; a local run is LOCAL_OBSERVED and carries no CI-level credit. NOT_RUN, PENDING
or LOCAL_OBSERVED never counts as PASS.

The prior pin (348b37db, successor lock v8) stays historical. The Owner-signed
Architecture Freeze stays bound to b479fe74; current_qualification does not move with
the pin: it moves only when PB-03 runs on the Lab main merge commit of this repin, AF11
is re-adjudicated for the new pin (the mage jar names change) and the epoch is sealed.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "043579bb7829fa866ade893909c9ba4825a18b23"
CURRENT_TREE = "8a3a81952509adca28cb0a8b296642de18766987"
PRIOR_PIN = "348b37db5cf64f4ed503e8d37b776d5edc70e6d5"
PRIOR_TREE = "f62bfea3d215441c568baa8ff9878597a60979bc"
PIN_PARENT = "6a4d4189545d39655cf88445f5265ec8046cd8bb"
UPSTREAM_MASTER = "fab0f23b78ddd755102cebfe20d618be87af59d0"
MERGE_COMMIT = "7e4360a2284a99626714a38585b4b0f87d0ed06d"
CANDIDATE_LINE_HEAD = "c39ab8a99617496e1880e3cc053a793517b2b238"
FREEZE_PIN = "b479fe74fd1eaf899ff16c6a9203e74a91c0f339"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
ENGINE_VERSION = "1.4.62"
SUCCESSOR_LOCK = "qualification/xmage-upstream-update-repin-v9-20261020/SUCCESSOR_SOURCE_LOCK.json"
PRIOR_LOCKS = ("qualification/xmage-sos-prepare-repin-v8-20261017/SUCCESSOR_SOURCE_LOCK.json",)
FREEZE_ARTIFACT_SHA256 = "ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d"
FREEZE_EPOCH = "qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4"
EPOCH_ROOT = "qualification/current-boundary-epochs"

RESOLVED_CONFLICT_FILES = (
    ".github/workflows/maven.yml",
    "Mage.Sets/src/mage/cards/a/AshlingTheLimitless.java",
    "Mage.Sets/src/mage/cards/n/NYamiClassMotherShip.java",
    "Mage.Sets/src/mage/cards/s/ShuriTheBlackPanther.java",
    "Mage.Sets/src/mage/cards/s/StormOfMemories.java",
    "Mage.Sets/src/mage/cards/s/StormQueenOfWakanda.java",
    "Mage.Sets/src/mage/cards/t/ThorAsgardsAvenger.java",
    "Mage.Sets/src/mage/cards/w/WKabiShieldOfTheNation.java",
    "Mage.Sets/src/mage/cards/w/WakandaForever.java",
    "Mage.Sets/src/mage/sets/SecretsOfStrixhaven.java",
    "Mage.Sets/src/mage/sets/SecretsOfStrixhavenCommander.java",
    "Mage.Tests/src/test/java/org/mage/test/cards/abilities/keywords/PrepareTest.java",
    "Mage.Tests/src/test/java/org/mage/test/cards/single/msc/StormQueenOfWakandaTest.java",
    "Mage.Tests/src/test/java/org/mage/test/cards/single/msc/ThorAsgardsAvengerTest.java",
    "Mage/src/main/java/mage/MageIdentifier.java",
    "Mage/src/main/java/mage/abilities/effects/common/BecomePreparedTargetEffect.java",
    "Mage/src/main/java/mage/cards/PrepareCard.java",
    "Mage/src/main/java/mage/cards/PrepareSpellCard.java",
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
    assert pin["parents"] == [PIN_PARENT]
    assert pin["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["tree"] == PRIOR_TREE
    assert lock["prior_live_pin"]["successor_locks"] == list(PRIOR_LOCKS)
    assert [d["pr"] for d in lock["donors"]] == ["moeendres-png/mage#64"]
    assert lock["donors"][0]["head"] == CURRENT_PIN
    lineage = lock["lineage"]
    assert lineage["prior_pin"] == {"commit": PRIOR_PIN, "tree": PRIOR_TREE}
    assert lineage["candidate_line_head"]["commit"] == CANDIDATE_LINE_HEAD
    assert lineage["upstream_master"]["commit"] == UPSTREAM_MASTER
    assert lineage["upstream_master"]["version"] == ENGINE_VERSION
    assert lineage["merge_commit"]["commit"] == MERGE_COMMIT
    assert lineage["merge_commit"]["parents"] == [CANDIDATE_LINE_HEAD, UPSTREAM_MASTER]
    assert lineage["final_integrated_candidate"]["commit"] == CURRENT_PIN
    assert lineage["final_integrated_candidate"]["tree"] == CURRENT_TREE
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_engine_delta_declares_the_resolved_conflicts_and_the_dependency_change() -> None:
    delta = _lock()["engine_delta"]
    # Lists of path/blob objects, not path -> blob maps: a "SecretsOf..." key next to a
    # 40-hex value is flagged by the broad secret scan as a generic API key.
    resolved = delta["resolved_conflict_files"]
    assert tuple(sorted(item["path"] for item in resolved)) == tuple(
        sorted(RESOLVED_CONFLICT_FILES)
    )
    assert all(len(item["blob"]) == 40 for item in resolved + delta["post_merge_edits"])
    assert "Mage/src/main/java/mage/game/GameImpl.java" in {
        item["path"] for item in delta["post_merge_edits"]
    }
    assert delta["dependency_change"] is True
    on_provider_classpath = {
        change["artifact"]: change["on_provider_classpath"]
        for change in delta["dependency_changes"]
    }
    # No dependency of the provider classpath changes, so AF11's licence inventory only
    # renames the five mage jars.
    assert on_provider_classpath and not any(on_provider_classpath.values())
    assert delta["version_change"] == {
        "from": "1.4.61",
        "to": ENGINE_VERSION,
        "note": delta["version_change"]["note"],
    }


def test_muse_patches_are_declared_out_of_the_pin() -> None:
    not_in_pin = _lock()["not_in_pin"]
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
    assert native["run"] >= 7198
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


def test_engine_version_moves_with_the_pin_everywhere_it_is_declared() -> None:
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
