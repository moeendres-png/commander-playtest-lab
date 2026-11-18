"""Printing choice of the Scryfall import and the image cache (issue #1342).

The fold prefers the printing the collection itself holds (``card_printing``), then
a plain standard printing, and records which rule produced the picture. The image
cache is bound to the chosen printing by an address stamp next to each file.
All data here is synthetic; downloads are monkeypatched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import catalog
from commander_lab.studio.images import (
    cached_image,
    cached_image_by_name,
    fetch_images,
    image_address,
    image_cache_status,
    image_folder,
    valid_image_url,
    web_image_url,
    web_image_url_by_name,
)
from commander_lab.studio.store import DataClass, StudioStore

IMAGE = "https://cards.scryfall.io/normal/front/a/b/{}.jpg"
FRONT = IMAGE.format("forest")
BACK = IMAGE.format("forest-back")
PRINT_FRONT = IMAGE.format("owned-print")


def _printing(oracle_id: str, name: str, number: str, slug: str, **extra: object) -> dict:
    card: dict[str, object] = {
        "id": f"print-{slug}",
        "oracle_id": oracle_id,
        "name": name,
        "layout": "normal",
        "set": "tst",
        "collector_number": number,
        "lang": "en",
        "games": ["paper"],
        "digital": False,
        "full_art": False,
        "border_color": "black",
        "frame_effects": [],
        "promo": False,
        "promo_types": [],
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Artifact",
        "oracle_text": "",
        "color_identity": [],
        "legalities": {"commander": "legal"},
        "keywords": [],
        "image_uris": {"normal": IMAGE.format(slug)},
    }
    card.update(extra)
    return card


def _bulk(path: Path, cards: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(card) + "\n" for card in cards),
        encoding="utf-8",
    )
    return path


def _source(store: StudioStore) -> str:
    return store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title="test.xlsx", sha256="0" * 64
    )


def _card(store: StudioStore, source_id: str, card_id: str, name: str) -> None:
    with store.connection as db:
        db.execute(
            "INSERT INTO card(card_id, oracle_name, color_identity, mana_cost, mana_value, "
            "type_line, oracle_text, is_basic_land, source_id) "
            "VALUES (?, ?, '', '{1}', 1.0, 'Artifact', '', 0, ?)",
            (card_id, name, source_id),
        )


def _owned(
    store: StudioStore,
    card_id: str,
    number: str,
    *,
    lang: str | None = None,
    set_code: str = "tst",
    scryfall_id: str | None = None,
    image_front: str | None = None,
    image_back: str | None = None,
) -> None:
    with store.connection as db:
        db.execute(
            "INSERT INTO card_printing(card_id, set_code, collector_number, lang, "
            "ref_status, scryfall_id, image_front, image_back) "
            "VALUES (?, ?, ?, ?, 'EXACT_CANDIDATE', ?, ?, ?)",
            (card_id, set_code, number, lang, scryfall_id, image_front, image_back),
        )


def _winner(store: StudioStore, oracle_id: str) -> dict:
    row = store.connection.execute(
        "SELECT printing_set, printing_number, printing_basis, image_front "
        "FROM scryfall_card WHERE oracle_id = ?",
        (oracle_id,),
    ).fetchone()
    assert row is not None
    return dict(row)


def test_special_variants_lose_to_the_standard_printing(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        cards = [
            _printing("oracle-rule", "Rule Card", "2", "fullart",
                      full_art=True, border_color="borderless", frame_effects=["extendedart"]),
            _printing("oracle-rule", "Rule Card", "3", "showcase", frame_effects=["showcase"]),
            _printing("oracle-rule", "Rule Card", "4", "promo",
                      promo=True, promo_types=["promopack"]),
            _printing("oracle-rule", "Rule Card", "1", "standard"),
        ]  # fmt: skip
        report = catalog.import_scryfall_oracle(store, _bulk(tmp_path / "bulk.jsonl", cards))
        winner = _winner(store, "oracle-rule")
        assert winner["printing_set"] == "tst"
        assert winner["printing_number"] == "1"
        assert winner["printing_basis"] == "STANDARD_RULE"
        assert winner["image_front"] == IMAGE.format("standard")
        assert report["printings_exact"] == 0
        assert report["printings_standard"] == 1
        assert report["printings_default"] == 0
    finally:
        store.close()


def test_exact_owned_printing_beats_the_standard_rule(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        source_id = _source(store)
        _card(store, source_id, "card:project:1001", "Exact Card")
        _owned(store, "card:project:1001", "09")  # the sheet pads the number, Scryfall does not
        cards = [
            _printing("oracle-exact", "Exact Card", "1", "standard"),
            _printing("oracle-exact", "Exact Card", "9", "ownedpromo",
                      promo=True, promo_types=["prerelease"]),
        ]  # fmt: skip
        report = catalog.import_scryfall_oracle(store, _bulk(tmp_path / "bulk.jsonl", cards))
        winner = _winner(store, "oracle-exact")
        assert winner["printing_number"] == "9"
        assert winner["printing_basis"] == "EXACT_COLLECTION"
        assert winner["image_front"] == IMAGE.format("ownedpromo")
        assert report["printings_exact"] == 1
        assert report["printings_standard"] == 0
    finally:
        store.close()


def test_exact_match_needs_the_reference_language(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        source_id = _source(store)
        _card(store, source_id, "card:project:1002", "Lang Card")
        _owned(store, "card:project:1002", "9", lang="de")
        _card(store, source_id, "card:project:1003", "German Card")
        _owned(store, "card:project:1003", "7", lang="de")
        cards = [
            _printing("oracle-lang", "Lang Card", "9", "englishpromo",
                      promo=True, promo_types=["prerelease"]),
            _printing("oracle-lang", "Lang Card", "1", "langstandard"),
            _printing("oracle-german", "German Card", "7", "germanpromo",
                      lang="de", promo=True, promo_types=["prerelease"]),
            _printing("oracle-german", "German Card", "1", "germanstandard"),
        ]  # fmt: skip
        report = catalog.import_scryfall_oracle(store, _bulk(tmp_path / "bulk.jsonl", cards))
        english = _winner(store, "oracle-lang")
        assert english["printing_number"] == "1"  # the English #9 is not the owned German one
        assert english["printing_basis"] == "STANDARD_RULE"
        german = _winner(store, "oracle-german")
        assert german["printing_number"] == "7"
        assert german["printing_basis"] == "EXACT_COLLECTION"
        assert report["printings_exact"] == 1
        assert report["printings_standard"] == 1
    finally:
        store.close()


def test_a_single_candidate_is_the_scryfall_default(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        cards = [
            _printing("oracle-lonely", "Lonely Card", "5", "onlyfullart",
                      full_art=True, border_color="borderless"),
            _printing("oracle-single", "Single Card", "6", "onlystandard"),
        ]  # fmt: skip
        report = catalog.import_scryfall_oracle(store, _bulk(tmp_path / "bulk.jsonl", cards))
        for oracle_id, number in (("oracle-lonely", "5"), ("oracle-single", "6")):
            winner = _winner(store, oracle_id)
            assert winner["printing_number"] == number
            assert winner["printing_basis"] == "SCRYFALL_DEFAULT"
        assert report["printings_default"] == 2
        assert report["printings_standard"] == 0
    finally:
        store.close()


def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("no network in tests")

    monkeypatch.setattr("urllib.request.urlopen", blocked)


def _face_store(tmp_path: Path) -> StudioStore:
    """One collection card whose public data carries a front and a back image."""
    store = StudioStore.open(tmp_path / "studio")
    source_id = _source(store)
    with store.connection as db:
        db.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, is_basic_land, source_id) "
            "VALUES ('card:project:0002', 'oracle-forest', 'Forest', 'G', '', 0.0, "
            "'Basic Land — Forest', '', 1, ?)",
            (source_id,),
        )
        db.execute(
            "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
            "color_identity, commander_legality, keywords, produced_mana, image_front, "
            "image_back, source_id) VALUES ('oracle-forest', 'print-forest', 'Forest', "
            "'Forest', 'normal', 'G', 'legal', '[]', '[]', ?, ?, ?)",
            (FRONT, BACK, source_id),
        )
    return store


def test_local_image_cache_is_disabled_and_never_writes_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_network(monkeypatch)
    store = _face_store(tmp_path)
    try:
        folder = image_folder(store)
        assert not folder.exists()
        assert cached_image(store, "card:project:0002") is None
        assert cached_image_by_name(store, "Forest") is None
        assert not folder.exists()

        status_empty = image_cache_status(store)
        assert status_empty["cache_enabled"] is False
        assert status_empty["exists"] is False
        assert status_empty["files"] == 0

        # Pre-existing legacy images/ folder is reported with size, never deleted automatically
        folder.mkdir(parents=True)
        (folder / "oracle-forest-front.jpg").write_bytes(b"x" * 2048)
        report = fetch_images(store, ["card:project:0002"])
        assert report["deprecated"] is True
        assert report["cache_enabled"] is False
        assert report["exists"] is True
        assert report["files"] == 1
        assert report["bytes"] == 2048
        assert "gelöscht werden" in str(report["hint"])
        assert (folder / "oracle-forest-front.jpg").exists()
    finally:
        store.close()


def test_valid_image_url_accepts_only_https_scryfall_host() -> None:
    assert valid_image_url(FRONT) == FRONT
    assert valid_image_url("http://cards.scryfall.io/normal/front/a/b/forest.jpg") is None
    assert valid_image_url("https://example.invalid/forest.jpg") is None
    assert valid_image_url("") is None
    assert valid_image_url(None) is None


def test_image_address_prefers_the_collection_printing(tmp_path: Path) -> None:
    store = _face_store(tmp_path)
    try:
        _owned(
            store,
            "card:project:0002",
            "1",
            scryfall_id="print-owned",
            image_front=PRINT_FRONT,
            image_back=None,
        )
        assert image_address(store, "card:project:0002") == ("oracle-forest", PRINT_FRONT)
        assert web_image_url(store, "card:project:0002") == PRINT_FRONT
        # the printing has no back image: the public card data answers for that face
        assert image_address(store, "card:project:0002", "back") == ("oracle-forest", BACK)
        assert web_image_url(store, "card:project:0002", "back") == BACK
    finally:
        store.close()


def test_image_address_ignores_an_unresolved_printing(tmp_path: Path) -> None:
    store = _face_store(tmp_path)
    try:
        _owned(store, "card:project:0002", "1", scryfall_id="print-owned")  # no image resolved
        assert image_address(store, "card:project:0002") == ("oracle-forest", FRONT)
    finally:
        store.close()


def test_by_name_serves_the_collection_printing_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_network(monkeypatch)
    store = _face_store(tmp_path)
    try:
        assert web_image_url_by_name(store, "Forest") == FRONT
        _owned(store, "card:project:0002", "1", scryfall_id="print-owned", image_front=PRINT_FRONT)
        assert web_image_url_by_name(store, "Forest") == PRINT_FRONT
        assert not image_folder(store).exists()
    finally:
        store.close()


@pytest.mark.parametrize(
    "traits",
    [
        {"full_art": True},
        {"border_color": "borderless"},
        {"frame_effects": ["showcase"]},
        {"frame_effects": ["extendedart"]},
        {"promo": True},
        {"promo_types": ["promopack"]},
    ],
)
def test_each_standard_criterion_alone_decides(tmp_path: Path, traits: dict) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        cards = [
            _printing("oracle-rule", "Rule Card", "2", "variant", **traits),
            _printing("oracle-rule", "Rule Card", "1", "standard"),
        ]
        catalog.import_scryfall_oracle(store, _bulk(tmp_path / "bulk.jsonl", cards))
        winner = _winner(store, "oracle-rule")
        assert winner["printing_number"] == "1"
        assert winner["printing_basis"] == "STANDARD_RULE"
    finally:
        store.close()


def test_static_pages_set_no_referrer_on_images() -> None:
    static_dir = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
    for name in ("app.js", "tierliste.js", "partie.js", "index.html", "partie.html"):
        text = (static_dir / name).read_text(encoding="utf-8")
        assert "no-referrer" in text, f"{name} must set referrerpolicy=no-referrer"


def test_schema_16_to_17_migration_converts_tables_to_without_rowid(tmp_path: Path) -> None:
    import sqlite3

    db_dir = tmp_path / "legacy16"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "studio.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO meta(key, value) VALUES ('schema_version', '16');
        CREATE TABLE source (
            source_id TEXT PRIMARY KEY, data_class TEXT NOT NULL, title TEXT NOT NULL,
            sha256 TEXT NOT NULL, snapshot_date TEXT, url TEXT, imported_at TEXT NOT NULL
        );
        INSERT INTO source VALUES ('src:1', 'ORIGINAL_SOURCE', 't', '00', NULL, NULL, '2026-11-15T00:00:00Z');
        CREATE TABLE corpus_deck (
            deck_id TEXT PRIMARY KEY, cohort TEXT NOT NULL, url TEXT NOT NULL,
            platform TEXT NOT NULL, play_group TEXT NOT NULL, deck_date TEXT,
            tags TEXT NOT NULL, fingerprint TEXT NOT NULL, duplicate_of TEXT,
            legality_audit TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES source(source_id)
        );
        INSERT INTO corpus_deck VALUES ('d1', 'c1', 'u', 'p', 'tuned', NULL, '[]', 'fp1', NULL, 'ok', 'src:1');
        CREATE TABLE corpus_deck_card (
            deck_id TEXT NOT NULL REFERENCES corpus_deck(deck_id),
            card_name TEXT NOT NULL, oracle_id TEXT, quantity INTEGER NOT NULL,
            section TEXT NOT NULL, normalization_status TEXT NOT NULL,
            PRIMARY KEY (deck_id, card_name, section)
        );
        CREATE INDEX corpus_card_name ON corpus_deck_card(card_name);
        CREATE INDEX corpus_deck_cover ON corpus_deck_card(deck_id, section, quantity, card_name);
        INSERT INTO corpus_deck_card VALUES ('d1', 'Sol Ring', 'o-sol', 1, 'mainboard', 'EXACT');
        """
    )
    conn.close()

    store = StudioStore.open(db_dir)
    try:
        ver = store.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert ver == "21"
        ddl = store.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'corpus_deck_card'"
        ).fetchone()[0]
        assert "WITHOUT ROWID" in ddl.upper()
        indexes = {
            r[0]
            for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert "corpus_card_name" not in indexes
        assert "corpus_deck_cover" not in indexes
        assert "corpus_card_cover" in indexes
        assert store.count("corpus_deck_card") == 1
        assert store.data_epoch() is not None
        store.compact()
    finally:
        store.close()
