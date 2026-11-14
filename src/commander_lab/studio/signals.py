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
- ``topdeck_card_conversions``: per commander and card, the TopDeck conversion:
  decks with the card that reached the tournament's top cut over the decks
  whose top-cut outcome is known at all (``sample_size_base``); that base is
  the stored denominator, so the strength component's Wilson bound is computed
  from the same figures the source published. The source publishes the rate
  only from a base of 10 (below it the file carries the literal ``NULL``);
  the numerator and denominator are stored anyway and the value stays NULL.
  ``appearances`` (every deck with the card, outcome known or not) is not
  stored: no strength component reads it, and the figure stays available in
  the source file.
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
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import TypedDict

from .store import DataClass, StudioStore, sha256_file

CARD_FILE = "commander_card_signals"
BRACKET_FILE = "commander_bracket_signals"
GLOBAL_FILE = "card_global_signals"
SPELLBOOK_FILE = "spellbook_card_links"
TOURNAMENT_FILE = "topdeck_chulane_decks"
EDHTOP16_FILE = "edhtop16_commander_signals"
CONVERSION_FILE = "topdeck_card_conversions"
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
SIGNAL_TOURNAMENT = "tournament_lists"
SIGNAL_SALT = "edhrec_salt"
SIGNAL_COMBO_DECKS = "edhrec_combo_decks"
SALT_FILE = "edhrec_salt"
COMBOS_FILE = "edhrec_chulane_combos"
SIGNAL_EDHTOP16 = "edhtop16_commander_play_rate"
SIGNAL_CONVERSION = "topdeck_card_conversion"
SIGNAL_DECKLIST = "decklist_universe"
REFUSED = "REFUSED"
COMMANDER_NOT_IN_EVERY_DECK = "COMMANDER_NOT_IN_EVERY_DECK"
MIXED_DENOMINATORS = "MIXED_DENOMINATORS"
INVALID_UNIVERSE_NAME = "INVALID_UNIVERSE_NAME"  # a ":" in the source or bracket
INVALID_COUNT = "INVALID_COUNT"
DECKLIST_COLUMNS = {"card_name", "source", "bracket", "decks_with_card", "universe_decks"}
SIGNAL_PLAYGROUP = "playgroup_observed_winrate_gap"

_Row = tuple[str, str, str, float | None, int | None, int | None]  # commander, signal, card, ...


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
    pooled_into: str | None  # tournament files: the file that carries the pooled rows stored
    universes_refused: list[RefusedUniverse]  # counted deck-list files: refused universes
    universes_unmatched: list[UnmatchedRows]  # counted deck-list files: rows without a card


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


def _deck_counts(row: dict[str, str], report: FileReport) -> tuple[int | None, int | None]:
    """Numerator and denominator of an inclusion figure; both None, with a counted reason,
    when either is missing or they contradict each other."""
    numerator = _count(row.get("num_decks"))
    denominator = _count(row.get("potential_decks"))
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
        synergy = _number(row.get("synergy"))
        if synergy is None:
            reason = (
                "SYNERGY_NOT_PUBLISHED"
                if not row.get("synergy", "").strip()
                else "SYNERGY_NOT_NUMERIC"
            )
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
        cards = sorted({name.strip() for name in row["cards"].split(";") if name.strip()})
        decks = _count(row["num_decks"])
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


