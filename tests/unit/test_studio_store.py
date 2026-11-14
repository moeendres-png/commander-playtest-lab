"""Studio data contract: store location, importers, deck revisions, checks, read models.

All data here is synthetic. Real collection and deck data never enter the repository.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.studio import (
    DataClass,
    RevisionCard,
    StudioStore,
    create_revision,
    importers,
    lab_snapshot,
    studio_data_dir,
    validate_revision,
)
from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.decks import deck_hash
from commander_lab.studio.queries import corpus_inclusion, legal_pool
from commander_lab.studio.store import STUDIO_DATA_ENV

IDENTITY_COLUMNS = [
    "card_id", "oracle_id", "oracle_name", "color_identity", "mana_cost", "mana_value",
    "type_line", "oracle_text", "is_basic_land", "commander_legal", "legality_verified_at",
    "identity_evidence_type",
]  # fmt: skip
INVENTORY_COLUMNS = [
    "card_id", "oracle_name", "observed_quantity", "physical_owned_quantity_lower_bound",
    "reserved_for_opponents_quantity", "available_for_own_decks_quantity_lower_bound",
    "quantity_exact", "number_of_lots", "last_verified_at",
]  # fmt: skip


def _card(
    number: int, name: str, colors: str, type_line: str, **extra: object
) -> dict[str, object]:
    row: dict[str, object] = {
        "card_id": f"card:project:{number:04d}",
        "oracle_id": None,
        "oracle_name": name,
        "color_identity": colors,
        "mana_cost": "{1}",
        "mana_value": 1,
        "type_line": type_line,
        "oracle_text": "",
        "is_basic_land": False,
        "commander_legal": True,
        "legality_verified_at": "2026-11-07",
        "identity_evidence_type": "synthetic",
    }
    row.update(extra)
    return row


def _synthetic_cards() -> list[dict[str, object]]:
    cards = [
        _card(1, "Test Commander", "GWU", "Legendary Creature — Human Druid"),
        _card(2, "Forest", "G", "Basic Land — Forest", is_basic_land=True),
        _card(3, "Red Outsider", "R", "Creature — Goblin"),
        _card(4, "Banned Relic", "", "Artifact", commander_legal=False),
        _card(5, "Unverified Charm", "U", "Instant", commander_legal=None),
        _card(6, "Reserved Bear", "G", "Creature — Bear"),
        _card(7, "Swarm Rat", "W", "Creature — Rat",
              oracle_text="A deck can have any number of cards named Swarm Rat."),
    ]  # fmt: skip
    cards += [_card(100 + i, f"Filler {i:02d}", "GWU"[i % 3], "Creature") for i in range(70)]
    return cards


def _workbook(path: Path, cards: list[dict[str, object]]) -> Path:
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
        name = card["oracle_name"]
        owned = {"Forest": 40, "Swarm Rat": 30}.get(str(name), 1)
        reserved = 1 if name == "Reserved Bear" else 0
        inventory.append(
            [card["card_id"], name, owned, owned, reserved, owned - reserved, True, 1, "2026-11-07"]
        )
    workbook.save(path)
    return path


@pytest.fixture
def store(tmp_path: Path) -> StudioStore:
    opened = StudioStore.in_memory()
    importers.import_inventory_workbook(
        opened, _workbook(tmp_path / "cards.xlsx", _synthetic_cards())
    )
    return opened


def _legal_deck(store: StudioStore) -> list[RevisionCard]:
    cards = [RevisionCard("card:project:0001", 1, "commander")]
    cards += [RevisionCard(f"card:project:{100 + i:04d}") for i in range(70)]
    cards.append(RevisionCard("card:project:0002", 29))
    return cards


def _codes(store: StudioStore, revision_id: str, **options: bool) -> set[str]:
    return {issue.code for issue in validate_revision(store, revision_id, **options)}


def test_store_has_no_default_location_and_refuses_the_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(STUDIO_DATA_ENV, raising=False)
    monkeypatch.delenv("COMMANDER_LAB_OWNER_DATA", raising=False)
    with pytest.raises(RuntimeError, match="no default location"):
        studio_data_dir()
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.setenv(STUDIO_DATA_ENV, str(repository / "data" / "studio"))
    with pytest.raises(RuntimeError, match="outside the repository"):
        studio_data_dir()
    with pytest.raises(RuntimeError, match="outside the repository"):
        StudioStore.open(repository / "data" / "studio")
    monkeypatch.setenv(STUDIO_DATA_ENV, str(tmp_path / "studio"))
    assert studio_data_dir() == (tmp_path / "studio").resolve()
    monkeypatch.delenv(STUDIO_DATA_ENV)
    monkeypatch.setenv("COMMANDER_LAB_OWNER_DATA", str(tmp_path / "owner"))
    assert studio_data_dir() == (tmp_path / "owner" / "studio").resolve()


def test_store_persists_and_rejects_a_foreign_schema(tmp_path: Path) -> None:
    first = StudioStore.open(tmp_path)
    first.register_source(data_class=DataClass.ORIGINAL_SOURCE, title="a", sha256="ab" * 32)
    first.connection.commit()
    first.close()
    second = StudioStore.open(tmp_path)
    assert second.count("source") == 1
    second.connection.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
    second.connection.commit()
    second.close()
    with pytest.raises(RuntimeError, match="schema 999"):
        StudioStore.open(tmp_path)
    with pytest.raises(ValueError):
        StudioStore.in_memory().count("sqlite_master")


def test_inventory_import_keeps_unknown_legality_unknown(
    store: StudioStore, tmp_path: Path
) -> None:
    assert store.count("card") == 77
    assert store.count("inventory") == 77
    row = store.connection.execute(
        "SELECT commander_legal FROM card WHERE oracle_name = 'Unverified Charm'"
    ).fetchone()
    assert row["commander_legal"] is None
    reserved = store.connection.execute(
        "SELECT reserved, available_lower_bound FROM inventory WHERE card_id = 'card:project:0006'"
    ).fetchone()
    assert (reserved["reserved"], reserved["available_lower_bound"]) == (1, 0)
    # a second import of the same file replaces, it does not duplicate
    importers.import_inventory_workbook(store, tmp_path / "cards.xlsx")
    assert store.count("card") == 77
    assert store.count("source") == 1


def test_inventory_import_rejects_an_empty_quantity(tmp_path: Path) -> None:
    workbook = Workbook()
    identity = workbook.active
    assert identity is not None
    identity.title = importers.IDENTITY_SHEET
    identity.append(IDENTITY_COLUMNS)
    card = _card(1, "Lonely Card", "G", "Creature")
    identity.append([card[column] for column in IDENTITY_COLUMNS])
    inventory = workbook.create_sheet(importers.INVENTORY_SHEET)
    inventory.append(INVENTORY_COLUMNS)
    inventory.append([card["card_id"], "Lonely Card", None, 1, 0, 1, True, 1, None])
    path = tmp_path / "broken.xlsx"
    workbook.save(path)
    with pytest.raises(ValueError, match="observed_quantity is empty"):
        importers.import_inventory_workbook(StudioStore.in_memory(), path)


def test_legal_pool_follows_color_identity_and_legality(store: StudioStore) -> None:
    pool = legal_pool(store, ["Test Commander"])
    names = {row["oracle_name"] for row in pool}
    assert {"Forest", "Reserved Bear", "Swarm Rat", "Filler 00"} <= names
    assert names.isdisjoint({"Red Outsider", "Banned Relic", "Unverified Charm"})
    assert sum(1 for row in pool if row["available"] > 0) == len(pool) - 1
    with pytest.raises(KeyError):
        legal_pool(store, ["No Such Commander"])


def test_revision_is_content_addressed_and_idempotent(store: StudioStore) -> None:
    cards = _legal_deck(store)
    first = create_revision(store, deck_id="test", name="Test deck", cards=cards)
    again = create_revision(store, deck_id="test", name="Test deck", cards=list(reversed(cards)))
    assert first == again == f"test@{deck_hash(cards)[:16]}"
    assert store.count("deck_revision") == 1
    changed = [
        *cards[:-1],
        RevisionCard("card:project:0002", 28),
        RevisionCard("card:project:0007"),
    ]
    second = create_revision(
        store, deck_id="test", name="Test deck", cards=changed, parent_revision_id=first,
        branch="rats",
    )  # fmt: skip
    assert second != first
    branches = dict(
        store.connection.execute(
            "SELECT branch, revision_id FROM deck_branch WHERE deck_id = 'test'"
        )
    )
    assert branches == {"main": first, "rats": second}
    with pytest.raises(ValueError):
        create_revision(
            store, deck_id="test", name="Test deck", cards=[RevisionCard("card:project:9999")]
        )


def test_a_legal_revision_has_no_findings(store: StudioStore) -> None:
    revision = create_revision(store, deck_id="test", name="Test deck", cards=_legal_deck(store))
    assert validate_revision(store, revision) == []


@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        (RevisionCard("card:project:0003"), {"color_identity"}),
        (RevisionCard("card:project:0004"), {"not_legal"}),
        (RevisionCard("card:project:0005"), {"legality_unknown"}),
        (RevisionCard("card:project:0006"), {"not_available"}),
        (RevisionCard("card:project:0100"), {"singleton", "not_available"}),
        (RevisionCard("card:project:0007", 2), {"deck_size"}),
        (None, {"deck_size"}),
    ],
)
def test_validation_codes(
    store: StudioStore, replacement: RevisionCard | None, expected: set[str]
) -> None:
    cards = _legal_deck(store)
    cards[-1] = RevisionCard("card:project:0002", 28)
    if replacement is not None:
        cards.append(replacement)
    revision = create_revision(store, deck_id="test", name="Test deck", cards=cards)
    assert _codes(store, revision) == expected


def test_validation_of_commanders_and_ownership(store: StudioStore) -> None:
    cards = _legal_deck(store)
    no_commander = create_revision(
        store, deck_id="a", name="a", cards=[*cards[1:], RevisionCard("card:project:0007")]
    )
    assert "commander_count" in _codes(store, no_commander)
    plain = [RevisionCard("card:project:0100", 1, "commander"), *cards[2:], cards[1]]
    plain[-1] = RevisionCard("card:project:0001")
    odd_commander = create_revision(store, deck_id="b", name="b", cards=plain)
    assert "commander_type" in _codes(store, odd_commander)
    store.connection.execute("DELETE FROM inventory WHERE card_id = 'card:project:0101'")
    revision = create_revision(store, deck_id="c", name="c", cards=cards)
    assert _codes(store, revision) == {"not_owned"}
    assert _codes(store, revision, owned_only=False) == set()


def test_snapshot_is_readable_by_the_lab_loader(store: StudioStore, tmp_path: Path) -> None:
    revision = create_revision(store, deck_id="test", name="Test deck", cards=_legal_deck(store))
    snapshot = lab_snapshot(store, revision)
    assert snapshot["studio_revision_id"] == revision
    assert snapshot["commander"]["commanders"] == ["Test Commander"]
    assert sum(card["quantity"] for card in snapshot["cards"]) == 100
    path = tmp_path / "deck.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    loaded = load_rules_deck_snapshot(path)
    assert loaded.deck_id == "test"


def test_selection_import_creates_a_revision_and_reports_the_reserve(
    store: StudioStore, tmp_path: Path
) -> None:
    deck = {f"card:project:{100 + i:04d}": {"qty": 1, "status": "test"} for i in range(70)}
    deck["card:project:0002"] = {"qty": 29, "status": "test"}
    status = {card_id: {"status": "test"} for card_id in deck}
    status["card:project:0007"] = {"status": "reserve"}
    path = tmp_path / "selection.json"
    path.write_text(json.dumps({"state": {"deck": deck, "status": status}}), encoding="utf-8")
    result = importers.import_studio_selection(
        store, path, deck_id="test", name="Test deck", commander_names=["Test Commander"]
    )
    assert result["main_entries"] == 71
    assert result["reserve_card_ids"] == ["card:project:0007"]
    assert validate_revision(store, result["revision_id"]) == []
    with pytest.raises(ValueError, match="commander not found"):
        importers.import_studio_selection(
            store, path, deck_id="test", name="Test deck", commander_names=["Nobody"]
        )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _register_row(deck_id: str, group: str, duplicate_of: str = "") -> dict[str, object]:
    return {
        "deck_id": deck_id,
        "source_cohort": "SYNTHETIC",
        "original_url": f"https://example.invalid/{deck_id}",
        "source_platform": "example",
        "group": group,
        "date": "",
        "source_archetype_tags": "",
        "fingerprint_scryfall_oracle": f"fp-{duplicate_of or deck_id}",
        "exact_duplicate_of": duplicate_of,
        "current_legality_name_audit": "legal",
    }


def _card_row(deck_id: str, name: str, quantity: int = 1) -> dict[str, object]:
    return {
        "source": "SYNTHETIC",
        "deck_id": deck_id,
        "raw_card_name": name,
        "canonical_name": name,
        "oracle_id": "",
        "quantity": quantity,
        "section": "mainboard",
        "normalization_status": "exact",
    }


def test_corpus_inclusion_counts_distinct_decks_with_a_denominator(
    store: StudioStore, tmp_path: Path
) -> None:
    register = _write_csv(
        tmp_path / "register.csv",
        [
            _register_row("d1", "community"),
            _register_row("d2", "community"),
            _register_row("d3", "turnier_cedh"),
            _register_row("d4", "community", duplicate_of="d1"),
        ],
    )
    cards = _write_csv(
        tmp_path / "cards.csv",
        [
            _card_row("d1", "Forest", 3),
            _card_row("d1", "Forest", 2),
            _card_row("d1", "Swarm Rat"),
            _card_row("d3", "Swarm Rat"),
            _card_row("d4", "Swarm Rat"),
            _card_row("unregistered", "Swarm Rat"),
        ],
    )
    assert importers.import_corpus_register(store, register) == {"decks": 4}
    assert importers.import_corpus_cards(store, cards) == {
        "rows": 4,
        "rows_without_registered_deck": 1,
    }
    merged = store.connection.execute(
        "SELECT quantity FROM corpus_deck_card WHERE deck_id = 'd1' AND card_name = 'Forest'"
    ).fetchone()
    assert merged["quantity"] == 5
    named = ["Test Commander"]
    # without a binding no deck is counted: unknown, not zero percent
    unbound = corpus_inclusion(store, "Swarm Rat", named)
    assert (unbound["hits"], unbound["denominator"], unbound["share"]) == (0, 0, None)
    assert store.bind_unbound("Test Commander") == 4
    assert store.bind_unbound("Other Commander") == 0  # bound rows are never re-labelled
    assert corpus_inclusion(store, "Swarm Rat", ["Other Commander"])["denominator"] == 0
    everything = corpus_inclusion(store, "Swarm Rat", named)
    assert (everything["hits"], everything["denominator"]) == (2, 3)
    assert everything["share"] == pytest.approx(2 / 3)
    community = corpus_inclusion(store, "Swarm Rat", named, play_group="community")
    assert (community["hits"], community["denominator"]) == (1, 2)
    empty = corpus_inclusion(store, "Swarm Rat", named, play_group="no_such_group")
    assert empty["denominator"] == 0
    assert empty["share"] is None


def test_edhrec_import_keeps_denominators_and_marks_missing_lift_unknown(
    store: StudioStore, tmp_path: Path
) -> None:
    def row(theme: str, lift: str, numerator: int, denominator: int) -> dict[str, object]:
        return {
            "card_id": "card:project:0007",
            "oracle_id": "",
            "card_name": "Swarm Rat",
            "theme": theme,
            "inclusion_pct": round(100 * numerator / denominator, 2),
            "lift": lift,
            "num_decks": numerator,
            "potential_decks": denominator,
            "url": f"https://example.invalid/{theme}",
            "category": "creatures",
            "status": "ok",
            "snapshot_utc": "2026-11-09T00:00:00Z",
        }

    table = _write_csv(
        tmp_path / "edhrec.csv", [row("general", "1.5", 50, 1000), row("tiny", "", 3, 12)]
    )
    assert importers.import_edhrec_table(store, table) == {"rows": 2}
    assert importers.import_edhrec_table(store, table) == {"rows": 2}
    assert store.count("observation") == 4
    unknown = store.connection.execute(
        "SELECT cohort, metric, value FROM observation WHERE data_class = 'UNKNOWN'"
    ).fetchall()
    assert [tuple(item) for item in unknown] == [("edhrec:tiny", "lift", None)]
    tiny = store.connection.execute(
        "SELECT numerator, denominator, data_class FROM observation "
        "WHERE cohort = 'edhrec:tiny' AND metric = 'inclusion_pct'"
    ).fetchone()
    assert tuple(tiny) == (3, 12, "ORIGINAL_SOURCE")


def test_command_line_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workbook = _workbook(tmp_path / "cards.xlsx", _synthetic_cards())
    data = str(tmp_path / "studio")
    assert studio_main(["--data", data, "import-inventory", str(workbook)]) == 0
    assert studio_main(["--data", data, "pool", "--commander", "Test Commander"]) == 0
    assert studio_main(["--data", data, "status"]) == 0
    output = capsys.readouterr().out
    assert '"cards": 77' in output
    assert '"legal": 74' in output
    assert '"inventory": 77' in output


def test_hub_corpus_import_excludes_bracket_one_and_isolates_neutral_boards(
    store: StudioStore, tmp_path: Path
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_csv(
        hub / "01_DECK_CATALOG_994_SOURCES.csv",
        [
            {
                "deck_id": "d1",
                "cohort": "C087_BASELINE_2026_11_10",
                "source": "TEST",
                "platform": "archidekt",
                "title": "D1",
                "original_url": "https://example.invalid/d1",
                "mainboard_quantity": "99",
                "mainboard_name_rows": "2",
                "commander": "Test Commander",
                "content_fingerprint_sha256": "fp-1",
                "oracle_unresolved_count": "0",
                "is_new_vs_baseline": "false",
                "original_archetype_tag": "NOT_LISTED",
                "unique_deck_representative": "true",
                "identical_content_source_count": "2",
                "source_archetype_tag_status": "NOT_LISTED",
                "original_content_fingerprint_sha256": "fp-1",
                "source_revision_status": "FROZEN_BASELINE",
                "bracket_user_set": "",
                "bracket_import_policy": "",
                "source_key": "k1",
                "source_document_sha256": "s1",
            },
            {
                "deck_id": "d1_dup",
                "cohort": "2026_11_10_USER_BATCHES",
                "source": "TEST",
                "platform": "archidekt",
                "title": "D1 Dup",
                "original_url": "https://example.invalid/d1_dup",
                "mainboard_quantity": "99",
                "mainboard_name_rows": "2",
                "commander": "Test Commander",
                "content_fingerprint_sha256": "fp-1",
                "oracle_unresolved_count": "0",
                "is_new_vs_baseline": "true",
                "original_archetype_tag": "",
                "unique_deck_representative": "false",
                "identical_content_source_count": "2",
                "source_archetype_tag_status": "NOT_LISTED",
                "original_content_fingerprint_sha256": "fp-1",
                "source_revision_status": "NEW",
                "bracket_user_set": "UNKNOWN",
                "bracket_import_policy": "",
                "source_key": "k2",
                "source_document_sha256": "s2",
            },
            {
                "deck_id": "d_b1",
                "cohort": "NEW_RESEARCH_2026_11_10",
                "source": "TEST",
                "platform": "archidekt",
                "title": "Bracket 1 Excluded",
                "original_url": "https://example.invalid/db1",
                "mainboard_quantity": "99",
                "mainboard_name_rows": "1",
                "commander": "Test Commander",
                "content_fingerprint_sha256": "fp-b1",
                "oracle_unresolved_count": "0",
                "is_new_vs_baseline": "true",
                "original_archetype_tag": "",
                "unique_deck_representative": "true",
                "identical_content_source_count": "1",
                "source_archetype_tag_status": "NOT_LISTED",
                "original_content_fingerprint_sha256": "fp-b1",
                "source_revision_status": "NEW",
                "bracket_user_set": "1",
                "bracket_import_policy": "EXCLUDE",
                "source_key": "k3",
                "source_document_sha256": "s3",
            },
        ],
    )
    _write_csv(
        hub / "02_CARD_DICTIONARY_01.csv",
        [
            {
                "card_code": "C00001",
                "oracle_id": "oracle-forest",
                "canonical_name": "Forest",
                "snapshot_legality": "legal",
                "snapshot_color_identity": "G",
                "snapshot_type_line": "Basic Land — Forest",
                "oracle_id_status": "PROVIDED",
                "source_normalization_status": "RESOLVED_EXACT",
            },
            {
                "card_code": "C00002",
                "oracle_id": "oracle-koma",
                "canonical_name": "Koma, Cosmos Serpent",
                "snapshot_legality": "legal",
                "snapshot_color_identity": "GU",
                "snapshot_type_line": "Legendary Creature — Serpent",
                "oracle_id_status": "PROVIDED",
                "source_normalization_status": "RESOLVED_EXACT",
            },
        ],
    )
    (hub / "03_MAINBOARD_99_COMPACT_01.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "deck_id": "d1",
                        "fingerprint": "fp-1",
                        "cards": [["C00001", 98], ["C00002", 1]],
                    }
                ),
                json.dumps(
                    {
                        "deck_id": "d1_dup",
                        "fingerprint": "fp-1",
                        "cards": [["C00001", 98], ["C00002", 1]],
                    }
                ),
                json.dumps({"deck_id": "d_b1", "fingerprint": "fp-b1", "cards": [["C00001", 99]]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        hub / "06_OTHER_BOARDS_NEUTRAL_01.csv",
        [
            {
                "batch": "B1",
                "source_key": "k1",
                "section": "MAYBEBOARD",
                "name": "Swarm Rat",
                "oracle_id": "oracle-swarm-rat",
                "quantity": "1",
                "status": "CONFIRMED",
            },
            {
                "batch": "B1",
                "source_key": "k1",
                "section": "CUTS",
                "name": "Filler 00",
                "oracle_id": "oracle-filler-00",
                "quantity": "1",
                "status": "CONFIRMED",
            },
        ],
    )
    res = importers.import_hub_corpus(store, hub)
    assert res == {
        "decks": 2,
        "unique_decks": 1,
        "mainboard_rows": 4,
        "koma_decks": 2,
        "neutral_board_rows": 2,
    }
    # Swarm Rat is only in MAYBEBOARD, so its mainboard corpus inclusion is 0
    store.bind_unbound("Test Commander")
    assert corpus_inclusion(store, "Swarm Rat", ["Test Commander"])["hits"] == 0


def test_edhrec_delta_and_cardrecs_preserve_null_denominators_and_synergy(
    store: StudioStore, tmp_path: Path
) -> None:
    cardrecs = _write_csv(
        tmp_path / "cardrecs_alle.csv",
        [
            {
                "karte": "Swarm Rat",
                "karte_norm": "swarm rat",
                "rubrik": "tokens",
                "sektion": "Creatures",
                "inclusion_pct": "25.0",
                "lift": "1.2",
                "synergy": "0.15",
                "decks_with_card": "10",
                "eligible_decks": "40",
                "overall_decks": "40",
                "source_url": "https://example.invalid/tokens",
                "retrieved_at": "2026-11-09T00:00:00Z",
                "snapshot_id": "s1",
                "data_quality": "LIVE_JSON",
                "quelle_datei": "test",
                "nenner_warnung": "",
            }
        ],
    )
    assert importers.import_edhrec_cardrecs_csv(store, cardrecs) == {"rows": 1}
    delta = tmp_path / "10_EDHREC_STATISTICS_DELTA_001.jsonl"
    delta.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "data_kind": "EDHREC_CARDRECS_BRACKET2_CORE",
                        "oracle_name": "Swarm Rat",
                        "decks_with_card_reported": 187,
                        "inclusion_pct_reported": 33.0,
                        "lift_reported": 0.78,
                        "cohort_decks_reported": 563,
                        "eligible_decks_per_card": None,
                        "eligible_decks_status": "NOT_LISTED_IN_WEB_INDEX_TEXT",
                        "original_url": "https://example.invalid/core",
                        "source_index_crawled_date": "2026-11-09",
                    }
                ),
                json.dumps(
                    {
                        "data_kind": "EDHREC_CARDRECS_BRACKET2_CORE_HISTORIC_NN",
                        "oracle_name": "Swarm Rat",
                        "decks_with_card_n_shown": 317,
                        "eligible_decks_N_shown": 634,
                        "inclusion_pct_shown": 50.0,
                        "lift_shown": None,
                        "synergy_pct_shown": 43,
                        "original_url": "https://example.invalid/core-hist",
                        "retrieval_utc": "2026-11-10T00:00:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert importers.import_edhrec_delta_jsonl(store, delta) == {"files": 1, "rows": 2}
    core_idx = store.connection.execute(
        "SELECT numerator, denominator, snapshot FROM observation "
        "WHERE cohort = 'edhrec:core_b2_563_index' AND metric = 'inclusion_pct'"
    ).fetchone()
    # eligible_decks_per_card is None, never coerced to 563
    assert core_idx["numerator"] == 187
    assert core_idx["denominator"] is None
    assert "cohort_decks=563" in str(core_idx["snapshot"])
    syn_row = store.connection.execute(
        "SELECT value FROM observation "
        "WHERE cohort = 'edhrec:core_b2_634_hist' AND metric = 'synergy_pct'"
    ).fetchone()
    assert syn_row["value"] == pytest.approx(43.0)


def test_lab_deck_and_simulation_report_import(store: StudioStore, tmp_path: Path) -> None:
    revision = create_revision(store, deck_id="test", name="Test deck", cards=_legal_deck(store))
    snap_path = tmp_path / "chulane_current.json"
    snap_path.write_text(json.dumps(lab_snapshot(store, revision)), encoding="utf-8")
    imported = importers.import_lab_deck_snapshot(
        store, snap_path, deck_id="test", name="Test deck", branch="lab_current"
    )
    assert imported["revision_id"] == revision
    sim_path = tmp_path / "chulane_mixed_seeds1-12.json"
    sim_path.write_text(
        json.dumps(
            {
                "plan": {
                    "deck_id": "custom/chulane",
                    "pod": "mixed",
                    "games_planned": 12,
                    "seeds": [1, 2],
                },
                "summary": {
                    "games_completed": 12,
                    "games_failed": 0,
                    "wins_fractional": 2.0,
                    "win_rate_completed_games": 0.1667,
                    "mean_rounds": 11.75,
                    "hand_residence_turns": {
                        "status": "NOT_MEASURED",
                        "castable_but_uncast": [{"card": "Swarm Rat", "games_rotted": 2}],
                        "per_card_cast_opportunities": [
                            {
                                "card": "Swarm Rat",
                                "games_offered": 6,
                                "games_cast_after_offer": 4,
                                "offered_castable": 10,
                                "cast": 5,
                                "mean_first_cast_round": 4.5,
                            }
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    sim_res = importers.import_simulation_report(store, sim_path, engine_pin="f4d12f6e80")
    assert sim_res["games_completed"] == 12
    assert store.count("simulation_run") == 1
    assert store.count("simulation_card") == 1


def test_schema_12_adds_profile_lifecycle_columns_to_an_older_store(tmp_path: Path) -> None:
    import sqlite3

    from commander_lab.studio import universe

    folder = tmp_path / "studio"
    folder.mkdir()
    raw = sqlite3.connect(folder / "studio.sqlite3")
    raw.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute("INSERT INTO meta(key, value) VALUES ('schema_version', '11')")
    raw.execute(
        "CREATE TABLE universe_profile (profile_id TEXT PRIMARY KEY, "
        "name TEXT NOT NULL UNIQUE, spec TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    raw.execute(
        "INSERT INTO universe_profile VALUES ('universe:alt', 'alt', '{}', '2026-01-01T00:00:00Z')"
    )
    raw.commit()
    raw.close()
    store = StudioStore.open(folder)
    version = store.connection.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()[0]
    assert version == "14"
    profile = universe.get_profile(store, "alt")
    assert profile["version"] == 1 and profile["updated_at"] is None
    assert profile["created_at"] == "2026-01-01T00:00:00Z"
    saved = universe.save_profile(store, "alt", {})
    assert saved["version"] == 2 and saved["created_at"] == "2026-01-01T00:00:00Z"
    store.close()


def test_cli_universe_profile_lifecycle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    assert studio_main(["--data", str(data), "save-profile", "cli-profil"]) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["version"] == 1
    assert studio_main(["--data", str(data), "delete-profile", "cli-profil"]) == 0
    assert json.loads(capsys.readouterr().out) == {"deleted": "cli-profil"}
    assert studio_main(["--data", str(data), "profiles"]) == 0
    assert json.loads(capsys.readouterr().out) == {"profiles": []}
    with pytest.raises(SystemExit, match="unknown universe profile"):
        studio_main(["--data", str(data), "delete-profile", "cli-profil"])
