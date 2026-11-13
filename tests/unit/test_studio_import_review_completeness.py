"""Review findings on the completeness report (rulings status, per bracket, scope, names)."""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio import StudioStore, completeness, import_all
from commander_lab.studio.queries import legal_pool
from tests.unit.test_studio_import_all import COMMANDER, _delivery, _layers, _run, _write_csv
from tests.unit.test_studio_store import _card, _synthetic_cards, _workbook


def _filled(tmp_path: Path) -> tuple[StudioStore, dict[str, Path], dict[str, object]]:
    files = _delivery(tmp_path)
    store = StudioStore.in_memory()
    return store, files, _run(store, files)


def _rebuilt(store: StudioStore) -> dict[str, completeness.LayerRow]:
    rows, _, _ = completeness.build_layers(store, COMMANDER)
    return {row["layer"]: row for row in rows}


def test_rulings_status_is_never_forced(tmp_path: Path) -> None:
    store, _, report = _filled(tmp_path)
    assert _layers(report)["rulings"]["status"].startswith("ERFASST")
    store.connection.execute("UPDATE card_ruling SET oracle_id = 'oracle-foreign'")
    layer = _rebuilt(store)["rulings"]
    assert layer["n"] == 0
    assert layer["status"] == completeness.MISSING


def test_table_prints_the_notes(tmp_path: Path) -> None:
    _, _, report = _filled(tmp_path)
    text = completeness.format_table(report)
    assert "Quelle nennt nur Karten mit Regeltext" in text
    assert "nur die veröffentlichte Top-Liste" in text


def test_one_row_per_bracket(tmp_path: Path) -> None:
    files = _delivery(tmp_path)
    _write_csv(
        files["research"] / "pack" / "commander_bracket_signals_core_1.csv",
        ["commander_name", "variant", "card_name", "num_decks", "potential_decks"],
        [
            {"commander_name": COMMANDER, "variant": "core", "card_name": f"Filler {i:02d}",
             "num_decks": 1, "potential_decks": 2}
            for i in range(1, 4)
        ],
    )  # fmt: skip
    layers = _layers(_run(StudioStore.in_memory(), files))
    assert layers["bracket_inclusion_core"]["n"] == 3
    assert layers["bracket_inclusion_core"]["status"] == completeness.PARTIAL
    assert layers["bracket_inclusion_cedh"]["status"] == completeness.NOT_DELIVERED
    assert "bracket_inclusion" not in layers


def test_rows_of_other_commanders_only_mean_not_delivered(tmp_path: Path) -> None:
    store, _, _ = _filled(tmp_path)
    store.connection.execute("UPDATE card_signal SET commander_name = 'Someone Else'")
    layers = _rebuilt(store)
    assert layers["commander_inclusion"]["status"] == completeness.NOT_DELIVERED
    assert layers["tournament"]["status"] == completeness.NOT_DELIVERED


def test_commander_card_is_not_part_of_n_for_commander_layers(tmp_path: Path) -> None:
    store, _, _ = _filled(tmp_path)
    pool = len(legal_pool(store, [COMMANDER]))
    store.connection.execute(
        "INSERT INTO card_signal(commander_name, signal, card_name, value, source_id) "
        "SELECT commander_name, signal, ?, 0.5, source_id FROM card_signal "
        "WHERE signal = 'edhrec_commander_inclusion' LIMIT 1",
        (COMMANDER,),
    )
    layers = _rebuilt(store)
    assert layers["inventory"]["of"] == pool
    assert layers["commander_inclusion"]["of"] == pool - 1
    assert layers["commander_inclusion"]["n"] == 10  # the commander's own row is not counted
    assert "Commander selbst" in layers["commander_inclusion"]["note"]


def test_names_match_casefolded_and_ambiguous_front_faces_are_not_doubled(tmp_path: Path) -> None:
    cards = [
        *_synthetic_cards(),
        _card(900, "Twin // Alpha", "G", "Creature"),
        _card(901, "Twin // Beta", "G", "Creature"),
    ]
    files = _delivery(tmp_path)
    _workbook(files["collection"], cards)
    store = StudioStore.in_memory()
    _run(store, files)
    source = store.connection.execute("SELECT source_id FROM card_signal LIMIT 1").fetchone()[0]
    for name in ("filler 20", "Twin"):
        store.connection.execute(
            "INSERT INTO card_signal(commander_name, signal, card_name, value, source_id) "
            "VALUES (?, 'edhrec_commander_synergy', ?, 0.5, ?)",
            (COMMANDER, name, source),
        )
    before = _rebuilt(store)["synergy"]["n"]
    store.connection.execute("DELETE FROM card_signal WHERE card_name IN ('filler 20', 'Twin')")
    after = _rebuilt(store)["synergy"]["n"]
    assert before == (after or 0) + 1  # "filler 20" counts, the shared front face "Twin" does not


def test_import_all_module_exposes_aborted_marker() -> None:
    assert import_all.NOT_READ.startswith("nicht gelesen")
