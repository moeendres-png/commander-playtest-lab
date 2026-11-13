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
- ``topdeck_<name>_decks`` (any file of that shape, one commander per file): complete
  tournament lists. The commander of a file is the one written ALONE in the commander
  section of its lists (the most common one; ``--commander`` breaks a tie); a list counts
  only if its commander section is exactly that commander, lists of a partner pair or
  another commander are skipped and reported (``OTHER_COMMANDER_SET``). All tournament
  files of one import are read first and their lists pooled per commander (the same list
  in two files counts once), then stored once per commander. The player column is
  required because it tells two lists of one tournament and date apart: it is used as an
  in-memory grouping key while the file is read. Its value is never stored, logged or
  reported; a list is only counted, per tournament and date (the dataset carries neutral
  labels "Liste N" there).
- ``edhtop16_commander_signals``: per commander and card, the EDHTop16 play rate over
  the ONE_YEAR tournament window; the denominator is the commander's published entry
  count of that window, the per-card deck count is not published and stays NULL.
  Per-card conversion is not published by the source either and is never stored.
  Rows the fetch did not attribute to the commander (``fetch_status`` other than
  AVAILABLE, e.g. the API's global-staples fallback rows) are not imported.

Commander names of the files are matched against the commander names the store knows
(collection cards, bound decks, stored signals): exactly, else by a unique case-insensitive
match; a name that matches nothing is imported as written and listed in the report as not
recognised, next to the names that were imported.

A value the source does not publish is stored as NULL (unknown), never as 0. A card a
source does not list gets no row. When a card is listed under several headings of one
commander page with the same figures, the first row is kept. Re-importing replaces the rows
of each signal and commander the import writes, so the import is idempotent; a file with no
valid row replaces nothing and the report says so (``NOTHING_REPLACED``, with the number of
existing rows that were kept). Source rows of
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
    rows_replaced: int
    rows_kept: int
    rows_skipped: int
    skipped_reasons: dict[str, int]
    commander: str | None
    lists_read: int  # tournament files: distinct lists read from this file
    pooled_into: str | None  # tournament files: the file that carries the pooled rows stored


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


class _Commanders:
    """Maps the commander names of the files onto the names the store knows.

    Exact match first, else a unique case-insensitive match; anything else is kept as
    written and counted as not recognised. Records what it saw for the report."""

    def __init__(self, store: StudioStore) -> None:
        db = store.connection
        known = {str(row[0]) for row in db.execute("SELECT oracle_name FROM card")}
        known |= {
            str(row[0])
            for row in db.execute("SELECT DISTINCT commander_name FROM commander_binding")
        }
        known |= {
            str(row[0])
            for row in db.execute(
                "SELECT DISTINCT commander_name FROM card_signal WHERE commander_name != ''"
            )
        }
        self._known = known
        self._folded: dict[str, set[str]] = {}
        for name in known:
            self._folded.setdefault(name.casefold(), set()).add(name)
        self.imported: set[str] = set()
        self.not_recognised: set[str] = set()
        self.normalised: dict[str, str] = {}

    def resolve(self, name: str) -> str:
        if name in self._known:
            self.imported.add(name)
            return name
        matches = self._folded.get(name.casefold(), set())
        if len(matches) == 1:
            found = next(iter(matches))
            self.normalised[name] = found
            self.imported.add(found)
            return found
        self.imported.add(name)
        self.not_recognised.add(name)
        return name


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
        "rows_replaced": 0,
        "rows_kept": 0,
        "rows_skipped": 0,
        "skipped_reasons": {},
        "commander": None,
        "lists_read": 0,
        "pooled_into": None,
    }


def _read_commander_file(
    paths: list[Path], variant: str | None, report: FileReport, commanders: _Commanders
) -> list[_Row]:
    required = {"commander_name", "card_name", "num_decks", "potential_decks"}
    required |= set() if variant else {"synergy"}
    if variant:
        required.add("variant")
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        commander, card = row["commander_name"].strip(), row["card_name"].strip()
        if commander and card:
            commander = commanders.resolve(commander)
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


_ListKey = tuple[str, str, str, frozenset[str]]  # tournament, date, player key, main cards


