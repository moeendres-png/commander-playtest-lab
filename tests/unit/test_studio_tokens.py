"""Unit tests for local Scryfall-derived Token-Übersicht (#1450)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    catalog,
    create_revision,
    deck_evidence,
    strength,
    strength_view,
    tiers,
    tokens,
    universe,
)
from commander_lab.studio.decks import RevisionCard, list_rows
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill

COMMANDER = "Test Commander"
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def test_import_scryfall_oracle_extracts_tokens_and_all_parts_links(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        bulk_file = tmp_path / "tokens_slice.jsonl"
        records = [
            {
                "object": "card",
                "id": "scry-card-0100",
                "oracle_id": "oracle-0100",
                "name": "Filler 00",
                "layout": "normal",
                "mana_cost": "{2}{G}",
                "cmc": 3.0,
                "type_line": "Creature — Elf Druid",
                "oracle_text": "When Filler 00 enters, create a 3/3 green Beast creature token.",
                "color_identity": ["G"],
                "legalities": {"commander": "legal"},
                "keywords": [],
                "produced_mana": [],
                "power": "2",
                "toughness": "2",
                "games": ["paper"],
                "all_parts": [
                    {
                        "object": "related_card",
                        "id": "tok-beast-id",
                        "component": "token",
                        "name": "Beast",
                        "type_line": "Token Creature — Beast",
                        "uri": "https://api.scryfall.com/cards/tok-beast-id",
                    }
                ],
            },
            {
                "object": "card",
                "id": "scry-card-0101",
                "oracle_id": "oracle-0101",
                "name": "Filler 01",
                "layout": "normal",
                "mana_cost": "{3}{G}",
                "cmc": 4.0,
                "type_line": "Sorcery",
                "oracle_text": "Create two 3/3 green Beast creature tokens and a Treasure token.",
                "color_identity": ["G"],
                "legalities": {"commander": "legal"},
                "keywords": [],
                "produced_mana": [],
                "games": ["paper"],
                "all_parts": [
                    {
                        "object": "related_card",
                        "id": "tok-beast-other-printing",
                        "component": "token",
                        "name": "Beast",
                        "type_line": "Token Creature — Beast",
                    },
                    {
                        "object": "related_card",
                        "id": "tok-treasure-missing-row",
                        "component": "token",
                        "name": "Treasure",
                        "type_line": "Token Artifact — Treasure",
                    },
                ],
            },
            {
                "object": "card",
                "id": "scry-card-0102",
                "oracle_id": "oracle-0102",
                "name": "Filler 02",
                "layout": "normal",
                "mana_cost": "{1}{U}",
                "cmc": 2.0,
                "type_line": "Instant",
                "oracle_text": "Create a 1/1 blue Bird creature token with flying.",
                "color_identity": ["U"],
                "legalities": {"commander": "legal"},
                "keywords": [],
                "produced_mana": [],
                "games": ["paper"],
                # Intentionally omit all_parts to test UNKNOWN classification
            },
            {
                "object": "card",
                "id": "tok-beast-id",
                "oracle_id": "oracle-tok-beast",
                "name": "Beast",
                "layout": "token",
                "type_line": "Token Creature — Beast",
                "oracle_text": "",
                "power": "3",
                "toughness": "3",
                "colors": ["G"],
                "color_identity": ["G"],
                "image_uris": {"normal": "https://cards.scryfall.io/normal/front/b/beast.jpg"},
            },
        ]
        bulk_file.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

        report = catalog.import_scryfall_oracle(store, bulk_file)
        assert report["tokens"] == 1
        assert report["card_token_links"] == 3

        deck_cards = [
            RevisionCard("card:project:0001", 1, "commander"),
            RevisionCard("card:project:0100", 1, "main"),
            RevisionCard("card:project:0101", 1, "main"),
            RevisionCard("card:project:0102", 1, "main"),
        ]
        res = tokens.deck_tokens(store, deck_cards)
        assert res["schema"] == tokens.TOKEN_OVERVIEW_SCHEMA

        tok_list = res["tokens"]
        assert isinstance(tok_list, list)
        assert len(tok_list) == 2

        beast = next(t for t in tok_list if t["name"] == "Beast")  # type: ignore[index]
        assert beast["pt"] == "3/3"
        assert beast["colors"] == "G"
        assert beast["detail_status"] == "FULL"
        assert beast["creator_count"] == 2
        creator_names = [c["name"] for c in beast["creating_cards"]]  # type: ignore[index,union-attr]
        assert creator_names == ["Filler 00", "Filler 01"]

        treasure = next(t for t in tok_list if t["name"] == "Treasure")  # type: ignore[index]
        assert treasure["type_line"] == "Token Artifact — Treasure"
        assert treasure["detail_status"] == "PARTIAL_ALL_PARTS"
        assert treasure["creator_count"] == 1

        # Filler 02 mentions token creation in oracle_text without all_parts -> UNKNOWN
        unresolved = res["unresolved_creators"]
        assert isinstance(unresolved, list)
        unresolved_by_cid = {str(u["card_id"]): u for u in unresolved}  # type: ignore[index]
        assert "card:project:0102" in unresolved_by_cid
        u02 = unresolved_by_cid["card:project:0102"]
        assert u02["status"] == "UNKNOWN"
        assert u02["reason_code"] == "ORACLE_MENTIONS_TOKEN_WITHOUT_ALL_PARTS"

        counts = res["counts"]
        assert isinstance(counts, dict)
        assert counts["distinct_tokens"] == 2
        resolved_cnt = counts["resolved_creator_cards"]
        assert isinstance(resolved_cnt, dict)
        assert resolved_cnt["numerator"] == 2
        assert resolved_cnt["denominator"] == 2 + len(unresolved)
    finally:
        store.close()


def test_unlinked_card_without_oracle_text_is_marked_unknown(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        # Clear oracle_text and scryfall_card link for card:project:0105 so its token status is UNKNOWN
        with store.connection as db:
            db.execute(
                "UPDATE card SET oracle_id = NULL, oracle_text = NULL WHERE card_id = 'card:project:0105'"
            )
        res = tokens.deck_tokens(
            store,
            [
                RevisionCard("card:project:0001", 1, "commander"),
                RevisionCard("card:project:0105", 1, "main"),
            ],
        )
        unresolved = res["unresolved_creators"]
        assert isinstance(unresolved, list)
        u05 = next(u for u in unresolved if u["card_id"] == "card:project:0105")  # type: ignore[index]
        assert u05["status"] == "UNKNOWN"
        assert u05["reason_code"] == "NO_ORACLE_TEXT"
    finally:
        store.close()


def test_tokens_never_affect_tiers_strength_or_evidence(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        rev_id = create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)

        inc_before = universe.inclusion(store, commander_names=[COMMANDER])
        tiers_before = tiers.tiers_for_universe(
            inc_before, universe_snapshot="snap-1", params=tiers.TierParams()
        )
        strength_before = strength_view.compute(store, COMMANDER, strength.StrengthSettings())
        evidence_before = deck_evidence.deck_evidence(store, list_rows(store, full_cards))

        tokens.revision_tokens(store, rev_id)

        inc_after = universe.inclusion(store, commander_names=[COMMANDER])
        tiers_after = tiers.tiers_for_universe(
            inc_after, universe_snapshot="snap-1", params=tiers.TierParams()
        )
        assert tiers_after == tiers_before
        assert (
            strength_view.compute(store, COMMANDER, strength.StrengthSettings()) == strength_before
        )
        assert deck_evidence.deck_evidence(store, list_rows(store, full_cards)) == evidence_before
    finally:
        store.close()


def test_tokens_http_routes_and_static_ui_wiring(tmp_path: Path) -> None:
    studio_dir = tmp_path / "studio"
    store = StudioStore.open(studio_dir)
    try:
        _fill(store, tmp_path)
        full_cards = _deck()
        rev_id = create_revision(store, deck_id="chulane", name="Chulane", cards=full_cards)
    finally:
        store.close()

    client = TestClient(create_app(studio_dir))
    headers = {"X-Studio": "1"}

    post_resp = client.post(
        "/api/tokens",
        headers=headers,
        json={
            "cards": [
                {"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in full_cards
            ],
            "owned_only": True,
        },
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["schema"] == tokens.TOKEN_OVERVIEW_SCHEMA

    rev_resp = client.get(f"/api/revisions/{rev_id}/tokens", headers=headers)
    assert rev_resp.status_code == 200
    assert rev_resp.json()["revision_id"] == rev_id

    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert '["tokens", "Tokens"]' in app_js
    assert "renderTokens" in app_js
