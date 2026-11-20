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
- ``spellbook_card_links``: combo quality of a card (commander independent): the number
  of combo variants it is part of, the number of its distinct combo partners that are
  in the collection (``partners_in_collection``, when the file carries the column) and
  the number of its variants that use exactly two cards (derived from ``variant_ids``
  when the file carries that column: a variant id joins the spellbook card ids of the
  variant, one id per card slot, a template slot counting as one card). The strength
  index's combos component ranks the three figures together (``strength.combo_quality``),
  so a two-card combo with its partner in the collection counts more than a long list of
  variants nobody can build. What the file does not publish stays unknown: the result a
  combo produces and the partners of one single variant are not in the file, so neither
  is stored.
- ``spellbook_shells``: per commander and card, distinct qualifying combo shells
  within the commander's colour identity and legal pool (plus optional 2-card and
  commander-involvement breakdowns), derived from the bulk export without mixing
  commanders.
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
- ``playgroup_card_atlas_signals``: the observed win-rate gap of the Playgroup card
  atlas (commander independent): how much more often players won when they cast a card
  than when it never left their library, in percentage points, as published by the
  source with its own 95 % interval. The atlas fetch status measures another sample
  (the cast-turn funnel), not this observation, so a row is kept when the win-rate
  observation itself is published and rests on at least ``ATLAS_MIN_SAMPLE`` games in
  which the card was cast; the sample size is stored as the denominator and the
  strength component applies the same minimum plus shrinkage. Rows without a
  published gap, and rows of a card the source did not deliver, are not stored.

