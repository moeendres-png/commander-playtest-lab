"""TopDeck tournament conversion analysis with vs. without card (#1412).

Pure local calculation over TopDeck tournament deck CSVs (``topdeck_*_decks.csv``):
no network calls, no player names stored or returned, and strict fail-closed
minimum sample enforcement (``MIN_CONVERSION = 20``).

Top-cut conversion follows the normative definition from ``compute_topdeck_conversion.py``
and ``docs/TOPDECK.md`` §6:
- Denominator (``total_known_decks``): deduplicated single-commander decks in tournaments
  with ``top_cut > 0`` AND a known bracket record (``wins_bracket is not None`` or
  ``losses_bracket is not None``).
- Converted: ``(wins_bracket or 0) + (losses_bracket or 0) > 0``.
- Per card (``main`` section): split known decks into ``with_known`` vs ``without_known``,
  computing exact conversion rates, 95% Wilson score intervals, and ``diff_pp``
  (only when BOTH groups meet ``MIN_CONVERSION``, else ``None`` — never ``0``).
"""

from __future__ import annotations

import csv
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from . import strength

MIN_CONVERSION: int = strength.DEFAULT_MIN_DENOMINATORS[strength.MIN_CONVERSION]
COHORT = "Bracket 5 (Turnier)"
DATA_CLASS = "DERIVED_DESCRIPTIVE"
STATUS_OK = "OK"
STATUS_PARTIAL = "PARTIAL"
STATUS_INSUFFICIENT = "INSUFFICIENT_DATA"
INSUFFICIENT_REASON = "zu wenig Daten"
INSUFFICIENT_WITHOUT_REASON = "zu wenig Daten ohne Karte"

TOPDECK_DIR_ENV = "COMMANDER_LAB_TOPDECK_DIR"
DEFAULT_RESEARCH_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "research" / "topdeck_20261115"
)
_TOURNAMENT_PATTERN = re.compile(r"^(topdeck_.+_decks)(?:_(\d+))?\.csv$")
_COUNTED_SECTIONS = frozenset({"main", "commander"})


class CardConversionComparison(TypedDict):
    card_name: str
    total_known_decks: int
    with_known: int
    with_converted: int
    with_rate: float | None
    with_ci_low: float | None
    with_ci_high: float | None
    without_known: int
    without_converted: int
    without_rate: float | None
    without_ci_low: float | None
    without_ci_high: float | None
    diff_pp: float | None
    status: str
    reason: str | None
    cohort: str
    data_class: str


class CommanderConversionReport(TypedDict):
    commander: str
    cohort: str
    data_class: str
    min_sample: int
    total_decks: int
    total_known_decks: int
    total_converted_decks: int
    baseline_conversion_rate: float | None
    baseline_ci_low: float | None
    baseline_ci_high: float | None
    status: str
    reason: str | None
    source_files: list[str]
    cards: list[CardConversionComparison]


@dataclass(frozen=True)
class _ParsedDeck:
    """In-memory deck record without any player identifier."""

    commander: str
    cards: frozenset[str]
    top_cut_reached: bool | None


@dataclass(slots=True)
class _GroupedDeck:
    """Mutable grouping accumulator before finalizing into _ParsedDeck."""

    commanders: set[str]
    cards: set[str]
    top_cut_reached: bool | None


def _resolve_research_dir(research_dir: str | Path | None = None) -> Path:
    if research_dir is not None:
        return Path(research_dir)
    env_dir = os.environ.get(TOPDECK_DIR_ENV, "").strip()
    if env_dir:
        return Path(env_dir)
    return DEFAULT_RESEARCH_DIR


def research_dir() -> Path:
    """The TopDeck folder ``analyze_commander_conversion`` reads without an explicit folder."""
    return _resolve_research_dir()


def _optional_int(raw: object) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(float(text)) if "." in text else int(text)
    except ValueError:
        return None


def _top_cut_reached(
    top_cut: int | None, wins_bracket: int | None, losses_bracket: int | None
) -> bool | None:
    if top_cut is None or top_cut <= 0:
        return None
    if wins_bracket is None and losses_bracket is None:
        return None
    return ((wins_bracket or 0) + (losses_bracket or 0)) > 0


def wilson_interval(
    numerator: int, denominator: int, z: float = strength.Z_95
) -> tuple[float, float] | None:
    """Two-sided Wilson score interval ``(ci_low, ci_high)`` in ``[0, 1]``."""
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        return None
    n = float(denominator)
    p = numerator / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))) / denom
    low = 0.0 if numerator == 0 else max(0.0, center - half)
    high = 1.0 if numerator == denominator else min(1.0, center + half)
    return (low, high)


def _tournament_csv_paths(folder: Path) -> list[tuple[str, Path]]:
    if not folder.is_dir():
        return []
    matched: list[tuple[str, int, Path]] = []
    for path in folder.iterdir():
        if not path.is_file():
            continue
        m = _TOURNAMENT_PATTERN.match(path.name)
        if m:
            part = int(m.group(2)) if m.group(2) else 0
            matched.append((m.group(1), part, path))
    matched.sort(key=lambda item: (item[0], item[1], item[2].name))
    return [(item[0], item[2]) for item in matched]


