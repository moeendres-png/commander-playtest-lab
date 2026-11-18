"""Defensive field reading with fallback chains (#1453). All data here is synthetic."""

from __future__ import annotations

import csv
from pathlib import Path

from commander_lab.studio import StudioStore, data_report, importers, signals
from commander_lab.studio.field_read import (
    EDHREC_DECK_COUNT_ALIASES,
    EDHREC_POTENTIAL_DECKS_ALIASES,
    FallbackTracker,
    read_field,
)
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"


def test_read_field_primary_alias_and_empty_exhaustion() -> None:
    tracker = FallbackTracker()
    val, used = read_field(
        {"num_decks": "42", "inclusion": "99"},
        EDHREC_DECK_COUNT_ALIASES,
        tracker=tracker,
    )
    assert val == "42"
    assert used == "num_decks"
    assert tracker.to_dict() == {}

    val2, used2 = read_field(
        {"num_decks": "  ", "inclusion": "42"},
        EDHREC_DECK_COUNT_ALIASES,
        tracker=tracker,
    )
    assert val2 == "42"
    assert used2 == "inclusion"
    assert tracker.to_dict() == {"num_decks<-inclusion": 1}

    val3, used3 = read_field(
        {"num_decks": "", "inclusion": None},
        EDHREC_DECK_COUNT_ALIASES,
        tracker=tracker,
    )
    assert val3 is None
    assert used3 is None
    assert tracker.to_dict() == {"num_decks<-inclusion": 1}
    assert EDHREC_POTENTIAL_DECKS_ALIASES[0] == "potential_decks"


def test_signals_import_with_renamed_columns_matches_canonical_and_reports_fallbacks(
    tmp_path: Path,
) -> None:
    store_canon = StudioStore.open(tmp_path / "canon_store")
    _fill(store_canon, tmp_path)
    canon_dir = tmp_path / "canon_signals"
    canon_dir.mkdir()
    with (canon_dir / "commander_card_signals.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["commander_name", "card_name", "num_decks", "potential_decks", "synergy"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "commander_name": COMMANDER,
                "card_name": "Forest",
                "num_decks": "120",
                "potential_decks": "200",
                "synergy": "0.15",
            }
        )
        writer.writerow(
            {
                "commander_name": COMMANDER,
                "card_name": "Swarm Rat",
                "num_decks": "50",
                "potential_decks": "200",
                "synergy": "-0.05",
            }
        )
    rep_canon = signals.import_signals(store_canon, canon_dir, commander=COMMANDER)
    assert rep_canon["fallbacks_used"] == {}
    assert data_report.data_report(store_canon)["fallbacks_used"] == {}

    store_renamed = StudioStore.open(tmp_path / "renamed_store")
    _fill(store_renamed, tmp_path)
    renamed_dir = tmp_path / "renamed_signals"
    renamed_dir.mkdir()
    with (renamed_dir / "commander_card_signals.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "commander_name",
                "card_name",
                "inclusion",
                "total_decks",
                "synergy_score",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "commander_name": COMMANDER,
                "card_name": "Forest",
                "inclusion": "120",
                "total_decks": "200",
                "synergy_score": "0.15",
            }
        )
        writer.writerow(
            {
                "commander_name": COMMANDER,
                "card_name": "Swarm Rat",
                "inclusion": "50",
                "total_decks": "200",
                "synergy_score": "-0.05",
            }
        )
    rep_renamed = signals.import_signals(store_renamed, renamed_dir, commander=COMMANDER)
    expected_fallbacks = {
        "num_decks<-inclusion": 2,
        "potential_decks<-total_decks": 2,
        "synergy<-synergy_score": 2,
    }
    assert rep_renamed["fallbacks_used"] == expected_fallbacks
    files_map = rep_renamed["files"]
    assert isinstance(files_map, dict)
    assert files_map["commander_card_signals"]["fallbacks_used"] == expected_fallbacks

    drep = data_report.data_report(store_renamed)
    assert drep["fallbacks_used"] == expected_fallbacks
    formatted = data_report.format_data_report(drep)
    assert "num_decks<-inclusion: 2" in formatted

    rows_canon = store_canon.connection.execute(
        "SELECT commander_name, signal, card_name, value, numerator, denominator "
        "FROM card_signal ORDER BY 1, 2, 3"
    ).fetchall()
    rows_renamed = store_renamed.connection.execute(
        "SELECT commander_name, signal, card_name, value, numerator, denominator "
        "FROM card_signal ORDER BY 1, 2, 3"
    ).fetchall()
    assert [tuple(r) for r in rows_renamed] == [tuple(r) for r in rows_canon]
    store_canon.close()
    store_renamed.close()


def test_total_failure_across_all_aliases_stores_null_and_triggers_rate_alarm(
    tmp_path: Path,
) -> None:
    store = StudioStore.open(tmp_path / "alarm_store")
    _fill(store, tmp_path)
    broken_dir = tmp_path / "broken_signals"
    broken_dir.mkdir()
    with (broken_dir / "commander_card_signals.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["commander_name", "card_name", "inclusion", "total_decks", "synergy"],
        )
        writer.writeheader()
        for card_name in ("Forest", "Swarm Rat", "Filler 00"):
            writer.writerow(
                {
                    "commander_name": COMMANDER,
                    "card_name": card_name,
                    "inclusion": "",
                    "total_decks": "200",
                    "synergy": "",
                }
            )
    rep = signals.import_signals(store, broken_dir, commander=COMMANDER)
    alarms = rep["rate_alarms"]
    assert isinstance(alarms, list)
    alarm_signals = {a["signal_name"] for a in alarms if a["alarm_type"] == "null_reason_rate"}
    assert signals.SIGNAL_INCLUSION in alarm_signals
    assert signals.SIGNAL_SYNERGY in alarm_signals

    stored = store.connection.execute(
        "SELECT value, numerator, denominator FROM card_signal WHERE signal = ?",
        (signals.SIGNAL_INCLUSION,),
    ).fetchall()
    assert len(stored) == 3
    assert all(tuple(r) == (None, None, None) for r in stored)
    store.close()


def test_edhrec_table_importer_fallback_chain(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "obs_store")
    _fill(store, tmp_path)
    csv_path = tmp_path / "edhrec_renamed.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "card_id",
                "name",
                "theme",
                "inclusion",
                "total_decks",
                "inclusion_pct_shown",
                "lift_shown",
                "url",
                "snapshot_utc",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "card_id": "card:project:0002",
                "name": "Forest",
                "theme": "lands",
                "inclusion": "80",
                "total_decks": "100",
                "inclusion_pct_shown": "80.0",
                "lift_shown": "1.2",
                "url": "https://edhrec.example/lands",
                "snapshot_utc": "2026-11-10T00:00:00Z",
            }
        )
    res = importers.import_edhrec_table(store, csv_path)
    assert res["rows"] == 1
    assert res["fallbacks_used"] == {
        "card_name<-name": 1,
        "inclusion_pct<-inclusion_pct_shown": 1,
        "lift<-lift_shown": 1,
        "num_decks<-inclusion": 1,
        "potential_decks<-total_decks": 1,
    }
    obs = store.connection.execute(
        "SELECT metric, value, numerator, denominator FROM observation ORDER BY metric"
    ).fetchall()
    assert [tuple(r) for r in obs] == [
        ("inclusion_pct", 80.0, 80, 100),
        ("lift", 1.2, None, None),
    ]
    store.close()
