"""Artifact byte-integrity tests; fixtures are synthetic, not Rules evidence."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import evidence


def test_missing_root_is_not_empty_success(tmp_path):
    with pytest.raises(ValueError):
        evidence.artifact_index([str(tmp_path / "missing")])


def test_file_root_is_rejected(tmp_path):
    file = tmp_path / "f"
    file.write_text("evidence")
    with pytest.raises(ValueError):
        evidence.artifact_index([str(file)])


def test_overlapping_roots_patterns_are_deduplicated(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    file = child / "result.json"
    file.write_text("{}")
    rows = evidence.artifact_index(
        [str(tmp_path), str(child), str(tmp_path)], patterns=("*", "*.json")
    )["artifacts"]
    assert len(rows) == 1
    assert rows[0]["size"] == 2
    assert rows[0]["sha256"] == hashlib.sha256(b"{}").hexdigest()


def test_cli_output_never_indexes_itself(tmp_path):
    (tmp_path / "result.txt").write_text("stable evidence")
    output = tmp_path / "manifest.json"
    args = ["artifact-index", "--root", str(tmp_path), "--output", str(output)]
    assert evidence.main(args) == 0
    first = json.loads(output.read_text())["artifacts"]
    assert evidence.main(args) == 0
    assert json.loads(output.read_text())["artifacts"] == first


def test_failure_preserves_existing_output(tmp_path, capsys):
    output = tmp_path / "manifest.json"
    output.write_text("previous sealed manifest")
    assert (
        evidence.main(
            ["artifact-index", "--root", str(tmp_path / "missing"), "--output", str(output)]
        )
        == 1
    )
    assert output.read_text() == "previous sealed manifest"
    assert not capsys.readouterr().out


def test_file_mutated_during_hash_is_rejected(tmp_path, monkeypatch):
    file = tmp_path / "result.txt"
    file.write_bytes(b"original")
    factory = hashlib.sha256

    class MutatingDigest:
        def __init__(self):
            self.inner = factory()

        def update(self, chunk):
            file.write_bytes(b"changed content and size")
            self.inner.update(chunk)

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(evidence.hashlib, "sha256", MutatingDigest)
    with pytest.raises(ValueError):
        evidence.artifact_index([str(tmp_path)])


def test_empty_existing_root_is_legitimate_empty_inventory(tmp_path):
    assert evidence.artifact_index([str(tmp_path)])["artifacts"] == []


def test_links_do_not_export_external_bytes(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("PRIVATE_CANARY")
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside)
    assert evidence.artifact_index([str(root)])["artifacts"] == []


def test_recursive_pattern_keeps_top_level_files(tmp_path):
    (tmp_path / "result.json").write_text("{}")
    assert len(evidence.artifact_index([str(tmp_path)], patterns=("**/*.json",))["artifacts"]) == 1


def test_publish_failure_preserves_manifest_and_cleans_temp(tmp_path, monkeypatch):
    (tmp_path / "result.txt").write_text("bytes")
    output = tmp_path / "manifest.json"
    output.write_text("sealed")

    def fail(*a):
        raise OSError("injected replace failure")

    monkeypatch.setattr(evidence.os, "replace", fail)
    assert evidence.main(["artifact-index", "--root", str(tmp_path), "--output", str(output)]) == 1
    assert output.read_text() == "sealed"
    assert not list(tmp_path.glob(".artifact-index-*"))


def test_path_replaced_during_hash_is_rejected(tmp_path, monkeypatch):
    file = tmp_path / "result.txt"
    file.write_bytes(b"original")
    replacement = tmp_path / "new"
    replacement.write_bytes(b"original")
    factory = hashlib.sha256

    class ReplacingDigest:
        def __init__(self):
            self.inner = factory()

        def update(self, chunk):
            replacement.replace(file)
            self.inner.update(chunk)

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(evidence.hashlib, "sha256", ReplacingDigest)
    with pytest.raises(ValueError):
        evidence.sha256_of(file)


def test_traversal_error_fails_closed(tmp_path, monkeypatch):
    def broken_walk(*args, **kwargs):
        kwargs["onerror"](PermissionError("PRIVATE_CANARY"))
        return iter(())

    monkeypatch.setattr(evidence.os, "walk", broken_walk)
    with pytest.raises(ValueError, match="traversal failed"):
        evidence.artifact_index([str(tmp_path)])


def test_cli_failure_never_exposes_content(tmp_path, monkeypatch, capsys):
    def fail(*a, **kw):
        raise OSError("PRIVATE_CANARY")

    monkeypatch.setattr(evidence, "artifact_index", fail)
    assert evidence.main(["artifact-index", "--root", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert "PRIVATE_CANARY" not in output.err + output.out
    assert "ARTIFACT_INDEX_FAIL" in output.err