- ``<slug>_decklist_inclusion_<date>`` (also numbered parts): counted deck-list universes.
  The columns are ``card_name, source, bracket, decks_with_card, universe_decks`` (plus
  ``share`` and ``universe_snapshot``, which are not required: the share is recomputed). One
  universe is one ``(source, bracket)`` pair of complete deck lists that were counted, so a
  card without a row is a true 0 of ``universe_decks``, not unknown. The file has no commander
  column: it belongs to the commander of the import, and that is CHECKED. In every universe
  the commander's own card must be in every deck (``decks_with_card == universe_decks``),
  otherwise THAT universe alone is refused for this commander (``COMMANDER_NOT_IN_EVERY_DECK``)
  and nothing of it is stored; the other universes of the file are stored. Mixed denominators
  inside one universe (``MIXED_DENOMINATORS``) and an invalid count (``INVALID_COUNT``: not a
  whole number, negative, or above the denominator) refuse that universe too: dropping such a
  row would turn it into a false zero. Each refused universe is named in the report
  (``universes_refused``: source, bracket, reason, the commander's decks and the universe's
  decks, and ``rows_removed``: the rows a former import had stored for that universe, which
  go with it so a refused universe cannot stay selectable); the file is ``REFUSED`` only when no universe of it could be stored. Duplicate card
  rows keep the first and are counted in the report. Per universe one signal
  ``decklist_universe:<source>:<bracket>`` is stored (value the share, numerator the decks
  with the card, denominator the decks of the universe); its source row carries the snapshot
  id of the file (``<file>#<snapshot>`` as title).

Commander names of the files are matched against the commander names the store knows
(collection cards, bound decks, stored signals): exactly, else by a unique case-insensitive
match; a name that matches nothing is imported as written and listed in the report as not
recognised, next to the names that were imported.

A value the source does not publish is stored as NULL (unknown), never as 0. A card a
source does not list gets no row. When a card is listed under several headings of one
commander page with the same figures, the first row is kept. Re-importing replaces the rows
of each signal a file declares, for every commander the import writes, so the import is
idempotent; a declared signal the file no longer writes (an older file shape) loses its
stored rows with the import instead of keeping stale ones, and the report counts them as
replaced. A file with no valid row replaces nothing and the report says so
(``NOTHING_REPLACED``, with the number of existing rows that were kept). Source rows of
a commander are never mixed with another commander's.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TypedDict

from .field_read import (
    CARD_NAME_ALIASES,
    COMMANDER_NAME_ALIASES,
    DECK_LIST_CARDS_ALIASES,
    EDHREC_DECK_COUNT_ALIASES,
    EDHREC_POTENTIAL_DECKS_ALIASES,
    EDHREC_SYNERGY_ALIASES,
    FallbackTracker,
    missing_required_columns,
    read_str,
    record_store_fallbacks,
)
from .provenance import readme_retrieval_date, readme_source_url, register_stated_source
from .store import DataClass, StudioStore, sha256_file

CARD_FILE = "commander_card_signals"
BRACKET_FILE = "commander_bracket_signals"
GLOBAL_FILE = "card_global_signals"
SPELLBOOK_FILE = "spellbook_card_links"
SHELLS_FILE = "spellbook_shells"
TOURNAMENT_FILE = "topdeck_chulane_decks"
EDHTOP16_FILE = "edhtop16_commander_signals"
ATLAS_FILE = "playgroup_card_atlas_signals"
BRACKET_VARIANTS = ("core", "upgraded", "optimized", "cedh")
AVAILABLE = "AVAILABLE"
LIST_SECTIONS = frozenset({"main", "commander"})
# Atlas rows whose card the source delivered at all; the status says nothing about
# the win-rate sample, so the sample rule below is applied on top of it.
ATLAS_STATUSES = frozenset({"OK", "PARTIAL"})
# Minimum games in which the card was cast before its observed win-rate gap counts
# as evidence at all; mirrors the minimum of the strength component, which also
# shrinks the gap of a small sample towards zero (strength.py).
ATLAS_MIN_SAMPLE = 25

SIGNAL_INCLUSION = "edhrec_commander_inclusion"
SIGNAL_SYNERGY = "edhrec_commander_synergy"
SIGNAL_BRACKET = "edhrec_bracket_inclusion"
SIGNAL_GLOBAL = "edhrec_global_inclusion"
SIGNAL_VARIANTS = "spellbook_variants"
SIGNAL_PARTNERS = "spellbook_partners_in_collection"
SIGNAL_TWO_CARD = "spellbook_two_card_variants"
SIGNAL_SHELLS = "spellbook_shells"
SIGNAL_TWO_CARD_SHELLS = "spellbook_two_card_shells"
SIGNAL_COMMANDER_SHELLS = "spellbook_commander_shells"
SIGNAL_TOURNAMENT = "tournament_lists"
SIGNAL_SALT = "edhrec_salt"
SIGNAL_COMBO_DECKS = "edhrec_combo_decks"
SALT_FILE = "edhrec_salt"
COMBOS_FILE = "edhrec_chulane_combos"
SIGNAL_EDHTOP16 = "edhtop16_commander_play_rate"
SIGNAL_DECKLIST = "decklist_universe"
REFUSED = "REFUSED"
COMMANDER_NOT_IN_EVERY_DECK = "COMMANDER_NOT_IN_EVERY_DECK"
MIXED_DENOMINATORS = "MIXED_DENOMINATORS"
INVALID_UNIVERSE_NAME = "INVALID_UNIVERSE_NAME"  # a ":" in the source or bracket
INVALID_COUNT = "INVALID_COUNT"
DECKLIST_COLUMNS = {"card_name", "source", "bracket", "decks_with_card", "universe_decks"}
SIGNAL_PLAYGROUP = "playgroup_observed_winrate_gap"
# Q1-b4 (#1679, E15 Q1): stored signals no importer writes and no component reads any more, the
# rubric v1 rows (mean H, its spread, the rater count) and the TopDeck conversion. Rows a store
# already holds stay as they are (no migration, nothing deleted); the signal listings
# (``strength_view.signal_coverage``, the data layers) leave them out, because nothing can
# refill or use them. Rubric v2 ("Kartenverständnis") is a data file, never a stored signal.
RETIRED_SIGNALS = frozenset(
    {"rubric_h_mean", "rubric_h_sd", "rubric_raters", "topdeck_card_conversion"}
)

CORE_RATE_ALARM_SIGNALS: frozenset[str] = frozenset(
    {
        SIGNAL_INCLUSION,
        SIGNAL_SYNERGY,
        SIGNAL_BRACKET,
        SIGNAL_GLOBAL,
    }
)
NULL_REASON_RATE_ALARM_THRESHOLD: float = 0.50
ZERO_NUMERATOR_RATE_ALARM_THRESHOLD: float = 0.90

_Row = tuple[str, str, str, float | None, int | None, int | None]  # commander, signal, card, ...


class SignalRateAlarm(TypedDict):
    signal_name: str
    alarm_type: str
    commander: str
    count: int
    denominator: int
    rate: float
    threshold: float
    message: str


class RefusedUniverse(TypedDict):
    source: str
    bracket: str
    reason: str
    commander_decks: int | None  # decks_with_card of the commander's own row, None when absent
    universe_decks: int  # the denominator of the universe (the largest one when they are mixed)
    rows_removed: int  # rows of this universe a former import had stored: removed with it
    rows_kept: int  # its stored rows that stayed (append mode, wrong-commander file)


class UnmatchedRows(TypedDict):
    source: str
    bracket: str
    rows: int  # stored rows whose name matches no card of the store (oracle catalog included)
    examples: list[str]  # up to UNMATCHED_EXAMPLES names, the most counted first


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
    null_value_reasons: dict[str, int]  # why a stored value is unknown (NULL), per reason
    warnings: list[str]
    rate_alarms: list[SignalRateAlarm]
    fallbacks_used: dict[str, int]
    pooled_into: str | None  # tournament files: the file that carries the pooled rows stored
    universes_refused: list[RefusedUniverse]  # counted deck-list files: refused universes
    universes_unmatched: list[UnmatchedRows]  # counted deck-list files: rows without a card


def _merge_report_fallbacks(report: FileReport, tracker: FallbackTracker) -> None:
    target = report["fallbacks_used"]
    for key, cnt in tracker.to_dict().items():
        target[key] = target.get(key, 0) + cnt


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
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = missing_required_columns(reader.fieldnames, required)
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


def _deck_counts(row: dict[str, str], report: FileReport) -> tuple[int | None, int | None]:
    """Numerator and denominator of an inclusion figure; both None, with a counted reason,
    when either is missing or they contradict each other."""
    tracker = FallbackTracker()
    raw_num = read_str(row, EDHREC_DECK_COUNT_ALIASES, tracker=tracker)
    raw_den = read_str(row, EDHREC_POTENTIAL_DECKS_ALIASES, tracker=tracker)
    _merge_report_fallbacks(report, tracker)
    numerator = _count(raw_num or None)
    denominator = _count(raw_den or None)
    reasons = report["null_value_reasons"]
    reason: str | None = None
    if numerator is None or denominator is None:
        reason = "DECK_COUNTS_MISSING_OR_NOT_NUMERIC"
    elif denominator <= 0:
        reason = "POTENTIAL_DECKS_NOT_POSITIVE"
    elif numerator > denominator:
        reason = "NUM_DECKS_ABOVE_POTENTIAL_DECKS"
    if reason is not None:
        reasons[reason] = reasons.get(reason, 0) + 1
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
        tracker = FallbackTracker()
        raw_syn = read_str(row, EDHREC_SYNERGY_ALIASES, tracker=tracker)
        _merge_report_fallbacks(report, tracker)
        synergy = _number(raw_syn or None)
        if synergy is None:
            reason = "SYNERGY_NOT_PUBLISHED" if not raw_syn else "SYNERGY_NOT_NUMERIC"
            reasons = report["null_value_reasons"]
            reasons[reason] = reasons.get(reason, 0) + 1
        rows.append((commander, SIGNAL_SYNERGY, card, synergy, None, None))
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
    conflicts = report["skipped_reasons"].get("DUPLICATE_CONFLICT", 0)
    if conflicts:
        report["warnings"].append(
            f"{conflicts} duplicate(s) with different figures: the first row was kept"
        )
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
        "null_value_reasons": {},
        "warnings": [],
        "rate_alarms": [],
        "fallbacks_used": {},
        "pooled_into": None,
        "universes_refused": [],
        "universes_unmatched": [],
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
        tracker = FallbackTracker()
        commander = read_str(row, COMMANDER_NAME_ALIASES, tracker=tracker)
        card = read_str(row, CARD_NAME_ALIASES, tracker=tracker)
        _merge_report_fallbacks(report, tracker)
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
        for item in _commander_rows(row, commander, card, variant, report):
            pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _read_independent(
    paths: list[Path],
    required: set[str],
    convert: Callable[[dict[str, str], str, FileReport], list[_Row]],
    report: FileReport,
) -> list[_Row]:
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        tracker = FallbackTracker()
        card = read_str(row, CARD_NAME_ALIASES, tracker=tracker)
        _merge_report_fallbacks(report, tracker)
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
        for item in convert(row, card, report):
            pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _global_rows(row: dict[str, str], card: str, report: FileReport) -> list[_Row]:
    numerator, denominator = _deck_counts(row, report)
    return [("", SIGNAL_GLOBAL, card, _share(numerator, denominator), numerator, denominator)]


_VARIANT_ID_TOKEN = re.compile(r"-?\d+")


def _variant_card_slots(variant_id: str) -> int:
    """The card slots of one spellbook variant: its id joins the spellbook card ids of
    the cards it uses (the id is the combo's page address), so the token count is the
    card count of the combo. A template slot is written as a negative id (``--108`` in
    the joined form) and counts as the one card it stands for."""
    return len(_VARIANT_ID_TOKEN.findall(variant_id))


def _two_card_variants(row: dict[str, str], variant_count: float | None) -> float | None:
    """How many of the card's variants use exactly two cards, from the file's
    ``variant_ids``. A card without variants has none of them (a counted 0, not an
    unknown); without the ids of a card that has variants the figure is unknown."""
    if variant_count is not None and variant_count == 0:
        return 0.0
    ids = row.get("variant_ids")
    if ids is None or not ids.strip():
        return None
    return float(
        sum(
            1
            for variant_id in ids.split(";")
            if variant_id.strip() and _variant_card_slots(variant_id) == 2
        )
    )


def _spellbook_rows(row: dict[str, str], card: str, report: FileReport) -> list[_Row]:
    rows: list[_Row] = []
    value = _number(row.get("variant_count"))
    if value is None:
        reasons = report["null_value_reasons"]
        reasons["VARIANT_COUNT_NOT_NUMERIC"] = reasons.get("VARIANT_COUNT_NOT_NUMERIC", 0) + 1
    rows.append(("", SIGNAL_VARIANTS, card, value, None, None))
    if "partners_in_collection" in row:
        partners = _number(row.get("partners_in_collection"))
        if partners is None:
            reasons = report["null_value_reasons"]
            reasons["PARTNER_COUNT_NOT_NUMERIC"] = reasons.get("PARTNER_COUNT_NOT_NUMERIC", 0) + 1
        rows.append(("", SIGNAL_PARTNERS, card, partners, None, None))
    if "variant_ids" in row:
        two_card = _two_card_variants(row, value)
        if two_card is None:
            reasons = report["null_value_reasons"]
            reasons["VARIANT_IDS_MISSING"] = reasons.get("VARIANT_IDS_MISSING", 0) + 1
        rows.append(("", SIGNAL_TWO_CARD, card, two_card, None, None))
    return rows


def _shells_rows(row: dict[str, str], commander: str, card: str, report: FileReport) -> list[_Row]:
    """The shell counts of one card (#1366): distinct spellbook combos instead of
    raw variants, split by card count and commander involvement. The file lists
    every card of the collection, so a card without a qualifying shell holds a
    counted 0; a non-numeric or negative count stays unknown (NULL). Contradictory
    breakdown counts above ``shell_count`` stay unknown too. The breakdown columns
    are optional in the file the same way the variant quality columns are: a file
    without them declares the signals and writes no rows for them."""
    rows: list[_Row] = []
    count = _count(row.get("shell_count"))
    value = float(count) if count is not None else None
    if value is None:
        reasons = report["null_value_reasons"]
        reasons["SHELL_COUNT_NOT_NUMERIC"] = reasons.get("SHELL_COUNT_NOT_NUMERIC", 0) + 1
    rows.append((commander, SIGNAL_SHELLS, card, value, None, None))
    for column, signal, reason_name, exceeds_reason in (
        (
            "shell_count_2card",
            SIGNAL_TWO_CARD_SHELLS,
            "SHELL_TWO_CARD_NOT_NUMERIC",
            "SHELL_TWO_CARD_EXCEEDS_TOTAL",
        ),
        (
            "shell_count_commander",
            SIGNAL_COMMANDER_SHELLS,
            "SHELL_COMMANDER_NOT_NUMERIC",
            "SHELL_COMMANDER_EXCEEDS_TOTAL",
        ),
    ):
        if column not in row:
            continue
        raw_part = _count(row.get(column))
        part = float(raw_part) if raw_part is not None else None
        if part is None:
            reasons = report["null_value_reasons"]
            reasons[reason_name] = reasons.get(reason_name, 0) + 1
        elif value is not None and part > value:
            part = None
            reasons = report["null_value_reasons"]
            reasons[exceeds_reason] = reasons.get(exceeds_reason, 0) + 1
        rows.append((commander, signal, card, part, None, None))
    return rows


def _read_shells(paths: list[Path], report: FileReport, commanders: _Commanders) -> list[_Row]:
    """Commander-scoped combo shell counts (#1366).

    Requires ``commander_name`` so shell rows of one commander's identity and
    legal pool are never shared silently with another commander."""
    required = {"commander_name", "card_name", "fetch_status", "shell_count"}
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        raw_commander = row["commander_name"].strip()
        card = row["card_name"].strip()
        if not raw_commander or not card:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["NAME_MISSING"] = (
                report["skipped_reasons"].get("NAME_MISSING", 0) + 1
            )
            continue
        if row["fetch_status"].strip() != AVAILABLE:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["FETCH_STATUS_NOT_AVAILABLE"] = (
                report["skipped_reasons"].get("FETCH_STATUS_NOT_AVAILABLE", 0) + 1
            )
            continue
        commander = commanders.resolve(raw_commander)
        for item in _shells_rows(row, commander, card, report):
            pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _read_salt(paths: list[Path], report: FileReport) -> list[_Row]:
    """The published salt list: one value per listed card (the rank is not stored). A card that
    is not listed has no row: its salt is unknown, not zero."""
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, {"card_name", "salt"}):
        report["rows_read"] += 1
        card = row["card_name"].strip()
        value = _number(row.get("salt"))
        if not card or value is None:
            reason = "NAME_MISSING" if not card else "SALT_NOT_NUMERIC"
            report["rows_skipped"] += 1
            report["skipped_reasons"][reason] = report["skipped_reasons"].get(reason, 0) + 1
            continue
        item: _Row = ("", SIGNAL_SALT, card, value, None, None)
        pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _read_combos(
    paths: list[Path],
    commander: str,
    report: FileReport,
    sets: list[tuple[list[str], int]] | None = None,
) -> list[_Row]:
    """Per card of the commander's EDHREC combo lists: ``numerator`` the number of listed
    combos it is part of, ``value`` the largest deck count among them. The commander itself
    (part of its own combos) is not a card signal. ``sets`` collects the full card set and
    deck count of every accepted combo (the commander included), in file order."""
    combos: dict[str, tuple[int, int]] = {}
    seen: set[tuple[str, int]] = set()
    for row in _rows(paths, {"cards", "num_decks"}):
        report["rows_read"] += 1
        tracker = FallbackTracker()
        raw_cards = read_str(row, DECK_LIST_CARDS_ALIASES, tracker=tracker)
        raw_decks = read_str(row, EDHREC_DECK_COUNT_ALIASES, tracker=tracker)
        _merge_report_fallbacks(report, tracker)
        cards = sorted({name.strip() for name in raw_cards.split(";") if name.strip()})
        decks = _count(raw_decks or None)
        reason = (
            "COMBO_WITHOUT_CARDS"
            if not cards
            else "NUM_DECKS_NOT_NUMERIC"
            if decks is None
            else "DUPLICATE_COMBO"
            if (";".join(cards), decks) in seen
            else None
        )
        if reason is not None or decks is None:
            report["rows_skipped"] += 1
            key = reason or "NUM_DECKS_NOT_NUMERIC"
            report["skipped_reasons"][key] = report["skipped_reasons"].get(key, 0) + 1
            continue
        seen.add((";".join(cards), decks))
        if sets is not None:
            sets.append((cards, decks))
        for name in cards:
            if name.casefold() == commander.casefold():
                continue
            count, best = combos.get(name, (0, 0))
            combos[name] = (count + 1, max(best, decks))
    return [
        (commander, SIGNAL_COMBO_DECKS, name, float(best), count, None)
        for name, (count, best) in sorted(combos.items())
    ]


