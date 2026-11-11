"""Verify an EDHREC V5 ZIP against its public, filename-free source checksum multiset.

No extraction, network calls, deck data publication or import side effects.
The Drive V011 index hashes the logical decompressed bytes of *.json.gz files.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

HASH_SIZE = 64
EXPECTED_ARCHIVE_SHA256 = "877a113f54aa73e02a67fc716d897c32718dd9ba7898b7a90d4e733a871d1f0d"
EXPECTED_ARCHIVE_BYTES = 16669766
EXPECTED_COUNTS = {"state": 473, "raw_previews": 470, "diagnose": 8, "exports": 12}
DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1] / "data/provenance/edhrec_v5_20261110/source_multiset.csv"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path) -> Counter[tuple[str, int, str]]:
    expected: Counter[tuple[str, int, str]] = Counter()
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            group = row["group"]
            size = int(row["uncompressed_bytes"])
            digest = row["sha256"]
            count = int(row["count"])
            if group not in EXPECTED_COUNTS or size < 0 or count <= 0:
                raise ValueError("Invalid group, size or count in EDHREC source manifest")
            if len(digest) != HASH_SIZE or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Invalid SHA-256 value in EDHREC source manifest")
            if (group, size, digest) in expected:
                raise ValueError("Duplicate source multiset key in EDHREC manifest")
            expected[(group, size, digest)] = count
    return expected


def verify_no_complete_decks(source: zipfile.ZipFile) -> dict[str, int]:
    """Check the V5 status data, not just the archive checksum.

    EDHREC preview IDs are never evidence of a verified 99-card mainboard.
    """
    required = {
        "01_EDHREC_DECK_INDEX.csv",
        "02_DECKS_COMPACT_ELIGIBLE.jsonl",
        "02_MAINBOARD_CARDS_NORMALIZED.csv",
        "05_BRACKET1_EXHIBITION_EXCLUDED.csv",
    }
    if not required.issubset(source.namelist()):
        raise ValueError("EDHREC V5 is missing a required deck-verification export")
    index_text = source.read("01_EDHREC_DECK_INDEX.csv").decode("utf-8-sig")
    index = list(csv.DictReader(io.StringIO(index_text)))
    if (
        len(index) != 470
        or len({row["id"] for row in index}) != 470
        or any(row["status"] != "DECK_NOT_VERIFIED" for row in index)
        or any(row["fingerprint"].strip() for row in index)
    ):
        raise ValueError("EDHREC V5 preview index is not the expected unverified 470-row cohort")
    if source.read("02_DECKS_COMPACT_ELIGIBLE.jsonl").strip():
        raise ValueError("EDHREC V5 contains unexpected purported verified deck records")
    mainboard_text = source.read("02_MAINBOARD_CARDS_NORMALIZED.csv").decode("utf-8-sig")
    mainboard = list(csv.DictReader(io.StringIO(mainboard_text)))
    if mainboard:
        raise ValueError("EDHREC V5 has mainboard rows requiring separate legality verification")
    excluded_text = source.read("05_BRACKET1_EXHIBITION_EXCLUDED.csv").decode("utf-8-sig")
    excluded = list(csv.DictReader(io.StringIO(excluded_text)))
    if len(excluded) != 2:
        raise ValueError("EDHREC V5 Bracket 1 exclusion evidence count changed")
    return {
        "source_preview_ids": len(index),
        "verified_complete_99_card_decks": 0,
        "excluded_bracket1_preview_ids": len(excluded),
    }


def verify_archive(
    archive: Path,
    manifest: Path,
    *,
    strict_archive: bool = True,
    strict_counts: bool = True,
) -> dict[str, object]:
    expected = read_manifest(manifest)
    if strict_archive:
        if archive.stat().st_size != EXPECTED_ARCHIVE_BYTES:
            raise ValueError("Archive byte size differs from the frozen V5 source")
        with archive.open("rb") as stream:
            file_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if file_digest != EXPECTED_ARCHIVE_SHA256:
            raise ValueError("Archive SHA-256 differs from the frozen V5 source")
    actual: Counter[tuple[str, int, str]] = Counter()
    groups: Counter[str] = Counter()
    evidence: dict[str, int] | None = None
    with zipfile.ZipFile(archive) as source:
        names: set[str] = set()
        for item in source.infolist():
            if item.is_dir():
                continue
            name = item.filename.replace("\\", "/")
            if name in names:
                raise ValueError("Duplicate path in ZIP")
            names.add(name)
            group = name.split("/", maxsplit=1)[0] if "/" in name else "exports"
            if group not in EXPECTED_COUNTS:
                raise ValueError("Unexpected V5 archive group")
            data = source.read(item)
            if name.endswith(".json.gz"):
                data = gzip.decompress(data)
            actual[(group, len(data), sha256(data))] += 1
            groups[group] += 1
        if strict_counts:
            evidence = verify_no_complete_decks(source)
    if actual != expected:
        missing = sum((expected - actual).values())
        unexpected = sum((actual - expected).values())
        raise ValueError(
            f"EDHREC V5 checksum multiset mismatch: missing={missing}, unexpected={unexpected}"
        )
    if strict_counts and dict(groups) != EXPECTED_COUNTS:
        raise ValueError("EDHREC V5 source group counts do not match the snapshot manifest")
    return {
        "status": "PASS",
        "archive_sha256": EXPECTED_ARCHIVE_SHA256 if strict_archive else None,
        "verified_source_files": sum(groups.values()),
        "unique_checksum_keys": len(actual),
        "source_groups": dict(sorted(groups.items())),
        "deck_evidence": evidence,
        "verified_complete_99_card_decks": 0,
        "active_studio_import": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Local ERGEBNISSE_EDHREC_V5.zip")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_archive(args.archive, args.manifest), sort_keys=True))
    except (ValueError, OSError, zipfile.BadZipFile, gzip.BadGzipFile) as exc:
        parser.exit(1, f"EDHREC V5 validation FAILED: {exc}\n")


if __name__ == "__main__":
    main()
