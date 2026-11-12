"""Unit tests for EDHTop16 probe fetcher and generated dataset.

Validates that data/research/edhtop16_probe_20261112.csv conforms to the
dataset schema, contains the expected commander cohorts, and satisfies
structural integrity requirements.

References:
    GitHub Issue #1225: EDHTop16 probe & verification
"""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.fetch_edhtop16_probe import (
    CSV_COLUMNS,
    TARGET_COMMANDERS,
    write_probe_csv,
)

PROBE_CSV_PATH = Path("data/research/edhtop16_probe_20261112.csv")


def test_probe_csv_structure_and_cohorts() -> None:
    """Validate that the committed probe CSV exists and has exact structure."""
    assert PROBE_CSV_PATH.is_file(), f"Missing probe CSV at {PROBE_CSV_PATH}"

    with PROBE_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        assert header == list(CSV_COLUMNS), f"Header mismatch: {header} vs {CSV_COLUMNS}"

        rows = list(reader)

    assert len(rows) == 300, f"Expected 300 rows (100 per commander), got {len(rows)}"

    commander_counts: dict[str, int] = {}
    for r in rows:
        cmd = r["commander"]
        commander_counts[cmd] = commander_counts.get(cmd, 0) + 1

        # play_rate must be a valid float in [0.0, 1.0]
        rate_val = float(r["play_rate"])
        assert 0.0 <= rate_val <= 1.0, f"Invalid play_rate {rate_val} for {r}"

        # window must be ONE_YEAR
        assert r["window"] == "ONE_YEAR"

        # source_url must point to edhtop16
        assert r["source_url"].startswith("https://edhtop16.com/commander/")

        # fetched_at_utc must be populated
        assert len(r["fetched_at_utc"]) > 0

    assert set(commander_counts.keys()) == set(TARGET_COMMANDERS)
    for cmd, count in commander_counts.items():
        assert count == 100, f"Expected 100 rows for {cmd}, got {count}"


def test_probe_csv_commander_sample_sizes() -> None:
    """Validate commander-specific sample sizes (entries_n)."""
    with PROBE_CSV_PATH.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    chulane_entries = {r["entries_n"] for r in rows if r["commander"] == "Chulane, Teller of Tales"}
    kinnan_entries = {r["entries_n"] for r in rows if r["commander"] == "Kinnan, Bonder Prodigy"}
    tymna_entries = {r["entries_n"] for r in rows if r["commander"] == "Tymna the Weaver"}

    # Chulane had 48 1-year entries
    assert chulane_entries == {"48"}
    # Kinnan had 6503 1-year entries
    assert kinnan_entries == {"6503"}
    # Solo Tymna is unpartnered, count is 0
    assert tymna_entries == {"0"}


def test_write_probe_csv_helper(tmp_path: Path) -> None:
    """Validate write_probe_csv helper function writes valid CSV structure."""
    test_out = tmp_path / "sub" / "test_probe.csv"
    sample_rows = [
        {
            "commander": "Chulane, Teller of Tales",
            "card_name": "Sol Ring",
            "play_rate": "0.895833",
            "conversion_rate": "",
            "entries_n": "48",
            "window": "ONE_YEAR",
            "source_url": "https://edhtop16.com/commander/Chulane?tab=staples",
            "fetched_at_utc": "2026-11-12T11:00:00Z",
        }
    ]

    write_probe_csv(sample_rows, test_out)
    assert test_out.is_file()

    with test_out.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert list(reader.fieldnames or []) == list(CSV_COLUMNS)
        loaded = list(reader)
        assert len(loaded) == 1
        assert loaded[0]["card_name"] == "Sol Ring"
        assert loaded[0]["play_rate"] == "0.895833"
