"""Per-card corpus trend: recent decks versus older decks from stored deck dates.

Everything here is a derived descriptive count over the deduplicated source decks already
in the Studio store (``corpus_deck.deck_date`` and ``corpus_deck_card``), with no network
access and no schema change.

For a commander (and an optional bracket filter), deduplicated decks are partitioned by
``deck_date`` relative to the newest stored ``deck_date`` (``data_as_of``):

- recent window: ``deck_date >= data_as_of - recent_days``
- older window: ``deck_date < data_as_of - recent_days``
- undated decks: excluded from both windows and reported in ``excluded_no_date``

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
  ``ci_low``, ``ci_high``, ``excludes_zero``, and ``direction`` (``rising``, ``falling``,
  ``flat``). A card in ``0`` of ``N > 0`` decks stays ``0 / N`` (``0.0``), never ``None``.

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

ORIGIN_NOTE = (
    "Abgeleitet aus den deduplizierten Quelldecks des eigenen Korpus "
    "(corpus_deck.deck_date), ohne neuen Netzabruf."
)
LIMITATION_DATE = (
    "Das Datum ist das Speicher- oder Änderungsdatum der Liste bei der Quelle, "
    "nicht das Erstelldatum."
)
LIMITATION_BRACKET = (
    "Je Bracket sind die jungen Kohorten klein; Standard ist deshalb der ganze Korpus, "
    "Bracket nur mit Warnung."
)
LIMITATION_STRENGTH = (
    "Verbreitung ist nicht Stärke. Der Trend hat kein Gewicht im Stärke-Index und ist "
    "getrennt von EDHREC-, Playgroup- und Turnierzahlen."
)

TrendStatus = Literal["ok", "too_few_data", "unknown"]
TrendDirection = Literal["rising", "falling", "flat", "too_few_data", "unknown"]


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
    rising: int
    falling: int
    excludes_zero: int


class CardTrendResult(TypedDict):
    schema: str
    data_class: str
    commander: list[str]
    bracket: str | None
    recent_days: int
    min_decks_per_window: int
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


def _normalize_bracket(bracket: str | None) -> str | None:
    if bracket is None:
        return None
    cleaned = bracket.strip()
    if not cleaned or cleaned.casefold() == "all":
        return None
    if cleaned in {"1", "2", "3", "4", "5"}:
        return f"bracket:{cleaned}"
    if cleaned.startswith("bracket:") and len(cleaned) > len("bracket:"):
        return cleaned
    raise ValueError(f"unsupported bracket filter: {bracket}")


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


def _compute_card_trend(
    store: StudioStore,
    commander_names: tuple[str, ...],
    recent_days: int,
    min_decks_per_window: int,
    bracket: str | None,
) -> CardTrendResult:
    spec: UniverseSpec = {"commanders": list(commander_names)}
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
            if raw_low > 0.0:
                direction: TrendDirection = "rising"
                rising += 1
            elif raw_high < 0.0:
                direction = "falling"
                falling += 1
            else:
                direction = "flat"
        elif window_status == "too_few_data":
            diff = None
            ci_low = None
            ci_high = None
            excludes_zero = False
            direction = "too_few_data"
        else:
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
                "status": window_status,
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
            "ganzen Korpus."
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
        "bracket": bracket,
        "recent_days": recent_days,
        "min_decks_per_window": min_decks_per_window,
        "data_as_of": data_as_of,
        "oldest_date": oldest_date,
        "cutoff_date": cutoff_date,
        "recent_total": recent_total,
        "older_total": older_total,
        "excluded_no_date": excluded_no_date,
        "status": window_status,
        "summary": {
            "cards_total": len(cards),
            "rising": rising,
            "falling": falling,
            "excludes_zero": rising + falling,
        },
        "origin_note": ORIGIN_NOTE,
        "warnings": warnings,
        "limitations": [LIMITATION_DATE, LIMITATION_BRACKET, LIMITATION_STRENGTH],
        "cards": cards,
    }


def card_trend(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    recent_days: int = DEFAULT_RECENT_DAYS,
    min_decks_per_window: int = DEFAULT_MIN_DECKS_PER_WINDOW,
    bracket: str | None = None,
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
    normalized_bracket = _normalize_bracket(bracket)
    key = (
        "card_trend",
        cleaned_commanders,
        recent_days,
        min_decks_per_window,
        normalized_bracket,
    )
    return cached(
        store,
        key,
        lambda: _compute_card_trend(
            store, cleaned_commanders, recent_days, min_decks_per_window, normalized_bracket
        ),
    )
