"""Fail-closed checksum contract for XMage full-game evidence artifacts."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "seal_xmage_full_game_artifacts.py"
WORKFLOW = ROOT / ".github" / "workflows" / "xmage-full-game-conformance.yml"


@pytest.fixture(scope="module")
def integrity() -> Any:
    spec = importlib.util.spec_from_file_location("xmage_full_game_artifact_integrity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_root(integrity: Any, tmp_path: Path) -> Path:
    root = tmp_path / "xmage-full-game"
    root.mkdir()
    for index, name in enumerate(integrity.REQUIRED_EVIDENCE):
        (root / name).write_text(f"evidence-{index}\n", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "diagnostic.txt").write_text("diagnostic\n", encoding="utf-8")
    return root


def test_complete_artifact_root_seals_and_verifies_with_root_relative_paths(
    integrity: Any, tmp_path: Path
) -> None:
    root = _complete_root(integrity, tmp_path)
    manifest = integrity.seal(root)

    assert manifest.is_file()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines
    assert all("  ./" in line for line in lines)
    assert not any(str(root) in line for line in lines)
    integrity.verify_manifest(root)


def test_tampered_hashed_file_fails_verification(integrity: Any, tmp_path: Path) -> None:
    root = _complete_root(integrity, tmp_path)
    integrity.seal(root)
    target = root / integrity.REQUIRED_EVIDENCE[0]
    target.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(integrity.ArtifactIntegrityError, match="checksum mismatch"):
        integrity.verify_manifest(root)


def test_missing_hashed_file_fails_verification(integrity: Any, tmp_path: Path) -> None:
    root = _complete_root(integrity, tmp_path)
    integrity.seal(root)
    (root / integrity.REQUIRED_EVIDENCE[0]).unlink()

    with pytest.raises(integrity.ArtifactIntegrityError):
        integrity.verify_manifest(root)


@pytest.mark.parametrize("manifest_text", ["", "not-a-valid-manifest\n"])
def test_empty_or_invalid_manifest_fails_verification(
    integrity: Any, tmp_path: Path, manifest_text: str
) -> None:
    root = _complete_root(integrity, tmp_path)
    (root / integrity.MANIFEST_NAME).write_text(manifest_text, encoding="utf-8")

    with pytest.raises(integrity.ArtifactIntegrityError):
        integrity.verify_manifest(root)


def test_missing_required_evidence_fails_seal_without_leaving_manifest(
    integrity: Any, tmp_path: Path
) -> None:
    root = _complete_root(integrity, tmp_path)
    (root / integrity.REQUIRED_EVIDENCE[-1]).unlink()

    with pytest.raises(
        integrity.ArtifactIntegrityError, match="required full-game evidence missing"
    ):
        integrity.seal(root)
    assert not (root / integrity.MANIFEST_NAME).exists()


def test_workflow_uses_fail_closed_integrity_seal_and_preserves_forensic_upload() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    assert isinstance(workflow, dict)
    assert "conformance" in workflow["jobs"]

    start = text.index("- name: Record test validation and checksums")
    end = text.index("- name: Upload full-game technical conformance evidence")
    block = text[start:end]

    assert "if: always()" in block
    assert "scripts/seal_xmage_full_game_artifacts.py" in block
    assert "test -s SHA256SUMS" in block
    assert "sha256sum -c SHA256SUMS" in block
    assert "|| true" not in block

    upload = text[end:]
    assert "if: always()" in upload