def _read_edhtop16(paths: list[Path], report: FileReport, commanders: _Commanders) -> list[_Row]:
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
        item: _Row = (commanders.resolve(commander), SIGNAL_EDHTOP16, card, rate, None, entries)
        pairs.append(((item[0], item[1], item[2]), item))
    return list(_first_wins(iter(pairs), report).values())


def _read_atlas(paths: list[Path], report: FileReport) -> list[_Row]:
    """Rows of the Playgroup card atlas: the published observed win-rate gap per card.

    The value is the gap in percentage points, exactly as published; the denominator
    is the number of games in which the card was cast (the sample of the observation;
    the comparison group, games in which it never left the library, is larger for
    almost every card of the atlas). There is no numerator: the source publishes the
    two win rates rounded, so a win count is not reconstructed. A row is stored only
    when the source delivered the card, published the gap, and the sample reaches
    ``ATLAS_MIN_SAMPLE``; anything else stays unknown, never zero."""
    required = {"card_name", "fetch_status", "observed_winrate_gap_pp", "winrate_when_cast_n"}
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        card = row["card_name"].strip()
        if not card:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["NAME_MISSING"] = (
                report["skipped_reasons"].get("NAME_MISSING", 0) + 1
            )
            continue
        if row["fetch_status"].strip() not in ATLAS_STATUSES:
            # The source did not deliver this card: unknown, not zero.
            report["rows_skipped"] += 1
            report["skipped_reasons"]["FETCH_STATUS_NOT_AVAILABLE"] = (
                report["skipped_reasons"].get("FETCH_STATUS_NOT_AVAILABLE", 0) + 1
            )
            continue
        gap = _number(row.get("observed_winrate_gap_pp"))
        sample = _count(row.get("winrate_when_cast_n"))
        if gap is None or sample is None:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["VALUE_NOT_PUBLISHED"] = (
                report["skipped_reasons"].get("VALUE_NOT_PUBLISHED", 0) + 1
            )
            continue
        if sample < ATLAS_MIN_SAMPLE:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["SAMPLE_BELOW_MINIMUM"] = (
                report["skipped_reasons"].get("SAMPLE_BELOW_MINIMUM", 0) + 1
            )
            continue
        item: _Row = ("", SIGNAL_PLAYGROUP, card, gap, None, sample)
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


