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
    inventory = status["source_inventory"]
    assert inventory["access_status_counts"]["prohibited"] >= 1
    # VERIFIED sources whose retrieval is prohibited (stock only) are counted apart
    assert inventory["verified_access_prohibited"] == 2
    assert "cache_enabled" in status["image_cache"]
    assert "with_snapshot_date" in status["freshness"]
    assert status["source_layers"] and "dated" in status["source_layers"][0]
    assert status["sources"] and "title" in status["sources"][0]
    for key in (
        "total_sources",
        "status_counts",
        "access_status_counts",
        "verified_access_prohibited",
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
    # #1545: the per-source status is shown on the page, not only in the JSON report
    source_status = report["source_status"]
    for key in (
        "date_known",
        "date_unknown_titles",
        "deck_file_sources",
        "snapshot_date_origin",
        "licence_and_access",
        "details",
    ):
        assert key in source_status and f"ss.{key}" in js, key
    for key in ("rows_in_store", "snapshot_date", "age_days", "address_stored"):
        assert key in source_status["details"][0] and f"src.{key}" in js, key

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


def test_daten_js_renders_source_status_with_authors_save_date_apart_from_retrieval() -> None:
    """#1545: run the real render function of daten.js against a report, not only grep its text."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = """
const fs = require('fs');
const src = fs.readFileSync('daten.js', 'utf8').replace(/^init\\(\\)[^\\n]*$/m, '');
const flat = (n) => (n === null || n === undefined ? '' : typeof n !== 'object' ? String(n)
  : Array.isArray(n) ? n.map(flat).join(' ') : [flat(n.children)].join(' '));
globalThis.StudioUI = { h: (tag, props, ...kids) => ({ tag, children: kids }),
  num: (v) => String(v), pct: (v) => String(v) };
globalThis.StudioCommander = {};
globalThis.document = { getElementById: () => null };
const report = JSON.parse(process.argv[1]);
const load = new Function(src + '; return sourceStatusNodes;');
console.log(flat(load()(report)));
"""
    report = {
        "source_status": {
            "date_known": {"count": 1, "of": 2},
            "date_unknown": 1,
            "date_unknown_of_which_value_not_a_date": 0,
            "date_unknown_titles": ["undated.csv"],
            "snapshot_date_origin": "ORIGIN-TEXT",
            "rows_in_store_origin": "ROWS-TEXT",
            "address_stored": {"count": 0, "of": 2},
            "deck_file_sources": {
                "total": 7,
                "retrieval_date": "unbekannt",
                "author_save_date_known": 5,
                "author_save_date_unknown": 2,
            },
            "licence_and_access": "LICENCE-TEXT",
            "details": [
                {
                    "title": "dated.csv",
                    "data_class": "X",
                    "rows_in_store": 3,
                    "snapshot_date": "2026-11-01",
                    "age_days": 10,
                    "address_stored": False,
                },
                {
                    "title": "undated.csv",
                    "data_class": "X",
                    "rows_in_store": 0,
                    "snapshot_date": "unbekannt",
                    "age_days": "unbekannt",
                    "address_stored": False,
                },
            ],
        }
    }
    done = subprocess.run(
        [node, "-e", script, json.dumps(report)],
        capture_output=True,
        text=True,
        check=True,
        cwd=STATIC,
    )
    out = done.stdout
    for expected in (
        "1 / 2",
        "Speicherdatum des Autors (kein Abrufdatum) 5 / 7",
        "Abrufdatum (als eine Gruppe) unbekannt (7 Dateien)",
        "ORIGIN-TEXT",
        "undated.csv",
        "dated.csv",
        "2026-11-01",
        "10 Tage",
    ):
        assert expected in out, expected
