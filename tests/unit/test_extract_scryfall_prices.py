"""Unit tests for Scryfall price snapshot extraction script.

Source and Provenance:
- Source: Scryfall Bulk Data API (https://api.scryfall.com/bulk-data, type: "default_cards")
- Test fixture: 5 distinct card printings extracted from Scryfall Default Cards:
  1. Sol Ring (C21, collector 263, id: 4cbc6901-6a4a-4d0a-83ea-7eefa3b35021)
     - EUR price present: "0.86"
  2. Sol Ring (LEA, collector 269, id: c4300d24-1cae-4dd5-be7e-38cc677cf5bd)
     - EUR price present: "1061.58"
  3. Koma, Cosmos Serpent (KHM, collector 221, id: 2de25ea4-284a-4c16-b823-048ff00c6a03)
     - EUR price present: "5.16", EUR foil: "5.72"
  4. Counterspell (VMA, collector 64, id: 18388c02-8b29-4f83-877b-706c68a9ee29)
     - Digital MTGO release: EUR price EMPTY (""), USD EMPTY (""), TIX: "0.04"
  5. Dismember (ANA, collector 40, id: 26021cb7-b2e8-41dd-8af0-0c9b3baffde0)
     - Arena promo release: ALL prices EMPTY ("")
- Semantics: Preis = Momentaufnahme, kein Verlauf. Fehlende Preise bleiben leer (kein 0).
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

import pytest
from scripts.extract_scryfall_prices import (
    filter_prices_from_stream,
    format_price_counting_protocol,
    load_target_scryfall_ids,
    main,
    parse_price_value,
    stream_card_objects,
)

FIXTURE_PATH = Path("tests/fixtures/scryfall_default_cards_fixture.jsonl")


def test_fixture_file_exists() -> None:
    assert FIXTURE_PATH.is_file(), f"Fixture file not found: {FIXTURE_PATH}"


def test_price_value_normalization() -> None:
    assert parse_price_value(None) == ""
    assert parse_price_value("") == ""
    assert parse_price_value("0.86") == "0.86"
    assert parse_price_value(1.98) == "1.98"
    assert parse_price_value(0) == "0"
    # None must never become "0"
    assert parse_price_value(None) != "0"


def test_stream_and_filter_prices_exact_counts() -> None:
    target_ids = {
        "4cbc6901-6a4a-4d0a-83ea-7eefa3b35021",  # Sol Ring C21 (has EUR)
        "c4300d24-1cae-4dd5-be7e-38cc677cf5bd",  # Sol Ring LEA (has EUR)
        "2de25ea4-284a-4c16-b823-048ff00c6a03",  # Koma KHM (has EUR + foil)
        "18388c02-8b29-4f83-877b-706c68a9ee29",  # Counterspell VMA (empty EUR, has tix)
        "26021cb7-b2e8-41dd-8af0-0c9b3baffde0",  # Dismember ANA (no prices)
        "00000000-0000-0000-0000-000000000000",  # Non-existent ID (NOT_FOUND)
    }

    stream = stream_card_objects(FIXTURE_PATH)
    snapshot_date = "2026-11-12"
    records, stats = filter_prices_from_stream(stream, target_ids, snapshot_date)

    # Exact count assertions
    assert stats.total_bulk_lines == 5
    assert stats.input_ids_count == 6
    assert stats.matched_count == 5
    assert len(stats.missing_ids) == 1
    assert stats.missing_ids == ["00000000-0000-0000-0000-000000000000"]
    assert stats.ids_without_any_price == ["26021cb7-b2e8-41dd-8af0-0c9b3baffde0"]
    assert stats.parse_errors_count == 0

    records_by_id = {r.scryfall_id: r for r in records}

    # 1. Card WITH EUR price: Sol Ring C21
    sol_ring = records_by_id["4cbc6901-6a4a-4d0a-83ea-7eefa3b35021"]
    assert sol_ring.name == "Sol Ring"
    assert sol_ring.set_code == "c21"
    assert sol_ring.collector_number == "263"
    assert sol_ring.eur == "0.86"
    assert sol_ring.usd == "1.98"
    assert sol_ring.tix == "0.06"
    assert sol_ring.snapshot_date == "2026-11-12"
    assert sol_ring.has_any_price() is True

    # 2. Card WITHOUT EUR price (empty field, never "0"): Counterspell VMA
    counterspell = records_by_id["18388c02-8b29-4f83-877b-706c68a9ee29"]
    assert counterspell.name == "Counterspell"
    assert counterspell.set_code == "vma"
    assert counterspell.collector_number == "64"
    assert counterspell.eur == ""
    assert counterspell.eur_foil == ""
    assert counterspell.usd == ""
    assert counterspell.tix == "0.04"
    assert counterspell.has_any_price() is True

    # 3. Card WITHOUT ANY PRICE: Dismember ANA
    dismember = records_by_id["26021cb7-b2e8-41dd-8af0-0c9b3baffde0"]
    assert dismember.name == "Dismember"
    assert dismember.eur == ""
    assert dismember.eur_foil == ""
    assert dismember.usd == ""
    assert dismember.usd_foil == ""
    assert dismember.tix == ""
    assert dismember.has_any_price() is False


def test_gzip_streaming(tmp_path: Path) -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    gz_path = tmp_path / "default_cards_fixture.jsonl.gz"
    with gzip.open(gz_path, "wb") as f_out:
        f_out.write(raw_bytes)

    stream = stream_card_objects(gz_path)
    records, stats = filter_prices_from_stream(
        stream,
        {"4cbc6901-6a4a-4d0a-83ea-7eefa3b35021"},
        "2026-11-12",
    )
    assert stats.total_bulk_lines == 5
    assert stats.matched_count == 1
    assert records[0].eur == "0.86"


def test_load_target_scryfall_ids_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "targets.csv"
    csv_file.write_text(
        "id,scryfall_id,notes\n"
        "1,4cbc6901-6a4a-4d0a-83ea-7eefa3b35021,test\n"
        "2,18388C02-8B29-4F83-877B-706C68A9EE29,uppercase\n"
        "3,,empty\n",
        encoding="utf-8",
    )
    ids = load_target_scryfall_ids(csv_file)
    assert len(ids) == 2
    assert ids == [
        "4cbc6901-6a4a-4d0a-83ea-7eefa3b35021",
        "18388c02-8b29-4f83-877b-706c68a9ee29",
    ]


def test_main_cli_execution(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_csv = tmp_path / "input_cards.csv"
    input_csv.write_text(
        "scryfall_id,name\n"
        "4cbc6901-6a4a-4d0a-83ea-7eefa3b35021,Sol Ring\n"
        "18388c02-8b29-4f83-877b-706c68a9ee29,Counterspell\n"
        "missing-id-uuid,Missing Card\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "snapshot.csv"

    ret = main(
        [
            "--input-csv",
            str(input_csv),
            "--bulk",
            str(FIXTURE_PATH),
            "--snapshot-date",
            "2026-11-12",
            "--out",
            str(output_csv),
        ]
    )
    assert ret == 0
    assert output_csv.is_file()

    with output_csv.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 2

    # Check Sol Ring row
    sol_ring_row = next(
        r for r in reader if r["scryfall_id"] == "4cbc6901-6a4a-4d0a-83ea-7eefa3b35021"
    )
    assert sol_ring_row["eur"] == "0.86"
    assert sol_ring_row["snapshot_date"] == "2026-11-12"

    # Check Counterspell row has empty eur (not "0")
    cs_row = next(r for r in reader if r["scryfall_id"] == "18388c02-8b29-4f83-877b-706c68a9ee29")
    assert cs_row["eur"] == ""

    captured = capsys.readouterr().out
    assert "Bulk-Zeilen gesamt: 5" in captured
    assert "Eingabe-IDs: 3" in captured
    assert "Treffer (AVAILABLE): 2" in captured
    assert "IDs ohne Treffer (NOT_FOUND): 1" in captured
    assert "missing-id-uuid" in captured
    assert "Parse-Fehler: 0" in captured


def test_format_counting_protocol() -> None:
    from scripts.extract_scryfall_prices import PriceSnapshotStats

    stats = PriceSnapshotStats(
        total_bulk_lines=1000,
        input_ids_count=10,
        matched_count=8,
        missing_ids=["dummy-missing"],
        ids_without_any_price=["dummy-no-price"],
        parse_errors_count=0,
    )
    report = format_price_counting_protocol(stats)
    assert "Bulk-Zeilen gesamt: 1000" in report
    assert "Treffer (AVAILABLE): 8" in report
    assert "NOT_FOUND): 1" in report
    assert "dummy-missing" in report
    assert "IDs ohne jeden Preis: 1" in report
    assert "dummy-no-price" in report
    assert "Parse-Fehler: 0" in report