def _read_tournament_lists(
    paths: list[Path], preferred: str, commanders: _Commanders, report: FileReport
) -> tuple[str | None, set[_ListKey]]:
    """The file's commander and the lists that count for it.

    The file's commander is the one written, alone, in the commander section of its lists
    (the most common one; ``preferred`` breaks a tie). A list counts only if its commander
    section is exactly that one card (the exact-set rule of ``universe.resolve_universe``):
    lists of a partner pair or another commander are skipped and reported, never stored under
    a single partner. Commander-section cards are not deck cards. The player column is
    required and read: it is only an in-memory grouping key that tells two lists of one
    tournament and date apart. Its value is never stored, logged or reported."""
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
        identity = (row["tournament"], row["date"], row["player"])
        cards, listed_commanders = lists.setdefault(identity, (set(), set()))
        name = row["card_name"].strip()
        if row["section"].strip() == "commander":
            listed_commanders.add(name)
        else:
            cards.add(name)
    report["lists_read"] = len(lists)
    reasons = report["skipped_reasons"]
    empty = sum(1 for _cards, listed in lists.values() if not listed)
    multiple = sum(1 for _cards, listed in lists.values() if len(listed) > 1)
    if empty:
        reasons["NO_COMMANDER_SECTION"] = empty
    if multiple:
        reasons["OTHER_COMMANDER_SET"] = multiple
    votes: dict[str, int] = {}
    for _cards, listed in lists.values():
        if len(listed) == 1:
            (name,) = listed
            votes[name] = votes.get(name, 0) + 1
    if not votes:
        return None, set()
    most = max(votes.values())
    leaders = sorted(name for name, count in votes.items() if count == most)
    chosen = preferred if preferred in leaders else leaders[0]
    commander = commanders.resolve(chosen)
    report["commander"] = commander
    valid: set[_ListKey] = {
        (identity[0], identity[1], identity[2], frozenset(cards))
        for identity, (cards, listed) in lists.items()
        if listed == {chosen}
    }
    other = sum(1 for _cards, listed in lists.values() if len(listed) == 1 and chosen not in listed)
    if other:
        reasons["LIST_OF_OTHER_COMMANDER"] = other
    return commander, valid


def _tournament_signal_rows(commander: str, lists: set[_ListKey]) -> list[_Row]:
    counts: dict[str, int] = {}
    for _tournament, _date, _player, cards in lists:
        for name in cards:
            counts[name] = counts.get(name, 0) + 1
    total = len(lists)
    return [
        (commander, SIGNAL_TOURNAMENT, name, count / total, count, total)
        for name, count in sorted(counts.items())
    ]


def _store_rows(store: StudioStore, rows: list[_Row], source_id: str) -> tuple[int, int]:
    """Replace the rows of every (commander, signal) pair of ``rows``; returns (rows written,
    existing rows that were replaced)."""
    db = store.connection
    pairs = sorted({(row[0], row[1]) for row in rows})
    replaced = 0
    for pair in pairs:
        replaced += int(
            db.execute(
                "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal = ?", pair
            ).fetchone()[0]
        )
    db.executemany("DELETE FROM card_signal WHERE commander_name = ? AND signal = ?", pairs)
    db.executemany(
        "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, "
        "numerator, denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*row, source_id) for row in rows],
    )
    return len(rows), replaced


def _register(store: StudioStore, paths: list[Path]) -> str | None:
    source_id: str | None = None
    for path in paths:
        registered = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE, title=path.name, sha256=sha256_file(path)
        )
        source_id = source_id or registered
    return source_id


def _file_signals(file_name: str, variant: str | None) -> list[str]:
    """The stored signals a file writes (the bracket files write one signal per variant)."""
    if variant is not None:
        return [f"{SIGNAL_BRACKET}:{variant}"]
    if file_name == CARD_FILE:
        return [SIGNAL_INCLUSION, SIGNAL_SYNERGY]
    if file_name == GLOBAL_FILE:
        return [SIGNAL_GLOBAL]
    if file_name == SPELLBOOK_FILE:
        return [SIGNAL_VARIANTS]
    if file_name == EDHTOP16_FILE:
        return [SIGNAL_EDHTOP16]
    return [SIGNAL_TOURNAMENT]


def _kept_rows(store: StudioStore, signals_written: list[str], commander: str | None) -> int:
    """Existing rows a file with no valid row leaves untouched: those of its signals (for the
    commander of a tournament file, for all commanders otherwise)."""
    marks = ", ".join("?" for _ in signals_written)
    sql = f"SELECT COUNT(*) FROM card_signal WHERE signal IN ({marks})"
    params: list[str] = list(signals_written)
    if commander is not None:
        sql += " AND commander_name = ?"
        params.append(commander)
    return int(store.connection.execute(sql, params).fetchone()[0])


def _read_file(
    file_name: str,
    paths: list[Path],
    variant: str | None,
    report: FileReport,
    commanders: _Commanders,
) -> list[_Row]:
    if file_name == CARD_FILE or variant is not None:
        return _read_commander_file(paths, variant, report, commanders)
    if file_name == GLOBAL_FILE:
        required = {"card_name", "fetch_status", "num_decks", "potential_decks"}
        return _read_independent(paths, required, _global_rows, report)
    if file_name == SPELLBOOK_FILE:
        required = {"card_name", "fetch_status", "variant_count"}
        return _read_independent(paths, required, _spellbook_rows, report)
    if file_name == EDHTOP16_FILE:
        return _read_edhtop16(paths, report)
    raise ValueError(f"not a per-file signal: {file_name}")


_TOURNAMENT_PATTERN = re.compile(r"^(topdeck_.+_decks)(?:_(\d+))?\.csv$")


def _tournament_bases(folder: Path) -> list[str]:
    """Base names of every tournament file of the folder: ``topdeck_<name>_decks`` (with or
    without numbered parts), in name order. The legacy name is always planned, so an absent
    file is still reported as ABSENT."""
    found = {TOURNAMENT_FILE}
    for path in folder.iterdir():
        match = _TOURNAMENT_PATTERN.match(path.name)
        if match and path.is_file():
            found.add(match.group(1))
    return sorted(found)


