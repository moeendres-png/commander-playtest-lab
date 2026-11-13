"""Official card rulings (Scryfall rulings bulk) in the Studio store.

A ruling is a public statement of the rules, published with a date and a source (Wizards of the
Coast or Scryfall). The files are JSON lines, one ruling per line (``oracle_id``, ``source``,
``published_at``, ``comment``). The bulk lists only cards that have rulings: a card that is not
in the table has none published, while an empty table means the rulings were never imported
(unknown). An import replaces the rulings of the files it reads (by file name); every ruling
remembers which files provide it (``card_ruling_source``), so a ruling listed by two files
stays as long as one of them still provides it, and repeating an import changes nothing.
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
    rows_linked: int
    rows_skipped: int
    skipped_reasons: dict[str, int]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def import_rulings(store: StudioStore, paths: Sequence[str | Path]) -> dict[str, object]:
    """Read one or several rulings files; the rulings of each file replace the rulings stored
    from a file of the same name.

    Every ruling remembers the files that provide it (``card_ruling_source``): replacing a
    file removes exactly the rulings no other imported file still provides, so a ruling
    listed by two files survives replacing one of them. In the per-file report,
    ``rows_written`` counts ruling rows this file created and ``rows_linked`` counts rulings
    that were already stored from another file and only gained this file as one more
    provider. A ruling listed twice in one file (same card, date and text) is kept once. A
    line that is not a JSON object with ``oracle_id``, ``published_at`` and ``comment`` is
    skipped and counted with its reason. A file without any importable ruling is refused and
    nothing changes. One transaction: a failure leaves the earlier rulings in place."""
    files = [Path(path) for path in paths]
    if not files:
        raise ValueError("no rulings file given")
    if len({file.name for file in files}) != len(files):
        raise ValueError("two of the given files have the same name")
    rows_before = store.count("card_ruling")
    reports: list[RulingFileReport] = []
    current_ids: list[str] = []
    with store.connection as db:
        for file in files:
            digest = sha256_file(file)
            source_id = store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=file.name,
                sha256=digest,
                url="https://scryfall.com/docs/api/rulings",
            )
            current_ids.append(source_id)
            report: RulingFileReport = {
                "file": file.name,
                "source_id": source_id,
                "sha256": digest,
                "rows_read": 0,
                "rows_written": 0,
                "rows_linked": 0,
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
                    if reason is not None:
                        report["rows_skipped"] += 1
                        reasons = report["skipped_reasons"]
                        reasons[reason] = reasons.get(reason, 0) + 1
            if not collected:
                raise ValueError(
                    f"{file.name}: no ruling in the file; the stored rulings were not changed"
                )
            next_ordinal: dict[str, int] = {}
            for (oracle_id, published_at, comment), ruling_source in collected.items():
                key = (oracle_id, published_at, comment)
                stored = db.execute(
                    "SELECT 1 FROM card_ruling WHERE oracle_id = ? AND published_at = ? "
                    "AND comment = ?",
                    key,
                ).fetchone()
                if stored is None:
                    if oracle_id not in next_ordinal:
                        top = db.execute(
                            "SELECT COALESCE(MAX(ordinal), 0) FROM card_ruling WHERE oracle_id = ?",
                            (oracle_id,),
                        ).fetchone()
                        next_ordinal[oracle_id] = int(top[0])
                    next_ordinal[oracle_id] += 1
                    db.execute(
                        "INSERT INTO card_ruling(oracle_id, ordinal, published_at, "
                        "ruling_source, comment, source_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            oracle_id,
                            next_ordinal[oracle_id],
                            published_at,
                            ruling_source,
                            comment,
                            source_id,
                        ),
                    )
                    report["rows_written"] += 1
                link = db.execute(
                    "INSERT OR IGNORE INTO card_ruling_source(oracle_id, published_at, "
                    "comment, source_id) VALUES (?, ?, ?, ?)",
                    (*key, source_id),
                )
                if stored is not None and link.rowcount:
                    report["rows_linked"] += 1
            reports.append(report)
        # The older versions of the re-read files (same title, other content) lose their
        # provenance links; a ruling no imported file provides any more goes with them. The
        # replaced source rows stay in ``source`` as provenance.
        names = [file.name for file in files]
        marks_names = ",".join("?" * len(names))
        marks_ids = ",".join("?" * len(current_ids))
        db.execute(
            "DELETE FROM card_ruling_source WHERE source_id IN (SELECT source_id FROM source "
            f"WHERE title IN ({marks_names}) AND source_id NOT IN ({marks_ids}))",
            [*names, *current_ids],
        )
        db.execute(
            "DELETE FROM card_ruling WHERE NOT EXISTS (SELECT 1 FROM card_ruling_source s "
            "WHERE s.oracle_id = card_ruling.oracle_id "
            "AND s.published_at = card_ruling.published_at AND s.comment = card_ruling.comment)"
        )
        # The ordinal presents a card's rulings in publication order: renumber by date
        # (the old ordinal breaks a same-day tie, so the order is stable across imports).
        # The offset keeps the (oracle_id, ordinal) key free while the numbers are written.
        stored_rows = db.execute(
            "SELECT oracle_id, published_at, ordinal FROM card_ruling "
            "ORDER BY oracle_id, published_at, ordinal"
        ).fetchall()
        counters: dict[str, int] = {}
        renumbered: list[tuple[int, str, int]] = []
        for oracle_id, _published_at, ordinal in stored_rows:
            counters[oracle_id] = counters.get(oracle_id, 0) + 1
            renumbered.append((counters[oracle_id], oracle_id, ordinal))
        if any(new != old for new, _oracle, old in renumbered):
            db.execute("UPDATE card_ruling SET ordinal = ordinal + 1000000")
            db.executemany(
                "UPDATE card_ruling SET ordinal = ? WHERE oracle_id = ? AND ordinal = ?",
                [(new, oracle, old + 1000000) for new, oracle, old in renumbered],
            )
    cards = store.connection.execute("SELECT COUNT(DISTINCT oracle_id) FROM card_ruling").fetchone()
    return {
        "files": reports,
        "rows_before": rows_before,
        "rulings": store.count("card_ruling"),
        "cards_with_rulings": int(cards[0]),
        "rows_skipped": sum(report["rows_skipped"] for report in reports),
        "rows_linked": sum(report["rows_linked"] for report in reports),
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
    (rulings are imported and the card has none), ``AVAILABLE`` (the card has rulings) or
    ``UNKNOWN`` (the card has no oracle id, so it cannot be looked up at all)."""
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
