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
    for query in ("id:c", "id=c"):
        status, reason, matched = combos.evaluate_scryfall_query(query, cards)
        assert status == "OK" and reason is None
        assert [c["name"] for c in matched] == ["Sol Ring", "Arcane Signet"]
    # Card color is not exact from the mana cost alone: c: stays unknown, never a count.
    for query in ("c:c", "c=c"):
        status, reason, matched = combos.evaluate_scryfall_query(query, cards)
        assert status == "UNKNOWN" and reason
        assert matched == []


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
    html_files = sorted(STATIC_DIR.glob("*.html"))
    assert html_files
    for html_path in html_files:
        text = html_path.read_text(encoding="utf-8")
        assert " style=" not in text, f"inline style= in {html_path.name}"
        assert "<script>" not in text, f"inline <script> in {html_path.name}"

    style_key_re = re.compile(r"\bstyle\s*:")
    style_attr_re = re.compile(r"setAttribute\(\s*['\"]style['\"]|style\s*=")
    js_files = sorted(STATIC_DIR.glob("*.js"))
    assert js_files
    for js_path in js_files:
        text = js_path.read_text(encoding="utf-8")
        assert ".innerHTML" not in text and ".outerHTML" not in text, js_path.name
        assert "insertAdjacentHTML" not in text and "eval(" not in text, js_path.name
        assert not style_attr_re.search(text), f"style attribute/assignment in {js_path.name}"
        lines = text.splitlines()
        assert lines
        for lineno, line in enumerate(lines, start=1):
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
    assert "/api/deck-doctor" in overview_js
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


