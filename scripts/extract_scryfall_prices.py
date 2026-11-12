#!/usr/bin/env python3
"""Generate a price snapshot from Scryfall Default Cards bulk dataset.

Source and Provenance:
- Source: Scryfall Bulk Data API (https://api.scryfall.com/bulk-data, type: "default_cards")
- Bulk snapshot download URI format:
  https://data.scryfall.io/default-cards/default-cards-<timestamp>.jsonl.gz
- Scryfall Attribution / License Notice:
  Card data and prices courtesy of Scryfall (https://scryfall.com).
  Magic: The Gathering is copyright Wizards of the Coast LLC.
  Scryfall is not affiliated with Wizards of the Coast. Scryfall data is
  provided under Scryfall's API Terms of Service.

Important Pricing Semantics:
- Hinweis: Preis = Momentaufnahme, kein Verlauf.
- Missing price values remain completely empty in CSV (never replaced by 0 or estimates).

Status Vocabulary:
- AVAILABLE: Printing found with price data in the bulk dataset.
- NOT_FOUND: scryfall_id not found in the bulk dataset.
- BLOCKED: Network / upstream rate limiting prevents fetching bulk data.
- UNKNOWN: Status could not be determined.

No private collection, deck, or owner data is stored or processed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

SCRYFALL_BULK_METADATA_URL = "https://api.scryfall.com/bulk-data"
USER_AGENT = (
    "CommanderPlaytestLab-Research/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CSV_COLUMNS: list[str] = [
    "scryfall_id",
    "oracle_id",
    "name",
    "set",
    "collector_number",
    "eur",
    "eur_foil",
    "usd",
    "usd_foil",
    "tix",
    "snapshot_date",
]


@dataclass(frozen=True)
class PriceRecord:
    scryfall_id: str
    oracle_id: str
    name: str
    set_code: str
    collector_number: str
    eur: str
    eur_foil: str
    usd: str
    usd_foil: str
    tix: str
    snapshot_date: str

    def has_any_price(self) -> bool:
        return any(bool(v) for v in (self.eur, self.eur_foil, self.usd, self.usd_foil, self.tix))

    def to_row(self) -> dict[str, str]:
        return {
            "scryfall_id": self.scryfall_id,
            "oracle_id": self.oracle_id,
            "name": self.name,
            "set": self.set_code,
            "collector_number": self.collector_number,
            "eur": self.eur,
            "eur_foil": self.eur_foil,
            "usd": self.usd,
            "usd_foil": self.usd_foil,
            "tix": self.tix,
            "snapshot_date": self.snapshot_date,
        }


@dataclass(frozen=True)
class PriceSnapshotStats:
    total_bulk_lines: int
    input_ids_count: int
    matched_count: int
    missing_ids: list[str]
    ids_without_any_price: list[str]
    parse_errors_count: int


def load_target_scryfall_ids(path: Path) -> list[str]:
    """Load target scryfall_ids from a local CSV (column 'scryfall_id') or plain text file."""
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    ids: list[str] = []
    seen: set[str] = set()

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    lines = content.splitlines()
    first_line = lines[0].strip().lower()

    if "scryfall_id" in first_line:
        # Parse as CSV
        reader = csv.DictReader(lines)
        for row in reader:
            val = row.get("scryfall_id", "").strip().lower()
            if val and val not in seen:
                seen.add(val)
                ids.append(val)
    else:
        # Fallback: line-by-line list of IDs
        for line in lines:
            val = line.strip().lower()
            if val and not val.startswith("#") and val not in seen:
                seen.add(val)
                ids.append(val)

    return ids


def stream_card_objects_from_stream(stream: IO[str]) -> Iterator[tuple[dict[str, object], int]]:
    """Stream card dictionary objects line-by-line from a JSONL text stream."""
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
        yield obj, idx


def stream_card_objects(path: Path) -> Iterator[tuple[dict[str, object], int]]:
    """Stream card objects from .jsonl, .jsonl.gz, or .json file."""
    if str(path).endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            yield from stream_card_objects_from_stream(f)
    else:
        with path.open("rt", encoding="utf-8") as f:
            yield from stream_card_objects_from_stream(f)


def parse_price_value(raw: object) -> str:
    """Normalize a raw price field into string or empty string. Never return 0 for None."""
    if raw is None:
        return ""
    if isinstance(raw, (str, int, float)):
        s = str(raw).strip()
        return s
    return ""


def extract_price_record(card: dict[str, object], line_idx: int, snapshot_date: str) -> PriceRecord:
    """Validate and convert card dictionary into a PriceRecord."""
    scryfall_id = card.get("id")
    if not isinstance(scryfall_id, str) or not scryfall_id.strip():
        raise ValueError(f"Line #{line_idx}: Missing or invalid card 'id': {scryfall_id!r}")

    oracle_id = card.get("oracle_id")
    oracle_id_str = str(oracle_id).strip() if isinstance(oracle_id, str) else ""

    name = card.get("name")
    if not isinstance(name, str):
        name = ""

    set_code = card.get("set")
    if not isinstance(set_code, str):
        set_code = ""

    collector_number = card.get("collector_number")
    col_str = str(collector_number).strip() if collector_number is not None else ""

    raw_prices = card.get("prices")
    prices_dict: dict[str, object] = raw_prices if isinstance(raw_prices, dict) else {}

    eur = parse_price_value(prices_dict.get("eur"))
    eur_foil = parse_price_value(prices_dict.get("eur_foil"))
    usd = parse_price_value(prices_dict.get("usd"))
    usd_foil = parse_price_value(prices_dict.get("usd_foil"))
    tix = parse_price_value(prices_dict.get("tix"))

    return PriceRecord(
        scryfall_id=scryfall_id.strip().lower(),
        oracle_id=oracle_id_str,
        name=name.strip(),
        set_code=set_code.strip().lower(),
        collector_number=col_str,
        eur=eur,
        eur_foil=eur_foil,
        usd=usd,
        usd_foil=usd_foil,
        tix=tix,
        snapshot_date=snapshot_date,
    )


def filter_prices_from_stream(
    card_stream: Iterator[tuple[dict[str, object], int]],
    target_ids: set[str],
    snapshot_date: str,
) -> tuple[list[PriceRecord], PriceSnapshotStats]:
    """Stream bulk cards, extract matched target printings, and compute statistics."""
    total_lines = 0
    parse_errors = 0
    matched: list[PriceRecord] = []
    matched_ids: set[str] = set()
    ids_without_any_price: list[str] = []

    for card_obj, line_idx in card_stream:
        total_lines += 1
        card_id_raw = card_obj.get("id")
        if not isinstance(card_id_raw, str):
            continue
        card_id = card_id_raw.strip().lower()

        if card_id in target_ids:
            try:
                record = extract_price_record(card_obj, line_idx, snapshot_date)
            except Exception as exc:
                parse_errors += 1
                raise ValueError(f"Parse error at line {line_idx}: {exc}") from exc

            matched.append(record)
            matched_ids.add(card_id)
            if not record.has_any_price():
                ids_without_any_price.append(card_id)

    missing_ids = sorted(list(target_ids - matched_ids))
    ids_without_any_price.sort()

    stats = PriceSnapshotStats(
        total_bulk_lines=total_lines,
        input_ids_count=len(target_ids),
        matched_count=len(matched),
        missing_ids=missing_ids,
        ids_without_any_price=ids_without_any_price,
        parse_errors_count=parse_errors,
    )

    return matched, stats


def write_price_csv(records: list[PriceRecord], out_path: Path) -> None:
    """Write PriceRecord objects to CSV."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in records:
            writer.writerow(r.to_row())


