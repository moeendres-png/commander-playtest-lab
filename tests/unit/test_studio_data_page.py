"""Tests for the dedicated Studio Data Health & Sources page (daten.html / daten.js)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore
from commander_lab.studio.web import STATIC, create_app


def test_data_page_is_linked_in_all_studio_navs_and_served(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _fill

    for name in ("index.html", "tierliste.html", "decks.html", "partie.html", "daten.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert '<a href="daten.html"' in html, f"{name} missing daten.html nav link"

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()

    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    resp = client.get("/daten.html")
    assert resp.status_code == 200
    assert "Datenlage" in resp.text

    js_resp = client.get("/daten.js")
    assert js_resp.status_code == 200
    assert "bridge_qualification" in js_resp.text


def test_daten_js_renders_counts_only_without_unsafe_html_or_pricing(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _fill

    js = (STATIC / "daten.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    for required in (
        "/api/status",
        "/api/data-report",
        "/api/layers",
        "/api/roles/audit",
        "/api/tournament-conversion",
        "bridge_qualification",
        "fallbacks_used",
        "signal_rate_alarms",
        "scryfall_facts",
        "commander-lab studio data-report",
    ):
        assert required in js

    lowered = js.casefold()
    for forbidden in ("preis", "euro", "dollar", "kaufen", "empfehl"):
        assert forbidden not in lowered

    # Verify that daten.js references real keys returned by the backend endpoints.
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})

    status = client.get("/api/status").json()
    assert "total_sources" in status["source_inventory"]
    assert "status_counts" in status["source_inventory"]
    assert "cache_enabled" in status["image_cache"]
    assert "with_snapshot_date" in status["freshness"]
    assert status["source_layers"] and "dated" in status["source_layers"][0]
    assert status["sources"] and "title" in status["sources"][0]
    for key in (
        "total_sources",
        "status_counts",
        "cache_enabled",
        "with_snapshot_date",
        "undated_note",
        "data_class",
    ):
        assert key in js, f"daten.js missing /api/status key {key}"

    report = client.get("/api/data-report").json()
    assert "identities" in report["collection"]
    assert "inventory_rows" in report["collection"]
    for key in ("identities", "inventory_rows", "ALIGNED_WITH_SEALED_EPOCH"):
        assert key in js

    layers = client.get("/api/layers?commander=Chulane,%20Teller%20of%20Tales").json()
    assert layers["layers"] and "covered" in layers["layers"][0] and "pool" in layers["layers"][0]
    assert "item.covered" in js and "item.pool" in js

    audit = client.get("/api/roles/audit").json()
    assert "claims_by_origin" in audit
    assert "claims_by_origin" in js and "pool_total" in js

    conv = client.get("/api/tournament-conversion?commander=Chulane,%20Teller%20of%20Tales").json()
    assert "total_decks" in conv and "total_known_decks" in conv and "total_converted_decks" in conv
    for key in ("total_decks", "total_known_decks", "total_converted_decks"):
        assert key in js
