"""Regression tests for Issue #1307 and Studio follow-ups (#1277). Synthetic data only."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    RevisionCard,
    StudioStore,
    catalog,
    create_revision,
    import_all,
    queries,
    signals,
)
from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.web import STATIC, create_app

HEADERS = {"X-Studio": "1"}
COMMANDER_NAME = "Test Commander"
COMMANDER_ID = "card:test:0001"
FOREST_ID = "card:test:0002"
SRC_ID = "src:test"


def _seed_store(tmp_path: Path, *, num_fillers: int = 5) -> StudioStore:
    """Populate an isolated Studio DB with synthetic cards, scryfall data, and inventory."""
    store = StudioStore.open(tmp_path / "studio")
    with store.connection as db:
        db.execute(
            "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
            "VALUES (?, 'ORIGINAL_SOURCE', 'Test Source', 'deadbeef', '2026-11-14T00:00:00Z')",
            (SRC_ID,),
        )
        cards = [
            (
                COMMANDER_ID,
                COMMANDER_NAME,
                "Legendary Creature — Human Druid",
                2.0,
                "G,U,W",
                "oracle-cmd",
                0,
            ),
            (
                FOREST_ID,
                "Forest",
                "Basic Land — Forest",
                0.0,
                "G",
                "oracle-forest",
                1,
            ),
        ]
        for i in range(1, num_fillers + 1):
            cards.append(
                (
                    f"card:test:{100 + i:04d}",
                    f"Filler {i:02d}",
                    "Creature — Elf",
                    2.0,
                    "G",
                    f"oracle-filler-{i:02d}",
                    0,
                )
            )
        for cid, oname, tline, mv, ci, oid, is_basic in cards:
            db.execute(
                "INSERT INTO card("
                "card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value, "
                "type_line, oracle_text, is_basic_land, commander_legal, source_id"
                ") VALUES (?, ?, ?, ?, '{1}{G}', ?, ?, '', ?, 1, ?)",
                (cid, oid, oname, ci, mv, tline, is_basic, SRC_ID),
            )
            db.execute(
                "INSERT INTO scryfall_card("
                "oracle_id, scryfall_id, name, front_name, layout, mana_cost, mana_value, "
                "type_line, oracle_text, color_identity, commander_legality, keywords, "
                "produced_mana, source_id"
                ") VALUES (?, ?, ?, ?, 'normal', '{1}{G}', ?, ?, '', ?, 'legal', '[]', '[]', ?)",
                (oid, f"scry-{cid}", oname, oname, mv, tline, ci, SRC_ID),
            )
            db.execute(
                "INSERT INTO inventory("
                "card_id, observed, owned_lower_bound, reserved, available_lower_bound, "
                "quantity_exact, lots, source_id"
                ") VALUES (?, 10, 10, 0, 10, 1, 1, ?)",
                (cid, SRC_ID),
            )
    return store


def _create_test_deck(
    store: StudioStore, *, deck_id: str = "test-deck", branch: str = "main"
) -> str:
    cards = [RevisionCard(COMMANDER_ID, 1, "commander"), RevisionCard(FOREST_ID, 6, "main")]
    cards.extend(RevisionCard(f"card:test:{101 + i:04d}", 1, "main") for i in range(3))
    return create_revision(store, deck_id=deck_id, branch=branch, name="Test Deck", cards=cards)


def test_counted_sections_exclude_sideboard_maybeboard_and_cuts(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)
    try:
        with store.connection as db:
            for idx in range(1, 5):
                db.execute(
                    "INSERT INTO corpus_deck("
                    "deck_id, cohort, url, platform, play_group, tags, fingerprint, "
                    "legality_audit, source_id"
                    ") VALUES (?, 'coh', ?, 'moxfield', '', '[]', ?, 'LEGAL', ?)",
                    (f"deck-{idx}", f"https://example.invalid/{idx}", f"fp-{idx}", SRC_ID),
                )
            db.execute(
                "INSERT INTO commander_binding(kind, key, commander_name, basis) "
                "SELECT 'corpus_deck', deck_id, ?, 'SYNTHETIC' FROM corpus_deck",
                (COMMANDER_NAME,),
            )
            db.execute(
                "INSERT INTO corpus_deck_card("
                "deck_id, card_name, oracle_id, quantity, section, normalization_status"
                ") VALUES "
                "('deck-1', 'Filler 01', 'oracle-filler-01', 1, 'mainboard', 'EXACT'),"
                "('deck-2', 'Filler 01', 'oracle-filler-01', 1, 'commander', 'EXACT'),"
                "('deck-3', 'Filler 01', 'oracle-filler-01', 1, 'maybeboard', 'EXACT'),"
                "('deck-4', 'Filler 01', 'oracle-filler-01', 1, 'cuts', 'EXACT')"
            )
            db.execute(
                "INSERT INTO corpus_deck_card("
                "deck_id, card_name, oracle_id, quantity, section, normalization_status"
                ") VALUES "
                "('deck-1', 'Forest', 'oracle-forest', 1, 'mainboard', 'EXACT'),"
                "('deck-2', 'Forest', 'oracle-forest', 1, 'sideboard', 'EXACT'),"
                "('deck-3', 'Forest', 'oracle-forest', 1, 'considering', 'EXACT')"
            )

        res = catalog.refresh_corpus_stats(store)
        assert res["corpus_decks_with_stats"] == 2
        row1 = store.connection.execute(
            "SELECT cards FROM corpus_deck_stat WHERE deck_id = 'deck-1'"
        ).fetchone()
        row2 = store.connection.execute(
            "SELECT cards FROM corpus_deck_stat WHERE deck_id = 'deck-2'"
        ).fetchone()
        assert row1 is not None and int(row1["cards"]) == 2
        assert row2 is not None and int(row2["cards"]) == 1

        inc = queries.corpus_inclusion(store, "Filler 01", commander_names=[COMMANDER_NAME])
        assert inc["hits"] == 2
        assert inc["denominator"] == 4
    finally:
        store.close()


def test_import_all_completeness_excludes_commander_for_commander_layers(tmp_path: Path) -> None:
    store = _seed_store(tmp_path, num_fillers=4)
    try:
        with store.connection as db:
            db.execute(
                "INSERT INTO corpus_deck("
                "deck_id, cohort, url, platform, play_group, tags, fingerprint, "
                "legality_audit, source_id"
                ") VALUES ('d1', 'coh', 'https://example.invalid/d1', 'moxfield', '', '[]', "
                "'fp-d1', 'LEGAL', ?)",
                (SRC_ID,),
            )
            db.execute(
                "INSERT INTO commander_binding(kind, key, commander_name, basis) "
                "VALUES ('corpus_deck', 'd1', ?, 'SYNTHETIC')",
                (COMMANDER_NAME,),
            )
            for idx in (1, 2):
                db.execute(
                    "INSERT INTO corpus_deck_card("
                    "deck_id, card_name, oracle_id, quantity, section, normalization_status"
                    ") VALUES ('d1', ?, ?, 1, 'mainboard', 'EXACT')",
                    (f"Filler {idx:02d}", f"oracle-filler-{idx:02d}"),
                )
            db.execute(
                "INSERT INTO card_signal(commander_name, signal, card_name, value, source_id) "
                "VALUES "
                "(?, ?, ?, 0.99, ?),"
                "(?, ?, 'Filler 01', 0.5, ?),"
                "('', ?, ?, 1.2, ?),"
                "('', ?, 'Filler 01', 0.8, ?)",
                (
                    COMMANDER_NAME,
                    signals.SIGNAL_INCLUSION,
                    COMMANDER_NAME,
                    SRC_ID,
                    COMMANDER_NAME,
                    signals.SIGNAL_INCLUSION,
                    SRC_ID,
                    signals.SIGNAL_SALT,
                    COMMANDER_NAME,
                    SRC_ID,
                    signals.SIGNAL_SALT,
                    SRC_ID,
                ),
            )
            db.execute(
                "INSERT INTO observation("
                "card_id, card_name, metric, cohort, value, numerator, denominator, "
                "data_class, source_id"
                ") VALUES "
                "(?, ?, 'm', 'coh', 0.5, 1, 2, 'OBSERVED', ?),"
                "('card:test:0101', 'Filler 01', 'm', 'coh', 0.5, 1, 2, 'OBSERVED', ?)",
                (COMMANDER_ID, COMMANDER_NAME, SRC_ID, SRC_ID),
            )
            db.execute(
                "INSERT INTO commander_binding(kind, key, commander_name, basis) "
                "VALUES ('observation_cohort', 'coh', ?, 'SYNTHETIC')",
                (COMMANDER_NAME,),
            )

        pool_size, layers = import_all.completeness(store, COMMANDER_NAME)
        assert pool_size == 6
        by_key = {item["key"]: item for item in layers}
        assert by_key["scryfall"]["pool"] == 6
        assert by_key[signals.SIGNAL_SALT]["pool"] == 6
        assert by_key[signals.SIGNAL_SALT]["covered"] == 2
        assert by_key["observations"]["pool"] == 5
        assert by_key["observations"]["covered"] == 1
        assert by_key["decklists"]["pool"] == 5
        assert by_key["decklists"]["covered"] == 2
        sig_top = by_key[f"signal:{signals.SIGNAL_INCLUSION}"]
        assert sig_top["pool"] == 5
        assert sig_top["covered"] == 1
    finally:
        store.close()


def test_import_all_writes_failure_report_on_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "studio"
    # Missing --inventory / --from-repo triggers ValueError -> SystemExit + failure report
    with pytest.raises(SystemExit):
        studio_main(["--data", str(data_dir), "import-all", "--commander", COMMANDER_NAME])
    err = capsys.readouterr().err
    reports = list(data_dir.glob("import-all-fehlerbericht-*.txt"))
    assert len(reports) == 1
    assert "Fehlerbericht gespeichert:" in err
    text = reports[0].read_text(encoding="utf-8")
    assert COMMANDER_NAME in text and "Ursache:" in text


def test_draft_optimistic_concurrency_returns_409_on_stale_write(tmp_path: Path) -> None:
    data_dir = tmp_path / "studio"
    store = _seed_store(tmp_path)
    rev1 = _create_test_deck(store)
    store.close()

    client = TestClient(create_app(data_dir))
    r1 = client.put(
        "/api/decks/test-deck/branches/main/draft",
        json={
            "cards": [{"card_id": COMMANDER_ID, "quantity": 1, "zone": "commander"}],
            "base_revision_id": rev1,
        },
        headers=HEADERS,
    )
    assert r1.status_code == 200
    ts1 = r1.json()["updated_at"]
    assert isinstance(ts1, str) and ts1

    # Another tab changes a card via /draft/card (even within the same second)
    r_card = client.post(
        "/api/decks/test-deck/branches/main/draft/card",
        json={"card_id": "card:test:0104", "delta": 1},
        headers=HEADERS,
    )
    assert r_card.status_code == 200

    # Stale tab sends PUT with expected_updated_at=ts1 and check_conflict=True -> 409
    r_conflict = client.put(
        "/api/decks/test-deck/branches/main/draft",
        json={
            "cards": [{"card_id": COMMANDER_ID, "quantity": 1, "zone": "commander"}],
            "base_revision_id": rev1,
            "expected_updated_at": ts1,
            "expected_base_revision_id": rev1,
            "check_conflict": True,
        },
        headers=HEADERS,
    )
    assert r_conflict.status_code == 409

    # Reading latest draft gives updated stamp; sending that stamp succeeds
    latest = client.get("/api/decks/test-deck/branches/main/draft").json()["draft"]
    assert latest["updated_at"] > ts1
    r_ok = client.put(
        "/api/decks/test-deck/branches/main/draft",
        json={
            "cards": [{"card_id": COMMANDER_ID, "quantity": 1, "zone": "commander"}],
            "base_revision_id": rev1,
            "expected_updated_at": latest["updated_at"],
            "expected_base_revision_id": rev1,
            "check_conflict": True,
        },
        headers=HEADERS,
    )
    assert r_ok.status_code == 200


def test_slash_in_branch_and_profile_names_supported_end_to_end(tmp_path: Path) -> None:
    data_dir = tmp_path / "studio"
    store = _seed_store(tmp_path)
    rev = _create_test_deck(store, deck_id="test-deck", branch="ideeen/ramp")
    store.close()

    client = TestClient(create_app(data_dir))

    # Branch with "/" in draft GET, PUT, POST /draft/card, DELETE
    r_put = client.put(
        "/api/decks/test-deck/branches/ideeen%2Framp/draft",
        json={
            "cards": [{"card_id": COMMANDER_ID, "quantity": 1, "zone": "commander"}],
            "base_revision_id": rev,
        },
        headers=HEADERS,
    )
    assert r_put.status_code == 200
    r_get = client.get("/api/decks/test-deck/branches/ideeen%2Framp/draft")
    assert r_get.status_code == 200 and r_get.json()["draft"] is not None
    r_card = client.post(
        "/api/decks/test-deck/branches/ideeen%2Framp/draft/card",
        json={"card_id": "card:test:0104", "delta": 1},
        headers=HEADERS,
    )
    assert r_card.status_code == 200 and r_card.json()["quantity"] == 1
    r_del = client.delete("/api/decks/test-deck/branches/ideeen%2Framp/draft", headers=HEADERS)
    assert r_del.status_code == 200

    # Branch longer than 60 chars still rejected (422)
    too_long = "a" * 61
    assert client.get(f"/api/decks/test-deck/branches/{too_long}/draft").status_code == 422

    # Strength profile with "/" in PUT / GET / DELETE
    presets = client.get("/api/strength/presets").json()
    settings = presets["recommended"]
    sp_put = client.put(
        "/api/strength/profiles/turnier%2Fbudget",
        json={"settings": settings},
        headers=HEADERS,
    )
    assert sp_put.status_code == 200
    sp_get = client.get("/api/strength/profiles/turnier%2Fbudget")
    assert sp_get.status_code == 200 and sp_get.json()["name"] == "turnier/budget"
    sp_del = client.delete("/api/strength/profiles/turnier%2Fbudget", headers=HEADERS)
    assert sp_del.status_code == 200 and sp_del.json() == {"deleted": "turnier/budget"}

    # Universe profile with "/" in PUT / GET .../summary / DELETE
    up_put = client.put(
        f"/api/universe/profiles/cedh%2F2026?commander={COMMANDER_NAME}",
        json={},
        headers=HEADERS,
    )
    assert up_put.status_code == 200 and up_put.json()["profile"] == "cedh/2026"
    up_sum = client.get(f"/api/universe/profiles/cedh%2F2026/summary?commander={COMMANDER_NAME}")
    assert up_sum.status_code == 200 and up_sum.json()["profile"] == "cedh/2026"
    up_del = client.delete("/api/universe/profiles/cedh%2F2026", headers=HEADERS)
    assert up_del.status_code == 200 and up_del.json() == {"deleted": "cedh/2026"}


def test_tierliste_and_builder_ui_contracts_for_issue_1307() -> None:
    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    tier_js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")

    # tierliste.js uses /api/marks instead of /api/pool in init()
    assert 'api("/api/marks")' in tier_js
    assert "/api/pool?" not in tier_js
    assert 'apiView === "commander"' in tier_js

    # tierliste.js shows German empty universe badge, level_name, deck summary, bodyless DELETE
    assert 'id: "universe-empty"' in tier_js
    assert "UNIVERSE_EMPTY" in tier_js and "NO_SOURCE_DECKS_FOR_COMMANDER" in tier_js
    assert "item.level_name || item.level" in tier_js
    assert "im Deck von ${summary.cards} legalen Karten." in tier_js
    assert "Gespeicherte Einstellung „${p.name}“ geladen und berechnet" in tier_js
    assert (
        'api(`/api/strength/profiles/${encodeURIComponent(name)}`, undefined, "DELETE")' in tier_js
    )
    assert (
        'api(`/api/universe/profiles/${encodeURIComponent(name)}`, undefined, "DELETE")' in tier_js
    )

    # tierliste.html uses German spread names
    for expected in (
        "Verbreitung: sehr häufig (S)",
        "Verbreitung: häufig (A)",
        "Verbreitung: gelegentlich (B)",
        "Verbreitung: selten (C)",
        "Verbreitung: sehr selten (D)",
        "Verbreitung: unbekannt (U)",
        "Verbreitung: Filterkarten",
    ):
        assert expected in html

    # app.js sends optimistic concurrency check and surfaces 409 conflict without inline styles
    assert "check_conflict: true" in app_js
    assert "error.status === 409" in app_js
    assert "if (state.changeSeq === seq) state.needsDraftPut = false;" in app_js
    assert "Aktuellen Stand laden" in app_js
    assert "draftConflict" in app_js
    assert "style=" not in app_js and "style=" not in tier_js
