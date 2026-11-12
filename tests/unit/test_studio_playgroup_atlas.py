"""Unit tests for Playgroup.gg Card Atlas parser and metrics extractor (#1192).

Governing mission:
- Verify exact extraction of live card statistics from Playgroup.gg HTML fixtures.
- Verify central integration test: Koma, Cosmos Serpent.
- Verify discrepancy detection: Koma, World-Eater (817 vs 821 brought; 53% vs 25/157 on-curve).
- Verify high-volume card: Sol Ring (all 7 turn buckets, 131k brought, narrow CI).
- Verify low-sample card: Esperzoa (n < 30, PARTIAL, insufficient sample flag).
- Verify slug normalization across diverse MTG card names (split, DFC, accents, punctuation).
- Verify error resilience (empty HTML, 404, missing sections).
"""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio.playgroup_parser import (
    PLAYGROUP_DISCLOSURE,
    parse_playgroup_card_html,
    to_playgroup_slug,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "playgroup"


def test_slug_normalization() -> None:
    """Verify card name to Playgroup slug conversion across diverse card names."""
    assert to_playgroup_slug("Koma, Cosmos Serpent") == "koma-cosmos-serpent"
    assert to_playgroup_slug("Koma, World-Eater") == "koma-world-eater"
    assert to_playgroup_slug("Sol Ring") == "sol-ring"
    assert to_playgroup_slug("Esperzoa") == "esperzoa"
    assert (
        to_playgroup_slug("Dread Linnorm // Scale Deflection") == "dread-linnorm-scale-deflection"
    )
    assert to_playgroup_slug("Drach'Nyen") == "drach-nyen"
    assert to_playgroup_slug("Séance") == "seance"
    assert to_playgroup_slug("Lim-Dûl's Vault") == "lim-dul-s-vault"
    assert to_playgroup_slug("Jace, the Mind Sculptor") == "jace-the-mind-sculptor"
    assert to_playgroup_slug("B.F.M. (Big Furry Monster)") == "b-f-m-big-furry-monster"


def test_parse_koma_cosmos_serpent_fixture() -> None:
    """Central integration test: Koma, Cosmos Serpent with complete live dataset."""
    html_path = FIXTURES_DIR / "koma-cosmos-serpent.html"
    assert html_path.is_file(), f"Fixture missing: {html_path}"
    html = html_path.read_text(encoding="utf-8")

    rec = parse_playgroup_card_html(
        html,
        slug="koma-cosmos-serpent",
        card_id="card:project:test-koma-uuid",
        oracle_id="6ba0656f-e0d2-4735-9c66-3a00afa9fc23",
        retrieved_at_utc="2026-11-11T16:00:00Z",
    )

    # 1. Identity & Context
    assert rec.card_name == "Koma, Cosmos Serpent"
    assert rec.slug == "koma-cosmos-serpent"
    assert rec.card_id == "card:project:test-koma-uuid"
    assert rec.oracle_id == "6ba0656f-e0d2-4735-9c66-3a00afa9fc23"
    assert rec.card_type == "Legendary Creature — Serpent"
    assert rec.format_mode == "multiplayer"
    assert rec.retrieved_at_utc == "2026-11-11T16:00:00Z"
    assert rec.disclosure == PLAYGROUP_DISCLOSURE

    # 2. JSON-LD
    assert rec.dataset_identifier == "6ba0656f-e0d2-4735-9c66-3a00afa9fc23"
    assert rec.license == "https://creativecommons.org/licenses/by/4.0/"

    # 3. Prevalence
    assert rec.live_inclusion_pct == 4.0
    assert rec.times_brought == 1319
    assert rec.decks_running == 499
    assert rec.median_cast_turn == 6.0
    assert rec.drawn_to_played_pct == 62.0

    # 4. First-cast tempo & 7 Turn buckets
    assert rec.first_cast_n == 320
    assert rec.turn_1_pct == 0.0
    assert rec.turn_2_pct == 1.0
    assert rec.turn_3_pct == 3.0
    assert rec.turn_4_pct == 10.0
    assert rec.turn_5_pct == 18.0
    assert rec.turn_6_to_9_pct == 58.0
    assert rec.turn_10_plus_pct == 11.0
    assert rec.p25_cast_turn == 5.0
    assert rec.p75_cast_turn == 8.0
    assert rec.max_cast_turn == 17.0

    # 5. On curve & same turn
    assert rec.on_curve_pct == 68.0
    assert rec.on_curve_count == 51
    assert rec.on_curve_denominator == 320
    assert rec.on_curve_turn == "T7"
    assert rec.cast_same_turn_as_drawn_pct == 36.0

    # 6. Funnel
    assert rec.funnel_brought_n == 1322
    assert rec.funnel_players_n == 458
    assert rec.ever_drawn_n == 388
    assert rec.reached_battlefield_n == 241
    assert rec.still_on_board_at_end_n == 154
    assert rec.battlefield_survival_pct == 64.0

    # 7. Winrate observations & CI
    assert rec.winrate_when_cast_pct == 43.0
    assert rec.winrate_when_cast_n == 219
    assert rec.winrate_when_in_library_pct == 28.0
    assert rec.winrate_when_in_library_n == 775
    assert rec.winrate_when_in_hand_pct == 30.0
    assert rec.winrate_when_in_hand_n == 134
    assert rec.observed_winrate_gap_pp == 14.5
    assert rec.ci_95_lower_pp == 7.6
    assert rec.ci_95_upper_pp == 21.3
    assert rec.conservative_ranking_indicator == "≥ +7.6pp"

    # 8. Final Zones (4 zones)
    assert rec.final_zones_instances_n == 425
    assert len(rec.final_zones) == 4
    zone_map = {z.zone_name: z.pct for z in rec.final_zones}
    assert zone_map["Library"] == 2.6
    assert zone_map["Battlefield"] == 36.2
    assert zone_map["Graveyard"] == 20.5
    assert zone_map["Exile"] == 6.1

    # 9. Top Commanders (10 entries)
    assert len(rec.top_commanders) == 10
    top1 = rec.top_commanders[0]
    assert top1.rank == 1
    assert top1.commander_name == "Kiora, Sovereign of the Deep"
    assert top1.decks_count == 36
    assert top1.color_identity == "GU"

    top2 = rec.top_commanders[1]
    assert top2.rank == 2
    assert "Spider-Man" in top2.commander_name
    assert top2.decks_count == 30

    # 10. QA Discrepancies flagged
    assert rec.fetch_status == "OK"
    assert rec.insufficient_sample is False
    assert len(rec.quality_warnings) >= 2
    assert any("Brought count discrepancy" in w for w in rec.quality_warnings)
    assert any("On-curve calculation discrepancy" in w for w in rec.quality_warnings)


def test_parse_koma_world_eater_discrepancies() -> None:
    """Verify exact discrepancy detection on Koma, World-Eater:
    - Times Brought = 817 vs Funnel Brought = 821
    - On Curve = 53% reported vs 25/157 = 15.9% calculated.
    """
    html_path = FIXTURES_DIR / "koma-world-eater.html"
    assert html_path.is_file()
    html = html_path.read_text(encoding="utf-8")

    rec = parse_playgroup_card_html(html, slug="koma-world-eater")

    assert rec.card_name == "Koma, World-Eater"
    assert rec.times_brought == 817
    assert rec.funnel_brought_n == 821
    assert rec.on_curve_pct == 53.0
    assert rec.on_curve_count == 25
    assert rec.on_curve_denominator == 157

    # Discrepancy warnings must be present and explicit
    warnings_str = " | ".join(rec.quality_warnings)
    assert "Brought count discrepancy" in warnings_str
    assert "817 vs Funnel Brought = 821" in warnings_str
    assert "On-curve calculation discrepancy" in warnings_str
    assert "reported 53.0% but 25/157 = 15.9%" in warnings_str


def test_parse_sol_ring_high_sample_fixture() -> None:
    """Verify Sol Ring with high observation volume and narrow CI."""
    html_path = FIXTURES_DIR / "sol-ring.html"
    assert html_path.is_file()
    html = html_path.read_text(encoding="utf-8")

    rec = parse_playgroup_card_html(html, slug="sol-ring")

    assert rec.card_name == "Sol Ring"
    assert rec.live_inclusion_pct == 88.0
    assert rec.times_brought == 131091
    assert rec.first_cast_n == 33509
    assert rec.median_cast_turn == 3.0
    assert rec.turn_1_pct == 35.0
    assert rec.turn_2_pct == 11.0
    assert rec.turn_3_pct == 7.0

    assert rec.winrate_when_cast_pct == 31.0
    assert rec.winrate_when_cast_n == 30121
    assert rec.winrate_when_in_library_pct == 22.0
    assert rec.winrate_when_in_library_n == 78386
    assert rec.observed_winrate_gap_pp == 9.1
    assert rec.ci_95_lower_pp == 8.5
    assert rec.ci_95_upper_pp == 9.7
    assert rec.conservative_ranking_indicator == "≥ +8.5pp"


def test_parse_esperzoa_partial_fixture() -> None:
    """Verify Esperzoa with low play count (< 100 plays), classified as PARTIAL."""
    html_path = FIXTURES_DIR / "esperzoa.html"
    assert html_path.is_file()
    html = html_path.read_text(encoding="utf-8")

    rec = parse_playgroup_card_html(html, slug="esperzoa")

    assert rec.card_name == "Esperzoa"
    assert rec.times_brought == 9
    assert rec.first_cast_n is None
    assert rec.live_inclusion_pct is None
    assert rec.winrate_when_cast_pct is None
    assert rec.fetch_status == "PARTIAL"
    assert rec.insufficient_sample is True
    assert any("insufficient evidence" in w for w in rec.quality_warnings)
    assert len(rec.final_zones) == 0
    assert len(rec.top_commanders) == 0


def test_parse_empty_and_not_found_edge_cases() -> None:
    """Verify error resilience on empty HTML and 404/not found templates."""
    # Empty HTML
    rec_empty = parse_playgroup_card_html("", slug="unknown-card")
    assert rec_empty.fetch_status == "NO_DATA"
    assert rec_empty.times_brought is None

    # 404 Not Found error page
    not_found_html = (
        "<html><head><title>404 Not Found</title></head><body><h1>Not Found</h1></body></html>"
    )
    rec_404 = parse_playgroup_card_html(not_found_html, slug="phantom-card")
    assert rec_404.fetch_status == "NO_DATA"

    # Dict serialization roundtrip
    d = rec_empty.to_dict()
    assert isinstance(d, dict)
    assert d["slug"] == "unknown-card"
    assert d["fetch_status"] == "NO_DATA"


def test_import_playgroup_atlas_html_and_builder_integration(tmp_path: Path) -> None:
    """Test importing HTML fixture into StudioStore and retrieving via builder."""
    from commander_lab.studio import builder, importers
    from commander_lab.studio.store import DataClass, StudioStore

    store = StudioStore.in_memory()
    db = store.connection

    # Setup source and card
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title="test_source",
        sha256="abc12345",
    )
    db.execute(
        """
        INSERT INTO card (
            card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value,
            type_line, oracle_text, is_basic_land, commander_legal, source_id
        ) VALUES (
            'card:project:koma-uuid', '6ba0656f-e0d2-4735-9c66-3a00afa9fc23',
            'Koma, Cosmos Serpent', 'GU', '{3}{G}{G}{U}{U}', 7.0,
            'Legendary Creature — Serpent', 'Cannot be countered...', 0, 1, ?
        )
        """,
        (source_id,),
    )
    db.execute(
        """
        INSERT INTO inventory (
            card_id, observed, owned_lower_bound, reserved, available_lower_bound,
            quantity_exact, source_id
        ) VALUES ('card:project:koma-uuid', 1, 1, 0, 1, 1, ?)
        """,
        (source_id,),
    )

    # 1. Import HTML fixture
    html_path = FIXTURES_DIR / "koma-cosmos-serpent.html"
    result = importers.import_playgroup_atlas(store, html_path)

    assert result["records_imported"] == 1
    assert result["top_commanders_imported"] == 10
    assert result["final_zones_imported"] == 4

    # 2. Verify store.count
    assert store.count("playgroup_card_atlas") == 1
    assert store.count("playgroup_top_commander") == 10
    assert store.count("playgroup_final_zone") == 4

    # 3. Verify row in playgroup_card_atlas
    row = db.execute(
        "SELECT * FROM playgroup_card_atlas WHERE oracle_id = '6ba0656f-e0d2-4735-9c66-3a00afa9fc23'"
    ).fetchone()
    assert row is not None
    assert row["card_name"] == "Koma, Cosmos Serpent"
    assert row["card_id"] == "card:project:koma-uuid"
    assert row["slug"] == "koma-cosmos-serpent"
    assert row["live_inclusion_pct"] == 4.0
    assert row["median_cast_turn"] == 6.0
    assert row["observed_winrate_gap_pp"] == 14.5
    assert row["conservative_ranking_indicator"] == "≥ +7.6pp"
    assert row["fetch_status"] == "OK"
    assert row["insufficient_sample"] == 0

    # 4. Verify idempotency: importing again updates in place
    result2 = importers.import_playgroup_atlas(store, html_path)
    assert result2["records_imported"] == 1
    assert store.count("playgroup_card_atlas") == 1
    assert store.count("playgroup_top_commander") == 10
    assert store.count("playgroup_final_zone") == 4

    # 5. Verify builder.pool_cards
    pool = builder.pool_cards(store, ["Koma, Cosmos Serpent"])
    cards = pool["cards"]
    assert isinstance(cards, list)
    koma_card = next(c for c in cards if c["name"] == "Koma, Cosmos Serpent")
    assert koma_card["playgroup"] is not None
    pg = koma_card["playgroup"]
    assert pg["live_inclusion_pct"] == 4.0
    assert pg["median_cast_turn"] == 6.0
    assert pg["observed_winrate_gap_pp"] == 14.5
    assert pg["ci_95_lower_pp"] == 7.6
    assert pg["ci_95_upper_pp"] == 21.3
    assert pg["status"] == "OK"

    # 6. Verify builder.card_detail
    detail = builder.card_detail(store, "card:project:koma-uuid")
    assert detail["playgroup"] is not None
    pg_detail = detail["playgroup"]
    assert pg_detail["card_name"] == "Koma, Cosmos Serpent"
    assert pg_detail["funnel_brought_n"] == 1322
    assert pg_detail["reached_battlefield_n"] == 241
    assert pg_detail["battlefield_survival_pct"] == 64.0
    assert len(pg_detail["top_commanders"]) == 10
    assert len(pg_detail["final_zones"]) == 4
    assert len(pg_detail["quality_warnings"]) >= 2
    assert pg_detail["disclosure"] == "Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke."


