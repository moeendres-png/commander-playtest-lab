"""EDHTop16 signal family of the signal import (data package A1).

All data here is synthetic. The family stores the published per-commander
play rate of a card over the ONE_YEAR tournament window; per-card
conversion is not published by the source and must never appear, and
rows the fetch did not attribute to the commander (the API's
global-staples fallback rows) must never be imported.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, signals
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"
OTHER = "Other Commander"

FIELDS = [
    "commander_name",
    "card_name",
    "play_rate",
    "entries_n",
    "window",
    "fetch_status",
    "conversion_rate",
]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    commander: str, card: str, rate: object, entries: object, status: str
) -> dict[str, object]:
    return {
        "commander_name": commander,
        "card_name": card,
        "play_rate": rate,
        "entries_n": entries,
        "window": "ONE_YEAR",
        "fetch_status": status,
        # Published nowhere per card; the column exists in the file to
        # prove the importer never reads it into storage.
        "conversion_rate": 0.5,
    }


def _write_edhtop16(folder: Path) -> None:
    folder.mkdir()
    _write(
        folder / "edhtop16_commander_signals_1.csv",
        [
            _row(COMMANDER, "Filler 00", 0.9, 10, "AVAILABLE"),
            _row(COMMANDER, "Filler 01", 1, 10, "AVAILABLE"),
            _row(COMMANDER, "Filler 02", "", 10, "AVAILABLE"),
            _row(COMMANDER, "Filler 03", 1.5, 10, "AVAILABLE"),
            _row(COMMANDER, "Filler 04", 0.25, 10, "DISCARDED_GLOBAL_FALLBACK"),
        ],
    )
    _write(
        folder / "edhtop16_commander_signals_2.csv",
        [
            _row(COMMANDER, "Filler 05", 0.5, 10, "PARTIAL"),
            _row(OTHER, "Filler 00", 0.5, 4, "AVAILABLE"),
            _row(COMMANDER, "Filler 06", 0.5, "", "AVAILABLE"),
            _row(COMMANDER, "Filler 07", 0.5, 0, "AVAILABLE"),
            _row("", "Filler 08", 0.5, 10, "AVAILABLE"),
            _row(COMMANDER, "Filler 00", 0.9, 10, "AVAILABLE"),  # same figures: first wins
        ],
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _write_edhtop16(tmp_path / "signals")
    yield opened
    opened.close()


def _import(store: StudioStore, tmp_path: Path) -> dict[str, object]:
    return signals.import_signals(store, tmp_path / "signals", commander=COMMANDER)


def _signal(store: StudioStore, card: str, commander: str = COMMANDER) -> sqlite3.Row | None:
    return store.connection.execute(  # type: ignore[no-any-return]
        "SELECT * FROM card_signal WHERE commander_name = ? AND signal = ? AND card_name = ?",
        (commander, signals.SIGNAL_EDHTOP16, card),
    ).fetchone()


def test_edhtop16_import_stores_play_rate_with_published_denominator(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    files = report["files"]
    assert isinstance(files, dict)
    entry = files[signals.EDHTOP16_FILE]
    assert entry["parts"] == [
        "edhtop16_commander_signals_1.csv",
        "edhtop16_commander_signals_2.csv",
    ]
    assert entry["rows_read"] == 11
    assert entry["rows_written"] == 5
    assert entry["skipped_reasons"] == {
        "PLAY_RATE_INVALID": 2,
        "FETCH_STATUS_NOT_AVAILABLE": 2,
        "NAME_MISSING": 1,
        "DUPLICATE_SAME_FIGURES": 1,
    }
    first = _signal(store, "Filler 00")
    assert first is not None
    # The numerator (entries containing the card) is not published: NULL, never derived.
    assert (first["value"], first["numerator"], first["denominator"]) == (0.9, None, 10)
    top = _signal(store, "Filler 01")
    assert top is not None and top["value"] == 1.0


def test_edhtop16_unattributed_and_invalid_rows_are_not_stored(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    for card in ("Filler 02", "Filler 03", "Filler 04", "Filler 05", "Filler 08"):
        assert _signal(store, card) is None
    # An unpublished entry count stays NULL; a stored 0 would be a false denominator.
    for card in ("Filler 06", "Filler 07"):
        row = _signal(store, card)
        assert row is not None and row["value"] == 0.5 and row["denominator"] is None


def test_edhtop16_commanders_are_never_mixed(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    other = _signal(store, "Filler 00", commander=OTHER)
    assert other is not None
    assert (other["value"], other["denominator"]) == (0.5, 4)
    own = _signal(store, "Filler 00")
    assert own is not None and own["value"] == 0.9


def test_edhtop16_conversion_is_never_stored(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    distinct = {
        row[0] for row in store.connection.execute("SELECT DISTINCT signal FROM card_signal")
    }
    assert distinct == {signals.SIGNAL_EDHTOP16}
    assert not any("conversion" in name for name in distinct)


def test_edhtop16_import_is_idempotent(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    before = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    _import(store, tmp_path)
    after = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    assert [tuple(row) for row in before] == [tuple(row) for row in after]
    assert store.count("card_signal") == len(before) == 5


def test_edhtop16_absent_file_is_reported_not_an_error(store: StudioStore, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    report = signals.import_signals(store, empty, commander=COMMANDER)
    files = report["files"]
    assert isinstance(files, dict)
    assert files[signals.EDHTOP16_FILE]["status"] == "ABSENT"
    assert store.count("card_signal") == 0


def test_edhtop16_rejects_a_file_without_its_columns(store: StudioStore, tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    with (broken / "edhtop16_commander_signals.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["commander_name", "card_name"])
        writer.writeheader()
        writer.writerow({"commander_name": COMMANDER, "card_name": "Filler 00"})
    with pytest.raises(ValueError, match="missing column"):
        signals.import_signals(store, broken, commander=COMMANDER)


def test_edhtop16_commander_names_are_normalised_and_reported(
    store: StudioStore, tmp_path: Path
) -> None:
    folder = tmp_path / "names16"
    folder.mkdir()
    _write(
        folder / "edhtop16_commander_signals.csv",
        [
            _row("test commander", "Filler 00", 0.4, 10, "AVAILABLE"),  # lower case
            _row("Mystery Commander", "Filler 00", 0.2, 5, "AVAILABLE"),  # unknown
        ],
    )
    report = signals.import_signals(store, folder, commander=COMMANDER)
    assert report["commanders_imported"] == ["Mystery Commander", COMMANDER]
    assert report["commanders_not_recognised"] == ["Mystery Commander"]
    assert report["commanders_normalised"] == [{"from": "test commander", "to": COMMANDER}]
    own = _signal(store, "Filler 00")
    assert own is not None and own["value"] == 0.4
    assert _signal(store, "Filler 00", commander="test commander") is None