def _read_commander_decks(commander: str, folder: Path) -> tuple[list[_ParsedDeck], list[str]]:
    """Read and deduplicate single-commander decks across all TopDeck CSVs in ``folder``.

    Deduplication key is ``(base_stem, tournament, date, player)``; scoping by the
    commander-file base stem keeps multipart deduplication intact while preventing
    anonymized ``Liste N`` labels from colliding across different commander files.
    Player labels are discarded immediately after grouping and never leave this function.
    """
    target_cf = commander.strip().casefold()
    if not target_cf:
        return [], []

    grouped: dict[tuple[str, str, str, str], _GroupedDeck] = {}
    used_files: list[str] = []

    for base_stem, csv_path in _tournament_csv_paths(folder):
        file_has_target = False
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                section = str(row.get("section") or "").strip().lower()
                if section not in _COUNTED_SECTIONS:
                    continue
                card_name = str(row.get("card_name") or "").strip()
                if not card_name:
                    continue
                t_name = str(row.get("tournament") or "").strip()
                d_str = str(row.get("date") or "").strip()
                p_name = str(row.get("player") or "").strip()
                key = (base_stem, t_name, d_str, p_name)

                entry = grouped.get(key)
                if entry is None:
                    tc = _optional_int(row.get("topCut") or row.get("top_cut"))
                    wb = _optional_int(row.get("winsBracket") or row.get("wins_bracket"))
                    lb = _optional_int(row.get("lossesBracket") or row.get("losses_bracket"))
                    entry = _GroupedDeck(
                        commanders=set(),
                        cards=set(),
                        top_cut_reached=_top_cut_reached(tc, wb, lb),
                    )
                    grouped[key] = entry

                if section == "commander":
                    entry.commanders.add(card_name)
                    if card_name.casefold() == target_cf:
                        file_has_target = True
                else:
                    qty = _optional_int(row.get("quantity"))
                    if qty is None or qty > 0:
                        entry.cards.add(card_name)

        if file_has_target:
            used_files.append(csv_path.name)

    parsed: list[_ParsedDeck] = []
    for entry in grouped.values():
        if len(entry.commanders) != 1:
            continue
        sole_cmd = next(iter(entry.commanders))
        if sole_cmd.casefold() != target_cf:
            continue
        parsed.append(
            _ParsedDeck(
                commander=sole_cmd,
                cards=frozenset(entry.cards),
                top_cut_reached=entry.top_cut_reached,
            )
        )
    return parsed, sorted(set(used_files))


def analyze_commander_conversion(
    commander: str,
    research_dir: str | Path | None = None,
    *,
    min_sample: int = MIN_CONVERSION,
) -> CommanderConversionReport:
    """Compute TopDeck with-vs-without conversion statistics for ``commander``."""
    folder = _resolve_research_dir(research_dir)
    decks, source_files = _read_commander_decks(commander, folder)

    total_decks = len(decks)
    known_decks = [d for d in decks if d.top_cut_reached is not None]
    total_known = len(known_decks)
    total_converted = sum(1 for d in known_decks if d.top_cut_reached)

    commander_ok = total_known >= min_sample
    baseline_rate: float | None = None
    baseline_low: float | None = None
    baseline_high: float | None = None
    if commander_ok:
        baseline_rate = total_converted / total_known
        ci = wilson_interval(total_converted, total_known)
        if ci is not None:
            baseline_low, baseline_high = ci

    all_cards: set[str] = set()
    for d in decks:
        all_cards.update(d.cards)

    comparisons: list[CardConversionComparison] = []
    for card_name in sorted(all_cards):
        with_known = 0
        with_converted = 0
        for d in known_decks:
            if card_name in d.cards:
                with_known += 1
                if d.top_cut_reached:
                    with_converted += 1

        without_known = total_known - with_known
        without_converted = total_converted - with_converted

        with_rate: float | None = None
        with_ci_low: float | None = None
        with_ci_high: float | None = None
        without_rate: float | None = None
        without_ci_low: float | None = None
        without_ci_high: float | None = None
        diff_pp: float | None = None

        if not commander_ok or with_known < min_sample:
            status = STATUS_INSUFFICIENT
            reason: str | None = INSUFFICIENT_REASON
        else:
            with_rate = with_converted / with_known
            with_ci = wilson_interval(with_converted, with_known)
            if with_ci is not None:
                with_ci_low, with_ci_high = with_ci

            if without_known >= min_sample:
                without_rate = without_converted / without_known
                without_ci = wilson_interval(without_converted, without_known)
                if without_ci is not None:
                    without_ci_low, without_ci_high = without_ci
                diff_pp = (with_rate - without_rate) * 100.0
                status = STATUS_OK
                reason = None
            else:
                status = STATUS_PARTIAL
                reason = INSUFFICIENT_WITHOUT_REASON

        comparisons.append(
            CardConversionComparison(
                card_name=card_name,
                total_known_decks=total_known,
                with_known=with_known,
                with_converted=with_converted,
                with_rate=with_rate,
                with_ci_low=with_ci_low,
                with_ci_high=with_ci_high,
                without_known=without_known,
                without_converted=without_converted,
                without_rate=without_rate,
                without_ci_low=without_ci_low,
                without_ci_high=without_ci_high,
                diff_pp=diff_pp,
                status=status,
                reason=reason,
                cohort=COHORT,
                data_class=DATA_CLASS,
            )
        )

    status_rank = {STATUS_OK: 0, STATUS_PARTIAL: 1, STATUS_INSUFFICIENT: 2}
    comparisons.sort(
        key=lambda row: (
            status_rank.get(row["status"], 3),
            -(row["diff_pp"] if row["diff_pp"] is not None else -1e9),
            -row["with_known"],
            row["card_name"],
        )
    )

    return CommanderConversionReport(
        commander=commander,
        cohort=COHORT,
        data_class=DATA_CLASS,
        min_sample=min_sample,
        total_decks=total_decks,
        total_known_decks=total_known,
        total_converted_decks=total_converted,
        baseline_conversion_rate=baseline_rate,
        baseline_ci_low=baseline_low,
        baseline_ci_high=baseline_high,
        status=STATUS_OK if commander_ok else STATUS_INSUFFICIENT,
        reason=None if commander_ok else INSUFFICIENT_REASON,
        source_files=source_files,
        cards=comparisons,
    )
