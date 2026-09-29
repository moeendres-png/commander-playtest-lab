from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT = "fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c"
CURRENT_TREE = "ba0d02bdf5e9d62361d68dbdfb7e729d46ce9aed"
PRIOR = "f79e4168902e65063034b21be6f4585397fd43b3"
LOCK = ROOT / "qualification/xmage-f22-f23-successor-repin-20260929/SUCCESSOR_SOURCE_LOCK.json"


def test_successor_source_lock_binds_exact_mage_candidate() -> None:
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    assert data["prior_live_pin"]["commit"] == PRIOR
    assert data["new_live_pin"]["commit"] == CURRENT
    assert data["new_live_pin"]["tree"] == CURRENT_TREE
    assert data["new_live_pin"]["parent_commit"] == PRIOR
    assert data["new_live_pin"]["pull_request"] == "moeendres-png/mage#26"
    assert data["new_live_pin"]["semantic_fingerprint"] == "mage.game.Game#getOpponentsInGame(UUID)"


def test_live_pin_surfaces_bind_successor_not_prior() -> None:
    manifest = json.loads((ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    assert manifest["primary_engine"]["commit"] == CURRENT

    current_surfaces = [
        "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java",
        "engine-bridge/src/test/java/org/commanderlab/xmage/JsonlBridgeTest.java",
        "engine-bridge/src/test/java/org/commanderlab/xmage/XmageCandidateEngineFingerprintTest.java",
        "scripts/bootstrap_engine_linux.sh",
        "scripts/bootstrap_engine_windows.ps1",
        "scripts/run_external_full_game_conformance.py",
        "scripts/run_real_4p_full_game_smoke.py",
        "scripts/run_real_deck_gate.py",
        ".github/workflows/external-engine-integration.yml",
        ".github/workflows/meta-qualification.yml",
        ".github/workflows/xmage-full-game-conformance.yml",
        ".github/workflows/xmage-real-4p-smoke.yml",
    ]
    for rel in current_surfaces:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert CURRENT in text, rel


def test_runtime_fingerprint_is_successor_specific() -> None:
    text = (ROOT / "engine-bridge/src/test/java/org/commanderlab/xmage/XmageCandidateEngineFingerprintTest.java").read_text(encoding="utf-8")
    assert CURRENT in text
    assert 'getMethod("getOpponentsInGame", UUID.class)' in text


def test_f22_f23_bridge_regressions_are_enabled() -> None:
    battle = (ROOT / "engine-bridge/src/test/java/org/commanderlab/xmage/XmageMultiplayerBattleTest.java").read_text(encoding="utf-8")
    vote = (ROOT / "engine-bridge/src/test/java/org/commanderlab/xmage/XmageMultiplayerVoteTest.java").read_text(encoding="utf-8")
    assert "@Disabled" not in battle
    assert "@Disabled" not in vote
    assert 'f.protectorChoice = "P2";' in battle
    assert "aPlayerWhoLeftThisTurnDoesNotVote" in vote


def test_prior_epoch_lock_remains_historical() -> None:
    prior_lock = json.loads((ROOT / "qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json").read_text(encoding="utf-8"))
    assert prior_lock["new_live_pin"]["commit"] == PRIOR
