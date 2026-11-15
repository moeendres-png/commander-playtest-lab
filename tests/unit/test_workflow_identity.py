from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _replace_hash(
    rows: tuple[tuple[str, str], ...], key: str, value: str
) -> tuple[tuple[str, str], ...]:
    payload = dict(rows)
    payload[key] = value
    return tuple(sorted(payload.items()))
