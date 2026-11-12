"""Import of card usage signals for the strength index (``strength.py``).

Reads the files of one folder (all optional), keeps every figure keyed by the commander it
was published for, and writes them to ``card_signal``. Nothing here calls a network API.

Files (a large file may be split into ``<name>_1.csv``, ``<name>_2.csv``, ...; every part
has its own header and the parts are read one after another in number order):

- ``commander_card_signals``: per commander and card, EDHREC inclusion (decks with the card
  over decks of the commander) and synergy. The file's lift column is not stored: no
  strength component reads it, and the value stays available in the source file and in
  the observation pipeline.
- ``commander_bracket_signals_<core|upgraded|optimized|cedh>``: the same per bracket page.
- ``card_global_signals``: EDHREC inclusion over all decks (commander independent). Price
  columns of this file are not read.
- ``spellbook_card_links``: number of combo variants a card is part of (commander
  independent). The file's partner count is not stored: no strength component reads it,
  and the value stays available in the source file.
- ``topdeck_chulane_decks``: complete tournament lists of one commander. The player
  column is never read into storage; a list is only counted, per tournament and date.
- ``edhtop16_commander_signals``: per commander and card, the EDHTop16 play rate over
  the ONE_YEAR tournament window; the denominator is the commander's published entry
  count of that window, the per-card deck count is not published and stays NULL.
  Per-card conversion is not published by the source either and is never stored.
  Rows the fetch did not attribute to the commander (``fetch_status`` other than
  AVAILABLE, e.g. the API's global-staples fallback rows) are not imported.

A value the source does not publish is stored as NULL (unknown), never as 0. A card a
source does not list gets no row. When a card is listed under several headings of one
commander page with the same figures, the first row is kept. Re-importing replaces the rows
of each signal and commander the import writes, so the import is idempotent. Source rows of
a commander are never mixed with another commander's.
"""

from __future__ import annotations

import csv
import math
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypedDict

from .store import DataClass, StudioStore, sha256_file

CARD_FILE = "commander_card_signals"
BRACKET_FILE = "commander_bracket_signals"
GLOBAL_FILE = "card_global_signals"
SPELLBOOK_FILE = "spellbook_card_links"
TOURNAMENT_FILE = "topdeck_chulane_decks"
EDHTOP16_FILE = "edhtop16_commander_signals"
BRACKET_VARIANTS = ("core", "upgraded", "optimized", "cedh")
AVAILABLE = "AVAILABLE"
LIST_SECTIONS = frozenset({"main", "commander"})

SIGNAL_INCLUSION = "edhrec_commander_inclusion"
SIGNAL_SYNERGY = "edhrec_commander_synergy"
SIGNAL_BRACKET = "edhrec_bracket_inclusion"
SIGNAL_GLOBAL = "edhrec_global_inclusion"
SIGNAL_VARIANTS = "spellbook_variants"
SIGNAL_TOURNAMENT = "tournament_lists"
SIGNAL_EDHTOP16 = "edhtop16_commander_play_rate"

_Row = tuple[str, str, str, float | None, int | None, int | None]  # commander, signal, card, ...


class FileReport(TypedDict):
    status: str
    parts: list[str]
    rows_read: int
    rows_written: int
    rows_skipped: int
    skipped_reasons: dict[str, int]


def _number(text: str | None) -> float | None:
    if text is None or not text.strip():
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _count(text: str | None) -> int | None:
    value = _number(text)
    if value is None or value < 0 or value != int(value):
        return None
    return int(value)


def _parts(folder: Path, base: str) -> list[Path]:
    """The file ``<base>.csv`` and/or its numbered parts, in number order."""
    found = [folder / f"{base}.csv"] if (folder / f"{base}.csv").is_file() else []
    pattern = re.compile(rf"^{re.escape(base)}_(\d+)\.csv$")
    numbered: list[tuple[int, Path]] = []
    for path in folder.iterdir():
        match = pattern.match(path.name)
        if match and path.is_file():
            numbered.append((int(match.group(1)), path))
    return found + [path for _, path in sorted(numbered)]


def _rows(paths: list[Path], required: set[str]) -> Iterator[dict[str, str]]:
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path.name}: missing column(s) {', '.join(sorted(missing))}")
            for row in reader:
                yield {key: (value or "") for key, value in row.items() if key is not None}