def test_import_playgroup_atlas_tsv_and_cli(tmp_path: Path, capsys: object) -> None:
    """Test TSV import and CLI subcommand execution."""
    import json

    from commander_lab.studio import importers
    from commander_lab.studio.__main__ import main
    from commander_lab.studio.store import DataClass, StudioStore

    store = StudioStore.in_memory()
    db = store.connection

    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title="test_src",
        sha256="12345678",
    )
    db.execute(
        """
        INSERT INTO card (
            card_id, oracle_id, oracle_name, color_identity, mana_cost, mana_value,
            type_line, oracle_text, is_basic_land, commander_legal, source_id
        ) VALUES (
            'card:project:sol-ring-uuid', '895c2e36-7484-4861-840e-26f555c48b26',
            'Sol Ring', '', '{1}', 1.0, 'Artifact', '{T}: Add {C}{C}.', 0, 1, ?
        )
        """,
        (source_id,),
    )

    # Write a mock TSV row
    tsv_file = tmp_path / "mock_atlas.tsv"
    tsv_content = (
        "card_id\toracle_id\tcard_name\tslug\tformat_mode\tlive_inclusion_pct\ttimes_brought\t"
        "median_cast_turn\tobserved_winrate_gap_pp\tci_95_lower_pp\tci_95_upper_pp\t"
        "conservative_ranking_indicator\tfetch_status\tquality_warnings\tinsufficient_sample\n"
        "card:project:sol-ring-uuid\t895c2e36-7484-4861-840e-26f555c48b26\tSol Ring\tsol-ring\t"
        "multiplayer\t88.0\t131091\t3.0\t9.1\t8.5\t9.7\t≥ +8.5pp\tOK\t[]\t0\n"
    )
    tsv_file.write_text(tsv_content, encoding="utf-8")

    result = importers.import_playgroup_atlas(store, tsv_file)
    assert result["records_imported"] == 1

    row = db.execute(
        "SELECT * FROM playgroup_card_atlas WHERE oracle_id = '895c2e36-7484-4861-840e-26f555c48b26'"
    ).fetchone()
    assert row is not None
    assert row["card_name"] == "Sol Ring"
    assert row["live_inclusion_pct"] == 88.0
    assert row["times_brought"] == 131091
    assert row["median_cast_turn"] == 3.0

    # Test CLI invocation with --data
    db_dir = tmp_path / "studio_data"
    db_dir.mkdir()
    persistent_store = StudioStore.open(db_dir)
    persistent_store.close()

    cli_args = [
        "--data",
        str(db_dir),
        "import-playgroup-atlas",
        str(tsv_file),
    ]
    ret = main(cli_args)
    assert ret == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    out = json.loads(captured.out)
    assert out["records_imported"] == 1


