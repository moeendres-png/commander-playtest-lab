"""Unit tests for the Studio role-matched swap helper (Proposal 2), decklist parser
(Proposal 7 / D5), role coverage median (Proposal 4 / D2), and German deck validation (D7)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, builder, swap
from commander_lab.studio.web import create_app


def _seed_swap_store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        # Add 4 cards across 2 roles ('removal' and 'card_draw') + 1 card with unknown frequency:
        # Removal cards:
        # - 'rem-high': Swords to Plowshares (in d1, d2, d3 -> 3/3, available in pool)
        # - 'rem-mid': Path to Exile (in d1, d2 -> 2/3, available in pool)
        # - 'rem-low': Shattered Acolyte (in d1 -> 1/3, in deck)
        # - 'rem-unk': Obscure Purge (not in corpus_deck_card -> decks_known is False, available in pool)
        # Card draw card:
        # - 'draw-high': Harmonize (in d1, d2, d3 -> 3/3, role 'card_draw' only)
        cards = [
            ("rem-high", "Swords to Plowshares", "oid-rem-high", "removal"),
            ("rem-mid", "Path to Exile", "oid-rem-mid", "removal"),
            ("rem-low", "Shattered Acolyte", "oid-rem-low", "removal"),
            ("rem-unk", "Obscure Purge", "oid-rem-unk", "removal"),
            ("draw-high", "Harmonize", "oid-draw-high", "card_draw"),
        ]
        for cid, name, oid, role in cards:
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, 'G', '{1}{G}', 2, 'Instant', '', 0, 1, '2026-11-15', 'scryfall', ?)",
                (cid, oid, name, source_id),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 1, 0, 1, 1, 1, '2026-11-15', ?)",
                (cid, source_id),
            )
            db.execute(
                "INSERT INTO card_role VALUES (?, ?, ?)",
                (oid, role, source_id),
            )

        for did in ("d1", "d2", "d3"):
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, 'Swords to Plowshares', 'oid-rem-high', 1, 'main', 'exact')",
                (did,),
            )
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, 'Harmonize', 'oid-draw-high', 1, 'main', 'exact')",
                (did,),
            )
        for did in ("d1", "d2"):
            db.execute(
                "INSERT INTO corpus_deck_card VALUES (?, 'Path to Exile', 'oid-rem-mid', 1, 'main', 'exact')",
                (did,),
            )
        db.execute(
            "INSERT INTO corpus_deck_card VALUES ('d1', 'Shattered Acolyte', 'oid-rem-low', 1, 'main', 'exact')"
        )
    return store


def test_swap_replace_and_cut_exact_order_and_marks_invariance(tmp_path: Path) -> None:
    store = _seed_swap_store(tmp_path)
    pool_payload = builder.pool_cards(store, ["Test Commander"])
    pool_of = pool_payload["cohorts"]["all"]
    cmd_id = str(pool_payload["commander_ids"][0])
    forest_id = next(str(c["card_id"]) for c in pool_payload["cards"] if c["name"] == "Forest")

    # Deck currently plays Shattered Acolyte (1/3), Path to Exile (2/3), Harmonize (3/3), Forest, and Test Commander
    deck_ids = [cmd_id, forest_id, "rem-low", "rem-mid", "draw-high"]

    # 1. Mode 'replace' for Shattered Acolyte ('rem-low'):
    # Only free pool cards with role 'removal' NOT in deck -> 'rem-high' (3/3) and 'rem-unk' (unknown, sorted last).
    # 'draw-high' has role 'card_draw' and is excluded; 'rem-mid' is already in deck.
    rep = swap.swap_candidates(
        store,
        commander="Test Commander",
        deck_card_ids=deck_ids,
        card_id="rem-low",
        mode="replace",
        cohort="all",
    )
    assert rep["of"] == pool_of == 3
    assert rep["roles"] == ["removal"]
    assert [c["card_id"] for c in rep["candidates"]] == ["rem-high", "rem-unk"]
    assert rep["candidates"][0]["decks"] == 3 and rep["candidates"][0]["of"] == 3
    assert rep["candidates"][1]["decks_known"] is False and rep["candidates"][1]["decks"] is None
    assert rep["unknown_count"] == 1

    # 2. Mode 'cut' when considering adding 'rem-high' to deck:
    # Only cards IN deck with role 'removal' -> 'rem-low' (1/3) first, then 'rem-mid' (2/3).
    # Commander, basic land ('Forest'), and different role ('draw-high') never appear.
    cut_res = swap.swap_candidates(
        store,
        commander="Test Commander",
        deck_card_ids=deck_ids,
        card_id="rem-high",
        mode="cut",
        cohort="all",
    )
    assert cut_res["of"] == pool_of == 3
    assert [c["card_id"] for c in cut_res["candidates"]] == ["rem-low", "rem-mid"]
    for cand in cut_res["candidates"]:
        assert cand["card_id"] not in (cmd_id, forest_id, "draw-high")

    # 3. User marks (favorite, note) never alter candidate order; excluded only filters 'replace' when exclude_marked=True
    builder.set_mark(store, "rem-unk", favorite=True, excluded=False, note="love it")
    builder.set_mark(store, "rem-mid", favorite=True, excluded=False, note="keep")
    rep_after_fav = swap.swap_candidates(
        store,
        commander="Test Commander",
        deck_card_ids=deck_ids,
        card_id="rem-low",
        mode="replace",
        cohort="all",
    )
    assert [c["card_id"] for c in rep_after_fav["candidates"]] == ["rem-high", "rem-unk"]

    cut_after_fav = swap.swap_candidates(
        store,
        commander="Test Commander",
        deck_card_ids=deck_ids,
        card_id="rem-high",
        mode="cut",
        cohort="all",
    )
    assert [c["card_id"] for c in cut_after_fav["candidates"]] == ["rem-low", "rem-mid"]

    builder.set_mark(store, "rem-high", favorite=False, excluded=True, note="")
    rep_excluded = swap.swap_candidates(
        store,
        commander="Test Commander",
        deck_card_ids=deck_ids,
        card_id="rem-low",
        mode="replace",
        cohort="all",
        exclude_marked=True,
    )
    assert [c["card_id"] for c in rep_excluded["candidates"]] == ["rem-unk"]


def test_swap_unknown_frequency_is_sorted_last_never_treated_as_rare(tmp_path: Path) -> None:
    store = _seed_swap_store(tmp_path)
    # In 'cut' mode, deck has 'rem-low' (1/3), 'rem-mid' (2/3), and 'rem-unk' (unknown / not in corpus_deck_card).
    # Unknown must NOT be first (never treated as 0 / rarely played); it must be sorted LAST!
    res = swap.swap_candidates(
        store,
        commander="Test Commander",
        deck_card_ids=["rem-low", "rem-mid", "rem-unk"],
        card_id="rem-high",
        mode="cut",
        cohort="all",
    )
    assert res["of"] == 3
    assert res["unknown_count"] == 1
    assert [c["card_id"] for c in res["candidates"]] == ["rem-low", "rem-mid", "rem-unk"]
    assert res["candidates"][-1]["decks_known"] is False
    assert res["candidates"][-1]["decks"] is None


def test_swap_and_decklist_parse_routes_and_german_validation(tmp_path: Path) -> None:
    store = _seed_swap_store(tmp_path)
    # Verify role_coverage_median in cohort_shapes (Proposal 4 / D2)
    shapes = {row["cohort"]: row for row in builder.cohort_shapes(store, ["Test Commander"])}
    assert "role_coverage_median" in shapes["all"]
    assert shapes["all"]["role_coverage_median"] is not None

    # Verify German validation message (D7)
    pool_payload = builder.pool_cards(store, ["Test Commander"])
    cmd_id = str(pool_payload["commander_ids"][0])

    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})

    created = client.post(
        "/api/decks", json={"name": "Chulane Test", "commander_card_ids": [cmd_id]}
    ).json()
    rev = client.get(f"/api/revisions/{created['revision_id']}").json()
    size_issues = [i for i in rev["issues"] if i["code"] == "deck_size"]
    assert size_issues and "ein Commander-Deck hat 100" in size_issues[0]["message"]

    resp = client.post(
        "/api/swap",
        json={
            "commander": "Test Commander",
            "deck_card_ids": [cmd_id, "rem-low", "rem-mid"],
            "card_id": "rem-low",
            "mode": "replace",
            "cohort": "all",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidates"][0]["name"] == "Swords to Plowshares"

    parse_resp = client.post(
        "/api/decklist-parse",
        json={
            "commander": "Test Commander",
            "text": "// Maindeck\n1x Swords to Plowshares (2X2) 31\n4 Forest\n1 Black Lotus\n",
        },
    )
    assert parse_resp.status_code == 200
    parsed = parse_resp.json()
    in_names = {row["name"]: row["quantity"] for row in parsed["in_collection"]}
    assert in_names == {"Swords to Plowshares": 1, "Forest": 4}
    missing_names = [row["name"] for row in parsed["not_in_collection"]]
    assert missing_names == ["Black Lotus"]
    raw_text = str(parsed).casefold()
    for forbidden in ("kaufen", "zukauf", "preis", "eur", "usd", "$", "€"):
        assert forbidden not in raw_text
