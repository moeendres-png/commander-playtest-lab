"""Validate public EDHREC capture events before writing any Studio database row.

Every timestamp belongs to a *new HTTP request*, never to historical C079.
No external dependencies or network requests.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

URL_RE = re.compile(r"^https://json\.edhrec\.com/pages/commanders/chulane-teller-of-tales(?:/[a-z0-9-]+)?\.json$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EVENT_RE = re.compile(r"^EDHREC_NEW_[0-9a-f]{24}$")


@dataclass(frozen=True)
class VerifiedCapture:
    event_id: str
    url: str
    sha256: str
    request_start_utc: str
    response_complete_utc: str
    raw_bytes: bytes
    parsed: dict[str, Any]
    cardlists_count: int


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not UTC_RE.fullmatch(value):
        raise ValueError(f"{field}: ISO-8601 millisecond UTC-Z timestamp required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid date/time") from exc


def _contained_path(root: Path, name: object, field: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError(f"{field}: relative local file path required")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError(f"{field}: missing or outside capture directory")
    return target


def verify_captures(manifest_path: str | Path, raw_folder: str | Path | None = None) -> list[VerifiedCapture]:
    """Fail closed if any HTTP proof, SHA, source URL or card metric is invalid."""
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    records = manifest.get("records") if isinstance(manifest, dict) else None
    if not isinstance(records, list) or not records or len(records) > 20:
        raise ValueError("Capture manifest must contain 1–20 records")
    root = Path(raw_folder) if raw_folder is not None else manifest_file.parent
    seen_event_ids: set[str] = set()
    seen_urls: set[str] = set()
    out: list[VerifiedCapture] = []

    for rec in records:
        if not isinstance(rec, dict):
            raise ValueError("Capture record must be an object")
        event_id, url, expected_sha = rec.get("event_id"), rec.get("url"), rec.get("sha256")
        if not isinstance(event_id, str) or not EVENT_RE.fullmatch(event_id):
            raise ValueError("Invalid or missing capture event ID")
        if event_id in seen_event_ids:
            raise ValueError(f"Duplicate capture event ID: {event_id}")
        seen_event_ids.add(event_id)
        if not isinstance(url, str) or not URL_RE.fullmatch(url):
            raise ValueError(f"Not an allowed public Chulane EDHREC URL: {url}")
        if url in seen_urls:
            raise ValueError(f"Duplicate URL in one capture batch: {url}")
        seen_urls.add(url)
        if not isinstance(expected_sha, str) or not SHA_RE.fullmatch(expected_sha):
            raise ValueError(f"Invalid SHA-256 in {event_id}")
        raw = _contained_path(root, rec.get("raw"), "raw")
        meta_path = _contained_path(root, rec.get("metadata"), "metadata")
        raw_bytes = raw.read_bytes()
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        if expected_sha != actual_sha:
            raise ValueError(f"SHA-256 mismatch for {event_id}: expected {expected_sha}, got {actual_sha}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            raise ValueError(f"Invalid metadata object in {event_id}")
        identity = {"event_id": event_id, "url": url, "raw_response_sha256": expected_sha}
        if any(meta.get(key) != value for key, value in identity.items()):
            raise ValueError(f"Capture metadata identity/SHA mismatch in {event_id}")
        if type(meta.get("http_status")) is not int or meta["http_status"] != 200:
            raise ValueError(f"HTTP 200 proof missing in {event_id}")
        if meta.get("provenance_class") != "NEW_HTTP_CAPTURE_ONLY":
            raise ValueError(f"Capture provenance classification invalid in {event_id}")
        if meta.get("automatic_import") is not False or meta.get("historical_C079_timestamp_backfilled") is not False:
            raise ValueError(f"Capture is not review-only or claims historical backfill: {event_id}")
        if type(meta.get("raw_size_bytes")) is not int or meta["raw_size_bytes"] != len(raw_bytes):
            raise ValueError(f"Capture size mismatch in {event_id}")
        start = meta.get("request_start_utc")
        end = meta.get("response_complete_utc")
        if _utc(start, "request_start_utc") > _utc(end, "response_complete_utc"):
            raise ValueError(f"Reversed capture UTC times in {event_id}")
        if end != rec.get("observed_utc"):
            raise ValueError(f"Manifest observed_utc != response_complete_utc: {event_id}")
        calculated_event = "EDHREC_NEW_" + hashlib.sha256((url + "\n" + start + "\n" + expected_sha).encode()).hexdigest()[:24]
        if calculated_event != event_id:
            raise ValueError(f"Capture event fingerprint mismatch in {event_id}")
        try:
            parsed = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid raw JSON: {event_id}") from exc
        container = parsed.get("container") if isinstance(parsed, dict) else None
        json_dict = container.get("json_dict") if isinstance(container, dict) else None
        lists = json_dict.get("cardlists") if isinstance(json_dict, dict) else None
        if not isinstance(lists, list):
            raise ValueError(f"Missing EDHREC cardlists: {event_id}")
        if type(meta.get("cardlists")) is not int or meta["cardlists"] != len(lists):
            raise ValueError(f"EDHREC cardlist count mismatch in {event_id}")
        for cl in lists:
            if not isinstance(cl, dict) or not isinstance(cl.get("cardviews"), list):
                raise ValueError(f"Invalid EDHREC cardlist/cardviews in {event_id}")
            for cv in cl["cardviews"]:
                if not isinstance(cv, dict) or not isinstance(cv.get("name"), str) or not cv["name"].strip():
                    raise ValueError(f"Malformed EDHREC cardview in {event_id}")
                for key in ("num_decks", "potential_decks"):
                    if cv.get(key) is not None:
                        value = cv[key]
                        if isinstance(value, bool) or not str(value).isdigit() or int(str(value)) < 0:
                            raise ValueError(f"Invalid nonnegative count {key} in {event_id}")
                num, den = cv.get("num_decks"), cv.get("potential_decks")
                if num is not None and den is not None and int(str(num)) > int(str(den)):
                    raise ValueError(f"num_decks exceeds potential_decks in {event_id}")
                for key in ("lift", "synergy"):
                    if cv.get(key) is not None:
                        try:
                            numeric = float(str(cv[key]))
                        except (ValueError, TypeError) as exc:
                            raise ValueError(f"Malformed {key} in {event_id}") from exc
                        if not math.isfinite(numeric):
                            raise ValueError(f"Nonfinite {key} in {event_id}")
        out.append(VerifiedCapture(event_id, url, expected_sha, start, end, raw_bytes, parsed, len(lists)))
    return out
