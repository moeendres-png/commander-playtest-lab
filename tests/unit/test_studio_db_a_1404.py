"""Unit tests for PR DB-A: universal decklist import, repo baseline diff/seed, role origin
audit, and source freshness reporting (Refs #1404, #1413)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.studio import (
    DataClass,
    StudioStore,
    decks,
    import_all,
    importers,
    roles,
)
from commander_lab.studio.web import create_app

FORBIDDEN_PURCHASE_TERMS = (
    "price",
    "euro",
    "usd",
    "dollar",
    "buy",
    "purchase",
    "kaufen",
    "preis",
    "kosten",
)


def _seed_store(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    src = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title="coll.csv",
        sha256="a" * 64,
        snapshot_date="2026-11-10",
    )
    cards = [
        ("cmd-chulane", "oid-chulane", "Chulane, Teller of Tales", "GWU", 1),
        ("c-sol", "oid-sol", "Sol Ring", "", 1),
        ("c-counter", "oid-counter", "Counterspell", "U", 1),
        ("c-forest", "oid-forest", "Forest", "G", 1),
        ("c-bolt-coll", "oid-bolt-coll", "Lightning Bolt", "R", 1),
        ("c-banned", "oid-banned", "Black Lotus", "", 0),
    ]
    with store.connection as db:
        for cid, oid, name, identity, legal in cards:
            db.execute(
                "INSERT INTO card (card_id, oracle_id, oracle_name, color_identity, mana_cost, "
                "mana_value, type_line, oracle_text, is_basic_land, commander_legal, "
                "legality_verified_at, identity_evidence, source_id) "
                "VALUES (?, ?, ?, ?, '{1}', 1, 'Card', '', ?, ?, '2026-11-10', 'scryfall', ?)",
                (cid, oid, name, identity, 1 if name == "Forest" else 0, legal, src),
            )
            db.execute(
                "INSERT INTO inventory VALUES (?, 1, 2, 0, 2, 1, 1, '2026-11-10', ?)",
                (cid, src),
            )
        # Public-only cards (not in collection): one in identity, one outside identity
        db.execute(
            "INSERT INTO scryfall_card VALUES "
            "('oid-rhystic', 'sid-rhystic', 'Rhystic Study', 'Rhystic Study', 'normal', "
            "'{2}{U}', 3, 'Enchantment', '', 'U', 'legal', 10, '[]', '[]', NULL, NULL, "
            "0, '2020-01-01', NULL, NULL, ?, NULL, NULL, NULL)",
            (src,),
        )
        db.execute(
            "INSERT INTO scryfall_card VALUES "
            "('oid-dockside', 'sid-dockside', 'Demonic Tutor', 'Demonic Tutor', 'normal', "
            "'{1}{B}', 2, 'Sorcery', '', 'B', 'legal', 15, '[]', '[]', NULL, NULL, "
            "0, '2020-01-01', NULL, NULL, ?, NULL, NULL, NULL)",
            (src,),
        )
    return store


def test_parse_decklist_formats_buckets_and_no_purchase_terms(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)

    mox = decks.parse_decklist_text(
        store,
        ["Chulane, Teller of Tales"],
        "Commander\n1 Chulane, Teller of Tales *CMDR*\n\nDeck\n"
        "1 Sol Ring (CMM) 412 *F*\n1 Rhystic Study (WOT) 25\n1 Demonic Tutor\n"
        "1 Unknown Foil Brew\nSideboard\n1 Counterspell\n",
    )
    assert mox["detected_format"] == "moxfield"
    assert [c["name"] for c in mox["in_collection"]] == ["Sol Ring"]
    assert {c["name"] for c in mox["not_in_collection"]} == {"Rhystic Study", "Unknown Foil Brew"}
    assert {c["name"] for c in mox["outside_color_identity"]} == {"Demonic Tutor"}
    assert mox["summary"] == {
        "in_collection_cards": 1,
        "not_in_collection_cards": 2,
        "outside_color_identity_cards": 1,
        "unrecognized_lines": 0,
        "sideboard_lines_skipped": 1,
    }

    arch = decks.parse_decklist_text(
        store,
        ["Chulane, Teller of Tales"],
        "1 Counterspell [Removal] {keep}\n1 Forest\nMaybeboard\n1 Sol Ring [Ramp]\n",
    )
    assert arch["detected_format"] == "archidekt"
    assert {c["name"] for c in arch["in_collection"]} == {"Counterspell", "Forest"}

    arena = decks.parse_decklist_text(
        store,
        ["Chulane, Teller of Tales"],
        "1 Sol Ring (CMM) 412\n1 Lightning Bolt (STA) 42\n",
    )
    assert arena["detected_format"] == "arena"
    assert [c["name"] for c in arena["outside_color_identity"]] == ["Lightning Bolt"]

    csv_text = (
        "Count,Name,Section\n"
        "1,Sol Ring,Mainboard\n"
        "1,Counterspell,Mainboard\n"
        "1,Black Lotus,Mainboard\n"
        "bad,Forest,Mainboard\n"
        "1,Rhystic Study,Sideboard\n"
    )
    parsed_csv = decks.parse_decklist_text(store, ["Chulane, Teller of Tales"], csv_text)
    assert parsed_csv["detected_format"] == "csv"
    assert {c["name"] for c in parsed_csv["in_collection"]} == {"Sol Ring", "Counterspell"}
    assert [c["name"] for c in parsed_csv["outside_color_identity"]] == ["Black Lotus"]
    assert parsed_csv["outside_color_identity"][0]["reason"] == "nicht Commander-legal"
    assert len(parsed_csv["unrecognized_lines"]) == 1
    assert parsed_csv["summary"]["unrecognized_lines"] == 1
    # Sideboard row skipped
    assert all(c["name"] != "Rhystic Study" for c in parsed_csv["not_in_collection"])

    serialized = json.dumps([mox, arch, arena, parsed_csv]).casefold()
    for term in FORBIDDEN_PURCHASE_TERMS:
        assert term not in serialized
    store.close()


def test_repo_baseline_diff_prefilter_and_seed_idempotency(tmp_path: Path, monkeypatch) -> None:
    store = _seed_store(tmp_path)
    decks_dir = tmp_path / "decks"
    decks_dir.mkdir()
    (decks_dir / "chulane_current.txt").write_text(
        "Commander\n1 Chulane, Teller of Tales\n\nDeck\n1 Sol Ring\n1 Forest\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(decks, "_DECKS_DIR", decks_dir)

    assert (
        decks.repo_deck_file_for_commander(["Chulane, Teller of Tales"])
        == decks_dir / "chulane_current.txt"
    )
    baselines = decks.baseline_decks_for_commander(["Chulane, Teller of Tales"])
    assert baselines == [
        {
            "revision_id": "repo:chulane_current",
            "label": "chulane_current.txt (Repo-Stand)",
            "file": "chulane_current.txt",
        }
    ]

    # Seed idempotently via import_all._seed_repo_deck
    seeded = import_all._seed_repo_deck(store, "Chulane, Teller of Tales")
    assert seeded["seeded"] == 1
    assert seeded["cards"] == 3
    rev_id = str(
        store.connection.execute(
            "SELECT revision_id FROM deck_branch WHERE deck_id = 'chulane-current' AND branch = 'main'"
        ).fetchone()[0]
    )
    # Second seed call leaves existing deck untouched
    second = import_all._seed_repo_deck(store, "Chulane, Teller of Tales")
    assert second == {"seeded": 0, "already_present": 1}
    # Unknown commander skips cleanly without crashing
    assert import_all._seed_repo_deck(store, "Unknown, Missing Hero") == {"seeded": 0}

    # Test API endpoints (/api/diff-baselines, /api/diff, /api/prefilter) with repo: baseline
    store_path = tmp_path / "studio"
    store.close()
    client = TestClient(create_app(store_path))
    resp_base = client.get("/api/diff-baselines", params={"commander": "Chulane, Teller of Tales"})
    assert resp_base.status_code == 200
    assert resp_base.json()["baselines"] == baselines

    draft_cards = [
        {"card_id": "cmd-chulane", "quantity": 1, "zone": "commander"},
        {"card_id": "c-sol", "quantity": 1, "zone": "main"},
        {"card_id": "c-counter", "quantity": 1, "zone": "main"},
    ]
    marker = {"X-Studio": "1"}
    resp_diff = client.post(
        "/api/diff",
        json={"base_revision_id": "repo:chulane_current", "cards": draft_cards, "cohort": "all"},
        headers=marker,
    )
    assert resp_diff.status_code == 200
    diff_data = resp_diff.json()
    assert diff_data["added"][0]["card_id"] == "c-counter"
    assert diff_data["removed"][0]["card_id"] == "c-forest"

    resp_pre = client.post(
        "/api/prefilter",
        json={"base_revision_id": "repo:chulane_current", "cards": draft_cards, "trials": 50},
        headers=marker,
    )
    assert resp_pre.status_code == 200
    pre_data = resp_pre.json()
    assert pre_data["data_class"] == "HEURISTIC_MODEL"
    assert pre_data["comparable"] is False

    # Full 100-card repo baseline makes prefilter comparable
    (decks_dir / "chulane_full.txt").write_text(
        "Commander\n1 Chulane, Teller of Tales\n\nDeck\n99 Forest\n",
        encoding="utf-8",
    )
    full_draft = [
        {"card_id": "cmd-chulane", "quantity": 1, "zone": "commander"},
        {"card_id": "c-counter", "quantity": 1, "zone": "main"},
        {"card_id": "c-forest", "quantity": 98, "zone": "main"},
    ]
    resp_pre_full = client.post(
        "/api/prefilter",
        json={"base_revision_id": "repo:chulane_full", "cards": full_draft, "trials": 50},
        headers=marker,
    )
    assert resp_pre_full.status_code == 200
    assert resp_pre_full.json()["comparable"] is True

    resp_missing = client.post(
        "/api/diff",
        json={"base_revision_id": "repo:nonexistent_file", "cards": draft_cards, "cohort": "all"},
        headers=marker,
    )
    assert resp_missing.status_code == 404
    assert rev_id.startswith("chulane-current@")


def test_role_origin_audit_counts_and_overlap(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)
    src = store.register_source(
        data_class=DataClass.DERIVED_DESCRIPTIVE,
        title="roles.json",
        sha256="b" * 64,
        snapshot_date="2026-11-12",
    )
    with store.connection as db:
        claims = [
            ("oid-sol", "ramp", "SCRYFALL_TAGGER_ORIGINAL", "global", src, "mana-rock", "x"),
            ("oid-sol", "ramp", "ORACLE_TEXT_REVIEW", "global", src, None, "oracle:ramp"),
            ("oid-counter", "counterspell", "CROSSWALK_NORMALIZED", "global", src, "counter", "x"),
            ("oid-forest", "ramp", "ORACLE_TEXT_REVIEW", "global", src, None, "oracle:ramp"),
        ]
        db.executemany(
            "INSERT INTO card_role_claim VALUES (?, ?, ?, ?, ?, ?, ?)",
            claims,
        )
    audit = roles.role_origin_audit(store)
    assert audit["claims_by_origin"] == {
        "CROSSWALK_NORMALIZED": 1,
        "ORACLE_TEXT_REVIEW": 2,
        "SCRYFALL_TAGGER_ORIGINAL": 1,
    }
    by_role = {row["role"]: row for row in audit["roles"]}
    assert by_role["ramp"] == {
        "role": "ramp",
        "tagger_total": 1,
        "oracle_total": 2,
        "both": 1,
        "tagger_only": 0,
        "oracle_only": 1,
        "oracle_confirmed_share": 0.5,
    }
    assert by_role["counterspell"] == {
        "role": "counterspell",
        "tagger_total": 1,
        "oracle_total": 0,
        "both": 0,
        "tagger_only": 1,
        "oracle_only": 0,
        "oracle_confirmed_share": None,
    }
    store.close()


def test_source_freshness_coalesce_and_status_endpoint(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)
    digest = "c" * 64
    sid_first = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="edhrec_cards.csv",
        sha256=digest,
        snapshot_date=None,
    )
    sid_second = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="edhrec_cards.csv",
        sha256=digest,
        snapshot_date="2026-11-15",
    )
    assert sid_first == sid_second

    # Also test importer snapshot_date extraction from retrieved_at in edhrec cardrecs csv
    csv_path = tmp_path / "cardrecs.csv"
    csv_path.write_text(
        "karte,rubrik,decks_with_card,eligible_decks,inclusion_pct,lift,synergy,source_url,retrieved_at\n"
        "Sol Ring,ramp,10,20,50.0,0.1,10.0,https://example.invalid,2026-11-14T12:00:00Z\n",
        encoding="utf-8",
    )
    importers.import_edhrec_cardrecs_csv(store, csv_path)

    # Also test lab deck snapshot date extraction
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(
        json.dumps(
            {
                "deck_id": "lab-snap",
                "name": "Lab Snap",
                "date": "2026-11-16",
                "cards": [{"oracle_name": "Sol Ring", "quantity": 1, "zone": "main"}],
            }
        ),
        encoding="utf-8",
    )
    importers.import_lab_deck_snapshot(store, snap_path)

    store_path = tmp_path / "studio"
    store.close()

    client = TestClient(create_app(store_path))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["freshness"] == {
        "total_sources": 4,
        "with_snapshot_date": 4,
        "with_identifier": 0,
        "oldest_snapshot": "2026-11-10",
        "newest_snapshot": "2026-11-16",
    }
    dates = {row["title"]: row["snapshot_date"] for row in body["sources"]}
    assert dates["edhrec_cards.csv"] == "2026-11-15"
    assert dates["cardrecs.csv"] == "2026-11-14"
    assert dates["snap.json"] == "2026-11-16"


def test_status_freshness_ignores_identifier_labels_and_lists_layers(tmp_path: Path) -> None:
    """``universe:*`` snapshot labels are identifiers, not dates: they never enter the
    oldest/newest span (a text max would have answered ``universe:e``) and are counted apart.
    Other non-dates ("2026-11", "2026-13-45") are undated, not identifiers. Quelldecks are the
    sources a corpus deck names, never a plain ``name.json``."""
    store = StudioStore.open(tmp_path / "studio")
    rows = [
        ("11354052.json", "2025-02-13"),
        ("AbCdEfGhIjKlMnOpQrSt12.json", "2026-05-06T10:00:40.373+00:00"),
        ("chulane_decklist_inclusion_20261112.csv#universe:4236ac0a9befcd74:213", "universe:4"),
        ("chulane_corpus_decklist_inclusion_20261115.csv#universe:e5f1:66", "universe:e"),
        ("topdeck_chulane_decks.csv", "2026-09-17"),
        ("playgroup_atlas:playgroup_card_atlas_1.jsonl", None),
        ("spellbook_shells.csv", None),
        ("card_rulings_1655.jsonl", None),
        ("snap.json", "2026-10-01"),
        ("scryfall_oracle.json", "2026-11"),
        ("default-cards.json", "2026-13-45"),
        ("other.json", "12.11.2026"),
    ]
    with store.connection:
        for index, (title, snapshot) in enumerate(rows):
            store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=title,
                sha256=hashlib.sha256(str(index).encode()).hexdigest(),
                snapshot_date=snapshot,
            )
        for deck_index, title in enumerate(("11354052.json", "AbCdEfGhIjKlMnOpQrSt12.json")):
            source_id = store.connection.execute(
                "SELECT source_id FROM source WHERE title = ?", (title,)
            ).fetchone()[0]
            store.connection.execute(
                "INSERT INTO corpus_deck (deck_id, cohort, url, platform, play_group, tags, "
                "fingerprint, legality_audit, source_id) "
                "VALUES (?, 'all', ?, 'edhrec', 'community', '[]', ?, 'LEGAL', ?)",
                (
                    f"d{deck_index}",
                    f"https://example.invalid/{deck_index}",
                    f"fp{deck_index}",
                    source_id,
                ),
            )
    store.close()

    body = TestClient(create_app(tmp_path / "studio")).get("/api/status").json()
    assert body["freshness"] == {
        "total_sources": 12,
        "with_snapshot_date": 4,
        "with_identifier": 2,
        "oldest_snapshot": "2025-02-13",
        "newest_snapshot": "2026-10-01",
    }
    layers = {row["layer"]: row for row in body["source_layers"]}
    assert layers["Quelldecks"] == {
        "layer": "Quelldecks",
        "sources": 2,
        "dated": 2,
        "with_identifier": 0,
        "oldest": "2025-02-13",
        "newest": "2026-05-06",
        "undated_note": None,
    }
    # plain ``name.json`` files without a corpus deck are not source decks
    others = layers["Weitere Quellen"]
    assert (others["sources"], others["dated"], others["with_identifier"]) == (4, 1, 0)
    assert (others["oldest"], others["newest"]) == ("2026-10-01", "2026-10-01")
    cohorts = layers["Universum-Kohorten"]
    assert (cohorts["sources"], cohorts["dated"], cohorts["with_identifier"]) == (2, 0, 2)
    assert (cohorts["oldest"], cohorts["newest"]) == (None, None)
    for undated in ("Playgroup", "Spellbook", "Rulings", "Universum-Kohorten"):
        assert layers[undated]["undated_note"] == "Datum nicht im Store"
        assert layers[undated]["oldest"] is None
    assert layers["TopDeck / EDHTop16"]["newest"] == "2026-09-17"
    assert not any("universe:" in str(value) for value in (body["freshness"], body["sources"]))
    # every source is in exactly one layer; the sample holds only counted dated rows
    assert sum(row["sources"] for row in body["source_layers"]) == 12
    assert len(body["sources"]) == body["freshness"]["with_snapshot_date"]


def test_status_payload_carries_only_the_newest_dated_sources(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    with store.connection:
        for index in range(40):
            store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=f"Deck{index:018d}ab.json",
                sha256=hashlib.sha256(str(index).encode()).hexdigest(),
                snapshot_date="2026-01-01",
            )
    store.close()
    body = TestClient(create_app(tmp_path / "studio")).get("/api/status").json()
    assert len(body["sources"]) == 25
    assert body["freshness"]["total_sources"] == 40
    assert body["source_layers"][0]["sources"] == 40
