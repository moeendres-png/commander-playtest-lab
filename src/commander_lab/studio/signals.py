"""Import of card usage signals for the strength index (``strength.py``).

Reads the files of one folder (all optional), keeps every figure keyed by the commander it
was published for, and writes them to ``card_signal``. Nothing here calls a network API.

Files (a large file may be split into ``<name>_1.csv``, ``<name>_2.csv``, ...; every part
has its own header and the parts are read one after another in number order; a file with a
byte order mark is read as well):

- ``commander_card_signals``: per commander and card, EDHREC inclusion (decks with the card
  over decks of the commander) and synergy. The file's lift column is not stored: no
  strength component reads it, and the value stays available in the source file and in
  the observation pipeline.
- ``commander_bracket_signals_<core|upgraded|optimized|cedh>``: the same per bracket page.
- ``card_global_signals``: EDHREC inclusion over all decks (commander independent). Price
  columns and the salt column of this file are not read.
- ``spellbook_card_links``: number of combo variants a card is part of (commander
  independent). The file's partner count is not stored: no strength component reads it,
  and the value stays available in the source file.
- ``topdeck_<commander>_decks``: complete tournament lists of one commander. The player
  column is never read into storage; a list is only counted, per tournament and date.
  The file of the commander is found by its name (``chulane`` or ``chulane_teller_of_tales``)
  unless ``tournament_file`` names it.
- ``edhtop16_commander_signals``: per commander and card, the EDHTop16 play rate over
  the ONE_YEAR tournament window; the denominator is the commander's published entry
  count of that window, the per-card deck count is not published and stays NULL.
  Per-card conversion is not published by the source either and is never stored.
  Rows the fetch did not attribute to the commander (``fetch_status`` other than
  AVAILABLE, e.g. the API's global-staples fallback rows) are not imported.
- ``edhrec_salt``: the published EDHREC salt top list (commander independent). A card that is
  not on the list has no row: its salt is unknown, not zero.
- ``edhrec_<commander>_combos``: the combo lists EDHREC shows for one commander, with the
  number of decks of each. Per card: ``numerator`` is the number of listed combos the card
  is part of, ``value`` the largest deck count among them. Observed combos; they are kept
  apart from the verified Spellbook variants.

A value the source does not publish is stored as NULL (unknown), never as 0, and the reason is
counted in ``null_value_reasons``. A card a source does not list gets no row. When a card is
listed under several headings of one commander page with the same figures, the first row is
kept; with different figures the first row is kept as well and the conflict is reported.

Re-importing in the default mode (``replace``) replaces the rows of each signal and commander
the import writes, so the import is idempotent. ``replace=False`` (append) only adds and updates
the rows it reads. Rows of the same signals that remain from other source files are counted in
``stale_rows``. A present file that yields no row is reported as ``NO_ROWS`` and changes
nothing. Source rows of a commander are never mixed with another commander's; commander names
are matched case-insensitively against the names the store already knows.
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
SALT_FILE = "edhrec_salt"
COMBOS_FILE = "edhrec_chulane_combos"
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
SIGNAL_SALT = "edhrec_salt"
SIGNAL_COMBO_DECKS = "edhrec_combo_decks"

STATUS_IMPORTED = "IMPORTED"
STATUS_NO_ROWS = "NO_ROWS"
STATUS_ABSENT = "ABSENT"

# commander, signal, card, value, numerator, denominator
_Row = tuple[str, str, str, float | None, int | None, int | None]
_Key = tuple[str, str, str]
_Kept = dict[_Key, tuple[_Row, int]]  # row and the index of the file part it was read from


class SourceRef(TypedDict):
    file: str
    source_id: str
    sha256: str


class FileReport(TypedDict):
    status: str
    parts: list[str]
    sources: list[SourceRef]
    rows_read: int
    rows_written: int
    rows_skipped: int
    skipped_reasons: dict[str, int]
    null_value_reasons: dict[str, int]
    rows_replaced: int
    stale_rows: int
    warnings: list[str]


def _count_reason(table: dict[str, int], reason: str) -> None:
    table[reason] = table.get(reason, 0) + 1


def _skip(report: FileReport, reason: str) -> None:
    report["rows_skipped"] += 1
    _count_reason(report["skipped_reasons"], reason)


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


def _rows(paths: list[Path], required: set[str]) -> Iterator[tuple[int, dict[str, str]]]:
    for index, path in enumerate(paths):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path.name}: missing column(s) {', '.join(sorted(missing))}")
            for row in reader:
                yield index, {key: (value or "") for key, value in row.items() if key is not None}


def slug(name: str) -> str:
    """File-name form of a commander name: lower case, words joined by ``_``, hyphens kept."""
    return re.sub(r"[^a-z0-9-]+", "_", name.casefold()).strip("_")


def _file_candidates(commander: str, pattern: str) -> list[str]:
    """Base names ``pattern`` can take for ``commander``: by the name before the comma
    (``chulane``) and by the full name (``chulane_teller_of_tales``)."""
    short = slug(commander.split(",")[0])
    full = slug(commander)
    return [pattern.format(short), *([pattern.format(full)] if full != short else [])]


def _known_commander_names(store: StudioStore, extra: list[str]) -> dict[str, str]:
    """Spellings of commander names the store knows, by case-folded name; bound names first."""
    names: dict[str, str] = {}
    queries = (
        "SELECT DISTINCT commander_name FROM commander_binding ORDER BY 1",
        "SELECT DISTINCT commander_name FROM card_signal WHERE commander_name != '' ORDER BY 1",
        "SELECT DISTINCT oracle_name FROM card ORDER BY 1",
    )
    for sql in queries:
        for row in store.connection.execute(sql):
            names.setdefault(str(row[0]).casefold(), str(row[0]))
    for name in extra:
        names.setdefault(name.casefold(), name)
    return names


def resolve_commander_name(store: StudioStore, commander: str) -> str:
    """The spelling of ``commander`` the store already uses (matched case-insensitively against
    the names source data is bound to, the stored signals and the collection); the name as given
    when the store does not know it."""
    name = commander.strip()
    if not name:
        raise ValueError("a commander name is required")
    return _known_commander_names(store, []).get(name.casefold(), name)


def _canonical(known: dict[str, str]) -> Callable[[str], str]:
    """Spelling of a commander name inside one import: the known one, else the first seen."""

    def canon(name: str) -> str:
        return known.setdefault(name.casefold(), name)

    return canon


def _share(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0 or numerator > denominator:
        return None
    return numerator / denominator


def _deck_counts(row: dict[str, str], report: FileReport) -> tuple[int | None, int | None]:
    """Numerator and denominator of an inclusion figure; unknown (both None) with a counted
    reason when either is missing or they contradict each other."""
    numerator = _count(row.get("num_decks"))
    denominator = _count(row.get("potential_decks"))
    reasons = report["null_value_reasons"]
    if numerator is None or denominator is None:
        _count_reason(reasons, "DECK_COUNTS_MISSING_OR_NOT_NUMERIC")
        return None, None
    if denominator <= 0:
        _count_reason(reasons, "POTENTIAL_DECKS_NOT_POSITIVE")
        return None, None
    if numerator > denominator:
        _count_reason(reasons, "NUM_DECKS_ABOVE_POTENTIAL_DECKS")
        return None, None
    return numerator, denominator


def _commander_rows(
    row: dict[str, str], commander: str, card: str, variant: str | None, report: FileReport
) -> list[_Row]:
    numerator, denominator = _deck_counts(row, report)
    suffix = f":{variant}" if variant else ""
    inclusion = SIGNAL_BRACKET + suffix if variant else SIGNAL_INCLUSION
    rows: list[_Row] = [
        (commander, inclusion, card, _share(numerator, denominator), numerator, denominator)
    ]
    if not variant:
        synergy = _number(row.get("synergy"))
        if synergy is None:
            reason = (
                "SYNERGY_NOT_PUBLISHED"
                if not row.get("synergy", "").strip()
                else "SYNERGY_NOT_NUMERIC"
            )
            _count_reason(report["null_value_reasons"], reason)
        rows.append((commander, SIGNAL_SYNERGY, card, synergy, None, None))
    return rows


def _first_wins(pairs: list[tuple[_Key, _Row, int]], report: FileReport) -> _Kept:
    kept: _Kept = {}
    conflicts: list[str] = []
    for key, row, part in pairs:
        if key in kept:
            same = kept[key][0][3:] == row[3:]
            _skip(report, "DUPLICATE_SAME_FIGURES" if same else "DUPLICATE_CONFLICT")
            if not same:
                conflicts.append(f"{key[0] or '-'} / {key[2]}")
            continue
        kept[key] = (row, part)
    if conflicts:
        shown = ", ".join(conflicts[:3])
        report["warnings"].append(
            f"{len(conflicts)} duplicate(s) with different figures: the first row was kept "
            f"({shown}{', ...' if len(conflicts) > 3 else ''})"
        )
    return kept


def _empty(paths: list[Path]) -> FileReport:
    return {
        "status": STATUS_NO_ROWS if paths else STATUS_ABSENT,
        "parts": [path.name for path in paths],
        "sources": [],
        "rows_read": 0,
        "rows_written": 0,
        "rows_skipped": 0,
        "skipped_reasons": {},
        "null_value_reasons": {},
        "rows_replaced": 0,
        "stale_rows": 0,
        "warnings": [],
    }


def _read_commander_file(
    paths: list[Path], variant: str | None, canon: Callable[[str], str], report: FileReport
) -> _Kept:
    required = {"commander_name", "card_name", "num_decks", "potential_decks"}
    required |= set() if variant else {"synergy"}
    if variant:
        required.add("variant")
    pairs: list[tuple[_Key, _Row, int]] = []
    for part, row in _rows(paths, required):
        report["rows_read"] += 1
        commander, card = row["commander_name"].strip(), row["card_name"].strip()
        if not commander or not card:
            _skip(report, "NAME_MISSING")
            continue
        if variant and row["variant"].strip() != variant:
            _skip(report, "OTHER_VARIANT")
            continue
        for item in _commander_rows(row, canon(commander), card, variant, report):
            pairs.append(((item[0], item[1], item[2]), item, part))
    return _first_wins(pairs, report)


def _read_independent(
    paths: list[Path],
    required: set[str],
    convert: Callable[[dict[str, str], str, FileReport], list[_Row]],
    report: FileReport,
) -> _Kept:
    pairs: list[tuple[_Key, _Row, int]] = []
    for part, row in _rows(paths, required):
        report["rows_read"] += 1
        card = row["card_name"].strip()
        if not card:
            _skip(report, "NAME_MISSING")
            continue
        if row["fetch_status"].strip() != AVAILABLE:
            # The source did not deliver this card: unknown, not zero.
            _skip(report, "FETCH_STATUS_NOT_AVAILABLE")
            continue
        for item in convert(row, card, report):
            pairs.append(((item[0], item[1], item[2]), item, part))
    return _first_wins(pairs, report)


def _global_rows(row: dict[str, str], card: str, report: FileReport) -> list[_Row]:
    numerator, denominator = _deck_counts(row, report)
    return [("", SIGNAL_GLOBAL, card, _share(numerator, denominator), numerator, denominator)]


def _spellbook_rows(row: dict[str, str], card: str, report: FileReport) -> list[_Row]:
    value = _number(row.get("variant_count"))
    if value is None:
        _count_reason(report["null_value_reasons"], "VARIANT_COUNT_NOT_NUMERIC")
    return [("", SIGNAL_VARIANTS, card, value, None, None)]


def _read_salt(paths: list[Path], report: FileReport) -> _Kept:
    """The published salt list: one value per listed card; the rank is not stored."""
    pairs: list[tuple[_Key, _Row, int]] = []
    for part, row in _rows(paths, {"card_name", "salt"}):
        report["rows_read"] += 1
        card = row["card_name"].strip()
        if not card:
            _skip(report, "NAME_MISSING")
            continue
        value = _number(row.get("salt"))
        if value is None:
            _skip(report, "SALT_NOT_NUMERIC")
            continue
        item: _Row = ("", SIGNAL_SALT, card, value, None, None)
        pairs.append(((item[0], item[1], item[2]), item, part))
    return _first_wins(pairs, report)


def _read_edhtop16(paths: list[Path], canon: Callable[[str], str], report: FileReport) -> _Kept:
    """EDHTop16 play rates per commander and card (ONE_YEAR window).

    Only rows the fetch attributed to the commander (``fetch_status``
    AVAILABLE) are imported; the staples answer of the API carries
    global-staples fallback rows for commanders whose own list is
    short, and those rows are not the commander's data. The published
    entry count of the commander is the rate's denominator; how many
    of the entries contain the card is not published, so the numerator
    stays NULL, and per-card conversion is not published at all."""
    required = {"commander_name", "card_name", "play_rate", "entries_n", "fetch_status"}
    pairs: list[tuple[_Key, _Row, int]] = []
    for part, row in _rows(paths, required):
        report["rows_read"] += 1
        commander, card = row["commander_name"].strip(), row["card_name"].strip()
        if not commander or not card:
            _skip(report, "NAME_MISSING")
            continue
        if row["fetch_status"].strip() != AVAILABLE:
            # Not attributed to this commander by the fetch: unknown, not zero.
            _skip(report, "FETCH_STATUS_NOT_AVAILABLE")
            continue
        rate = _number(row.get("play_rate"))
        if rate is None or not 0.0 <= rate <= 1.0:
            _skip(report, "PLAY_RATE_INVALID")
            continue
        entries = _count(row.get("entries_n"))
        if entries == 0:
            entries = None
        if entries is None:
            _count_reason(report["null_value_reasons"], "ENTRIES_NOT_PUBLISHED")
        item: _Row = (canon(commander), SIGNAL_EDHTOP16, card, rate, None, entries)
        pairs.append(((item[0], item[1], item[2]), item, part))
    return _first_wins(pairs, report)


def _read_tournament_lists(paths: list[Path], commander: str, report: FileReport) -> list[_Row]:
    """Count, per card, the commander's tournament lists that contain it.

    The player column is not read. Lists are told apart by tournament and date in file
    order; the identity of a list is kept only while the file is read."""
    required = {"tournament", "date", "card_name", "section"}
    lists: dict[tuple[str, str, str], tuple[set[str], set[str]]] = {}
    for _, row in _rows(paths, required | {"player"}):
        report["rows_read"] += 1
        if row["section"].strip() not in LIST_SECTIONS:
            _skip(report, "SECTION_NOT_COUNTED")
            continue
        # The identity is only a grouping key in memory; it is never written.
        identity = (row["tournament"], row["date"], row["player"])
        cards, commanders = lists.setdefault(identity, (set(), set()))
        name = row["card_name"].strip()
        cards.add(name)
        if row["section"].strip() == "commander":
            commanders.add(name)
    folded = commander.casefold()
    valid = [
        cards
        for cards, commanders in lists.values()
        if folded in {name.casefold() for name in commanders}
    ]
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


def _read_combos(paths: list[Path], commander: str, report: FileReport) -> list[_Row]:
    """Per card of the commander's listed combos: how many combos, the largest deck count."""
    combos: dict[str, tuple[int, int]] = {}
    seen: set[tuple[str, int]] = set()
    for _, row in _rows(paths, {"cards", "num_decks"}):
        report["rows_read"] += 1
        cards = sorted({name.strip() for name in row["cards"].split(";") if name.strip()})
        decks = _count(row["num_decks"])
        if not cards:
            _skip(report, "COMBO_WITHOUT_CARDS")
            continue
        if decks is None:
            _skip(report, "NUM_DECKS_NOT_NUMERIC")
            continue
        if (";".join(cards), decks) in seen:
            _skip(report, "DUPLICATE_COMBO")
            continue
        seen.add((";".join(cards), decks))
        for name in cards:
            if name.casefold() == commander.casefold():
                continue  # the commander is in its own combos; it is not a card signal
            count, best = combos.get(name, (0, 0))
            combos[name] = (count + 1, max(best, decks))
    return [
        (commander, SIGNAL_COMBO_DECKS, name, float(best), count, None)
        for name, (count, best) in sorted(combos.items())
    ]