def _store_rows(
    store: StudioStore,
    rows: list[_Row],
    source_id: str,
    *,
    replace: bool = True,
    declared: Sequence[str] | None = None,
) -> tuple[int, int]:
    """Replace the rows of every (commander, signal) pair of ``rows``; returns (rows written,
    existing rows that were replaced).

    ``declared`` names every signal the file declares: a replacing import then replaces the
    rows of those signals wholesale (for the commanders of ``rows``), so the stored rows of
    a declared signal this file did not write — an older file shape, say — go with the
    import instead of staying behind as stale rows of the file, and count as replaced."""
    db = store.connection
    pairs = sorted({(row[0], row[1]) for row in rows})
    if declared is not None:
        pairs = sorted({(row[0], signal) for row in rows for signal in declared} | set(pairs))
    replaced = 0
    for pair in pairs:
        replaced += int(
            db.execute(
                "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal = ?", pair
            ).fetchone()[0]
        )
    if replace:
        db.executemany("DELETE FROM card_signal WHERE commander_name = ? AND signal = ?", pairs)
    else:
        replaced = 0  # append mode only adds and updates rows
    db.executemany(
        "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, "
        "numerator, denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*row, source_id) for row in rows],
    )
    return len(rows), replaced


class _Universe:
    """The rows of one counted universe while a decklist file is read."""

    def __init__(self) -> None:
        self.cards: dict[str, tuple[int, int]] = {}
        self.denominators: set[int] = set()
        self.snapshot = ""
        self.invalid = 0


def _bump(report: FileReport, reason: str, count: int = 1) -> None:
    report["skipped_reasons"][reason] = report["skipped_reasons"].get(reason, 0) + count


def _read_decklist_universes(
    paths: list[Path], report: FileReport
) -> dict[tuple[str, str], _Universe]:
    """The universes of a counted deck-list file, each with the rows it was given. First row
    wins for a duplicated card. A universe with an invalid count is marked (``invalid``)."""
    universes: dict[tuple[str, str], _Universe] = {}
    for row in _rows(paths, DECKLIST_COLUMNS):
        report["rows_read"] += 1
        card = row["card_name"].strip()
        source, bracket = row["source"].strip().lower(), row["bracket"].strip()
        if not card or not source or not bracket:
            report["rows_skipped"] += 1
            _bump(report, "NAME_MISSING")
            continue
        universe = universes.setdefault((source, bracket), _Universe())
        decks, total = _count(row["decks_with_card"]), _count(row["universe_decks"])
        if decks is None or total is None or total <= 0 or decks > total:
            universe.invalid += 1
            continue
        universe.denominators.add(total)
        universe.snapshot = universe.snapshot or row.get("universe_snapshot", "").strip()
        if card in universe.cards:
            report["rows_skipped"] += 1
            same = universe.cards[card] == (decks, total)
            _bump(report, "DUPLICATE_SAME_FIGURES" if same else "DUPLICATE_CONFLICT")
            continue
        universe.cards[card] = (decks, total)
    return universes


def _universe_refusal(
    key: tuple[str, str], universe: _Universe, names: set[str]
) -> tuple[str, int | None]:
    """Why a universe cannot be stored for the commander (empty reason: it can), and the
    decks the commander's own row counts (None when it has no single row)."""
    wanted = {name.casefold() for name in names}
    own = [figures for card, figures in universe.cards.items() if card.casefold() in wanted]
    commander_decks = own[0][0] if len(own) == 1 else None
    if ":" in key[0] or ":" in key[1]:  # the signal name ``decklist_universe:<source>:<bracket>``
        return INVALID_UNIVERSE_NAME, commander_decks
    if universe.invalid:
        return INVALID_COUNT, commander_decks
    if len(universe.denominators) > 1:
        return MIXED_DENOMINATORS, commander_decks
    if len(own) != 1 or own[0][0] != own[0][1]:
        return COMMANDER_NOT_IN_EVERY_DECK, commander_decks
    return "", commander_decks


def _import_decklists(
    store: StudioStore,
    root: Path,
    commander: str,
    raw_name: str,
    reports: dict[str, FileReport],
    *,
    replace: bool = True,
) -> None:
    """Read every counted deck-list file of the folder. A universe whose commander check or
    counts fail is refused alone and named in the report; the other universes of the file are
    stored. The file is ``REFUSED`` when none of its universes can be stored."""
    for base in _decklist_bases(root):
        paths = _parts(root, base)
        report = _empty(paths)
        reports[base] = report
        universes = _read_decklist_universes(paths, report)
        if not universes:
            report["status"] = "NOTHING_REPLACED"
            continue
        usable: dict[tuple[str, str], _Universe] = {}
        # Decided once per file: a file in which no universe lists this commander in EVERY deck
        # (decks == total) was built around another commander (it may list this one as an
        # ordinary card) or says nothing valid about it, so none of its refusals says anything
        # about the rows stored for this one.
        wanted = {commander.casefold(), raw_name.casefold()}
        wrong_file = not any(
            decks == total and total > 0
            for item in universes.values()
            for card, (decks, total) in item.cards.items()
            if card.casefold() in wanted
        )
        for (source, bracket), universe in sorted(universes.items()):
            reason, commander_decks = _universe_refusal(
                (source, bracket), universe, {commander, raw_name}
            )
            if not reason:
                usable[(source, bracket)] = universe
                continue
            _bump(report, reason)
            removed = 0
            # A stale universe must not stay selectable: its rows go with the refusal, except
            # for an invalid name (no such signal), a wrong-commander file, and append mode
            # (which never deletes: the rows that stay are reported).
            signal = decklist_signal(source, bracket)
            if replace and not wrong_file and reason != INVALID_UNIVERSE_NAME:
                removed = _remove_universe(store, commander, signal)
            kept = _count_rows(store, commander, signal)
            report["universes_refused"].append(
                {
                    "source": source,
                    "bracket": bracket,
                    "reason": reason,
                    "commander_decks": commander_decks,
                    "universe_decks": max(universe.denominators, default=0),
                    "rows_removed": removed,
                    "rows_kept": kept,
                }
            )
        report["commander"] = commander
        if not usable:
            report["status"] = REFUSED
            report["rows_kept"] = _kept_decklist_rows(store, commander)
            continue
        file_hash = hashlib.sha256(
            "".join(sha256_file(path) for path in paths).encode()
        ).hexdigest()
        known = known_card_names(store)
        for (source, bracket), universe in usable.items():
            signal = decklist_signal(source, bracket)
            source_id = register_stated_source(
                store,
                data_class=DataClass.NORMALIZED_SOURCE,
                title=f"{paths[0].name}#{universe.snapshot}",
                sha256=hashlib.sha256(f"{file_hash}:{signal}".encode()).hexdigest(),
                snapshot_date=_decklist_snapshot_date(universe.snapshot, paths[0]),
                url=readme_source_url(paths[0]),
            )
            rows: list[_Row] = [
                (commander, signal, card, decks / total, decks, total)
                for card, (decks, total) in sorted(universe.cards.items())
            ]
            written, replaced = _store_rows(store, rows, source_id)
            report["rows_written"] += written
            report["rows_replaced"] += replaced
            missing = unmatched_universe_names(store, commander, signal, known)
            if missing:
                report["universes_unmatched"].append(
                    {
                        "source": source,
                        "bracket": bracket,
                        "rows": len(missing),
                        "examples": missing[:UNMATCHED_EXAMPLES],
                    }
                )


