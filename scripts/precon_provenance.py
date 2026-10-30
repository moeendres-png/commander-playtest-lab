"""Provenance of a precon deck file: REAL (the printed deck) or SYNTHETIC (a variant copy).

A variant copy (the directory ``data/decks/precon_variants/`` held nine of them until repin v14
retired it) replaces cards the engine pin does not know with real, importable cards. It is a test deck, not the printed precon: it says nothing about how the
original plays. Import and sweep reports therefore carry this label per deck and count REAL and
SYNTHETIC decks apart, so a figure such as "186 of 195" is never read as one population.

The marker is the ``deck_id`` prefix (``precon-synthetic/``; ``precon-variant/`` was the prefix of
the first nine copies). The checked-in pool has no such deck since repin v14, so old reports stay
readable and a future replacement set would again be counted apart.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

REAL = "REAL"
SYNTHETIC = "SYNTHETIC"
SYNTHETIC_DECK_ID_PREFIXES = ("precon-synthetic/", "precon-variant/")


def deck_provenance(deck: Mapping[str, object]) -> str:
    """SYNTHETIC for a variant copy (by ``deck_id`` prefix), REAL for everything else."""
    deck_id = str(deck.get("deck_id", ""))
    return SYNTHETIC if deck_id.startswith(SYNTHETIC_DECK_ID_PREFIXES) else REAL


def deck_file_provenance(path: Path) -> str:
    return deck_provenance(json.loads(path.read_text(encoding="utf-8")))


def provenance_by_stem(deck_dir: Path, stems: Iterable[str]) -> dict[str, str]:
    """Provenance of ``deck_dir/<stem>.json`` for each stem."""
    return {stem: deck_file_provenance(deck_dir / f"{stem}.json") for stem in stems}


def provenance_by_path(paths: Mapping[str, Path]) -> dict[str, str]:
    """Provenance of each deck file, keyed by stem."""
    return {stem: deck_file_provenance(path) for stem, path in paths.items()}


def count_by_provenance(labels: Iterable[str]) -> dict[str, int]:
    counts = Counter(labels)
    return {REAL: counts.get(REAL, 0), SYNTHETIC: counts.get(SYNTHETIC, 0)}
