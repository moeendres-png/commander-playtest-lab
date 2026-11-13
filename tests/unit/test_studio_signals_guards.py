"""Signal import: replace/append, zero rows, BOM, skipped reasons, commander names, salt, combos.

All data here is synthetic. No network.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, signals

COMMANDER = "Test Commander"
CARD_FIELDS = ["commander_name", "card_name", "num_decks", "potential_decks", "synergy"]


def _csv(
    path: Path, fields: list[str], rows: list[dict[str, object]], *, bom: bool = False
) -> None:
    with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _card_row(
    card: str, num: object, pot: object, syn: object = 0.1, name: str = COMMANDER
) -> dict[str, object]:
    return {
        "commander_name": name,
        "card_name": card,
        "num_decks": num,
        "potential_decks": pot,
        "synergy": syn,
    }


@pytest.fixture()
def store() -> StudioStore:
    return StudioStore.in_memory()


def _file(folder: Path) -> Path:
    folder.mkdir(exist_ok=True)
    return folder / "commander_card_signals.csv"


def _names(store: StudioStore, signal: str) -> set[str]:
    return {
        str(row[0])
        for row in store.connection.execute(
            "SELECT card_name FROM card_signal WHERE signal = ?", (signal,)
        )
    }


def _files(report: dict[str, object]) -> dict[str, signals.FileReport]:
    files = report["files"]
    assert isinstance(files, dict)
    return files


def test_replace_drops_cards_the_new_file_no_longer_lists(
    store: StudioStore, tmp_path: Path
) -> None:
    path = _file(tmp_path)
    _csv(path, CARD_FIELDS, [_card_row("A", 1, 2), _card_row("B", 1, 2)])
    signals.import_signals(store, tmp_path, commander=COMMANDER)
    _csv(path, CARD_FIELDS, [_card_row("A", 1, 2)])
    report = signals.import_signals(store, tmp_path, commander=COMMANDER)
    assert _names(store, signals.SIGNAL_INCLUSION) == {"A"}
    assert _files(report)[signals.CARD_FILE]["rows_replaced"] == 4  # 2 cards x 2 signals


def test_append_keeps_old_rows_and_updates_listed_ones(store: StudioStore, tmp_path: Path) -> None:
    path = _file(tmp_path)
    _csv(path, CARD_FIELDS, [_card_row("A", 1, 2), _card_row("B", 1, 2)])
    signals.import_signals(store, tmp_path, commander=COMMANDER)
    _csv(path, CARD_FIELDS, [_card_row("A", 2, 2)])
    report = signals.import_signals(store, tmp_path, commander=COMMANDER, replace=False)
    assert _names(store, signals.SIGNAL_INCLUSION) == {"A", "B"}
    assert report["mode"] == "append"
    row = store.connection.execute(
        "SELECT numerator FROM card_signal WHERE card_name = 'A' AND signal = ?",
        (signals.SIGNAL_INCLUSION,),
    ).fetchone()
    assert row[0] == 2


def test_header_only_file_is_a_warning_not_imported(store: StudioStore, tmp_path: Path) -> None:
    path = _file(tmp_path)
    _csv(path, CARD_FIELDS, [_card_row("A", 1, 2)])
    signals.import_signals(store, tmp_path, commander=COMMANDER)
    _csv(path, CARD_FIELDS, [])
    report = signals.import_signals(store, tmp_path, commander=COMMANDER)
    entry = _files(report)[signals.CARD_FILE]
    assert entry["status"] == "NOTHING_REPLACED"
    assert entry["rows_written"] == 0 and entry["rows_kept"] > 0
    assert _names(store, signals.SIGNAL_INCLUSION) == {"A"}  # earlier rows untouched


def test_bom_header_is_read(store: StudioStore, tmp_path: Path) -> None:
    _csv(_file(tmp_path), CARD_FIELDS, [_card_row("A", 1, 2)], bom=True)
    report = signals.import_signals(store, tmp_path, commander=COMMANDER)
    assert _files(report)[signals.CARD_FILE]["rows_written"] == 2


def test_unknown_values_carry_a_counted_reason(store: StudioStore, tmp_path: Path) -> None:
    _csv(
        _file(tmp_path),
        CARD_FIELDS,
        [
            _card_row("A", 5, 2),
            _card_row("B", "n/a", 2),
            _card_row("C", 1, 0),
            _card_row("D", 1, 2, syn=""),
            _card_row("E", 1, 2, syn="x"),
        ],
    )
    entry = _files(signals.import_signals(store, tmp_path, commander=COMMANDER))[signals.CARD_FILE]
    assert entry["null_value_reasons"]["NUM_DECKS_ABOVE_POTENTIAL_DECKS"] == 1
    assert entry["null_value_reasons"]["DECK_COUNTS_MISSING_OR_NOT_NUMERIC"] == 1
    assert entry["null_value_reasons"]["POTENTIAL_DECKS_NOT_POSITIVE"] == 1
    assert entry["null_value_reasons"]["SYNERGY_NOT_NUMERIC"] == 1
    assert entry["null_value_reasons"]["SYNERGY_NOT_PUBLISHED"] == 1
    # the unknown inclusion is NULL, never 0
    nulls = store.connection.execute(
        "SELECT COUNT(*) FROM card_signal WHERE signal = ? AND value IS NULL",
        (signals.SIGNAL_INCLUSION,),
    ).fetchone()[0]
    assert nulls == 3


def test_conflicting_duplicate_is_reported_and_first_kept(
    store: StudioStore, tmp_path: Path
) -> None:
    _csv(_file(tmp_path), CARD_FIELDS, [_card_row("A", 1, 2), _card_row("A", 2, 2)])
    report = signals.import_signals(store, tmp_path, commander=COMMANDER)
    entry = _files(report)[signals.CARD_FILE]
    assert entry["skipped_reasons"]["DUPLICATE_CONFLICT"] == 1
    assert any("different figures" in warning for warning in entry["warnings"])


def test_a_split_file_carries_one_source_covering_all_parts(
    store: StudioStore, tmp_path: Path
) -> None:
    tmp_path.mkdir(exist_ok=True)
    _csv(tmp_path / "commander_card_signals_1.csv", CARD_FIELDS, [_card_row("A", 1, 2)])
    _csv(tmp_path / "commander_card_signals_2.csv", CARD_FIELDS, [_card_row("B", 1, 2)])
    signals.import_signals(store, tmp_path, commander=COMMANDER)
    titles = {
        str(r[0])
        for r in store.connection.execute(
            "SELECT s.title FROM card_signal c JOIN source s USING (source_id) WHERE c.signal = ?",
            (signals.SIGNAL_INCLUSION,),
        )
    }
    assert titles == {"commander_card_signals_1.csv (+1 parts)"}


def test_commander_names_match_case_insensitively(store: StudioStore, tmp_path: Path) -> None:
    store.connection.execute(
        "INSERT INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('corpus_deck', 'd1', ?, 'IMPORT_DECLARED')",
        (COMMANDER,),
    )
    _csv(
        _file(tmp_path),
        CARD_FIELDS,
        [_card_row("A", 1, 2, name=COMMANDER.upper()), _card_row("B", 1, 2)],
    )
    signals.import_signals(store, tmp_path, commander=COMMANDER.lower())
    commanders = {
        str(r[0])
        for r in store.connection.execute("SELECT DISTINCT commander_name FROM card_signal")
    }
    assert commanders == {COMMANDER}


def test_commander_is_required(store: StudioStore, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="commander name is required"):
        signals.import_signals(store, tmp_path, commander="  ")


def test_cli_requires_an_explicit_commander(tmp_path: Path) -> None:
    from commander_lab.studio.__main__ import main

    with pytest.raises(SystemExit) as raised:
        main(["--data", str(tmp_path / "d"), "import-signals", str(tmp_path)])
    assert raised.value.code == 2


def test_salt_and_combo_signals(store: StudioStore, tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    _csv(
        tmp_path / "edhrec_salt.csv",
        ["card_name", "salt", "rank"],
        [
            {"card_name": "Stasis", "salt": 3.05, "rank": 1},
            {"card_name": "Broken", "salt": "x", "rank": 2},
        ],
    )
    _csv(
        tmp_path / "edhrec_test_commander_combos.csv",
        ["combo_label", "cards", "num_decks"],
        [
            {"combo_label": "1", "cards": f"{COMMANDER};Alpha;Beta", "num_decks": 100},
            {"combo_label": "2", "cards": "Alpha;Gamma", "num_decks": 40},
            {"combo_label": "3", "cards": "Alpha;Gamma", "num_decks": 40},
            {"combo_label": "4", "cards": "Delta", "num_decks": "many"},
        ],
    )
    report = signals.import_signals(store, tmp_path, commander=COMMANDER)
    files = _files(report)
    assert files[signals.SALT_FILE]["skipped_reasons"] == {"SALT_NOT_NUMERIC": 1}
    salt = store.connection.execute(
        "SELECT value, commander_name FROM card_signal WHERE signal = ?", (signals.SIGNAL_SALT,)
    ).fetchall()
    assert [(row[0], row[1]) for row in salt] == [(3.05, "")]
    combo = {
        str(r[0]): (r[1], r[2])
        for r in store.connection.execute(
            "SELECT card_name, value, numerator FROM card_signal WHERE signal = ? "
            "AND commander_name = ?",
            (signals.SIGNAL_COMBO_DECKS, COMMANDER),
        )
    }
    assert combo == {"Alpha": (100.0, 2), "Beta": (100.0, 1), "Gamma": (40.0, 1)}
    assert files["edhrec_test_commander_combos"]["skipped_reasons"] == {
        "DUPLICATE_COMBO": 1,
        "NUM_DECKS_NOT_NUMERIC": 1,
    }
    again = signals.import_signals(store, tmp_path, commander=COMMANDER)
    assert again["rows_written"] == report["rows_written"]
    written = report["rows_written"]
    assert isinstance(written, int)
    assert store.count("card_signal") == written


def test_a_folder_with_only_a_combos_or_salt_file_is_a_signal_folder(tmp_path: Path) -> None:
    combos = tmp_path / "combos"
    combos.mkdir()
    assert not signals.has_signal_files(combos)
    (combos / f"{signals.COMBOS_FILE}.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert signals.has_signal_files(combos)
    salt = tmp_path / "salt"
    salt.mkdir()
    (salt / f"{signals.SALT_FILE}.csv").write_text("card_name,salt\nA,1\n", encoding="utf-8")
    assert signals.has_signal_files(salt)


def test_a_combos_file_of_any_commander_makes_a_signal_folder(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "edhrec_atraxa_combos.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert signals.has_signal_files(other)
    numbered = tmp_path / "numbered"
    numbered.mkdir()
    (numbered / "edhrec_kinnan_bonder_prodigy_combos_2.csv").write_text("a\n1\n", encoding="utf-8")
    assert signals.has_signal_files(numbered)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "notes_combos.csv").write_text("a\n1\n", encoding="utf-8")
    assert not signals.has_signal_files(unrelated)
