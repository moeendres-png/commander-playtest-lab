"""Unit tests for scripts/generate_chulane_edhtop16_signal.py.

Validates EDHTop16 tournament signal matching and CSV generation.
"""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_chulane_edhtop16_signal import (
    CSV_COLUMNS,
    Top16Staple,
    generate_signal_rows,
    load_edhtop16_chulane_staples,
    write_signal_csv,
)

PROBE_CSV_PATH = Path("data/research/edhtop16_probe_20261112.csv")
SIGNAL_CSV_PATH = Path("data/research/chulane_edhtop16_signal_20261112.csv")


def test_load_edhtop16_chulane_staples() -> None:
    staples = load_edhtop16_chulane_staples(PROBE_CSV_PATH)
    assert len(staples) == 100
    assert "Shrieking Drake" in staples
    assert "Sol Ring" in staples
    assert staples["Shrieking Drake"].rank == 4
    assert staples["Sol Ring"].rank == 5
    assert staples["Shrieking Drake"].entries_n == 48


def test_generate_signal_rows_matching() -> None:
    mock_cards = [
        ("oid-1", "Shrieking Drake"),
        ("oid-2", "Sol Ring"),
        ("oid-3", "Grizzly Bears"),
    ]
    mock_staples = {
        "Shrieking Drake": Top16Staple("Shrieking Drake", 4, 0.895833, 48),
        "Sol Ring": Top16Staple("Sol Ring", 5, 0.895833, 48),
    }

    rows = generate_signal_rows(mock_cards, mock_staples)
    assert len(rows) == 3

    assert rows[0]["card_name"] == "Shrieking Drake"
    assert rows[0]["in_top16_probe"] == "1"
    assert rows[0]["top16_rank"] == "4"
    assert rows[0]["top16_entries"] == "48"

    assert rows[1]["card_name"] == "Sol Ring"
    assert rows[1]["in_top16_probe"] == "1"
    assert rows[1]["top16_rank"] == "5"

    assert rows[2]["card_name"] == "Grizzly Bears"
    assert rows[2]["in_top16_probe"] == "0"
    assert rows[2]["top16_rank"] == ""
    assert rows[2]["top16_entries"] == ""


def test_write_and_read_signal_csv(tmp_path: Path) -> None:
    output_file = tmp_path / "test_signal.csv"
    mock_rows = [
        {
            "oracle_id": "oid-1",
            "card_name": "Test Card",
            "in_top16_probe": "1",
            "top16_rank": "1",
            "top16_entries": "48",
        }
    ]
    write_signal_csv(mock_rows, output_file)

    with output_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CSV_COLUMNS
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["card_name"] == "Test Card"


def test_signal_file_integrity() -> None:
    assert SIGNAL_CSV_PATH.is_file(), "Signal CSV must exist"
    with SIGNAL_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CSV_COLUMNS
        rows = list(reader)

    assert len(rows) == 1414, "Must contain all 1,414 store collection cards"

    matched = [r for r in rows if r["in_top16_probe"] == "1"]
    unmatched = [r for r in rows if r["in_top16_probe"] == "0"]

    assert len(matched) == 16, "Exactly 16 cards must match Chulane top16 probe"
    assert len(unmatched) == 1398, "Remaining 1,398 cards must be marked 0"

    # Validate matched row structure
    for r in matched:
        assert r["top16_rank"].isdigit()
        rank = int(r["top16_rank"])
        assert 1 <= rank <= 100
        assert r["top16_entries"] == "48"

    # Validate unmatched row structure
    for r in unmatched:
        assert r["top16_rank"] == ""
        assert r["top16_entries"] == ""

    # Known staples verification
    matched_names = {r["card_name"]: int(r["top16_rank"]) for r in matched}
    assert matched_names["Shrieking Drake"] == 4
    assert matched_names["Sol Ring"] == 5
    assert matched_names["Llanowar Elves"] == 6
    assert matched_names["Avacyn's Pilgrim"] == 10
    assert matched_names["Elvish Mystic"] == 16
    assert matched_names["Silence"] == 17
    assert matched_names["Tireless Provisioner"] == 18
    assert matched_names["Crop Rotation"] == 19
    assert matched_names["Faerie Mastermind"] == 26
    assert matched_names["Whitemane Lion"] == 58
    assert matched_names["Veil of Summer"] == 60
    assert matched_names["Swords to Plowshares"] == 62
    assert matched_names["Arbor Elf"] == 63
    assert matched_names["Lavinia, Azorius Renegade"] == 66
    assert matched_names["Path to Exile"] == 89
    assert matched_names["An Offer You Can't Refuse"] == 95
