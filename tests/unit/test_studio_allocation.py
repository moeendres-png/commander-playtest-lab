"""Card allocation: bindings of saved decks, overbooking, locations (#1419)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from commander_lab.studio import StudioStore, allocation, builder, importers
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.web import create_app
from tests.unit.test_studio_printings import _lot, _workbook_with_printings
from tests.unit.test_studio_store import _card


def _cards() -> list[dict[str, object]]:
    return [
        _card(1, "Alpha Bear", "G", "Creature"),
        _card(2, "Beta Bear", "G", "Creature"),
        _card(3, "Gamma", "G", "Creature"),
    ]


A, B, C = "card:project:0001", "card:project:0002", "card:project:0003"


def _store_with_locations(tmp_path: Path, *, with_location_sheet: bool = True) -> StudioStore:
    lots = [
        {**_lot(A, "ISD#1", 1), "location_id": "location:l_box"},
        {**_lot(A, "ISD#2", 1), "location_id": "location:a_box"},
        {**_lot(A, "ISD#3", 1), "location_id": "location:a_box"},
        {**_lot(B, "ISD#4", 1), "location_id": None},
        # Only a lower bound known (observed 0, at least 37): never stored as 0.
        {
            **_lot(C, "ISD#5", 0),
            "quantity_lower_bound": 37,
            "quantity_exact": False,
            "location_id": "location:unknown",
        },
        {
            **_lot(C, "ISD#6", 1),
            "quantity_observed": None,
            "quantity_lower_bound": None,
            "location_id": "location:unknown",
        },
    ]
    path = _workbook_with_printings(tmp_path / "cards.xlsx", _cards(), lots)
    if with_location_sheet:
        workbook = load_workbook(path)
        sheet = workbook.create_sheet(importers.LOCATIONS_SHEET)
        sheet.append(["location_id", "location_name", "location_type", "ownership_semantics"])
        sheet.append(["location:l_box", "L Box", "physical_storage", "Location only."])
        sheet.append(["location:a_box", "A Box", "physical_storage", "Location only."])
        workbook.save(path)
    store = StudioStore.open(tmp_path / "studio")
    importers.import_inventory_workbook(store, path)
    return store


def test_locations_come_from_the_lot_sheet_in_the_data_wording(tmp_path: Path) -> None:
    store = _store_with_locations(tmp_path)
    cards = allocation.allocation(store)["cards"]
    assert cards[A]["locations"] == [
        {
            "location_id": "location:a_box",
            "name": "A Box",
            "type": "physical_storage",
            "quantity": 2,
            "exact": True,
            "unknown_lots": 0,
        },
        {
            "location_id": "location:l_box",
            "name": "L Box",
            "type": "physical_storage",
            "quantity": 1,
            "exact": True,
            "unknown_lots": 0,
        },
    ]
    unknown = cards[C]["locations"]
    assert [(i["quantity"], i["exact"], i["unknown_lots"]) for i in unknown] == [(37, False, 1)]
    # A lot without a location id gives no location: the field is absent, never guessed.
    assert B not in cards


def test_location_without_sheet_keeps_its_id(tmp_path: Path) -> None:
    store = _store_with_locations(tmp_path, with_location_sheet=False)
    names = [item["name"] for item in allocation.allocation(store)["cards"][A]["locations"]]
    assert names == ["location:a_box", "location:l_box"]


def test_one_copy_in_two_saved_decks_is_overbooked_variants_and_drafts_bind_nothing(
    tmp_path: Path,
) -> None:
    store = _store_with_locations(tmp_path)
    # Every card of the fixture has 1 copy, 1 free.
    create_revision(store, deck_id="d1", name="Deck Eins", cards=[RevisionCard(C)])
    create_revision(store, deck_id="d2", name="Deck Zwei", cards=[RevisionCard(C)])
    # A second variant of d1 with card:b binds nothing (alternative of the same deck).
    create_revision(store, deck_id="d1", name="Deck Eins", cards=[RevisionCard(B)], branch="probe")
    builder.write_draft(store, "d2", "main", [RevisionCard(B)], None)
    result = allocation.allocation(store)
    gamma = result["cards"][C]
    assert gamma["bound"] == 2
    assert gamma["available"] == 1
    assert gamma["overbooked"] is True
    assert [item["deck_id"] for item in gamma["decks"]] == ["d1", "d2"]
    beta = result["cards"][B]
    assert beta["bound"] == 0 and beta["overbooked"] is False
    assert [(v["deck_id"], v["branch"]) for v in beta["other_variants"]] == [("d1", "probe")]
    assert result["overbooked"] == [C]


def test_allocation_route(tmp_path: Path) -> None:
    store = _store_with_locations(tmp_path)
    create_revision(store, deck_id="d1", name="Deck Eins", cards=[RevisionCard(A)])
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    body = client.get("/api/allocation").json()
    assert body["schema"] == allocation.SCHEMA
    assert body["locations_known"] is True
    assert body["cards"][A]["bound"] == 1
    assert body["cards"][A]["overbooked"] is False


def test_reserved_copy_and_missing_inventory(tmp_path: Path) -> None:
    store = _store_with_locations(tmp_path)
    with store.connection as db:
        # One copy owned, kept for an opponent's deck: none free.
        db.execute(
            "UPDATE inventory SET reserved = 1, available_lower_bound = 0 WHERE card_id = ?", (A,)
        )
    create_revision(store, deck_id="d1", name="Deck Eins", cards=[RevisionCard(A)])
    entry = allocation.allocation(store)["cards"][A]
    assert (entry["bound"], entry["available"], entry["reserved"]) == (1, 0, 1)
    assert entry["overbooked"] is True
    with store.connection as db:
        db.execute("DELETE FROM inventory WHERE card_id = ?", (B,))
    create_revision(store, deck_id="d2", name="Deck Zwei", cards=[RevisionCard(B)])
    entry = allocation.allocation(store)["cards"][B]
    # Without an inventory row the free copies are unknown: no overbooking is claimed.
    assert entry["available"] is None
    assert entry["overbooked"] is False
