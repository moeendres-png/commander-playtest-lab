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
    assert "NOT a Production Provider" in terminology["primary_engine"]
    assert "NOT SELECTED" in terminology["selection_truth"]
    assert "NO_PROVIDER_READY" in terminology["selection_truth"]


def test_manifest_pins_match_current_owner_authority(repo_root: Path) -> None:
    config = _manifest(repo_root)
    # R-1: current Forge authority is the admitted Commander-Lab fork successor.
    assert config["secondary_engine"]["commit"] == "b3ed4fe5433b9272c4e58f3d909a7fbb673de169"
    assert config["secondary_engine"]["bridge_source"]["commit"] == "bb0a740d2bef725194798383c2452213ecdd0b37"
    assert config["secondary_engine"]["bridge_source"]["rules_core_base_commit"] == "b3ed4fe5433b9272c4e58f3d909a7fbb673de169"
    assert config["secondary_engine"]["repository"] == "https://github.com/moeendres-png/forge.git"
    assert config["secondary_engine"]["engine_identity_pb09"]["pb09_status"].startswith(
        "RESOLVED_BY_OWNER_R1"
    )
    # Residual-campaign forward repin: cumulative M1-M4 Mage candidate.
    assert config["primary_engine"]["commit"] == "9375f35ac7c9a540ebcb8b262b8645b8c6b1b326"
    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["current_runtime"]["provider_selected"] is False
    assert config["current_runtime"]["production_provider"] is None


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
    assert "NO_PROVIDER_READY" in text
