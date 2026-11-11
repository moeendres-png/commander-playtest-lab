"""Strict immutable EDHREC event proof and isolated Studio re-import regression."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from commander_lab.studio.edhrec_capture_proof import verify_captures
from commander_lab.studio.importers import import_edhrec_capture_manifest
from commander_lab.studio.store import DataClass, StudioStore

BASE = "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales.json"
OTHER = "https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/blink.json"
RAW = b'{"container":{"json_dict":{"cardlists":[{"cardviews":[{"name":"Sol Ring","num_decks":24,"potential_decks":120,"lift":1.5}]}]}}}'


def _event(root: Path, url: str, raw: bytes = RAW, start: str = "2026-11-11T12:54:59.352Z",
           end: str = "2026-11-11T12:54:59.435Z") -> dict:
    sha = hashlib.sha256(raw).hexdigest()
    eid = "EDHREC_NEW_" + hashlib.sha256((url + "\n" + start + "\n" + sha).encode()).hexdigest()[:24]
    raw_path = "raw/" + eid + ".json"
    meta_path = "observations/" + eid + ".json"
    for sub in ("raw", "observations"):
        (root / sub).mkdir(exist_ok=True)
    (root / raw_path).write_bytes(raw)
    metadata = dict(
        event_id=eid, url=url, http_status=200, request_start_utc=start,
        response_complete_utc=end, raw_response_sha256=sha,
        raw_size_bytes=len(raw), cardlists=1,
        provenance_class="NEW_HTTP_CAPTURE_ONLY",
        automatic_import=False, historical_C079_timestamp_backfilled=False,
    )
    (root / meta_path).write_text(json.dumps(metadata))
    return dict(event_id=eid, url=url, raw=raw_path, metadata=meta_path,
                sha256=sha, observed_utc=end)


def _manifest(root: Path, records: list[dict]) -> Path:
    f = root / "manifest.json"
    f.write_text(json.dumps({"records": records}))
    return f


def test_time_is_not_rewritten_and_unknown_marker_survives_repeat(tmp_path: Path):
    r = _event(tmp_path, BASE)
    manifest = _manifest(tmp_path, [r])
    store = StudioStore.in_memory()
    try:
        first = import_edhrec_capture_manifest(store, manifest, target_comparison_cards={"Missing", "Sol Ring"})
        assert first["events"] == 1
        assert first["unlisted_comparison_cards"] == 1
        ev = store.connection.execute("SELECT * FROM source_capture_event").fetchone()
        assert ev["request_start_utc"] == "2026-11-11T12:54:59.352Z"
        assert ev["response_complete_utc"] == "2026-11-11T12:54:59.435Z"
        assert ev["request_start_utc"] != ev["response_complete_utc"]
        original = store.count("observation")
        import_edhrec_capture_manifest(store, manifest)
        assert store.count("observation") == original
        missing = store.connection.execute(
            "SELECT * FROM observation WHERE card_name='Missing'"
        ).fetchone()
        assert missing["data_class"] == DataClass.UNKNOWN.value
        assert missing["numerator"] is None and missing["denominator"] is None
        assert missing["value"] is None
    finally:
        store.close()


def test_same_raw_sha_is_not_same_http_event(tmp_path: Path):
    a = _event(tmp_path, BASE, start="2026-11-11T12:54:59.352Z",
               end="2026-11-11T12:54:59.435Z")
    b = _event(tmp_path, OTHER, start="2026-11-11T12:55:01.352Z",
               end="2026-11-11T12:55:01.435Z")
    store = StudioStore.in_memory()
    try:
        assert a["sha256"] == b["sha256"]
        result = import_edhrec_capture_manifest(store, _manifest(tmp_path, [a, b]))
        assert result["events"] == 2
        assert store.count("source_capture_event") == 2
        source_ids = [row[0] for row in store.connection.execute(
            "SELECT source_id FROM source_capture_event ORDER BY event_id"
        )]
        assert len(set(source_ids)) == 2
        assert store.count("observation") == 4
        import_edhrec_capture_manifest(store, tmp_path / "manifest.json")
        assert store.count("observation") == 4
    finally:
        store.close()


@pytest.mark.parametrize("change,match", [
    ({"http_status": 403}, "HTTP 200"),
    ({"request_start_utc": "2026-11-11T12:55:59.352Z"}, "Reversed"),
    ({"raw_response_sha256": "f" * 64}, "metadata identity/SHA"),
    ({"historical_C079_timestamp_backfilled": True}, "historical backfill"),
    ({"automatic_import": True}, "review-only"),
])
def test_forged_metadata_fails_closed(tmp_path: Path, change: dict, match: str):
    r = _event(tmp_path, BASE)
    metadata_path = tmp_path / r["metadata"]
    meta = json.loads(metadata_path.read_text())
    meta.update(change)
    metadata_path.write_text(json.dumps(meta))
    store = StudioStore.in_memory()
    try:
        with pytest.raises(ValueError, match=match):
            import_edhrec_capture_manifest(store, _manifest(tmp_path, [r]))
        assert store.count("source_capture_event") == 0
        assert store.count("observation") == 0
    finally:
        store.close()


def test_missing_proof_or_path_traversal_fails_before_write(tmp_path: Path):
    r = _event(tmp_path, BASE)
    r["metadata"] = "../unauthorized.json"
    store = StudioStore.in_memory()
    try:
        with pytest.raises(ValueError, match="outside capture directory"):
            import_edhrec_capture_manifest(store, _manifest(tmp_path, [r]))
        assert store.count("source_capture_event") == 0
    finally:
        store.close()


def test_malformed_count_is_rejected_without_partial_import(tmp_path: Path):
    good = _event(tmp_path, BASE)
    bad_json = b'{"container":{"json_dict":{"cardlists":[{"cardviews":[{"name":"Fake","num_decks":9,"potential_decks":2}]}]}}}'
    bad = _event(tmp_path, OTHER, raw=bad_json, start="2026-11-11T12:55:01.352Z",
                 end="2026-11-11T12:55:01.435Z")
    store = StudioStore.in_memory()
    try:
        with pytest.raises(ValueError, match="exceeds"):
            import_edhrec_capture_manifest(store, _manifest(tmp_path, [good, bad]))
        assert store.count("source_capture_event") == 0
        assert store.count("observation") == 0
    finally:
        store.close()


def test_preexisting_event_id_must_not_change_metadata(tmp_path: Path):
    r = _event(tmp_path, BASE)
    manifest = _manifest(tmp_path, [r])
    store = StudioStore.in_memory()
    try:
        import_edhrec_capture_manifest(store, manifest)
        original = store.count("observation")
        store.connection.execute("UPDATE source_capture_event SET http_status=503")
        store.connection.commit()
        with pytest.raises(ValueError, match="Immutable HTTP event"):
            import_edhrec_capture_manifest(store, manifest)
        assert store.count("observation") == original
        assert store.connection.execute("SELECT http_status FROM source_capture_event").fetchone()[0] == 503
    finally:
        store.close()
