#!/usr/bin/env python3
"""Generate EDHTop16 tournament signal CSV for Chulane and the 1,414 store collection cards.

Cross-references EDHTop16 tournament staples (from data/research/edhtop16_probe_20261112.csv)
against the collection cards in the Studio store.

Output format (data/research/chulane_edhtop16_signal_20261112.csv):
oracle_id,card_name,in_top16_probe,top16_rank,top16_entries

Rules:
- Strictly objective counts and rankings.
- No personal collection, deck, or owner data.
- Unmatched cards have in_top16_probe=0, empty top16_rank and empty top16_entries.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

TARGET_COMMANDER = "Chulane, Teller of Tales"
CSV_COLUMNS: list[str] = [
    "oracle_id",
    "card_name",
    "in_top16_probe",
    "top16_rank",
    "top16_entries",
]


@dataclass(frozen=True)
class Top16Staple:
    card_name: str
    rank: int
    play_rate: float
    entries_n: int


def load_edhtop16_chulane_staples(probe_path: Path) -> dict[str, Top16Staple]:
    """Read probe CSV and return mapping of card_name -> Top16Staple for Chulane."""
    staples: dict[str, Top16Staple] = {}
    with probe_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rank = 1
        for row in reader:
            if row.get("commander") == TARGET_COMMANDER:
                name = row["card_name"].strip()
                play_rate = float(row["play_rate"]) if row.get("play_rate") else 0.0
                entries_n = int(row["entries_n"]) if row.get("entries_n") else 0
                staples[name] = Top16Staple(
                    card_name=name,
                    rank=rank,
                    play_rate=play_rate,
                    entries_n=entries_n,
                )
                rank += 1
    return staples


def load_store_cards(db_path: Path) -> list[tuple[str, str]]:
    """Load all (oracle_id, oracle_name) from Studio SQLite card table."""
    resolved_path = db_path / "studio.sqlite3" if db_path.is_dir() else db_path
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Studio database not found at {resolved_path}")
    with sqlite3.connect(resolved_path) as conn:
        rows = conn.execute(
            "SELECT oracle_id, oracle_name FROM card ORDER BY oracle_name ASC, oracle_id ASC"
        ).fetchall()
        return [(str(row[0]), str(row[1])) for row in rows]


def generate_signal_rows(
    cards: list[tuple[str, str]],
    staples: dict[str, Top16Staple],
) -> list[dict[str, str]]:
    """Match store cards against EDHTop16 Chulane staples."""
    rows: list[dict[str, str]] = []
    for oracle_id, card_name in cards:
        staple = staples.get(card_name)
        if staple is not None:
            rows.append(
                {
                    "oracle_id": oracle_id,
                    "card_name": card_name,
                    "in_top16_probe": "1",
                    "top16_rank": str(staple.rank),
                    "top16_entries": str(staple.entries_n),
                }
            )
        else:
            rows.append(
                {
                    "oracle_id": oracle_id,
                    "card_name": card_name,
                    "in_top16_probe": "0",
                    "top16_rank": "",
                    "top16_entries": "",
                }
            )
    return rows


def write_signal_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write rows to CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        "-d",
        type=Path,
        default=Path.home() / ".local/share/commander-studio",
        help="Path to Studio data dir or studio.sqlite3",
    )
    parser.add_argument(
        "--probe",
        "-p",
        type=Path,
        default=Path("data/research/edhtop16_probe_20261112.csv"),
        help="Path to EDHTop16 probe CSV",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/research/chulane_edhtop16_signal_20261112.csv"),
        help="Path to output signal CSV",
    )
    args = parser.parse_args()

    staples = load_edhtop16_chulane_staples(args.probe)
    cards = load_store_cards(args.data)
    rows = generate_signal_rows(cards, staples)
    write_signal_csv(rows, args.output)

    matched = sum(1 for r in rows if r["in_top16_probe"] == "1")
    print(f"Generated {len(rows)} signal rows -> {args.output}")
    print(f"Store cards: {len(cards)}, Chulane staples in probe: {len(staples)}")
    print(f"Matched cards in probe: {matched} / {len(cards)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