def _store_rows(
    store: StudioStore, rows: list[tuple[_Row, str]], *, replace: bool
) -> tuple[int, int]:
    """Write rows with their source; return (rows written, old rows removed)."""
    db = store.connection
    removed = 0
    if replace:
        pairs = sorted({(row[0], row[1]) for row, _ in rows})
        for pair in pairs:
            removed += db.execute(
                "DELETE FROM card_signal WHERE commander_name = ? AND signal = ?", pair
            ).rowcount
    db.executemany(
        "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, "
        "numerator, denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*row, source_id) for row, source_id in rows],
    )
    return len(rows), removed


def _register(store: StudioStore, paths: list[Path]) -> list[SourceRef]:
    refs: list[SourceRef] = []
    for path in paths:
        digest = sha256_file(path)
        source_id = store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE, title=path.name, sha256=digest
        )
        refs.append({"file": path.name, "source_id": source_id, "sha256": digest})
    return refs


def _combined_source(store: StudioStore, base: str, refs: list[SourceRef]) -> str:
    """One source for rows counted over all parts of a file (one part: that part's source)."""
    if len(refs) == 1:
        return refs[0]["source_id"]
    import hashlib

    digest = hashlib.sha256(
        "".join(f"{ref['file']}:{ref['sha256']}\n" for ref in refs).encode("utf-8")
    ).hexdigest()
    return store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE, title=f"{base} ({len(refs)} parts)", sha256=digest
    )


