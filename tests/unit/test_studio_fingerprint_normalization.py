"""Fingerprint normalization (#1394): one physical deck, two source spellings.

All decks here are invented. No network, no engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, catalog, decklist_import, universe
from commander_lab.studio.store import DataClass

CHULANE = "Chulane, Teller of Tales"


@pytest.fixture()
def store() -> StudioStore:
    return StudioStore.in_memory()


def _edhrec_file(folder: Path, urlhash: str, cards: list[tuple[str, int]]) -> None:
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
    (folder / f"{urlhash}.json").write_text(json.dumps(payload), encoding="utf-8")


def _archidekt_file(folder: Path, deck_id: int, cards: list[dict]) -> None:
    payload = {
        "id": deck_id,
        "bracket": 4,
        "updated_at": "2026-09-15",
        "cards": cards,
        "summe_hauptdeck": 100,
        "summe_gesamt": 100,
    }
    (folder / f"{deck_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _card(name: str, quantity: int = 1, categories: list[str] | None = None) -> dict:
    return {"name": name, "quantity": quantity, "categories": categories or []}


def _seed_catalog(store: StudioStore, cards: list[tuple[str, str, str]]) -> None:
    """Public catalog rows: (oracle id, full name, front-face name)."""
    source_id = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="catalog", sha256="c" * 64
    )
    with store.connection as db:
        db.executemany(
            "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
            "color_identity, commander_legality, keywords, produced_mana, source_id) "
            "VALUES (?, ?, ?, ?, 'normal', '', 'legal', '[]', '', ?)",
            [
                (oracle_id, f"printing-{oracle_id}", name, front, source_id)
                for oracle_id, name, front in cards
            ],
        )


def _fingerprints(store: StudioStore) -> dict[str, tuple[str, str | None]]:
    return {
        str(row[0]): (str(row[1]), row[2])
        for row in store.connection.execute(
            "SELECT deck_id, fingerprint, duplicate_of FROM corpus_deck"
        )
    }


_BEANSTALK = ("oracle-beanstalk", "Beanstalk Giant // Fertile Footsteps", "Beanstalk Giant")
_BASE_CATALOG = [
    ("oracle-chulane", CHULANE, CHULANE),
    ("oracle-sol-ring", "Sol Ring", "Sol Ring"),
    ("oracle-forest", "Forest", "Forest"),
    ("oracle-island", "Island", "Island"),
    _BEANSTALK,
]


def test_front_face_and_full_name_spellings_of_one_deck_collapse(
    store: StudioStore, tmp_path: Path
) -> None:
    # One physical deck, listed by EDHREC under the front-face spelling of a
    # two-part card and by Archidekt under its full name: after the names are
    # linked, both copies carry one fingerprint and count once.
    _seed_catalog(store, _BASE_CATALOG)
    edhrec = tmp_path / "edhrec"
    edhrec.mkdir()
    archidekt = tmp_path / "archidekt"
    archidekt.mkdir()
    _edhrec_file(
        edhrec, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Beanstalk Giant", 1), ("Forest", 10)]
    )
    _archidekt_file(
        archidekt,
        43,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Sol Ring"),
            _card("Beanstalk Giant // Fertile Footsteps"),
            _card("Forest", 10),
        ],
    )
    decklist_import.import_decklists(store, edhrec, format="edhrec")
    result = decklist_import.import_decklists(store, archidekt, format="archidekt")
    # At import time the spellings still differ, so the importer itself marks nothing;
    # the collapse comes from the link step the import runs at its end.
    assert result["corpus_fingerprint_groups_collapsed"] == 1
    fingerprints = _fingerprints(store)
    assert fingerprints["edhrec:aaa"][0] == fingerprints["archidekt:43"][0]
    canonical = [deck for deck, (_, mark) in fingerprints.items() if mark is None]
    assert len(canonical) == 1
    duplicate = next(deck for deck, (_, mark) in fingerprints.items() if mark is not None)
    assert fingerprints[duplicate][1] == canonical[0]
    assert universe.resolve_universe(store, {}) == canonical


def test_decks_differing_in_a_real_card_do_not_collapse(store: StudioStore, tmp_path: Path) -> None:
    _seed_catalog(store, _BASE_CATALOG)
    edhrec = tmp_path / "edhrec"
    edhrec.mkdir()
    archidekt = tmp_path / "archidekt"
    archidekt.mkdir()
    _edhrec_file(
        edhrec, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Beanstalk Giant", 1), ("Forest", 10)]
    )
    _archidekt_file(
        archidekt,
        43,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Sol Ring"),
            _card("Beanstalk Giant // Fertile Footsteps"),
            _card("Island", 10),
        ],
    )
    decklist_import.import_decklists(store, edhrec, format="edhrec")
    decklist_import.import_decklists(store, archidekt, format="archidekt")
    fingerprints = _fingerprints(store)
    assert fingerprints["edhrec:aaa"][0] != fingerprints["archidekt:43"][0]
    assert all(mark is None for _, mark in fingerprints.values())
    assert universe.resolve_universe(store, {}) == ["archidekt:43", "edhrec:aaa"]


def test_an_ambiguous_front_face_name_never_merges_decks(
    store: StudioStore, tmp_path: Path
) -> None:
    # Two catalog cards share one front-face name; the resolver leaves that name
    # undecided, so a deck spelling it by its front face must not merge with a deck
    # spelling one of the two cards by its full name.
    _seed_catalog(
        store,
        [
            *_BASE_CATALOG,
            ("oracle-twin-a", "Twin Card // Alpha", "Twin Card"),
            ("oracle-twin-b", "Twin Card // Beta", "Twin Card"),
        ],
    )
    edhrec = tmp_path / "edhrec"
    edhrec.mkdir()
    archidekt = tmp_path / "archidekt"
    archidekt.mkdir()
    _edhrec_file(edhrec, "aaa", [(CHULANE, 1), ("Twin Card", 1), ("Forest", 10)])
    _edhrec_file(edhrec, "bbb", [(CHULANE, 1), ("Twin Card", 1), ("Forest", 10)])
    _archidekt_file(
        archidekt,
        43,
        [_card(CHULANE, 1, ["Commander"]), _card("Twin Card // Alpha"), _card("Forest", 10)],
    )
    decklist_import.import_decklists(store, edhrec, format="edhrec")
    decklist_import.import_decklists(store, archidekt, format="archidekt")
    fingerprints = _fingerprints(store)
    # The two front-face copies are one deck (identical source rows) ...
    assert fingerprints["edhrec:aaa"][0] == fingerprints["edhrec:bbb"][0]
    # ... but the full-name deck stays its own deck: the ambiguous name decided nothing.
    assert fingerprints["archidekt:43"][0] != fingerprints["edhrec:aaa"][0]
    assert fingerprints["archidekt:43"][1] is None
    assert len(universe.resolve_universe(store, {})) == 2


def test_a_later_catalog_link_collapses_the_spellings_then(
    store: StudioStore, tmp_path: Path
) -> None:
    # Deck lists first, catalog later (the import order the link step exists for):
    # the fingerprints start apart and converge when the link runs.
    edhrec = tmp_path / "edhrec"
    edhrec.mkdir()
    archidekt = tmp_path / "archidekt"
    archidekt.mkdir()
    _edhrec_file(
        edhrec, "aaa", [(CHULANE, 1), ("Sol Ring", 1), ("Beanstalk Giant", 1), ("Forest", 10)]
    )
    _archidekt_file(
        archidekt,
        43,
        [
            _card(CHULANE, 1, ["Commander"]),
            _card("Sol Ring"),
            _card("Beanstalk Giant // Fertile Footsteps"),
            _card("Forest", 10),
        ],
    )
    decklist_import.import_decklists(store, edhrec, format="edhrec")
    decklist_import.import_decklists(store, archidekt, format="archidekt")
    before = _fingerprints(store)
    assert before["edhrec:aaa"][0] != before["archidekt:43"][0]
    _seed_catalog(store, _BASE_CATALOG)
    result = catalog.relink_corpus(store)
    assert result["corpus_fingerprint_groups_collapsed"] == 1
    after = _fingerprints(store)
    assert after["edhrec:aaa"][0] == after["archidekt:43"][0]
    assert universe.resolve_universe(store, {}) == [
        deck for deck, (_, mark) in after.items() if mark is None
    ]
