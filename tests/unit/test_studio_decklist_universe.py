"""External deck lists, deck universes and tiers: counting rules on synthetic decks.

All decks here are invented. No network, no engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, decklist_import, tiers, universe

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


def test_universe_inclusion_counts_only_the_selected_decks(
    store: StudioStore, tmp_path: Path
) -> None:
    _edhrec_file(tmp_path, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Forest", 10)])
    _edhrec_file(tmp_path, "bbb", [(CHULANE, 1), ("Island", 9)], bracket=4, variante="optimized")
    decklist_import.import_decklists(store, tmp_path, format="edhrec")

    everything = universe.inclusion(store)
    assert everything["denominator"] == 2
    by_name = {row["card_name"]: row for row in everything["rows"]}
    assert by_name["Sol Ring"]["hits"] == 1 and by_name["Sol Ring"]["share"] == 0.5

    universe.save_profile(store, "nur-bracket-3", {"cohorts": ["bracket:3"]})
    only_b3 = universe.inclusion(store, profile="nur-bracket-3", card_names=["Sol Ring", "Island"])
    assert only_b3["denominator"] == 1
    rows = {row["card_name"]: row for row in only_b3["rows"]}
    assert rows["Sol Ring"]["hits"] == 1 and rows["Island"]["hits"] == 0

    empty = universe.inclusion(store, spec={"cohorts": ["bracket:5"]}, card_names=["Sol Ring"])
    assert empty["denominator"] == 0 and empty["rows"][0]["share"] is None

    with pytest.raises(KeyError):
        universe.inclusion(store, profile="gibt-es-nicht")
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
    pairs = universe.cooccurrence(store, "Sol Ring")
    assert pairs["decks_with_card"] == 2
    assert {pair["card_name"] for pair in pairs["pairs"]} == {CHULANE, "Forest"}


def test_tiers_are_pure_counts_with_a_u_state(store: StudioStore, tmp_path: Path) -> None:
    for index in range(4):
        _edhrec_file(
            tmp_path,
            f"d{index}",
            [(CHULANE, 1), ("Sol Ring", 1), (f"Filler Card {index}", 1)]
            + ([("Rare Card", 1)] if index == 0 else []),
        )
    decklist_import.import_decklists(store, tmp_path, format="edhrec")
    counted = universe.inclusion(store)
    snapshot = universe.snapshot_id(store)
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
    assert universe.snapshot_id(store) != snapshot
