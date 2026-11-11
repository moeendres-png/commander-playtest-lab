"""Small offline end-to-end contract: XLSX -> Scryfall -> commander pool -> cache."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from commander_lab.studio import catalog, importers
from commander_lab.studio.store import StudioStore
from commander_lab.studio.web import create_app


def test_inventory_scryfall_commander_cache_and_upload(tmp_path: Path) -> None:
    cards = [
        ("c-chulane", "Chulane, Teller of Tales", "WUG", "Legendary Creature — Human Druid"),
        ("c-elf", "Llanowar Elves", "G", "Creature — Elf Druid"),
        ("c-bolt", "Lightning Bolt", "R", "Instant"),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "01_CARD_IDENTITY"
    ws.append(["card_id", "oracle_id", "oracle_name", "color_identity", "mana_cost",
               "mana_value", "type_line", "oracle_text", "is_basic_land",
               "commander_legal", "legality_verified_at", "identity_evidence_type"])
    for card_id, name, colors, type_line in cards:
        ws.append([card_id, None, name, colors, "{1}", 1, type_line, "Test text",
                   False, True, "2026-11-11", "SOURCE"])
    inventory = wb.create_sheet("05_INVENTORY_CURRENT")
    inventory.append(["card_id", "oracle_name", "observed_quantity",
                      "physical_owned_quantity_lower_bound", "reserved_for_opponents_quantity",
                      "available_for_own_decks_quantity_lower_bound", "quantity_exact",
                      "quantity_semantics", "number_of_lots", "currently_available_for_own_decks",
                      "last_verified_at"])
    for card_id, name, *_ in cards:
        inventory.append([card_id, name, 1, 1, 0, 1, True, "exact", 1, True, "2026-11-11"])
    source = tmp_path / "collection.xlsx"
    wb.save(source)
    bulk = tmp_path / "scryfall.jsonl"
    with bulk.open("w", encoding="utf-8") as f:
        for i, (_, name, colors, kind) in enumerate(cards):
            f.write(json.dumps({
                "id": f"printing-{i}", "oracle_id": f"oracle-{i}", "name": name,
                "layout": "normal", "lang": "en", "digital": False,
                "games": ["paper"], "type_line": kind, "color_identity": list(colors),
                "legalities": {"commander": "legal"}, "mana_cost": "{1}", "cmc": 1,
                "oracle_text": "Test text", "released_at": "2026-11-09",
            }) + "\n")
    store = StudioStore.open(tmp_path / "private")
    try:
        assert importers.import_inventory_workbook(store, source)["cards"] == 3
        report = catalog.import_scryfall_oracle(store, bulk)
        assert report["linked"] == 3
    finally:
        store.close()

    with TestClient(create_app(tmp_path / "private")) as client:
        commanders = client.get("/api/commanders")
        assert commanders.status_code == 200
        assert "Chulane, Teller of Tales" in [x["name"] for x in commanders.json()]
        pool = client.get("/api/pool", params={"commander": "Chulane, Teller of Tales"})
        assert pool.status_code == 200, pool.text
        names = {c["name"] for c in pool.json()["cards"]}
        assert "Llanowar Elves" in names
        assert "Lightning Bolt" not in names
        files = list((tmp_path / "private" / "cache" / "commanders").glob("*.json"))
        assert len(files) == 1
        assert json.loads(files[0].read_text())["public_card_count"] == 2
        upload = client.post(
            "/api/import-inventory",
            files={"file": ("collection.xlsx", source.read_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers={"X-Studio": "1"},
        )
        assert upload.status_code == 200, upload.text
        assert upload.json()["cards"] == 3