def _import_tournaments(
    store: StudioStore,
    root: Path,
    preferred: str,
    commanders: _Commanders,
    reports: dict[str, FileReport],
) -> None:
    """Read ALL tournament files first, pool their lists per commander, store each commander
    once. A list is (tournament, date, player key, cards); the same list read from two files
    counts once. ``rows_written``/``rows_replaced`` sit on the first file of the commander and
    are what was stored / what existed before this import; the other files of the commander
    name that file in ``pooled_into``."""
    pooled: dict[str, set[_ListKey]] = {}
    carriers: dict[str, str] = {}
    members: dict[str, list[str]] = {}
    source_ids: dict[str, str | None] = {}
    for base in _tournament_bases(root):
        paths = _parts(root, base)
        report = _empty(paths)
        reports[base] = report
        if not paths:
            continue
        commander, lists = _read_tournament_lists(paths, preferred, commanders, report)
        source_ids[base] = _register(store, paths)
        if commander is not None:
            pooled.setdefault(commander, set()).update(lists)
            carriers.setdefault(commander, base)
            members.setdefault(commander, []).append(base)
    written: set[str] = set()
    for commander, lists in pooled.items():
        rows = _tournament_signal_rows(commander, lists)
        source_id = source_ids[carriers[commander]]
        if source_id is None or not rows:
            continue
        stored, replaced = _store_rows(store, rows, source_id)
        carrier = reports[carriers[commander]]
        carrier["rows_written"], carrier["rows_replaced"] = stored, replaced
        written.add(commander)
        for base in members[commander][1:]:
            reports[base]["pooled_into"] = carriers[commander]
    for report in reports.values():
        if report["status"] == "ABSENT" or (report["commander"] in written):
            continue
        report["status"] = "NOTHING_REPLACED"
        report["rows_kept"] = _kept_rows(
            store, [SIGNAL_TOURNAMENT], report["commander"] or preferred
        )


def import_signals(store: StudioStore, folder: str | Path, *, commander: str) -> dict[str, object]:
    """Import every signal file of ``folder`` (all optional); one report entry per file.

    The EDHREC signals carry their own commander column; every ``topdeck_*_decks`` file
    belongs to the commander written in its commander section, ``commander`` breaks a tie
    between commanders of equal count. All files are written in one transaction.

    The report is truthful about what changed: per file ``rows_written`` and
    ``rows_replaced`` (existing rows of the same commander and signal that were swapped for
    the new ones) and, when a file had no valid row, ``status`` ``NOTHING_REPLACED`` with
    ``rows_kept``, the existing rows that stayed. ``commanders_imported`` and
    ``commanders_not_recognised`` list the commander names of the import."""
    root = Path(folder)
    if not root.is_dir():
        raise ValueError(f"not a folder: {root}")
    name = commander.strip()
    if not name:
        raise ValueError("a commander name is required")
    reports: dict[str, FileReport] = {}
    plan: list[tuple[str, str | None]] = [(CARD_FILE, None)]
    plan += [(f"{BRACKET_FILE}_{variant}", variant) for variant in BRACKET_VARIANTS]
    plan += [(GLOBAL_FILE, None), (SPELLBOOK_FILE, None)]
    plan += [(EDHTOP16_FILE, None)]
    commanders = _Commanders(store)
    preferred = commanders.resolve(name)
    commanders.imported.discard(preferred)  # only commanders the files name are "imported"
    commanders.not_recognised.discard(name)
    with store.connection:
        _import_tournaments(store, root, preferred, commanders, reports)
        for file_name, variant in plan:
            paths = _parts(root, file_name)
            report = _empty(paths)
            reports[file_name] = report
            if not paths:
                continue
            independent = (CARD_FILE, GLOBAL_FILE, SPELLBOOK_FILE, EDHTOP16_FILE)
            base = file_name if file_name in independent else None
            kind = base or BRACKET_FILE
            rows = _read_file(kind, paths, variant, report, commanders)
            source_id = _register(store, paths)
            if source_id is not None and rows:
                written, replaced = _store_rows(store, rows, source_id)
                report["rows_written"], report["rows_replaced"] = written, replaced
            else:
                report["status"] = "NOTHING_REPLACED"
                report["rows_kept"] = _kept_rows(store, _file_signals(kind, variant), None)
    return {
        "folder": root.name,
        "tournament_commander": preferred,
        "files": reports,
        "rows_written": sum(report["rows_written"] for report in reports.values()),
        "rows_replaced": sum(report["rows_replaced"] for report in reports.values()),
        "rows_kept": sum(report["rows_kept"] for report in reports.values()),
        "commanders_imported": sorted(commanders.imported),
        "commanders_not_recognised": sorted(commanders.not_recognised),
        "commanders_normalised": [
            {"from": raw, "to": found} for raw, found in sorted(commanders.normalised.items())
        ],
    }
