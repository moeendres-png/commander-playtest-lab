"""External deck lists, deck universes and tiers: counting rules on synthetic decks.

All decks here are invented. No network, no engine.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from commander_lab.studio import (
    StudioStore,
    decklist_import,
    sources,
    tiers,
    universe,
    universe_view,
)

CHULANE = "Chulane, Teller of Tales"


def _edhrec_file(folder: Path, urlhash: str, cards: list[tuple[str, int]], **extra: object) -> None:
    payload = {
        "urlhash": urlhash,
        "variante": "upgraded",
        "bracket": 3,
        "savedate": "2026-10-01",
        "source_url": f"https://archidekt.com/decks/{urlhash}",
        "commanders": [CHULANE],
        "cards": [{"name": name, "quantity": qty} for name, qty in cards],
        "karten_summe": sum(qty for _, qty in cards),
        "parse_status": "ok",
    }
    payload.update(extra)
    (folder / f"{urlhash}.json").write_text(json.dumps(payload), encoding="utf-8")


def _archidekt_file(folder: Path, deck_id: int, cards: list[dict], **extra: object) -> None:
    payload = {
        "id": deck_id,
        "bracket": 4,
        "updated_at": "2026-09-15",
        "cards": cards,
        "summe_hauptdeck": 100,
        "summe_gesamt": 100,
    }
    payload.update(extra)
    (folder / f"{deck_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _card(name: str, quantity: int = 1, categories: list[str] | None = None, **kw: object) -> dict:
    return {"name": name, "quantity": quantity, "categories": categories or [], **kw}


@pytest.fixture()
def store() -> StudioStore:
    return StudioStore.in_memory()


def test_import_edhrec_decklists_registers_decks_cards_and_cohorts(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)])
    _edhrec_file(tmp_path, "bbb", [(CHULANE, 1), ("Sol Ring", 1), ("Island", 9)])
    result = decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert result == {"decks": 2, "duplicates_marked": 0, "card_rows": 6, "files_without_cards": 0}
    db = store.connection
    assert db.execute("SELECT COUNT(*) FROM corpus_deck").fetchone()[0] == 2
    sections = {
        (row[0], row[1])
        for row in db.execute(
            "SELECT card_name, section FROM corpus_deck_card WHERE deck_id = 'edhrec:aaa'"
        )
    }
    assert (CHULANE, "commander") in sections and ("Sol Ring", "main") in sections
    cohorts = {
        row[0]
        for row in db.execute("SELECT cohort FROM corpus_cohort WHERE deck_id = 'edhrec:aaa'")
    }
    assert cohorts == {"source:edhrec", "bracket:3", "variant:upgraded", "commander:chulane"}
    row = db.execute(
        "SELECT cohort, play_group, legality_audit FROM corpus_deck WHERE deck_id = 'edhrec:aaa'"
    ).fetchone()
    assert tuple(row) == ("chulane", "community", "not_audited")
    # Re-importing the same folder is a replace, not an append and not a self-duplicate.
    again = decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert again["decks"] == 2 and again["duplicates_marked"] == 0
    assert db.execute("SELECT COUNT(*) FROM corpus_deck").fetchone()[0] == 2


def test_import_marks_exact_duplicates_across_sources(store: StudioStore, tmp_path: Path) -> None:
    edhrec = tmp_path / "edhrec"
    edhrec.mkdir()
    archidekt = tmp_path / "archidekt"
    archidekt.mkdir()
    cards = [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)]
    _edhrec_file(edhrec, "aaa", cards)
    _archidekt_file(
        archidekt,
        42,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Sol Ring"),
            _card("Forest", 10),
            _card("Sideboard Card", 1, ["Sideboard"]),
        ],
    )
    decklist_import.import_decklists(store, edhrec, format="edhrec")
    result = decklist_import.import_decklists(store, archidekt, format="archidekt")
    # Not a duplicate: the Archidekt deck carries an extra sideboard card, so its
    # fingerprint differs. A truly identical list would be marked.
    assert result["duplicates_marked"] == 0
    _archidekt_file(
        archidekt,
        43,
        [_card(CHULANE, 1, ["Commander"]), _card("Sol Ring"), _card("Forest", 10)],
    )
    (archidekt / "42.json").unlink()
    result = decklist_import.import_decklists(store, archidekt, format="archidekt")
    assert result["duplicates_marked"] == 1
    row = store.connection.execute(
        "SELECT duplicate_of FROM corpus_deck WHERE deck_id = 'archidekt:43'"
    ).fetchone()
    assert row[0] == "edhrec:aaa"


def test_archidekt_sections_follow_category_names(store: StudioStore, tmp_path: Path) -> None:
    _archidekt_file(
        tmp_path,
        7,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Sol Ring"),
            _card("Wish Card", 1, ["Sideboard"]),
            _card("Maybe Card", 1, ["Maybeboard"]),
            _card("Partner Card", 1, [], companion=True),
        ],
    )
    decklist_import.import_decklists(store, tmp_path, format="archidekt")
    sections = {
        row[0]: row[1]
        for row in store.connection.execute(
            "SELECT card_name, section FROM corpus_deck_card WHERE deck_id = 'archidekt:7'"
        )
    }
    assert sections == {
        CHULANE: "commander",
        "Sol Ring": "main",
        "Wish Card": "sideboard",
        "Maybe Card": "maybeboard",
        "Partner Card": "companion",
    }


def test_import_merges_split_rows_of_one_section(store: StudioStore, tmp_path: Path) -> None:
    # Real Archidekt exports list one card in several category groups of the same
    # section; the corpus table is keyed by (deck, card, section), so rows merge.
    _archidekt_file(
        tmp_path,
        9,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Forest", 4, ["Land"]),
            _card("Forest", 6, ["Ramp", "Land"]),
        ],
    )
    result = decklist_import.import_decklists(store, tmp_path, format="archidekt")
    assert result["card_rows"] == 2
    row = store.connection.execute(
        "SELECT quantity FROM corpus_deck_card WHERE deck_id = 'archidekt:9' "
        "AND card_name = 'Forest'"
    ).fetchone()
    assert row[0] == 10


def test_reimport_of_the_original_keeps_it_canonical(store: StudioStore, tmp_path: Path) -> None:
    # Review regression: A imported, identical B marked as A's duplicate, then A
    # re-imported (the refresh workflow). A must stay canonical; with the first
    # implementation both pointed at each other and vanished from every universe.
    first = tmp_path / "first"
    first.mkdir()
    second = tmp_path / "second"
    second.mkdir()
    cards = [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)]
    _edhrec_file(first, "aaa", cards)
    _archidekt_file(
        second,
        43,
        [_card(CHULANE, 1, ["Commander"]), _card("Sol Ring"), _card("Forest", 10)],
    )
    decklist_import.import_decklists(store, first, format="edhrec")
    decklist_import.import_decklists(store, second, format="archidekt")
    result = decklist_import.import_decklists(store, first, format="edhrec")
    assert result["duplicates_marked"] == 0
    db = store.connection
    assert (
        db.execute("SELECT duplicate_of FROM corpus_deck WHERE deck_id = 'edhrec:aaa'").fetchone()[
            0
        ]
        is None
    )
    assert (
        db.execute(
            "SELECT duplicate_of FROM corpus_deck WHERE deck_id = 'archidekt:43'"
        ).fetchone()[0]
        == "edhrec:aaa"
    )
    counted = universe.inclusion(store, card_names=["Sol Ring"], commander_names=None)
    assert counted["denominator"] == 1 and counted["rows"][0]["hits"] == 1


def test_reimport_of_a_folder_with_duplicates_is_stable(store: StudioStore, tmp_path: Path) -> None:
    cards = [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)]
    _edhrec_file(tmp_path, "aaa", cards)
    _edhrec_file(tmp_path, "bbb", cards)
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    snapshot_first = universe.snapshot_id(store, commander_names=None)
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert universe.snapshot_id(store, commander_names=None) == snapshot_first
    rows = dict(
        store.connection.execute("SELECT deck_id, duplicate_of FROM corpus_deck").fetchall()
    )
    assert rows == {"edhrec:aaa": None, "edhrec:bbb": "edhrec:aaa"}


def test_import_rejects_broken_deck_files_with_the_file_name(
    store: StudioStore, tmp_path: Path
) -> None:
    (tmp_path / "kaputt.json").write_text(
        json.dumps({"bracket": 3, "cards": [{"quantity": 1}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"kaputt\.json"):
        decklist_import.import_decklists(store, tmp_path, format="edhrec")
    (tmp_path / "kaputt.json").write_text(
        json.dumps({"cards": [{"name": "Sol Ring", "quantity": 1}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"kaputt\.json"):
        decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert store.count("corpus_deck") == 0


def test_universe_inclusion_counts_only_the_selected_decks(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)])
    _edhrec_file(tmp_path, "bbb", [(CHULANE, 1), ("Island", 9)], bracket=4, variante="optimized")
    decklist_import.import_decklists(store, tmp_path, format="edhrec")

    everything = universe.inclusion(store, commander_names=None)
    assert everything["denominator"] == 2
    by_name = {row["card_name"]: row for row in everything["rows"]}
    assert by_name["Sol Ring"]["hits"] == 1 and by_name["Sol Ring"]["share"] == 0.5

    universe.save_profile(store, "nur-bracket-3", {"cohorts": ["bracket:3"]})
    only_b3 = universe.inclusion(
        store, profile="nur-bracket-3", card_names=["Sol Ring", "Island"], commander_names=None
    )
    assert only_b3["denominator"] == 1
    rows = {row["card_name"]: row for row in only_b3["rows"]}
    assert rows["Sol Ring"]["hits"] == 1 and rows["Island"]["hits"] == 0

    empty = universe.inclusion(
        store, spec={"cohorts": ["bracket:5"]}, card_names=["Sol Ring"], commander_names=None
    )
    assert empty["denominator"] == 0 and empty["rows"][0]["share"] is None

    with pytest.raises(KeyError):
        universe.inclusion(store, profile="gibt-es-nicht", commander_names=None)
    with pytest.raises(ValueError):
        universe.save_profile(store, "kaputt", {"farbe": ["gruen"]})


def test_universe_date_and_size_filters_and_cooccurrence(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)])
    _edhrec_file(tmp_path, "bbb", [(CHULANE, 1), ("Sol Ring", 1)], savedate="2025-01-01")
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert universe.resolve_universe(store, {"date_from": "2026-01-01"}) == ["edhrec:aaa"]
    assert universe.resolve_universe(store, {"min_main_cards": 5}) == ["edhrec:aaa"]
    pairs = universe.cooccurrence(store, "Sol Ring", commander_names=None)
    assert pairs["decks_with_card"] == 2
    assert {pair["card_name"] for pair in pairs["pairs"]} == {CHULANE, "Forest"}


def test_cooccurrence_counts_each_deck_once_and_spec_types_are_checked(
    store: StudioStore, tmp_path: Path
) -> None:
    # One deck whose Sol Ring sits in two counted sections (commander + main):
    # decks_with_card must still be 1.
    _archidekt_file(
        tmp_path,
        11,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Sol Ring", 1, ["Commander"]),
            _card("Sol Ring", 1, []),
        ],
    )
    decklist_import.import_decklists(store, tmp_path, format="archidekt")
    pairs = universe.cooccurrence(store, "Sol Ring", commander_names=None)
    assert pairs["decks_with_card"] == 1
    with pytest.raises(ValueError):
        universe.resolve_universe(store, {"platforms": "edhrec"})
    with pytest.raises(ValueError):
        universe.resolve_universe(store, {"date_from": "gestern"})


def test_snapshot_changes_when_a_decks_cards_change(store: StudioStore, tmp_path: Path) -> None:
    _edhrec_file(tmp_path, "s1", [(CHULANE, 1), ("Sol Ring", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    before = universe.snapshot_id(store, commander_names=None)
    _edhrec_file(tmp_path, "s1", [(CHULANE, 1), ("Black Lotus", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert universe.snapshot_id(store, commander_names=None) != before


def test_tier_params_keep_an_explicitly_empty_cut_list() -> None:
    params = tiers.TierParams.from_dict({"cuts": [], "min_universe": 5})
    assert params.cuts == ()
    tier, reason = tiers.tier_for_share(0.9, 10, params)
    assert (tier, reason) == ("D", "BELOW_LOWEST_CUT")
    defaulted = tiers.TierParams.from_dict({"min_universe": 5})
    assert defaulted.cuts == tiers.TierParams().cuts


def test_tiers_are_pure_counts_with_a_u_state(store: StudioStore, tmp_path: Path) -> None:
    for index in range(4):
        _edhrec_file(
            tmp_path,
            f"d{index}",
            [(CHULANE, 1), ("Sol Ring", 1), (f"Filler Card {index}", 1)]
            + ([("Rare Card", 1)] if index == 0 else []),
        )
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    counted = universe.inclusion(store, commander_names=None)
    snapshot = universe.snapshot_id(store, commander_names=None)
    params = tiers.TierParams(min_universe=30)
    result = {
        row["card_name"]: row
        for row in tiers.tiers_for_universe(counted, universe_snapshot=snapshot, params=params)
    }
    # Four decks are below the minimum universe of 30: everything is U, nothing guessed.
    assert {row["tier"] for row in result.values()} == {"U"}
    assert result["Sol Ring"]["reason"] == "UNIVERSE_TOO_SMALL"

    params = tiers.TierParams(min_universe=4, cuts=(("S", 0.9), ("A", 0.5)))
    result = {
        row["card_name"]: row
        for row in tiers.tiers_for_universe(counted, universe_snapshot=snapshot, params=params)
    }
    assert result["Sol Ring"]["tier"] == "S"  # 4/4 decks
    assert result["Rare Card"]["tier"] == "D"  # 1/4 decks, below the lowest cut
    assert result["Rare Card"]["share"] == 0.25
    assert result["Rare Card"]["universe_snapshot"] == snapshot

    # A new deck changes the snapshot: figures counted later cite a different universe.
    _edhrec_file(tmp_path, "d4", [(CHULANE, 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert universe.snapshot_id(store, commander_names=None) != snapshot


def test_changed_reimport_releases_stale_duplicate_marks(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "a", [(CHULANE, 1), ("Sol Ring", 1)])
    _edhrec_file(tmp_path, "b", [(CHULANE, 1), ("Sol Ring", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    assert universe.inclusion(store, commander_names=None)["denominator"] == 1
    _edhrec_file(tmp_path, "a", [(CHULANE, 1), ("Black Lotus", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    counted = universe.inclusion(store, card_names=["Sol Ring"], commander_names=None)
    assert counted["denominator"] == 2
    assert counted["rows"][0]["hits"] == 1
    marks = dict(store.connection.execute("SELECT deck_id, duplicate_of FROM corpus_deck"))
    assert marks == {"edhrec:a": None, "edhrec:b": None}


def test_duplicates_are_collapsed_inside_the_selected_universe(
    store: StudioStore, tmp_path: Path
) -> None:
    cards = [(CHULANE, 1), ("Sol Ring", 1)]
    _edhrec_file(tmp_path, "a", cards, savedate="2026-05-01")
    _edhrec_file(tmp_path, "b", cards, savedate="2020-05-01")
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    old = universe.inclusion(
        store, spec={"date_to": "2021-01-01"}, card_names=["Sol Ring"], commander_names=None
    )
    assert old["denominator"] == 1 and old["rows"][0]["hits"] == 1
    assert universe.inclusion(store, commander_names=None)["denominator"] == 1


@pytest.mark.parametrize("quantity", [0, -1])
def test_non_positive_quantities_are_not_hits(
    store: StudioStore, tmp_path: Path, quantity: int
) -> None:
    _edhrec_file(tmp_path, "q", [(CHULANE, 1), ("Sol Ring", 1), ("Ghost Card", quantity)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    ghost = universe.inclusion(store, card_names=["Ghost Card"], commander_names=None)["rows"][0]
    assert ghost["hits"] == 0
    assert universe.cooccurrence(store, "Ghost Card", commander_names=None)["decks_with_card"] == 0
    names = {
        pair["card_name"]
        for pair in universe.cooccurrence(store, "Sol Ring", commander_names=None)["pairs"]
    }
    assert "Ghost Card" not in names
    # Even a row that reached the table directly is not counted by the queries.
    store.connection.execute(
        "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
        "normalization_status) VALUES ('edhrec:q', 'Raw Ghost', 'main', NULL, ?, 'source_name')",
        (quantity,),
    )
    assert (
        universe.inclusion(store, card_names=["Raw Ghost"], commander_names=None)["rows"][0]["hits"]
        == 0
    )
    assert universe.cooccurrence(store, "Raw Ghost", commander_names=None)["decks_with_card"] == 0


def test_tier_params_are_validated() -> None:
    with pytest.raises(ValueError):
        tiers.TierParams(cuts=(("C", 0.1), ("S", 0.5)))
    with pytest.raises(ValueError):
        tiers.TierParams(cuts=(("S", 0.5), ("A", 0.5)))
    with pytest.raises(ValueError):
        tiers.TierParams(cuts=(("S", 1.5),))
    with pytest.raises(ValueError):
        tiers.TierParams(cuts=(("S", 0.0),))
    with pytest.raises(ValueError):
        tiers.TierParams(min_universe=-5)
    with pytest.raises(ValueError):
        tiers.TierParams(min_universe=0)
    with pytest.raises(ValueError):
        tiers.TierParams(cuts=(("", 0.5),))
    with pytest.raises(ValueError):
        tiers.TierParams(cuts=(("S", 0.5), ("S", 0.2)))
    with pytest.raises(ValueError):
        tiers.TierParams(fallback_tier="")
    with pytest.raises(ValueError):
        tiers.TierParams.from_dict({"cuts": [["C", 0.1], ["S", 0.5]]})
    with pytest.raises(ValueError):
        tiers.TierParams.from_dict({"min_universe": -5})


def test_pooled_universe_reports_its_composition(store: StudioStore, tmp_path: Path) -> None:
    edhrec = tmp_path / "e"
    edhrec.mkdir()
    archidekt = tmp_path / "a"
    archidekt.mkdir()
    _edhrec_file(edhrec, "e1", [(CHULANE, 1), ("Sol Ring", 1)])
    _edhrec_file(edhrec, "e2", [(CHULANE, 1), ("Island", 1)])
    _archidekt_file(archidekt, 5, [_card(CHULANE, 1, ["Commander"]), _card("Forest")])
    decklist_import.import_decklists(store, edhrec, format="edhrec")
    decklist_import.import_decklists(store, archidekt, format="archidekt")
    counted = universe.inclusion(store, commander_names=None)
    assert counted["denominator_by_platform"] == {"archidekt": 1, "edhrec": 2}
    assert counted["denominator_by_bracket"] == {"bracket:3": 2, "bracket:4": 1}
    snapshot = universe.snapshot_id(store, commander_names=None)
    row = tiers.tiers_for_universe(
        counted, universe_snapshot=snapshot, params=tiers.TierParams(min_universe=1)
    )[0]
    assert row["denominator_by_platform"] == {"archidekt": 1, "edhrec": 2}
    assert row["denominator_by_bracket"] == {"bracket:3": 2, "bracket:4": 1}
    co = universe.cooccurrence(store, "Sol Ring", commander_names=None)
    assert co["denominator"] == 3
    assert co["denominator_by_platform"] == {"archidekt": 1, "edhrec": 2}


def test_cooccurrence_limit_is_validated(store: StudioStore, tmp_path: Path) -> None:
    _edhrec_file(tmp_path, "l", [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    for bad in (0, -1):
        with pytest.raises(ValueError):
            universe.cooccurrence(store, "Sol Ring", limit=bad, commander_names=None)
    assert (
        len(universe.cooccurrence(store, "Sol Ring", limit=None, commander_names=None)["pairs"])
        == 2
    )
    assert (
        len(universe.cooccurrence(store, "Sol Ring", limit=1, commander_names=None)["pairs"]) == 1
    )


def _raw_deck(
    store: StudioStore,
    deck_id: str,
    cards: list[tuple[str, str, int]],
    *,
    fingerprint: str,
    cohorts: tuple[str, ...] = (),
) -> None:
    """Write a deck straight to the tables, as another importer might."""
    db = store.connection
    db.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('raw', 'DERIVED_DESCRIPTIVE', 'raw', 'x', '2026-01-01')"
    )
    db.execute(
        "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, tags, "
        "fingerprint, duplicate_of, legality_audit, source_id) "
        "VALUES (?, 'c', '', 'raw', 'g', NULL, '[]', ?, NULL, 'not_audited', 'raw')",
        (deck_id, fingerprint),
    )
    db.executemany(
        "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
        "normalization_status) VALUES (?, ?, ?, NULL, ?, 'source_name')",
        [(deck_id, name, section, qty) for name, section, qty in cards],
    )
    db.executemany(
        "INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)",
        [(cohort, deck_id) for cohort in cohorts],
    )


def test_empty_fingerprints_are_unknown_and_never_collapsed(store: StudioStore) -> None:
    _raw_deck(store, "d1", [("Sol Ring", "main", 1)], fingerprint="")
    _raw_deck(store, "d2", [("Forest", "main", 1)], fingerprint="")
    assert universe.resolve_universe(store, {}) == ["d1", "d2"]
    result = universe.inclusion(store, commander_names=None)
    assert result["denominator"] == 2
    assert {row["card_name"]: row["hits"] for row in result["rows"]} == {
        "Sol Ring": 1,
        "Forest": 1,
    }


def test_decks_without_a_counted_card_row_leave_the_denominator(store: StudioStore) -> None:
    _raw_deck(store, "full", [("Sol Ring", "main", 1)], fingerprint="f1")
    _raw_deck(store, "zero", [("Sol Ring", "main", 0)], fingerprint="f2")
    _raw_deck(store, "side", [("Sol Ring", "sideboard", 1)], fingerprint="f3")
    _raw_deck(store, "bare", [], fingerprint="f4")
    assert universe.resolve_universe(store, {}) == ["full"]
    assert universe.inclusion(store, commander_names=None)["denominator"] == 1


def test_several_bracket_cohorts_are_reported_as_multiple(store: StudioStore) -> None:
    _raw_deck(store, "a", [("Sol Ring", "main", 1)], fingerprint="f1", cohorts=("bracket:3",))
    _raw_deck(
        store,
        "b",
        [("Forest", "main", 1)],
        fingerprint="f2",
        cohorts=("bracket:2", "bracket:4"),
    )
    _raw_deck(store, "c", [("Island", "main", 1)], fingerprint="f3")
    result = universe.inclusion(store, commander_names=None)
    assert result["denominator_by_bracket"] == {"bracket:3": 1, "multiple": 1, "unknown": 1}
    assert sum(result["denominator_by_bracket"].values()) == result["denominator"]


def test_large_universe_exceeds_the_sql_variable_limit(store: StudioStore) -> None:
    # Emulate an old sqlite build (999 bound variables) on any runtime.
    store.connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 900)
    for index in range(1200):
        _raw_deck(
            store,
            f"deck{index:04d}",
            [("Sol Ring", "main", 1), (f"Unique {index % 3}", "main", 1)],
            fingerprint=f"fp{index}",
            cohorts=("bracket:3",),
        )
    result = universe.inclusion(store, commander_names=None)
    assert result["denominator"] == 1200
    assert result["denominator_by_platform"] == {"raw": 1200}
    assert result["denominator_by_bracket"] == {"bracket:3": 1200}
    hits = {row["card_name"]: row["hits"] for row in result["rows"]}
    assert hits == {"Sol Ring": 1200, "Unique 0": 400, "Unique 1": 400, "Unique 2": 400}
    together = universe.cooccurrence(store, "Sol Ring", limit=None, commander_names=None)
    assert together["decks_with_card"] == 1200
    assert {p["card_name"]: p["decks_together"] for p in together["pairs"]}["Unique 1"] == 400
    assert universe.snapshot_id(store, commander_names=None).endswith(":1200")


def test_read_only_queries_leave_no_open_transaction(store: StudioStore, tmp_path: Path) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    _edhrec_file(tmp_path, "bbb", [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 3)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    store.connection.commit()
    assert store.connection.in_transaction is False
    universe.inclusion(store, spec={}, commander_names=None)
    assert store.connection.in_transaction is False
    universe.cooccurrence(store, "Sol Ring", spec={}, commander_names=None)
    assert store.connection.in_transaction is False


def test_universe_counts_only_decks_bound_to_the_commander(
    store: StudioStore, tmp_path: Path
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _edhrec_file(first, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    _edhrec_file(first, "bbb", [(CHULANE, 1), ("Island", 1)])
    _edhrec_file(second, "ccc", [("Second Commander", 1), ("Sol Ring", 1), ("Swamp", 1)])
    decklist_import.import_decklists(store, first, format="edhrec")
    store.bind_unbound(CHULANE)
    decklist_import.import_decklists(store, second, format="edhrec")

    # Without a commander every stored deck is selected; the third deck is still unbound.
    assert (
        universe.inclusion(store, card_names=["Sol Ring"], commander_names=None)["denominator"] == 3
    )
    mine = universe.inclusion(store, card_names=["Sol Ring"], commander_names=[CHULANE])
    assert (mine["rows"][0]["hits"], mine["denominator"]) == (1, 2)
    assert mine["spec"]["commanders"] == [CHULANE]
    other = ["Second Commander"]
    assert universe.inclusion(store, commander_names=other)["denominator"] == 0
    store.bind_unbound("Second Commander")
    assert universe.inclusion(store, commander_names=other)["denominator"] == 1
    assert universe.inclusion(store, commander_names=[CHULANE])["denominator"] == 2
    assert universe.snapshot_id(store, commander_names=[CHULANE]) != universe.snapshot_id(
        store, commander_names=other
    )
    assert universe.cooccurrence(store, "Sol Ring", commander_names=other)["decks_with_card"] == 1


def test_a_profile_of_one_commander_is_not_read_for_another(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    store.bind_unbound(CHULANE)
    universe.save_profile(store, "mine", {"commanders": [CHULANE]})
    assert universe.inclusion(store, profile="mine", commander_names=[CHULANE])["denominator"] == 1
    with pytest.raises(ValueError, match="not for"):
        universe.inclusion(store, profile="mine", commander_names=["Second Commander"])


def test_a_deck_list_of_another_commander_is_refused(store: StudioStore, tmp_path: Path) -> None:
    _edhrec_file(
        tmp_path, "ccc", [("Second Commander", 1), ("Sol Ring", 1)], commanders=["Second Commander"]
    )
    with pytest.raises(ValueError, match="another commander"):
        decklist_import.import_decklists(store, tmp_path, format="edhrec", commander=CHULANE)
    assert store.count("corpus_deck") == 0
    result = decklist_import.import_decklists(
        store, tmp_path, format="edhrec", commander="Second Commander"
    )
    assert result["decks"] == 1


def test_corpus_importer_mainboard_section_is_counted(store: StudioStore) -> None:
    """The corpus importer writes "mainboard"; such decks must not vanish from a universe."""
    _raw_deck(store, "corpus1", [("Sol Ring", "mainboard", 1)], fingerprint="f1")
    _raw_deck(store, "list1", [("Sol Ring", "main", 1), ("Forest", "main", 5)], fingerprint="f2")
    _raw_deck(store, "side1", [("Sol Ring", "sideboard", 1)], fingerprint="f3")
    store.connection.commit()
    assert universe.resolve_universe(store, {}) == ["corpus1", "list1"]
    result = universe.inclusion(store, spec={}, card_names=["Sol Ring"], commander_names=None)
    assert result["denominator"] == 2
    assert result["rows"][0]["hits"] == 2


def test_the_sources_commander_statement_decides_without_a_card_row(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "ddd", [("Sol Ring", 1)], commanders=["Second Commander"])
    with pytest.raises(ValueError, match="another commander"):
        decklist_import.import_decklists(store, tmp_path, format="edhrec", commander=CHULANE)


# ---------- steps 1-3: spec validation, options, counted exclusions ----------


def test_save_profile_rejects_values_the_store_does_not_hold(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    store.bind_unbound(CHULANE)
    # A typo must be refused, not silently counted as an empty universe.
    with pytest.raises(ValueError, match="unknown universe platform"):
        universe.save_profile(store, "x", {"platforms": ["archidekt"]})
    with pytest.raises(ValueError, match="unknown universe cohort"):
        universe.save_profile(store, "x", {"cohorts": ["bracket:9"]})
    with pytest.raises(ValueError, match="unknown universe commander"):
        universe.save_profile(store, "x", {"commanders": ["Nobody"]})
    assert universe.list_profiles(store) == []
    saved = universe.save_profile(
        store,
        "ok",
        {"platforms": ["edhrec"], "cohorts": ["bracket:3"], "commanders": [CHULANE]},
    )
    assert saved["spec"]["commanders"] == [CHULANE]


def test_save_profile_accepts_values_of_a_dimension_whose_stock_is_empty(
    store: StudioStore, tmp_path: Path
) -> None:
    # No decks at all: nothing can be checked, everything is accepted as-is.
    universe.save_profile(store, "leer", {"platforms": ["future"], "commanders": ["Anyone"]})
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    # Decks exist but none is bound yet: commander values cannot be checked …
    universe.save_profile(store, "ungebunden", {"commanders": ["Anyone"]})
    # … while the platform dimension, whose stock is known, is checked.
    with pytest.raises(ValueError, match="unknown universe platform"):
        universe.save_profile(store, "x", {"platforms": ["nope"]})


def test_min_universe_is_validated_and_stored(store: StudioStore, tmp_path: Path) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    for bad in (0, -3):
        with pytest.raises(ValueError, match="min_universe"):
            universe.save_profile(store, "x", {"min_universe": bad})
    universe.save_profile(store, "klein", {"min_universe": 5})
    assert universe.get_profile(store, "klein")["spec"]["min_universe"] == 5
    counted = universe.inclusion(store, profile="klein", commander_names=None)
    assert counted["spec"]["min_universe"] == 5


def _dated_deck(store: StudioStore, deck_id: str, deck_date: str | None, cards: list[str]) -> None:
    db = store.connection
    db.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('raw', 'DERIVED_DESCRIPTIVE', 'raw', 'x', '2026-01-01')"
    )
    db.execute(
        "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, tags, "
        "fingerprint, duplicate_of, legality_audit, source_id) "
        "VALUES (?, 'c', '', 'raw', 'g', ?, '[]', ?, NULL, 'not_audited', 'raw')",
        (deck_id, deck_date, f"fp-{deck_id}"),
    )
    db.executemany(
        "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
        "normalization_status) VALUES (?, ?, 'main', NULL, 1, 'source_name')",
        [(deck_id, name) for name in cards],
    )


def test_excluded_no_date_counts_only_undated_decks_the_filter_drops(
    store: StudioStore,
) -> None:
    _dated_deck(store, "neu", "2026-10-01", ["Sol Ring"])
    _dated_deck(store, "ohne-datum", None, ["Sol Ring"])
    _dated_deck(store, "alt", "2020-01-01", ["Sol Ring"])
    store.connection.commit()
    spec = {"date_from": "2026-01-01"}
    assert universe.resolve_universe(store, spec) == ["neu"]
    # "ohne-datum" is dropped only because it has no date; "alt" is dropped by its date.
    assert universe.excluded_no_date(store, spec) == 1
    counted = universe.inclusion(store, spec=spec, card_names=["Sol Ring"], commander_names=None)
    assert counted["excluded_no_date"] == 1 and counted["denominator"] == 1
    assert universe.excluded_no_date(store, {}) == 0
    # Even a range every dated deck passes drops the undated one: it has no date to check.
    assert universe.excluded_no_date(store, {"date_from": "2019-01-01"}) == 1
    assert universe.excluded_no_date(store, {"date_to": "2021-01-01"}) == 1


def test_options_report_the_stored_values_with_deck_counts(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1)])
    _edhrec_file(tmp_path, "bbb", [(CHULANE, 1), ("Island", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    _dated_deck(store, "raw1", "2026-10-01", ["Forest"])
    store.connection.execute(
        "INSERT INTO corpus_cohort(cohort, deck_id) VALUES ('bracket:4', 'raw1')"
    )
    store.bind_unbound(CHULANE)
    store.connection.execute(
        "INSERT OR IGNORE INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('corpus_deck', 'raw1', ?, 'TEST')",
        (CHULANE,),
    )
    store.connection.commit()
    found = universe.options(store)
    assert {item["value"]: item["decks"] for item in found["platforms"]} == {
        "edhrec": 2,
        "raw": 1,
    }
    cohorts = {item["value"]: item["decks"] for item in found["cohorts"]}
    assert cohorts["bracket:3"] == 2 and cohorts["bracket:4"] == 1
    assert found["commanders"] == [{"value": CHULANE, "decks": 3}]
    assert universe.options(store, commander_names=[CHULANE]) == found
    empty = universe.options(store, commander_names=["Second Commander"])
    assert empty == {"platforms": [], "cohorts": [], "commanders": []}


# ---------- step 2 (profile min_universe, model version) and A5 (lift, combos) ----------


def _studio_card(store: StudioStore, card_id: str, name: str) -> None:
    store.connection.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('raw', 'DERIVED_DESCRIPTIVE', 'raw', 'x', '2026-01-01')"
    )
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
        "VALUES (?, NULL, ?, 'C', 'raw')",
        (card_id, name),
    )


def test_a_profile_min_universe_grades_a_small_universe(store: StudioStore, tmp_path: Path) -> None:
    for index in range(3):
        _edhrec_file(tmp_path, f"m{index}", [(CHULANE, 1), ("Sol Ring", 1), (f"Filler {index}", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    _studio_card(store, "card:t:sol", "Sol Ring")
    store.connection.commit()
    universe.save_profile(store, "streng", {})
    universe.save_profile(store, "locker", {"min_universe": 3})

    strict = universe_view.pool_spread(store, "streng", commander_names=None)
    loose = universe_view.pool_spread(store, "locker", commander_names=None)
    strict_sol = next(card for card in strict["cards"] if card["name"] == "Sol Ring")
    loose_sol = next(card for card in loose["cards"] if card["name"] == "Sol Ring")
    # Three decks are below the model default of 30: U. The profile's own minimum of 3 grades.
    assert strict_sol["level"] == "U" and strict_sol["reason"] == "UNIVERSE_TOO_SMALL"
    assert strict["universe"]["below_min_universe"] is True
    assert strict["params"]["min_universe"] == 30
    assert loose_sol["level"] == "S" and loose_sol["hits"] == 3
    assert loose["universe"]["below_min_universe"] is False
    assert loose["params"]["min_universe"] == 3
    # The cuts are model constants: identical in both, and the model version is reported.
    assert (
        loose["params"]["cuts"] == strict["params"]["cuts"] == tiers.TierParams().to_dict()["cuts"]
    )
    assert strict["model_version"] == loose["model_version"] == tiers.MODEL_VERSION
    summary = universe_view.profile_summary(store, "locker", commander_names=None)
    assert summary["min_universe"] == 3 and summary["below_min_universe"] is False
    assert summary["excluded_no_date"] == 0


def test_cooccurrence_pairs_carry_lift_and_combo_partners(
    store: StudioStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edhrec_file(
        tmp_path, "d1", [(CHULANE, 1), ("Base Card", 1), ("Alpha Card", 1), ("Gamma Card", 1)]
    )
    _edhrec_file(tmp_path, "d2", [(CHULANE, 1), ("Base Card", 1), ("Alpha Card", 1)])
    _edhrec_file(tmp_path, "d3", [(CHULANE, 1), ("Gamma Card", 1)])
    _edhrec_file(tmp_path, "d4", [(CHULANE, 1), ("Gamma Card", 1), ("Delta Card", 1)])
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    store.bind_unbound(CHULANE)
    _studio_card(store, "card:t:base", "Base Card")
    store.connection.commit()
    combos = tmp_path / "combos.json"
    combos.write_text(
        json.dumps(
            {
                "combos": [
                    {"cards": ["Base Card", "Alpha Card"], "commander": "Chulane, Teller of Tales"},
                    {"cards": ["Base Card", "Gamma Card"], "commander": "Other, Person"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(universe_view, "_COMBOS_PATH", combos)
    universe.save_profile(store, "alle", {})

    result = universe_view.card_cooccurrence(
        store, "alle", "card:t:base", commander_names=[CHULANE]
    )
    assert result["decks_with_card"] == 2 and result["denominator"] == 4
    pairs = {pair["card_name"]: pair for pair in result["pairs"]}
    # Alpha: together 2 of 2 decks with the card; in 2 of 4 universe decks -> lift 2.
    assert pairs["Alpha Card"]["decks_together"] == 2
    assert pairs["Alpha Card"]["lift"] == pytest.approx(2.0)
    assert pairs["Alpha Card"]["combo_partner"] is True
    # Gamma: together 1 of 2; in 3 of 4 universe decks -> lift (1/2)/(3/4) = 2/3.
    assert pairs["Gamma Card"]["lift"] == pytest.approx(2 / 3)
    # The Gamma combo is listed for another commander: it must not mark the pair here.
    assert pairs["Gamma Card"]["combo_partner"] is False
    assert "Delta Card" not in pairs


def test_cli_save_profile_flags_and_tiers_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main

    folder = tmp_path / "studio"
    decks = tmp_path / "decks"
    decks.mkdir()
    for index in range(3):
        _edhrec_file(decks, f"c{index}", [(CHULANE, 1), ("Sol Ring", 1), (f"Filler {index}", 1)])
    store = StudioStore.open(folder)
    decklist_import.import_decklists(store, decks, format="edhrec")
    store.bind_unbound(CHULANE)
    store.close()

    assert (
        main(
            [
                "--data",
                str(folder),
                "save-profile",
                "cli",
                "--platform",
                "edhrec",
                "--commander",
                CHULANE,
                "--min-universe",
                "3",
            ]
        )
        == 0
    )
    saved = json.loads(capsys.readouterr().out)
    assert saved["spec"]["commanders"] == [CHULANE]
    assert saved["spec"]["min_universe"] == 3

    # Without --min-universe the tiers command uses the profile's own minimum (3):
    # three decks are enough, Sol Ring (3 of 3) is graded instead of U.
    assert main(["--data", str(folder), "tiers", "--profile", "cli", "--commander", CHULANE]) == 0
    result = json.loads(capsys.readouterr().out)
    sol = next(row for row in result["tiers"] if row["card_name"] == "Sol Ring")
    assert sol["tier"] == "S"
    # An explicit flag wins over the profile value.
    assert (
        main(
            [
                "--data",
                str(folder),
                "tiers",
                "--profile",
                "cli",
                "--commander",
                CHULANE,
                "--min-universe",
                "30",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    sol = next(row for row in result["tiers"] if row["card_name"] == "Sol Ring")
    assert sol["tier"] == "U"

    with pytest.raises(ValueError, match="unknown universe platform"):
        main(["--data", str(folder), "save-profile", "bad", "--platform", "nope"])


def test_spellbook_combo_partners_follow_the_commander_of_the_combo(tmp_path: Path) -> None:
    combos = tmp_path / "combos.json"
    combos.write_text(
        json.dumps(
            {
                "combos": [
                    {"cards": ["Base Card", "Alpha Card"], "commander": "Chulane, Teller of Tales"},
                    {"cards": ["Base Card", "Gamma Card"], "commander": "Other, Person"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert sources.load_spellbook_combo_partners(combos, commander="Chulane") == {
        "base card": {"alpha card"},
        "alpha card": {"base card"},
    }
    assert sources.load_spellbook_combo_partners(combos, commander="Nobody") == {}
    assert sources.load_spellbook_combo_partners(tmp_path / "fehlt.json") == {}
