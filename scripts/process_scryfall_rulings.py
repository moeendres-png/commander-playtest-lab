#!/usr/bin/env python3
"""Process and filter Scryfall Rulings bulk dataset.

Source and Provenance:
- Source: Scryfall Bulk Data API (https://api.scryfall.com/bulk-data, type: "rulings")
- Bulk snapshot download URI format:
  https://data.scryfall.io/rulings/rulings-<timestamp>.jsonl.gz
- Scryfall Attribution / License Notice:
  Card data and rulings courtesy of Scryfall (https://scryfall.com).
  Magic: The Gathering is copyright Wizards of the Coast LLC.
  Scryfall is not affiliated with Wizards of the Coast. Scryfall data is
  provided under Scryfall's API Terms of Service.

Status Vocabulary:
- AVAILABLE: Rulings found for the oracle_id in the bulk dataset.
- NOT_FOUND: No rulings exist for the oracle_id in the bulk dataset.
- BLOCKED: Network / upstream rate limiting prevents fetching bulk data.
- UNKNOWN: Status could not be determined.

No private collection, deck, or owner data is stored or processed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

SCRYFALL_BULK_METADATA_URL = "https://api.scryfall.com/bulk-data"
USER_AGENT = (
    "CommanderPlaytestLab-Research/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class RulingRecord:
    oracle_id: str
    published_at: str
    source: str
    comment: str
    object_type: str = "ruling"

    def to_dict(self) -> dict[str, str]:
        return {
            "object": self.object_type,
            "oracle_id": self.oracle_id,
            "source": self.source,
            "published_at": self.published_at,
            "comment": self.comment,
        }


@dataclass(frozen=True)
class RulingsStats:
    total_bulk_rulings: int
    distinct_bulk_oracle_ids: int
    input_ids_count: int
    matched_rulings_count: int
    matched_oracle_ids_count: int
    missing_oracle_ids: list[str]
    parse_errors_count: int


def validate_ruling_dict(obj: dict[str, object], index: int) -> RulingRecord:
    """Validate a raw ruling object against required fields."""
    if not isinstance(obj, dict):
        raise ValueError(f"Record #{index} is not a JSON object: {type(obj).__name__}")

    oracle_id = obj.get("oracle_id")
    if not isinstance(oracle_id, str) or not oracle_id.strip():
        raise ValueError(f"Record #{index}: invalid or missing 'oracle_id': {oracle_id!r}")

    published_at = obj.get("published_at")
    if (
        not isinstance(published_at, str)
        or not published_at.strip()
        or not DATE_PATTERN.match(published_at.strip())
    ):
        raise ValueError(
            f"Record #{index}: invalid or missing 'published_at' (expected YYYY-MM-DD): {published_at!r}"
        )

    source = obj.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"Record #{index}: invalid or missing 'source': {source!r}")

    comment = obj.get("comment")
    if not isinstance(comment, str):
        raise ValueError(f"Record #{index}: invalid or missing 'comment': {type(comment).__name__}")

    object_type = obj.get("object")
    obj_str = str(object_type) if isinstance(object_type, str) else "ruling"

    return RulingRecord(
        oracle_id=oracle_id.strip().lower(),
        published_at=published_at.strip(),
        source=source.strip(),
        comment=comment,
        object_type=obj_str,
    )


def iter_bulk_rulings_from_stream(stream: IO[str]) -> Iterator[RulingRecord]:
    """Iterate through rulings from a text stream (supporting JSONL and JSON array)."""
    first_char = ""
    while True:
        pos = stream.tell()
        ch = stream.read(1)
        if not ch:
            break
        if not ch.isspace():
            first_char = ch
            stream.seek(pos)
            break

    if first_char == "[":
        raw_content = stream.read()
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to decode JSON array: {exc}") from exc
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array, got {type(data).__name__}")
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"Item #{idx} in JSON array is not a dict")
            yield validate_ruling_dict(item, idx)
    else:
        for idx, line in enumerate(stream, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                obj = json.loads(line_str)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line #{idx}: Invalid JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"Line #{idx}: Expected JSON object, got {type(obj).__name__}")
            yield validate_ruling_dict(obj, idx)


def iter_bulk_rulings(path: Path) -> Iterator[RulingRecord]:
    """Stream RulingRecord objects from a file (.jsonl, .jsonl.gz, or .json)."""
    if str(path).endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            yield from iter_bulk_rulings_from_stream(f)
    else:
        with path.open("rt", encoding="utf-8") as f:
            yield from iter_bulk_rulings_from_stream(f)


def load_target_oracle_ids(path: Path) -> list[str]:
    """Load oracle_ids from a local text file, one per line."""
    if not path.is_file():
        raise FileNotFoundError(f"Oracle IDs file not found: {path}")

    ids: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        lowered = cleaned.lower()
        if lowered not in seen:
            seen.add(lowered)
            ids.append(lowered)
    return ids


def filter_rulings(
    records: Iterator[RulingRecord],
    target_oracle_ids: set[str],
) -> tuple[list[RulingRecord], RulingsStats]:
    """Filter rulings to matching target_oracle_ids and compute counts."""
    total_bulk = 0
    distinct_oracle_ids: set[str] = set()
    matched_rulings: list[RulingRecord] = []
    matched_ids: set[str] = set()
    parse_errors = 0

    for rec in records:
        total_bulk += 1
        distinct_oracle_ids.add(rec.oracle_id)
        if rec.oracle_id in target_oracle_ids:
            matched_rulings.append(rec)
            matched_ids.add(rec.oracle_id)

    # Sort deterministically by oracle_id, published_at, then comment
    matched_rulings.sort(key=lambda r: (r.oracle_id, r.published_at, r.comment))

    missing_ids = sorted(list(target_oracle_ids - matched_ids))

    stats = RulingsStats(
        total_bulk_rulings=total_bulk,
        distinct_bulk_oracle_ids=len(distinct_oracle_ids),
        input_ids_count=len(target_oracle_ids),
        matched_rulings_count=len(matched_rulings),
        matched_oracle_ids_count=len(matched_ids),
        missing_oracle_ids=missing_ids,
        parse_errors_count=parse_errors,
    )

    return matched_rulings, stats


def write_rulings_jsonl(rulings: list[RulingRecord], out_path: Path) -> None:
    """Write ruling records as JSONL."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rulings:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")


