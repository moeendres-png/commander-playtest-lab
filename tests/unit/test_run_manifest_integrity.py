from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.storage.run_integrity import create_run_manifest, verify_run


@pytest.fixture
def sealed_run(tmp_path: Path) -> Path:
    root = tmp_path / "run"
    root.mkdir()
    (root / "result.json").write_text('{"result": 1}', encoding="utf-8")
    create_run_manifest(root, run_id="r1", status="completed", metadata={"seed": 1})
    return root


def _manifest(root: Path) -> dict:
    return json.loads((root / "run-manifest.json").read_text(encoding="utf-8"))


def _replace(root: Path, payload: object) -> None:
    (root / "run-manifest.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("payload", [None, [], 7, "manifest"])
def test_non_object_manifest_fails_closed(sealed_run: Path, payload: object) -> None:
    _replace(sealed_run, payload)
    result = verify_run(sealed_run)
    assert not result.valid and result.status == "corrupt"


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", 99), ("schema_version", True), ("run_id", ""), ("metadata", [])],
)
def test_invalid_manifest_header_fails_closed(sealed_run: Path, field: str, value: object) -> None:
    payload = _manifest(sealed_run)
    payload[field] = value
    _replace(sealed_run, payload)
    assert not verify_run(sealed_run).valid


@pytest.mark.parametrize("record", [None, [], "hash", {"size": True, "sha256": "0" * 64}])
def test_invalid_file_record_is_not_an_exception(sealed_run: Path, record: object) -> None:
    payload = _manifest(sealed_run)
    payload["files"]["result.json"] = record
    _replace(sealed_run, payload)
    result = verify_run(sealed_run)
    assert not result.valid and result.status == "corrupt"


def test_removed_file_declaration_cannot_hide_existing_artifact(sealed_run: Path) -> None:
    payload = _manifest(sealed_run)
    payload["files"] = {}
    _replace(sealed_run, payload)
    assert not verify_run(sealed_run).valid


def test_added_artifact_invalidates_seal(sealed_run: Path) -> None:
    (sealed_run / "unlisted-result.json").write_text("{}", encoding="utf-8")
    assert not verify_run(sealed_run).valid


def test_nested_manifest_is_covered(tmp_path: Path) -> None:
    nested = tmp_path / "child"
    nested.mkdir()
    artifact = nested / "run-manifest.json"
    artifact.write_text("child receipt", encoding="utf-8")
    create_run_manifest(tmp_path, run_id="parent", status="completed", metadata={})
    assert "child/run-manifest.json" in _manifest(tmp_path)["files"]
    artifact.write_text("tampered child receipt", encoding="utf-8")
    assert not verify_run(tmp_path).valid


def test_duplicate_json_keys_are_rejected(sealed_run: Path) -> None:
    path = sealed_run / "run-manifest.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"status": "completed"', '"status": "failed", "status": "completed"'), encoding="utf-8")
    assert not verify_run(sealed_run).valid


def test_invalid_utf8_manifest_fails_closed(sealed_run: Path) -> None:
    (sealed_run / "run-manifest.json").write_bytes(b"\xff")
    assert not verify_run(sealed_run).valid


@pytest.mark.parametrize("relative", ["./result.json", "child/../result.json", "/result.json"])
def test_noncanonical_manifest_paths_rejected(sealed_run: Path, relative: str) -> None:
    payload = _manifest(sealed_run)
    payload["files"][relative] = payload["files"].pop("result.json")
    _replace(sealed_run, payload)
    assert not verify_run(sealed_run).valid


def test_in_run_symlink_is_not_a_sealed_artifact(sealed_run: Path) -> None:
    link = sealed_run / "alias.json"
    link.symlink_to(sealed_run / "result.json")
    original = (sealed_run / "run-manifest.json").read_bytes()
    with pytest.raises(ValueError):
        create_run_manifest(sealed_run, run_id="r1", status="completed", metadata={})
    assert (sealed_run / "run-manifest.json").read_bytes() == original
    assert not verify_run(sealed_run).valid
