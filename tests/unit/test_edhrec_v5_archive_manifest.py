"""Synthetic, network-free regression tests for historical EDHREC provenance."""

from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
import warnings
import zipfile
from collections import Counter
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
    # Drop a row that is not the largest logical member, so the size cap stays unchanged.
    manifest.write_text("\n".join([lines[0], *lines[2:]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"missing=0, unexpected=1"):
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
        "44a6370ff215477ebe32a49486f5b615769ab1441c6e0d9c1f27dfa67a1b406b"
    )


@pytest.mark.parametrize("fault", ["none", "verified", "mainboard", "index"])
def test_preview_status_requires_actual_empty_deck_exports(tmp_path: Path, fault: str) -> None:
    archive = tmp_path / "preview-evidence.zip"
    status = "VERIFIED" if fault == "index" else "DECK_NOT_VERIFIED"
    index = "id,status,fingerprint\n" + "".join(f"test-{i},{status},\n" for i in range(470))
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


# ---------------------------------------------------------------------------
# Strict path, negative controls, manifest cross-check and bounded reads.
# ---------------------------------------------------------------------------

PROVENANCE = MODULE.parents[1] / "data/provenance/edhrec_v5_20261110"
SYNTHETIC_COUNTS = {"state": 1, "raw_previews": 1, "diagnose": 1, "exports": 4}
INDEX = "id,status,fingerprint\n" + "".join(f"test-{i},DECK_NOT_VERIFIED,\n" for i in range(470))
Members = list[tuple[str, bytes]]
MAX_LOGICAL = len(INDEX.encode())  # the largest logical member in the synthetic manifest


def base_members() -> Members:
    """Logical members satisfying every strict check with SYNTHETIC_COUNTS."""
    return [
        ("01_EDHREC_DECK_INDEX.csv", INDEX.encode()),
        ("02_DECKS_COMPACT_ELIGIBLE.jsonl", b""),
        ("02_MAINBOARD_CARDS_NORMALIZED.csv", b"id,name,oracle_id,quantity\n"),
        ("05_BRACKET1_EXHIBITION_EXCLUDED.csv", b"id,url,evidence_url\ntest-a,,\ntest-b,,\n"),
        ("state/safe.json", b'{"status":"not_verified"}'),
        ("raw_previews/one.json.gz", b'{"public":"preview"}'),
        ("diagnose/note.txt", b"diagnose"),
    ]


def group_of(name: str) -> str:
    return name.split("/", maxsplit=1)[0] if "/" in name else "exports"


def stored(name: str, content: bytes) -> bytes:
    return gzip.compress(content, mtime=0) if name.endswith(".json.gz") else content


def write_zip(path: Path, raw: Members) -> Path:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # duplicate names are the point
        with zipfile.ZipFile(path, "w") as dest:
            for name, data in raw:
                dest.writestr(name, data)
    return path


def write_manifest(path: Path, logical: Members) -> Path:
    rows = Counter((group_of(n), len(c), hashlib.sha256(c).hexdigest()) for n, c in logical)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["group", "uncompressed_bytes", "sha256", "count"])
        for (group, size, digest), count in sorted(rows.items()):
            writer.writerow([group, size, digest, count])
    return path


def build(tmp_path: Path, archive_members: Members | None = None) -> tuple[Path, Path]:
    """Archive from archive_members (default base) with a manifest of the base members."""
    logical = base_members()
    raw = [(n, stored(n, c)) for n, c in (logical if archive_members is None else archive_members)]
    return write_zip(tmp_path / "a.zip", raw), write_manifest(tmp_path / "m.csv", logical)


