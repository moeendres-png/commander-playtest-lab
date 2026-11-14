"""TopDeck conversion signal family of the signal import (#1261 P1.1).

All data here is synthetic. The family stores, per commander and card, the
published conversion rate of the counted TopDeck research file: decks with
the card that reached the top cut over the decks whose top-cut outcome is
known at all (``sample_size_base``). That base is the stored denominator —
never ``appearances``, which also counts decks of unknown outcome. Where
the source publishes no rate (base below 10, the literal ``NULL`` in the
file) the value stays NULL; numerator and denominator are stored anyway.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, signals, strength, strength_view
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"
OTHER = "Other Commander"

FIELDS = [
    "commander",
    "card_name",
    "appearances",
    "conversions",
    "conversion_rate",
    "sample_size_base",
]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    commander: str, card: str, appearances: object, conversions: object, rate: object, base: object
) -> dict[str, object]:
    return {
        "commander": commander,
        "card_name": card,
        "appearances": appearances,
        "conversions": conversions,
        "conversion_rate": rate,
        "sample_size_base": base,
    }


def _write_conversion(folder: Path) -> None:
    folder.mkdir()
    _write(
        folder / "topdeck_card_conversions_1.csv",
        [
            # 4 of 13 known-outcome decks converted; appearances (14) is not the base.
            _row(COMMANDER, "Filler 00", 14, 4, 0.307692, 13),
            # Below the source's publication base: NULL rate, counts still stored.
            _row(COMMANDER, "Filler 01", 3, 1, "NULL", 3),
            _row(COMMANDER, "Filler 02", 5, 0, "NULL", 0),
            # The same card name under another commander is that commander's figure.
            _row(OTHER, "Filler 00", 13, 4, 0.307692, 13),
            _row(COMMANDER, "Filler 00", 14, 4, 0.307692, 13),  # duplicate: first wins
            # A published rate that disagrees with its own figures is refused.
            _row(COMMANDER, "Filler 04", 10, 5, 0.9, 10),
        ],
    )
    _write(
        folder / "topdeck_card_conversions_2.csv",
        [
            _row(COMMANDER, "Filler 05", 10, 6, "NULL", 5),  # conversions above the base
            _row(COMMANDER, "Filler 06", -1, 0, "NULL", 0),  # negative count
            _row(COMMANDER, "Filler 07", 10, "many", "NULL", 5),  # not a count
            _row(COMMANDER, "Filler 08", 4, 0, 0.0, 0),  # a rate without a base
            # A published zero is a value (0 of 25), not an unknown.
            _row(COMMANDER, "Filler 09", 30, 0, 0.0, 25),
            _row(COMMANDER, "", 10, 1, "NULL", 5),  # no card name
            # Lower-case commander name: normalised onto the store's spelling.
            _row("test commander", "Filler 03", 20, 10, 0.5, 20),
        ],
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StudioStore]:
    opened = StudioStore.open(tmp_path / "studio")
    _fill(opened, tmp_path)
    _write_conversion(tmp_path / "signals")
    yield opened
    opened.close()


def _import(store: StudioStore, tmp_path: Path) -> dict[str, object]:
    return signals.import_signals(store, tmp_path / "signals", commander=COMMANDER)


def _signal(store: StudioStore, card: str, commander: str = COMMANDER) -> sqlite3.Row | None:
    return store.connection.execute(  # type: ignore[no-any-return]
        "SELECT * FROM card_signal WHERE commander_name = ? AND signal = ? AND card_name = ?",
        (commander, signals.SIGNAL_CONVERSION, card),
    ).fetchone()


def test_conversion_import_stores_the_rate_with_its_base_as_denominator(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    files = report["files"]
    assert isinstance(files, dict)
    entry = files[signals.CONVERSION_FILE]
    assert entry["parts"] == [
        "topdeck_card_conversions_1.csv",
        "topdeck_card_conversions_2.csv",
    ]
    assert entry["rows_read"] == 13
    assert entry["rows_written"] == 6
    first = _signal(store, "Filler 00")
    assert first is not None
    # The denominator is the known-outcome base (13), never the appearances (14).
    assert (first["value"], first["numerator"], first["denominator"]) == (0.307692, 4, 13)


def test_conversion_unpublished_rate_keeps_the_counts_and_a_null_value(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    files = report["files"]
    assert isinstance(files, dict)
    assert files[signals.CONVERSION_FILE]["null_value_reasons"] == {"RATE_NOT_PUBLISHED": 2}
    small = _signal(store, "Filler 01")
    assert small is not None
    assert (small["value"], small["numerator"], small["denominator"]) == (None, 1, 3)
    empty = _signal(store, "Filler 02")
    assert empty is not None
    assert (empty["value"], empty["numerator"], empty["denominator"]) == (None, 0, 0)


def test_conversion_a_published_zero_is_a_value_not_an_unknown(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    row = _signal(store, "Filler 09")
    assert row is not None
    assert (row["value"], row["numerator"], row["denominator"]) == (0.0, 0, 25)


def test_conversion_commanders_are_never_mixed(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    other = _signal(store, "Filler 00", commander=OTHER)
    assert other is not None
    assert (other["value"], other["numerator"], other["denominator"]) == (0.307692, 4, 13)
    own = _signal(store, "Filler 00")
    assert own is not None and own["denominator"] == 13


def test_conversion_inconsistent_and_invalid_rows_are_not_stored(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    files = report["files"]
    assert isinstance(files, dict)
    assert files[signals.CONVERSION_FILE]["skipped_reasons"] == {
        "DUPLICATE_SAME_FIGURES": 1,
        "INCONSISTENT_RATE": 2,
        "CONVERSION_FIGURES_INVALID": 3,
        "NAME_MISSING": 1,
    }
    for card in ("Filler 04", "Filler 05", "Filler 06", "Filler 07", "Filler 08"):
        assert _signal(store, card) is None


def test_conversion_commander_names_are_normalised_and_reported(
    store: StudioStore, tmp_path: Path
) -> None:
    report = _import(store, tmp_path)
    assert report["commanders_normalised"] == [{"from": "test commander", "to": COMMANDER}]
    row = _signal(store, "Filler 03")
    assert row is not None
    assert (row["value"], row["numerator"], row["denominator"]) == (0.5, 10, 20)
    assert _signal(store, "Filler 03", commander="test commander") is None


def test_conversion_import_is_idempotent(store: StudioStore, tmp_path: Path) -> None:
    _import(store, tmp_path)
    before = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    _import(store, tmp_path)
    after = store.connection.execute("SELECT * FROM card_signal ORDER BY 1, 2, 3").fetchall()
    assert [tuple(row) for row in before] == [tuple(row) for row in after]
    assert store.count("card_signal") == len(before) == 6


def test_conversion_reimport_replaces_the_rows_of_its_commanders(
    store: StudioStore, tmp_path: Path
) -> None:
    _import(store, tmp_path)
    lean = tmp_path / "lean"
    lean.mkdir()
    _write(
        lean / "topdeck_card_conversions.csv",
        [_row(COMMANDER, "Filler 00", 14, 4, 0.307692, 13)],
    )
    signals.import_signals(store, lean, commander=COMMANDER)
    # The leaner file no longer lists Filler 01: its row of this commander is gone,
    # while the other commander's rows are not this file's to replace.
    assert _signal(store, "Filler 01") is None
    assert _signal(store, "Filler 00") is not None
    assert _signal(store, "Filler 00", commander=OTHER) is not None


def test_conversion_absent_file_is_reported_not_an_error(
    store: StudioStore, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    report = signals.import_signals(store, empty, commander=COMMANDER)
    files = report["files"]
    assert isinstance(files, dict)
    assert files[signals.CONVERSION_FILE]["status"] == "ABSENT"
    assert store.count("card_signal") == 0


def test_conversion_rejects_a_file_without_its_columns(store: StudioStore, tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    with (broken / "topdeck_card_conversions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["commander", "card_name"])
        writer.writeheader()
        writer.writerow({"commander": COMMANDER, "card_name": "Filler 00"})
    with pytest.raises(ValueError, match="missing column"):
        signals.import_signals(store, broken, commander=COMMANDER)


def test_conversion_gate_end_to_end_on_a_thin_base(store: StudioStore, tmp_path: Path) -> None:
    """Chulane-shaped data (every base <= 3): the component is collected, its rows
    exist, and the minimum denominator keeps it out of the index for every card."""
    thin = tmp_path / "thin"
    thin.mkdir()
    _write(
        thin / "topdeck_card_conversions.csv",
        [
            _row(COMMANDER, "Filler 00", 7, 1, "NULL", 3),
            _row(COMMANDER, "Filler 01", 5, 1, "NULL", 2),
            _row(COMMANDER, "Filler 02", 4, 0, "NULL", 3),
        ],
    )
    signals.import_signals(store, thin, commander=COMMANDER)
    result = strength_view.compute(store, COMMANDER, strength.StrengthSettings())
    cards = {card["name"]: card for card in result["cards"]}
    for name in ("Filler 00", "Filler 01", "Filler 02"):
        row = next(
            item
            for item in cards[name]["components"]
            if item["component"] == strength.TOURNAMENT_CONVERSION
        )
        assert row["status"] == strength.NO_VALUE
        assert row["reason"] == strength.BELOW_MIN_DENOMINATOR
        assert "Mindest-Nenner 20" in row["note"]
    first = next(
        item
        for item in cards["Filler 00"]["components"]
        if item["component"] == strength.TOURNAMENT_CONVERSION
    )
    assert "Nenner 3" in first["note"]


def test_conversion_ranks_end_to_end_from_a_real_base(store: StudioStore, tmp_path: Path) -> None:
    wide = tmp_path / "wide"
    wide.mkdir()
    _write(
        wide / "topdeck_card_conversions.csv",
        [
            _row(COMMANDER, "Filler 00", 44, 20, 0.5, 40),
            _row(COMMANDER, "Filler 01", 41, 10, 0.25, 40),
        ],
    )
    signals.import_signals(store, wide, commander=COMMANDER)
    result = strength_view.compute(store, COMMANDER, strength.StrengthSettings())
    cards = {card["name"]: card for card in result["cards"]}

    def conversion(name: str) -> strength.ComponentResult:
        return next(
            item
            for item in cards[name]["components"]
            if item["component"] == strength.TOURNAMENT_CONVERSION
        )

    assert conversion("Filler 00")["status"] == strength.PRESENT
    assert conversion("Filler 00")["percentile"] == 1.0
    w_high = strength.wilson_lower(20, 40)
    w_low = strength.wilson_lower(10, 40)
    assert w_high is not None and w_low is not None
    assert conversion("Filler 01")["percentile"] == pytest.approx((w_low / w_high) ** 0.5)
    assert conversion("Filler 00")["denominator"] == 40
    ranked = strength_view.compute(store, COMMANDER, strength.StrengthSettings(share_scale="rank"))
    ranked_cards = {card["name"]: card for card in ranked["cards"]}
    ranked_low = next(
        item
        for item in ranked_cards["Filler 01"]["components"]
        if item["component"] == strength.TOURNAMENT_CONVERSION
    )
    assert ranked_low["percentile"] == 0.0