def test_deck_doctor_remedies_and_route(tmp_path: Path) -> None:
    from commander_lab.studio import builder

    commander = "Chulane, Teller of Tales"
    store = StudioStore.open(tmp_path)
    try:
        _insert_card(
            store,
            "cmd-chulane",
            commander,
            identity="G,U,W",
            mana_cost="{2}{G}{W}{U}",
            mana_value=5.0,
            type_line="Legendary Creature — Human Druid",
        )
        _insert_card(
            store,
            "c-big",
            "Primeval Titanlike",
            identity="G",
            mana_cost="{4}{G}{G}",
            mana_value=6.0,
            type_line="Creature — Giant",
        )
        _insert_card(
            store,
            "c-dork",
            "Birds of Paradise",
            identity="G",
            mana_cost="{G}",
            mana_value=1.0,
            type_line="Creature — Bird",
        )
        _insert_card(
            store,
            "c-land-u",
            "Breeding Pool",
            identity="G,U",
            mana_cost="",
            mana_value=0.0,
            type_line="Land — Forest Island",
            oracle_text="({T}: Add {G} or {U}.)",
        )
        with store.connection:
            store.connection.execute(
                "INSERT OR IGNORE INTO card_role (oracle_id, role, source_id) "
                "VALUES ('oid-c-dork', 'ramp', 'src-dbd')"
            )
            store.connection.execute(
                "INSERT OR REPLACE INTO scryfall_card "
                "(oracle_id, scryfall_id, name, front_name, layout, mana_cost, mana_value, "
                "type_line, oracle_text, color_identity, commander_legality, keywords, "
                "produced_mana, source_id) "
                "VALUES ('oid-c-land-u', 'scry-bp', 'Breeding Pool', 'Breeding Pool', 'normal', "
                "'', 0.0, 'Land — Forest Island', '({T}: Add {G} or {U}.)', 'G,U', 'legal', '[]', 'G,U', 'src-dbd')"
            )
            for idx in range(4):
                did = f"src-deck-{idx}"
                store.connection.execute(
                    "INSERT INTO corpus_deck "
                    "(deck_id, cohort, url, platform, play_group, tags, fingerprint, legality_audit, source_id) "
                    "VALUES (?, 'all', ?, 'moxfield', 'casual', '[]', ?, 'LEGAL', 'src-dbd')",
                    (did, f"https://example.invalid/{did}", f"fp-{did}"),
                )
                store.connection.execute(
                    "INSERT INTO commander_binding (kind, key, commander_name, basis) "
                    "VALUES ('corpus_deck', ?, ?, 'test')",
                    (did, commander),
                )
                store.connection.execute(
                    "INSERT INTO corpus_deck_stat "
                    "(deck_id, cards, resolved, lands, creatures, nonland_cards, nonland_mana_value) "
                    "VALUES (?, 99, 99, 36, 30, 63, 126.0)",
                    (did,),
                )
                store.connection.execute(
                    "INSERT INTO corpus_deck_role (deck_id, role, cards) VALUES (?, 'ramp', 10)",
                    (did,),
                )
                for cname, oid in (
                    ("Birds of Paradise", "oid-c-dork"),
                    ("Breeding Pool", "oid-c-land-u"),
                ):
                    store.connection.execute(
                        "INSERT INTO corpus_deck_card "
                        "(deck_id, card_name, oracle_id, quantity, section, normalization_status) "
                        "VALUES (?, ?, ?, 1, 'main', 'OK')",
                        (did, cname, oid),
                    )

        cards = [
            RevisionCard(card_id="cmd-chulane", quantity=1, zone="commander"),
            RevisionCard(card_id="c-big", quantity=1, zone="main"),
        ]
        doc = packages.deck_doctor_remedies(store, [commander], cards, cohort="all", limit=5)
        assert doc["schema"] == packages.DECK_DOCTOR_SCHEMA
        assert doc["data_class"] == "DERIVED_DESCRIPTIVE"
        assert doc["cohort_decks"] == 4
        remedies = doc["remedies"]
        assert isinstance(remedies, list) and len(remedies) >= 4
        by_key = {str(r["key"]): r for r in remedies}
        assert "lands" in by_key
        assert by_key["lands"]["deck_value"] == 0
        assert by_key["lands"]["candidates"][0]["name"] == "Breeding Pool"
        assert by_key["lands"]["candidates"][0]["decks"] == 4
        assert by_key["lands"]["candidates"][0]["of"] == 4
        assert "colour:U" in by_key
        assert by_key["colour:U"]["candidates"][0]["name"] == "Breeding Pool"
        assert "role:ramp" in by_key
        assert by_key["role:ramp"]["candidates"][0]["name"] == "Birds of Paradise"
        assert "mana_value" in by_key
        assert by_key["mana_value"]["deck_value"] == 6.0
        assert by_key["mana_value"]["candidates"][0]["name"] == "Birds of Paradise"

        # Marks never affect deck_doctor_remedies
        builder.set_mark(store, "c-dork", favorite=False, excluded=True, note="skip")
        doc_marked = packages.deck_doctor_remedies(store, [commander], cards, cohort="all", limit=5)
        assert doc_marked == doc
    finally:
        store.close()

    client = TestClient(create_app(tmp_path))
    resp = client.post(
        "/api/deck-doctor",
        headers={"X-Studio": "1"},
        json={
            "commander": commander,
            "cards": [
                {"card_id": "cmd-chulane", "quantity": 1, "zone": "commander"},
                {"card_id": "c-big", "quantity": 1, "zone": "main"},
            ],
            "cohort": "all",
            "limit": 3,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["schema"] == packages.DECK_DOCTOR_SCHEMA
    assert len(payload["remedies"]) >= 4


def test_pod_matchup_matrix_aggregates_runs_by_pod_with_denominators_and_qualification(
    tmp_path: Path,
) -> None:
    from commander_lab.studio import builder

    commander = "Chulane, Teller of Tales"
    store = StudioStore.open(tmp_path)
    try:
        _insert_card(store, "cmd-chulane", commander)
        with store.connection:
            store.connection.execute(
                "INSERT INTO simulation_run "
                "(run_id, deck_id, pod, engine_pin, bridge_jar_sha256, bridge_qualification_state, "
                "pilot_policy, seeds, games_planned, games_completed, games_failed, "
                "wins_fractional, win_rate, mean_rounds, hand_dwell_status, source_id) "
                "VALUES ('r1', 'chulane-current', 'precon', 'pin-1', 'sha-a', "
                "'ALIGNED_WITH_SEALED_EPOCH', 'heuristic_v1', '[1,2]', 10, 10, 0, 3.0, 0.3, 8.0, 'unknown', 'src-dbd')"
            )
            store.connection.execute(
                "INSERT INTO simulation_run "
                "(run_id, deck_id, pod, engine_pin, bridge_jar_sha256, bridge_qualification_state, "
                "pilot_policy, seeds, games_planned, games_completed, games_failed, "
                "wins_fractional, win_rate, mean_rounds, hand_dwell_status, source_id) "
                "VALUES ('r2', 'chulane-current', 'precon', 'pin-1', 'sha-b', "
                "'BRIDGE_AHEAD_OF_QUALIFICATION', 'heuristic_v1', '[3,4]', 10, 10, 0, 5.0, 0.5, 6.0, 'unknown', 'src-dbd')"
            )
            store.connection.execute(
                "INSERT INTO commander_binding (kind, key, commander_name, basis) "
                "VALUES ('simulation_run', 'r1', ?, 'test'), ('simulation_run', 'r2', ?, 'test')",
                (commander, commander),
            )
        mat = builder.pod_matchup_matrix(store, [commander])
        assert mat["schema"] == "studio-pod-matrix-1"
        assert mat["data_class"] == "SIMULATED_RESULT"
        assert mat["total_runs"] == 2
        assert mat["total_games_completed"] == 20
        pods = mat["pods"]
        assert isinstance(pods, list) and len(pods) == 1
        p0 = pods[0]
        assert p0["pod"] == "precon"
        assert p0["runs_count"] == 2
        assert p0["games_completed"] == 20
        assert p0["games_planned"] == 20
        assert p0["wins_fractional"] == 8.0
        assert p0["win_rate"] == 0.4
        assert p0["mean_rounds"] == 7.0
        assert p0["all_covered_by_sealed_epoch"] is False
        assert p0["bridge_qualification_states"] == [
            "ALIGNED_WITH_SEALED_EPOCH",
            "BRIDGE_AHEAD_OF_QUALIFICATION",
        ]
    finally:
        store.close()

    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/simulations/pod-matrix", params={"commander": commander})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_games_completed"] == 20
    assert body["pods"][0]["win_rate"] == 0.4


def test_saved_filter_presets_and_quick_chips_wired_in_builder_and_tierlist() -> None:
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    tier_html = (STATIC_DIR / "tierliste.html").read_text(encoding="utf-8")
    tier_js = (STATIC_DIR / "tierliste.js").read_text(encoding="utf-8")

    assert 'id="quick-filter-presets"' in index_html
    assert "studio.builder.savedPreset" in app_js
    assert "Frühe Aktionen (MV ≤ 2)" in app_js
    assert "Ohne Rollenmarke" in app_js

    assert 'id="tier-quick-presets"' in tier_html
    assert "studio.tierlist.savedPreset" in tier_js
    assert "Verbreitung unbekannt (U)" in tier_js


def test_export_deck_dossier_and_route_with_revision_changelog(tmp_path: Path) -> None:
    from commander_lab.studio.decks import create_revision, export_deck_dossier

    commander = "Chulane, Teller of Tales"
    store = StudioStore.open(tmp_path)
    try:
        _insert_card(
            store,
            "cmd-chulane",
            commander,
            identity="G,U,W",
            mana_cost="{2}{G}{W}{U}",
            mana_value=5.0,
            type_line="Legendary Creature — Human Druid",
        )
        _insert_card(
            store,
            "c-dork",
            "Birds of Paradise",
            identity="G",
            mana_cost="{G}",
            mana_value=1.0,
            type_line="Creature — Bird",
        )
        _insert_card(
            store,
            "c-land",
            "Breeding Pool",
            identity="G,U",
            mana_cost="",
            mana_value=0.0,
            type_line="Land — Forest Island",
        )
        rev1 = create_revision(
            store,
            deck_id="chulane-test",
            name="Chulane Test",
            cards=[
                RevisionCard("cmd-chulane", 1, "commander"),
                RevisionCard("c-land", 1, "main"),
            ],
            note="Basis",
        )
        rev2 = create_revision(
            store,
            deck_id="chulane-test",
            name="Chulane Test",
            cards=[
                RevisionCard("cmd-chulane", 1, "commander"),
                RevisionCard("c-land", 1, "main"),
                RevisionCard("c-dork", 1, "main"),
            ],
            parent_revision_id=rev1,
            note="Mit Dork",
        )
        md = export_deck_dossier(store, rev2)
        assert "# Deck-Dossier: Chulane Test (chulane-test)" in md
        assert f"Änderungsprotokoll gegenüber `{rev1}`" in md
        assert "1x Birds of Paradise" in md
        assert "### Länder (1)" in md
        assert "### Zauber (1)" in md
    finally:
        store.close()

    client = TestClient(create_app(tmp_path))
    resp = client.get(f"/api/revisions/{rev2}/dossier")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers.get("content-type", "")
    assert "1x Birds of Paradise" in resp.text