def test_load_target_cards_public_corpus(tmp_path: Path) -> None:
    """Verify load_target_cards queries public corpus decks without touching private collection."""
    import sqlite3
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.collect_playgroup_card_atlas import load_target_cards

    db_path = tmp_path / "test_store.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE corpus_deck_card (
                deck_id TEXT NOT NULL,
                card_name TEXT NOT NULL,
                oracle_id TEXT,
                quantity INTEGER,
                section TEXT,
                normalization_status TEXT
            )
            """
        )
        conn.execute("INSERT INTO corpus_deck_card VALUES ('d1', 'Sol Ring', 'o1', 1, 'mainboard', 'OK')")
        conn.execute("INSERT INTO corpus_deck_card VALUES ('d1', 'Birds of Paradise', 'o2', 1, 'mainboard', 'OK')")
        conn.execute("INSERT INTO corpus_deck_card VALUES ('d2', 'Birds of Paradise', 'o2', 1, 'mainboard', 'OK')")

    targets = load_target_cards(store_path=db_path)
    assert len(targets) == 2
    # Cards must be sorted alphabetically by name
    assert targets[0]["card_name"] == "Birds of Paradise"
    assert targets[1]["card_name"] == "Sol Ring"


def test_fetch_card_html_caching_and_404(tmp_path: Path) -> None:
    """Verify fetch_card_html cache reading and .404 marker detection."""
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.collect_playgroup_card_atlas import fetch_card_html

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # 1. Uncached offline request returns status 0 (UNKNOWN)
    html, status, err = fetch_card_html("test-card", cache_dir=cache_dir, offline_only=True)
    assert html is None
    assert status == 0
    assert "not in cache" in err

    # 2. Cached HTML hit
    (cache_dir / "test-card.html").write_text("<html><body>test</body></html>", encoding="utf-8")
    html, status, err = fetch_card_html("test-card", cache_dir=cache_dir, offline_only=True)
    assert html == "<html><body>test</body></html>"
    assert status == 200

    # 3. Cached .404 marker hit
    (cache_dir / "missing-card.404").touch()
    html, status, err = fetch_card_html("missing-card", cache_dir=cache_dir, offline_only=False)
    assert html is None
    assert status == 404
    assert "Cached HTTP 404" in err
