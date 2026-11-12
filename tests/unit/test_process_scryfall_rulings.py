"""Unit tests for Scryfall Rulings bulk processing script.

Source and Provenance of Test Fixture:
- Source: Scryfall Bulk Data API (https://api.scryfall.com/bulk-data, file: rulings)
- Cards selected:
  * Chulane, Teller of Tales (oracle_id: ebf7ce9b-9e5e-4557-9e28-76556997f0ee) - 2 rulings
  * Rhystic Study (oracle_id: 53236dd7-845a-444c-96d5-f41ed7325d8f) - 2 rulings
  * Cyclonic Rift (oracle_id: d75b9c82-1b49-4c3e-a1b5-aeef57d6644b) - 4 rulings
  * Sol Ring (oracle_id: 6ad8011d-3471-4369-9d68-b264cc027487) - 0 rulings in bulk (negative control)
  * Counterspell (oracle_id: cc187110-1148-4090-bbb8-e205694a39f5) - 0 rulings in bulk (negative control)
- Total rulings in fixture: 8
- Distinct Oracle IDs in fixture: 3
- Data extracted directly from Scryfall public API / rulings dataset.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from scripts.process_scryfall_rulings import (
    filter_rulings,
    format_counting_protocol,
    iter_bulk_rulings,
    load_target_oracle_ids,
    main,
    validate_ruling_dict,
)

FIXTURE_PATH = Path("tests/fixtures/scryfall_rulings_fixture.jsonl")


def test_fixture_file_exists() -> None:
    assert FIXTURE_PATH.is_file(), f"Fixture file not found: {FIXTURE_PATH}"


def test_filter_rulings_exact_fixture_counts(tmp_path: Path) -> None:
    # 3 cards with rulings + 2 cards without rulings
    target_ids = {
        "ebf7ce9b-9e5e-4557-9e28-76556997f0ee",  # Chulane (2 rulings)
        "53236dd7-845a-444c-96d5-f41ed7325d8f",  # Rhystic Study (2 rulings)
        "d75b9c82-1b49-4c3e-a1b5-aeef57d6644b",  # Cyclonic Rift (4 rulings)
        "6ad8011d-3471-4369-9d68-b264cc027487",  # Sol Ring (0 rulings)
        "cc187110-1148-4090-bbb8-e205694a39f5",  # Counterspell (0 rulings)
    }

    records_iter = iter_bulk_rulings(FIXTURE_PATH)
    matched, stats = filter_rulings(records_iter, target_ids)

    # Hardcoded exact fixture counts
    assert stats.total_bulk_rulings == 8
    assert stats.distinct_bulk_oracle_ids == 3
    assert stats.input_ids_count == 5
    assert stats.matched_rulings_count == 8
    assert stats.matched_oracle_ids_count == 3
    assert len(stats.missing_oracle_ids) == 2
    assert stats.missing_oracle_ids == [
        "6ad8011d-3471-4369-9d68-b264cc027487",
        "cc187110-1148-4090-bbb8-e205694a39f5",
    ]
    assert stats.parse_errors_count == 0

    # Verify per-card ruling counts
    chulane_rulings = [r for r in matched if r.oracle_id == "ebf7ce9b-9e5e-4557-9e28-76556997f0ee"]
    rhystic_rulings = [r for r in matched if r.oracle_id == "53236dd7-845a-444c-96d5-f41ed7325d8f"]
    cyclonic_rulings = [r for r in matched if r.oracle_id == "d75b9c82-1b49-4c3e-a1b5-aeef57d6644b"]

    assert len(chulane_rulings) == 2
    assert len(rhystic_rulings) == 2
    assert len(cyclonic_rulings) == 4

    # Verify sorting order (by oracle_id, published_at, comment)
    for i in range(len(matched) - 1):
        prev_key = (matched[i].oracle_id, matched[i].published_at, matched[i].comment)
        next_key = (matched[i + 1].oracle_id, matched[i + 1].published_at, matched[i + 1].comment)
        assert prev_key <= next_key


def test_json_array_bulk_parsing(tmp_path: Path) -> None:
    lines = FIXTURE_PATH.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    json_array_path = tmp_path / "rulings_array.json"
    json_array_path.write_text(json.dumps(records), encoding="utf-8")

    loaded = list(iter_bulk_rulings(json_array_path))
    assert len(loaded) == 8
    assert loaded[0].oracle_id == "ebf7ce9b-9e5e-4557-9e28-76556997f0ee"


def test_gzip_jsonl_bulk_parsing(tmp_path: Path) -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    gz_path = tmp_path / "rulings_fixture.jsonl.gz"
    with gzip.open(gz_path, "wb") as f_out:
        f_out.write(raw_bytes)

    loaded = list(iter_bulk_rulings(gz_path))
    assert len(loaded) == 8


def test_validation_rejects_invalid_records() -> None:
    # Missing oracle_id
    with pytest.raises(ValueError, match="invalid or missing 'oracle_id'"):
        validate_ruling_dict({"published_at": "2020-01-01", "source": "wotc", "comment": "test"}, 0)

    # Invalid published_at date format
    with pytest.raises(ValueError, match="invalid or missing 'published_at'"):
        validate_ruling_dict(
            {
                "oracle_id": "ebf7ce9b-9e5e-4557-9e28-76556997f0ee",
                "published_at": "invalid-date",
                "source": "wotc",
                "comment": "test",
            },
            1,
        )

    # Missing source
    with pytest.raises(ValueError, match="invalid or missing 'source'"):
        validate_ruling_dict(
            {
                "oracle_id": "ebf7ce9b-9e5e-4557-9e28-76556997f0ee",
                "published_at": "2020-01-01",
                "source": "",
                "comment": "test",
            },
            2,
        )

    # Non-string comment
    with pytest.raises(ValueError, match="invalid or missing 'comment'"):
        validate_ruling_dict(
            {
                "oracle_id": "ebf7ce9b-9e5e-4557-9e28-76556997f0ee",
                "published_at": "2020-01-01",
                "source": "wotc",
                "comment": None,
            },
            3,
        )


def test_load_target_oracle_ids(tmp_path: Path) -> None:
    ids_file = tmp_path / "target_ids.txt"
    ids_file.write_text(
        "# Header comment\n"
        "ebf7ce9b-9e5e-4557-9e28-76556997f0ee\n"
        "\n"
        "  53236dd7-845a-444c-96d5-f41ed7325d8f  \n"
        "EBF7CE9B-9E5E-4557-9E28-76556997F0EE\n",  # duplicate uppercase
        encoding="utf-8",
    )
    loaded = load_target_oracle_ids(ids_file)
    assert len(loaded) == 2
    assert loaded == [
        "ebf7ce9b-9e5e-4557-9e28-76556997f0ee",
        "53236dd7-845a-444c-96d5-f41ed7325d8f",
    ]


def test_main_cli_execution(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text(
        "ebf7ce9b-9e5e-4557-9e28-76556997f0ee\n"
        "6ad8011d-3471-4369-9d68-b264cc027487\n",  # Sol Ring (has 0 rulings)
        encoding="utf-8",
    )
    out_file = tmp_path / "filtered_rulings.jsonl"

    ret = main(
        [
            "--oracle-ids",
            str(ids_file),
            "--bulk",
            str(FIXTURE_PATH),
            "--out",
            str(out_file),
        ]
    )
    assert ret == 0
    assert out_file.is_file()

    # Read output
    output_lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(output_lines) == 2
    record_0 = json.loads(output_lines[0])
    assert record_0["oracle_id"] == "ebf7ce9b-9e5e-4557-9e28-76556997f0ee"
    assert "Chulane" in record_0["comment"]

    captured = capsys.readouterr().out
    assert "Gesamtzahl Rulings im Bulk: 8" in captured
    assert "Distinkte Oracle-IDs im Bulk: 3" in captured
    assert "Treffer (Rulings zu Eingabe-IDs): 2" in captured
    assert "Treffer (Oracle-IDs mit Rulings, AVAILABLE): 1" in captured
    assert "Eingabe-IDs ohne Rulings (NOT_FOUND): 1" in captured
    assert "6ad8011d-3471-4369-9d68-b264cc027487" in captured
    assert "Parse-Fehler: 0" in captured


def test_format_counting_protocol() -> None:
    from scripts.process_scryfall_rulings import RulingsStats

    stats = RulingsStats(
        total_bulk_rulings=100,
        distinct_bulk_oracle_ids=50,
        input_ids_count=5,
        matched_rulings_count=10,
        matched_oracle_ids_count=4,
        missing_oracle_ids=["dummy-id-1"],
        parse_errors_count=0,
    )
    report = format_counting_protocol(stats)
    assert "AVAILABLE): 4" in report
    assert "NOT_FOUND): 1" in report
    assert "dummy-id-1" in report
    assert "Parse-Fehler: 0" in report
