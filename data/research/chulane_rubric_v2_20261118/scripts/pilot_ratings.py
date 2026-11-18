"""Reads ``pilot_ratings.jsonl`` (one rating per line) for the pilot scripts.

Each line holds the rater content plus ``rater``, ``rater_tier`` (``small`` for H1, H2, ``large``
for S1, S2, T1, T2, F1), ``batch``, ``retest`` and ``version`` (``v2`` for H1, H2, S1, S2; ``v2.1``
for T1, T2).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATINGS = ROOT / "pilot_ratings.jsonl"


def load_rows(path: Path = RATINGS, version: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if version is None or r["version"] == version]


def split_by_rater(rows: list[dict], rater: str) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (first ratings, retest ratings) of one rater, each keyed by card name."""
    first: dict[str, dict] = {}
    retest: dict[str, dict] = {}
    for row in rows:
        if row["rater"] == rater:
            (retest if row["retest"] else first)[row["card"]] = row
    return first, retest