UNMATCHED_EXAMPLES = 10


def known_card_names(store: StudioStore) -> set[str]:
    """Every card name the store knows, casefolded: the collection's oracle and engine names,
    the Scryfall catalog and the front face of each two-part name."""
    db = store.connection
    names: set[str] = set()
    for sql in (
        "SELECT oracle_name FROM card_fact",
        "SELECT engine_name FROM card_fact",
        "SELECT name FROM scryfall_card",
    ):
        names.update(str(row[0]) for row in db.execute(sql) if row[0])
    names.update(name.split(" // ")[0].strip() for name in list(names) if " // " in name)
    return {name.casefold() for name in names}


def unmatched_universe_names(
    store: StudioStore, commander: str, signal: str, known: set[str] | None = None
) -> list[str]:
    """The card names of a stored counted universe that match no card of the store, the
    most counted first. Empty while the store holds no card at all (nothing to match against).
    A notice only: no name is dropped and nothing is refused because of it."""
    names = known if known is not None else known_card_names(store)
    if not names:
        return []
    rows = store.connection.execute(
        "SELECT card_name FROM card_signal WHERE commander_name = ? AND signal = ? "
        "ORDER BY numerator DESC, card_name",
        (commander, signal),
    )
    return [str(row[0]) for row in rows if str(row[0]).casefold() not in names]


def unmatched_notice(rows: int, examples: Sequence[str]) -> str:
    if rows <= 0:
        return ""
    return f"{rows} Zeilen ohne Karte im Store, z. B. {'; '.join(examples)}"


def _count_rows(store: StudioStore, commander: str, signal: str) -> int:
    return int(
        store.connection.execute(
            "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal = ?",
            (commander, signal),
        ).fetchone()[0]
    )


def _remove_universe(store: StudioStore, commander: str, signal: str) -> int:
    """Delete the stored rows of one counted universe of ``commander``; how many there were."""
    cursor = store.connection.execute(
        "DELETE FROM card_signal WHERE commander_name = ? AND signal = ?", (commander, signal)
    )
    return int(cursor.rowcount)


def _kept_decklist_rows(store: StudioStore, commander: str) -> int:
    return int(
        store.connection.execute(
            "SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal LIKE ?",
            (commander, f"{SIGNAL_DECKLIST}:%"),
        ).fetchone()[0]
    )


def _calendar_date(year: str, month: str, day: str) -> str | None:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _snapshot_from_signal_path(path: Path) -> str | None:
    """The retrieval date a signal file states, or ``None`` (shown as unknown, never estimated).

    In this order: a date in the file or folder name; a retrieval field of the first CSV row
    (``snapshot_utc``, ``retrieved_at``, ``snapshot_date``; a ``date`` column is not read: in the
    tournament lists it is the tournament date); the ``Abruf`` date of the folder README row
    (``provenance``). Every value must be a valid calendar date (#1545)."""
    for candidate in (path.name, path.parent.name):
        m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", candidate)
        if m and (found := _calendar_date(m.group(1), m.group(2), m.group(3))):
            return found
    if path.suffix.lower() == ".csv" and path.is_file():
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                first = next(reader, None)
                if first:
                    for key in ("snapshot_utc", "retrieved_at", "snapshot_date"):
                        m = re.fullmatch(
                            r"(20\d{2})-(\d{2})-(\d{2})(?:[T ].*)?", (first.get(key) or "").strip()
                        )
                        if m and (found := _calendar_date(m.group(1), m.group(2), m.group(3))):
                            return found
        except OSError:
            pass
    return readme_retrieval_date(path)


def _decklist_snapshot_date(snapshot: object, path: Path) -> str | None:
    """A date for a counted deck-list source: the snapshot when it is a calendar date, otherwise
    only the ``Abruf`` date the folder README states. A date in the file name is not taken here:
    for an inclusion file it is when the file was generated, not when the lists were fetched; and
    never an id fragment (#1545)."""
    m = re.fullmatch(r"(20\d{2})-(\d{2})-(\d{2})", str(snapshot or "")[:10])
    if m and (found := _calendar_date(m.group(1), m.group(2), m.group(3))):
        return found
    return readme_retrieval_date(path)


def _register(store: StudioStore, paths: list[Path]) -> str | None:
    """Register every part of a file; the rows carry the source of the whole file: its only
    part, or (several parts) one source whose hash covers all parts, not just the first."""
    ids: list[tuple[str, str]] = []
    dates: list[str | None] = []
    for path in paths:
        digest = sha256_file(path)
        snap = _snapshot_from_signal_path(path)
        dates.append(snap)
        register_stated_source(
            store,
            data_class=DataClass.NORMALIZED_SOURCE,
            title=path.name,
            sha256=digest,
            snapshot_date=snap,
            url=readme_source_url(path),
        )
        ids.append((path.name, digest))
    if len(ids) <= 1:
        return f"src:{ids[0][1][:16]}" if ids else None
    combined = hashlib.sha256(
        "".join(f"{name}:{digest}\n" for name, digest in ids).encode("utf-8")
    ).hexdigest()
    stated = [d for d in dates if d]
    part_urls = {readme_source_url(path) for path in paths}
    return register_stated_source(
        store,
        data_class=DataClass.NORMALIZED_SOURCE,
        title=f"{ids[0][0]} (+{len(ids) - 1} parts)",
        sha256=combined,
        # One date for the whole file only when every part states one: the oldest (all parts are
        # at least that fresh); a part without a date leaves the combined source unknown.
        snapshot_date=min(stated) if stated and len(stated) == len(dates) else None,
        # One address for the whole file only when every part names the same one.
        url=next(iter(part_urls)) if len(part_urls) == 1 else None,
    )


def _file_signals(file_name: str, variant: str | None) -> list[str]:
    """The stored signals a file writes (the bracket files write one signal per variant)."""
    if variant is not None:
        return [f"{SIGNAL_BRACKET}:{variant}"]
    if file_name == CARD_FILE:
        return [SIGNAL_INCLUSION, SIGNAL_SYNERGY]
    if file_name == GLOBAL_FILE:
        return [SIGNAL_GLOBAL]
    if file_name == SPELLBOOK_FILE:
        return [SIGNAL_VARIANTS, SIGNAL_PARTNERS, SIGNAL_TWO_CARD]
    if file_name == SHELLS_FILE:
        return [SIGNAL_SHELLS, SIGNAL_TWO_CARD_SHELLS, SIGNAL_COMMANDER_SHELLS]
    if file_name == EDHTOP16_FILE:
        return [SIGNAL_EDHTOP16]
    if file_name == ATLAS_FILE:
        return [SIGNAL_PLAYGROUP]
    if file_name == SALT_FILE:
        return [SIGNAL_SALT]
    if file_name == COMBOS_FILE:
        return [SIGNAL_COMBO_DECKS]
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
    if file_name == SHELLS_FILE:
        return _read_shells(paths, report, commanders)
    if file_name == EDHTOP16_FILE:
        return _read_edhtop16(paths, report, commanders)
    if file_name == ATLAS_FILE:
        return _read_atlas(paths, report)
    if file_name == SALT_FILE:
        return _read_salt(paths, report)
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