def freeze(monkeypatch: pytest.MonkeyPatch, archive: Path) -> str:
    """Point the frozen constants at the synthetic archive; return its SHA-256."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(verifier, "EXPECTED_ARCHIVE_SHA256", digest)
    monkeypatch.setattr(verifier, "EXPECTED_ARCHIVE_BYTES", archive.stat().st_size)
    monkeypatch.setattr(verifier, "EXPECTED_COUNTS", dict(SYNTHETIC_COUNTS))
    return digest


def loose(archive: Path, manifest: Path) -> dict[str, object]:
    return verifier.verify_archive(archive, manifest, strict_archive=False, strict_counts=False)


def run_main(
    monkeypatch: pytest.MonkeyPatch, archive: Path, manifest: Path
) -> tuple[int | str | None, str]:
    monkeypatch.setattr(sys, "argv", ["verify", str(archive), "--manifest", str(manifest)])
    try:
        verifier.main()
    except SystemExit as exc:
        return exc.code, ""
    return 0, ""


def test_strict_mode_passes_and_reports_archive_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, manifest = build(tmp_path)
    digest = freeze(monkeypatch, archive)
    result = verifier.verify_archive(archive, manifest)
    assert result["status"] == "PASS"
    assert result["archive_sha256"] == digest
    assert result["source_groups"] == dict(sorted(SYNTHETIC_COUNTS.items()))
    assert result["verified_source_files"] == sum(SYNTHETIC_COUNTS.values())
    assert loose(archive, manifest)["archive_sha256"] is None


def test_strict_mode_rejects_wrong_archive_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, manifest = build(tmp_path)
    freeze(monkeypatch, archive)
    monkeypatch.setattr(verifier, "EXPECTED_ARCHIVE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="SHA-256 differs"):
        verifier.verify_archive(archive, manifest)


def test_strict_mode_rejects_wrong_archive_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, manifest = build(tmp_path)
    freeze(monkeypatch, archive)
    monkeypatch.setattr(verifier, "EXPECTED_ARCHIVE_BYTES", archive.stat().st_size + 1)
    with pytest.raises(ValueError, match="byte size differs"):
        verifier.verify_archive(archive, manifest)


@pytest.mark.parametrize("group", sorted(SYNTHETIC_COUNTS))
def test_strict_mode_rejects_wrong_group_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, group: str
) -> None:
    archive, manifest = build(tmp_path)
    freeze(monkeypatch, archive)
    monkeypatch.setattr(verifier, "EXPECTED_COUNTS", {**SYNTHETIC_COUNTS, group: 99})
    with pytest.raises(ValueError, match="group counts do not match"):
        verifier.verify_archive(archive, manifest)


def test_cli_exit_zero_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archive, manifest = build(tmp_path)
    digest = freeze(monkeypatch, archive)
    assert run_main(monkeypatch, archive, manifest)[0] == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["archive_sha256"] == digest


def test_cli_exit_nonzero_with_validation_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archive, manifest = build(tmp_path)
    freeze(monkeypatch, archive)
    monkeypatch.setattr(verifier, "EXPECTED_ARCHIVE_SHA256", "0" * 64)
    code, _ = run_main(monkeypatch, archive, manifest)
    assert code not in (0, None)
    assert "validation FAILED" in capsys.readouterr().err


def test_real_cli_process_fails_cleanly_on_non_zip(tmp_path: Path) -> None:
    bogus = tmp_path / "not.zip"
    bogus.write_bytes(b"not a zip")
    done = subprocess.run(
        [sys.executable, "-I", str(MODULE), str(bogus)], capture_output=True, text=True, check=False
    )
    assert done.returncode != 0
    assert "validation FAILED" in done.stderr
    assert "Traceback" not in done.stderr


def test_reject_extra_member(tmp_path: Path) -> None:
    archive, manifest = build(tmp_path, [*base_members(), ("state/extra.json", b"{}")])
    with pytest.raises(ValueError, match=r"missing=0, unexpected=1"):
        loose(archive, manifest)


def test_reject_missing_member(tmp_path: Path) -> None:
    archive, manifest = build(tmp_path, base_members()[:-1])
    with pytest.raises(ValueError, match=r"missing=1, unexpected=0"):
        loose(archive, manifest)


def test_reject_duplicate_zip_path(tmp_path: Path) -> None:
    members = base_members()
    archive, manifest = build(tmp_path, [*members, members[4]])
    with pytest.raises(ValueError, match="Duplicate path in ZIP"):
        loose(archive, manifest)


def test_reject_unknown_group(tmp_path: Path) -> None:
    archive, manifest = build(tmp_path, [*base_members(), ("bogus/x.json", b"{}")])
    with pytest.raises(ValueError, match="Unexpected V5 archive group"):
        loose(archive, manifest)


def test_reject_altered_content_under_same_name(tmp_path: Path) -> None:
    members = base_members()
    members[4] = ("state/safe.json", b'{"status":"verified_xxx"}')  # same length, new bytes
    assert len(members[4][1]) == len(base_members()[4][1])
    archive, manifest = build(tmp_path, members)
    with pytest.raises(ValueError, match=r"missing=1, unexpected=1"):
        loose(archive, manifest)


@pytest.mark.parametrize("fault", ["truncated", "corrupt", "not_gzip"])
def test_reject_unreadable_gzip_member(tmp_path: Path, fault: str) -> None:
    logical = base_members()
    good = stored("raw_previews/one.json.gz", logical[5][1])
    bad = {"truncated": good[:-12], "corrupt": good[:12] + b"\xff" * 8, "not_gzip": b"plain"}[fault]
    raw = [(n, stored(n, c)) for n, c in logical]
    raw[5] = ("raw_previews/one.json.gz", bad)
    archive = write_zip(tmp_path / "a.zip", raw)
    manifest = write_manifest(tmp_path / "m.csv", logical)
    with pytest.raises(ValueError, match="Unreadable ZIP member"):
        loose(archive, manifest)


def test_manifest_json_agrees_with_verifier_constants_and_real_csv() -> None:
    meta = json.loads((PROVENANCE / "manifest.json").read_text(encoding="utf-8"))
    csv_path = PROVENANCE / meta["source_multiset_file"]
    counts = verifier.read_manifest(csv_path)
    assert meta["original_archive_sha256"] == verifier.EXPECTED_ARCHIVE_SHA256
    assert meta["original_archive_bytes"] == verifier.EXPECTED_ARCHIVE_BYTES
    assert meta["group_counts"] == verifier.EXPECTED_COUNTS
    assert meta["source_file_count"] == sum(verifier.EXPECTED_COUNTS.values()) == 963
    assert meta["source_file_count"] == sum(counts.values())
    assert len(counts) == 962
    assert meta["source_multiset_sha256"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert meta["group_counts"] == {
        g: sum(n for (kind, _s, _d), n in counts.items() if kind == g) for g in meta["group_counts"]
    }
    assert meta["fully_verified_99_card_decks"] == 0


def test_reject_member_larger_than_manifest_maximum(tmp_path: Path) -> None:
    archive, manifest = build(
        tmp_path, [*base_members(), ("state/big.json", b"y" * (MAX_LOGICAL + 1))]
    )
    with pytest.raises(ValueError, match="maximum logical size"):
        loose(archive, manifest)


def test_reject_gzip_expanding_beyond_manifest_maximum(tmp_path: Path) -> None:
    members = base_members()
    members[5] = (
        "raw_previews/one.json.gz",
        b"\0" * (MAX_LOGICAL * 10),
    )  # small file_size, big logical size
    logical = base_members()
    raw = [(n, stored(n, c)) for n, c in members]
    assert len(raw[5][1]) < MAX_LOGICAL
    archive = write_zip(tmp_path / "a.zip", raw)
    manifest = write_manifest(tmp_path / "m.csv", logical)
    with pytest.raises(ValueError, match="maximum logical size"):
        loose(archive, manifest)


def test_member_at_exact_maximum_is_accepted(tmp_path: Path) -> None:
    archive, manifest = build(tmp_path)  # the index CSV is exactly the maximum logical size
    assert loose(archive, manifest)["status"] == "PASS"


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (
            "group,uncompressed_bytes,sha256\nstate,1," + "a" * 64 + "\n",
            "missing a required column",
        ),
        ("group,uncompressed_bytes,sha256,count\nstate,1\n", "malformed row"),
        ("group,uncompressed_bytes,sha256,count\nstate,1,x,1,extra\n", "malformed row"),
    ],
)
def test_malformed_manifest_is_value_error_and_cli_reports_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    text: str,
    match: str,
) -> None:
    archive, _ = build(tmp_path)
    broken = tmp_path / "broken.csv"
    broken.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        verifier.read_manifest(broken)
    code, _ = run_main(monkeypatch, archive, broken)
    assert code not in (0, None)
    assert "validation FAILED" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("index", "match"),
    [
        (
            "id,status\n" + "".join(f"t{i},DECK_NOT_VERIFIED\n" for i in range(470)),
            "required column",
        ),
        (INDEX.replace("test-7,DECK_NOT_VERIFIED,\n", "test-7\n"), "malformed row"),
    ],
)
def test_malformed_index_csv_is_value_error_and_cli_reports_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    index: str,
    match: str,
) -> None:
    members = base_members()
    members[0] = ("01_EDHREC_DECK_INDEX.csv", index.encode())
    archive = write_zip(tmp_path / "a.zip", [(n, stored(n, c)) for n, c in members])
    manifest = write_manifest(tmp_path / "m.csv", members)
    freeze(monkeypatch, archive)
    with zipfile.ZipFile(archive) as source, pytest.raises(ValueError, match=match):
        verifier.verify_no_complete_decks(source)
    code, _ = run_main(monkeypatch, archive, manifest)
    assert code not in (0, None)
    assert "validation FAILED" in capsys.readouterr().err


class _RecordingStream:
    """Stands in for a member stream and records every requested read size."""

    def __init__(self, sizes: list[int | None]) -> None:
        self.sizes = sizes

    def __enter__(self) -> _RecordingStream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, size: int | None = None) -> bytes:
        self.sizes.append(size)
        return b"x" * 5


class _RecordingZip:
    def __init__(self, sizes: list[int | None]) -> None:
        self.sizes = sizes

    def open(self, item: zipfile.ZipInfo) -> _RecordingStream:
        return _RecordingStream(self.sizes)


@pytest.mark.parametrize("gz", [False, True])
def test_member_reads_are_requested_with_a_bound(gz: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap is enforced while reading: no unbounded read() is ever requested."""
    sizes: list[int | None] = []
    monkeypatch.setattr(
        verifier.gzip, "GzipFile", lambda fileobj: _RecordingStream(sizes), raising=True
    )
    item = zipfile.ZipInfo("raw_previews/one.json.gz" if gz else "state/one.json")
    item.file_size = 3
    data = verifier.read_member(_RecordingZip(sizes), item, 7, gz=gz)
    assert sizes == [8]
    assert data == b"x" * 5


def test_plain_member_with_oversized_header_is_rejected_before_reading() -> None:
    sizes: list[int | None] = []
    item = zipfile.ZipInfo("state/one.json")
    item.file_size = 8
    with pytest.raises(ValueError, match="maximum logical size"):
        verifier.read_member(_RecordingZip(sizes), item, 7, gz=False)
    assert sizes == []
