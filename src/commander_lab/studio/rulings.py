"""Official card rulings (Scryfall rulings bulk) in the Studio store.

A ruling is a public statement of the rules, published with a date and a source (Wizards of the
Coast or Scryfall). The files are JSON lines, one ruling per line (``oracle_id``, ``source``,
``published_at``, ``comment``). The bulk lists only cards that have rulings: a card that is not
in the table has none published, while an empty table means the rulings were never imported
(unknown). An import replaces the rulings of the files it reads (by file name) and keeps the
rulings of other files, so repeating it changes nothing.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

from .store import DataClass, StudioStore, sha256_file

_REQUIRED = ("oracle_id", "published_at", "comment")


class RulingFileReport(TypedDict):
    file: str
    source_id: str
    sha256: str
    rows_read: int
    rows_written: int
    rows_skipped: int
    skipped_reasons: dict[str, int]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def import_rulings(store: StudioStore, paths: Sequence[str | Path]) -> dict[str, object]:
    """Read one or several rulings files; the rulings of each file replace the rulings stored
    from a file of the same name, and the rulings of every other file stay.

    A ruling listed twice in one file (same card, date and text) is kept once. A line that is
    not a JSON object with ``oracle_id``, ``published_at`` and ``comment`` is skipped and
    counted with its reason. A file without any importable ruling is refused and nothing
    changes. One transaction: a failure leaves the earlier rulings in place."""
    files = [Path(path) for path in paths]
    if not files:
        raise ValueError("no rulings file given")
    if len({file.name for file in files}) != len(files):
        raise ValueError("two of the given files have the same name")
    reports: list[RulingFileReport] = []
    fresh: list[tuple[str, str, str, str, str]] = []  # oracle, published, source, comment, source
    with store.connection as db:
        for file in files:
            digest = sha256_file(file)
            source_id = store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=file.name,
                sha256=digest,
                url="https://scryfall.com/docs/api/rulings",
            )
            report: RulingFileReport = {
                "file": file.name,
                "source_id": source_id,
                "sha256": digest,
                "rows_read": 0,
                "rows_written": 0,
                "rows_skipped": 0,
                "skipped_reasons": {},
            }
            collected: dict[tuple[str, str, str], str] = {}
            with file.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    report["rows_read"] += 1
                    reason = _read_line(line, collected)
                    if reason is None:
                        report["rows_written"] += 1
                    else:
                        report["rows_skipped"] += 1
                        reasons = report["skipped_reasons"]
                        reasons[reason] = reasons.get(reason, 0) + 1
            if not collected:
                raise ValueError(
                    f"{file.name}: no ruling in the file; the stored rulings were not changed"
                )
            fresh += [(o, d, src, c, source_id) for (o, d, c), src in collected.items()]
            reports.append(report)
        marks = ",".join("?" * len(files))
        kept = [
            (str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]))
            for r in db.execute(
                "SELECT r.oracle_id, r.published_at, r.ruling_source, r.comment, r.source_id "
                "FROM card_ruling r JOIN source s USING (source_id) "
                f"WHERE s.title NOT IN ({marks}) ORDER BY r.oracle_id, r.ordinal",
                [file.name for file in files],
            )
        ]
        ordered = sorted(
            enumerate([*kept, *fresh]), key=lambda item: (item[1][0], item[1][1], item[0])
        )
        db.execute("DELETE FROM card_ruling")
        ordinals: dict[str, int] = {}
        rows: list[tuple[str, int, str, str, str, str]] = []
        for _, (oracle_id, published_at, ruling_source, comment, source_id) in ordered:
            ordinals[oracle_id] = ordinals.get(oracle_id, 0) + 1
            rows.append(
                (oracle_id, ordinals[oracle_id], published_at, ruling_source, comment, source_id)
            )
        db.executemany(
            "INSERT INTO card_ruling(oracle_id, ordinal, published_at, ruling_source, comment, "
            "source_id) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
    return {
        "files": reports,
        "rulings": len(rows),
        "cards_with_rulings": len(ordinals),
        "rows_skipped": sum(report["rows_skipped"] for report in reports),
    }


def _read_line(line: str, collected: dict[tuple[str, str, str], str]) -> str | None:
    """Add one line to ``collected``; return the reason when the line is skipped."""
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return "NOT_JSON"
    if not isinstance(value, dict):
        return "NOT_AN_OBJECT"
    fields = {name: _text(value.get(name)) for name in _REQUIRED}
    if not all(fields.values()):
        return "FIELD_MISSING"
    key = (fields["oracle_id"], fields["published_at"], fields["comment"])
    if key in collected:
        return "DUPLICATE"
    collected[key] = _text(value.get("source")) or "unknown"
    return None


def rulings_for_card(store: StudioStore, card_id: str) -> dict[str, object]:
    """The rulings of one collection card; ``KeyError`` for an unknown card.

    ``status``: ``NOT_IMPORTED`` (no rulings in the store at all: unknown), ``NONE_PUBLISHED``
    (rulings are imported and the card has none) or ``AVAILABLE``."""
    row = store.connection.execute(
        "SELECT oracle_id FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None:
        raise KeyError(card_id)
    oracle_id = row["oracle_id"]
    found: list[sqlite3.Row] = []
    seen: set[tuple[str, str]] = set()
    if oracle_id:
        for item in store.connection.execute(
            "SELECT published_at, ruling_source, comment FROM card_ruling "
            "WHERE oracle_id = ? ORDER BY ordinal",
            (oracle_id,),
        ):
            key = (str(item["published_at"]), str(item["comment"]))
            if key not in seen:  # the same ruling from two files is shown once
                seen.add(key)
                found.append(item)
    if not oracle_id:
        status = "UNKNOWN"  # without an oracle id the card cannot be looked up at all
    elif found:
        status = "AVAILABLE"
    elif store.count("card_ruling") == 0:
        status = "NOT_IMPORTED"
    else:
        status = "NONE_PUBLISHED"
    return {
        "card_id": card_id,
        "oracle_id": oracle_id,
        "status": status,
        "rulings": [
            {
                "published_at": item["published_at"],
                "source": item["ruling_source"],
                "comment": item["comment"],
            }
            for item in found
        ],
        "data_class": "NORMALIZED_SOURCE",
    }