_DECKLIST_PATTERN = re.compile(r"^(.+_decklist_inclusion_\d+)(?:_(\d+))?\.csv$")


def decklist_signal(source: str, bracket: str) -> str:
    """The stored signal name of one counted universe."""
    return f"{SIGNAL_DECKLIST}:{source}:{bracket}"


def _decklist_bases(folder: Path) -> list[str]:
    """Base names of every counted deck-list file of the folder, in name order."""
    found: set[str] = set()
    for path in folder.iterdir():
        match = _DECKLIST_PATTERN.match(path.name)
        if match and path.is_file():
            found.add(match.group(1))
    return sorted(found)


def has_decklist_files(folder: str | Path) -> bool:
    """Whether ``folder`` itself holds a counted deck-list file."""
    root = Path(folder)
    return root.is_dir() and bool(_decklist_bases(root))


def has_signal_files(folder: str | Path) -> bool:
    """Whether ``folder`` holds at least one file ``import_signals`` reads."""
    root = Path(folder)
    if not root.is_dir():
        return False
    bases = [
        CARD_FILE,
        GLOBAL_FILE,
        SPELLBOOK_FILE,
        SHELLS_FILE,
        EDHTOP16_FILE,
        ATLAS_FILE,
        SALT_FILE,
        COMBOS_FILE,
    ]
    bases += [f"{BRACKET_FILE}_{variant}" for variant in BRACKET_VARIANTS]
    bases += _tournament_bases(root)
    bases += _combo_bases(root)
    return any(_parts(root, base) for base in bases) or bool(_decklist_bases(root))


def _combo_bases(root: Path) -> list[str]:
    """Every ``edhrec_<commander>_combos`` file of the folder (any commander, numbered parts
    included), not only the one of the default commander."""
    pattern = re.compile(r"^(edhrec_[a-z0-9_-]+_combos)(?:_\d+)?\.csv$")
    found = {m.group(1) for path in root.iterdir() if (m := pattern.match(path.name))}
    return sorted(found)


def _import_tournaments(
    store: StudioStore,
    root: Path,
    preferred: str,
    commanders: _Commanders,
    reports: dict[str, FileReport],
    *,
    replace: bool = True,
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
        stored, replaced = _store_rows(store, rows, source_id, replace=replace)
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


def _store_combo_sets(
    store: StudioStore,
    commander: str,
    sets: list[tuple[list[str], int]],
    source_id: str,
    *,
    replace: bool,
) -> None:
    """The full card set of each listed combo of ``commander`` (table ``commander_combo``).
    A replacing import swaps the commander's list; an appending one adds the sets that are
    not stored yet and updates the deck count of the ones that are."""
    db = store.connection
    if replace:
        db.execute("DELETE FROM commander_combo WHERE commander_name = ?", (commander,))
    known = {
        str(row[0])
        for row in db.execute(
            "SELECT cards FROM commander_combo WHERE commander_name = ?", (commander,)
        )
    }
    ordinal = int(
        db.execute(
            "SELECT COALESCE(MAX(ordinal), 0) FROM commander_combo WHERE commander_name = ?",
            (commander,),
        ).fetchone()[0]
    )
    for cards, decks in sets:
        encoded = json.dumps(cards, ensure_ascii=False)
        if encoded in known:
            # The set is stored already: the newer file's deck count replaces the old one.
            db.execute(
                "UPDATE commander_combo SET num_decks = ?, source_id = ? "
                "WHERE commander_name = ? AND cards = ?",
                (decks, source_id, commander, encoded),
            )
            continue
        known.add(encoded)
        ordinal += 1
        db.execute(
            "INSERT INTO commander_combo(commander_name, ordinal, cards, num_decks, source_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (commander, ordinal, encoded, decks, source_id),
        )


def _import_combos(
    store: StudioStore,
    root: Path,
    commander: str,
    reports: dict[str, FileReport],
    *,
    replace: bool,
) -> None:
    """The combo list file of ``commander`` (``edhrec_<short name>_combos`` or the full name)."""
    short = re.sub(r"[^a-z0-9-]+", "_", commander.split(",")[0].casefold()).strip("_")
    full = re.sub(r"[^a-z0-9-]+", "_", commander.casefold()).strip("_")
    for base in dict.fromkeys([f"edhrec_{short}_combos", f"edhrec_{full}_combos"]):
        paths = _parts(root, base)
        if not paths:
            continue
        report = _empty(paths)
        reports[base] = report
        sets: list[tuple[list[str], int]] = []
        rows = _read_combos(paths, commander, report, sets)
        source_id = _register(store, paths)
        if source_id is not None and rows:
            report["rows_written"], report["rows_replaced"] = _store_rows(
                store, rows, source_id, replace=replace
            )
            _store_combo_sets(store, commander, sets, source_id, replace=replace)
        else:
            report["status"] = "NOTHING_REPLACED"
            report["rows_kept"] = _kept_rows(store, [SIGNAL_COMBO_DECKS], commander)
        return
    reports[f"edhrec_{short}_combos"] = _empty([])


@dataclass
class SignalFileReport:
    """Structured report for a single signal file import (#1416)."""

    status: str = "IMPORTED"
    parts: list[str] = field(default_factory=list)
    rows_read: int = 0
    rows_written: int = 0
    rows_replaced: int = 0
    rows_kept: int = 0
    rows_skipped: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)
    commander: str | None = None
    lists_read: int = 0
    null_value_reasons: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    rate_alarms: list[SignalRateAlarm] = field(default_factory=list)
    fallbacks_used: dict[str, int] = field(default_factory=dict)
    pooled_into: str | None = None
    universes_refused: list[RefusedUniverse] = field(default_factory=list)
    universes_unmatched: list[UnmatchedRows] = field(default_factory=list)

    def to_dict(self) -> FileReport:
        return {
            "status": self.status,
            "parts": list(self.parts),
            "rows_read": self.rows_read,
            "rows_written": self.rows_written,
            "rows_replaced": self.rows_replaced,
            "rows_kept": self.rows_kept,
            "rows_skipped": self.rows_skipped,
            "skipped_reasons": dict(self.skipped_reasons),
            "commander": self.commander,
            "lists_read": self.lists_read,
            "null_value_reasons": dict(self.null_value_reasons),
            "warnings": list(self.warnings),
            "rate_alarms": list(self.rate_alarms),
            "fallbacks_used": dict(self.fallbacks_used),
            "pooled_into": self.pooled_into,
            "universes_refused": list(self.universes_refused),
            "universes_unmatched": list(self.universes_unmatched),
        }

    @classmethod
    def from_dict(cls, data: FileReport) -> SignalFileReport:
        return cls(
            status=data["status"],
            parts=list(data["parts"]),
            rows_read=data["rows_read"],
            rows_written=data["rows_written"],
            rows_replaced=data["rows_replaced"],
            rows_kept=data["rows_kept"],
            rows_skipped=data["rows_skipped"],
            skipped_reasons=dict(data["skipped_reasons"]),
            commander=data["commander"],
            lists_read=data["lists_read"],
            null_value_reasons=dict(data["null_value_reasons"]),
            warnings=list(data["warnings"]),
            rate_alarms=list(data.get("rate_alarms", [])),
            fallbacks_used=dict(data.get("fallbacks_used", {})),
            pooled_into=data["pooled_into"],
            universes_refused=list(data["universes_refused"]),
            universes_unmatched=list(data["universes_unmatched"]),
        )


