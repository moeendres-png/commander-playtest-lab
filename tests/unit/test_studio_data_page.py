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


def test_daten_js_renders_counts_only_without_unsafe_html_or_pricing() -> None:
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
