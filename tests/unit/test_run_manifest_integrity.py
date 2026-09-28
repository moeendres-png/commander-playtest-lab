from __future__ import annotations

import json
import os
import subprocess
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


def _symlink(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable; covered by Linux CI")
        raise


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
    path.write_text(
        text.replace('"status": "completed"', '"status": "failed", "status": "completed"'),
        encoding="utf-8",
    )
    assert not verify_run(sealed_run).valid


def _write_seed_literal(root: Path, literal: str, *, nested: bool = False) -> None:
    payload = _manifest(root)
    payload["metadata"] = {"nested": {"seed": 1}} if nested else {"seed": 1}
    text = json.dumps(payload)
    marker = '"seed": 1'
    assert marker in text
    text = text.replace(marker, f'"seed": {literal}', 1)
    assert f'"seed": {literal}' in text
    (root / "run-manifest.json").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("literal", ["1e999", "-1e999", "NaN", "Infinity", "-Infinity"])
def test_nonfinite_numeric_literal_fails_closed(sealed_run: Path, literal: str) -> None:
    _write_seed_literal(sealed_run, literal)
    result = verify_run(sealed_run)
    assert not result.valid and result.status == "corrupt"


def test_nested_overflowing_numeric_literal_fails_closed(sealed_run: Path) -> None:
    _write_seed_literal(sealed_run, "1e999", nested=True)
    result = verify_run(sealed_run)
    assert not result.valid and result.status == "corrupt"


def test_large_finite_numeric_literal_remains_valid(sealed_run: Path) -> None:
    _write_seed_literal(sealed_run, "1e308")
    result = verify_run(sealed_run)
    assert result.valid and result.status == "valid"


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
    _symlink(link, sealed_run / "result.json")
    original = (sealed_run / "run-manifest.json").read_bytes()
    with pytest.raises(ValueError):
        create_run_manifest(sealed_run, run_id="r1", status="completed", metadata={})
    assert (sealed_run / "run-manifest.json").read_bytes() == original
    assert not verify_run(sealed_run).valid


@pytest.mark.parametrize(
    "field", ["schema_version", "run_id", "created_at", "status", "metadata", "files"]
)
def test_missing_required_field_is_corrupt(sealed_run: Path, field: str) -> None:
    payload = _manifest(sealed_run)
    del payload[field]
    _replace(sealed_run, payload)
    assert not verify_run(sealed_run).valid


@pytest.mark.parametrize("size", [True, -1, 1.0, "1"])
def test_file_size_is_strictly_a_nonnegative_integer(sealed_run: Path, size: object) -> None:
    (sealed_run / "result.json").write_bytes(b"x")
    create_run_manifest(sealed_run, run_id="r1", status="completed", metadata={})
    payload = _manifest(sealed_run)
    payload["files"]["result.json"]["size"] = size
    _replace(sealed_run, payload)
    assert not verify_run(sealed_run).valid


def test_quarantine_exclusion_is_relative_to_run_root(tmp_path: Path) -> None:
    root = tmp_path / ".quarantine" / "run"
    root.mkdir(parents=True)
    (root / "result.json").write_bytes(b"result")
    excluded = root / ".quarantine"
    excluded.mkdir()
    (excluded / "ignored.json").write_bytes(b"ignored")
    create_run_manifest(root, run_id="r1", status="completed", metadata={})
    assert set(_manifest(root)["files"]) == {"result.json"}
    assert verify_run(root).valid
    (excluded / "ignored.json").write_bytes(b"excluded mutation")
    assert verify_run(root).valid
    (root / "result.json").write_bytes(b"ordinary mutation")
    assert not verify_run(root).valid


@pytest.mark.parametrize("kind", ["manifest", "directory", "dangling"])
def test_symbolic_links_fail_closed(sealed_run: Path, tmp_path: Path, kind: str) -> None:
    if kind == "manifest":
        path = sealed_run / "run-manifest.json"
        source = tmp_path / "other-manifest.json"
        source.write_bytes(path.read_bytes())
        path.unlink()
        _symlink(path, source)
    elif kind == "directory":
        _symlink(sealed_run / "linked-directory", tmp_path, directory=True)
    else:
        _symlink(sealed_run / "dangling", tmp_path / "absent")
    assert not verify_run(sealed_run).valid


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unavailable on this platform")
def test_special_file_rejected_without_opening_it(sealed_run: Path) -> None:
    os.mkfifo(sealed_run / "pipe")
    assert not verify_run(sealed_run).valid
    with pytest.raises(ValueError):
        create_run_manifest(sealed_run, run_id="r1", status="completed", metadata={})


@pytest.mark.parametrize("metadata", [{"value": float("nan")}, {1: "one", "1": "other"}])
def test_failed_creation_preserves_previous_seal(sealed_run: Path, metadata: dict) -> None:
    before = (sealed_run / "run-manifest.json").read_bytes()
    with pytest.raises(ValueError):
        create_run_manifest(sealed_run, run_id="r1", status="completed", metadata=metadata)
    assert (sealed_run / "run-manifest.json").read_bytes() == before
    assert verify_run(sealed_run).valid


@pytest.mark.parametrize("status", ["completed", "failed", "aborted", "incomplete"])
def test_existing_run_statuses_round_trip(sealed_run: Path, status: str) -> None:
    create_run_manifest(sealed_run, run_id="r1", status=status, metadata={})
    result = verify_run(sealed_run)
    assert result.valid is (status == "completed")
    assert not result.errors
    assert result.checked_files == 1


def test_cli_emits_structured_rejection_for_malformed_manifest(sealed_run: Path) -> None:
    from typer.testing import CliRunner

    from commander_lab.cli.app import app

    _replace(sealed_run, ["private-marker-invalid-manifest"])
    result = CliRunner().invoke(app, ["runs-verify", str(sealed_run)])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["valid"] is False and payload["status"] == "corrupt"
    assert "private-marker" not in result.stdout


def test_unreadable_artifact_fails_closed_without_raw_diagnostics(
    sealed_run: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.storage import run_integrity

    def unavailable(path: Path) -> tuple[int, str]:
        raise PermissionError("private-marker from filesystem")

    monkeypatch.setattr(run_integrity, "_snapshot", unavailable)
    result = verify_run(sealed_run)
    assert not result.valid and result.status == "corrupt"
    assert "private-marker" not in str(result.errors)


def test_incomplete_directory_scan_cannot_replace_a_seal(
    sealed_run: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.storage import run_integrity

    before = (sealed_run / "run-manifest.json").read_bytes()

    def unavailable(*args: object, **kwargs: object) -> object:
        callback = kwargs["onerror"]
        assert callable(callback)
        callback(PermissionError("private-marker from scan"))
        return iter(())

    monkeypatch.setattr(run_integrity.os, "walk", unavailable)
    with pytest.raises(OSError):
        create_run_manifest(sealed_run, run_id="r1", status="completed", metadata={})
    assert (sealed_run / "run-manifest.json").read_bytes() == before
    assert not verify_run(sealed_run).valid


@pytest.mark.skipif(os.name != "nt", reason="Windows junction semantics")
def test_windows_directory_junction_cannot_import_external_artifacts(
    sealed_run: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "external.json").write_bytes(b"external artifact")
    link = sealed_run / "junction"
    subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(link), str(outside)],
        capture_output=True,
        check=True,
    )
    assert link.is_junction()
    original = (sealed_run / "run-manifest.json").read_bytes()
    with pytest.raises(ValueError):
        create_run_manifest(sealed_run, run_id="r1", status="completed", metadata={})
    assert (sealed_run / "run-manifest.json").read_bytes() == original
    assert not verify_run(sealed_run).valid