def _share(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0 or numerator > denominator:
        return None
    return numerator / denominator


def _commander_rows(
    row: dict[str, str], commander: str, card: str, variant: str | None
) -> list[_Row]:
    numerator = _count(row.get("num_decks"))
    denominator = _count(row.get("potential_decks"))
    if numerator is None or denominator is None or denominator <= 0 or numerator > denominator:
        numerator = denominator = None
    suffix = f":{variant}" if variant else ""
    inclusion = SIGNAL_BRACKET + suffix if variant else SIGNAL_INCLUSION
    rows: list[_Row] = [
        (commander, inclusion, card, _share(numerator, denominator), numerator, denominator)
    ]
    if not variant:
        rows.append((commander, SIGNAL_SYNERGY, card, _number(row.get("synergy")), None, None))
    return rows


def _first_wins(
    rows: Iterator[tuple[tuple[str, str, str], _Row]], report: FileReport
) -> dict[tuple[str, str, str], _Row]:
    kept: dict[tuple[str, str, str], _Row] = {}
    for key, row in rows:
        if key in kept:
            report["rows_skipped"] += 1
            reason = "DUPLICATE_SAME_FIGURES" if kept[key][3:] == row[3:] else "DUPLICATE_CONFLICT"
            report["skipped_reasons"][reason] = report["skipped_reasons"].get(reason, 0) + 1
            continue
        kept[key] = row
    return kept


def _empty(paths: list[Path]) -> FileReport:
    return {
        "status": "IMPORTED" if paths else "ABSENT",
        "parts": [path.name for path in paths],
        "rows_read": 0,
        "rows_written": 0,
        "rows_skipped": 0,
        "skipped_reasons": {},
    }


def _read_commander_file(paths: list[Path], variant: str | None, report: FileReport) -> list[_Row]:
    required = {"commander_name", "card_name", "num_decks", "potential_decks"}
    required |= set() if variant else {"synergy"}
    if variant:
        required.add("variant")
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        commander, card = row["commander_name"].strip(), row["card_name"].strip()
        if not commander or not card:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["NAME_MISSING"] = (
                report["skipped_reasons"].get("NAME_MISSING", 0) + 1
            )
            continue
        if variant and row["variant"].strip() != variant:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["OTHER_VARIANT"] = (
                report["skipped_reasons"].get("OTHER_VARIANT", 0) + 1
            )
            continue
        for item in _commander_rows(row, commander, card, variant):
            pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _read_independent(
    paths: list[Path],
    required: set[str],
    convert: Callable[[dict[str, str], str], list[_Row]],
    report: FileReport,
) -> list[_Row]:
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        card = row["card_name"].strip()
        if not card:
            report["rows_skipped"] += 1
            continue
        if row["fetch_status"].strip() != AVAILABLE:
            # The source did not deliver this card: unknown, not zero.
            report["rows_skipped"] += 1
            report["skipped_reasons"]["FETCH_STATUS_NOT_AVAILABLE"] = (
                report["skipped_reasons"].get("FETCH_STATUS_NOT_AVAILABLE", 0) + 1
            )
            continue
        for item in convert(row, card):
            pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _global_rows(row: dict[str, str], card: str) -> list[_Row]:
    numerator = _count(row.get("num_decks"))
    denominator = _count(row.get("potential_decks"))
    if numerator is None or denominator is None or denominator <= 0 or numerator > denominator:
        numerator = denominator = None
    return [("", SIGNAL_GLOBAL, card, _share(numerator, denominator), numerator, denominator)]


def _spellbook_rows(row: dict[str, str], card: str) -> list[_Row]:
    return [
        ("", SIGNAL_VARIANTS, card, _number(row.get("variant_count")), None, None),
    ]


def _read_edhtop16(paths: list[Path], report: FileReport) -> list[_Row]:
    """EDHTop16 play rates per commander and card (ONE_YEAR window).

    Only rows the fetch attributed to the commander (``fetch_status``
    AVAILABLE) are imported; the staples answer of the API carries
    global-staples fallback rows for commanders whose own list is
    short, and those rows are not the commander's data. The published
    entry count of the commander is the rate's denominator; how many
    of the entries contain the card is not published, so the numerator
    stays NULL, and per-card conversion is not published at all."""
    required = {"commander_name", "card_name", "play_rate", "entries_n", "fetch_status"}
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        commander, card = row["commander_name"].strip(), row["card_name"].strip()
        if not commander or not card:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["NAME_MISSING"] = (
                report["skipped_reasons"].get("NAME_MISSING", 0) + 1
            )
            continue
        if row["fetch_status"].strip() != AVAILABLE:
            # Not attributed to this commander by the fetch: unknown, not zero.
            report["rows_skipped"] += 1
            report["skipped_reasons"]["FETCH_STATUS_NOT_AVAILABLE"] = (
                report["skipped_reasons"].get("FETCH_STATUS_NOT_AVAILABLE", 0) + 1
            )
            continue
        rate = _number(row.get("play_rate"))
        if rate is None or not 0.0 <= rate <= 1.0:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["PLAY_RATE_INVALID"] = (
                report["skipped_reasons"].get("PLAY_RATE_INVALID", 0) + 1
            )
            continue
        entries = _count(row.get("entries_n"))
        if entries == 0:
            entries = None
        item: _Row = (commander, SIGNAL_EDHTOP16, card, rate, None, entries)
        pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _read_tournament_lists(paths: list[Path], commander: str, report: FileReport) -> list[_Row]:
    """Count, per card, the commander's tournament lists that contain it.

    The player column is not read. Lists are told apart by tournament and date in file
    order; the identity of a list is kept only while the file is read."""
    required = {"tournament", "date", "card_name", "section"}
    lists: dict[tuple[str, str, str], tuple[set[str], set[str]]] = {}
    for row in _rows(paths, required | {"player"}):
        report["rows_read"] += 1
        if row["section"].strip() not in LIST_SECTIONS:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["SECTION_NOT_COUNTED"] = (
                report["skipped_reasons"].get("SECTION_NOT_COUNTED", 0) + 1
            )
            continue
        # The identity is only a grouping key in memory; it is never written.
        identity = (row["tournament"], row["date"], row["player"])
        cards, commanders = lists.setdefault(identity, (set(), set()))
        name = row["card_name"].strip()
        cards.add(name)
        if row["section"].strip() == "commander":
            commanders.add(name)
    valid = [cards for cards, commanders in lists.values() if commander in commanders]
    invalid = len(lists) - len(valid)
    if invalid:
        report["skipped_reasons"]["LIST_OF_OTHER_COMMANDER"] = invalid
    counts: dict[str, int] = {}
    for cards in valid:
        for name in cards:
            counts[name] = counts.get(name, 0) + 1
    total = len(valid)
    return [
        (commander, SIGNAL_TOURNAMENT, name, count / total, count, total)
        for name, count in sorted(counts.items())
    ]


def _store_rows(store: StudioStore, rows: list[_Row], source_id: str) -> int:
    db = store.connection
    pairs = sorted({(row[0], row[1]) for row in rows})
    db.executemany("DELETE FROM card_signal WHERE commander_name = ? AND signal = ?", pairs)
    db.executemany(
        "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, "
        "numerator, denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*row, source_id) for row in rows],
    )
    return len(rows)


def _register(store: StudioStore, paths: list[Path]) -> str | None:
    source_id: str | None = None
    for path in paths:
        registered = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE, title=path.name, sha256=sha256_file(path)
        )
        source_id = source_id or registered
    return source_id


