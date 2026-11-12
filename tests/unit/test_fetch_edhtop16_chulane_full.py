"""Unit tests for full EDHTop16 Chulane dataset and fetcher.

Validates that data/research/edhtop16_chulane_full_20261112.csv conforms to the
dataset schema, contains exactly the 100 cards published for Chulane, and
satisfies structural and oracle resolution requirements.

References:
    GitHub Issue #1232: EDHTop16 — Vollauszug Chulane (1-Jahres-Fenster)
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from scripts.fetch_edhtop16_chulane_full import (
    COMMANDER_NAME,
    CSV_COLUMNS,
    WINDOW,
    write_csv,
)

FULL_CSV_PATH = Path("data/research/edhtop16_chulane_full_20261112.csv")


def test_chulane_full_csv_structure_and_values() -> None:
    """Validate that the committed full Chulane CSV exists and has exact structure."""
    assert FULL_CSV_PATH.is_file(), f"Missing full CSV at {FULL_CSV_PATH}"

    with FULL_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        assert header == list(CSV_COLUMNS), f"Header mismatch: {header} vs {CSV_COLUMNS}"

        rows = list(reader)

    assert len(rows) == 100, f"Expected 100 rows, got {len(rows)}"

    prev_rate = 1.0
    for idx, r in enumerate(rows):
        assert r["commander"] == COMMANDER_NAME
        assert r["window"] == WINDOW
        assert r["entries_n"] == "48"

        # conversion_rate must be explicitly empty: source only publishes commander-level aggregate
        assert r["conversion_rate"] == "", f"Expected empty conversion_rate on row {idx}"

        rate_val = float(r["play_rate"])
        assert 0.0 <= rate_val <= 1.0, f"Invalid play_rate {rate_val} for {r['card_name']}"
        assert rate_val <= prev_rate + 1e-6, f"Rows not sorted by play_rate descending at row {idx}"
        prev_rate = rate_val

        assert r["source_url"].startswith("https://edhtop16.com/commander/")
        assert len(r["fetched_at_utc"]) > 0


def test_chulane_full_oracle_resolution() -> None:
    """Verify that all 100 published card names resolve to Scryfall Oracle names."""
    assert FULL_CSV_PATH.is_file(), f"Missing full CSV at {FULL_CSV_PATH}"

    with FULL_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        card_names = [r["card_name"] for r in reader]

    assert len(card_names) == 100

    db_path = Path.home() / ".local/share/commander-studio/studio.sqlite3"
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT oracle_name FROM card UNION SELECT name FROM scryfall_card")
            known_names = {row[0] for row in cur.fetchall()}

        unresolved = [name for name in card_names if name not in known_names]
        assert len(unresolved) == 0, f"Unresolved card names: {unresolved}"


def test_write_csv_helper(tmp_path: Path) -> None:
    """Test the write_csv helper with a mock row."""
    out_file = tmp_path / "test.csv"
    mock_rows = [
        {
            "commander": COMMANDER_NAME,
            "card_name": "Test Card",
            "play_rate": "0.500000",
            "conversion_rate": "",
            "entries_n": "48",
            "window": WINDOW,
            "source_url": "https://edhtop16.com",
            "fetched_at_utc": "2026-11-12T12:00:00Z",
        }
    ]
    write_csv(mock_rows, out_file)
    assert out_file.is_file()

    with out_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["card_name"] == "Test Card"
