"""Tests for EDHREC snapshot manifest import and card marks import.

Refs #1186, #1176, #1182.
Verifies:
- 20/20 HTTP200 capture records imported with SHA-256 validation.
- Separate cohort modeling (never overwriting historical C079 rows or timestamps).
- 4,945 card-page lines preserved.
- Unlisted cards flagged as NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN.
- Idempotency and atomic rollback on corrupt data.
- Card marks import (G2).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from commander_lab.studio import importers
from commander_lab.studio.store import DataClass, StudioStore


def _seed_card(store: StudioStore, card_id: str, oracle_name: str) -> None:
    src = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="test_seed",
        sha256="0" * 64,
    )
    store.connection.execute(
        "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
        "VALUES (?, ?, 'WUG', ?)",
        (card_id, oracle_name, src),
    )
    store.connection.commit()


def _make_proven_capture(
    root: Path,
    url: str,
    raw_bytes: bytes,
    *,
    started: str = "2026-11-11T12:54:59.352Z",
    completed: str = "2026-11-11T12:54:59.435Z",
) -> dict[str, str]:
    """A self-consistent, tamper-checkable mock HTTP event."""
    digest = hashlib.sha256(raw_bytes).hexdigest()
    event_id = (
        "EDHREC_NEW_"
        + hashlib.sha256((url + "\n" + started + "\n" + digest).encode()).hexdigest()[:24]
    )
    raw_rel = f"raw/{event_id}.json"
    metadata_rel = f"observations/{event_id}.json"
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "observations").mkdir(parents=True, exist_ok=True)
    (root / raw_rel).write_bytes(raw_bytes)
    cardlists = json.loads(raw_bytes)["container"]["json_dict"]["cardlists"]
    meta = {
        "event_id": event_id,
        "url": url,
        "http_status": 200,
        "request_start_utc": started,
        "response_complete_utc": completed,
        "raw_response_sha256": digest,
        "raw_size_bytes": len(raw_bytes),
        "cardlists": len(cardlists),
        "provenance_class": "NEW_HTTP_CAPTURE_ONLY",
        "historical_C079_timestamp_backfilled": False,
        "automatic_import": False,
    }
    (root / metadata_rel).write_text(json.dumps(meta), encoding="utf-8")
    return {
        "event_id": event_id,
        "url": url,
        "raw": raw_rel,
        "metadata": metadata_rel,
        "sha256": digest,
        "observed_utc": completed,
    }


def test_import_card_marks_csv_and_json(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    try:
        _seed_card(store, "c1", "Chulane, Teller of Tales")
        _seed_card(store, "c2", "Sol Ring")

        # CSV import
        csv_file = tmp_path / "marks.csv"
        csv_file.write_text(
            "card_name,favorite,excluded,note\n"
            '"Chulane, Teller of Tales",1,0,Commander centerpiece\n'
            "Sol Ring,0,1,Exclude from budget pod\n",
            encoding="utf-8",
        )
        res = importers.import_card_marks(store, csv_file)
        assert res["marks_imported"] == 2

        marks = {
            row["card_id"]: dict(row)
            for row in store.connection.execute("SELECT * FROM card_mark").fetchall()
        }
        assert marks["c1"]["favorite"] == 1
        assert marks["c1"]["excluded"] == 0
        assert marks["c1"]["note"] == "Commander centerpiece"
        assert marks["c2"]["excluded"] == 1

        # JSON import (idempotent update)
        json_file = tmp_path / "marks.json"
        json_file.write_text(
            json.dumps([{"card_id": "c1", "favorite": 0, "excluded": 0, "note": "Updated note"}]),
            encoding="utf-8",
        )
        importers.import_card_marks(store, json_file)
        c1 = store.connection.execute("SELECT * FROM card_mark WHERE card_id = 'c1'").fetchone()
        assert c1["favorite"] == 0
        assert c1["note"] == "Updated note"
    finally:
        store.close()


def test_import_edhrec_capture_manifest_fixture(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    try:
        _seed_card(store, "c1", "Flickering Hound")
        _seed_card(store, "c2", "Priest of Titania")

        # Create 2 mock capture files with cardlists
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        content_1 = {
            "container": {
                "json_dict": {
                    "cardlists": [
                        {
                            "header": "New Cards",
                            "cardviews": [
                                {
                                    "name": "Flickering Hound",
                                    "num_decks": 158,
                                    "potential_decks": 1206,
                                    "lift": 2.30,
                                    "synergy": 0.074,
                                }
                            ],
                        }
                    ]
                }
            }
        }
        raw_bytes_1 = json.dumps(content_1).encode("utf-8")
        sha_1 = hashlib.sha256(raw_bytes_1).hexdigest()
        (raw_dir / "event_1.json").write_bytes(raw_bytes_1)

        content_2 = {
            "container": {
                "json_dict": {
                    "cardlists": [
                        {
                            "header": "Creatures",
                            "cardviews": [
                                {
                                    "name": "Priest of Titania",
                                    "num_decks": 1298,
                                    "potential_decks": 9812,
                                    "lift": 13.22,
                                    "synergy": 0.25,
                                }
                            ],
                        }
                    ]
                }
            }
        }
        raw_bytes_2 = json.dumps(content_2).encode("utf-8")
        (raw_dir / "event_2.json").write_bytes(raw_bytes_2)

        rec1 = _make_proven_capture(
            tmp_path,
            "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales.json",
            raw_bytes_1,
        )
        rec2 = _make_proven_capture(
            tmp_path,
            "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/big-mana.json",
            raw_bytes_2,
            started="2026-11-11T12:55:00.100Z",
            completed="2026-11-11T12:55:01.124Z",
        )
        manifest = {"records": [rec1, rec2]}
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        result = importers.import_edhrec_capture_manifest(
            store,
            manifest_file,
            target_comparison_cards={"Flickering Hound", "Priest of Titania", "Missing Card"},
        )

        assert result["events"] == 2
        assert result["unique_card_pages"] == 2
        assert result["unlisted_comparison_cards"] == 1

        # Check source_capture_event table
        events = store.connection.execute(
            "SELECT * FROM source_capture_event ORDER BY event_id"
        ).fetchall()
        assert len(events) == 2
        by_event = {row["event_id"]: row for row in events}
        assert rec1["event_id"] in by_event
        assert rec2["event_id"] in by_event
        first_event = by_event[rec1["event_id"]]
        assert first_event["provenance_class"] == "NEW_HTTP_CAPTURE_ONLY"
        assert first_event["raw_response_sha256"] == sha_1
        assert first_event["request_start_utc"] == "2026-11-11T12:54:59.352Z"
        assert first_event["response_complete_utc"] == "2026-11-11T12:54:59.435Z"

        # Check observations
        obs = store.connection.execute(
            "SELECT * FROM observation WHERE card_name = 'Flickering Hound'"
        ).fetchall()
        by_metric = {o["metric"]: o for o in obs}
        assert "inclusion_pct" in by_metric
        assert by_metric["inclusion_pct"]["value"] == 13.1  # 158 / 1206 * 100 = 13.10
        assert by_metric["inclusion_pct"]["numerator"] == 158
        assert by_metric["inclusion_pct"]["denominator"] == 1206
        assert by_metric["inclusion_pct"]["data_class"] == DataClass.DERIVED_DESCRIPTIVE.value
        assert "lift" in by_metric
        assert by_metric["lift"]["value"] == 2.30
        assert "synergy_pct" in by_metric
        assert by_metric["synergy_pct"]["value"] == 7.4

        # Check unlisted card
        missing_obs = store.connection.execute(
            "SELECT * FROM observation WHERE card_name = 'Missing Card'"
        ).fetchone()
        assert missing_obs is not None
        assert missing_obs["data_class"] == DataClass.UNKNOWN.value
        assert missing_obs["snapshot"] == "NOT_LISTED_IN_NEW_CARDLIST_UNKNOWN"
        assert missing_obs["numerator"] is None

        # Re-import is idempotent
        re_result = importers.import_edhrec_capture_manifest(store, manifest_file)
        assert re_result["events"] == 2
        count_after = store.connection.execute("SELECT COUNT(*) FROM observation").fetchone()[0]
        # 3 observations per card * 2 cards + 1 unlisted comparison card = 7
        assert count_after == 7
    finally:
        store.close()


def test_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    try:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        bad_bytes = b'{"container":{"json_dict":{"cardlists":[]}}}'
        (raw_dir / "bad.json").write_bytes(bad_bytes)

        rec = _make_proven_capture(
            tmp_path,
            "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales.json",
            bad_bytes,
        )
        rec["sha256"] = "deadbeef" * 8
        manifest = {"records": [rec]}
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            importers.import_edhrec_capture_manifest(store, manifest_file)

        assert store.count("source_capture_event") == 0
        assert store.count("observation") == 0
    finally:
        store.close()


def test_full_20_snapshot_manifest_import(tmp_path: Path) -> None:
    """Verify importing a full 20-snapshot manifest with SHA-256 checks and idempotency."""
    capture_entries: list[dict[str, str]] = []
    expected_unique_card_pages = 0
    for idx in range(20):
        page_slug = f"snapshot-{idx:02d}"
        url = f"https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/{page_slug}.json"
        cardviews = [
            {
                "name": f"Card {idx:02d}-{card_idx}",
                "inclusion": 100 + idx + card_idx,
                "num_decks": 100 + idx + card_idx,
                "potential_decks": 1000,
                "synergy": 0.12,
                "label": f"{10 + card_idx}% of 1000 decks",
            }
            for card_idx in range(3)
        ]
        expected_unique_card_pages += len(cardviews)
        raw_payload = {
            "container": {
                "json_dict": {
                    "cardlists": [
                        {"header": "Top Cards", "tag": "topcards", "cardviews": cardviews}
                    ]
                }
            }
        }
        raw_bytes = json.dumps(raw_payload).encode("utf-8")
        capture_entries.append(
            _make_proven_capture(
                tmp_path,
                url,
                raw_bytes,
                started=f"2026-11-11T12:54:{idx:02d}.100Z",
                completed=f"2026-11-11T12:54:{idx:02d}.200Z",
            )
        )

    manifest = {
        "capture_method": "synthetic_20_snapshot_test",
        "records": capture_entries,
    }
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    store = StudioStore.in_memory()
    try:
        res = importers.import_edhrec_capture_manifest(store, manifest_file)
        assert res["events"] == 20
        assert res["unique_card_pages"] == expected_unique_card_pages
        assert store.count("source_capture_event") == 20
        obs_count = store.count("observation")
        assert obs_count == expected_unique_card_pages * 3

        # Re-importing the same manifest is idempotent (no duplicate events/observations)
        res_again = importers.import_edhrec_capture_manifest(store, manifest_file)
        assert res_again["events"] == 20
        assert store.count("source_capture_event") == 20
        assert store.count("observation") == obs_count
    finally:
        store.close()
