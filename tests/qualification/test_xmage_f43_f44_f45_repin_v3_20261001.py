"""Successor guard for the 2026-10-01 XMage candidate repin (v3).

The live XMage pin is the multiplayer candidate branch advanced by F-44 (leaver
trigger order, mage#33), F-43 (combat-damage source revalidation, mage#29) and
F-45 (copied-spell library move, mage#35). The intermediate candidate 4e59e8b9
(F-44 + F-43 only) was qualified but never live; the lock keeps that evidence
under its own identity.
The prior pin (9375f35a, successor lock v2), its current-boundary epoch
4cad91897216-a43e80d96595 and the frozen WSR22 identity (b19596980f27) stay
historical: this repin opens a new successor epoch, it does not relabel
earlier evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_PIN = "37e4df6c914f1e189e24f0ef59fa91734c922436"
CURRENT_TREE = "dac695ab2862e965cdaa30b0ce67052840dc7a5e"
INTERMEDIATE = "4e59e8b9087878816b37728055eb61757a2fbf07"
F45_HEAD = "9dbda865f91fe7bba1791c9398f0607f5e791606"
PRIOR_PIN = "9375f35ac7c9a540ebcb8b262b8645b8c6b1b326"
WSR22_PIN = "b19596980f2734496ea1896504253e1bdd2756dd"
PRIOR_EPOCH = "qualification/current-boundary-epochs/4cad91897216-a43e80d96595"
SUCCESSOR_LOCK = "qualification/xmage-f43-f44-f45-repin-v3-20261001/SUCCESSOR_SOURCE_LOCK.json"

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


def test_successor_lock_binds_the_candidate_its_donors_and_the_prior_pin() -> None:
    lock = _lock()
    assert lock["new_live_pin"]["commit"] == CURRENT_PIN
    assert lock["new_live_pin"]["tree"] == CURRENT_TREE
    assert lock["new_live_pin"]["source_archive"] == _manifest()["primary_engine"]["source_archive"]
    assert lock["prior_live_pin"]["commit"] == PRIOR_PIN
    assert lock["prior_live_pin"]["current_boundary_epoch"] == PRIOR_EPOCH
    assert {donor["finding"] for donor in lock["donors"]} == {"F-43", "F-44", "F-45"}
    for donor in lock["donors"]:
        assert len(donor["head"]) == 40, donor
    native = lock["native_qualification"]["full_mage_tests"]
    assert native["commit"] == CURRENT_PIN
    assert native["failures"] == 0 and native["errors"] == 0
    assert lock["lab_runtime_qualification"]["bridge_suite"]["failures"] == 0
    assert lock["lab_runtime_qualification"]["installed_artifacts_commit"] == CURRENT_PIN
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "ARCHITECTURE_FREEZE"}


def test_intermediate_candidate_evidence_keeps_its_own_identity() -> None:
    intermediate = _lock()["intermediate_candidate"]
    assert intermediate["commit"] == INTERMEDIATE
    assert intermediate["live"] is False
    assert intermediate["native_qualification"]["commit"] == INTERMEDIATE
    assert intermediate["lab_runtime_qualification"]["commit"] == INTERMEDIATE


def test_lineage_binds_each_identity_once() -> None:
    lineage = _lock()["lineage"]
    assert lineage["old_lab_pin"]["commit"] == PRIOR_PIN
    assert lineage["intermediate_candidate"]["commit"] == INTERMEDIATE
    assert lineage["f45_fix_head"]["commit"] == F45_HEAD
    assert lineage["final_integrated_candidate"] == {
        "commit": CURRENT_PIN,
        "tree": CURRENT_TREE,
        "content": "F-43 + F-44 + F-45",
    }
    # Same tree, different commits: the F-45 head's runs are not the final pin's runs.
    assert lineage["f45_fix_head"]["tree"] == CURRENT_TREE
    lock = _lock()
    assert lock["native_qualification"]["full_mage_tests"]["commit"] == CURRENT_PIN
    assert lock["lab_runtime_qualification"]["installed_artifacts_commit"] == CURRENT_PIN


def test_all_active_literal_pin_consumers_migrated() -> None:
    for rel in ACTIVE_LITERAL_CONSUMERS:
        text = (REPO_ROOT / rel).read_text()
        assert CURRENT_PIN in text, rel
        assert PRIOR_PIN not in text, rel
        assert INTERMEDIATE not in text, rel


def test_prior_pin_and_its_epoch_stay_historical() -> None:
    from commander_lab.qualification.current_boundary import source_lock

    assert source_lock.XMAGE_CANDIDATE_COMMIT == WSR22_PIN
    prior = json.loads(
        (
            REPO_ROOT
            / "qualification/xmage-mp-candidate-repin-v2-20260930/SUCCESSOR_SOURCE_LOCK.json"
        ).read_text()
    )
    assert prior["new_live_pin"]["commit"] == PRIOR_PIN
    # The prior epoch is evidence about PRIOR_PIN; it is never re-labelled.
    assert (REPO_ROOT / PRIOR_EPOCH).is_dir()
    epoch_text = "".join(
        p.read_text(encoding="utf-8") for p in (REPO_ROOT / PRIOR_EPOCH).glob("*.json")
    )
    assert CURRENT_PIN not in epoch_text
    note = _manifest()["authority_note"]["known_stale_pointers"]
    assert f"Prior canonical xmage pin {PRIOR_PIN}" in note
    assert f"Canonical xmage pin is now {CURRENT_PIN}" in note