def is_core_rate_alarm_signal(signal_name: str) -> bool:
    """Whether ``signal_name`` is one of ``CORE_RATE_ALARM_SIGNALS`` (including bracket variants)."""
    if signal_name in CORE_RATE_ALARM_SIGNALS:
        return True
    base, sep, _variant = signal_name.partition(":")
    return bool(sep) and base in CORE_RATE_ALARM_SIGNALS


def _build_rate_alarm(
    *,
    signal_name: str,
    alarm_type: str,
    commander: str,
    count: int,
    denominator: int,
    threshold: float,
) -> SignalRateAlarm:
    rate = count / denominator
    pct = rate * 100.0
    threshold_pct = threshold * 100.0
    scope = f" [{commander}]" if commander else ""
    label = (
        "Null-Grund-Quote (unbekannte Werte)"
        if alarm_type == "null_reason_rate"
        else "Zähler-0-Quote (numerator == 0 bei Nenner > 0)"
    )
    message = (
        f"Raten-Alarm ({alarm_type}) für {signal_name}{scope}: {label} "
        f"{count}/{denominator} ({pct:.1f} %) überschreitet Schwelle "
        f"> {threshold_pct:.0f} % ({threshold:.2f})"
    )
    return {
        "signal_name": signal_name,
        "alarm_type": alarm_type,
        "commander": commander,
        "count": count,
        "denominator": denominator,
        "rate": round(rate, 6),
        "threshold": threshold,
        "message": message,
    }


def evaluate_core_signal_rate_alarms(
    rows: Sequence[_Row | Mapping[str, object]],
    *,
    commander: str | None = None,
    null_threshold: float = NULL_REASON_RATE_ALARM_THRESHOLD,
    zero_threshold: float = ZERO_NUMERATOR_RATE_ALARM_THRESHOLD,
) -> list[SignalRateAlarm]:
    """Evaluate core-signal null-reason and zero-numerator rate alarms (#1416).

    Accepts either internal ``_Row`` tuples ``(commander, signal, card, value, numerator,
    denominator)`` or mapping rows with keys ``signal``/``signal_name``, ``value``,
    ``numerator``, ``denominator``, and optional ``null_value_reasons`` / ``commander_name``.
    When ``commander`` is given, only rows belonging to that commander (or commander-independent
    rows with ``commander_name == ""``) are evaluated; otherwise rows are grouped by
    ``(commander_name, signal_name)`` if multiple commanders exist, or evaluated per signal.
    """
    grouped: dict[tuple[str, str], list[tuple[float | None, int | None, int | None, bool]]] = {}
    target_cmd = commander.strip() if commander is not None else None
    for item in rows:
        if isinstance(item, tuple):
            row_cmd, sig, _card, val, num, den = item
            has_null_reason = val is None
        else:
            row_cmd = str(item.get("commander_name", item.get("commander", "")) or "")
            sig = str(item.get("signal_name", item.get("signal", "")) or "")
            raw_val = item.get("value")
            val = float(raw_val) if isinstance(raw_val, int | float) else None
            raw_num = item.get("numerator")
            num = (
                int(raw_num) if isinstance(raw_num, int) and not isinstance(raw_num, bool) else None
            )
            raw_den = item.get("denominator")
            den = (
                int(raw_den) if isinstance(raw_den, int) and not isinstance(raw_den, bool) else None
            )
            reasons = item.get("null_value_reasons")
            has_reasons = bool(reasons) if isinstance(reasons, Mapping | Sequence | set) else False
            has_null_reason = val is None or has_reasons
        if not is_core_rate_alarm_signal(sig):
            continue
        if target_cmd is not None and row_cmd not in (target_cmd, ""):
            continue
        grouped.setdefault((row_cmd, sig), []).append((val, num, den, has_null_reason))

    alarms: list[SignalRateAlarm] = []
    for (row_cmd, sig), entries in sorted(grouped.items()):
        total_rows = len(entries)
        if total_rows <= 0:
            continue
        null_reason_rows = sum(1 for _val, _num, _den, is_null in entries if is_null)
        if null_reason_rows / total_rows > null_threshold:
            alarms.append(
                _build_rate_alarm(
                    signal_name=sig,
                    alarm_type="null_reason_rate",
                    commander=row_cmd,
                    count=null_reason_rows,
                    denominator=total_rows,
                    threshold=null_threshold,
                )
            )
        pos_entries = [
            (val, num, den) for val, num, den, _is_null in entries if den is not None and den > 0
        ]
        positive_denominator_rows = len(pos_entries)
        if positive_denominator_rows > 0:
            zero_numerator_rows = sum(
                1
                for val, num, _den in pos_entries
                if num == 0 or (num is None and val is not None and val == 0.0)
            )
            if zero_numerator_rows / positive_denominator_rows > zero_threshold:
                alarms.append(
                    _build_rate_alarm(
                        signal_name=sig,
                        alarm_type="zero_numerator_rate",
                        commander=row_cmd,
                        count=zero_numerator_rows,
                        denominator=positive_denominator_rows,
                        threshold=zero_threshold,
                    )
                )
    return alarms


def store_signal_rows_by_commander(store: StudioStore) -> dict[str, list[_Row]]:
    """Every stored signal row as the rate alarms read it, per commander name, each list in
    the order ``compute_store_signal_rate_alarms`` reads it (signal, card name)."""
    found: dict[str, list[_Row]] = {}
    for r in store.connection.execute(
        "SELECT commander_name, signal, card_name, value, numerator, denominator "
        "FROM card_signal ORDER BY commander_name, signal, card_name"
    ):
        found.setdefault(str(r[0]), []).append(
            (
                str(r[0]),
                str(r[1]),
                str(r[2]),
                float(r[3]) if r[3] is not None else None,
                int(r[4]) if r[4] is not None else None,
                int(r[5]) if r[5] is not None else None,
            )
        )
    return found


def compute_store_signal_rate_alarms(
    store: StudioStore,
    *,
    commander: str | None = None,
    null_threshold: float = NULL_REASON_RATE_ALARM_THRESHOLD,
    zero_threshold: float = ZERO_NUMERATOR_RATE_ALARM_THRESHOLD,
    rows_by_commander: Mapping[str, Sequence[_Row]] | None = None,
) -> list[SignalRateAlarm]:
    """Compute core-signal rate alarms across stored rows in ``store`` (#1416).

    ``rows_by_commander`` (from ``store_signal_rows_by_commander``, read once by a caller that
    asks for many commanders) replaces the per-call read of one commander's rows; the rows and
    their order are the same, so are the alarms."""
    db = store.connection
    if commander is not None and rows_by_commander is not None:
        cmd = commander.strip()
        # The SQL order below (commander name first): the independent rows ('') come first.
        own = rows_by_commander.get(cmd, ()) if cmd else ()
        return evaluate_core_signal_rate_alarms(
            [*rows_by_commander.get("", ()), *own],
            commander=commander,
            null_threshold=null_threshold,
            zero_threshold=zero_threshold,
        )
    if commander is not None:
        cmd = commander.strip()
        sql_rows = db.execute(
            "SELECT commander_name, signal, card_name, value, numerator, denominator "
            "FROM card_signal WHERE commander_name IN (?, '') "
            "ORDER BY commander_name, signal, card_name",
            (cmd,),
        ).fetchall()
    else:
        sql_rows = db.execute(
            "SELECT commander_name, signal, card_name, value, numerator, denominator "
            "FROM card_signal ORDER BY commander_name, signal, card_name"
        ).fetchall()
    tuples: list[_Row] = [
        (
            str(r[0]),
            str(r[1]),
            str(r[2]),
            float(r[3]) if r[3] is not None else None,
            int(r[4]) if r[4] is not None else None,
            int(r[5]) if r[5] is not None else None,
        )
        for r in sql_rows
    ]
    return evaluate_core_signal_rate_alarms(
        tuples,
        commander=commander,
        null_threshold=null_threshold,
        zero_threshold=zero_threshold,
    )