def _read_topdeck_conversion(
    paths: list[Path], report: FileReport, commanders: _Commanders
) -> list[_Row]:
    """TopDeck conversion per commander and card, from the counted research file.

    The published rate is the conversions over the decks whose top-cut outcome
    is known at all (``sample_size_base``), and that base is the stored
    denominator — not ``appearances``, which also counts decks whose outcome
    is unknown, so a Wilson bound from it would rate a different figure than
    the one the source published. The source publishes the rate only from a
    base of 10; below it the file carries the literal ``NULL`` and the value
    stays NULL, while numerator and denominator are stored as counted, so the
    strength component's own minimum decides from real figures. A published
    rate that disagrees with its own numerator and denominator is refused,
    never silently trusted."""
    required = {
        "commander",
        "card_name",
        "appearances",
        "conversions",
        "conversion_rate",
        "sample_size_base",
    }
    pairs: list[tuple[tuple[str, str, str], _Row]] = []
    for row in _rows(paths, required):
        report["rows_read"] += 1
        commander, card = row["commander"].strip(), row["card_name"].strip()
        if not commander or not card:
            report["rows_skipped"] += 1
            report["skipped_reasons"]["NAME_MISSING"] = (
                report["skipped_reasons"].get("NAME_MISSING", 0) + 1
            )
            continue
        appearances = _count(row.get("appearances"))
        conversions = _count(row.get("conversions"))
        base = _count(row.get("sample_size_base"))
        if (
            appearances is None
            or conversions is None
            or base is None
            or conversions > base
            or base > appearances
        ):
            report["rows_skipped"] += 1
            report["skipped_reasons"]["CONVERSION_FIGURES_INVALID"] = (
                report["skipped_reasons"].get("CONVERSION_FIGURES_INVALID", 0) + 1
            )
            continue
        raw_rate = row.get("conversion_rate", "").strip()
        value: float | None = None
        if raw_rate and raw_rate != "NULL":
            rate = _number(raw_rate)
            if rate is None or base == 0 or abs(rate - conversions / base) > 1e-6:
                report["rows_skipped"] += 1
                report["skipped_reasons"]["INCONSISTENT_RATE"] = (
                    report["skipped_reasons"].get("INCONSISTENT_RATE", 0) + 1
                )
                continue
            value = rate
        else:
            reasons = report["null_value_reasons"]
            reasons["RATE_NOT_PUBLISHED"] = reasons.get("RATE_NOT_PUBLISHED", 0) + 1
        item: _Row = (
            commanders.resolve(commander),
            SIGNAL_CONVERSION,
            card,
            value,
            conversions,
            base,
        )
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
            source_id = store.register_source(
                data_class=DataClass.NORMALIZED_SOURCE,
                title=f"{paths[0].name}#{universe.snapshot}",
                sha256=hashlib.sha256(f"{file_hash}:{signal}".encode()).hexdigest(),
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


def _register(store: StudioStore, paths: list[Path]) -> str | None:
    """Register every part of a file; the rows carry the source of the whole file: its only
    part, or (several parts) one source whose hash covers all parts, not just the first."""
    ids: list[tuple[str, str]] = []
    for path in paths:
        digest = sha256_file(path)
        store.register_source(
            data_class=DataClass.NORMALIZED_SOURCE, title=path.name, sha256=digest
        )
        ids.append((path.name, digest))
    if len(ids) <= 1:
        return f"src:{ids[0][1][:16]}" if ids else None
    combined = hashlib.sha256(
        "".join(f"{name}:{digest}\n" for name, digest in ids).encode("utf-8")
    ).hexdigest()
    return store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title=f"{ids[0][0]} (+{len(ids) - 1} parts)",
        sha256=combined,
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
    if file_name == EDHTOP16_FILE:
        return [SIGNAL_EDHTOP16]
    if file_name == CONVERSION_FILE:
        return [SIGNAL_CONVERSION]
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
    if file_name == EDHTOP16_FILE:
        return _read_edhtop16(paths, report, commanders)
    if file_name == CONVERSION_FILE:
        return _read_topdeck_conversion(paths, report, commanders)
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
        EDHTOP16_FILE,
        CONVERSION_FILE,
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
    plan += [(GLOBAL_FILE, None), (SPELLBOOK_FILE, None)]
    plan += [(EDHTOP16_FILE, None), (SALT_FILE, None)]
    plan += [(ATLAS_FILE, None)]
    plan += [(CONVERSION_FILE, None)]
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
                EDHTOP16_FILE,
                ATLAS_FILE,
                SALT_FILE,
                CONVERSION_FILE,
            )
            base = file_name if file_name in independent else None
            kind = base or BRACKET_FILE
            rows = _read_file(kind, paths, variant, report, commanders)
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
        "commanders_imported": sorted(commanders.imported),
        "commanders_not_recognised": sorted(commanders.not_recognised),
        "commanders_normalised": [
            {"from": raw, "to": found} for raw, found in sorted(commanders.normalised.items())
        ],
    }
