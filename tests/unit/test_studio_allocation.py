"""Card allocation: bindings of saved decks, overbooking, locations (#1419)."""

from __future__ import annotations

from pathlib import Path

import pytest
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


def test_deck_without_main_variant_and_without_inventory_row(tmp_path: Path) -> None:
    store = _store_with_locations(tmp_path)
    with store.connection as db:
        db.execute("DELETE FROM inventory WHERE card_id = ?", (B,))
    # Only a "probe" variant exists: it is the most recently saved one and binds the copies.
    create_revision(store, deck_id="d1", name="Deck Eins", cards=[RevisionCard(B)], branch="probe")
    result = allocation.allocation(store)
    assert [(d["deck_id"], d["branch"]) for d in result["decks_binding"]] == [("d1", "probe")]
    entry = result["cards"][B]
    assert (entry["bound"], entry["available"], entry["owned"]) == (1, None, None)
    assert entry["overbooked"] is False
    assert entry["other_variants"] == []
    assert B not in result["overbooked"]


# --- build list by storage location (#1404) ---


def _rows(store: StudioStore, *cards: RevisionCard):  # type: ignore[no-untyped-def]
    from commander_lab.studio.decks import list_rows

    return list_rows(store, list(cards))


def _group_map(result: dict[str, object]) -> dict[str, list[tuple[str, int]]]:
    groups = result["groups"]
    assert groups
    return {
        str(g["name"]): [(str(c["name"]), int(c["quantity"])) for c in g["cards"]] for g in groups
    }


def test_build_list_places_copies_largest_stock_first_and_rest_is_unknown(tmp_path: Path) -> None:
    from commander_lab.studio import build_list

    store = _store_with_locations(tmp_path)
    # A lies 2x in "A Box", 1x in "L Box"; B has no location; C only "mindestens 37" in the
    # unknown-location row, which is no box.
    rows = _rows(store, RevisionCard(A, 4), RevisionCard(B, 1), RevisionCard(C, 2))
    result = build_list.build_list(store, rows, expected_total=7)
    assert result["error"] is None
    assert _group_map(result) == {
        "A Box": [("Alpha Bear", 2)],
        "L Box": [("Alpha Bear", 1)],
        "Standort unbekannt": [("Alpha Bear", 1), ("Beta Bear", 1), ("Gamma", 2)],
    }
    names = [g["name"] for g in result["groups"]]
    assert names[-1] == build_list.UNKNOWN_GROUP_NAME
    assert [g["count"] for g in result["groups"]] == [2, 1, 4]
    assert result["totals"]["counted"] == 7 == result["totals"]["list_size"]
    # Alpha: 3 of 4 placed (rest unknown); Beta and Gamma: no known location.
    assert result["card_status"] == {
        "exact": 0,
        "lower_bound": 0,
        "partly_unknown": 1,
        "unknown": 2,
        "of": 3,
    }


def test_build_list_lower_bound_location_and_exactness(tmp_path: Path) -> None:
    from commander_lab.studio import build_list

    store = _store_with_locations(tmp_path)
    with store.connection as db:
        db.execute(
            "UPDATE card_location SET exact = 0, unknown_lots = 1 "
            "WHERE card_id = ? AND location_id = 'location:l_box'",
            (A,),
        )
    result = build_list.build_list(store, _rows(store, RevisionCard(A, 3)), expected_total=3)
    cards = {g["name"]: g["cards"][0] for g in result["groups"]}
    assert cards["A Box"]["exact"] is True
    assert (cards["L Box"]["exact"], cards["L Box"]["unknown_lots"]) == (False, 1)
    assert result["card_status"]["lower_bound"] == 1


def test_build_list_bound_note_only_when_free_copies_fall_short(tmp_path: Path) -> None:
    from commander_lab.studio import build_list

    store = _store_with_locations(tmp_path)
    with store.connection as db:
        db.execute("UPDATE inventory SET available_lower_bound = 3 WHERE card_id = ?", (A,))
    create_revision(store, deck_id="d1", name="Deck Eins", cards=[RevisionCard(A, 2)])
    rows = _rows(store, RevisionCard(A, 2))
    # 3 free - 2 bound elsewhere = 1 < 2 needed: a note, nothing is blocked.
    other = build_list.build_list(store, rows, expected_total=2, deck_id="d2")
    notes = [c["note"] for g in other["groups"] for c in g["cards"]]
    assert notes and set(notes) == {"in Deck Eins gebunden (2)"}
    # The deck itself does not count as "another" deck.
    own = build_list.build_list(store, rows, expected_total=2, deck_id="d1")
    assert {c["note"] for g in own["groups"] for c in g["cards"]} == {None}
    # Enough free copies left: no note.
    one = build_list.build_list(store, _rows(store, RevisionCard(A, 1)), expected_total=1)
    assert {c["note"] for g in one["groups"] for c in g["cards"]} == {None}


def test_build_list_basic_lands_commander_and_sum_probe(tmp_path: Path) -> None:
    from commander_lab.studio import build_list

    store = _store_with_locations(tmp_path)
    with store.connection as db:
        db.execute("UPDATE card SET is_basic_land = 1 WHERE card_id = ?", (B,))
    rows = _rows(store, RevisionCard(A, 1, "commander"), RevisionCard(B, 30), RevisionCard(C, 1))
    result = build_list.build_list(store, rows, expected_total=32)
    assert result["basic_lands"] == {
        "cards": [{"card_id": B, "name": "Beta Bear", "quantity": 30}],
        "count": 30,
    }
    assert [c["name"] for c in result["commander"]] == ["Alpha Bear"]
    assert [g["name"] for g in result["groups"]] == ["Standort unbekannt"]
    assert result["error"] is None and result["totals"]["counted"] == 32
    # A differing list size is an error line, never a silent difference.
    wrong = build_list.build_list(store, rows, expected_total=33)
    assert "Summenprobe" in str(wrong["error"])
    with pytest.raises(build_list.BuildListError):
        build_list.build_list(store, [], expected_total=0)


def test_build_list_route_paths(tmp_path: Path) -> None:
    store = _store_with_locations(tmp_path)
    store.close()
    app = create_app(tmp_path / "studio")
    client = TestClient(app, headers={"X-Studio": "1"})
    ok = client.post("/api/build-list", json={"cards": [{"card_id": A, "quantity": 3}]})
    assert ok.status_code == 200, ok.text
    assert [g["name"] for g in ok.json()["groups"]] == ["A Box", "L Box"]
    assert (
        client.post("/api/build-list", json={"cards": [{"card_id": "card:x"}]}).status_code == 404
    )
    assert client.post("/api/build-list", json={"cards": []}).status_code == 422
    too_many = [{"card_id": f"card:{i}"} for i in range(301)]
    assert client.post("/api/build-list", json={"cards": too_many}).status_code == 422
    bare = TestClient(app)
    assert bare.post("/api/build-list", json={"cards": [{"card_id": A}]}).status_code == 403
