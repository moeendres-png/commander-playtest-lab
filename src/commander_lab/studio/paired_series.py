"""Paired overnight comparison series controller and C-3 simulator-readiness audit.

Orchestrates background paired A-vs-B comparison series (same seeds, same seats,
same opponent pod, O'Brien-Fleming sequential looks) on top of ``paired_comparison``
and provides the C-3 simulator readiness audit across a deck and its free Tier-S/A
pool candidates (#1404 Option 6, C-3).

Hard invariants:
- XMage remains the sole rules authority; no rule decisions live here.
- Simulation results stay strictly ``SIMULATED_RESULT`` and never touch ``strength_view``
  weights or the tier list (``simulation`` weight stays 0).
- Fail-closed: missing XMage/pilot catalogs report ``UNKNOWN`` (never fabricated PASS).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, cast

from commander_lab.agents.card_knowledge import CardCatalogError, card_facts
from commander_lab.bridge_qualification import bridge_qualification
from commander_lab.engine.rules.full_game_comparison import (
    PLANNED_PAIR_SD,
    SlotAlignment,
    align_to_baseline_slots,
    difference_quantiles,
    pairs_needed,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import RulesDeckInput

from . import builder, decks, launch, paired_comparison, strength_view
from .card_outcomes import pilot_identity, wilson_unrounded
from .decks import RevisionCard, lab_snapshot, list_rows, resolve_repo_baseline_cards
from .games import games_folder
from .launch import (
    MAX_SEATS,
    MIN_SEATS,
    SeriesEngine,
    cards_unknown_to_pilots,
    cards_unsupported_by_engine,
    checked_series_settings,
    engine_state,
    pod_opponent_ids,
    resolve_opponent_paths,
    series_engine,
    validate_released_seat_count,
)
from .launch import POD_PRESETS as POD_PRESETS  # re-exported for callers and tests
from .launch import (
    bridge_jar_sha256 as command_bridge_jar_sha256,
)
from .play import header_pilot_fingerprint
from .series_record import (
    DETERMINISM_VIOLATION,
    ManifestMismatch,
    series_guard,
    series_key_problem,
    series_violation,
)
from .store import StudioStore, now_utc
from .strength import StrengthSettings

SCHEMA_PAIRED_JOB = "studio-paired-series-job-1"
SCHEMA_READINESS_AUDIT = "studio-sim-readiness-audit-1"

#: Per-worker throughput that #1513 multiplies by the workers: an UNMEASURED assumption, kept as
#: ``assumed_games_per_hour_unmeasured`` and never used for the duration shown. Measured is only
#: the batch series on the Owner PC (#1251): 541.2 games/hour for the WHOLE series with 6 workers
#: and 8 games per JVM, after the #1299 forced-pass option, i.e. about 90 per worker.
ESTIMATED_GAMES_PER_HOUR = 540.0
#: The one measured rate (#1251, whole batch series, 6 workers): the duration shown is the time
#: at this rate, a lower bound while no more than 6 workers run; paired series are unmeasured.
MEASURED_BATCH_GAMES_PER_HOUR = 541.2
MEASURED_BATCH_WORKERS = 6
#: The table size the measured rate belongs to (four seats). For any other table size the
#: duration is UNKNOWN: no throughput is measured for it (n = 0 games), and a rate of another
#: table size is not a floor for it (smaller tables play faster, larger ones are unmeasured).
MEASURED_TABLE_SEATS = 4
THROUGHPUT_SOURCE = (
    "gemessen sind nur 541 Partien/h für eine ganze Batch-Serie mit 6 Workern und 8 Partien je "
    "JVM (#1251), also etwa 90 je Worker; für gepaarte Serien ist der Durchsatz ungemessen"
)
#: Five and six seats (#1661, Owner 2026-11-22): the duration is the measured four-seat rate
#: divided by the measured wall-time ratio of one game at that table against four seats (part
#: B, F6): table A, seeds 1-10, one JVM per game, median wall 12.91 s (4) -> 20.18 s (5) ->
#: 28.73 s (6), n = 10/10 finished games per seat count, SIMULATED_RESULT on the Owner PC
#: (docs/analysis-reports/seats_5_6_part_b_report.md, section 5). A ratio of medians of one
#: table is no floor and no forecast: the figure is a rough orientation from table A, never
#: "mindestens". Two and three seats are not measured.
#: 20.18 / 12.91 = 1.563 -> 1.56; 28.73 / 12.91 = 2.2254 -> 2.23 (the report rounds it to 2.22).
WALL_RATIO_VS_FOUR_SEATS: dict[int, float] = {5: 1.56, 6: 2.23}
WALL_RATIO_GAMES = (10, 10)  # n/N finished games per seat count behind each ratio
WALL_RATIO_SOURCE = (
    "Verhältnis der Wandzeit-Mediane je Partie gegenüber 4 Sitzen aus #1661 Teil B (F6): nur "
    "Tisch A, Seeds 1 bis 10, eine JVM je Partie, Median 12,91 s (4) → 20,18 s (5) → 28,73 s "
    "(6), n = 10/10 Partien je Sitzzahl, Owner-PC (WSL2), SIMULATED_RESULT"
)
#: How much that ratio spreads (part B, section 5): the median of the per-seed ratios on table A
#: and table B's medians against table A at four seats (table B has no four-seat run).
WALL_RATIO_SEED_PAIR_MEDIAN: dict[int, float] = {5: 1.63, 6: 2.63}
WALL_RATIO_TABLE_B_VS_A4: dict[int, float] = {5: 1.43, 6: 1.68}
#: The paired series of part B in the pool (B6/F8, 3 workers, 16 games per JVM): a reference
#: with its own n/N, never the figure used (another path and worker count than the four-seat
#: rate; it would show five seats faster than four).
POOL_REFERENCE_PART_B: dict[int, dict[str, object]] = {
    5: {"games_per_hour": 607.3, "games": 50, "planned": 50, "workers": 3, "games_per_jvm": 16},
    6: {"games_per_hour": 379.2, "games": 72, "planned": 72, "workers": 3, "games_per_jvm": 16},
}
#: Assumed block correlation of the seat rotations of one seed, as in ``power_table`` (#1043).
PLANNING_BLOCK_CORRELATION = 0.25
PLANNING_REFERENCE_EFFECT_PP = 5.0
#: Tables whose plan uses the base win rate 1/N of N equally strong seats (#1661, #1672, #1757):
#: all seat counts except four (2, 3, 5, 6, 7, 8). Four seats keep the engine lane's 0.63 (built
#: on 25 % = 1/4) byte for byte. At two seats p = 1/2 (exact independent pair sd 0.7071, scaled
#: pair_sd 0.7275); at three seats p = 1/3 (exact 0.6667, scaled pair_sd 0.6859).
BASELINE_PLAN_SEATS = (2, 3, 5, 6, 7, 8)
#: Seven and eight seats (#1672): no throughput and no wall-time ratio is measured on the Owner PC,
#: so the duration of a series stays UNKNOWN. What exists is one game per JVM in the cloud container
#: of the feasibility run (research branch ``research/seats-7-8-1672``, report
#: docs/analysis-reports/seats_7_8_feasibility_20261122.md, table A7/A8, seeds 1-6, foreign load,
#: no AppCDS, -Xmx3g, SIMULATED_RESULT, never 4P/6P evidence): per game median wall time
#: (min-max), JVM peak RSS median and maximum, n/N finished games. Shown as a reference beside the
#: plan, never used as a rate. The gate runs of #1672 (report
#: docs/analysis-reports/seats_7_8_simulate_gates_20261122.md on docs/fable-sonnet-haiku-reports,
#: two tables in parallel, foreign load) add a second single-game measurement (median, max, n) and
#: the peak RSS of a JVM with 8 games (two runs, ``batched_rss_mib``); 16 games per JVM, the Studio
#: default, is UNKNOWN (n = 0).
SINGLE_GAME_REFERENCE_7_8: dict[int, dict[str, object]] = {
    7: {
        "wall_seconds_median": 87.0,
        "wall_seconds_range": (46.1, 102.3),
        "rss_mib_median": 955,
        "rss_mib_max": 1343,
        "decisions_median": 9760,
        "games": 6,
        "planned": 6,
        "second_wall_seconds_median": 114.4,
        "second_wall_seconds_max": 140.9,
        "second_games": 8,
        "second_planned": 8,
        "batched_rss_mib": (1231, 883),
    },
    8: {
        "wall_seconds_median": 98.8,
        "wall_seconds_range": (65.7, 121.9),
        "rss_mib_median": 945,
        "rss_mib_max": 1006,
        "decisions_median": 10314,
        "games": 6,
        "planned": 6,
        "second_wall_seconds_median": 143.8,
        "second_wall_seconds_max": 189.0,
        "second_games": 8,
        "second_planned": 8,
        "batched_rss_mib": (1255, 1255),
    },
}
SINGLE_GAME_REFERENCE_7_8_SOURCE = (
    "Machbarkeitsversuch 7/8 Sitze (#1672, docs/analysis-reports/seats_7_8_feasibility_20261122.md "
    "auf dem Forschungs-Branch): Cloud-Container mit Fremdlast, eine JVM je Partie, -Xmx3g, ohne "
    "AppCDS, Tisch A7/A8, Seeds 1 bis 6, SIMULATED_RESULT, kein Owner-PC-Wert"
)
#: The precision a single win share is planned for: +-20 % of the base win rate (relative).
WILSON_RELATIVE_PRECISION = 0.20
_SD_AT_QUARTER = math.sqrt(2 * 0.25 * 0.75)


def _de(value: float, digits: int) -> str:
    """A decimal in German notation (comma), for the duration texts."""
    return f"{value:.{digits}f}".replace(".", ",")


class ObservedTables(NamedTuple):
    """What the played games of a stored series say about its table (#1661)."""

    #: the table sizes of the readable pods, sorted (never dropped because another pod is broken)
    sizes: list[int]
    #: a pod that cannot be read, or counted pairs without a readable pod: the size is not proven
    unreadable: bool


def observed_table_sizes(raw: Mapping[str, object]) -> ObservedTables:
    """The table sizes the played games of a stored series show (#1661).

    Read from the result's ``pods``: each pod is the decks of the other seats of its pairs, as the
    seat rows of the game headers named them (``pair_exposures``), so its size is 1 + that count.
    Fail-closed: a pod that cannot be read (no list of non-empty deck ids, no positive pair count)
    sets ``unreadable`` and keeps the sizes already seen; a result whose readable pods do not
    cover every counted pair (``pairs_completed`` against the sum of the pods' ``pairs``, also
    with no pod at all) is ``unreadable`` too, never "nothing seen".
    """
    result = raw.get("result")
    res: Mapping[str, object] = result if isinstance(result, dict) else {}
    pods = res.get("pods")
    sizes: set[int] = set()
    unreadable = pods is not None and not isinstance(pods, list)
    pod_pairs = 0
    for pod in pods if isinstance(pods, list) else []:
        opponents = pod.get("opponents") if isinstance(pod, dict) else None
        count = pod.get("pairs") if isinstance(pod, dict) else None
        if (
            isinstance(opponents, list)
            and opponents
            and all(isinstance(deck, str) and deck.strip() for deck in opponents)
            and type(count) is int
            and count > 0
        ):
            sizes.add(1 + len(opponents))
            pod_pairs += count
        else:
            unreadable = True  # no deck ids, or no pair count: this pod proves no table
    pairs = res.get("pairs_completed")
    if type(pairs) is int and pairs > 0 and (not sizes or pod_pairs != pairs):
        unreadable = True  # the pods do not cover every counted pair
    return ObservedTables(sorted(sizes), unreadable)


def planning_pair_sd(table_size: int) -> float:
    """The planning sd of one pair at ``table_size`` seats.

    Four seats: the engine lane's conservative 0.63, unchanged. All other seat counts (two, three,
    five to eight): the same conservative factor (0.63 / 0.612) on the exact sd of independent
    games at the base win rate p = 1/N, ``sqrt(2 * p * (1 - p))``: 0.7275 at two, 0.6859 at
    three, 0.582 at five, 0.5422 at six, 0.5091 at seven, 0.4812 at eight seats.
    """
    seats = int(table_size)
    if seats not in BASELINE_PLAN_SEATS:
        return PLANNED_PAIR_SD
    p = 1.0 / seats
    return round(PLANNED_PAIR_SD * math.sqrt(2 * p * (1 - p)) / _SD_AT_QUARTER, 4)


def wilson_games_needed(win_rate: float, relative: float = WILSON_RELATIVE_PRECISION) -> int:
    """Fewest games whose 95 % Wilson interval at the share ``win_rate`` is at most
    ``relative * win_rate`` wide on each side (half the interval width), e.g. +-4 pp at 20 %.

    Uses the Wilson bounds of the card evaluation (``card_outcomes.wilson_unrounded``), unrounded.
    """
    p = float(win_rate)
    if not 0.0 < p < 1.0 or relative <= 0.0:
        raise ValueError("win_rate muss zwischen 0 und 1 liegen, relative größer 0")
    target = relative * p
    games = 1
    while True:
        low, high = wilson_unrounded(p * games, games)
        if (high - low) / 2.0 <= target:
            return games
        games += 1


def planning_baseline(table_size: int) -> dict[str, object]:
    """The base win rate 1/N of a table and the games a single win share needs for +-20 %.

    ``applies_to_plan`` says whether the pair sd of the plan is built on it (two, three, and
    five to eight seats) or the engine lane's 0.63 stays (four seats)."""
    seats = int(table_size)
    if not MIN_SEATS <= seats <= MAX_SEATS:
        raise ValueError(f"Tischgröße muss zwischen {MIN_SEATS} und {MAX_SEATS} liegen")
    p = 1.0 / seats
    games = wilson_games_needed(p)
    return {
        "table_size": seats,
        "win_rate": round(p, 4),
        "win_rate_pct": round(100.0 * p, 1),
        "relative_precision": WILSON_RELATIVE_PRECISION,
        "half_width_pp": round(100.0 * p * WILSON_RELATIVE_PRECISION, 2),
        "games_needed_wilson": games,
        "applies_to_plan": seats in BASELINE_PLAN_SEATS,
        "basis": (
            f"Zufallsbasis 1/{seats} bei {seats} gleich starken Plätzen; ein einzelner "
            f"Siegrate-Anteil braucht {games} Partien, bis das 95-%-Wilson-Intervall höchstens "
            f"±{round(100.0 * p * WILSON_RELATIVE_PRECISION, 2):g} pp (±20 % relativ) breit "
            "ist. Ein Plan, keine Messung."
        ),
    }


SERIES_PURPOSES = ("unspecified", "exploration", "confirmation", "control")
_SAFE_SERIES_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")


class SeriesCancelledError(RuntimeError):
    """Raised internally when an active paired series is cancelled by the user."""


def validate_series_id(series_id: str) -> str:
    cleaned = series_id.strip()
    if not _SAFE_SERIES_ID.fullmatch(cleaned):
        raise ValueError("invalid series_id")
    return cleaned


def _planned_detectable(pairs: int, seats_per_seed: int, sd: float = PLANNED_PAIR_SD) -> float:
    """``(t95 + t80) * sd / sqrt(pairs)`` with t at (seeds - 1) df, as the evaluation uses."""
    seeds = max(1, math.ceil(pairs / seats_per_seed))
    t95, t80 = difference_quantiles(max(1, seeds - 1))
    return (t95 + t80) * sd / math.sqrt(pairs)


def planned_detectable_difference_pp(
    budget_pairs: int, seats_per_seed: int, table_size: int = MEASURED_TABLE_SEATS
) -> dict[str, object]:
    """What ``budget_pairs`` can detect before a game is played, with the assumptions named.

    The arithmetic of the evaluation (``cluster_difference_stats``: Student-t quantiles at
    seeds - 1 degrees of freedom, one cluster per seed) on the assumed pair sd 0.63, the
    engine lane's conservative planning value (exact for independent games at a 25 % win rate:
    ``sqrt(2 * 0.25 * 0.75) = 0.612``). The pairing correlation is unmeasured, so the sd is not
    lowered for it; the seat rotations of one seed count with the design effect
    ``1 + (m - 1) * 0.25`` at the upper end. A plan, not a measurement.

    ``table_size`` (seats at the table, never the seats per seed: without rotation that is 1)
    names the base win rate 1/N (``baseline``); at two, three, and five to eight seats the pair
    sd is built on it (``planning_pair_sd``), at four seats the 0.63 stays.
    """
    pairs = max(2, int(budget_pairs))
    seats = max(1, int(seats_per_seed))
    baseline = planning_baseline(table_size)
    sd = planning_pair_sd(table_size)
    on_baseline = bool(baseline["applies_to_plan"])
    p = 1.0 / int(table_size) if on_baseline else 0.25
    design_effect = 1.0 + (seats - 1) * PLANNING_BLOCK_CORRELATION
    seeds = max(1, math.ceil(pairs / seats))
    # one seed: no spread between seeds, the evaluation gives no interval either (unknown)
    low: float | None = _planned_detectable(pairs, seats, sd) if seeds >= 2 else None
    effect = PLANNING_REFERENCE_EFFECT_PP / 100.0
    needed = pairs_needed(effect, sd)  # normal quantiles: a lower bound
    while _planned_detectable(needed, seats, sd) > effect:
        needed += 1
    return {
        "budget_pairs": pairs,
        "detectable_pp_low": None if low is None else round(low * 100.0, 1),
        "detectable_pp_high": (
            None if low is None else round(low * math.sqrt(design_effect) * 100.0, 1)
        ),
        "reference_effect_pp": PLANNING_REFERENCE_EFFECT_PP,
        "pairs_needed_low": needed,
        "pairs_needed_high": math.ceil(needed * design_effect),
        "assumptions": {
            "confidence": 0.95,
            "power": 0.80,
            "quantiles": "Student-t at seeds - 1 degrees of freedom (as cluster_difference_stats)",
            "degrees_of_freedom": max(1, seeds - 1),
            "pair_sd": sd,
            "pair_sd_independent_exact": round(math.sqrt(2 * p * (1 - p)), 4),
            "pair_sd_win_rate_pct": round(100.0 * p, 1),
            "pair_sd_basis": (
                (
                    f"conservative planning value on the base win rate 1/{int(table_size)}: "
                    f"independent games at {round(100.0 * p, 1):g} % win rate give "
                    f"{round(math.sqrt(2 * p * (1 - p)), 3):g}, times 0.63 / 0.612 as at four "
                    "seats; pairing correlation unmeasured"
                )
                if on_baseline
                else (
                    "conservative planning value; independent games at 25 % win rate give "
                    "0.612; pairing correlation unmeasured"
                )
            ),
            "seats_per_seed": seats,
            "design_effect": round(design_effect, 4),
            "block_correlation_assumed": PLANNING_BLOCK_CORRELATION,
            "sequential_looks": "not included (O'Brien-Fleming looks cost a little power)",
        },
        "baseline": baseline,
    }


def rotation_plan(
    table_size: int, budget_pairs: int, *, rotate_seats: bool = True, first_seed: int = 0
) -> dict[str, object]:
    """The seat rotation of a paired series before a game is played (#1702).

    One unit is one pair at one tested seat of one seed, seed by seed and seat by seat, cut at
    the budget, exactly as ``run_comparison_series`` plays them. The engine starts the game at
    seat ``seed % table_size`` (consecutive seeds), so a **block** of ``table_size`` consecutive
    seeds at ``table_size`` tested seats (``table_size ** 2`` pairs) plays every combination of
    starting seat and tested seat exactly once: 25 pairs at five seats, 36 at six, which is 25
    or 36 games per arm. A budget that is not a whole number of blocks leaves the rotation
    incomplete; this says so (``rotation_complete`` false, the cells that are missing) and
    never rounds the budget on its own.
    """
    seats = int(table_size)
    if not MIN_SEATS <= seats <= MAX_SEATS:
        raise ValueError(f"Tischgröße muss zwischen {MIN_SEATS} und {MAX_SEATS} liegen")
    pairs = int(budget_pairs)
    if pairs < 1:
        raise ValueError("budget_pairs muss mindestens 1 sein")
    tested = list(range(seats)) if rotate_seats else [0]
    seeds_planned = -(-pairs // len(tested))
    units = [(first_seed + i, seat) for i in range(seeds_planned) for seat in tested][:pairs]
    cells: dict[tuple[int, int], int] = {
        (start, seat): 0 for start in range(seats) for seat in tested
    }
    for seed, seat in units:
        cells[(seed % seats, seat)] += 1
    block_pairs = seats * len(tested)
    full_blocks, remainder = divmod(pairs, block_pairs)
    counts = sorted(cells.values())
    return {
        "table_size": seats,
        "rotate_seats": bool(rotate_seats),
        "tested_seats": tested,
        "budget_pairs": pairs,
        "seeds_planned": seeds_planned,
        "seed_rule": "consecutive",
        "starting_seat_rule": "seed % table_size",
        "pairs_per_block": block_pairs,
        "games_per_arm_per_block": block_pairs,
        "full_blocks": full_blocks,
        "remainder_pairs": remainder,
        "rotation_complete": remainder == 0,
        "cells_total": len(cells),
        "cells_missing": sum(1 for count in cells.values() if count == 0),
        "cells_min_pairs": counts[0],
        "cells_max_pairs": counts[-1],
        "max_games": 2 * pairs,
        "games_per_arm": pairs,
    }


def table_plan(
    table_size: int, budget_pairs: int, *, rotate_seats: bool = True
) -> dict[str, object]:
    """The plan of a series at ``table_size`` seats, also behind the seat lock (#1702).

    The usual plan (detectable difference at the seats per seed, base win rate 1/N) plus
    ``table``: the rotation (``rotation_plan``), the effort (games, duration: measured at four
    seats, a rough orientation from table A at five and six, UNKNOWN at two and three) and
    whether the Studio may start this table at all. Planning a locked table starts nothing;
    ``released`` false and ``locked_text`` say why.
    """
    rotation = rotation_plan(table_size, budget_pairs, rotate_seats=rotate_seats)
    seats_per_seed = len(cast(list[int], rotation["tested_seats"]))
    plan = planned_detectable_difference_pp(budget_pairs, seats_per_seed, table_size)
    effort = estimate_series_duration(
        budget_pairs, seats_per_seed=seats_per_seed, table_size=table_size
    )
    effort.pop("planning", None)
    released = table_size <= launch.MAX_RELEASED_SEATS  # read at call time: one lock line
    locked_text = (
        None
        if released
        else (
            f"Tische mit {table_size} Sitzen sind nicht freigegeben: Das Studio startet "
            f"{MIN_SEATS} bis {launch.MAX_RELEASED_SEATS} Sitze. Die Planung zeigt, was eine Serie "
            "wäre; gestartet wird sie erst nach Qualifikation und Owner-Freigabe (E15 Q5)."
        )
    )
    return {
        **plan,
        "table": {
            **rotation,
            "released": released,
            "max_released_seats": launch.MAX_RELEASED_SEATS,
            "locked_text": locked_text,
            "effort": effort,
        },
    }


def single_game_reference_text(size: int) -> str:
    """The warning of a table of seven or eight seats (#1672): duration and memory of one game in
    the container of the feasibility run, with n/N and origin; no Owner-PC value, no rate."""
    ref = SINGLE_GAME_REFERENCE_7_8[int(size)]
    low, high = cast(tuple[float, float], ref["wall_seconds_range"])
    second_median = float(cast(float, ref["second_wall_seconds_median"]))
    second_max = float(cast(float, ref["second_wall_seconds_max"]))
    batch_a, batch_b = cast(tuple[int, int], ref["batched_rss_mib"])
    return (
        f"Hinweis {size} Sitze: eine Partie dauerte im Median {_de(float(cast(float, ref['wall_seconds_median'])), 1)} s "
        f"({_de(low, 1)} bis {_de(high, 1)} s) bei etwa {ref['decisions_median']} Entscheidungen, "
        f"Spitzen-Speicher der Engine (RSS) im Median {ref['rss_mib_median']} MiB, höchstens "
        f"{ref['rss_mib_max']} MiB (n = {ref['games']}/{ref['planned']} Partien; "
        f"{SINGLE_GAME_REFERENCE_7_8_SOURCE}). Zweite Messung (Gates #1672, zwei Tische parallel, "
        f"Fremdlast): Median {_de(second_median, 1)} s, bis {_de(second_max, 1)} s "
        f"(n = {ref['second_games']}/{ref['second_planned']} Partien); Spitzen-Speicher einer JVM mit "
        f"8 Partien {batch_a} und {batch_b} MiB (2 Läufe). Bei 16 Partien je JVM (Studio-Standard) "
        "ist der Speicher unbekannt (n = 0): wenige Worker wählen und den freien Arbeitsspeicher "
        "prüfen (je Worker eine JVM mit bis zu 3 GB Heap)."
    )


def estimate_series_duration(
    budget_pairs: int,
    *,
    pairs_planned_max: int | None = None,
    workers: int | None = None,
    games_per_jvm: int | None = None,
    seats_per_seed: int = 4,
    table_size: int = MEASURED_TABLE_SEATS,
) -> dict[str, object]:
    """Pre-run duration floor and plan for a paired A-vs-B comparison series.

    The measured rate belongs to a table of ``MEASURED_TABLE_SEATS`` seats: there the duration
    is the time at that rate (``MEASURED_BATCH_GAMES_PER_HOUR``, a whole 6-worker batch series),
    a lower bound, not a forecast, while no more than 6 workers run. At five and six seats it is
    a rough orientation from table A (``duration_kind`` ``rough_orientation``, neither floor nor
    forecast): the four-seat batch rate divided by the ratio of the wall-time medians of table A
    (``WALL_RATIO_VS_FOUR_SEATS``, with its n/N and its spread), never called a floor (``minimum_*`` stay None, ``estimated_*`` carry it); the part-B pool rate is
    shown beside it as a reference with its own n/N. At two and three seats nothing is measured:
    UNKNOWN (``duration_known`` false, no seconds, no minutes). ``estimated_seconds`` /
    ``estimated_minutes`` keep their names for older readers. The #1513 per-worker figure stays
    visible as an unmeasured assumption.
    """
    size = int(table_size)
    if not MIN_SEATS <= size <= MAX_SEATS:
        # never a silent stand-in table: the plan block would name another size
        raise ValueError(f"Tischgröße muss zwischen {MIN_SEATS} und {MAX_SEATS} liegen")
    used_workers = max(1, int(workers)) if workers is not None else 1
    assumed_rate = ESTIMATED_GAMES_PER_HOUR * used_workers
    pairs = max(0, int(pairs_planned_max if pairs_planned_max is not None else budget_pairs))
    max_games = pairs * 2
    ratio = WALL_RATIO_VS_FOUR_SEATS.get(size)
    floor = size == MEASURED_TABLE_SEATS
    known = floor or ratio is not None
    rate = MEASURED_BATCH_GAMES_PER_HOUR / (ratio if ratio is not None else 1.0)
    seconds = round(max_games * (3600.0 / rate))
    minutes = round(seconds / 60.0, 1)
    floor_holds = used_workers <= MEASURED_BATCH_WORKERS
    pool_ref = POOL_REFERENCE_PART_B.get(size)
    if floor:
        basis = (
            f"mindestens ~{minutes} min bei der gemessenen Rate von "
            f"{MEASURED_BATCH_GAMES_PER_HOUR:.0f} Partien/h; {THROUGHPUT_SOURCE}, die Dauer "
            "ist vermutlich deutlich länger"
            + ("" if floor_holds else " (mit mehr als 6 Workern keine sichere Untergrenze)")
            + ". 2 Partien je Paar; früher Stopp je nach Look möglich."
        )
    elif ratio is not None and pool_ref is not None:
        pool_rate = float(cast(float, pool_ref["games_per_hour"]))
        basis = (
            f"grobe Orientierung ~{_de(minutes, 1)} min aus Tisch A (weder Untergrenze noch "
            f"Prognose): die Batch-Rate des Vierertischs {MEASURED_BATCH_GAMES_PER_HOUR:.0f} "
            "Partien/h (ganze Batch-Serie, 6 Worker, 8 Partien je JVM, #1251) geteilt durch "
            f"{_de(ratio, 2)} = {rate:.0f} Partien/h; {WALL_RATIO_SOURCE}. Das Verhältnis streut: "
            f"Median der Seed-Paar-Verhältnisse {_de(WALL_RATIO_SEED_PAIR_MEDIAN[size], 2)}, "
            f"Tisch B gegen Tisch A mit 4 Sitzen etwa {_de(WALL_RATIO_TABLE_B_VS_A4[size], 2)}. "
            f"Gemessen ist bei {size} Sitzen die gepaarte Serie im Pool mit "
            f"{pool_ref['workers']} Workern mit {pool_rate:.0f} Partien/h "
            f"(n = {pool_ref['games']}/{pool_ref['planned']} Partien, #1661 Teil B, B6), "
            f"{'schneller' if pool_rate > rate else 'langsamer'} als dieser Wert: die Dauer "
            "kann deutlich kürzer oder länger sein. Bis zu "
            f"{max_games} Partien ({pairs} je Arm), 2 Partien je Paar; früher Stopp je nach "
            "Look möglich."
        )
    else:
        basis = (
            f"unbekannt (UNKNOWN): für einen Tisch mit {size} Sitzen ist kein "
            "Durchsatz gemessen (n = 0 Partien). Gemessen ist nur der Vierertisch "
            f"({MEASURED_BATCH_GAMES_PER_HOUR:.0f} Partien/h, ganze Batch-Serie, 6 Worker, "
            "8 Partien je JVM, #1251, Zahl der Partien im Repository nicht belegt) und das "
            "Wandzeit-Verhältnis für 5 und 6 Sitze (#1661 Teil B); ein Wert eines anderen "
            "Tisches ist hier weder Schätzung noch Untergrenze. "
            f"Der Aufwand ist die Zahl der Partien: bis zu {max_games} "
            f"({pairs} je Arm), 2 Partien je Paar."
        )
    reference = SINGLE_GAME_REFERENCE_7_8.get(size)
    if reference is not None:
        basis += " " + single_game_reference_text(size)
    payload: dict[str, object] = {
        "budget_pairs": int(budget_pairs),
        "table_size": size,
        "duration_known": known,
        "duration_kind": "floor" if floor else ("rough_orientation" if known else "unknown"),
        "measured_table_seats": MEASURED_TABLE_SEATS,
        "measured_games": None,  # the number of games behind the 541.2 is not in the repository
        "max_games": max_games,
        "measured_batch_games_per_hour": MEASURED_BATCH_GAMES_PER_HOUR,
        "games_per_hour_used": round(rate, 1) if known else None,
        "wall_ratio_vs_four_seats": ratio,
        "wall_ratio_games": list(WALL_RATIO_GAMES) if ratio is not None else None,
        "wall_ratio_seed_pair_median": WALL_RATIO_SEED_PAIR_MEDIAN.get(size),
        "wall_ratio_table_b_vs_a4": WALL_RATIO_TABLE_B_VS_A4.get(size),
        "pool_reference_part_b": dict(pool_ref) if pool_ref is not None else None,
        "single_game_reference": (
            {
                **{k: list(v) if isinstance(v, tuple) else v for k, v in reference.items()},
                "source": SINGLE_GAME_REFERENCE_7_8_SOURCE,
                "multi_game_jvm_memory_known": False,  # at 16 games per JVM (n = 0)
            }
            if reference is not None
            else None
        ),
        "minimum_seconds": seconds if floor else None,
        "minimum_minutes": minutes if floor else None,
        "minimum_is_lower_bound": floor_holds and floor,
        "estimated_seconds": seconds if known else None,
        "estimated_minutes": minutes if known else None,
        "assumed_games_per_hour_unmeasured": int(assumed_rate),
        "workers": used_workers,
        "throughput_measured_for_paired_series": False,
        "throughput_source": THROUGHPUT_SOURCE,
        "basis": basis,
        "planning": planned_detectable_difference_pp(max(2, pairs), seats_per_seed, size),
    }
    if games_per_jvm is not None:
        payload["games_per_jvm"] = int(games_per_jvm)
    return payload


#: One resolver for every surface (batch, series, experiment): unknown is an error.
_resolve_opponent_paths = resolve_opponent_paths


def is_revision_ref(ref: str) -> bool:
    """A Studio deck state (``<deck>@<hash>`` or ``repo:<stem>``), not a repository precon."""
    return "@" in ref or ref.startswith("repo:")


def _table_opponent_paths(
    store: StudioStore | None,
    deck_dir: Path,
    pod: str,
    opponent_ids: Sequence[str] | None,
    taken_deck_ids: set[str],
    *,
    allow_unreleased_seats: bool = False,
) -> list[Path]:
    """The opponents' deck files: precons from the repository, Studio deck states (E15 Q6)
    as snapshot files in the series folder. With ``store`` the snapshots are written (start);
    without, they must already be there (resume). Unknown is an error, never a stand-in."""
    if opponent_ids is None or not any(is_revision_ref(str(o)) for o in opponent_ids):
        return resolve_opponent_paths(
            pod, opponent_ids, allow_unreleased_seats=allow_unreleased_seats
        )
    ids = [str(o).strip() for o in opponent_ids]
    # the whole table against the lock, before the split: the precons alone are fewer (#1708)
    validate_released_seat_count(len(ids), allow_unreleased_seats=allow_unreleased_seats)
    if len(set(ids)) != len(ids):
        raise ValueError("Gegner-Decks dürfen nicht doppelt vorkommen")
    precons = [o for o in ids if not is_revision_ref(o)]
    precon_paths = iter(
        resolve_opponent_paths(pod, precons, allow_unreleased_seats=allow_unreleased_seats)
        if precons
        else []
    )
    paths: list[Path] = []
    for index, oid in enumerate(ids):
        if not is_revision_ref(oid):
            paths.append(next(precon_paths))
            continue
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", oid)[:80]
        path = deck_dir / f"opponent-{index}-{safe}.json"
        if store is None:
            if not path.is_file():
                raise FileNotFoundError(f"Gegner-Snapshot {path.name} fehlt (nicht fortsetzbar)")
        else:
            snap = _snapshot_for_ref(store, oid)
            _preflight_snapshot_cards(f"Gegner-Deck {oid}", snap)
            if str(snap["deck_id"]) in taken_deck_ids:  # e.g. another state of the same deck
                snap["deck_id"] = f"{snap['deck_id']}--opp{index}"
            _write_json_atomic(path, snap)
        paths.append(path)
        taken_deck_ids.add(load_rules_deck_snapshot(path).deck_id)
    return paths


def _snapshot_for_ref(store: StudioStore, ref_id: str) -> dict[str, object]:
    """Convert a stored ``rev@...`` revision OR ``repo:<stem>`` baseline into a Rules snapshot."""
    if ref_id.startswith("repo:"):
        entries = resolve_repo_baseline_cards(store, ref_id)
        rows = list_rows(store, entries)
        commanders = [
            str(row["engine_name"] or row["oracle_name"])
            for row in rows
            if row["zone"] == "commander"
        ]
        stem = ref_id.split(":", 1)[1]
        digest = hashlib.sha256(
            json.dumps(
                [(str(r["engine_name"]), int(r["quantity"]), str(r["zone"])) for r in rows],
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return {
            "deck_id": f"repo-{stem}",
            "name": f"Referenz ({stem})",
            "studio_revision_id": ref_id,
            "studio_deck_hash": digest,
            "commander": {
                "commanders": commanders,
                "uses_partner": len(commanders) > 1,
                "commander_identity_override": None,
            },
            "cards": [
                {
                    "oracle_name": str(row["engine_name"] or row["oracle_name"]),
                    "quantity": int(str(row["quantity"])),
                    "zone": str(row["zone"]),
                }
                for row in rows
            ],
        }
    return lab_snapshot(store, ref_id)


def _preflight_pool_wall_limit(opponent_count: int) -> None:
    """Refuse, before anything is written, a table the series pool has no wall-clock limit for.

    Only where the pool would run (the switch ``COMMANDER_LAB_STUDIO_SERIES_POOL`` is on); the
    default path does not use the limit. Five and six seats have none until F6 measures it (#1661);
    ``table_spec.game_wall_limit_seconds`` names the seat count and guesses nothing."""
    from .game_pool import series_pool_enabled
    from .table_spec import game_wall_limit_seconds

    if series_pool_enabled():
        game_wall_limit_seconds(opponent_count + 1)


def _preflight_snapshot_cards(label: str, snapshot: dict[str, object]) -> None:
    if not builder.sim_readiness_available():
        return
    unsupported = cards_unsupported_by_engine(snapshot)
    if unsupported:
        raise ValueError(
            f"{label}: XMage unterstützt diese Karten noch nicht: {', '.join(unsupported[:8])}"
        )
    unknown = cards_unknown_to_pilots(snapshot)
    if unknown:
        raise ValueError(
            f"{label}: Das Piloten-Kartenwissen kennt diese Karten noch nicht: {', '.join(unknown[:8])}"
        )


def _snapshot_file(folder: Path, prefix: str, ref_id: str, snapshot: Mapping[str, object]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", ref_id)[:80] or prefix
    path = folder / f"{prefix}-{safe}.json"
    path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _align_variant_file(
    base_deck: RulesDeckInput,
    variant_deck: RulesDeckInput,
    variant_snap: Mapping[str, object],
    variant_path: Path,
) -> tuple[RulesDeckInput, SlotAlignment]:
    """Rewrite the variant's deck file with its cards in the baseline's library slots.

    Studio snapshots list cards by name, so a swap that crosses the alphabet moves every
    card in between to another slot and the two games of a pair share no library shuffle.
    The engine reads the deck file (``recorded_game_player`` passes paths), so the file
    itself gets the aligned main-zone order (``align_to_baseline_slots`` of the engine
    lane); every other entry stays as it was. The cards are exactly the variant's.
    """
    aligned, alignment = align_to_baseline_slots(base_deck, variant_deck)
    raw_cards = variant_snap.get("cards")
    entries = [e for e in raw_cards if isinstance(e, dict)] if isinstance(raw_cards, list) else []
    runs: list[dict[str, object]] = []
    for name in aligned.mainboard:
        last = runs[-1] if runs else None
        if last is not None and last["oracle_name"] == name:
            last["quantity"] = int(str(last["quantity"])) + 1
        else:
            runs.append({"oracle_name": name, "quantity": 1, "zone": "main"})
    others = [e for e in entries if e.get("zone") not in (None, "main")]
    _write_json_atomic(variant_path, {**variant_snap, "cards": [*others, *runs]})
    reloaded = load_rules_deck_snapshot(variant_path)
    if reloaded.mainboard != aligned.mainboard:
        raise ValueError("aligned variant deck file does not reload in the aligned order")
    return reloaded, alignment


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        with contextlib.suppress(OSError):
            if tmp.exists():
                tmp.unlink()


def pilot_change_message(
    preloaded: Mapping[tuple[str, int, int], paired_comparison.PlayedGame], current: str
) -> str | None:
    """Why an interrupted series cannot go on with the current pilot, or None (#1658).

    Games already played with another pilot (or before the fingerprint existed) would meet
    games of the current pilot in one comparison; that is never counted together."""
    others = [
        str(pilot_identity(exposure))
        for played in preloaded.values()
        if (exposure := played.get("exposure")) is not None and pilot_identity(exposure) != current
    ]
    if not others:
        return None
    return (
        f"nicht fortsetzbar: {len(others)} gespeicherte Partien dieser Serie stammen von einem "
        f"anderen Piloten ({', '.join(o[:20] for o in sorted(set(others)))}) als dem aktuellen "
        f"({current[:20]}); Partien verschiedener Piloten werden nie zusammengezählt. "
        "Bitte die Serie neu starten."
    )


class PairedSeriesJob:
    """In-memory + on-disk handle for one background paired A-vs-B comparison series."""

    def __init__(
        self,
        *,
        series_id: str,
        data_folder: Path,
        base_ref: str,
        variant_ref: str,
        base_deck: RulesDeckInput,
        variant_deck: RulesDeckInput,
        opponents: Sequence[RulesDeckInput],
        paths_by_deck_id: Mapping[str, Path],
        pod_name: str,
        seeds: list[int],
        tested_seats: list[int],
        budget_pairs: int,
        look_every_pairs: int,
        threshold_pp: float,
        significance_level: float = paired_comparison.DEFAULT_SIGNIFICANCE_LEVEL,
        play_override: paired_comparison.PairPlayer | None = None,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        engine: SeriesEngine | None = None,
        bridge_sha: str | None = None,
        qualification: Mapping[str, object] | None = None,
        slot_alignment: SlotAlignment | None = None,
        purpose: str = "unspecified",
        player_count: int | None = None,
        opponent_ids: Sequence[str] | None = None,
        raw_slot_alignment: dict[str, object] | None = None,
        created_at: str | None = None,
        preloaded_games: dict[tuple[str, int, int], paired_comparison.PlayedGame] | None = None,
        experiment: Mapping[str, object] | None = None,
    ) -> None:
        self.series_id = series_id
        #: The experiment this series plays (B2, #1658): id, plan SHA and table hash.
        self.experiment = dict(experiment) if experiment is not None else None
        self.data_folder = data_folder
        self.base_ref = base_ref
        self.variant_ref = variant_ref
        self.base_deck = base_deck
        self.variant_deck = variant_deck
        self.opponents = list(opponents)
        self.opponent_ids = list(opponent_ids) if opponent_ids is not None else None
        self.paths_by_deck_id = dict(paths_by_deck_id)
        self.pod_name = pod_name
        self.seeds = list(seeds)
        self.tested_seats = list(tested_seats)
        self.budget_pairs = budget_pairs
        self.look_every_pairs = look_every_pairs
        self.threshold_pp = threshold_pp
        self.significance_level = significance_level
        self.play_override = play_override
        self.workers, requested_batch = checked_series_settings(workers, games_per_jvm)
        self.engine = engine
        self.games_per_jvm = engine.games_per_jvm if engine is not None else requested_batch
        self.bridge_jar_sha256 = bridge_sha
        self.bridge_qualification = (
            dict(qualification) if qualification is not None else bridge_qualification()
        )
        self.estimate = estimate_series_duration(
            budget_pairs,
            workers=self.workers,
            games_per_jvm=self.games_per_jvm,
            seats_per_seed=len(tested_seats),
            table_size=player_count if player_count is not None else 1 + len(self.opponents),
        )
        table_size = player_count if player_count is not None else 1 + len(self.opponents)
        #: Consecutive seeds on purpose: the engine starts the game at seat ``seed % players``
        #: (``full_game``), so a run of consecutive seeds balances the turn order.
        self.seed_plan: dict[str, object] = {
            "purpose": purpose,
            "first_seed": self.seeds[0] if self.seeds else None,
            "last_seed": self.seeds[-1] if self.seeds else None,
            "seeds_planned": len(self.seeds),
            "seed_rule": "consecutive",
            "player_count": table_size,
            "starting_seat_rule": "seed % player_count",
        }
        #: How the variant's library was lined up with the base's; ``None`` only for a
        #: series written before the alignment existed (its pairs share no shuffle).
        self.slot_alignment: dict[str, object] | None = (
            dict(raw_slot_alignment)
            if raw_slot_alignment is not None
            else (slot_alignment.model_dump() if slot_alignment is not None else None)
        )
        self.preloaded_games: dict[tuple[str, int, int], paired_comparison.PlayedGame] = (
            dict(preloaded_games) if preloaded_games else {}
        )

        self.status = "pending"
        self.pairs_attempted = len(
            {
                (seed, seat)
                for seed in self.seeds
                for seat in self.tested_seats
                if ("base", seed, seat) in self.preloaded_games
                and ("variant", seed, seat) in self.preloaded_games
            }
        )
        self.created_at = created_at or now_utc()
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.error: str | None = None
        self.result: paired_comparison.PairedComparison | None = None
        self._cancel_requested = False
        #: Games the engine has played to their end: the ones taken over from disk plus those
        #: announced during this run. A progress count that comes before the pair is complete.
        self._games_played: set[tuple[str, int, int]] = {
            key
            for key, played in self.preloaded_games.items()
            if played.get("failure_class") is None
        }
        self._lock = threading.Lock()
        self._persist_lock = threading.Lock()
        self._progress_lock = threading.Lock()

    def series_file(self) -> Path:
        return games_folder(self.data_folder) / f"{self.series_id}.paired.json"

    def progress_file(self) -> Path:
        return games_folder(self.data_folder) / "paired_decks" / self.series_id / "progress.jsonl"

    def lock_file(self) -> Path:
        return games_folder(self.data_folder) / "paired_decks" / self.series_id / "running.lock"

    def _write_lock(self) -> None:
        path = self.lock_file()
        _write_json_atomic(
            path,
            {
                "series_id": self.series_id,
                "pid": os.getpid(),
                "started_at": now_utc(),
                "heartbeat": time.time(),
            },
        )

    def _release_lock(self) -> None:
        with contextlib.suppress(OSError):
            self.lock_file().unlink(missing_ok=True)

    def _ensure_progress_newline(self) -> None:
        path = self.progress_file()
        if not path.is_file():
            return
        with self._progress_lock:
            size = path.stat().st_size
            if size > 0:
                with path.open("rb") as handle:
                    handle.seek(-1, os.SEEK_END)
                    last = handle.read(1)
                if last != b"\n":
                    with path.open("ab") as handle:
                        handle.write(b"\n")

    def _append_game_result(
        self, arm: str, seed: int, seat: int, played: paired_comparison.PlayedGame
    ) -> None:
        if played.get("failure_class") is not None:
            with self._lock:  # a game that ended as a failure is not a played game
                self._games_played.discard((arm, seed, seat))
        path = self.progress_file()
        line = json.dumps(
            {"arm": arm, "seed": seed, "seat": seat, "played": played},
            ensure_ascii=False,
        )
        with self._progress_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        self._write_lock()

    def mark_game_played(self, arm: str, seed: int, seat: int) -> None:
        """Count one game of this series as played by the engine (progress only)."""
        with self._lock:
            self._games_played.add((arm, seed, seat))
        self.persist()

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def persist(self) -> None:
        with self._persist_lock:
            _write_json_atomic(self.series_file(), self.to_dict())

    def execution_metadata(self) -> dict[str, object]:
        engine = self.engine
        return {
            "workers": self.workers,
            "games_per_jvm": self.games_per_jvm,
            "serial_gc": engine.serial_gc if engine is not None else False,
            "appcds": engine.appcds if engine is not None else False,
        }

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            res = self.result
            bridge_shas = (
                list(res.get("bridge_jar_sha256s", []))
                if res
                else ([self.bridge_jar_sha256] if self.bridge_jar_sha256 else [])
            )
            qual_states = (
                list(res.get("bridge_qualification_states", []))
                if res
                else (
                    [str(self.bridge_qualification.get("status"))]
                    if self.bridge_qualification.get("status")
                    else []
                )
            )
            covered = bool(res.get("covered_by_sealed_epoch")) if res is not None else False
            return {
                "schema": SCHEMA_PAIRED_JOB,
                "series_id": self.series_id,
                "status": self.status,
                "base_ref": self.base_ref,
                "variant_ref": self.variant_ref,
                "base_deck_id": self.base_deck.deck_id,
                "variant_deck_id": self.variant_deck.deck_id,
                "pod": self.pod_name,
                "opponent_ids": list(self.opponent_ids) if self.opponent_ids is not None else None,
                "opponent_deck_ids": [deck.deck_id for deck in self.opponents],
                "budget_pairs": self.budget_pairs,
                "look_every_pairs": self.look_every_pairs,
                "tested_seats": list(self.tested_seats),
                "threshold_pp": self.threshold_pp,
                "significance_level": self.significance_level,
                "pairs_attempted": self.pairs_attempted,
                "games_played": len(self._games_played),
                "games_planned_max": 2 * self.budget_pairs,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "error": self.error,
                "estimate": self.estimate,
                "slot_alignment": self.slot_alignment,
                "seed_plan": self.seed_plan,
                "execution": self.execution_metadata(),
                "bridge_jar_sha256": bridge_shas[0]
                if len(bridge_shas) == 1
                else self.bridge_jar_sha256,
                "bridge_jar_sha256s": bridge_shas,
                "bridge_qualification_states": qual_states,
                "bridge_qualification": self.bridge_qualification,
                "covered_by_sealed_epoch": covered,
                "experiment": self.experiment,
                "result": res,
            }

    def run(self) -> None:
        self._write_lock()
        self._ensure_progress_newline()
        with self._lock:
            self.status = "running"
            self.started_at = now_utc()
            self.error = None
        self.persist()

        def _on_pair_done(count: int) -> None:
            with self._lock:
                self.pairs_attempted = max(self.pairs_attempted, count)
            self.persist()

        player = paired_comparison.parallel_window_player(
            self.data_folder,
            series_id=self.series_id,
            base_deck=self.base_deck,
            variant_deck=self.variant_deck,
            opponents=self.opponents,
            paths_by_deck_id=self.paths_by_deck_id,
            seeds=self.seeds,
            tested_seats=self.tested_seats,
            budget_pairs=self.budget_pairs,
            look_every_pairs=self.look_every_pairs,
            workers=self.workers,
            games_per_jvm=self.games_per_jvm,
            command=self.engine.command if self.engine is not None else None,
            play_single=self.play_override,
            is_cancelled=self.is_cancelled,
            on_pair_done=_on_pair_done,
            cancel_error_factory=lambda: SeriesCancelledError("Serie vom Benutzer abgebrochen"),
            preloaded=self.preloaded_games,
            on_game_result=self._append_game_result,
            on_game_played=self.mark_game_played,
        )

        final_status = "failed"
        final_result: paired_comparison.PairedComparison | None = None
        final_pairs_attempted: int | None = None
        final_error: str | None = None
        final_ended_at: str | None = None

        try:
            result = paired_comparison.run_comparison_series(
                base_deck_id=self.base_deck.deck_id,
                variant_deck_id=self.variant_deck.deck_id,
                seeds=self.seeds,
                tested_seats=self.tested_seats,
                budget_pairs=self.budget_pairs,
                look_every_pairs=self.look_every_pairs,
                threshold_pp=self.threshold_pp,
                significance_level=self.significance_level,
                play=player,
                execution={
                    "series_id": self.series_id,
                    "command": "studio web paired-series",
                    "base_ref": self.base_ref,
                    "variant_ref": self.variant_ref,
                    "pod": self.pod_name,
                    "rotate_seats": len(self.tested_seats) > 1,
                    "look_every_pairs": self.look_every_pairs,
                    "budget_pairs": self.budget_pairs,
                    "games_dir": str(games_folder(self.data_folder)),
                    "slot_alignment": self.slot_alignment,
                    "seed_plan": self.seed_plan,
                    **self.execution_metadata(),
                },
            )
            pool_summary = player.pool_summary()
            if pool_summary is not None:
                result["execution"] = {**result["execution"], "pool": pool_summary}
            final_result = result
            pairs_played = result.get("pairs_played")
            final_pairs_attempted = int(pairs_played) if pairs_played else None
            final_status = "completed"
            final_ended_at = now_utc()
        except SeriesCancelledError as exc:
            final_status = "cancelled"
            final_error = str(exc)
            final_ended_at = now_utc()
        except Exception as exc:
            final_status = "failed"
            final_error = str(exc)
            final_ended_at = now_utc()
        finally:
            try:
                player.close()  # the worker processes and their bridge JVMs end with the series
            finally:
                self._release_lock()
                with self._persist_lock:
                    with self._lock:
                        if final_result is not None:
                            self.result = final_result
                        if final_pairs_attempted is not None:
                            self.pairs_attempted = final_pairs_attempted
                        if final_error is not None:
                            self.error = final_error
                        self.ended_at = final_ended_at or now_utc()
                    payload = self.to_dict()
                    payload["status"] = final_status
                    try:
                        _write_json_atomic(self.series_file(), payload)
                    finally:
                        with self._lock:
                            self.status = final_status


class PairedSeriesManager:
    """Thread-safe registry for background paired overnight comparison jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, PairedSeriesJob] = {}
        self._seq = 0
        self._lock = threading.Lock()

    def start_series(
        self,
        store: StudioStore,
        data_folder: str | Path,
        *,
        base_revision_id: str,
        variant_revision_id: str,
        pod: str = "precon",
        opponent_ids: Sequence[str] | None = None,
        budget_pairs: int = 20,
        look_every_pairs: int = 4,
        base_seed: int = 1000,
        rotate_seats: bool = True,
        threshold_pp: float = paired_comparison.DEFAULT_THRESHOLD_PP,
        significance_level: float = paired_comparison.DEFAULT_SIGNIFICANCE_LEVEL,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        play_override: paired_comparison.PairPlayer | None = None,
        purpose: str = "unspecified",
        allow_unreleased_seats: bool = False,
        experiment: Mapping[str, object] | None = None,
        table_size: int | None = None,
    ) -> PairedSeriesJob:
        """Start a paired series. ``table_size`` (seats, 2 to 6) sizes a pod preset's table:
        the preset's first ``table_size - 1`` opponents sit down, and the series records them
        by id. Without it a preset seats its four-seat table as before. With explicit
        ``opponent_ids`` it must match their count. The seat lock applies in every case."""
        data_path = Path(data_folder).resolve()
        if purpose not in SERIES_PURPOSES:
            raise ValueError(f"purpose muss eines von {', '.join(SERIES_PURPOSES)} sein")
        if base_revision_id.strip() == variant_revision_id.strip():
            raise ValueError("Basis und Variante müssen zwei verschiedene Stände sein")
        if (
            not paired_comparison.MIN_BUDGET_PAIRS
            <= budget_pairs
            <= paired_comparison.MAX_BUDGET_PAIRS
        ):
            raise ValueError(
                f"budget_pairs muss zwischen {paired_comparison.MIN_BUDGET_PAIRS} und "
                f"{paired_comparison.MAX_BUDGET_PAIRS} liegen"
            )
        if look_every_pairs < 1:
            raise ValueError("look_every_pairs muss mindestens 1 sein")
        if table_size is not None:
            validate_released_seat_count(
                table_size - 1, allow_unreleased_seats=allow_unreleased_seats
            )
            if opponent_ids is None:
                opponent_ids = list(pod_opponent_ids(pod, table_size - 1))
            elif len(opponent_ids) + 1 != table_size:
                raise ValueError(
                    f"ein Tisch mit {table_size} Sitzen braucht {table_size - 1} Gegner, "
                    f"angegeben sind {len(opponent_ids)}"
                )
        if opponent_ids is not None:
            validate_released_seat_count(
                len(opponent_ids), allow_unreleased_seats=allow_unreleased_seats
            )
        if play_override is None and (opponent_ids is not None or pod in POD_PRESETS):
            # (an unknown pod is refused later with its own message, not as "1 seat")
            _preflight_pool_wall_limit(
                len(opponent_ids) if opponent_ids is not None else len(POD_PRESETS[pod])
            )
        used_workers, used_batch = checked_series_settings(workers, games_per_jvm)

        engine: SeriesEngine | None = None
        if play_override is None:
            engine = series_engine(data_path, used_batch)
            if engine is None:
                state = engine_state(data_path)
                raise RuntimeError(str(state.get("reason") or "Engine ist nicht bereitgestellt"))

        base_snap = _snapshot_for_ref(store, base_revision_id.strip())
        variant_snap = _snapshot_for_ref(store, variant_revision_id.strip())
        _preflight_snapshot_cards("Basis-Deck", base_snap)
        _preflight_snapshot_cards("Varianten-Deck", variant_snap)

        if opponent_ids is None or not any(is_revision_ref(str(o)) for o in opponent_ids):
            # precons only: checked before anything is written
            _resolve_opponent_paths(
                pod, opponent_ids, allow_unreleased_seats=allow_unreleased_seats
            )

        with self._lock:
            self._seq += 1
            seq = self._seq
        digest = hashlib.sha256(
            f"{base_revision_id}|{variant_revision_id}|{base_seed}|{seq}".encode()
        ).hexdigest()[:8]
        series_id = f"paired-{int(time.time())}-{seq}-{digest}"
        deck_dir = games_folder(data_path) / "paired_decks" / series_id
        base_path = _snapshot_file(deck_dir, "base", base_revision_id, base_snap)
        variant_path = _snapshot_file(deck_dir, "variant", variant_revision_id, variant_snap)

        base_deck = load_rules_deck_snapshot(base_path)
        variant_deck = load_rules_deck_snapshot(variant_path)
        if base_deck.deck_id == variant_deck.deck_id:
            # Paired exposures match on RulesDeckInput.deck_id; distinguish base vs variant cleanly
            base_snap["deck_id"] = f"{base_deck.deck_id}--base"
            variant_snap["deck_id"] = f"{variant_deck.deck_id}--variant"
            base_path = _snapshot_file(deck_dir, "base", base_revision_id, base_snap)
            variant_path = _snapshot_file(deck_dir, "variant", variant_revision_id, variant_snap)
            base_deck = load_rules_deck_snapshot(base_path)
            variant_deck = load_rules_deck_snapshot(variant_path)
        variant_deck, alignment = _align_variant_file(
            base_deck, variant_deck, variant_snap, variant_path
        )
        opp_paths = _table_opponent_paths(
            store,
            deck_dir,
            pod,
            opponent_ids,
            {base_deck.deck_id, variant_deck.deck_id},
            allow_unreleased_seats=allow_unreleased_seats,
        )
        opponents = [load_rules_deck_snapshot(p) for p in opp_paths]

        paths_by_deck_id: dict[str, Path] = {
            base_deck.deck_id: base_path,
            variant_deck.deck_id: variant_path,
        }
        for deck, path in zip(opponents, opp_paths, strict=True):
            paths_by_deck_id[deck.deck_id] = path

        table_size = 1 + len(opponents)
        rotation = rotation_plan(
            table_size, budget_pairs, rotate_seats=rotate_seats, first_seed=int(base_seed)
        )
        tested_seats = [int(seat) for seat in cast(list[int], rotation["tested_seats"])]
        seeds = [int(base_seed) + i for i in range(cast(int, rotation["seeds_planned"]))]

        jar_sha = (
            command_bridge_jar_sha256(data_path, engine.command) if engine is not None else None
        )
        job = PairedSeriesJob(
            series_id=series_id,
            data_folder=data_path,
            base_ref=base_revision_id,
            variant_ref=variant_revision_id,
            base_deck=base_deck,
            variant_deck=variant_deck,
            opponents=opponents,
            paths_by_deck_id=paths_by_deck_id,
            pod_name=pod,
            seeds=seeds,
            tested_seats=tested_seats,
            budget_pairs=budget_pairs,
            look_every_pairs=look_every_pairs,
            threshold_pp=threshold_pp,
            significance_level=significance_level,
            play_override=play_override,
            workers=used_workers,
            games_per_jvm=used_batch,
            engine=engine,
            bridge_sha=jar_sha,
            qualification=bridge_qualification(),
            slot_alignment=alignment,
            purpose=purpose,
            player_count=table_size,
            opponent_ids=opponent_ids,
            experiment=experiment,
        )
        job.persist()
        with self._lock:
            self._jobs[series_id] = job

        thread = threading.Thread(target=job.run, daemon=True)
        thread.start()
        return job

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if sys.platform == "win32":
            import ctypes

            win_dll = getattr(ctypes, "WinDLL", None)
            if win_dll is None:
                return False
            k32 = win_dll("kernel32", use_last_error=True)
            k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            k32.GetExitCodeProcess.restype = ctypes.c_int
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.restype = ctypes.c_int
            process_query_limited_info = 0x1000
            still_active = 259
            handle = k32.OpenProcess(process_query_limited_info, 0, pid)
            if not handle:
                return ctypes.get_last_error() == 5
            try:
                exit_code = ctypes.c_uint32()
                ok = k32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                return bool(ok) and exit_code.value == still_active
            finally:
                k32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @classmethod
    def _is_lock_alive(cls, lock_path: Path) -> bool:
        if not lock_path.is_file():
            return False
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict):
            return False
        pid = data.get("pid")
        if type(pid) is not int or pid <= 0:
            return False
        return cls._is_pid_alive(pid)

    @classmethod
    def _is_disk_resumable(cls, raw: dict[str, object], target_folder: Path | None = None) -> bool:
        opp_deck_ids = raw.get("opponent_deck_ids")
        if (
            not isinstance(opp_deck_ids, list)
            or not opp_deck_ids
            or not all(isinstance(x, str) and x for x in opp_deck_ids)
        ):
            return False
        seed_plan = raw.get("seed_plan")
        if not isinstance(seed_plan, dict):
            return False
        if type(seed_plan.get("first_seed")) is not int:
            return False
        seeds_planned = seed_plan.get("seeds_planned")
        if type(seeds_planned) is not int or seeds_planned < 1:
            return False
        tested_seats = raw.get("tested_seats")
        if (
            not isinstance(tested_seats, list)
            or not tested_seats
            or not all(type(s) is int for s in tested_seats)
        ):
            return False
        budget_pairs = raw.get("budget_pairs")
        if type(budget_pairs) is not int or budget_pairs < 1:
            return False
        threshold_pp = raw.get("threshold_pp")
        if not isinstance(threshold_pp, (int, float)) or isinstance(threshold_pp, bool):
            return False
        err = raw.get("error")
        if isinstance(err, str) and (
            "mixed " in err
            or "abweichen" in err
            or "nicht fortsetzbar" in err
            or DETERMINISM_VIOLATION in err
        ):
            return False
        if target_folder is not None and isinstance(raw.get("series_id"), str):
            sid = str(raw["series_id"])
            try:
                if series_violation(target_folder, sid) is not None:
                    return False
                if series_key_problem(target_folder, sid) is not None:
                    return False  # recorded with another game key version: start a new series
            except (ManifestMismatch, ValueError):
                return False
            deck_dir = games_folder(target_folder) / "paired_decks" / sid
            if not list(deck_dir.glob("base-*.json")) or not list(deck_dir.glob("variant-*.json")):
                return False
        return True

    @classmethod
    def _normalize_disk_series(
        cls, raw: dict[str, object], target_folder: Path | None = None
    ) -> dict[str, object]:
        out = dict(raw)
        status = out.get("status")
        if status in {"running", "pending"}:
            sid = out.get("series_id")
            if (
                target_folder is not None
                and isinstance(sid, str)
                and cls._is_lock_alive(
                    games_folder(target_folder) / "paired_decks" / sid / "running.lock"
                )
            ):
                out["status"] = "running"
                out["resumable"] = False
            else:
                out["status"] = "interrupted"
                out["resumable"] = cls._is_disk_resumable(out, target_folder)
        elif status in {"cancelled", "failed"}:
            out["resumable"] = cls._is_disk_resumable(out, target_folder)
        else:
            out["resumable"] = False
        return out

    @staticmethod
    def _load_progress_jsonl(
        path: Path,
    ) -> dict[tuple[str, int, int], paired_comparison.PlayedGame]:
        loaded: dict[tuple[str, int, int], paired_comparison.PlayedGame] = {}
        if not path.is_file():
            return loaded
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if text and not text.endswith("\n") and lines:
            lines = lines[:-1]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            arm = rec.get("arm")
            seed = rec.get("seed")
            seat = rec.get("seat")
            played = rec.get("played")
            if (
                isinstance(arm, str)
                and type(seed) is int
                and type(seat) is int
                and isinstance(played, dict)
            ):
                loaded[(arm, seed, seat)] = played  # type: ignore[assignment]
        return loaded

    def resume_series(
        self,
        data_folder: str | Path,
        series_id: str,
        *,
        workers: int | None = None,
        games_per_jvm: int | None = None,
        play_override: paired_comparison.PairPlayer | None = None,
    ) -> PairedSeriesJob:
        safe_id = validate_series_id(series_id)
        target_folder = Path(data_folder).resolve()
        with self._lock:
            existing = self._jobs.get(safe_id)
            if existing is not None and existing.status in {"pending", "running"}:
                raise RuntimeError(f"Serie {safe_id} läuft bereits (status={existing.status})")

            deck_dir = games_folder(target_folder) / "paired_decks" / safe_id
            if self._is_lock_alive(deck_dir / "running.lock"):
                raise RuntimeError(
                    f"Serie {safe_id} läuft bereits in einem aktiven Prozess (running.lock)"
                )

            disk = games_folder(target_folder) / f"{safe_id}.paired.json"
            if not disk.is_file():
                raise FileNotFoundError(f"Unbekannte Serie: {safe_id}")
            raw = json.loads(disk.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError(f"Ungültige Serien-Datei: {safe_id}")
            if raw.get("status") == "completed":
                raise RuntimeError(f"Serie {safe_id} ist bereits abgeschlossen")
            # on every path (chunked or pool): a journal with a violation ends the series for good
            violation = series_violation(target_folder, safe_id)
            if violation is not None:
                raise ValueError(f"{violation} (nicht fortsetzbar)")
            key_problem = series_key_problem(target_folder, safe_id)
            if key_problem is not None:
                # an older key version is no violation and never mixed with new games
                raise ValueError(f"{key_problem} (nicht fortsetzbar)")

            base_files = sorted(deck_dir.glob("base-*.json"))
            variant_files = sorted(deck_dir.glob("variant-*.json"))
            if not base_files or not variant_files:
                raise FileNotFoundError(f"Deck-Snapshots für Serie {safe_id} fehlen")
            base_path = base_files[0]
            variant_path = variant_files[0]
            base_deck = load_rules_deck_snapshot(base_path)
            variant_deck = load_rules_deck_snapshot(variant_path)

            pod_raw = raw.get("pod")
            if not isinstance(pod_raw, str) or not pod_raw:
                raise ValueError(f"pod fehlt in Serie {safe_id} (nicht fortsetzbar)")
            pod = pod_raw
            raw_opp_ids = raw.get("opponent_ids")
            if raw_opp_ids is not None and (
                not isinstance(raw_opp_ids, list)
                or not all(isinstance(x, str) and x for x in raw_opp_ids)
            ):
                raise ValueError(f"Ungültige opponent_ids in Serie {safe_id} (nicht fortsetzbar)")
            opp_ids = list(raw_opp_ids) if isinstance(raw_opp_ids, list) else None
            opp_paths = _table_opponent_paths(
                None, deck_dir, pod, opp_ids, {base_deck.deck_id, variant_deck.deck_id}
            )
            opponents = [load_rules_deck_snapshot(path) for path in opp_paths]

            raw_opp_deck_ids = raw.get("opponent_deck_ids")
            if (
                not isinstance(raw_opp_deck_ids, list)
                or not raw_opp_deck_ids
                or not all(isinstance(x, str) and x for x in raw_opp_deck_ids)
            ):
                raise ValueError(
                    f"opponent_deck_ids fehlt in Serie {safe_id} "
                    "(Alt-Serie ohne Gegner-Bindung, nicht fortsetzbar)"
                )
            if [d.deck_id for d in opponents] != [str(x) for x in raw_opp_deck_ids]:
                raise ValueError(
                    f"Gegner-Deck-IDs in Serie {safe_id} weichen ab (nicht fortsetzbar)"
                )

            seed_plan = raw.get("seed_plan")
            if not isinstance(seed_plan, dict):
                raise ValueError(f"seed_plan fehlt in Serie {safe_id} (nicht fortsetzbar)")
            first_seed = seed_plan.get("first_seed")
            seeds_planned = seed_plan.get("seeds_planned")
            if type(first_seed) is not int or type(seeds_planned) is not int or seeds_planned < 1:
                raise ValueError(f"Ungültiger seed_plan in Serie {safe_id} (nicht fortsetzbar)")
            plan_players = seed_plan.get("player_count")
            if type(plan_players) is int and plan_players != 1 + len(opponents):
                raise ValueError(
                    f"Sitzanzahl ({1 + len(opponents)}) weicht vom seed_plan "
                    f"({plan_players}) ab (nicht fortsetzbar)"
                )
            seen = observed_table_sizes(raw)
            if any(size != 1 + len(opponents) for size in seen.sizes):
                # the played games' seat rows name another table: never resumed on top of them
                raise ValueError(
                    f"Sitzanzahl ({1 + len(opponents)}) weicht von den gespielten Partien "
                    f"({', '.join(map(str, seen.sizes))} Sitze) ab (nicht fortsetzbar)"
                )
            if seen.unreadable:
                raise ValueError(
                    f"Sitzanzahl der gespielten Partien in Serie {safe_id} nicht lesbar "
                    "(nicht fortsetzbar)"
                )
            seeds = [first_seed + i for i in range(seeds_planned)]

            tested_seats_raw = raw.get("tested_seats")
            if (
                not isinstance(tested_seats_raw, list)
                or not tested_seats_raw
                or not all(type(s) is int for s in tested_seats_raw)
            ):
                raise ValueError(f"tested_seats fehlt in Serie {safe_id} (nicht fortsetzbar)")
            tested_seats = list(tested_seats_raw)

            budget_pairs = raw.get("budget_pairs")
            if type(budget_pairs) is not int or budget_pairs < 1:
                raise ValueError(f"budget_pairs fehlt in Serie {safe_id} (nicht fortsetzbar)")
            look_every_pairs = raw.get("look_every_pairs")
            if type(look_every_pairs) is not int or look_every_pairs < 1:
                raise ValueError(f"look_every_pairs fehlt in Serie {safe_id} (nicht fortsetzbar)")
            threshold_raw = raw.get("threshold_pp")
            if not isinstance(threshold_raw, (int, float)) or isinstance(threshold_raw, bool):
                raise ValueError(f"threshold_pp fehlt in Serie {safe_id} (nicht fortsetzbar)")
            threshold_pp = float(threshold_raw)
            sig_raw = raw.get("significance_level")
            if not isinstance(sig_raw, (int, float)) or isinstance(sig_raw, bool):
                raise ValueError(f"significance_level fehlt in Serie {safe_id} (nicht fortsetzbar)")
            significance_level = float(sig_raw)

            paths_by_deck_id: dict[str, Path] = {
                base_deck.deck_id: base_path,
                variant_deck.deck_id: variant_path,
            }
            for deck, path in zip(opponents, opp_paths, strict=True):
                paths_by_deck_id[deck.deck_id] = path

            raw_exec = raw.get("execution")
            exec_meta = raw_exec if isinstance(raw_exec, dict) else {}
            used_workers, used_batch = checked_series_settings(
                workers if workers is not None else exec_meta.get("workers"),
                games_per_jvm if games_per_jvm is not None else exec_meta.get("games_per_jvm"),
            )

            engine: SeriesEngine | None = None
            if play_override is None:
                engine = series_engine(target_folder, used_batch)
                if engine is None:
                    state = engine_state(target_folder)
                    raise RuntimeError(
                        str(state.get("reason") or "Engine ist nicht bereitgestellt")
                    )
            jar_sha = (
                command_bridge_jar_sha256(target_folder, engine.command)
                if engine is not None
                else (str(raw["bridge_jar_sha256"]) if raw.get("bridge_jar_sha256") else None)
            )
            recorded_sha = raw.get("bridge_jar_sha256")
            if (
                isinstance(recorded_sha, str)
                and recorded_sha
                and jar_sha is not None
                and recorded_sha != jar_sha
            ):
                raise ValueError(
                    f"Bridge-JAR-SHA weicht ab ({recorded_sha[:12]} != {jar_sha[:12]}, "
                    "nicht fortsetzbar)"
                )

            raw_alignment = (
                raw.get("slot_alignment") if isinstance(raw.get("slot_alignment"), dict) else None
            )
            preloaded = self._load_progress_jsonl(deck_dir / "progress.jsonl")
            if play_override is None:  # games the engine played, not stand-ins of a test
                stale = pilot_change_message(preloaded, f"fp:{header_pilot_fingerprint()}")
                if stale is not None:
                    raise ValueError(stale)

            job = PairedSeriesJob(
                series_id=safe_id,
                data_folder=target_folder,
                base_ref=str(raw.get("base_ref") or base_deck.deck_id),
                variant_ref=str(raw.get("variant_ref") or variant_deck.deck_id),
                base_deck=base_deck,
                variant_deck=variant_deck,
                opponents=opponents,
                paths_by_deck_id=paths_by_deck_id,
                pod_name=pod,
                seeds=seeds,
                tested_seats=tested_seats,
                budget_pairs=budget_pairs,
                look_every_pairs=look_every_pairs,
                threshold_pp=threshold_pp,
                significance_level=significance_level,
                play_override=play_override,
                workers=used_workers,
                games_per_jvm=used_batch,
                engine=engine,
                bridge_sha=jar_sha,
                qualification=bridge_qualification(),
                raw_slot_alignment=raw_alignment,
                purpose=str(seed_plan.get("purpose") or "unspecified"),
                player_count=1 + len(opponents),
                opponent_ids=opp_ids,
                created_at=str(raw.get("created_at")) if raw.get("created_at") else None,
                preloaded_games=preloaded,
                experiment=raw_exp if isinstance(raw_exp := raw.get("experiment"), dict) else None,
            )
            job.persist()
            job._write_lock()
            self._jobs[safe_id] = job

        thread = threading.Thread(target=job.run, daemon=True)
        try:
            thread.start()
        except Exception:
            job._release_lock()
            raise
        return job

    def get_series(self, data_folder: str | Path, series_id: str) -> dict[str, object] | None:
        safe_id = validate_series_id(series_id)
        target_folder = Path(data_folder).resolve()
        with self._lock:
            job = self._jobs.get(safe_id)
        found: dict[str, object] | None = None
        if job is not None and job.data_folder == target_folder:
            found = job.to_dict()
        disk = games_folder(target_folder) / f"{safe_id}.paired.json"
        if found is None and disk.is_file():
            try:
                raw = json.loads(disk.read_text(encoding="utf-8"))
            except ValueError:
                return None
            if isinstance(raw, dict):
                found = self._normalize_disk_series(raw, target_folder)
        if found is not None:
            found["determinism_guard"] = _guard_of(target_folder, safe_id)
        return found

    def get_job(self, series_id: str) -> PairedSeriesJob | None:
        """The running (or finished) job of this process, if it started here."""
        with self._lock:
            return self._jobs.get(validate_series_id(series_id))

    def cancel_series(self, series_id: str) -> bool:
        safe_id = validate_series_id(series_id)
        with self._lock:
            job = self._jobs.get(safe_id)
        if job is None:
            return False
        job.cancel()
        return True

    def list_series(self, data_folder: str | Path) -> list[dict[str, object]]:
        target_folder = Path(data_folder).resolve()
        folder = games_folder(target_folder)
        by_id: dict[str, dict[str, object]] = {}
        if folder.is_dir():
            for path in sorted(folder.glob("paired-*.paired.json"), reverse=True)[:30]:
                with contextlib.suppress(OSError, ValueError):
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and isinstance(raw.get("series_id"), str):
                        by_id[str(raw["series_id"])] = self._normalize_disk_series(
                            raw, target_folder
                        )
        with self._lock:
            for sid, job in self._jobs.items():
                if job.data_folder == target_folder:
                    by_id[sid] = job.to_dict()
        items = list(by_id.values())
        items.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        # read field only (S1 Rest): "unbewacht n/N" and "vergleichbar" next to every listed series
        for item in items[:30]:
            item["determinism_guard"] = _guard_of(target_folder, str(item.get("series_id")))
        return items[:30]


def _guard_of(data_folder: Path, series_id: str) -> dict[str, object] | None:
    """The determinism guard of a stored series as a read field; ``None`` when unknown.

    ``unbewacht n/N`` is ``unguarded`` of ``finished``, ``vergleichbar`` is ``comparable_keys``
    (see ``series_record.series_guard``). A series without a journal (the chunked path, or
    nothing played yet) and a series whose id is no valid id give ``None``: unknown, never 0.
    A manifest or journal that cannot be read gives ``{"error": ...}``.
    """
    try:
        return series_guard(data_folder, series_id)
    except ManifestMismatch as error:
        return {"error": str(error)}
    except ValueError:
        return None


paired_series_manager = PairedSeriesManager()


def simulator_readiness_audit(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    cards: Sequence[RevisionCard] | None = None,
    tiers: Sequence[str] = ("S", "A"),
    available_check: Callable[[], bool] | None = None,
    status_lookup: Callable[[str], str] | None = None,
    pilot_known: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    """Audit XMage engine & pilot readiness for the deck and its free Tier-S/A pool candidates (C-3).

    Fails closed to ``status = "UNKNOWN"`` when card catalogs are unreadable (never reports
    fake readiness). Never mutates scores or tiers.
    """
    check_avail = available_check or builder.sim_readiness_available
    get_status = status_lookup or builder.sim_readiness_status
    has_pilot = pilot_known or (lambda n: card_facts(n) is not None)

    if not commander_names:
        raise ValueError("commander is required")

    def _unknown_result(reason: str) -> dict[str, object]:
        return {
            "schema": SCHEMA_READINESS_AUDIT,
            "commander": list(commander_names),
            "available": False,
            "status": "UNKNOWN",
            "reason": reason,
            "deck": {"total": 0, "ready": None, "issues": []},
            "free_top_candidates": {
                "tiers": list(tiers),
                "total": 0,
                "ready": None,
                "issues": [],
                "items": [],
            },
        }

    if not check_avail():
        return _unknown_result("XMage-/Piloten-Kartendaten sind nicht lesbar.")

    if pilot_known is None:
        try:
            card_facts("__readiness_probe__")
        except (CardCatalogError, OSError, ValueError):
            return _unknown_result("Piloten-Kartenwissen ist nicht lesbar.")

    # Resolve deck cards
    deck_rows: list[Mapping[str, object]] = []
    if cards is not None and len(cards) > 0:
        deck_rows = [dict(r) for r in decks.list_rows(store, cards)]
    else:
        for base in decks.baseline_decks_for_commander(commander_names):
            with contextlib.suppress(KeyError):
                baseline = resolve_repo_baseline_cards(store, str(base["revision_id"]))
                deck_rows = [dict(r) for r in decks.list_rows(store, baseline)]
                break

    deck_seen: dict[str, dict[str, object]] = {}
    deck_card_ids: set[str] = set()
    deck_card_names: set[str] = set()
    try:
        for row in deck_rows:
            cid = str(row.get("card_id") or "")
            if cid:
                deck_card_ids.add(cid)
            eng_name = str(row.get("engine_name") or "")
            ora_name = str(row.get("oracle_name") or "")
            if eng_name:
                deck_card_names.add(eng_name)
            if ora_name:
                deck_card_names.add(ora_name)
            name = eng_name or ora_name
            if not name or name in deck_seen:
                continue
            sim_st = get_status(name)
            pilot_ok = bool(has_pilot(name))
            ok = sim_st == "OK" and pilot_ok
            deck_seen[name] = {
                "card_id": row.get("card_id"),
                "name": name,
                "zone": row.get("zone", "main"),
                "sim_status": sim_st,
                "pilot_known": pilot_ok,
                "ready": ok,
            }
    except (CardCatalogError, OSError, ValueError):
        return _unknown_result(
            "XMage-/Piloten-Kartendaten konnten nicht vollständig gelesen werden."
        )

    deck_issues = [item for item in deck_seen.values() if not item["ready"]]
    deck_ready = len(deck_seen) - len(deck_issues)

    # Free Tier S/A pool candidates not currently in deck
    _identity, _cmd_ids = builder.commander_identity(store, commander_names)
    engine_name_by_id = {
        str(r["card_id"]): str(r["engine_name"] or r["oracle_name"] or "")
        for r in store.connection.execute("SELECT card_id, engine_name, oracle_name FROM card_fact")
    }
    role_rows = store.connection.execute(
        "SELECT card_id, roles FROM ("
        "SELECT c.card_id, GROUP_CONCAT(r.role, ',') AS roles "
        "FROM card c LEFT JOIN card_role r ON r.oracle_id = c.oracle_id "
        "GROUP BY c.card_id)"
    ).fetchall()
    roles_by_id: dict[str, list[str]] = {
        str(r["card_id"]): sorted(str(r["roles"]).split(",")) if r["roles"] else []
        for r in role_rows
    }
    inv_rows = {
        str(r["card_id"]): int(r["available_lower_bound"] or 0)
        for r in store.connection.execute("SELECT card_id, available_lower_bound FROM inventory")
    }

    tier_set = {str(t).upper() for t in tiers}
    strength_res = strength_view.compute(store, commander_names[0], StrengthSettings())
    candidate_items: list[dict[str, object]] = []
    try:
        for entry in strength_res.get("cards", []):
            tier = str(entry.get("tier") or "")
            if tier not in tier_set:
                continue
            cid = str(entry.get("card_id") or "")
            cname = str(entry.get("name") or "")
            lookup_name = engine_name_by_id.get(cid) or cname
            avail = inv_rows.get(cid, 0)
            if (
                avail <= 0
                or (cid and cid in deck_card_ids)
                or cname in deck_card_names
                or lookup_name in deck_card_names
            ):
                continue
            sim_st = get_status(lookup_name)
            pilot_ok = bool(has_pilot(lookup_name))
            ok = sim_st == "OK" and pilot_ok
            candidate_items.append(
                {
                    "card_id": cid,
                    "name": cname,
                    "tier": tier,
                    "index": entry.get("index"),
                    "roles": roles_by_id.get(cid, []),
                    "available": avail,
                    "sim_status": sim_st,
                    "pilot_known": pilot_ok,
                    "ready": ok,
                }
            )
    except (CardCatalogError, OSError, ValueError):
        return _unknown_result(
            "XMage-/Piloten-Kartendaten konnten nicht vollständig gelesen werden."
        )

    tier_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}

    def _cand_key(item: Mapping[str, object]) -> tuple[int, float, str]:
        idx = item.get("index")
        idx_val = float(idx) if isinstance(idx, (int, float)) else -1.0
        return (
            tier_order.get(str(item.get("tier") or ""), 9),
            -idx_val,
            str(item.get("name") or ""),
        )

    candidate_items.sort(key=_cand_key)
    cand_issues = [item for item in candidate_items if not item["ready"]]
    cand_ready = len(candidate_items) - len(cand_issues)

    overall_ok = len(deck_issues) == 0 and len(cand_issues) == 0
    return {
        "schema": SCHEMA_READINESS_AUDIT,
        "commander": list(commander_names),
        "available": True,
        "status": "OK" if overall_ok else "GAPS_FOUND",
        "deck": {
            "total": len(deck_seen),
            "ready": deck_ready,
            "issues": deck_issues,
        },
        "free_top_candidates": {
            "tiers": list(tiers),
            "total": len(candidate_items),
            "ready": cand_ready,
            "issues": cand_issues,
            "items": candidate_items,
        },
    }


__all__ = [
    "ESTIMATED_GAMES_PER_HOUR",
    "MEASURED_BATCH_GAMES_PER_HOUR",
    "MEASURED_TABLE_SEATS",
    "SCHEMA_PAIRED_JOB",
    "SCHEMA_READINESS_AUDIT",
    "SERIES_PURPOSES",
    "THROUGHPUT_SOURCE",
    "PairedSeriesJob",
    "PairedSeriesManager",
    "estimate_series_duration",
    "paired_series_manager",
    "planned_detectable_difference_pp",
    "rotation_plan",
    "simulator_readiness_audit",
    "table_plan",
    "validate_series_id",
]