def _read_file(
    file_name: str, paths: list[Path], variant: str | None, commander: str, report: FileReport
) -> list[_Row]:
    if file_name == CARD_FILE or variant is not None:
        return _read_commander_file(paths, variant, report)
    if file_name == GLOBAL_FILE:
        required = {"card_name", "fetch_status", "num_decks", "potential_decks"}
        return _read_independent(paths, required, _global_rows, report)
    if file_name == SPELLBOOK_FILE:
        required = {"card_name", "fetch_status", "variant_count"}
        return _read_independent(paths, required, _spellbook_rows, report)
    if file_name == EDHTOP16_FILE:
        return _read_edhtop16(paths, report)
    return _read_tournament_lists(paths, commander, report)


def import_signals(store: StudioStore, folder: str | Path, *, commander: str) -> dict[str, object]:
    """Import every signal file of ``folder`` (all optional); one report entry per file.

    ``commander`` owns the tournament lists; the EDHREC signals carry their own commander
    column. All files are written in one transaction."""
    root = Path(folder)
    if not root.is_dir():
        raise ValueError(f"not a folder: {root}")
    name = commander.strip()
    if not name:
        raise ValueError("a commander name is required")
    reports: dict[str, FileReport] = {}
    plan: list[tuple[str, str | None]] = [(CARD_FILE, None)]
    plan += [(f"{BRACKET_FILE}_{variant}", variant) for variant in BRACKET_VARIANTS]
    plan += [(GLOBAL_FILE, None), (SPELLBOOK_FILE, None), (TOURNAMENT_FILE, None)]
    plan += [(EDHTOP16_FILE, None)]
    with store.connection:
        for file_name, variant in plan:
            paths = _parts(root, file_name)
            report = _empty(paths)
            reports[file_name] = report
            if not paths:
                continue
            rows = _read_file(file_name, paths, variant, name, report)
            source_id = _register(store, paths)
            if source_id is not None and rows:
                report["rows_written"] = _store_rows(store, rows, source_id)
    return {
        "folder": root.name,
        "tournament_commander": name,
        "files": reports,
        "rows_written": sum(report["rows_written"] for report in reports.values()),
    }
