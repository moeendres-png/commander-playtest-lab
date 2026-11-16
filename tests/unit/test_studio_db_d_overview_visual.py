"""Self-contained unit tests for PR DB-D (#1404 op. 9, P3 fixes, CSP inline-style removal, visual update)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, combos, decks, packages
from commander_lab.studio.decks import RevisionCard
from commander_lab.studio.store import now_utc
from commander_lab.studio.web import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def _seed_source(store: StudioStore, source_id: str = "src-dbd") -> None:
    store.connection.execute(
        "INSERT OR IGNORE INTO source (source_id, data_class, title, sha256, imported_at) "
        "VALUES (?, 'ORIGINAL_SOURCE', 'DB-D Fixture', ?, ?)",
        (source_id, "0" * 64, now_utc()),
    )


def _insert_card(
    store: StudioStore,
    card_id: str,
    name: str,
    *,
    identity: str = "G",
    mana_cost: str = "{G}",
    mana_value: float = 1.0,
    type_line: str = "Creature — Elf",
    oracle_text: str = "{T}: Add {G}.",
) -> None:
    oid = f"oid-{card_id}"
    with store.connection:
        _seed_source(store)
        store.connection.execute(
            "INSERT OR REPLACE INTO card "
            "(card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value, "
            "type_line, oracle_text, is_basic_land, commander_legal, source_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 'src-dbd')",
            (card_id, oid, name, identity, mana_cost, mana_value, type_line, oracle_text),
        )
        store.connection.execute(
            "INSERT OR REPLACE INTO inventory "
            "(card_id, observed, owned_lower_bound, reserved, available_lower_bound, "
            "quantity_exact, source_id) "
            "VALUES (?, 1, 1, 0, 1, 1, 'src-dbd')",
            (card_id,),
        )


def test_combos_rejects_nonfinite_and_invalid_color_filters() -> None:
    for bad_query in (
        "mv:nan",
        "mv:inf",
        "pow:-inf",
        "tou:nan",
        "id:xyz",
        "id:wc",
        "c:wc",
        "c:123",
    ):
        with pytest.raises(combos.UnsupportedQueryError):
            combos.compile_scryfall_query(bad_query)
        status, reason, matched = combos.evaluate_scryfall_query(bad_query, [])
        assert status == "UNKNOWN"
        assert reason is not None and reason.startswith("UNSUPPORTED_QUERY:")
        assert matched == []


def test_combos_supports_colorless_c_identity_and_color() -> None:
    cards = [
        {
            "name": "Sol Ring",
            "identity": frozenset(),
            "mana_colors": frozenset(),
            "mana_value": 1.0,
        },
        {
            "name": "Llanowar Elves",
            "identity": frozenset({"G"}),
            "mana_colors": frozenset({"G"}),
            "mana_value": 1.0,
        },
        {
            "name": "Arcane Signet",
            "identity": frozenset(),
            "mana_colors": frozenset(),
            "mana_value": 2.0,
        },
    ]
    for query in ("id:c", "id=c", "c:c", "c=c"):
        status, reason, matched = combos.evaluate_scryfall_query(query, cards)
        assert status == "OK" and reason is None
        assert [c["name"] for c in matched] == ["Sol Ring", "Arcane Signet"]


def test_deck_packages_queries_list_rows_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = StudioStore.open(tmp_path)
    _insert_card(
        store,
        "cmd-chulane",
        "Chulane, Teller of Tales",
        identity="G,U,W",
        mana_cost="{2}{G}{W}{U}",
        mana_value=5.0,
        type_line="Legendary Creature — Human Druid",
    )
    _insert_card(store, "c-elf", "Llanowar Elves")
    cards = [
        RevisionCard(card_id="cmd-chulane", quantity=1, zone="commander"),
        RevisionCard(card_id="c-elf", quantity=1, zone="main"),
    ]

    orig_list_rows = decks.list_rows
    calls = 0

    def _counting_list_rows(st: StudioStore, card_seq):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return orig_list_rows(st, card_seq)

    monkeypatch.setattr(packages, "list_rows", _counting_list_rows)
    result = packages.deck_packages(
        store,
        ["Chulane, Teller of Tales"],
        cards,
        template_snapshot_path=tmp_path / "missing_templates.json",
    )
    assert calls == 1
    assert result["schema"] == packages.PACKAGES_SCHEMA


def test_studio_static_has_zero_inline_styles_and_xss_sinks() -> None:
    for html_path in sorted(STATIC_DIR.glob("*.html")):
        text = html_path.read_text(encoding="utf-8")
        assert " style=" not in text, f"inline style= in {html_path.name}"
        assert "<script>" not in text, f"inline <script> in {html_path.name}"

    style_key_re = re.compile(r"\bstyle\s*:")
    style_attr_re = re.compile(r"setAttribute\(\s*['\"]style['\"]|style\s*=")
    for js_path in sorted(STATIC_DIR.glob("*.js")):
        text = js_path.read_text(encoding="utf-8")
        assert ".innerHTML" not in text and ".outerHTML" not in text, js_path.name
        assert "insertAdjacentHTML" not in text and "eval(" not in text, js_path.name
        assert not style_attr_re.search(text), f"style attribute/assignment in {js_path.name}"
        for lineno, line in enumerate(text.splitlines(), start=1):
            if style_key_re.search(line):
                # partie.js sends pilot JSON setting `style: Number(ownStyle.value)`
                assert js_path.name == "partie.js" and "ownStyle.value" in line, (
                    f"CSS style: in {js_path.name}:{lineno}: {line.strip()}"
                )


def test_overview_wiring_css_classes_and_http_serving(tmp_path: Path) -> None:
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    overview_js = (STATIC_DIR / "overview.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    app_css = (STATIC_DIR / "app.css").read_text(encoding="utf-8")

    assert '<script src="overview.js"></script>' in index_html
    assert "renderDeckOverview" in overview_js
    assert "/api/land-advisor" in overview_js
    assert "/api/castability" in overview_js
    assert "/api/deck-facts" in overview_js
    assert "/api/layers" in overview_js
    assert 'l.status === "MISSING"' in overview_js
    assert "l.present" not in overview_js
    assert "keine Gesamtnote" in overview_js
    assert '["state", "Zustand"]' in app_js
    assert "state: renderOverview" in app_js
    assert "bh-${pct}" in app_js

    for required_css in (
        ".bh-0{height:0%}",
        ".bh-50{height:50%}",
        ".bh-100{height:100%}",
        ".overview-grid",
        ".kpi-row",
        ".kpi-card",
        ".card-box",
        ".chip.chip-static",
        "#modal-box.plain.wide",
        ".mr-1",
        ".ml-1",
        ".nowrap",
        ".pre-line",
        ".inline-item",
    ):
        assert required_css in app_css, f"missing CSS rule {required_css}"

    store = StudioStore.open(tmp_path)
    store.close()
    app = create_app(tmp_path)
    client = TestClient(app)
    for asset in (
        "/",
        "/index.html",
        "/decks.html",
        "/tierliste.html",
        "/partie.html",
        "/overview.js",
        "/app.css",
        "/tierliste.css",
        "/partie.css",
    ):
        resp = client.get(asset)
        assert resp.status_code == 200, asset
        csp = resp.headers.get("content-security-policy", "")
        assert "style-src 'self'" in csp and "'unsafe-inline'" not in csp
