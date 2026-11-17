"""Unit tests for similar source decks (#1404 Proposal 3/5/10) and Deck-Browser (#1323)."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import (
    RevisionCard,
    StudioStore,
    builder,
    create_revision,
    labels,
)
from commander_lab.studio.similar_decks import find_similar_decks
from commander_lab.studio.web import create_app

COMMANDER = "Test Commander"
STATIC_DIR = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def _seed_store(tmp_path: Path, num_source_decks: int = 30) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    source_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        # Clear default corpus_deck tables from _fill so we have a clean synthetic corpus
        db.execute("DELETE FROM corpus_deck_role")
        db.execute("DELETE FROM corpus_deck_stat")
        db.execute("DELETE FROM corpus_deck_part")
        db.execute("DELETE FROM corpus_cohort")
        db.execute("DELETE FROM corpus_deck_card")
        db.execute("DELETE FROM commander_binding WHERE kind = 'corpus_deck'")
        db.execute("DELETE FROM corpus_deck")

        # Add 15 explicit pool cards (p_01 .. p_15) in card + inventory + card_role
        for i in range(1, 16):
            cid = f"p_{i:02d}"
            oid = f"oid_{i:02d}"
            name = f"Pool Card {i:02d}"
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, 'G', '{1}{G}', 2.0, 'Creature — Elf', '', 0, 1, '2026-11-15', 'scryfall', ?)",
                (cid, oid, name, source_id),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 2, 0, 2, 1, 1, '2026-11-15', ?)",
                (cid, source_id),
            )
            db.execute(
                "INSERT INTO card_role VALUES (?, ?, ?)",
                (oid, "ramp" if i <= 8 else "card_draw", source_id),
            )

        # Insert synthetic source decks sd_0001 .. sd_{num_source_decks:04d}
        deck_rows = []
        card_rows = []
        binding_rows = []
        for d_idx in range(1, num_source_decks + 1):
            did = f"sd_{d_idx:04d}"
            cohort = "bracket:4" if d_idx % 2 == 1 else "bracket:3"
            deck_rows.append(
                (
                    did,
                    cohort,
                    f"https://example.org/decks/{did}",
                    "moxfield",
                    "tuned",
                    "2026-11-01",
                    "Landfall",
                    f"fp_{did}",
                    None,
                    "ok",
                    source_id,
                )
            )
            binding_rows.append(("corpus_deck", did, COMMANDER, "test"))
            # Every source deck has Test Commander (commander) and Forest (basic land)
            card_rows.append((did, COMMANDER, "oracle-test-commander", 1, "commander", "exact"))
            card_rows.append((did, "Forest", "oracle-forest", 30, "main", "exact"))
            if d_idx <= 30:
                # Decks 1 and 2 share 10/10 with user deck (Pool Card 01..10) + 2 extra pool cards + 1 unowned card
                shared_k = max(1, 11 - ((d_idx + 1) // 2))
                for c_i in range(1, shared_k + 1):
                    card_rows.append(
                        (did, f"Pool Card {c_i:02d}", f"oid_{c_i:02d}", 1, "main", "exact")
                    )
                card_rows.append((did, "Pool Card 11", "oid_11", 1, "main", "exact"))
                card_rows.append((did, "Pool Card 12", "oid_12", 1, "main", "exact"))
                card_rows.append((did, "Unowned Secret Tech", "oid_unowned", 1, "main", "exact"))
            else:
                base = (d_idx % 10) + 1
                for offset in range(6):
                    c_i = ((base + offset - 1) % 15) + 1
                    card_rows.append(
                        (did, f"Pool Card {c_i:02d}", f"oid_{c_i:02d}", 1, "main", "exact")
                    )

        # Also insert 1 duplicate deck that MUST be ignored
        deck_rows.append(
            (
                "sd_dup",
                "bracket:4",
                "https://example.org/decks/dup",
                "moxfield",
                "tuned",
                "2026-11-01",
                "",
                "fp_sd_0001",
                "sd_0001",
                "ok",
                source_id,
            )
        )
        binding_rows.append(("corpus_deck", "sd_dup", COMMANDER, "test"))
        card_rows.append(("sd_dup", COMMANDER, "oracle-test-commander", 1, "commander", "exact"))
        card_rows.append(("sd_dup", "Pool Card 01", "oid_01", 1, "main", "exact"))

        db.executemany(
            "INSERT INTO corpus_deck VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            deck_rows,
        )
        db.executemany(
            "INSERT INTO commander_binding VALUES (?, ?, ?, ?)",
            binding_rows,
        )
        db.executemany(
            "INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, ?)",
            card_rows,
        )

    # Create a saved Studio deck with archetype label "Landfall"
    pool_payload = builder.pool_cards(store, [COMMANDER])
    cmd_id = str(pool_payload["commander_ids"][0])
    forest_id = next(str(c["card_id"]) for c in pool_payload["cards"] if c["name"] == "Forest")
    rev_cards = [
        RevisionCard(cmd_id, 1, "commander"),
        RevisionCard(forest_id, 12, "main"),
        *[RevisionCard(f"p_{i:02d}", 1, "main") for i in range(1, 11)],
    ]
    create_revision(
        store,
        deck_id="d_user",
        name="Mein Test Deck",
        cards=rev_cards,
        branch="main",
    )
    labels.set_deck_labels(store, "d_user", ["Landfall"])
    return store


def test_find_similar_decks_exact_jaccard_and_tie_break(tmp_path: Path) -> None:
    store = _seed_store(tmp_path, num_source_decks=30)
    pool_payload = builder.pool_cards(store, [COMMANDER])
    cmd_id = str(pool_payload["commander_ids"][0])
    forest_id = next(str(c["card_id"]) for c in pool_payload["cards"] if c["name"] == "Forest")
    user_card_ids = [cmd_id, forest_id] + [f"p_{i:02d}" for i in range(1, 11)]

    res = find_similar_decks(
        store,
        [COMMANDER],
        deck_card_ids=user_card_ids,
        cohort="all",
        n=10,
        include_unowned=False,
    )

    # Duplicate deck sd_dup excluded -> 30 source decks total
    assert res["decks_considered"] == 30
    assert res["user_nonbasic_cards"] == 10  # basic lands and commander excluded
    assert res["empty_reason"] is None

    top = res["nearest"]
    assert len(top) == 10
    # sd_0001 and sd_0002 both share all 10 user cards + 3 extra cards (Pool Card 11, 12, Unowned Secret Tech)
    # Union = 13, Shared = 10 -> Jaccard = 10/13 = 0.7692; tie broken by deck_id ASC
    assert top[0]["deck_id"] == "sd_0001"
    assert top[1]["deck_id"] == "sd_0002"
    assert top[0]["shared"] == 10
    assert top[0]["size"] == 13
    assert top[0]["similarity"] == round(10 / 13, 4)

    # By default include_unowned=False: "Unowned Secret Tech" must NOT be in they_play_you_dont
    they_names = [row["name"] for row in res["they_play_you_dont"]]
    assert "Pool Card 11" in they_names
    assert "Pool Card 12" in they_names
    assert "Unowned Secret Tech" not in they_names

    # Now enable include_unowned=True -> "Unowned Secret Tech" is surfaced with in_pool=False
    res_unowned = find_similar_decks(
        store,
        [COMMANDER],
        deck_card_ids=user_card_ids,
        cohort="all",
        n=10,
        include_unowned=True,
    )
    unowned_rows = [
        row for row in res_unowned["they_play_you_dont"] if row["name"] == "Unowned Secret Tech"
    ]
    assert len(unowned_rows) == 1
    assert unowned_rows[0]["in_pool"] is False
    assert unowned_rows[0]["hits"] == 10
    assert unowned_rows[0]["of"] == 10


def test_find_similar_decks_empty_cohort_reason(tmp_path: Path) -> None:
    store = _seed_store(tmp_path, num_source_decks=10)
    res = find_similar_decks(
        store,
        [COMMANDER],
        deck_card_ids=["p_01", "p_02"],
        cohort="bracket:2",
        n=10,
    )
    assert res["decks_considered"] == 0
    assert res["nearest"] == []
    assert res["empty_reason"] is not None
    assert "bracket:2" in str(res["empty_reason"])


def test_find_similar_decks_performance_3000_decks(tmp_path: Path) -> None:
    store = _seed_store(tmp_path, num_source_decks=3000)
    user_card_ids = [f"p_{i:02d}" for i in range(1, 11)]
    # Warm up index once, or even cold start must be < 2.0s
    t0 = time.perf_counter()
    res = find_similar_decks(
        store,
        [COMMANDER],
        deck_card_ids=user_card_ids,
        cohort="all",
        n=20,
    )
    elapsed = time.perf_counter() - t0
    assert res["decks_considered"] == 3000
    assert len(res["nearest"]) == 20
    assert elapsed < 2.0, f"Expected < 2.0s for 3,000 source decks, took {elapsed:.3f}s"


def test_deck_browser_filters_cooccurrence_and_detail_api(tmp_path: Path) -> None:
    _seed_store(tmp_path, num_source_decks=20)
    app = create_app(tmp_path / "studio")
    client = TestClient(app)

    # 1. GET /api/similar-decks via saved deck_id
    r_sim = client.get(
        "/api/similar-decks",
        params={"commander": COMMANDER, "deck_id": "d_user", "n": 5},
    )
    assert r_sim.status_code == 200
    sim_data = r_sim.json()
    assert sim_data["decks_considered"] == 20
    assert len(sim_data["nearest"]) == 5
    assert sim_data["nearest"][0]["deck_id"] == "sd_0001"

    # 2. GET /api/deck-browser with must_contain and must_not_contain
    # Pool Card 10 is only in sd_0001 and sd_0002 (and saved deck d_user)
    r_browse = client.get(
        "/api/deck-browser",
        params={
            "commander": COMMANDER,
            "origin": "all",
            "must_contain": ["Pool Card 10"],
        },
    )
    assert r_browse.status_code == 200
    b_data = r_browse.json()
    assert b_data["total_decks"] == 3
    co_map = {row["name"]: row for row in b_data["cooccurrence"]}
    assert "Pool Card 10" not in co_map  # filter card is not listed in co-occurrence
    assert co_map["Pool Card 01"]["decks"] == 3
    assert co_map["Pool Card 01"]["of"] == 3
    assert co_map["Pool Card 01"]["share"] == 1.0
    assert "Unowned Secret Tech" not in co_map  # hidden by default

    # Exclude Pool Card 11 (which is in sd_0001 and sd_0002, but NOT in saved deck d_user)
    r_excl = client.get(
        "/api/deck-browser",
        params={
            "commander": COMMANDER,
            "origin": "all",
            "must_contain": ["Pool Card 10"],
            "must_not_contain": ["Pool Card 11"],
        },
    )
    assert r_excl.status_code == 200
    excl_data = r_excl.json()
    assert excl_data["total_decks"] == 1
    assert excl_data["decks"][0]["id"] == "saved:d_user:main"

    # Filter by archetype label "Landfall" on saved decks -> saved:d_user:main matches
    r_label = client.get(
        "/api/deck-browser",
        params={"commander": COMMANDER, "origin": "saved", "label": "Landfall"},
    )
    assert r_label.status_code == 200
    assert r_label.json()["total_decks"] == 1
    assert r_label.json()["decks"][0]["id"] == "saved:d_user:main"

    # 3. GET /api/deck-browser/{item_id} read-only inspection
    r_det_saved = client.get("/api/deck-browser/saved:d_user:main")
    assert r_det_saved.status_code == 200
    assert r_det_saved.json()["origin"] == "saved"
    assert len(r_det_saved.json()["cards"]) >= 10

    r_det_src = client.get("/api/deck-browser/source:sd_0001")
    assert r_det_src.status_code == 200
    src_json = r_det_src.json()
    assert src_json["origin"] == "source"
    assert any(
        c["name"] == "Unowned Secret Tech" and not c["in_collection"] for c in src_json["cards"]
    )


def test_static_deck_browser_and_app_js_hygiene() -> None:
    decks_html = (STATIC_DIR / "decks.html").read_text(encoding="utf-8")
    decks_js = (STATIC_DIR / "decks.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "style=" not in decks_html
    assert "style=" not in decks_js
    assert "innerHTML" not in decks_js
    assert "innerHTML" not in app_js

    for page in ("index.html", "tierliste.html", "partie.html", "decks.html"):
        html = (STATIC_DIR / page).read_text(encoding="utf-8")
        assert 'href="decks.html"' in html
        assert "Deck-Browser" in html

    assert "renderSimilarDecks" in app_js
    assert "renderDeckStatusBox" in app_js
    assert "deck-status-box" in app_js
    assert "similar-decks-table" in app_js
    assert "similar-they-play" in app_js
    assert "similar-you-play" in app_js
    assert "similar-include-unowned" in app_js


def test_canonical_name_is_none_for_a_front_face_shared_by_several_cards() -> None:
    from commander_lab.studio.similar_decks import _canonical_name

    owners = {
        "fire": ["Fire // Ice", "Fire // Ruin"],
        "wear": ["Wear // Tear"],
        "fire // ice": ["Fire // Ice"],
    }
    assert _canonical_name(owners, "Fire") is None
    assert _canonical_name(owners, "Fire // Ice") == "Fire // Ice"
    assert _canonical_name(owners, "Wear") == "Wear // Tear"
    assert _canonical_name(owners, "Unlisted Card") == "Unlisted Card"
