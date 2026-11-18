"""Tests for Phase B3 (E2): Tierliste Deck-Bedarf / Role-Gap view and /api/cohorts contract."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio.web import STATIC, create_app


def test_tierliste_js_renders_role_gaps_and_filter_chip() -> None:
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    for token in (
        "activeDeckRoleCounts",
        "openRoleGaps",
        "roleGapLine",
        "role-gap-line",
        "chip-role-gap",
        "Schließt offenen Deck-Bedarf",
        "Offener Bedarf (Deck vs. Korpus",
        "/api/cohorts?commander=",
    ):
        assert token in js, f"tierliste.js missing {token}"


def test_cohorts_endpoint_exposes_role_p25_p75_contract(tmp_path: Path) -> None:
    from tests.unit.studio_synth import add_card, add_deck, make_store

    store = make_store(tmp_path)
    try:
        add_card(
            store,
            "Chulane, Teller of Tales",
            type_line="Legendary Creature — Human Druid",
            identity="WUG",
        )
        c_id = add_card(store, "Llanowar Elves", type_line="Creature — Elf Druid", identity="G")
        o_row = store.connection.execute(
            "SELECT oracle_id FROM card WHERE card_id = ?", (c_id,)
        ).fetchone()
        if o_row and o_row[0]:
            store.connection.execute(
                "INSERT INTO card_role (oracle_id, role, role_origin) VALUES (?, 'ramp', 'SCRYFALL_TAGGER_ORIGINAL')",
                (o_row[0],),
            )
            store.connection.commit()
        add_deck(
            store,
            "d1",
            ["Llanowar Elves"],
            cohorts=["commander:chulane-teller-of-tales"],
        )
    finally:
        store.close()

    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    resp = client.get("/api/cohorts?commander=Chulane,%20Teller%20of%20Tales")
    assert resp.status_code == 200
    shapes = resp.json()
    assert isinstance(shapes, list) and shapes
    assert "decks_counted" in shapes[0]