def _apply_file_rate_alarms(
    rows: Sequence[_Row],
    report: FileReport,
    *,
    preferred_commander: str | None = None,
) -> None:
    alarms = evaluate_core_signal_rate_alarms(rows, commander=preferred_commander)
    report["rate_alarms"].extend(alarms)
    for alarm in alarms:
        report["warnings"].append(alarm["message"])


def import_signal_file(
    store: StudioStore,
    path_or_paths: str | Path | Sequence[str | Path],
    *,
    commander: str = "",
    file_name: str | None = None,
    variant: str | None = None,
    replace: bool = True,
) -> SignalFileReport:
    """Import a single signal file (or its split parts) and evaluate core-signal rate alarms."""
    if isinstance(path_or_paths, str | Path):
        paths = [Path(path_or_paths)]
    else:
        paths = [Path(p) for p in path_or_paths]
    report = _empty(paths)
    if not paths or not all(p.is_file() for p in paths):
        report["status"] = "ABSENT"
        return SignalFileReport.from_dict(report)
    inferred_name = file_name or re.sub(r"_\d+$", "", paths[0].stem)
    inferred_variant = variant
    if inferred_variant is None and inferred_name.startswith(f"{BRACKET_FILE}_"):
        suffix = inferred_name.removeprefix(f"{BRACKET_FILE}_")
        if suffix in BRACKET_VARIANTS:
            inferred_variant = suffix
    independent = (
        CARD_FILE,
        GLOBAL_FILE,
        SPELLBOOK_FILE,
        SHELLS_FILE,
        EDHTOP16_FILE,
        ATLAS_FILE,
        SALT_FILE,
    )
    base = inferred_name if inferred_name in independent else None
    kind = base or BRACKET_FILE
    commanders = _Commanders(store)
    preferred = commanders.resolve(commander.strip()) if commander.strip() else None
    with store.connection:
        rows = _read_file(kind, paths, inferred_variant, report, commanders)
        _apply_file_rate_alarms(rows, report, preferred_commander=preferred)
        if report["fallbacks_used"]:
            record_store_fallbacks(store, report["fallbacks_used"])
        source_id = _register(store, paths)
        if source_id is not None and rows:
            written, replaced = _store_rows(
                store,
                rows,
                source_id,
                replace=replace,
                declared=_file_signals(kind, inferred_variant),
            )
            report["rows_written"], report["rows_replaced"] = written, replaced
        else:
            report["status"] = "NOTHING_REPLACED"
            report["rows_kept"] = _kept_rows(store, _file_signals(kind, inferred_variant), None)
    return SignalFileReport.from_dict(report)


def import_signals(
    store: StudioStore, folder: str | Path, *, commander: str, replace: bool = True
) -> dict[str, object]:
    """Import every signal file of ``folder`` (all optional); one report entry per file.

    The EDHREC signals carry their own commander column; every ``topdeck_*_decks`` file
    belongs to the commander written in its commander section, ``commander`` breaks a tie
    between commanders of equal count. All files are written in one transaction.

    The report is truthful about what changed: per file ``rows_written`` and
    ``rows_replaced`` (existing rows of the same commander and signal that were swapped for
    the new ones) and, when a file had no valid row, ``status`` ``NOTHING_REPLACED`` with
    ``rows_kept``, the existing rows that stayed; a counted deck-list file that fails its
    checks has ``status`` ``REFUSED`` and a reason in ``skipped_reasons``. ``commanders_imported`` and
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
    plan += [(GLOBAL_FILE, None), (SPELLBOOK_FILE, None), (SHELLS_FILE, None)]
    plan += [(EDHTOP16_FILE, None), (SALT_FILE, None)]
    plan += [(ATLAS_FILE, None)]
    commanders = _Commanders(store)
    preferred = commanders.resolve(name)
    commanders.imported.discard(preferred)  # only commanders the files name are "imported"
    commanders.not_recognised.discard(name)
    with store.connection:
        _import_tournaments(store, root, preferred, commanders, reports, replace=replace)
        _import_decklists(store, root, preferred, name, reports, replace=replace)
        for file_name, variant in plan:
            paths = _parts(root, file_name)
            report = _empty(paths)
            reports[file_name] = report
            if not paths:
                continue
            independent = (
                CARD_FILE,
                GLOBAL_FILE,
                SPELLBOOK_FILE,
                SHELLS_FILE,
                EDHTOP16_FILE,
                ATLAS_FILE,
                SALT_FILE,
            )
            base = file_name if file_name in independent else None
            kind = base or BRACKET_FILE
            rows = _read_file(kind, paths, variant, report, commanders)
            _apply_file_rate_alarms(rows, report, preferred_commander=preferred)
            source_id = _register(store, paths)
            if source_id is not None and rows:
                written, replaced = _store_rows(
                    store,
                    rows,
                    source_id,
                    replace=replace,
                    declared=_file_signals(kind, variant),
                )
                report["rows_written"], report["rows_replaced"] = written, replaced
            else:
                report["status"] = "NOTHING_REPLACED"
                report["rows_kept"] = _kept_rows(store, _file_signals(kind, variant), None)
        _import_combos(store, root, preferred, reports, replace=replace)
        total_fallbacks: dict[str, int] = {}
        for rep in reports.values():
            for fb_key, fb_cnt in rep["fallbacks_used"].items():
                total_fallbacks[fb_key] = total_fallbacks.get(fb_key, 0) + fb_cnt
        if total_fallbacks:
            record_store_fallbacks(store, total_fallbacks)
    rate_alarms = [alarm for report in reports.values() for alarm in report["rate_alarms"]]
    return {
        "folder": root.name,
        "tournament_commander": preferred,
        "mode": "replace" if replace else "append",
        "files": reports,
        "files_refused": sum(1 for report in reports.values() if report["status"] == REFUSED),
        "universes_refused": sum(len(report["universes_refused"]) for report in reports.values()),
        "rows_unmatched": sum(
            item["rows"] for report in reports.values() for item in report["universes_unmatched"]
        ),
        "rows_written": sum(report["rows_written"] for report in reports.values()),
        "rows_replaced": sum(report["rows_replaced"] for report in reports.values()),
        "rows_kept": sum(report["rows_kept"] for report in reports.values()),
        "warnings": [
            f"{file}: {warning}"
            for file, report in reports.items()
            for warning in report["warnings"]
        ],
        "rate_alarms": rate_alarms,
        "fallbacks_used": dict(sorted(total_fallbacks.items())),
        "commanders_imported": sorted(commanders.imported),
        "commanders_not_recognised": sorted(commanders.not_recognised),
        "commanders_normalised": [
            {"from": raw, "to": found} for raw, found in sorted(commanders.normalised.items())
        ],
    }


def import_signals_directory(
    store: StudioStore, folder: str | Path, *, commander: str, replace: bool = True
) -> dict[str, object]:
    """Alias for ``import_signals`` (#1416)."""
    return import_signals(store, folder, commander=commander, replace=replace)
