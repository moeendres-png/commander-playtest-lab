"""The collection's own printings (issue #1342): lot-sheet references, their aggregation
to one primary printing per card, and the Scryfall resolution of their images.

All data here is synthetic; the Scryfall lookup is always a fake.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from commander_lab.studio import importers, printings
from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.store import SCHEMA_VERSION, DataClass, StudioStore
from tests.unit.test_studio_store import IDENTITY_COLUMNS, INVENTORY_COLUMNS, _card, _workbook

LOTS_COLUMNS = [
    "physical_lot_id", "card_id", "oracle_name", "quantity_observed", "quantity_lower_bound",
    "quantity_exact", "printing_ref", "condition", "location_id", "pool_status",
    "reserved_quantity", "reservation_target_id", "source_id", "verified_at", "note",
]  # fmt: skip
DETAILS_COLUMNS = [
    "Karte (EN)", "card_id", "printing_ref", "Set-Code", "Sammlernr.", "Setname (EN)",
    "Seltenheit", "Künstler", "Release", "Sprache", "Zustand", "Finish", "Standort",
    "Verfügbarkeit", "Quelle Druckversion", "Quelle NM/Nonfoil",
]  # fmt: skip


def _lot(card_id: str, ref: object, quantity: int = 1) -> dict[str, object]:
    return {
        "physical_lot_id": f"lot:{card_id}:{ref}:{quantity}",
        "card_id": card_id,
        "oracle_name": "Synthetic",
        "quantity_observed": quantity,
        "quantity_lower_bound": quantity,
        "quantity_exact": True,
        "printing_ref": ref,
        "condition": None,
        "location_id": "location:test",
        "pool_status": "own_available",
        "reserved_quantity": 0,
        "reservation_target_id": None,
        "source_id": "source:test",
        "verified_at": "2026-11-07",
        "note": None,
    }


def _detail(card_id: str, ref: str, lang: str, finish: str) -> dict[str, object]:
    set_code, number = ref.split("#", 1)
    row: dict[str, object] = dict.fromkeys(DETAILS_COLUMNS)
    row.update(
        {
            "Karte (EN)": "Synthetic",
            "card_id": card_id,
            "printing_ref": ref,
            "Set-Code": set_code,
            "Sammlernr.": number,
            "Sprache": lang,
            "Finish": finish,
        }
    )
    return row


def _workbook_with_printings(
    path: Path,
    cards: list[dict[str, object]],
    lots: list[dict[str, object]],
    details: list[dict[str, object]] | None = None,
) -> Path:
    workbook = Workbook()
    identity = workbook.active
    assert identity is not None
    identity.title = importers.IDENTITY_SHEET
    identity.append(IDENTITY_COLUMNS)
    for card in cards:
        identity.append([card[column] for column in IDENTITY_COLUMNS])
    inventory = workbook.create_sheet(importers.INVENTORY_SHEET)
    inventory.append(INVENTORY_COLUMNS)
    for card in cards:
        inventory.append([card["card_id"], card["oracle_name"], 1, 1, 0, 1, True, 1, "2026-11-07"])
    lot_sheet = workbook.create_sheet(importers.LOTS_SHEET)
    lot_sheet.append(LOTS_COLUMNS)
    for lot in lots:
        lot_sheet.append([lot[column] for column in LOTS_COLUMNS])
    if details is not None:
        detail_sheet = workbook.create_sheet(importers.DETAILS_SHEET)
        detail_sheet.append(DETAILS_COLUMNS)
        for detail in details:
            detail_sheet.append([detail[column] for column in DETAILS_COLUMNS])
    workbook.save(path)
    return path


def _printing_row(store: StudioStore, card_id: str) -> sqlite3.Row | None:
    return store.connection.execute(
        "SELECT * FROM card_printing WHERE card_id = ?", (card_id,)
    ).fetchone()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ISD#1", ("isd", "1", None, None)),
        ("ALL#36b", ("all", "36b", None, None)),
        ("ECL#67|en", ("ecl", "67", "en", None)),
        ("MKM#279|de", ("mkm", "279", "de", None)),
        ("CMM#410|nonfoil", ("cmm", "410", None, "nonfoil")),
        ("FDC#1|foil", ("fdc", "1", None, "foil")),
        ("ECL#67|en|nonfoil", ("ecl", "67", "en", "nonfoil")),
        ("ECL#67|de|finish_unknown", ("ecl", "67", "de", None)),
        ("CMR#194/361|en|nonfoil", ("cmr", "194", "en", "nonfoil")),
        (" isd#12 ", ("isd", "12", None, None)),
        (None, None),
        ("", None),
        ("unknown", None),
        ("unknown|foil", None),
        ("unmapped[MOC#391, EOC#149]", None),
        ("collector#23|de|nonfoil", None),
        ("no-separator", None),
        ("SET#", None),
        ("AAA#1|xx", None),
        ("AAA#1|en|de", None),
        ("AAA#1|en|nonfoil|extra", None),
    ],
)
def test_parse_printing_ref_reads_every_workbook_form(
    raw: object, expected: tuple[str, str, str | None, str | None] | None
) -> None:
    assert printings.parse_printing_ref(raw) == expected


def _five_cards() -> list[dict[str, object]]:
    return [
        _card(1, "Alpha Card", "G", "Creature"),
        _card(2, "Beta Card", "G", "Creature"),
        _card(3, "Gamma Card", "G", "Creature"),
        _card(4, "Delta Card", "G", "Creature"),
        _card(5, "Echo Card", "G", "Creature"),
    ]


def test_inventory_import_aggregates_the_primary_printing(tmp_path: Path) -> None:
    cards = _five_cards()
    lots = [
        _lot("card:project:0001", "AAA#10", 1),
        _lot("card:project:0001", "BBB#5|en", 3),
        _lot("card:project:0001", "BBB#5|de", 1),
        _lot("card:project:0002", "CCC#7", 2),
        _lot("card:project:0002", "DDD#9", 2),
        _lot("card:project:0003", "EEE#3", 1),
        _lot("card:project:0003", "FFF#2", 1),
        _lot("card:project:0004", "unmapped[AAA#1, BBB#2]", 1),
        _lot("card:project:0004", None, 1),
    ]
    details = [_detail("card:project:0003", "FFF#2", "de", "foil")]
    path = _workbook_with_printings(tmp_path / "cards.xlsx", cards, lots, details)
    store = StudioStore.in_memory()
    report = importers.import_inventory_workbook(store, path)
    assert report == {
        "cards": 5,
        "inventory": 5,
        "printings_exact_candidate": 3,
        "printings_unresolved": 1,
        "printings_multi": 3,
    }
    alpha = _printing_row(store, "card:project:0001")
    assert alpha is not None
    # most copies win (BBB#5: 4 over AAA#10: 1); the language of its largest variant wins
    assert (
        alpha["set_code"],
        alpha["collector_number"],
        alpha["lang"],
        alpha["finish"],
        alpha["copies"],
        alpha["distinct_printings"],
        alpha["ref_status"],
    ) == ("bbb", "5", "en", None, 4, 2, "EXACT_CANDIDATE")
    beta = _printing_row(store, "card:project:0002")
    assert beta is not None
    # equal copies and no detail: the lowest (set, number) wins, deterministically
    assert (beta["set_code"], beta["collector_number"], beta["copies"]) == ("ccc", "7", 2)
    gamma = _printing_row(store, "card:project:0003")
    assert gamma is not None
    # equal copies: the printing the details sheet describes wins, and it enriches
    # language and finish the lot references do not carry
    assert (
        gamma["set_code"],
        gamma["collector_number"],
        gamma["lang"],
        gamma["finish"],
    ) == ("fff", "2", "de", "foil")
    delta = _printing_row(store, "card:project:0004")
    assert delta is not None
    assert (
        delta["set_code"],
        delta["collector_number"],
        delta["copies"],
        delta["distinct_printings"],
        delta["ref_status"],
        delta["basis"],
    ) == (None, None, 2, 0, "UNRESOLVED", None)
    # a card without lots has no printing row at all
    assert _printing_row(store, "card:project:0005") is None


def test_inventory_import_without_lot_sheet_stores_no_printings(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    report = importers.import_inventory_workbook(
        store, _workbook(tmp_path / "cards.xlsx", [_card(1, "Solo", "G", "Creature")])
    )
    assert report["printings_exact_candidate"] == 0
    assert report["printings_unresolved"] == 0
    assert report["printings_multi"] == 0
    assert store.count("card_printing") == 0
    assert store.count("card") == 1


def _seed_card(store: StudioStore, card_id: str) -> None:
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE, title="seed", sha256="seed"
    )
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_name, color_identity, source_id) "
        "VALUES (?, 'Seeded', '', ?)",
        (card_id, source_id),
    )


def _seed_printing(
    store: StudioStore,
    card_id: str,
    set_code: str,
    number: str,
    lang: str | None = None,
    *,
    image_front: str | None = None,
) -> None:
    _seed_card(store, card_id)
    store.connection.execute(
        "INSERT INTO card_printing(card_id, set_code, collector_number, lang, ref_status, "
        "image_front) VALUES (?, ?, ?, ?, 'EXACT_CANDIDATE', ?)",
        (card_id, set_code, number, lang, image_front),
    )
    store.connection.commit()


def _scryfall_card(
    set_code: str, number: str, lang: str = "en", *, front: str | None = None
) -> dict[str, object]:
    card: dict[str, object] = {
        "id": f"sf-{set_code}-{number}-{lang}",
        "set": set_code,
        "collector_number": number,
        "lang": lang,
    }
    if front is not None:
        card["image_uris"] = {"normal": front}
    return card


class _FakeLookup:
    """Answers from a table keyed by (set, number); records every batch it was given."""

    def __init__(
        self, answers: dict[tuple[str, str], tuple[list[dict[str, object]], list[dict[str, str]]]]
    ) -> None:
        self.answers = answers
        self.batches: list[list[tuple[str, str]]] = []

    def __call__(
        self, identifiers: Sequence[Mapping[str, str]]
    ) -> tuple[list[Mapping[str, object]], list[Mapping[str, str]]]:
        keys = [(item["set"], item["collector_number"]) for item in identifiers]
        assert len(keys) <= 75
        self.batches.append(keys)
        found: list[Mapping[str, object]] = []
        missed: list[Mapping[str, str]] = []
        for key in keys:
            cards, not_found = self.answers.get(
                key, ([], [{"set": key[0], "collector_number": key[1]}])
            )
            found.extend(cards)
            missed.extend(not_found)
        return found, missed


def test_resolver_batches_seventy_five_identifiers_per_lookup(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    answers: dict[tuple[str, str], tuple[list[dict[str, object]], list[dict[str, str]]]] = {}
    for index in range(80):
        number = str(index + 1)
        card_id = f"card:project:{index:04d}"
        _seed_printing(store, card_id, "syn", number)
        answers[("syn", number)] = (
            [_scryfall_card("syn", number, front=f"https://img.test/{number}.jpg")],
            [],
        )
    lookup = _FakeLookup(answers)
    report = printings.resolve_printing_images(store, lookup=lookup)
    assert report == {
        "candidates": 80,
        "identifiers": 80,
        "batches": 2,
        "resolved": 80,
        "not_found": 0,
        "ambiguous": 0,
    }
    assert [len(batch) for batch in lookup.batches] == [75, 5]
    row = _printing_row(store, "card:project:0000")
    assert row is not None
    assert (row["scryfall_id"], row["image_front"], row["basis"]) == (
        "sf-syn-1-en",
        "https://img.test/1.jpg",
        "EXACT_COLLECTION",
    )
    # a second run has nothing left to do and never calls the lookup again
    assert printings.resolve_printing_images(store, lookup=lookup)["candidates"] == 0
    assert len(lookup.batches) == 2


def test_resolver_picks_the_references_language_and_counts_the_rest() -> None:
    store = StudioStore.in_memory()
    _seed_printing(store, "card:project:0001", "syn", "1", "de")
    _seed_printing(store, "card:project:0002", "syn", "2")
    _seed_printing(store, "card:project:0003", "syn", "3")
    _seed_printing(store, "card:project:0004", "syn", "4")
    _seed_printing(store, "card:project:0005", "syn", "5", image_front="https://img.test/x.jpg")
    answers = {
        ("syn", "1"): (
            [
                _scryfall_card("syn", "1", "en", front="https://img.test/1-en.jpg"),
                _scryfall_card("syn", "1", "de", front="https://img.test/1-de.jpg"),
            ],
            [],
        ),
        # no language in the reference: English wins over the other language
        ("syn", "2"): (
            [
                _scryfall_card("syn", "2", "fr", front="https://img.test/2-fr.jpg"),
                _scryfall_card("syn", "2", "en", front="https://img.test/2-en.jpg"),
            ],
            [],
        ),
        # neither the reference's language context nor English: ambiguous, not guessed
        ("syn", "3"): (
            [
                _scryfall_card("syn", "3", "fr", front="https://img.test/3-fr.jpg"),
                _scryfall_card("syn", "3", "ja", front="https://img.test/3-ja.jpg"),
            ],
            [],
        ),
        ("syn", "4"): ([], [{"set": "syn", "collector_number": "4"}]),
    }
    lookup = _FakeLookup(answers)
    report = printings.resolve_printing_images(store, lookup=lookup)
    assert report == {
        "candidates": 4,
        "identifiers": 4,
        "batches": 1,
        "resolved": 2,
        "not_found": 1,
        "ambiguous": 1,
    }
    first = _printing_row(store, "card:project:0001")
    assert first is not None and first["image_front"] == "https://img.test/1-de.jpg"
    second = _printing_row(store, "card:project:0002")
    assert second is not None and second["image_front"] == "https://img.test/2-en.jpg"
    for card_id in ("card:project:0003", "card:project:0004"):
        row = _printing_row(store, card_id)
        assert row is not None
        assert (row["image_front"], row["basis"]) == (None, None)
    # the row that already had an image was never part of the lookup
    assert all(key != ("syn", "5") for batch in lookup.batches for key in batch)


def test_resolver_reads_multiface_images_like_the_catalog() -> None:
    store = StudioStore.in_memory()
    _seed_printing(store, "card:project:0001", "syn", "1")
    _seed_printing(store, "card:project:0002", "syn", "2")
    two_faces = {
        "id": "sf-syn-1-en",
        "set": "syn",
        "collector_number": "1",
        "lang": "en",
        "card_faces": [
            {"name": "Front", "image_uris": {"normal": "https://img.test/front.jpg"}},
            {"name": "Back", "image_uris": {"normal": "https://img.test/back.jpg"}},
        ],
    }
    own_image = _scryfall_card("syn", "2", front="https://img.test/own.jpg")
    own_image["card_faces"] = [
        {"name": "Front", "image_uris": {"normal": "https://img.test/face0.jpg"}},
        {"name": "Back", "image_uris": {"normal": "https://img.test/face1.jpg"}},
    ]
    answers = {
        ("syn", "1"): ([two_faces], []),
        ("syn", "2"): ([own_image], []),
    }
    report = printings.resolve_printing_images(store, lookup=_FakeLookup(answers))
    assert report["resolved"] == 2
    first = _printing_row(store, "card:project:0001")
    assert first is not None
    assert (first["image_front"], first["image_back"]) == (
        "https://img.test/front.jpg",
        "https://img.test/back.jpg",
    )
    second = _printing_row(store, "card:project:0002")
    assert second is not None
    # a printing with its own image has no separate back image (catalog rule)
    assert (second["image_front"], second["image_back"]) == ("https://img.test/own.jpg", None)


def test_reimport_keeps_resolution_only_for_an_unchanged_printing(tmp_path: Path) -> None:
    cards = [_card(1, "Alpha Card", "G", "Creature")]
    path = _workbook_with_printings(
        tmp_path / "cards.xlsx", cards, [_lot("card:project:0001", "BBB#5|en", 2)]
    )
    store = StudioStore.in_memory()
    importers.import_inventory_workbook(store, path)
    answers = {("bbb", "5"): ([_scryfall_card("bbb", "5", front="https://img.test/5.jpg")], [])}
    printings.resolve_printing_images(store, lookup=_FakeLookup(answers))
    importers.import_inventory_workbook(store, path)
    row = _printing_row(store, "card:project:0001")
    assert row is not None
    assert (row["image_front"], row["basis"]) == (
        "https://img.test/5.jpg",
        "EXACT_COLLECTION",
    )
    changed = _workbook_with_printings(
        tmp_path / "changed.xlsx", cards, [_lot("card:project:0001", "AAA#10", 2)]
    )
    importers.import_inventory_workbook(store, changed)
    row = _printing_row(store, "card:project:0001")
    assert row is not None
    assert (row["set_code"], row["image_front"], row["basis"]) == ("aaa", None, None)


_OLD_SCRYFALL_COLUMNS = """
CREATE TABLE scryfall_card (
    oracle_id TEXT PRIMARY KEY, scryfall_id TEXT NOT NULL, name TEXT NOT NULL,
    front_name TEXT NOT NULL, layout TEXT NOT NULL, mana_cost TEXT, mana_value REAL,
    type_line TEXT, oracle_text TEXT, color_identity TEXT NOT NULL,
    commander_legality TEXT NOT NULL, edhrec_rank INTEGER, keywords TEXT NOT NULL,
    produced_mana TEXT NOT NULL, power TEXT, toughness TEXT, game_changer INTEGER,
    released_at TEXT, image_front TEXT, image_back TEXT,
    source_id TEXT NOT NULL REFERENCES source(source_id)
);
"""  # fmt: skip


def test_schema_15_upgrades_an_existing_store_idempotently(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    folder.mkdir()
    connection = sqlite3.connect(folder / "studio.sqlite3")
    connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO meta VALUES ('schema_version', '14')")
    connection.execute(
        "CREATE TABLE source (source_id TEXT PRIMARY KEY, data_class TEXT NOT NULL, "
        "title TEXT NOT NULL, sha256 TEXT NOT NULL, snapshot_date TEXT, url TEXT, "
        "imported_at TEXT NOT NULL)"
    )
    connection.executescript(_OLD_SCRYFALL_COLUMNS)
    connection.execute(
        "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('src:test', 'ORIGINAL_SOURCE', 'test', 'x', '2026-11-07')"
    )
    connection.execute(
        "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
        "color_identity, commander_legality, keywords, produced_mana, source_id) "
        "VALUES ('oracle-1', 'sf-1', 'Old Card', 'Old Card', 'normal', '', 'legal', "
        "'[]', '', 'src:test')"
    )
    connection.commit()
    connection.close()
    for _ in range(2):  # opening twice: the ALTER guard must be idempotent
        store = StudioStore.open(folder)
        columns = [
            row["name"] for row in store.connection.execute("PRAGMA table_info(scryfall_card)")
        ]
        assert columns[-3:] == ["printing_set", "printing_number", "printing_basis"]
        row = store.connection.execute(
            "SELECT printing_set, printing_number, printing_basis FROM scryfall_card"
        ).fetchone()
        assert tuple(row) == (None, None, None)
        version = store.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert version["value"] == str(SCHEMA_VERSION) == "15"
        store.close()


def test_fresh_store_has_the_printing_schema() -> None:
    store = StudioStore.in_memory()
    columns = [row["name"] for row in store.connection.execute("PRAGMA table_info(card_printing)")]
    assert columns == [
        "card_id", "set_code", "collector_number", "lang", "finish", "copies",
        "distinct_printings", "ref_status", "scryfall_id", "image_front", "image_back",
        "basis",
    ]  # fmt: skip
    version = store.connection.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    assert version["value"] == "15"


def test_import_printings_command_runs_without_candidates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workbook = _workbook(tmp_path / "cards.xlsx", [_card(1, "Solo", "G", "Creature")])
    bulk = tmp_path / "default-cards.jsonl"
    bulk.write_text("", encoding="utf-8")
    data = str(tmp_path / "studio")
    assert (
        studio_main(["--data", data, "import-printings", str(workbook), "--bulk", str(bulk)]) == 0
    )
    output = capsys.readouterr().out
    assert '"printings_exact_candidate": 0' in output
    assert '"resolved": 0' in output
    assert '"batches": 0' in output


def test_resolver_matches_locally_against_a_bulk_file(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    _seed_printing(store, "card:project:0001", "ecl", "0316")
    _seed_printing(store, "card:project:0002", "zzz", "9")
    bulk = tmp_path / "default-cards.jsonl"
    bulk.write_text(
        json.dumps(_scryfall_card("ecl", "316", front="https://img.test/goliath.jpg")) + "\n",
        encoding="utf-8",
    )
    report = printings.resolve_printing_images(store, bulk_path=bulk)
    assert report["resolved"] == 1 and report["not_found"] == 1 and report["batches"] == 1
    row = _printing_row(store, "card:project:0001")
    assert row is not None
    assert (row["image_front"], row["basis"]) == (
        "https://img.test/goliath.jpg",
        "EXACT_COLLECTION",
    )
    missing = _printing_row(store, "card:project:0002")
    assert missing is not None and missing["basis"] is None


def test_resolver_without_a_source_fails_closed() -> None:
    store = StudioStore.in_memory()
    _seed_printing(store, "card:project:0001", "ecl", "316")
    with pytest.raises(ValueError, match="default-cards bulk"):
        printings.resolve_printing_images(store)


def test_inventory_import_tolerates_existing_but_empty_optional_sheets(
    tmp_path: Path,
) -> None:
    workbook_path = _workbook_with_printings(
        tmp_path / "cards.xlsx", [_card(1, "Solo", "G", "Creature")], []
    )
    workbook = load_workbook(filename=workbook_path)
    del workbook[importers.LOTS_SHEET]
    workbook.create_sheet(importers.LOTS_SHEET)
    workbook.create_sheet(importers.DETAILS_SHEET)
    workbook.save(workbook_path)
    workbook.close()
    store = StudioStore.in_memory()
    report = importers.import_inventory_workbook(store, workbook_path)
    assert report["printings_exact_candidate"] == 0
    assert report["printings_unresolved"] == 0
