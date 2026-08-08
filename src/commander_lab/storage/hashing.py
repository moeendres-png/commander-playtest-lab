from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from commander_lab.cards.normalize import oracle_lookup_key
from commander_lab.models import Deck, DeckZone

CANONICAL_JSON_VERSION = 1


def _canonicalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python", exclude_none=True))
    if is_dataclass(value):
        return _canonicalize(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_canonicalize(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def canonical_json_bytes(value: Any) -> bytes:
    envelope = {
        "canonical_json_version": CANONICAL_JSON_VERSION,
        "payload": _canonicalize(value),
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def compute_deck_hash(deck: Deck) -> str:
    grouped: dict[tuple[str, str], int] = {}
    for entry in deck.cards:
        if entry.zone in {DeckZone.SIDEBOARD, DeckZone.MAYBEBOARD}:
            continue
        key = (oracle_lookup_key(entry.oracle_name), entry.zone.value)
        grouped[key] = grouped.get(key, 0) + entry.quantity
    payload = {
        "format": deck.format.casefold(),
        "commanders": sorted(oracle_lookup_key(name) for name in deck.commander.commanders),
        "uses_partner": deck.commander.uses_partner,
        "cards": [
            {"name": name, "zone": zone, "quantity": quantity}
            for (name, zone), quantity in sorted(grouped.items())
        ],
    }
    return sha256_value(payload)


def compute_data_snapshot_hash(
    paths: Iterable[str | Path], *, root: str | Path | None = None
) -> str:
    root_path = Path(root).resolve() if root is not None else None
    records: list[dict[str, str | int]] = []
    for input_path in sorted((Path(path).resolve() for path in paths), key=str):
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        relative = input_path.relative_to(root_path).as_posix() if root_path else input_path.name
        raw = input_path.read_bytes()
        records.append(
            {
                "path": relative,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return sha256_value(records)


def compute_scenario_hash(value: Any) -> str:
    return sha256_value(value)
