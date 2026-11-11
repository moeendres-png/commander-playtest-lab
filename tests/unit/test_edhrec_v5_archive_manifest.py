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


def test_repository_manifest_covers_every_v5_source_byte() -> None:
    source = MODULE.parents[1] / "data/provenance/edhrec_v5_20261110/source_multiset.csv"
    counts = verifier.read_manifest(source)
    assert len(counts) == 962
    assert sum(counts.values()) == 963
    assert {
        group: sum(n for (kind, _size, _sha), n in counts.items() if kind == group)
        for group in verifier.EXPECTED_COUNTS
    } == verifier.EXPECTED_COUNTS
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "379416495bb5c606de38ec261c37d3a903468324f19e9f0f92fbd8ef2ff3ed3c"
    )


@pytest.mark.parametrize("fault", ["none", "verified", "mainboard", "index"])
def test_preview_status_requires_actual_empty_deck_exports(
    tmp_path: Path, fault: str
) -> None:
    archive = tmp_path / "preview-evidence.zip"
    status = "VERIFIED" if fault == "index" else "DECK_NOT_VERIFIED"
    index = "id,status,fingerprint\n" + "".join(
        f"test-{i},{status},\n" for i in range(470)
    )
    with zipfile.ZipFile(archive, "w") as dest:
        dest.writestr("01_EDHREC_DECK_INDEX.csv", index)
        dest.writestr(
            "02_DECKS_COMPACT_ELIGIBLE.jsonl",
            '{"fake":"deck"}\n' if fault == "verified" else "",
        )
        dest.writestr(
            "02_MAINBOARD_CARDS_NORMALIZED.csv",
            "id,name,oracle_id,quantity\n"
            + ("test-0,Forest,unknown,1\n" if fault == "mainboard" else ""),
        )
        dest.writestr(
            "05_BRACKET1_EXHIBITION_EXCLUDED.csv",
            "id,url,evidence_url\n" + "test-a,,\ntest-b,,\n",
        )
    with zipfile.ZipFile(archive) as source:
        if fault == "none":
            assert verifier.verify_no_complete_decks(source) == {
                "source_preview_ids": 470,
                "verified_complete_99_card_decks": 0,
                "excluded_bracket1_preview_ids": 2,
            }
        else:
            with pytest.raises(ValueError):
                verifier.verify_no_complete_decks(source)
