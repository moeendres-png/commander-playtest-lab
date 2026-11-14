"""The Owner's own card marks from an export (Refs #1182 G2, #1185).

Favorite, excluded and note are filters and availability conditions for the Owner's own use.
They are never a strength signal: no evidence, rating or tier reads them (see
``evidence.TIER_POLICY``). They stay in the local Studio database; a marks file is private data
and does not belong in the repository.

The import merges. A key that an entry does not mention stays as it is, an entry that cannot be
resolved to a collection card is counted and skipped, and the whole file is checked before
anything is written. Two formats are read:

* ``studio-marks-1``: ``{"format": "studio-marks-1", "marks": [{"card_id": "...",
  "card_name": "...", "favorite": true, "excluded": false, "note": "..."}]}``. ``card_id`` is
  tried first, ``card_name`` is the fallback.
* the export of the old HTML studio (``{"app": "chulane-studio", "state": {...}}``): ``fav``
  and ``notes`` are read; ``wish``, ``variants`` and ``tierOverride`` are counted as ignored
  (``tierOverride`` is a tier value and is deliberately not imported).
"""

from __future__ import annotations

import json
from pathlib import Path

from .store import StudioStore, now_utc

MARKS_FORMAT = "studio-marks-1"
OLD_STUDIO_APP = "chulane-studio"
_IGNORED_OLD_FIELDS = ("wish", "variants", "tierOverride")


def _flag(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValueError(f"{field} must be true or false, not {value!r}")


def _entries(data: object) -> tuple[list[dict[str, object]], dict[str, int]]:
    """The marks of a file as entries with only the keys the file states, plus ignored counts."""
    if not isinstance(data, dict):
        raise ValueError("a marks file is a JSON object")
    entries: list[dict[str, object]] = []
    ignored: dict[str, int] = {}
    if data.get("format") == MARKS_FORMAT:
        marks = data.get("marks")
        if not isinstance(marks, list):
            raise ValueError("'marks' must be a list")
        for item in marks:
            if not isinstance(item, dict):
                raise ValueError("every mark is an object")
            entries.append(item)
        return entries, ignored
    if data.get("app") == OLD_STUDIO_APP and isinstance(data.get("state"), dict):
        state = data["state"]
        if not isinstance(state, dict):
            raise ValueError("'state' must be an object")
        merged: dict[str, dict[str, object]] = {}
        fav = state.get("fav") or {}
        notes = state.get("notes") or {}
        if not isinstance(fav, dict) or not isinstance(notes, dict):
            raise ValueError("'fav' and 'notes' must be objects")
        for card_id, value in fav.items():
            if value:
                merged.setdefault(str(card_id), {})["favorite"] = True
        for card_id, text in notes.items():
            if isinstance(text, str) and text.strip():
                merged.setdefault(str(card_id), {})["note"] = text
        entries = [{"card_id": card_id, **keys} for card_id, keys in merged.items()]
        for field in _IGNORED_OLD_FIELDS:
            value = state.get(field)
            if isinstance(value, dict) and value:
                ignored[field] = len(value)
        return entries, ignored
    raise ValueError(f"not a marks file: expected format {MARKS_FORMAT!r} or the old studio export")


def _label(entry: dict[str, object]) -> str:
    return str(entry.get("card_name") or entry.get("card_id") or "")


def import_owner_marks(
    store: StudioStore, path: str | Path, *, detail: bool = False
) -> dict[str, object]:
    """Merge marks from ``path`` into ``card_mark``. All or nothing; the report holds counts
    only, unless ``detail`` asks for one line per entry: ``IMPORTED`` (applied or already
    stored), ``NOT_FOUND`` (no card of the store), ``CONFLICT`` (card id and name name
    different cards, or the file states different values for one card; nothing of it is
    applied) or ``IGNORED`` (the entry states no mark). Ratings are never touched."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries, ignored = _entries(data)
    plan: list[tuple[int, str, dict[str, object]]] = []
    rows: list[dict[str, object]] = []
    unresolved = 0
    for number, entry in enumerate(entries, start=1):
        keys: dict[str, object] = {}
        if "favorite" in entry:
            keys["favorite"] = _flag(entry["favorite"], "favorite")
        if "excluded" in entry:
            keys["excluded"] = _flag(entry["excluded"], "excluded")
        if "note" in entry:
            note = entry["note"]
            if not isinstance(note, str):
                raise ValueError("note must be text")
            keys["note"] = note
        row: dict[str, object] = {"row": number, "name": _label(entry), "status": "IGNORED"}
        rows.append(row)
        if not keys:
            continue
        by_id: str | None = None
        wanted = str(entry.get("card_id") or "").strip()
        if (
            wanted
            and store.connection.execute(
                "SELECT 1 FROM card WHERE card_id = ?", (wanted,)
            ).fetchone()
        ):
            by_id = wanted
        by_name = store.card_id_by_oracle_or_name(
            None, str(entry.get("card_name") or "").strip() or None
        )
        if by_id is not None and by_name is not None and by_id != by_name:
            row.update(
                status="CONFLICT",
                reason="Kartenkennung und Name zeigen auf verschiedene Karten",
            )
            continue
        card_id = by_id or by_name
        if card_id is None:
            unresolved += 1
            row.update(status="NOT_FOUND", reason="keine Karte dieses Namens im Studio")
            continue
        row["status"] = "IMPORTED"
        plan.append((number, card_id, keys))
    clashing: set[str] = set()
    seen: dict[tuple[str, str], object] = {}
    for _number, card_id, keys in plan:
        for key, value in keys.items():
            if seen.setdefault((card_id, key), value) != value:
                clashing.add(card_id)
    conflicting = [number for number, card_id, _keys in plan if card_id in clashing]
    for number in conflicting:
        rows[number - 1].update(
            status="CONFLICT", reason="die Datei nennt für dieselbe Karte verschiedene Werte"
        )
    plan = [(number, card_id, keys) for number, card_id, keys in plan if card_id not in clashing]
    conflicts = sum(1 for row in rows if row["status"] == "CONFLICT")
    plan_marks = [(card_id, keys) for _number, card_id, keys in plan]

    changed = 0
    with store.connection as db:
        for card_id, keys in plan_marks:
            row = db.execute(
                "SELECT favorite, excluded, note FROM card_mark WHERE card_id = ?", (card_id,)
            ).fetchone()
            before = (0, 0, "") if row is None else (row["favorite"], row["excluded"], row["note"])
            after = (
                int(bool(keys.get("favorite", before[0]))),
                int(bool(keys.get("excluded", before[1]))),
                str(keys.get("note", before[2])),
            )
            if row is not None and after == before:
                continue
            db.execute(
                "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(card_id) DO UPDATE SET "
                "favorite = excluded.favorite, excluded = excluded.excluded, "
                "note = excluded.note, updated_at = excluded.updated_at",
                (card_id, *after, now_utc()),
            )
            changed += 1
    favorites = int(
        store.connection.execute("SELECT COUNT(*) FROM card_mark WHERE favorite = 1").fetchone()[0]
    )
    report: dict[str, object] = {
        "entries": len(entries),
        "resolved": len(plan),
        "unresolved": unresolved,
        "conflicts": conflicts,
        "changed": changed,
        "favorites_after": favorites,
        "ignored_fields": ignored,
    }
    if detail:
        report["rows"] = rows
    return report