def format_price_counting_protocol(stats: PriceSnapshotStats) -> str:
    """Format counting protocol report for stdout."""
    lines: list[str] = [
        "=== Scryfall Preis-Snapshot Zählprotokoll ===",
        f"Bulk-Zeilen gesamt: {stats.total_bulk_lines}",
        f"Eingabe-IDs: {stats.input_ids_count}",
        f"Treffer (AVAILABLE): {stats.matched_count}",
        f"IDs ohne Treffer (NOT_FOUND): {len(stats.missing_ids)}",
    ]
    if stats.missing_ids:
        lines.append("Liste der IDs ohne Treffer (NOT_FOUND):")
        for mid in stats.missing_ids:
            lines.append(f"  - {mid}")

    lines.append(f"IDs ohne jeden Preis: {len(stats.ids_without_any_price)}")
    if stats.ids_without_any_price:
        lines.append("Liste der IDs ohne jeden Preis:")
        for no_price_id in stats.ids_without_any_price:
            lines.append(f"  - {no_price_id}")

    lines.append(f"Parse-Fehler: {stats.parse_errors_count}")
    return "\n".join(lines)


def fetch_default_cards_metadata() -> dict[str, str]:
    """Fetch download URL and timestamp for Scryfall default-cards bulk."""
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
        if isinstance(item, dict) and item.get("type") == "default_cards":
            uri = item.get("download_uri") or item.get("jsonl_download_uri")
            updated_at = item.get("updated_at")
            if isinstance(uri, str) and isinstance(updated_at, str):
                return {"download_uri": uri, "updated_at": updated_at}
    raise RuntimeError("No 'default_cards' bulk entry found in Scryfall bulk metadata")


