"""Per-card corpus trend: recent decks versus older decks from stored deck dates.

Everything here is a derived descriptive count over the deduplicated source decks already
in the Studio store (``corpus_deck.deck_date`` and ``corpus_deck_card``), with no network
access and no schema change.

For a commander, one source and an optional bracket filter, deduplicated decks are
partitioned by ``deck_date`` relative to the newest stored ``deck_date`` (``data_as_of``):

- recent window: ``deck_date >= data_as_of - recent_days``
- older window: ``deck_date < data_as_of - recent_days``
- undated decks: excluded from both windows and reported in ``excluded_no_date``

The source is never mixed (Owner rule: cohorts and sources are never pooled). The default is
``edhrec`` (the largest source); ``archidekt`` can be chosen on its own. A pooled "whole corpus"
would change its source mix between the windows (Archidekt share 5.4 % in the older window,
9.8 % in the recent one, measured on the Chulane corpus of 2026-11-15) and so show a source
effect as a card trend. "Whole corpus" in the sense of #1550 means: all brackets of one source.

For each Studio card, the module reports ``recent_hits / recent_total``,
``older_hits / older_total``, their shares, the difference ``recent_share - older_share``,
and the 95 % Newcombe hybrid score interval (reusing ``wilson_unrounded`` and
``newcombe_difference`` from ``card_outcomes.py``).

Semantics:
- Missing window (``recent_total == 0`` or ``older_total == 0``): the empty window's share
  is ``None`` ("unbekannt"), ``status = "unknown"``, ``diff`` and interval are ``None``.
- Small window (``0 < total < min_decks_per_window`` on either side): shares remain exact
  (including ``0 / N = 0.0``), ``status = "too_few_data"`` ("zu wenig Daten"), ``diff`` and
  interval are ``None`` so no unstable trend is shown.
- Sufficient windows (both ``>= min_decks_per_window``): ``status = "ok"``, with ``diff``,
  ``ci_low``, ``ci_high``, ``excludes_zero`` and ``direction``. A card in ``0`` of ``N > 0``
  decks stays ``0 / N`` (``0.0``), never ``None``.
- A card with 0 hits in the older window and hits in the recent one is no trend but a release
  date effect: ``status = direction = "new_in_recent_window"``, no arrow.
- An arrow (``rising`` / ``falling``) needs the interval to exclude zero AND
  ``|diff| >= min_arrow_diff`` (default 2 percentage points); otherwise ``flat``. The interval
  alone is not enough: one 95 % interval is computed per card (1,655 cards, 741 of them with
  hits), and without a multiple-testing correction about 5 % of unchanged cards still get an
  arrow. A fixed minimum effect is the simpler, auditable guard. Not chosen: a Bonferroni/Holm
  correction (z about 4.0 for 741 cards with hits instead of 1.96) needs a z other than the
  fixed one of the shared ``wilson_unrounded`` in ``card_outcomes.py`` (a change to a shared
  function), and with about 3,000 recent and 6,700 older decks it would still flag
  differences below one percentage point for cards with a small share, which carry no
  practical meaning for a deck builder.

This signal has zero weight in the strength index and stays strictly separate from EDHREC,
playgroup and tournament figures.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Literal, TypedDict

from .cache import cached
from .card_outcomes import newcombe_difference, wilson_unrounded
from .store import StudioStore
from .universe import UniverseSpec, _universe_table, deck_sets, resolve_universe, spelling_owners

SCHEMA = "studio-card-trend-1"
DATA_CLASS = "DERIVED_DESCRIPTIVE"
DEFAULT_RECENT_DAYS = 180
DEFAULT_MIN_DECKS_PER_WINDOW = 30
# Sources of the corpus (``corpus_deck.platform``); never mixed. The first is the default.
SOURCES = ("edhrec", "archidekt")
DEFAULT_SOURCE = SOURCES[0]
# Smallest absolute share difference (2 percentage points) that earns an arrow, on top of the
# interval excluding zero. Why: see the module docstring (multiple testing without correction).
DEFAULT_MIN_ARROW_DIFF = 0.02

ORIGIN_NOTE = (
    "Abgeleitet aus den deduplizierten Quelldecks des eigenen Korpus "
    "(corpus_deck.deck_date), ohne neuen Netzabruf."
)
LIMITATION_DATE = (
    "Das Datum ist das Speicher- oder Änderungsdatum der Liste bei der Quelle, "
    "nicht das Erstelldatum."
)
LIMITATION_BRACKET = (
    "Je Bracket sind die jungen Kohorten klein; Standard sind deshalb alle Brackets einer "
    "Quelle, ein einzelnes Bracket nur mit Warnung."
)
LIMITATION_SOURCE = (
    "Die Quellen (EDHREC, Archidekt) werden nie gemischt; der Trend gilt für die gewählte Quelle."
)
LIMITATION_MULTIPLE_TESTS = (
    "Alle Karten werden gleichzeitig geprüft, ohne Korrektur für Mehrfachtests: einzelne Pfeile "
    "können Zufall sein. Ein Pfeil braucht deshalb zusätzlich mindestens {pp} Prozentpunkte "
    "Unterschied. Eine Karte, die im alten Fenster nicht vorkam, ist neu und kein Trend."
)
LIMITATION_STRENGTH = (
    "Verbreitung ist nicht Stärke. Der Trend hat kein Gewicht im Stärke-Index und ist "
    "getrennt von EDHREC-, Playgroup- und Turnierzahlen."
)

TrendStatus = Literal["ok", "too_few_data", "unknown", "new_in_recent_window"]
TrendDirection = Literal[
    "rising", "falling", "flat", "new_in_recent_window", "too_few_data", "unknown"
]


class CardTrendRow(TypedDict):
    card_id: str
    oracle_id: str | None
    name: str
    status: TrendStatus
    recent_hits: int
    recent_total: int
    recent_share: float | None
    older_hits: int
    older_total: int
    older_share: float | None
    diff: float | None
    ci_low: float | None
    ci_high: float | None
    excludes_zero: bool
    direction: TrendDirection


class CardTrendSummary(TypedDict):
    cards_total: int
    cards_tested: int  # cards with hits in at least one window, in a window pair that is "ok"
    excludes_zero: int  # interval excludes zero (new cards not counted)
    below_min_arrow_diff: int  # interval excludes zero, but the difference is too small
    new_in_recent_window: int
    rising: int
    falling: int


class CardTrendResult(TypedDict):
    schema: str
    data_class: str
    commander: list[str]
    source: str
    bracket: str | None
    recent_days: int
    min_decks_per_window: int
    min_arrow_diff: float
    data_as_of: str | None
    oldest_date: str | None
    cutoff_date: str | None
    recent_total: int
    older_total: int
    excluded_no_date: int
    status: TrendStatus
    summary: CardTrendSummary
    origin_note: str
    warnings: list[str]
    limitations: list[str]
    cards: list[CardTrendRow]


_BRACKETS = ("1", "2", "3", "4", "5")


def _normalize_bracket(bracket: str | None) -> str | None:
    if bracket is None:
        return None
    cleaned = bracket.strip()
    if not cleaned or cleaned.casefold() == "all":
        return None
    number = cleaned.removeprefix("bracket:")
    if number in _BRACKETS:
        return f"bracket:{number}"
    raise ValueError(
        f"unsupported bracket filter: {bracket} (expected 1 to 5, bracket:1 to bracket:5 or all)"
    )


def _normalize_source(source: str | None) -> str:
    if source is None or not source.strip():
        return DEFAULT_SOURCE
    cleaned = source.strip().casefold()
    if cleaned not in SOURCES:
        raise ValueError(f"unsupported source: {source} (expected one of {', '.join(SOURCES)})")
    return cleaned


def _arrow(
    diff: float, low: float, high: float, min_arrow_diff: float
) -> Literal["rising", "falling", "flat"]:
    """The arrow of a card: the interval must exclude zero AND the (rounded, as reported)
    difference must reach ``min_arrow_diff`` in size; else ``flat``."""
    if round(abs(diff), 6) < min_arrow_diff:
        return "flat"
    if low > 0.0:
        return "rising"
    if high < 0.0:
        return "falling"
    return "flat"


def _parse_iso_date(raw: object) -> datetime.date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) < 10:
        return None
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _bracket_label(cohort: str) -> str:
    if cohort.startswith("bracket:"):
        return f"Bracket {cohort.split(':', 1)[1]}"
    return cohort


def _pp_text(fraction: float) -> str:
    """``0.02`` -> ``2`` (German decimal comma for non-integers)."""
    text = f"{fraction * 100:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _source_label(source: str) -> str:
    return {"edhrec": "EDHREC", "archidekt": "Archidekt"}.get(source, source)


def _compute_card_trend(
    store: StudioStore,
    commander_names: tuple[str, ...],
    recent_days: int,
    min_decks_per_window: int,
    bracket: str | None,
    source: str,
    min_arrow_diff: float,
) -> CardTrendResult:
    spec: UniverseSpec = {"commanders": list(commander_names), "platforms": [source]}
    if bracket is not None:
        spec["cohorts"] = [bracket]

    deck_ids = resolve_universe(store, spec)
    dated: list[tuple[str, datetime.date]] = []
    excluded_no_date = 0
    if deck_ids:
        with _universe_table(store, deck_ids, "card_trend_decks") as table:
            for row in store.connection.execute(
                f"SELECT d.deck_id, d.deck_date FROM corpus_deck d "
                f"JOIN {table} u ON u.deck_id = d.deck_id"
            ):
                parsed = _parse_iso_date(row[1])
                if parsed is None:
                    excluded_no_date += 1
                else:
                    dated.append((str(row[0]), parsed))

    if dated:
        newest = max(dt for _, dt in dated)
        oldest = min(dt for _, dt in dated)
        cutoff = newest - datetime.timedelta(days=recent_days)
        recent_deck_ids = [deck_id for deck_id, dt in dated if dt >= cutoff]
        older_deck_ids = [deck_id for deck_id, dt in dated if dt < cutoff]
        data_as_of: str | None = newest.isoformat()
        oldest_date: str | None = oldest.isoformat()
        cutoff_date: str | None = cutoff.isoformat()
    else:
        recent_deck_ids = []
        older_deck_ids = []
        data_as_of = None
        oldest_date = None
        cutoff_date = None

    recent_total = len(recent_deck_ids)
    older_total = len(older_deck_ids)

    if recent_total == 0 or older_total == 0:
        window_status: TrendStatus = "unknown"
    elif recent_total < min_decks_per_window or older_total < min_decks_per_window:
        window_status = "too_few_data"
    else:
        window_status = "ok"

    owners = spelling_owners(store)
    recent_sets = deck_sets(store, recent_deck_ids, group_of=owners) if recent_deck_ids else {}
    older_sets = deck_sets(store, older_deck_ids, group_of=owners) if older_deck_ids else {}

    card_rows = store.connection.execute(
        "SELECT card_id, oracle_id, oracle_name FROM card_fact ORDER BY oracle_name, card_id"
    ).fetchall()

    cards: list[CardTrendRow] = []
    rising = 0
    falling = 0
    new_cards = 0
    tested = 0
    interval_excludes_zero = 0
    below_min_diff = 0

    for row in card_rows:
        card_id = str(row["card_id"])
        oracle_id = str(row["oracle_id"]) if row["oracle_id"] is not None else None
        name = str(row["oracle_name"])

        recent_hits = len(recent_sets.get(name, set())) if recent_total > 0 else 0
        older_hits = len(older_sets.get(name, set())) if older_total > 0 else 0

        recent_share = round(recent_hits / recent_total, 6) if recent_total > 0 else None
        older_share = round(older_hits / older_total, 6) if older_total > 0 else None

        if window_status == "ok":
            p_recent = recent_hits / recent_total
            p_older = older_hits / older_total
            ci_recent = wilson_unrounded(recent_hits, recent_total)
            ci_older = wilson_unrounded(older_hits, older_total)
            raw_diff, raw_low, raw_high = newcombe_difference(
                p_recent, ci_recent, p_older, ci_older
            )
            diff: float | None = round(raw_diff, 6)
            ci_low: float | None = round(max(-1.0, raw_low), 6)
            ci_high: float | None = round(min(1.0, raw_high), 6)
            excludes_zero = raw_low > 0.0 or raw_high < 0.0
            row_status: TrendStatus = "ok"
            if older_hits == 0 and recent_hits > 0:
                # Not in a single older deck: a release date, not a trend. No arrow.
                direction: TrendDirection = "new_in_recent_window"
                row_status = "new_in_recent_window"
                new_cards += 1
            else:
                direction = _arrow(raw_diff, raw_low, raw_high, min_arrow_diff)
                if excludes_zero:
                    interval_excludes_zero += 1
                    if direction == "flat":
                        below_min_diff += 1
                if direction == "rising":
                    rising += 1
                elif direction == "falling":
                    falling += 1
            if recent_hits + older_hits > 0:
                tested += 1
        elif window_status == "too_few_data":
            row_status = "too_few_data"
            diff = None
            ci_low = None
            ci_high = None
            excludes_zero = False
            direction = "too_few_data"
        else:
            row_status = "unknown"
            diff = None
            ci_low = None
            ci_high = None
            excludes_zero = False
            direction = "unknown"

        cards.append(
            {
                "card_id": card_id,
                "oracle_id": oracle_id,
                "name": name,
                "status": row_status,
                "recent_hits": recent_hits,
                "recent_total": recent_total,
                "recent_share": recent_share,
                "older_hits": older_hits,
                "older_total": older_total,
                "older_share": older_share,
                "diff": diff,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "excludes_zero": excludes_zero,
                "direction": direction,
            }
        )

    warnings: list[str] = []
    if bracket is not None:
        warnings.append(
            f"Bracket-Filter aktiv ({_bracket_label(bracket)}): Je Bracket sind die jungen "
            "Kohorten klein; der Trend ist im Einzel-Bracket deutlich unsicherer als im "
            "ganzen Korpus der Quelle."
        )
    if window_status == "unknown":
        warnings.append(
            f"Mindestens ein Zeitfenster enthält 0 Decks (jung: {recent_total}, alt: "
            f"{older_total}); Trend daher unbekannt."
        )
    elif window_status == "too_few_data":
        warnings.append(
            f"Zu wenig Daten für einen Trend (Mindestzahl je Fenster: {min_decks_per_window}, "
            f"jung: {recent_total}, alt: {older_total})."
        )
    if excluded_no_date > 0:
        warnings.append(
            f"{excluded_no_date} deduplizierte Decks ohne gültiges Deck-Datum sind in keinem "
            "der beiden Zeitfenster enthalten."
        )

    return {
        "schema": SCHEMA,
        "data_class": DATA_CLASS,
        "commander": list(commander_names),
        "source": source,
        "bracket": bracket,
        "recent_days": recent_days,
        "min_decks_per_window": min_decks_per_window,
        "min_arrow_diff": min_arrow_diff,
        "data_as_of": data_as_of,
        "oldest_date": oldest_date,
        "cutoff_date": cutoff_date,
        "recent_total": recent_total,
        "older_total": older_total,
        "excluded_no_date": excluded_no_date,
        "status": window_status,
        "summary": {
            "cards_total": len(cards),
            "cards_tested": tested,
            "excludes_zero": interval_excludes_zero,
            "below_min_arrow_diff": below_min_diff,
            "new_in_recent_window": new_cards,
            "rising": rising,
            "falling": falling,
        },
        "origin_note": ORIGIN_NOTE,
        "warnings": warnings,
        "limitations": [
            LIMITATION_DATE,
            LIMITATION_SOURCE,
            LIMITATION_BRACKET,
            LIMITATION_MULTIPLE_TESTS.format(pp=_pp_text(min_arrow_diff)),
            LIMITATION_STRENGTH,
        ],
        "cards": cards,
    }


def card_trend(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    recent_days: int = DEFAULT_RECENT_DAYS,
    min_decks_per_window: int = DEFAULT_MIN_DECKS_PER_WINDOW,
    bracket: str | None = None,
    source: str | None = None,
    min_arrow_diff: float = DEFAULT_MIN_ARROW_DIFF,
) -> CardTrendResult:
    """Compute (or serve cached) per-card recent-vs-older corpus trends for a commander."""
    cleaned_commanders = tuple(
        sorted({str(name).strip() for name in commander_names if str(name).strip()})
    )
    if not cleaned_commanders:
        raise ValueError("at least one commander name is required")
    if recent_days < 1:
        raise ValueError("recent_days must be at least 1")
    if min_decks_per_window < 1:
        raise ValueError("min_decks_per_window must be at least 1")
    if not 0.0 <= min_arrow_diff <= 1.0:
        raise ValueError("min_arrow_diff must be between 0 and 1")
    normalized_bracket = _normalize_bracket(bracket)
    normalized_source = _normalize_source(source)
    key = (
        "card_trend",
        cleaned_commanders,
        recent_days,
        min_decks_per_window,
        normalized_bracket,
        normalized_source,
        min_arrow_diff,
    )
    return cached(
        store,
        key,
        lambda: _compute_card_trend(
            store,
            cleaned_commanders,
            recent_days,
            min_decks_per_window,
            normalized_bracket,
            normalized_source,
            min_arrow_diff,
        ),
    )