def find_commander_file(
    root: Path, commander: str, pattern: str, explicit: str | None, default: str | None
) -> list[Path]:
    """Parts of the file of ``commander`` (``pattern`` with its name; ``explicit`` wins)."""
    if explicit is not None:
        return _parts(root, explicit)
    for base in _file_candidates(commander, pattern):
        found = _parts(root, base)
        if found:
            return found
    return _parts(root, default) if default is not None else []


def import_signals(
    store: StudioStore,
    folder: str | Path,
    *,
    commander: str,
    replace: bool = True,
    tournament_file: str | None = None,
    combos_file: str | None = None,
) -> dict[str, object]:
    """Import every signal file of ``folder`` (all optional); one report entry per file.

    ``commander`` owns the tournament lists and the combo lists; the EDHREC and EDHTop16
    signals carry their own commander column. All files are written in one transaction.
    ``replace`` (default) replaces the rows of every signal and commander a file writes;
    ``replace=False`` only adds and updates."""
    root = Path(folder)
    if not root.is_dir():
        raise ValueError(f"not a folder: {root}")
    if not commander.strip():
        raise ValueError("a commander name is required")
    known = _known_commander_names(store, [commander.strip()])
    name = known[commander.strip().casefold()]
    canon = _canonical(known)
    reports: dict[str, FileReport] = {}
    plan: list[tuple[str, str | None]] = [(CARD_FILE, None)]
    plan += [(f"{BRACKET_FILE}_{variant}", variant) for variant in BRACKET_VARIANTS]
    plan += [(GLOBAL_FILE, None), (SPELLBOOK_FILE, None), (TOURNAMENT_FILE, None)]
    plan += [(EDHTOP16_FILE, None), (SALT_FILE, None), (COMBOS_FILE, None)]
    with store.connection:
        for file_name, variant in plan:
            if file_name == TOURNAMENT_FILE:
                paths = find_commander_file(
                    root, name, "topdeck_{}_decks", tournament_file, TOURNAMENT_FILE
                )
            elif file_name == COMBOS_FILE:
                paths = find_commander_file(root, name, "edhrec_{}_combos", combos_file, None)
            else:
                paths = _parts(root, file_name)
            report = _empty(paths)
            reports[file_name] = report
            if not paths:
                continue
            refs = _register(store, paths)
            report["sources"] = refs
            keyed: list[tuple[_Row, str]]
            if file_name in (TOURNAMENT_FILE, COMBOS_FILE):
                reader = _read_tournament_lists if file_name == TOURNAMENT_FILE else _read_combos
                combined = _combined_source(store, file_name, refs)
                keyed = [(row, combined) for row in reader(paths, name, report)]
            else:
                kept = _read_kept(file_name, paths, variant, canon, report)
                keyed = [(row, refs[part]["source_id"]) for row, part in kept.values()]
            if not keyed:
                report["warnings"].append(
                    "the file has no importable row: nothing was written, rows of earlier "
                    "imports were left as they are"
                )
                continue
            report["status"] = STATUS_IMPORTED
            report["rows_written"], report["rows_replaced"] = _store_rows(
                store, keyed, replace=replace
            )
            signals_written = sorted({row[1] for row, _ in keyed})
            marks = ",".join("?" * len(signals_written))
            ours = sorted({source_id for _, source_id in keyed})
            report["stale_rows"] = int(
                store.connection.execute(
                    f"SELECT COUNT(*) FROM card_signal WHERE signal IN ({marks}) "
                    f"AND source_id NOT IN ({','.join('?' * len(ours))})",
                    (*signals_written, *ours),
                ).fetchone()[0]
            )
            if report["stale_rows"]:
                report["warnings"].append(
                    f"{report['stale_rows']} row(s) of these signals remain from other source "
                    "files and were not replaced"
                )
    return {
        "folder": root.name,
        "tournament_commander": name,
        "mode": "replace" if replace else "append",
        "files": reports,
        "rows_written": sum(report["rows_written"] for report in reports.values()),
        "warnings": [
            f"{file}: {warning}"
            for file, report in reports.items()
            for warning in report["warnings"]
        ],
    }


def _read_kept(
    file_name: str,
    paths: list[Path],
    variant: str | None,
    canon: Callable[[str], str],
    report: FileReport,
) -> _Kept:
    if file_name == CARD_FILE or variant is not None:
        return _read_commander_file(paths, variant, canon, report)
    if file_name == GLOBAL_FILE:
        required = {"card_name", "fetch_status", "num_decks", "potential_decks"}
        return _read_independent(paths, required, _global_rows, report)
    if file_name == SPELLBOOK_FILE:
        required = {"card_name", "fetch_status", "variant_count"}
        return _read_independent(paths, required, _spellbook_rows, report)
    if file_name == SALT_FILE:
        return _read_salt(paths, report)
    return _read_edhtop16(paths, canon, report)