def download_file(url: str, dest: Path) -> Path:
    """Download remote bulk file via chunked streaming."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract price snapshot from Scryfall Default Cards bulk dataset."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        required=True,
        help="Path to local CSV containing scryfall_id column (or line-delimited IDs).",
    )
    parser.add_argument(
        "--bulk",
        type=Path,
        default=None,
        help="Path to local default-cards bulk file (.jsonl, .jsonl.gz).",
    )
    parser.add_argument(
        "--download-to",
        type=Path,
        default=None,
        help="If --bulk is omitted, download bulk file to this path and process it.",
    )
    parser.add_argument(
        "--snapshot-date",
        type=str,
        default=None,
        help="Snapshot date (YYYY-MM-DD). Defaults to bulk updated_at date or today's UTC date.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Path to output CSV file. Defaults to scryfall_prices_<snapshot_date>.csv.",
    )
    args = parser.parse_args(argv)

    snapshot_date = args.snapshot_date
    bulk_path = args.bulk
    if bulk_path is None:
        meta = fetch_default_cards_metadata()
        uri = meta["download_uri"]
        print(f"Discovered Scryfall default-cards bulk: {uri} (updated: {meta['updated_at']})")
        if not snapshot_date:
            snapshot_date = meta["updated_at"][:10]
        target_dest = args.download_to or Path("tmp") / Path(uri).name
        print(f"Downloading default-cards bulk to {target_dest}...")
        bulk_path = download_file(uri, target_dest)

    if not snapshot_date:
        snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")

    out_path = args.out or Path(f"scryfall_prices_{snapshot_date}.csv")

    print(f"Loading target scryfall_ids from {args.input_csv}...")
    target_ids = set(load_target_scryfall_ids(args.input_csv))
    print(f"Loaded {len(target_ids)} distinct target scryfall_ids.")

    print(f"Streaming bulk cards from {bulk_path} (snapshot_date: {snapshot_date})...")
    try:
        stream = stream_card_objects(bulk_path)
        matched_records, stats = filter_prices_from_stream(stream, target_ids, snapshot_date)
    except Exception as exc:
        print(f"ERROR: Streaming default cards failed: {exc}", file=sys.stderr)
        return 1

    if stats.parse_errors_count > 0:
        print(
            f"ERROR: Encountered {stats.parse_errors_count} parse errors. Aborting.",
            file=sys.stderr,
        )
        return 1

    print(f"Writing {len(matched_records)} matched price records to {out_path}...")
    write_price_csv(matched_records, out_path)

    print()
    print(format_price_counting_protocol(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
