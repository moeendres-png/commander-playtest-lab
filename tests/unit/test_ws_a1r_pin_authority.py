from __future__ import annotations

import json
from pathlib import Path

STALE_FORGE_PIN = "852066bf4f761b302ed17cb011999d8a8fe08ad6"
STALE_XMAGE_PIN = "06d166b098ad36b277edef01116472203d5a047e"
MANIFEST = "config/rules_engines.json"


def _manifest(repo_root: Path) -> dict:
    return json.loads((repo_root / MANIFEST).read_text(encoding="utf-8"))


def test_manifest_declares_sole_pin_authority(repo_root: Path) -> None:
    note = _manifest(repo_root)["authority_note"]
    assert "sole machine-readable authority" in note["pin_authority"]
    assert "primary_engine.commit" in note["pin_authority"]
    assert "secondary_engine.commit" in note["pin_authority"]
    terminology = note["role_terminology"]
    # After the Freeze (2026-10-10) and the D5 runtime switch: XMage is selected and
    # the launched runtime is the full-game lane.
    assert "launched runtime is the full-game lane" in terminology["primary_engine"]
    assert "ARCHITECTURE_FREEZE = CLAIMED" in terminology["selection_truth"]
    assert "D5 done" in terminology["selection_truth"]
    assert "XMAGE_SELECTED" in terminology["selection_truth"]
    manifest = _manifest(repo_root)
    assert manifest["architecture_freeze"]["status"] == "CLAIMED"
    assert manifest["architecture_freeze"]["runtime_switch"] == "DONE_D5"
    assert manifest["provider_decision"] == "XMAGE_SELECTED"


def test_manifest_pins_unchanged_by_authority_repair(repo_root: Path) -> None:
    config = _manifest(repo_root)
    assert config["secondary_engine"]["commit"] == "bb0a740d2bef725194798383c2452213ecdd0b37"
    # Live pin: multiplayer candidate after the CR 117.5/800.4a priority repair (mage#41)
    # and the deterministic commander-zone ask order (mage#57; Lab #720), repin v5.
    assert config["primary_engine"]["commit"] == "3cbf7741d29a2fe820725456b90f305f9f793ad1"
    assert config["provider_decision"] == "XMAGE_SELECTED"
    assert config["current_runtime"]["provider_selected"] is True
    assert config["current_runtime"]["production_provider"] == "xmage"


def test_forge_readme_defers_to_manifest(repo_root: Path) -> None:
    text = (repo_root / "integrations/forge/README.md").read_text(encoding="utf-8")
    assert MANIFEST in text
    assert STALE_FORGE_PIN not in text
    assert "historical_phase85" in text


def test_engine_setup_doc_defers_to_manifest(repo_root: Path) -> None:
    text = (repo_root / "docs/engine_setup.md").read_text(encoding="utf-8")
    assert MANIFEST in text
    assert STALE_FORGE_PIN not in text
    assert STALE_XMAGE_PIN not in text
    assert "XMAGE_SELECTED" in text
