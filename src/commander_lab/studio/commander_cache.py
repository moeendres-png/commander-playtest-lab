"""Local source-versioned cache for one commander legal collection pool.

No inventory details, decks or marks are sent to an external service. Store public
card facts in the cache; live inventory quantities and marks remain authoritative
in SQLite. This file lives outside the repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Sequence

from .store import StudioStore, now_utc

CACHE_SCHEMA = "commander-pool-1"
_SAFE = re.compile(r"[^a-z0-9-]+")


def cache_commander(store: StudioStore, commander_names: Sequence[str]) -> dict[str, object]:
    if not commander_names or len(commander_names) > 2:
        raise ValueError("one or two commander names required")
    db = store.connection
    commander_rows = []
    for name in commander_names:
        row = db.execute(
            "SELECT card_id, oracle_id, oracle_name, color_identity, type_line, "
            "commander_legal FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()
        if row is None:
            raise KeyError(name)
        if row["commander_legal"] != 1:
            raise ValueError(f"Commander legality not verified: {name}")
        if "Legendary Creature" not in str(row["type_line"] or ""):
            note = db.execute(
                "SELECT oracle_text FROM card_fact WHERE card_id = ?", (row["card_id"],)
            ).fetchone()
            if note is None or "can be your commander" not in str(note[0] or "").casefold():
                raise ValueError(f"Not identified as a commander: {name}")
        commander_rows.append(row)
    identity = set().union(*(set(str(r["color_identity"] or "")) for r in commander_rows))
    rows = db.execute(
        "SELECT c.card_id, c.oracle_id, c.oracle_name, c.color_identity, c.mana_cost, "
        "c.mana_value, c.type_line, c.oracle_text, c.commander_legal, "
        "c.image_front, c.image_back, c.fact_source "
        "FROM card_fact c JOIN inventory i USING (card_id) WHERE c.commander_legal = 1 "
        "ORDER BY c.oracle_name"
    )
    cards = [
        dict(row) for row in rows
        if set(str(row["color_identity"] or "")) <= identity
    ]
    sources = [
        dict(r) for r in db.execute(
            "SELECT title, sha256, snapshot_date FROM source ORDER BY source_id"
        )
    ]
    commander_ids = [str(r["oracle_id"] or r["card_id"]) for r in commander_rows]
    material = json.dumps(
        {"schema": CACHE_SCHEMA, "commander_ids": commander_ids, "sources": sources},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
    if store.path is None:
        raise ValueError("cache requires an on-disk store")
    slug = _SAFE.sub("-", str(commander_rows[0]["oracle_name"]).casefold()).strip("-")[:64]
    directory = store.path.parent / "cache" / "commanders"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}-{fingerprint[:20]}.json"
    if not path.exists():
        payload = {
            "schema": CACHE_SCHEMA, "cache_key": fingerprint, "fetched_at": now_utc(),
            "commander_names": list(commander_names),
            "commander_ids": commander_ids,
            "color_identity": "".join(c for c in "WUBRG" if c in identity),
            "data_origin": "LOCAL_INVENTORY_PLUS_PUBLIC_SCRYFALL",
            "public_card_count": len(cards), "cards": cards,
            "source_fingerprints": sources,
            "notice": "Inventory quantities, deck revisions and marks must be queried live",
        }
        temp = path.with_suffix(".tmp")
        try:
            with temp.open("w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    return {
        "path": str(path), "cache_key": fingerprint,
        "commander": list(commander_names), "legal_collection_cards": len(cards)
    }
