"""Synthetic, network-free regression tests for historical EDHREC provenance."""

from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import zipfile
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "scripts/verify_edhrec_v5_archive.py"
SPEC = importlib.util.spec_from_file_location("verify_edhrec_v5_archive", MODULE)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def fixture(tmp_path: Path) -> tuple[Path, Path]:
    archive = tmp_path / "source.zip"
    manifest = tmp_path / "checksums.csv"
    logical = [
        ("raw_previews", "raw_previews/one.json.gz", b'{"public":"preview"}', True),
        ("state", "state/safe.json", b'{"status":"not_verified"}', False),
        ("exports", "summary.csv", b"status,count\nnot_verified,1\n", False),
    ]
    with zipfile.ZipFile(archive, "w") as dest:
        for _group, name, content, compressed in logical:
            dest.writestr(name, gzip.compress(content, mtime=0) if compressed else content)
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["group", "uncompressed_bytes", "sha256", "count"])
        for group, _name, content, _compressed in logical:
            writer.writerow([group, len(content), hashlib.sha256(content).hexdigest(), 1])
    return archive, manifest


def test_private_source_archive_validates_without_public_payload(tmp_path: Path) -> None:
    archive, manifest = fixture(tmp_path)
    result = verifier.verify_archive(archive, manifest, strict_archive=False, strict_counts=False)
    assert result["status"] == "PASS"
    assert result["verified_source_files"] == 3
    assert result["verified_complete_99_card_decks"] == 0
    assert result["active_studio_import"] is False


def test_reject_content_mismatch(tmp_path: Path) -> None:
    archive, manifest = fixture(tmp_path)
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace("raw_previews,", "state,", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        verifier.verify_archive(archive, manifest, strict_archive=False, strict_counts=False)


def test_reject_incomplete_manifest(tmp_path: Path) -> None:
    archive, manifest = fixture(tmp_path)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    manifest.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        verifier.verify_archive(archive, manifest, strict_archive=False, strict_counts=False)


def test_reject_unexpected_sha(tmp_path: Path) -> None:
    _archive, manifest = fixture(tmp_path)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace(lines[1].split(",")[2], "bad")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid SHA-256"):
        verifier.read_manifest(manifest)
