"""The second overall rating of the tier list: "Kartenverständnis-Gesamtrating" (Owner decision
2026-11-18, #1369).

A transparent weighted mean (0 to 100) of eight axes: the card's usage index (the existing
strength index of the answer, read only) and the seven scores E, F, T, R, K, D, H of the
card-understanding data set (``card_understanding``). It stands next to the usage index and
never changes it: the tier, the index, the weights and the snapshots of the usage index stay as
they are; this module only adds the ``overall`` field of each card and ``overall_meta``.

The weights ``OVERALL_WEIGHTS_V1`` are a SETTING (Setzung), not a measurement: nothing here was
fitted to results. The ranking therefore comes with its stability against changed weights.

Locked rules (Owner decisions B11, E1.a, K5): no simulation value (weight 0), no measured result
layer (pace, play rate, staying power, win gap, large pod), no price, no mark (favourites and the
like) influences the rating; cohorts are never mixed (the usage axis is the cohort of the request:
its bracket and universe source); unknown is never 0; every number comes with n of N.

Missing axes: the weights of the axes a card has are renormalised, ``coverage`` is the share of
the nominal weights present. Below ``MIN_COVERAGE``, or without a card-understanding rating, the
score is None ("unbekannt"). The contributions of the axes sum exactly to the score (integer
tenths, largest remainder), so the breakdown is a real decomposition.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from typing import Final, TypedDict

from . import card_understanding, strength
from .card_understanding import UnderstandingRow
from .store import StudioStore

OVERALL_RULES_VERSION: Final = "overall-v1"
USAGE: Final = "usage"
# Setzung, keine Messung: chosen by the Owner's decision of 2026-11-18, not fitted to any data.
OVERALL_WEIGHTS_V1: Final[Mapping[str, float]] = {
    USAGE: 0.30,
    "H": 0.30,
    "F": 0.15,
    "E": 0.10,
    "T": 0.05,
    "R": 0.05,
    "D": 0.025,
    "K": 0.025,
}
AXES: Final[tuple[str, ...]] = tuple(OVERALL_WEIGHTS_V1)
MIN_COVERAGE: Final = 0.6
STABILITY_VARIANTS: Final = 80
STABILITY_SEED: Final = 20261118
STABILITY_FACTOR: Final = 0.3
UNSHARP_SHARE: Final = 0.10
UNCERTAIN_H_SD: Final = 20.0
RATED: Final = "bewertet"
UNKNOWN: Final = "unbekannt"
NAME: Final = "Kartenverständnis-Gesamtrating"
CAVEAT: Final = (
    "Setzung der Gewichte, Kartenverständnis durch Modell-Rater (große Stufe), "
    "Nutzung ist eine Achse"
)
LOCKED_RULES: Final[tuple[str, ...]] = (
    "keine Simulationswerte (Gewicht 0)",
    "keine gemessenen Ergebnisschichten (Tempo, Ausspielquote, Standfestigkeit, Sieg-Abstand, "
    "Großpod)",
    "keine Preise",
    "Markierungen ohne Einfluss",
    "Kohorten nie vermischen (Bracket und Quelle wie im Nutzungs-Index)",
    "unbekannt ist nie 0",
)
_BLOCKED_COMPONENTS: Final[tuple[str, ...]] = (
    strength.SIMULATION,
    strength.RUBRIC,
    strength.PLAYGROUP_OBSERVED,
)


class OverallAxis(TypedDict):
    axis: str
    value: float
    weight_effective: float
    contribution: float


class OverallConfidence(TypedDict):
    level: str
    uncertain: bool
    rater_confidence: str
    h_sd: float | None
    raters: int
    basis: str


class OverallStability(TypedDict):
    rank_min: int
    rank_max: int
    unscharf: bool
    variants: int


class OverallCard(TypedDict):
    status: str
    unknown_reason: str | None
    score: float | None
    rank: int | None
    n_rated: int
    coverage: float
    axes: list[OverallAxis]
    confidence: OverallConfidence | None
    reason: str | None
    version: str
    rater_tier: str | None
    stability: OverallStability | None


class Decomposition(TypedDict):
    score: float
    coverage: float
    axes: list[OverallAxis]


def coverage_of(values: Mapping[str, float | None], weights: Mapping[str, float]) -> float:
    """Share of the nominal weights that sit on axes with a value."""
    total = sum(weights.values())
    present = sum(weight for axis, weight in weights.items() if values.get(axis) is not None)
    return present / total if total > 0 else 0.0


def decompose(
    values: Mapping[str, float | None],
    weights: Mapping[str, float] = OVERALL_WEIGHTS_V1,
    *,
    min_coverage: float = MIN_COVERAGE,
) -> Decomposition | None:
    """Score and breakdown of one card, or None when the coverage is below ``min_coverage``.

    The weights of the present axes are renormalised to sum to 1. The score has one decimal;
    the contributions are shared out in tenths by largest remainder so that they add up to the
    score exactly."""
    coverage = coverage_of(values, weights)
    present = [axis for axis in weights if values.get(axis) is not None and weights[axis] > 0]
    if not present or coverage < min_coverage or coverage <= 0:
        return None
    present_weight = sum(weights[axis] for axis in present)
    raw: list[float] = []
    effective: list[float] = []
    for axis in present:
        value = float(values[axis])  # type: ignore[arg-type]
        effective.append(weights[axis] / present_weight)
        raw.append(value * weights[axis] / present_weight)
    score_tenths = round(sum(raw) * 10)
    floors = [int(part * 10 // 1) for part in raw]
    missing = score_tenths - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] * 10 - floors[i]), i))
    for index in order[: max(missing, 0)]:
        floors[index] += 1
    axes: list[OverallAxis] = [
        {
            "axis": axis,
            "value": float(values[axis]),  # type: ignore[arg-type]
            "weight_effective": round(effective[position], 4),
            "contribution": floors[position] / 10,
        }
        for position, axis in enumerate(present)
    ]
    return {"score": score_tenths / 10, "coverage": round(coverage, 4), "axes": axes}


def competition_ranks(scores: Mapping[str, float]) -> dict[str, int]:
    """Rank k of n by score (higher is better); ties share the best rank (1, 2, 2, 4)."""
    ordered = sorted(scores.items(), key=lambda item: (-round(item[1] * 10), item[0]))
    ranks: dict[str, int] = {}
    previous: int | None = None
    rank = 0
    for position, (key, score) in enumerate(ordered, start=1):
        tenths = round(score * 10)
        if previous is None or tenths != previous:
            rank = position
            previous = tenths
        ranks[key] = rank
    return ranks


def weight_variants(
    weights: Mapping[str, float] = OVERALL_WEIGHTS_V1,
    *,
    variants: int = STABILITY_VARIANTS,
    seed: int = STABILITY_SEED,
    factor: float = STABILITY_FACTOR,
) -> list[dict[str, float]]:
    """The weight variants of the stability check, in a fixed order: every weight scaled by a
    factor drawn uniformly from ``1 - factor`` to ``1 + factor`` with the fixed seed. They are
    renormalised per card over the axes the card has, as the base weights are."""
    rng = random.Random(seed)
    return [
        {axis: weights[axis] * rng.uniform(1.0 - factor, 1.0 + factor) for axis in weights}
        for _ in range(variants)
    ]


def rank_spans(
    values: Mapping[str, Mapping[str, float | None]],
    base_ranks: Mapping[str, int],
    weights: Mapping[str, float] = OVERALL_WEIGHTS_V1,
) -> dict[str, tuple[int, int]]:
    """Per rated card the lowest and highest rank over the weight variants (the base rank is part
    of the span, so the displayed rank always lies inside it). Ranks are taken inside the rated
    cards only, the same set as the base ranking."""
    spans = {card: (rank, rank) for card, rank in base_ranks.items()}
    for variant in weight_variants(weights):
        scores: dict[str, float] = {}
        for card in base_ranks:
            card_values = values[card]
            weight = 0.0
            weighted = 0.0
            for axis, axis_weight in variant.items():
                value = card_values.get(axis)
                if value is not None:
                    weight += axis_weight
                    weighted += axis_weight * value
            scores[card] = round(weighted / weight, 1) if weight > 0 else 0.0
        for card, rank in competition_ranks(scores).items():
            low, high = spans[card]
            spans[card] = (min(low, rank), max(high, rank))
    return spans


def confidence_of(row: UnderstandingRow) -> OverallConfidence:
    """The rater's confidence, lowered to "low" (uncertain) when the raters disagree on H by
    ``UNCERTAIN_H_SD`` points or more; with a single rater the spread is unknown, not 0."""
    spread = row.get("score_sd")
    h_sd = None if spread is None else float(spread["H"])
    raters = int(row.get("raters", 1))
    rater_level = row["confidence"]
    wide = h_sd is not None and h_sd >= UNCERTAIN_H_SD
    uncertain = rater_level == "low" or wide
    if wide:
        basis = f"Bewerter uneinig: Streuung von H {h_sd:g} bei {raters} Bewertern"
    elif rater_level == "low":
        basis = "Bewerter-Vertrauen niedrig"
    elif h_sd is None:
        basis = f"Bewerter-Vertrauen {rater_level}; Streuung unbekannt (1 Bewerter)"
    else:
        basis = f"Bewerter-Vertrauen {rater_level}; Streuung von H {h_sd:g} bei {raters} Bewertern"
    return {
        "level": "low" if uncertain else rater_level,
        "uncertain": uncertain,
        "rater_confidence": rater_level,
        "h_sd": h_sd,
        "raters": raters,
        "basis": basis,
    }


def usage_blocked(answer: Mapping[str, object]) -> str | None:
    """Why the usage index of this answer may not be an axis (None: it may). An index that
    weights simulation, the rubric itself or a measured result layer would carry a locked or
    double-counted signal into the overall rating. Without the weights the answer cannot be
    vouched for: the axis is blocked (fail closed)."""
    weights = answer.get("effective_weights")
    summary = answer.get("layer_summary")
    weighted = summary.get("weighted") if isinstance(summary, dict) else None
    if not isinstance(weights, dict) or not isinstance(weighted, list):
        return "die Gewichte des Nutzungs-Index fehlen in der Antwort"
    for name in _BLOCKED_COMPONENTS:
        value = weights.get(name)
        if isinstance(value, (int, float)) and value > 0:
            return f"der Nutzungs-Index gewichtet {name}"
    if weighted:
        return "der Nutzungs-Index gewichtet gemessene Ergebnisschichten"
    return None


def _card_axes(usage: float | None, row: UnderstandingRow | None) -> dict[str, float | None]:
    values: dict[str, float | None] = {USAGE: usage}
    for axis in card_understanding.CRITERIA:
        values[axis] = row["scores"][axis] if row is not None else None
    return values


def _unrated(
    n_rated: int, coverage: float, reason: str, version: str = OVERALL_RULES_VERSION
) -> OverallCard:
    return {
        "status": UNKNOWN,
        "unknown_reason": reason,
        "score": None,
        "rank": None,
        "n_rated": n_rated,
        "coverage": round(coverage, 4),
        "axes": [],
        "confidence": None,
        "reason": None,
        "version": version,
        "rater_tier": None,
        "stability": None,
    }


def rate_pool(
    usage: Mapping[str, float | None],
    oracle_ids: Mapping[str, str | None],
    dataset: Mapping[str, UnderstandingRow],
    *,
    weights: Mapping[str, float] = OVERALL_WEIGHTS_V1,
) -> dict[str, OverallCard]:
    """The overall rating of every card id in ``usage`` (usage index or None per card). A card
    whose oracle id the data set does not list, or whose coverage is too low, is "unbekannt"."""
    values: dict[str, dict[str, float | None]] = {}
    parts: dict[str, Decomposition] = {}
    rows: dict[str, UnderstandingRow] = {}
    for card_id, usage_value in usage.items():
        oracle_id = oracle_ids.get(card_id)
        row = dataset.get(oracle_id) if oracle_id else None
        if row is None:
            continue
        axes = _card_axes(usage_value, row)
        found = decompose(axes, weights)
        if found is None:
            continue
        values[card_id], parts[card_id], rows[card_id] = axes, found, row
    ranks = competition_ranks({card_id: part["score"] for card_id, part in parts.items()})
    spans = rank_spans(values, ranks, weights)
    n_rated = len(parts)
    threshold = UNSHARP_SHARE * n_rated
    result: dict[str, OverallCard] = {}
    for card_id, usage_value in usage.items():
        part = parts.get(card_id)
        if part is None:
            oracle_id = oracle_ids.get(card_id)
            reason = (
                "keine Kartenverständnis-Bewertung"
                if not oracle_id or oracle_id not in dataset
                else "zu wenig Achsen (Abdeckung unter dem Mindestwert)"
            )
            partial = coverage_of({USAGE: usage_value}, weights)
            result[card_id] = _unrated(n_rated, partial, reason)
            continue
        low, high = spans[card_id]
        row = rows[card_id]
        result[card_id] = {
            "status": RATED,
            "unknown_reason": None,
            "score": part["score"],
            "rank": ranks[card_id],
            "n_rated": n_rated,
            "coverage": part["coverage"],
            "axes": part["axes"],
            "confidence": confidence_of(row),
            "reason": row["reason"],
            "version": row["version"],
            "rater_tier": row["rater_tier"],
            "stability": {
                "rank_min": low,
                "rank_max": high,
                "unscharf": (high - low) >= threshold,
                "variants": STABILITY_VARIANTS,
            },
        }
    return result


def _oracle_ids(store: StudioStore, card_ids: Sequence[str]) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for start in range(0, len(card_ids), 500):
        chunk = list(card_ids[start : start + 500])
        marks = ",".join("?" for _ in chunk)
        for card_id, oracle_id in store.connection.execute(
            f"SELECT card_id, oracle_id FROM card WHERE card_id IN ({marks})",
            chunk,
        ):
            found[str(card_id)] = str(oracle_id) if oracle_id else None
    return found


def _meta(
    *,
    available: bool,
    n_rated: int,
    n_total: int,
    note: str,
    unavailable: str | None = None,
    dataset: Mapping[str, UnderstandingRow] | None = None,
    matched: int = 0,
    usage_reason: str | None = None,
    n_usage: int = 0,
    cohort: Mapping[str, object] | None = None,
    unscharf_count: int = 0,
) -> dict[str, object]:
    rows = dataset or {}
    tiers: dict[str, int] = {}
    for row in rows.values():
        tiers[row["rater_tier"]] = tiers.get(row["rater_tier"], 0) + 1
    return {
        "available": available,
        "unavailable_reason": unavailable,
        "name": NAME,
        "version": OVERALL_RULES_VERSION,
        "n_rated": n_rated,
        "n_total": n_total,
        "weights": dict(OVERALL_WEIGHTS_V1),
        "weights_note": "Setzung, keine Messung",
        "min_coverage": MIN_COVERAGE,
        "coverage_note": note,
        "caveat": CAVEAT,
        "locked_rules": list(LOCKED_RULES),
        "dataset": {
            "version": card_understanding.DATASET_VERSION,
            "rubric": card_understanding.DATASET_RUBRIC,
            "commander": card_understanding.DATASET_COMMANDER,
            "rows": len(rows),
            "matched": matched,
            "unmatched": len(rows) - matched,
            "rater_tiers": tiers,
        },
        "usage_axis": {
            "included": usage_reason is None,
            "excluded_reason": usage_reason,
            "n_with_usage": n_usage,
            "n_total": n_total,
        },
        "cohort": dict(cohort or {}),
        "stability": {
            "variants": STABILITY_VARIANTS,
            "seed": STABILITY_SEED,
            "factor": STABILITY_FACTOR,
            "unscharf_share": UNSHARP_SHARE,
            "unscharf_count": unscharf_count,
            "evaluated_cards": n_rated,
            "note": (
                f"{STABILITY_VARIANTS} Gewichtsvarianten (jedes Gewicht zufällig mit Faktor "
                f"{1 - STABILITY_FACTOR:g} bis {1 + STABILITY_FACTOR:g}, fester Seed); "
                f"unscharf: Rangspanne mindestens {UNSHARP_SHARE:.0%} der bewerteten Karten"
            ),
        },
    }


def with_overall(
    store: StudioStore,
    answer: Mapping[str, object],
    *,
    dataset: Mapping[str, UnderstandingRow] | None = None,
    commander: str | None = None,
) -> dict[str, object]:
    """``answer`` (an answer of the strength index, live or from a snapshot) plus the ``overall``
    field of every card and ``overall_meta``. Every other field is returned unchanged; the given
    answer (possibly a remembered one) is not modified.

    The data set belongs to ONE commander (``commander``, default
    ``card_understanding.DATASET_COMMANDER``): for another commander no card gets a rating."""
    commander = card_understanding.DATASET_COMMANDER if commander is None else commander
    raw_cards = answer.get("cards")
    cards = raw_cards if isinstance(raw_cards, list) else []
    n_total = len(cards)
    out: dict[str, object] = dict(answer)
    if str(answer.get("commander", "")).strip().casefold() != commander.casefold():
        out["overall_meta"] = _meta(
            available=False,
            n_rated=0,
            n_total=n_total,
            note=f"0 von {n_total} Karten bewertet: der Datensatz gilt nur für {commander}",
            unavailable=f"Kartenverständnis liegt nur für {commander} vor",
        )
        return out
    try:
        rows = card_understanding.load() if dataset is None else dataset
    except card_understanding.UnderstandingDataError as error:
        out["overall_meta"] = _meta(
            available=False,
            n_rated=0,
            n_total=n_total,
            note=f"0 von {n_total} Karten bewertet: der Datensatz ist nicht verfügbar",
            unavailable=(
                str(error)
                if isinstance(error, card_understanding.DatasetNotFoundError)
                else f"Datensatz Kartenverständnis nicht lesbar: {error}"
            ),
        )
        return out
    usage_reason = usage_blocked(answer)
    ids = [str(card["card_id"]) for card in cards if isinstance(card, dict)]
    usage: dict[str, float | None] = {}
    for card in cards:
        if not isinstance(card, dict):
            continue
        index = card.get("index")
        ok = (
            usage_reason is None
            and card.get("tier") in strength.TIERS
            and isinstance(index, (int, float))
            and not isinstance(index, bool)
            and math.isfinite(index)
        )
        usage[str(card["card_id"])] = float(index) if ok else None  # type: ignore[arg-type]
    oracle = _oracle_ids(store, ids)
    rated = rate_pool(usage, oracle, rows)
    n_rated = sum(1 for item in rated.values() if item["status"] == RATED)
    matched = len({oid for oid in oracle.values() if oid in rows})
    new_cards: list[object] = []
    for card in cards:
        if isinstance(card, dict):
            merged = dict(card)
            merged["overall"] = rated[str(card["card_id"])]
            new_cards.append(merged)
        else:
            new_cards.append(card)
    settings = answer.get("settings")
    settings_map = settings if isinstance(settings, dict) else {}
    out["cards"] = new_cards
    out["overall_meta"] = _meta(
        available=True,
        n_rated=n_rated,
        n_total=n_total,
        note=(
            f"{n_rated} von {n_total} Karten bewertet; {n_total - n_rated} ohne "
            f"Kartenverständnis-Bewertung (unbekannt, nicht 0); "
            f"Nutzungs-Achse bei {sum(1 for v in usage.values() if v is not None)} von {n_total} "
            "Karten, sonst werden die übrigen Gewichte renormalisiert"
        ),
        dataset=rows,
        matched=matched,
        usage_reason=usage_reason,
        n_usage=sum(1 for value in usage.values() if value is not None),
        cohort={
            "commander": answer.get("commander"),
            "bracket": settings_map.get("bracket"),
            "universe_source": settings_map.get("universe_source"),
        },
        unscharf_count=sum(
            1
            for item in rated.values()
            if item["stability"] is not None and item["stability"]["unscharf"]
        ),
    )
    return out
