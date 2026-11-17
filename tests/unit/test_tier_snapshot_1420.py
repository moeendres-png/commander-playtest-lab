"""Unit tests for #1420 (D2: Persisted Tier Snapshot) and #1369 summary targets.

Self-contained synthetic store tests: no ``from tests.*`` imports, no unguarded loops.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    builder,
    import_all,
    strength_view,
    tier_snapshot,
)
from commander_lab.studio.__main__ import main as studio_main
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app

HEADER = {"X-Studio": "1"}
COMMANDER = "Snap Commander"
CARDS = [f"Snap Spell {index:02d}" for index in range(10)]
LANDS = ["Snap Utility Land", "Snap Dual Land"]


def _card_row(
    number: int,
    name: str,
    colors: str,
    mana_cost: str,
    mana_value: float,
    type_line: str,
    *,
    is_basic_land: bool = False,
) -> dict[str, object]:
    return {
        "card_id": f"card:snap:{number:04d}",
        "oracle_id": None,
        "oracle_name": name,
        "color_identity": colors,
        "mana_cost": mana_cost,
        "mana_value": mana_value,
        "type_line": type_line,
        "oracle_text": "",
        "is_basic_land": is_basic_land,
        "commander_legal": True,
        "legality_verified_at": "2026-11-16",
        "identity_evidence_type": "synthetic",
    }


def _write_workbook(path: Path) -> None:
    identity_cols = [
        "card_id",
        "oracle_id",
        "oracle_name",
        "color_identity",
        "mana_cost",
        "mana_value",
        "type_line",
        "oracle_text",
        "is_basic_land",
        "commander_legal",
        "legality_verified_at",
        "identity_evidence_type",
    ]
    inventory_cols = [
        "card_id",
        "oracle_name",
        "observed_quantity",
        "physical_owned_quantity_lower_bound",
        "reserved_for_opponents_quantity",
        "available_for_own_decks_quantity_lower_bound",
        "quantity_exact",
        "number_of_lots",
        "last_verified_at",
    ]
    rows: list[dict[str, object]] = [
        _card_row(1, COMMANDER, "WU", "{2}{W}{U}", 4.0, "Legendary Creature — Wizard"),
        _card_row(2, "Plains", "W", "", 0.0, "Basic Land — Plains", is_basic_land=True),
    ]
    for index, name in enumerate(CARDS):
        rows.append(
            _card_row(
                10 + index,
                name,
                "W" if index % 2 == 0 else "U",
                "{2}{W}",
                3.0,
                "Creature — Human",
            )
        )
    for idx, land in enumerate(LANDS):
        rows.append(_card_row(50 + idx, land, "WU", "", 0.0, "Land"))

    wb = openpyxl.Workbook()
    identity = wb.active
    assert identity is not None
    identity.title = "01_CARD_IDENTITY"
    identity.append(identity_cols)
    for row in rows:
        identity.append([row[col] for col in identity_cols])

    inventory = wb.create_sheet("05_INVENTORY_CURRENT")
    inventory.append(inventory_cols)
    for row in rows:
        qty = 10 if row["oracle_name"] == "Plains" else 1
        inventory.append(
            [row["card_id"], row["oracle_name"], qty, qty, 0, qty, True, 1, "2026-11-16"]
        )
    wb.save(path)


def _write_scryfall(path: Path) -> None:
    records = [
        {
            "oracle_id": "oid-cmd",
            "id": "scry-cmd",
            "name": COMMANDER,
            "layout": "normal",
            "mana_cost": "{2}{W}{U}",
            "cmc": 4.0,
            "type_line": "Legendary Creature — Wizard",
            "oracle_text": "Flying",
            "color_identity": ["W", "U"],
            "legalities": {"commander": "legal"},
            "keywords": ["Flying"],
            "produced_mana": [],
        },
        *[
            {
                "oracle_id": f"oid-spell-{index:02d}",
                "id": f"scry-spell-{index:02d}",
                "name": name,
                "layout": "normal",
                "mana_cost": "{2}{W}",
                "cmc": 3.0,
                "type_line": "Creature — Human",
                "oracle_text": "",
                "color_identity": ["W" if index % 2 == 0 else "U"],
                "legalities": {"commander": "legal"},
                "keywords": [],
                "produced_mana": [],
            }
            for index, name in enumerate(CARDS)
        ],
        *[
            {
                "oracle_id": f"oid-land-{idx}",
                "id": f"scry-land-{idx}",
                "name": land,
                "layout": "normal",
                "mana_cost": "",
                "cmc": 0.0,
                "type_line": "Land",
                "oracle_text": "{T}: Add {W} or {U}.",
                "color_identity": ["W", "U"],
                "legalities": {"commander": "legal"},
                "keywords": [],
                "produced_mana": ["W", "U"],
            }
            for idx, land in enumerate(LANDS)
        ],
        {
            "oracle_id": "oid-plains",
            "id": "scry-plains",
            "name": "Plains",
            "layout": "normal",
            "mana_cost": "",
            "cmc": 0.0,
            "type_line": "Basic Land — Plains",
            "oracle_text": "",
            "color_identity": ["W"],
            "legalities": {"commander": "legal"},
            "keywords": [],
            "produced_mana": ["W"],
        },
    ]
    path.write_text(json.dumps(records), encoding="utf-8")


def _write_signals(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "commander_name": COMMANDER,
            "card_name": name,
            "num_decks": 95 - index * 8,
            "potential_decks": 100,
            "synergy": 0.05 * (10 - index),
            "lift": 1.2,
        }
        for index, name in enumerate(CARDS[:9])
    ] + [
        {
            "commander_name": COMMANDER,
            "card_name": land,
            "num_decks": 80 - idx * 20,
            "potential_decks": 100,
            "synergy": 0.1,
            "lift": 1.1,
        }
        for idx, land in enumerate(LANDS)
    ]
    with (folder / "commander_card_signals_1.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "commander_name",
                "card_name",
                "num_decks",
                "potential_decks",
                "synergy",
                "lift",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    global_rows = [
        {
            "card_name": name,
            "fetch_status": "AVAILABLE",
            "num_decks": 1000 * (index + 1),
            "potential_decks": 100000,
            "price_cardmarket": 1.0,
        }
        for index, name in enumerate(CARDS + LANDS)
    ]
    with (folder / "card_global_signals.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "card_name",
                "fetch_status",
                "num_decks",
                "potential_decks",
                "price_cardmarket",
            ],
        )
        writer.writeheader()
        writer.writerows(global_rows)


def _import_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        commander=COMMANDER,
        from_repo=False,
        inventory=str(tmp_path / "collection.xlsx"),
        scryfall=str(tmp_path / "oracle.json"),
        roles=None,
        tagger_roles=None,
        force=False,
        rulings=[],
        signals=[str(tmp_path / "signals")],
        decklists=None,
        decklist_format="edhrec",
        marks=None,
        expect_pool=None,
    )


@pytest.fixture(autouse=True)
def _no_repo_research(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(import_all, "_RESEARCH", tmp_path / "no-research")


@pytest.fixture
def store_dir(tmp_path: Path) -> Iterator[tuple[Path, StudioStore]]:
    _write_workbook(tmp_path / "collection.xlsx")
    _write_scryfall(tmp_path / "oracle.json")
    _write_signals(tmp_path / "signals")
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    res = import_all.run(_import_args(tmp_path), store)
    assert not res["failed"], res
    yield folder, store
    store.close()


def test_schema_creates_tier_snapshot_table_and_count_allowlist(tmp_path: Path) -> None:
    folder = tmp_path / "fresh"
    store = StudioStore.open(folder)
    try:
        assert store.count("tier_snapshot") == 0
        cols = [
            str(row["name"]) for row in store.connection.execute("PRAGMA table_info(tier_snapshot)")
        ]
        assert cols == [
            "commander_name",
            "spec_hash",
            "profile_name",
            "spec_version",
            "data_epoch",
            "created_at",
            "tier_counts_json",
            "component_denominators_json",
            "payload_json",
        ]
    finally:
        store.close()

    # Existing store lacking tier_snapshot gets it automatically on open.
    raw = sqlite3.connect(folder / "studio.sqlite3")
    raw.execute("DROP TABLE tier_snapshot")
    raw.commit()
    raw.close()
    reopened = StudioStore.open(folder)
    try:
        assert reopened.count("tier_snapshot") == 0
    finally:
        reopened.close()


def test_compute_spec_hash_and_epoch_fingerprint_deterministic(
    store_dir: tuple[Path, StudioStore],
) -> None:
    _folder, store = store_dir
    rec = StrengthSettings.recommended()
    h1 = tier_snapshot.compute_spec_hash(rec, True)
    h2 = tier_snapshot.compute_spec_hash(StrengthSettings(), True)
    h_no_layers = tier_snapshot.compute_spec_hash(rec, False)
    h_custom = tier_snapshot.compute_spec_hash(StrengthSettings(bracket="cedh"), True)
    assert len(h1) == 64 and h1 == h2
    assert h_no_layers != h1
    assert h_custom != h1

    ep1 = tier_snapshot.epoch_fingerprint(store)
    assert len(ep1) == 64
    card_row = store.connection.execute("SELECT card_id FROM card LIMIT 1").fetchone()
    assert card_row is not None
    builder.set_mark(store, str(card_row["card_id"]), favorite=True, excluded=False, note="keep")
    ep2 = tier_snapshot.epoch_fingerprint(store)
    assert ep2 == ep1


def test_write_and_read_snapshot_hit_is_pure_without_marks(
    store_dir: tuple[Path, StudioStore],
) -> None:
    _folder, store = store_dir
    spell_id = store.card_id_by_name(CARDS[0])
    assert spell_id is not None
    builder.set_mark(store, spell_id, favorite=True, excluded=True, note="secret owner mark")

    settings = StrengthSettings.recommended()
    written = tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert written["commander_name"] == COMMANDER
    assert written["profile_name"] == "Ausgewogen"
    assert store.count("tier_snapshot") == 1

    raw_payload = str(
        store.connection.execute(
            "SELECT payload_json FROM tier_snapshot WHERE commander_name = ?",
            (COMMANDER,),
        ).fetchone()[0]
    )
    assert "secret owner mark" not in raw_payload
    assert '"favorite"' not in raw_payload
    assert '"excluded"' not in raw_payload

    hit = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    live = strength_view.compute(store, COMMANDER, settings)
    assert hit["snapshot"]["status"] == "HIT"  # type: ignore[index]
    assert hit["snapshot"]["profile_name"] == "Ausgewogen"  # type: ignore[index]
    assert hit["snapshot"]["data_epoch"] == written["data_epoch"]  # type: ignore[index]
    assert hit["tier_counts"] == live["tier_counts"]
    assert hit["tier_counts_by_kind"] == live["tier_counts_by_kind"]
    assert hit["cards"] == live["cards"]

    # Mutating owner marks afterwards must still HIT cleanly.
    builder.set_mark(store, spell_id, favorite=False, excluded=False, note="changed mark")
    hit2 = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert hit2["snapshot"]["status"] == "HIT"  # type: ignore[index]


def test_read_snapshot_stale_on_epoch_change(store_dir: tuple[Path, StudioStore]) -> None:
    _folder, store = store_dir
    settings = StrengthSettings.recommended()
    written = tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")

    # Simulate new signal import / epoch bump without rewriting snapshot.
    src_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, "
            "numerator, denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (COMMANDER, "edhrec_commander_inclusion", CARDS[9], 0.5, 50, 100, src_id),
        )

    res = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    snap = res["snapshot"]
    assert isinstance(snap, dict)
    assert snap["status"] == "STALE"
    assert snap["snapshot_epoch"] == written["data_epoch"]
    assert snap["current_epoch"] != written["data_epoch"]
    assert "Snapshot veraltet, Neuberechnung läuft" in res["notices"]  # type: ignore[operator]

    summary = tier_snapshot.latest_snapshot_summary(store, COMMANDER)
    assert summary is not None
    assert summary["stale"] is True
    assert "cards" not in summary


def test_read_snapshot_stale_on_spec_mismatch(store_dir: tuple[Path, StudioStore]) -> None:
    _folder, store = store_dir
    settings = StrengthSettings.recommended()
    tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")

    # 1) Changed spec_version on same (commander, spec_hash)
    with store.connection as db:
        db.execute(
            "UPDATE tier_snapshot SET spec_version = 'legacy-0' WHERE commander_name = ?",
            (COMMANDER,),
        )
    stale_ver = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert stale_ver["snapshot"]["status"] == "STALE"  # type: ignore[index]
    assert "Snapshot veraltet, Neuberechnung läuft" in stale_ver["notices"]  # type: ignore[operator]

    # 2) Rewrite current snapshot, then query same profile_name with modified settings
    tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    changed = StrengthSettings(bracket="cedh")
    stale_spec = tier_snapshot.read_snapshot(store, COMMANDER, changed, profile_name="Ausgewogen")
    assert stale_spec["snapshot"]["status"] == "STALE"  # type: ignore[index]
    assert "Snapshot veraltet, Neuberechnung läuft" in stale_spec["notices"]  # type: ignore[operator]
    assert stale_spec["settings"]["bracket"] == "cedh"  # type: ignore[index]


def test_read_snapshot_missing_fallback(store_dir: tuple[Path, StudioStore]) -> None:
    _folder, store = store_dir
    with store.connection as db:
        db.execute("DELETE FROM tier_snapshot")
    res = tier_snapshot.read_snapshot(
        store, COMMANDER, StrengthSettings.recommended(), profile_name="Ausgewogen"
    )
    snap = res["snapshot"]
    assert isinstance(snap, dict)
    assert snap["status"] == "MISSING"
    assert "Snapshot veraltet, Neuberechnung läuft" not in res["notices"]  # type: ignore[operator]
    assert len(res["cards"]) == len(CARDS) + len(LANDS) + 2  # type: ignore[arg-type]


def test_import_all_writes_snapshot_and_summary_targets(
    store_dir: tuple[Path, StudioStore],
) -> None:
    _folder, store = store_dir
    assert store.count("tier_snapshot") == 1
    summary = tier_snapshot.latest_snapshot_summary(store, COMMANDER)
    assert summary is not None
    assert summary["commander_name"] == COMMANDER
    assert summary["profile_name"] == "Ausgewogen"
    assert summary["stale"] is False
    assert "cards" not in summary

    counts = summary["tier_counts"]
    assert isinstance(counts, dict)
    assert set(counts) == {"S", "A", "B", "C", "D", "U", "N"}
    assert sum(int(v) for v in counts.values()) == len(CARDS) + len(LANDS) + 2

    by_kind = summary["tier_counts_by_kind"]
    assert isinstance(by_kind, dict)
    assert set(by_kind) == {"spells", "lands"}
    assert sum(int(v) for v in by_kind["lands"].values()) == len(LANDS) + 1

    denoms = summary["component_denominators"]
    assert isinstance(denoms, dict)
    assert "commander_inclusion" in denoms
    assert denoms["commander_inclusion"]["denominator"] == 100
    assert denoms["commander_inclusion"]["covered"] == 11

    assert tier_snapshot.latest_snapshot_summary(store, "Unknown Commander") is None


def test_import_all_result_and_render_include_tier_snapshot(tmp_path: Path) -> None:
    _write_workbook(tmp_path / "collection.xlsx")
    _write_scryfall(tmp_path / "oracle.json")
    _write_signals(tmp_path / "signals")
    store = StudioStore.open(tmp_path / "studio")
    try:
        res = import_all.run(_import_args(tmp_path), store)
        snap = res["tier_snapshot"]
        assert isinstance(snap, dict)
        assert snap["profile_name"] == "Ausgewogen"
        assert "Tier-Snapshot" in import_all.render(res)
    finally:
        store.close()


def test_web_api_strength_uses_snapshot_and_snapshot_endpoint(
    store_dir: tuple[Path, StudioStore],
) -> None:
    folder, store = store_dir
    client = TestClient(create_app(folder))

    # HIT right after import_all
    snap_resp = client.get("/api/strength/snapshot", params={"commander": COMMANDER})
    assert snap_resp.status_code == 200
    snap_json = snap_resp.json()
    assert snap_json["commander_name"] == COMMANDER
    assert snap_json["stale"] is False
    assert "tier_counts" in snap_json
    assert "tier_counts_by_kind" in snap_json
    assert "component_denominators" in snap_json

    post_resp = client.post(
        "/api/strength",
        json={"commander": COMMANDER, "settings": StrengthSettings.recommended().to_dict()},
        headers=HEADER,
    )
    assert post_resp.status_code == 200
    post_json = post_resp.json()
    assert post_json["snapshot"]["status"] == "HIT"

    # Custom settings not matching Ausgewogen snapshot -> MISSING (not STALE)
    custom = StrengthSettings(bracket="cedh").to_dict()
    custom_resp = client.post(
        "/api/strength",
        json={"commander": COMMANDER, "settings": custom},
        headers=HEADER,
    )
    assert custom_resp.status_code == 200
    assert custom_resp.json()["snapshot"]["status"] == "MISSING"

    # Epoch bump -> STALE on both endpoints
    src_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, "
            "numerator, denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (COMMANDER, "edhrec_commander_inclusion", CARDS[9], 0.4, 40, 100, src_id),
        )
    stale_summary = client.get("/api/strength/snapshot", params={"commander": COMMANDER}).json()
    assert stale_summary["stale"] is True
    stale_post = client.post("/api/strength", json={"commander": COMMANDER}, headers=HEADER).json()
    assert stale_post["snapshot"]["status"] == "STALE"
    assert "Snapshot veraltet, Neuberechnung läuft" in stale_post["notices"]


def test_tierliste_js_renders_snapshot_status_without_inline_styles() -> None:
    js_path = Path(tier_snapshot.__file__).resolve().parent / "static" / "tierliste.js"
    script = js_path.read_text(encoding="utf-8")
    assert "result.snapshot" in script
    assert "Snapshot veraltet, Neuberechnung läuft" in script
    assert "Epoche" in script
    assert "Stand" in script
    assert "innerHTML" not in script
    assert "style=" not in script


def test_ranking_check_cli_reports_tier_snapshot(
    store_dir: tuple[Path, StudioStore], capsys: pytest.CaptureFixture[str]
) -> None:
    folder, _store = store_dir
    rc = studio_main(["--data", str(folder), "ranking-check", "--commander", COMMANDER, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tier_snapshot"]["commander_name"] == COMMANDER
    assert payload["tier_snapshot"]["stale"] is False


def test_playgroup_atlas_update_invalidates_snapshot_and_epoch(
    store_dir: tuple[Path, StudioStore],
) -> None:
    _folder, store = store_dir
    settings = StrengthSettings.recommended()
    written = tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    hit = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert hit["snapshot"]["status"] == "HIT"  # type: ignore[index]

    src_id = str(store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
    spell_id = store.card_id_by_name(CARDS[0])
    with store.connection as db:
        db.execute(
            "INSERT INTO playgroup_card_atlas(oracle_id, format_mode, card_id, card_name, slug, "
            "on_curve_pct, source_id, created_at, updated_at) "
            "VALUES (?, 'multiplayer', ?, ?, ?, ?, ?, ?, ?)",
            (
                "oid-spell-00",
                spell_id,
                CARDS[0],
                "snap-spell-00",
                55.0,
                src_id,
                "2026-11-16T00:00:00Z",
                "2026-11-16T00:00:00Z",
            ),
        )
    res_insert = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert res_insert["snapshot"]["status"] == "STALE"  # type: ignore[index]
    assert res_insert["snapshot"]["current_epoch"] != written["data_epoch"]  # type: ignore[index]

    rewritten = tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert (
        tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")[
            "snapshot"
        ]["status"]
        == "HIT"
    )  # type: ignore[index]

    with store.connection as db:
        db.execute(
            "UPDATE playgroup_card_atlas SET on_curve_pct = ?, updated_at = ? WHERE oracle_id = ?",
            (62.5, "2026-11-16T01:00:00Z", "oid-spell-00"),
        )
    res_update = tier_snapshot.read_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    assert res_update["snapshot"]["status"] == "STALE"  # type: ignore[index]
    assert res_update["snapshot"]["current_epoch"] != rewritten["data_epoch"]  # type: ignore[index]


def test_same_second_tiebreak_trimmed_commander_and_bypass_flags(
    store_dir: tuple[Path, StudioStore],
) -> None:
    _folder, store = store_dir
    settings = StrengthSettings.recommended()
    tier_snapshot.write_snapshot(store, COMMANDER, settings, profile_name="Ausgewogen")
    alt = StrengthSettings(bracket="cedh")
    tier_snapshot.write_snapshot(store, COMMANDER, alt, profile_name="CustomLatest")

    # Force identical created_at so SQLite must break tie by rowid DESC.
    with store.connection as db:
        db.execute(
            "UPDATE tier_snapshot SET created_at = '2026-11-16T12:00:00Z' WHERE commander_name = ?",
            (COMMANDER,),
        )
    summary = tier_snapshot.latest_snapshot_summary(store, f"  {COMMANDER}  ")
    assert summary is not None
    assert summary["profile_name"] == "CustomLatest"

    # Bypass flags on an up-to-date snapshot must not falsely claim STALE.
    bypassed = tier_snapshot.read_snapshot(
        store,
        f" {COMMANDER} ",
        settings,
        profile_name="Ausgewogen",
        notices=("custom notice",),
    )
    assert bypassed["snapshot"]["status"] == "BYPASSED"  # type: ignore[index]
    assert "Snapshot veraltet, Neuberechnung läuft" not in bypassed["notices"]  # type: ignore[operator]
    assert "custom notice" in bypassed["notices"]  # type: ignore[operator]
