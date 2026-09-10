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


def test_manifest_pins_unchanged_by_authority_repair(repo_root: Path) -> None:
    config = _manifest(repo_root)
    assert config["secondary_engine"]["commit"] == "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
    assert config["primary_engine"]["commit"] == "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
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
