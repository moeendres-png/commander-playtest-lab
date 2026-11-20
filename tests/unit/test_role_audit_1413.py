"""Unit tests for #1413 role origin audit (pool coverage) and Tierliste UI completion."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import DataClass, StudioStore, roles
from commander_lab.studio.web import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def _seed_role_audit_store(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    src = store.register_source(
        data_class=DataClass.DERIVED_DESCRIPTIVE,
        title="seed.json",
        sha256="a" * 64,
        snapshot_date="2026-11-15",
    )
    cards = [
        ("cmd-chulane", "oid-chulane", "Chulane, Teller of Tales", "GWU", 1),
        ("c-sol", "oid-sol", "Sol Ring", "", 1),
        ("c-counter", "oid-counter", "Counterspell", "U", 1),
        ("c-forest", "oid-forest", "Forest", "G", 1),
        ("c-elk", "oid-elk", "Vanilla Elk", "G", 1),  # in GWU pool, untagged
        ("c-bolt", "oid-bolt", "Lightning Bolt", "R", 1),  # outside GWU identity
        ("c-lotus", "oid-lotus", "Black Lotus", "", 0),  # not commander legal
    ]
    with store.connection as db:
        for cid, oid, name, identity, legal in cards:
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, ?, '{1}', 1, 'Card', '', ?, ?, '2026-11-15', 'scryfall', ?)",
                (cid, oid, name, identity, 1 if name == "Forest" else 0, legal, src),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 1, 0, 1, 1, 1, '2026-11-15', ?)",
                (cid, src),
            )
        claims = [
            ("oid-sol", "ramp", roles.ORIGIN_TAGGER, "global", src, "ramp", "tagger:ramp"),
            ("oid-sol", "ramp", roles.ORIGIN_ORACLE_TEXT, "global", src, None, "oracle:ramp"),
            (
                "oid-counter",
                "counterspell",
                roles.ORIGIN_CROSSWALK,
                "global",
                src,
                "counter",
                "x",
            ),
            ("oid-forest", "ramp", roles.ORIGIN_ORACLE_TEXT, "global", src, None, "oracle:ramp"),
            # Off-color & banned claims must NOT leak into Chulane's pool coverage!
            ("oid-bolt", "removal", roles.ORIGIN_TAGGER, "global", src, "removal", "t"),
            ("oid-lotus", "ramp", roles.ORIGIN_TAGGER, "global", src, "ramp", "t"),
        ]
        db.executemany(
            "INSERT INTO card_role_claim VALUES (?, ?, ?, ?, ?, ?, ?)",
            claims,
        )
        db.executemany(
            "INSERT INTO card_role VALUES (?, ?, ?)",
            [
                ("oid-sol", "ramp", src),
                ("oid-counter", "counterspell", src),
                ("oid-forest", "ramp", src),
                ("oid-bolt", "removal", src),
                ("oid-lotus", "ramp", src),
            ],
        )
    return store


def test_role_origin_audit_global_compat_and_pool_scoped(tmp_path: Path) -> None:
    store = _seed_role_audit_store(tmp_path)
    try:
        # Global call stays backwards-compatible (only claims_by_origin and roles)
        global_audit = roles.role_origin_audit(store)
        assert set(global_audit.keys()) == {"claims_by_origin", "roles"}
        by_role_global = {row["role"]: row for row in global_audit["roles"]}  # type: ignore[iterable]
        assert by_role_global["ramp"] == {
            "role": "ramp",
            "tagger_total": 2,  # oid-sol + oid-lotus
            "oracle_total": 2,  # oid-sol + oid-forest
            "both": 1,
            "tagger_only": 1,
            "oracle_only": 1,
            "oracle_confirmed_share": 0.5,
        }

        # Pool-scoped call for Chulane (5 cards: cmd-chulane, c-sol, c-counter, c-forest, c-elk)
        pool_audit = roles.role_origin_audit(store, commander="Chulane, Teller of Tales")
        assert pool_audit["commander"] == "Chulane, Teller of Tales"
        assert pool_audit["pool_total"] == 5
        assert pool_audit["pool_tagged"] == 3  # Sol Ring, Counterspell, Forest
        assert pool_audit["pool_untagged"] == 2  # Chulane, Vanilla Elk
        per_role = pool_audit["per_role_pool_counts"]
        assert isinstance(per_role, dict)
        assert per_role["ramp"] == 2  # Sol Ring, Forest (Black Lotus excluded!)
        assert per_role["counterspell"] == 1
        assert per_role["removal"] == 0  # Lightning Bolt excluded (red)

        by_role_pool = {row["role"]: row for row in pool_audit["roles"]}  # type: ignore[iterable]
        assert by_role_pool["ramp"]["pool_count"] == 2
        assert by_role_pool["ramp"]["pool_tagger_total"] == 1  # Sol Ring only
        assert by_role_pool["ramp"]["pool_oracle_total"] == 2  # Sol Ring, Forest
        assert by_role_pool["ramp"]["pool_both"] == 1
        assert by_role_pool["ramp"]["pool_tagger_only"] == 0
        assert by_role_pool["ramp"]["pool_oracle_only"] == 1
        assert by_role_pool["removal"]["pool_count"] == 0
        assert by_role_pool["removal"]["pool_tagger_total"] == 0

        with pytest.raises(KeyError):
            roles.role_origin_audit(store, commander="Unknown Commander")
    finally:
        store.close()


def test_web_route_roles_audit(tmp_path: Path) -> None:
    store = _seed_role_audit_store(tmp_path)
    store.close()

    with TestClient(create_app(tmp_path / "studio")) as client:
        r_global = client.get("/api/roles/audit")
        assert r_global.status_code == 200
        g_body = r_global.json()
        assert "claims_by_origin" in g_body
        assert "roles" in g_body

        r_pool = client.get(
            "/api/roles/audit",
            params={"commander": "Chulane, Teller of Tales"},
        )
        assert r_pool.status_code == 200
        p_body = r_pool.json()
        assert p_body["commander"] == "Chulane, Teller of Tales"
        assert p_body["pool_total"] == 5
        assert p_body["pool_tagged"] == 3
        assert p_body["pool_untagged"] == 2
        assert p_body["per_role_pool_counts"]["ramp"] == 2

        r_unknown = client.get("/api/roles/audit", params={"commander": "Unknown"})
        assert r_unknown.status_code == 404


def test_tierliste_csp_quick_toggle_and_audit_ui_markers() -> None:
    tier_html = (STATIC_DIR / "tierliste.html").read_text(encoding="utf-8")
    tier_js = (STATIC_DIR / "tierliste.js").read_text(encoding="utf-8")

    # CSP: zero inline styles, zero inline handlers, zero DOM injection sinks
    assert "style=" not in tier_html
    assert not re.search(r"\son[a-z]+=", tier_html)
    assert "style=" not in tier_js
    assert ".innerHTML" not in tier_js
    assert ".outerHTML" not in tier_js
    assert "eval(" not in tier_js

    # Quick toggle in main filter bar wired to rank_group ("pool" / "function")
    assert 'id="rank-group-toggle"' in tier_html
    assert "Gesamtpool" in tier_html
    assert "Gleiche Funktion" in tier_html
    assert 'data-rank-group="pool"' in tier_html
    assert 'data-rank-group="function"' in tier_html
    assert "rank_group" in tier_js
    assert "refreshStrength()" in tier_js

    # Role audit descriptive summary markers (the TopDeck Mit/Ohne panel left with Q1-b1, #1676)
    assert "/api/roles/audit" in tier_js
    assert "/api/tournament-conversion" not in tier_js
    assert "pool_tagged" in tier_js
    assert "pool_total" in tier_js
    assert "zu wenig Daten" in tier_js