def fetch_rulings_bulk_metadata() -> dict[str, str]:
    """Fetch download URL and timestamp for Scryfall rulings bulk data."""
    req = urllib.request.Request(
        SCRYFALL_BULK_METADATA_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} fetching bulk metadata")
        payload = json.loads(resp.read().decode("utf-8"))

    data = payload.get("data", [])
    if not isinstance(data, list):
        raise ValueError("Invalid bulk metadata response: 'data' is not a list")

    for item in data:
        if isinstance(item, dict) and item.get("type") == "rulings":
            uri = item.get("download_uri") or item.get("jsonl_download_uri")
            updated_at = item.get("updated_at")
            if isinstance(uri, str) and isinstance(updated_at, str):
                return {"download_uri": uri, "updated_at": updated_at}
    raise RuntimeError("No 'rulings' bulk entry found in Scryfall bulk metadata")


def download_file(url: str, dest: Path) -> Path:
    """Download a remote file using chunked streaming."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req) as resp, dest.open("wb") as out_f:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} downloading {url}")
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out_f.write(chunk)
    return dest


def format_counting_protocol(stats: RulingsStats) -> str:
    """Format counting protocol report for stdout."""
    lines: list[str] = [
        "=== Scryfall Rulings Zählprotokoll ===",
        f"Gesamtzahl Rulings im Bulk: {stats.total_bulk_rulings}",
        f"Distinkte Oracle-IDs im Bulk: {stats.distinct_bulk_oracle_ids}",
        f"Eingabe-Oracle-IDs: {stats.input_ids_count}",
        f"Treffer (Rulings zu Eingabe-IDs): {stats.matched_rulings_count}",
        f"Treffer (Oracle-IDs mit Rulings, AVAILABLE): {stats.matched_oracle_ids_count}",
        f"Eingabe-IDs ohne Rulings (NOT_FOUND): {len(stats.missing_oracle_ids)}",
    ]
    if stats.missing_oracle_ids:
        lines.append("Liste der IDs ohne Rulings (NOT_FOUND):")
        for oid in stats.missing_oracle_ids:
            lines.append(f"  - {oid}")
    lines.append(f"Parse-Fehler: {stats.parse_errors_count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Filter Scryfall rulings bulk data by a list of oracle_ids."
    )
    parser.add_argument(
        "--oracle-ids",
        type=Path,
        required=True,
        help="Path to local text file containing oracle_ids (one per line).",
    )
    parser.add_argument(
        "--bulk",
        type=Path,
        default=None,
        help="Path to local rulings bulk file (.jsonl, .jsonl.gz, .json).",
    )
    parser.add_argument(
        "--download-to",
        type=Path,
        default=None,
        help="If --bulk is omitted, download bulk file to this path and process it.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Path to output JSONL file with filtered rulings.",
    )
    args = parser.parse_args(argv)

    bulk_path = args.bulk
    if bulk_path is None:
        meta = fetch_rulings_bulk_metadata()
        uri = meta["download_uri"]
        print(f"Discovered Scryfall rulings bulk: {uri} (updated: {meta['updated_at']})")
        target_dest = args.download_to or Path("tmp") / Path(uri).name
        print(f"Downloading rulings bulk to {target_dest}...")
        bulk_path = download_file(uri, target_dest)

    print(f"Reading target Oracle IDs from {args.oracle_ids}...")
    target_ids = set(load_target_oracle_ids(args.oracle_ids))
    print(f"Loaded {len(target_ids)} distinct target Oracle IDs.")

    print(f"Processing rulings bulk from {bulk_path}...")
    try:
        records_iter = iter_bulk_rulings(bulk_path)
        matched_rulings, stats = filter_rulings(records_iter, target_ids)
    except Exception as exc:
        print(f"ERROR: Failed processing rulings bulk: {exc}", file=sys.stderr)
        return 1

    if stats.parse_errors_count > 0:
        print(
            f"ERROR: Encountered {stats.parse_errors_count} parse errors. Aborting.",
            file=sys.stderr,
        )
        return 1

    print(f"Writing {len(matched_rulings)} matched rulings to {args.out}...")
    write_rulings_jsonl(matched_rulings, args.out)

    print()
    print(format_counting_protocol(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
