"""Listed combos of a commander against a deck (schema 14): import of the full card sets,
complete and one-short comparison, name matching by front face only."""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio import combos, signals
from commander_lab.studio.store import SCHEMA_VERSION, StudioStore

COMMANDER = "Chulane, Teller of Tales"


def _combo_file(folder: Path, lines: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "edhrec_chulane_combos.csv").write_text(
        "combo_label,cards,num_decks\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )


def _store_with_cards(names: list[tuple[str, str]]) -> tuple[StudioStore, list[dict[str, str]]]:
    """A store plus deck rows shaped like ``decks.list_rows`` (``oracle_name``, ``zone``)."""
    store = StudioStore.in_memory()
    return store, [{"oracle_name": name, "zone": zone} for name, zone in names]


def _import(store: StudioStore, folder: Path, *, replace: bool = True) -> None:
    reports: dict[str, signals.FileReport] = {}
    with store.connection:
        signals._import_combos(store, folder, COMMANDER, reports, replace=replace)


def test_the_schema_is_14_and_holds_the_combo_table() -> None:
    store = StudioStore.in_memory()
    tables = {
        str(row[0])
        for row in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert SCHEMA_VERSION == 15
    assert "commander_combo" in tables


def test_import_stores_the_full_card_set_with_the_commander(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    _combo_file(
        tmp_path,
        [
            f'x,"{COMMANDER};Intruder Alarm",10468',
            "y,Intruder Alarm;Shrieking Drake,6671",
            "bad,,5",
        ],
    )
    _import(store, tmp_path)
    stored = combos.stored_combos(store, COMMANDER)
    assert stored == [
        ([COMMANDER, "Intruder Alarm"], 10468),
        (["Intruder Alarm", "Shrieking Drake"], 6671),
    ]


def test_a_replacing_import_swaps_the_list_and_an_appending_one_adds(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    first, second = tmp_path / "a", tmp_path / "b"
    _combo_file(first, ["y,Intruder Alarm;Shrieking Drake,6671"])
    _combo_file(second, ["z,Aluren;Whitemane Lion,300"])
    _import(store, first)
    _import(store, second, replace=False)
    assert [cards for cards, _ in combos.stored_combos(store, COMMANDER)] == [
        ["Intruder Alarm", "Shrieking Drake"],
        ["Aluren", "Whitemane Lion"],
    ]
    _import(store, second)
    assert combos.stored_combos(store, COMMANDER) == [(["Aluren", "Whitemane Lion"], 300)]


def test_complete_and_one_short_combos_of_a_deck(tmp_path: Path) -> None:
    store, rows = _store_with_cards(
        [(COMMANDER, "commander"), ("Intruder Alarm", "main"), ("Aluren", "main")]
    )
    _combo_file(
        tmp_path,
        [
            f'x,"{COMMANDER};Intruder Alarm",10468',
            "y,Intruder Alarm;Shrieking Drake,6671",
            "z,Aluren;Whitemane Lion,300",
            "far,Food Chain;Eternal Scourge;Misthollow Griffin,50",
        ],
    )
    _import(store, tmp_path)
    result = combos.deck_combos(store, rows)  # type: ignore[arg-type]
    assert result["listed"] == 4
    assert result["complete"] == [{"cards": [COMMANDER, "Intruder Alarm"], "num_decks": 10468}]
    assert result["one_missing"] == [
        {
            "cards": ["Intruder Alarm", "Shrieking Drake"],
            "num_decks": 6671,
            "missing": "Shrieking Drake",
        },
        {"cards": ["Aluren", "Whitemane Lion"], "num_decks": 300, "missing": "Whitemane Lion"},
    ]


def test_a_two_part_card_matches_by_its_front_face_never_by_the_back(tmp_path: Path) -> None:
    store, rows = _store_with_cards([(COMMANDER, "commander"), ("Fire // Ice", "main")])
    _combo_file(tmp_path, ["front,Fire;Aluren,10", "back,Ice;Aluren,9"])
    _import(store, tmp_path)
    result = combos.deck_combos(store, rows)  # type: ignore[arg-type]
    one_missing = result["one_missing"]
    assert isinstance(one_missing, list)
    assert [entry["cards"] for entry in one_missing] == [["Aluren", "Fire"]]
    assert one_missing[0]["missing"] == "Aluren"


def test_without_a_stored_list_nothing_is_claimed() -> None:
    store, rows = _store_with_cards([(COMMANDER, "commander"), ("Intruder Alarm", "main")])
    result = combos.deck_combos(store, rows)  # type: ignore[arg-type]
    assert result["listed"] == 0
    assert result["complete"] == []
    assert result["one_missing"] == []


def test_an_appending_import_updates_the_deck_count_of_a_stored_set(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    first, second = tmp_path / "a", tmp_path / "b"
    _combo_file(first, ["y,Intruder Alarm;Shrieking Drake,6671"])
    _combo_file(second, ["y,Intruder Alarm;Shrieking Drake,7000", "z,Aluren;Whitemane Lion,300"])
    _import(store, first)
    _import(store, second, replace=False)
    assert combos.stored_combos(store, COMMANDER) == [
        (["Intruder Alarm", "Shrieking Drake"], 7000),
        (["Aluren", "Whitemane Lion"], 300),
    ]


def test_a_damaged_row_is_skipped_and_the_deck_check_still_answers(tmp_path: Path) -> None:
    store, rows = _store_with_cards(
        [(COMMANDER, "commander"), ("Intruder Alarm", "main"), ("Shrieking Drake", "main")]
    )
    _combo_file(tmp_path, ["y,Intruder Alarm;Shrieking Drake,6671"])
    _import(store, tmp_path)
    with store.connection:
        for ordinal, cards in enumerate(["not json", "{}", "[]", "[1, 2]", '["", "x"]'], 50):
            store.connection.execute(
                "INSERT INTO commander_combo(commander_name, ordinal, cards, num_decks, source_id) "
                "SELECT ?, ?, ?, 5, source_id FROM commander_combo WHERE ordinal = 1",
                (COMMANDER, ordinal, cards),
            )
    assert combos.stored_combos(store, COMMANDER) == [(["Intruder Alarm", "Shrieking Drake"], 6671)]
    found = combos.deck_combos(store, rows)
    assert found["listed"] == 1
    assert [entry["cards"] for entry in found["complete"]] == [
        ["Intruder Alarm", "Shrieking Drake"]
    ]


def test_the_commander_name_matches_whatever_its_case(tmp_path: Path) -> None:
    store, rows = _store_with_cards(
        [(COMMANDER.lower(), "commander"), ("Intruder Alarm", "main"), ("Shrieking Drake", "main")]
    )
    _combo_file(tmp_path, ["y,Intruder Alarm;Shrieking Drake,6671"])
    _import(store, tmp_path)
    assert combos.deck_combos(store, rows)["listed"] == 1


def test_a_list_without_a_commander_names_no_commander() -> None:
    store, rows = _store_with_cards([("Intruder Alarm", "main")])
    found = combos.deck_combos(store, rows)
    assert (found["commanders"], found["listed"]) == ([], 0)
    app = (Path(combos.__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    assert "Kein Commander gewählt" in app


def test_the_result_names_the_source_of_the_combo_list(tmp_path: Path) -> None:
    store, rows = _store_with_cards([(COMMANDER, "commander"), ("Intruder Alarm", "main")])
    assert combos.deck_combos(store, rows)["sources"] == []  # type: ignore[arg-type]
    _combo_file(tmp_path, ["y,Intruder Alarm;Shrieking Drake,6671"])
    _import(store, tmp_path)
    sources = combos.deck_combos(store, rows)["sources"]  # type: ignore[arg-type]
    assert isinstance(sources, list) and len(sources) == 1
    assert sources[0]["title"] and sources[0]["imported_at"]
    assert set(sources[0]) == {"title", "snapshot_date", "imported_at"}
