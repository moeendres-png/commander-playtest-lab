"""Unit tests for Issue #1416: Null-/0-Raten-Alarm für Kernsignale beim Import und im Datenbericht.

All test data is synthetic. No imports from tests.* or conftest.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, import_all, importers, signals
from commander_lab.studio.data_report import (
    build_data_report,
    data_report,
    format_data_report,
)

COMMANDER = "Test Commander"
TODAY = date(2026, 11, 16)
CARD_FIELDS = ["commander_name", "card_name", "num_decks", "potential_decks", "synergy"]
BRACKET_FIELDS = [*CARD_FIELDS, "variant", "bracket"]
GLOBAL_FIELDS = ["card_name", "fetch_status", "num_decks", "potential_decks"]
SPELLBOOK_FIELDS = ["card_name", "fetch_status", "variant_count"]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _build_synthetic_workbook(path: Path) -> Path:
    from openpyxl import Workbook

    identity_columns = [
        "card_id",
        "oracle_id",
        "oracle_name",
        "color_identity",
        "mana_cost",
        "mana_value",
        "type_line",
        "oracle_text",
        "is_basic_land",
        "commander_legal",
        "legality_verified_at",
        "identity_evidence_type",
    ]
    inventory_columns = [
        "card_id",
        "oracle_name",
        "observed_quantity",
        "physical_owned_quantity_lower_bound",
        "reserved_for_opponents_quantity",
        "available_for_own_decks_quantity_lower_bound",
        "quantity_exact",
        "number_of_lots",
        "last_verified_at",
    ]
    cards = [
        ("cmd:test", COMMANDER, "GWU", "Legendary Creature — Scout"),
        *(
            (f"card:test:{idx:02d}", f"Synthetic Card {idx:02d}", "G", "Creature — Beast")
            for idx in range(10)
        ),
    ]
    wb = Workbook()
    identity = wb.active
    assert identity is not None
    identity.title = importers.IDENTITY_SHEET
    identity.append(identity_columns)
    for cid, name, colors, tline in cards:
        identity.append(
            [cid, None, name, colors, "{2}", 2, tline, "", False, True, "2026-11-16", "synthetic"]
        )
    inv = wb.create_sheet(importers.INVENTORY_SHEET)
    inv.append(inventory_columns)
    for cid, name, _colors, _tline in cards:
        inv.append([cid, name, 1, 1, 0, 1, True, 1, "2026-11-16"])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def test_core_signal_constants_and_thresholds() -> None:
    expected = {
        "edhrec_commander_inclusion",
        "edhrec_commander_synergy",
        "edhrec_bracket_inclusion",
        "edhrec_global_inclusion",
    }
    assert set(signals.CORE_RATE_ALARM_SIGNALS) == expected
    assert signals.NULL_REASON_RATE_ALARM_THRESHOLD == 0.50
    assert signals.ZERO_NUMERATOR_RATE_ALARM_THRESHOLD == 0.90
    assert signals.is_core_rate_alarm_signal("edhrec_commander_inclusion")
    assert signals.is_core_rate_alarm_signal("edhrec_bracket_inclusion:core")
    assert not signals.is_core_rate_alarm_signal("spellbook_variants")


def test_null_reason_rate_alarm_triggers_above_50_percent_only_for_core_signals(
    tmp_path: Path,
) -> None:
    store = StudioStore.in_memory()
    # 3 out of 4 rows (75.0 %) have missing num_decks -> null_reason_rate alarm for inclusion
    # synergy is valid on all 4 rows (0 % null) -> no alarm for synergy
    bad_path = _write_csv(
        tmp_path / "bad" / "commander_card_signals.csv",
        CARD_FIELDS,
        [
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 00",
                "num_decks": "",
                "potential_decks": 100,
                "synergy": 0.10,
            },
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 01",
                "num_decks": "",
                "potential_decks": 100,
                "synergy": 0.12,
            },
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 02",
                "num_decks": "",
                "potential_decks": 100,
                "synergy": 0.15,
            },
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 03",
                "num_decks": 25,
                "potential_decks": 100,
                "synergy": 0.20,
            },
        ],
    )
    file_report = signals.import_signal_file(store, bad_path, commander=COMMANDER)
    assert isinstance(file_report, signals.SignalFileReport)
    report_dict = file_report.to_dict()
    assert len(file_report.rate_alarms) == 1
    alarm = file_report.rate_alarms[0]
    assert alarm["signal_name"] == "edhrec_commander_inclusion"
    assert alarm["alarm_type"] == "null_reason_rate"
    assert alarm["count"] == 3
    assert alarm["denominator"] == 4
    assert alarm["rate"] == pytest.approx(0.75)
    assert alarm["threshold"] == 0.50
    assert "3/4" in alarm["message"]
    assert "75.0 %" in alarm["message"]
    assert report_dict["rate_alarms"] == file_report.rate_alarms

    # Boundary check: exactly 50 % (2/4) does NOT trigger (> 50 % required)
    boundary_path = _write_csv(
        tmp_path / "boundary" / "commander_card_signals.csv",
        CARD_FIELDS,
        [
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 00",
                "num_decks": "",
                "potential_decks": 100,
                "synergy": 0.10,
            },
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 01",
                "num_decks": "",
                "potential_decks": 100,
                "synergy": 0.12,
            },
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 02",
                "num_decks": 40,
                "potential_decks": 100,
                "synergy": 0.15,
            },
            {
                "commander_name": COMMANDER,
                "card_name": "Synthetic Card 03",
                "num_decks": 25,
                "potential_decks": 100,
                "synergy": 0.20,
            },
        ],
    )
    boundary_report = signals.import_signal_file(store, boundary_path, commander=COMMANDER)
    assert boundary_report.rate_alarms == []

    # Non-core signal (spellbook_variants) with 100 % null values does NOT trigger core rate alarm
    spellbook_path = _write_csv(
        tmp_path / "spellbook" / "spellbook_card_links.csv",
        SPELLBOOK_FIELDS,
        [
            {"card_name": "Synthetic Card 00", "fetch_status": "AVAILABLE", "variant_count": ""},
            {"card_name": "Synthetic Card 01", "fetch_status": "AVAILABLE", "variant_count": ""},
        ],
    )
    sb_report = signals.import_signal_file(store, spellbook_path, commander=COMMANDER)
    assert sb_report.rate_alarms == []


def test_zero_numerator_rate_alarm_triggers_above_90_percent_and_respects_boundary(
    tmp_path: Path,
) -> None:
    store = StudioStore.in_memory()
    # 10 out of 10 rows (100 %) have numerator == 0 with denominator == 200 (> 0)
    zero_rows = [
        {
            "commander_name": COMMANDER,
            "card_name": f"Synthetic Card {idx:02d}",
            "num_decks": 0,
            "potential_decks": 200,
            "synergy": 0.05,
            "variant": "core",
            "bracket": 2,
        }
        for idx in range(10)
    ]
    zero_path = _write_csv(
        tmp_path / "zero" / "commander_bracket_signals_core.csv",
        BRACKET_FIELDS,
        zero_rows,
    )
    zero_report = signals.import_signal_file(store, zero_path, commander=COMMANDER)
    assert len(zero_report.rate_alarms) == 1
    alarm = zero_report.rate_alarms[0]
    assert alarm["signal_name"] == "edhrec_bracket_inclusion:core"
    assert alarm["alarm_type"] == "zero_numerator_rate"
    assert alarm["count"] == 10
    assert alarm["denominator"] == 10
    assert alarm["rate"] == pytest.approx(1.0)
    assert alarm["threshold"] == 0.90
    assert "10/10" in alarm["message"]
    assert "100.0 %" in alarm["message"]

    # Boundary check: 9 out of 10 rows (90.0 %) with numerator == 0 does NOT trigger (> 90 % required)
    boundary_rows = list(zero_rows)
    boundary_rows[-1] = {**boundary_rows[-1], "num_decks": 15}
    boundary_path = _write_csv(
        tmp_path / "boundary90" / "commander_bracket_signals_core.csv",
        BRACKET_FIELDS,
        boundary_rows,
    )
    boundary_report = signals.import_signal_file(store, boundary_path, commander=COMMANDER)
    assert boundary_report.rate_alarms == []


def test_evaluate_core_signal_rate_alarms_with_mapping_rows() -> None:
    rows: list[dict[str, object]] = [
        {
            "signal_name": "edhrec_global_inclusion",
            "value": None,
            "numerator": None,
            "denominator": None,
            "null_value_reasons": {"DECK_COUNTS_MISSING_OR_NOT_NUMERIC": 1},
        },
        {
            "signal_name": "edhrec_global_inclusion",
            "value": None,
            "numerator": None,
            "denominator": None,
            "null_value_reasons": {"DECK_COUNTS_MISSING_OR_NOT_NUMERIC": 1},
        },
        {
            "signal_name": "edhrec_global_inclusion",
            "value": 0.25,
            "numerator": 25,
            "denominator": 100,
            "null_value_reasons": {},
        },
    ]
    alarms = signals.evaluate_core_signal_rate_alarms(rows)
    assert len(alarms) == 1
    assert alarms[0]["signal_name"] == "edhrec_global_inclusion"
    assert alarms[0]["alarm_type"] == "null_reason_rate"
    assert alarms[0]["count"] == 2
    assert alarms[0]["denominator"] == 3


def test_import_signals_directory_and_import_all_surface_alarms_without_aborting_healthy_files(
    tmp_path: Path,
) -> None:
    sig_dir = tmp_path / "signals"
    # Defective commander_card_signals.csv: 100 % zero num_decks for inclusion AND 100 % empty synergy
    _write_csv(
        sig_dir / "commander_card_signals.csv",
        CARD_FIELDS,
        [
            {
                "commander_name": COMMANDER,
                "card_name": f"Synthetic Card {idx:02d}",
                "num_decks": 0,
                "potential_decks": 100,
                "synergy": "",
            }
            for idx in range(5)
        ],
    )
    # Healthy card_global_signals.csv in the same directory
    _write_csv(
        sig_dir / "card_global_signals.csv",
        GLOBAL_FIELDS,
        [
            {
                "card_name": f"Synthetic Card {idx:02d}",
                "fetch_status": "AVAILABLE",
                "num_decks": 50 + idx,
                "potential_decks": 1000,
            }
            for idx in range(5)
        ],
    )

    store = StudioStore.open(tmp_path / "studio")
    workbook = _build_synthetic_workbook(tmp_path / "collection.xlsx")
    importers.import_inventory_workbook(store, workbook)

    dir_report = signals.import_signals_directory(store, sig_dir, commander=COMMANDER)
    alarms = dir_report["rate_alarms"]
    assert isinstance(alarms, list)
    alarm_types = {(a["signal_name"], a["alarm_type"]) for a in alarms}
    assert ("edhrec_commander_inclusion", "zero_numerator_rate") in alarm_types
    assert ("edhrec_commander_synergy", "null_reason_rate") in alarm_types
    # Healthy global file was still imported and did not trigger an alarm
    files = dir_report["files"]
    assert isinstance(files, dict)
    assert files["card_global_signals"]["status"] == "IMPORTED"
    assert files["card_global_signals"]["rows_written"] == 5
    assert files["card_global_signals"]["rate_alarms"] == []
    store.close()

    # Now verify import_all.run and import_all.render
    store_all = StudioStore.open(tmp_path / "studio_all")
    args = argparse.Namespace(
        commander=COMMANDER,
        inventory=str(workbook),
        scryfall=None,
        roles=None,
        rulings=[],
        signals=[str(sig_dir)],
        decklists=None,
        decklist_format="edhrec",
        marks=None,
        expect_pool=None,
    )
    result = import_all.run(args, store_all)
    assert result["failed"] is False
    assert len(result["rate_alarms"]) == 2
    assert any("5/5" in w for w in result["warnings"])
    sig_step = next(s for s in result["steps"] if s["step"].startswith("Signale"))
    assert sig_step["status"] == import_all.WARNING
    rendered = import_all.render(result)
    assert "Raten-Alarm" in rendered
    assert "edhrec_commander_inclusion" in rendered
    assert "edhrec_commander_synergy" in rendered
    assert "5/5" in rendered
    store_all.close()


def test_build_and_format_data_report_surface_signal_rate_alarms(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio_report")
    workbook = _build_synthetic_workbook(tmp_path / "collection.xlsx")
    importers.import_inventory_workbook(store, workbook)

    # Healthy signal import first
    healthy_dir = tmp_path / "healthy_signals"
    _write_csv(
        healthy_dir / "commander_card_signals.csv",
        CARD_FIELDS,
        [
            {
                "commander_name": COMMANDER,
                "card_name": f"Synthetic Card {idx:02d}",
                "num_decks": 20 + idx,
                "potential_decks": 100,
                "synergy": 0.10,
            }
            for idx in range(5)
        ],
    )
    signals.import_signals(store, healthy_dir, commander=COMMANDER)
    healthy_report = build_data_report(store, today=TODAY, commander=COMMANDER)
    assert healthy_report["signal_rate_alarms"] == []
    healthy_text = format_data_report(healthy_report)
    assert "Raten-Alarme für Kernsignale:" not in healthy_text

    # Now import defective core signal (> 50 % null inclusion and > 90 % zero bracket inclusion)
    defective_dir = tmp_path / "defective_signals"
    _write_csv(
        defective_dir / "commander_card_signals.csv",
        CARD_FIELDS,
        [
            {
                "commander_name": COMMANDER,
                "card_name": f"Synthetic Card {idx:02d}",
                "num_decks": "" if idx < 4 else 10,
                "potential_decks": 100,
                "synergy": 0.10,
            }
            for idx in range(5)
        ],
    )
    signals.import_signals(store, defective_dir, commander=COMMANDER)

    defective_report = data_report(store, today=TODAY, commander=COMMANDER)
    alarms = defective_report["signal_rate_alarms"]
    assert isinstance(alarms, list) and len(alarms) == 1
    alarm = alarms[0]
    assert alarm["signal_name"] == "edhrec_commander_inclusion"
    assert alarm["alarm_type"] == "null_reason_rate"
    assert alarm["count"] == 4
    assert alarm["denominator"] == 5
    assert alarm["rate"] == pytest.approx(0.80)
    assert alarm["threshold"] == 0.50

    formatted = format_data_report(defective_report)
    assert "Raten-Alarme für Kernsignale:" in formatted
    assert "edhrec_commander_inclusion" in formatted
    assert "4/5" in formatted
    assert "80.0 %" in formatted
    assert "50 %" in formatted
    store.close()
