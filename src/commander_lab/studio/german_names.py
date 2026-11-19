"""German printed card names for the deck builder search and the deck list import (#1553).

The names come from the checked-in print data of the collection
(``data/research/deckbuilder_1655/mtgjson_printings_1655_{1..3}.jsonl``, MTGJSON build
2026-11-11, filtered per ``oracle_id``): every print row carries the foreign names that
exist for it, and the German one is read here. Nothing is written to the Studio database
(no table, no schema change): the files are read at the first use and kept in memory, so
the start of the Studio does not pay for them.

A card without a German name in the files has no entry (unknown, never an empty name made
up). A German name that denotes more than one card is reported as such by ``oracle_ids``
(a set with all of them); callers must not pick one of them.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PRINTINGS_DIR = Path(__file__).resolve().parents[3] / "data" / "research" / "deckbuilder_1655"
_PART = re.compile(r"^mtgjson_printings_1655_(\d+)\.jsonl$")
_GERMAN = "German"


def fold_name(name: str) -> str:
    """The lookup key of a card name: composed form, case-folded, single spaces."""
    return " ".join(unicodedata.normalize("NFC", name).casefold().split())


@dataclass(frozen=True)
class GermanNames:
    """German names per card (oracle id) and the reverse lookup."""

    names: dict[str, tuple[str, ...]] = field(default_factory=dict)
    english: dict[str, str] = field(default_factory=dict)
    by_key: dict[str, frozenset[str]] = field(default_factory=dict)

    def names_for(self, oracle_id: object) -> tuple[str, ...] | None:
        """The German names of one card, or ``None`` when the files hold none (unknown)."""
        return self.names.get(str(oracle_id)) if oracle_id else None

    def oracle_ids(self, name: str) -> frozenset[str]:
        """Every card a German name (or one face of a double-faced name) denotes."""
        return self.by_key.get(fold_name(name), frozenset())

    def oracle_name(self, oracle_id: str) -> str | None:
        """The Oracle name the print data gives to ``oracle_id``."""
        return self.english.get(oracle_id)

    @property
    def card_count(self) -> int:
        return len(self.names)


def _part_files(folder: Path) -> list[Path]:
    parts = [(int(m.group(1)), p) for p in folder.glob("*.jsonl") if (m := _PART.match(p.name))]
    return [path for _, path in sorted(parts)]


def _german_names(row: object) -> Iterable[str]:
    if not isinstance(row, dict):
        return
    foreign = row.get("foreign_names")
    if not isinstance(foreign, list):
        return
    for entry in foreign:
        if isinstance(entry, dict) and entry.get("language") == _GERMAN:
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                yield name.strip()


def read_german_names(folder: str | Path) -> GermanNames:
    """Read the print files of ``folder`` in the order of their part numbers.

    A folder without part files, an unreadable file or a damaged line yields fewer names,
    never an error: the German names are an addition to the search, not a requirement."""
    names: dict[str, list[str]] = {}
    english: dict[str, str] = {}
    keys: dict[str, set[str]] = {}
    for path in _part_files(Path(folder)):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            oracle_id, oracle_name = row.get("oracle_id"), row.get("name")
            if not isinstance(oracle_id, str) or not oracle_id:
                continue
            if isinstance(oracle_name, str) and oracle_name:
                english.setdefault(oracle_id, oracle_name)
            for german in _german_names(row):
                known = names.setdefault(oracle_id, [])
                if german not in known:
                    known.append(german)
                keys.setdefault(fold_name(german), set()).add(oracle_id)
                for face in german.split(" // ") if " // " in german else ():
                    keys.setdefault(fold_name(face), set()).add(oracle_id)
    return GermanNames(
        names={oracle_id: tuple(items) for oracle_id, items in names.items()},
        english=english,
        by_key={key: frozenset(ids) for key, ids in keys.items()},
    )


@lru_cache(maxsize=4)
def _cached(folder: str) -> GermanNames:
    return read_german_names(folder)


def load_german_names(folder: str | Path | None = None) -> GermanNames:
    """The German names of the checked-in print data, read once per process."""
    return _cached(str(folder if folder is not None else PRINTINGS_DIR))
