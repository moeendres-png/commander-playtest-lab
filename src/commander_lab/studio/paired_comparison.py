"""Paired deck comparison on Studio game logs: base versus variant, same tables.

Two deck lists (a base and a variant with swapped cards) play the same seeds at the
same tables in the same seat; only the deck in the tested seat differs, so the games
form pairs and the difference of the win credits is a paired difference, not the
difference of two independent samples. A comparison carries a question ("is the
difference greater than x percentage points?") and a budget of pairs; after every
planned look it stops by itself once the interval answers the question, and at the
budget it ends ``NOT_DECIDED``. A failed game censors its pair: it is counted and
never scored as a loss.

The statistics are the repository's qualified paired machinery, reused as-is from
``commander_lab.engine.rules.full_game_comparison`` (#731, #832, #870, #1043):
the cluster-robust Student-t interval of the paired differences (one cluster per
seed), the exact sign test on discordant pairs — over the discordant seeds in a
zero-spread look, where the seed is the independent unit — and the O'Brien-Fleming
alpha spending over the planned looks. This module only pairs Studio logs
(``card_outcomes`` exposures), applies the threshold decision the Studio question
asks for, and drives a series of recorded games. It decides no rule; XMage plays
every game. The result is a ``SIMULATED_RESULT``: these pilots, this pod set, this
engine pin.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, TypedDict

from commander_lab.engine.rules.full_game_comparison import (
    cluster_difference_stats,
    pod_decks,
    sequential_look_alphas,
    sequential_look_seed_counts,
    sign_test_p_value,
    student_t_quantile,
)
from commander_lab.models import RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)

from .card_outcomes import GameExposure, LoadReport, game_exposures, load_exposures
from .games import games_folder

SCHEMA = "studio-paired-comparison-1"
DATA_CLASS = "SIMULATED_RESULT"
ESTIMAND = (
    "win-credit difference variant minus base over paired games "
    "(same seed, same seat, same other decks); simulated games, these pilots, this pod set"
)
DEFAULT_SIGNIFICANCE_LEVEL = 0.05
DEFAULT_THRESHOLD_PP = 0.0
DEFAULT_MAX_CENSORED_SHARE = 0.05
ASYMMETRIC_CENSORING_P_MAX = 0.25
MIN_BUDGET_PAIRS = 2
MAX_BUDGET_PAIRS = 1000
ARMS = ("base", "variant")

Answer = Literal["ABOVE", "NOT_ABOVE"]
Status = Literal["DECIDED", "NOT_DECIDED", "NO_PAIRS"]


class PairRecord(TypedDict):
    seed: int
    seat: int
    opponents: list[str]
    base_game_id: str
    variant_game_id: str
    base_credit: float
    variant_credit: float
    difference: float


class PodPairs(TypedDict):
    opponents: list[str]
    pairs: int


class Question(TypedDict):
    threshold_pp: float
    significance_level: float
    method: str


class PairedComparison(TypedDict):
    schema: str
    data_class: str
    estimand: str
    status: Status
    answer: Answer | None
    stop_reason: str
    base_deck_id: str
    variant_deck_id: str
    question: Question
    pairs_completed: int
    pairs_censored: int
    unpaired_base: int
    unpaired_variant: int
    games_failed_base: int
    games_failed_variant: int
    failure_classes: dict[str, dict[str, int]]
    base_rate: float | None
    variant_rate: float | None
    difference_pp: float | None
    difference_ci95_pp: list[float] | None
    decision_alpha: float | None
    decision_level_pct: float | None
    decision_ci_pp: list[float] | None
    detectable_difference_pp: float | None
    variant_only_wins: int
    baseline_only_wins: int
    tied_pairs: int
    sign_test_p_value: float | None
    seeds: list[int]
    seeds_completed: list[int]
    pods: list[PodPairs]
    tested_seats: list[int]
    engine_commits: list[str]
    pilots: list[str]
    decision_policies: list[str]
    engine_pin: str
    looks_planned: int
    looks_used: int
    pairs_played: int
    execution: dict[str, object]
    warnings: list[str]
    pairs: list[PairRecord]


class PlayedGame(TypedDict):
    """One played game of a comparison series: its exposure, or why there is none."""

    exposure: GameExposure | None
    failure_class: str | None


#: Plays one game of one arm ("base" or "variant") at (seed, seat) and reports it.
PairPlayer = Callable[[str, int, int], PlayedGame]

_METHOD_LOGS = (
    "One look at the full significance level over the pairs found in the logs. "
    "Cluster-robust Student-t interval of the paired win-credit differences (one "
    "cluster per seed, commander_lab.engine.rules.full_game_comparison."
    "cluster_difference_stats); the look decides when that interval at the look's "
    "level lies entirely above the threshold (difference greater) or entirely at or "
    "below it (not greater). A zero-spread look (no variation between the seed "
    "clusters) decides only through the exact sign test on the discordant seeds "
    "at the look's level: the seat rotations of one seed share one library "
    "shuffle, so the seed, not the pair, is the independent unit. Failed games "
    "censor their pair and never count as a loss."
)
_METHOD_SERIES = (
    "Looks at fixed cumulative pair counts; the level of each look is spent along an "
    "O'Brien-Fleming-type Lan-DeMets function over the planned looks "
    "(commander_lab.engine.rules.full_game_comparison.sequential_look_alphas), so "
    "repeated looking keeps the overall level. Cluster-robust Student-t interval of "
    "the paired win-credit differences (one cluster per seed, cluster_difference_stats); "
    "a look decides when that interval at the look's level lies entirely above the "
    "threshold (difference greater) or entirely at or below it (not greater). A "
    "zero-spread look (no variation between the seed clusters) decides only "
    "through the exact sign test on the discordant seeds at the look's level: "
    "the seat rotations of one seed share one library shuffle, so the seed, not "
    "the pair, is the independent unit. Failed games censor their pair and never "
    "count as a loss."
)


def _pp(value: float) -> float:
    return round(value * 100.0, 3)


def _credit_at(game: GameExposure, seat: int, deck_id: str) -> float | None:
    """The win credit of ``deck_id`` seated at ``seat`` in this game, or None."""
    for row in game["seats"]:
        if row["seat"] == seat and row["deck_id"] == deck_id:
            return row["win_credit"]
    return None


def _arm_index(
    exposures: Sequence[GameExposure], deck_id: str
) -> tuple[dict[tuple[int, int, tuple[str, ...]], list[tuple[str, float]]], int]:
    """Finished games of one arm by (seed, seat, opponents) key; seedless games counted.

    A deck seated twice in one game counts at its lowest seat only, as everywhere in
    the Studio outcomes. Games without a recorded seed cannot pair and are counted
    in the second return value instead of being dropped silently.
    """
    index: dict[tuple[int, int, tuple[str, ...]], list[tuple[str, float]]] = {}
    seedless = 0
    for game in exposures:
        own = sorted((s for s in game["seats"] if s["deck_id"] == deck_id), key=lambda s: s["seat"])
        if not own:
            continue
        if game["seed"] is None:
            seedless += 1
            continue
        seat = own[0]
        opponents = tuple(s["deck_id"] for s in game["seats"] if s["seat"] != seat["seat"])
        key = (game["seed"], seat["seat"], opponents)
        index.setdefault(key, []).append((game["game_id"], seat["win_credit"]))
    for games in index.values():
        games.sort()
    return index, seedless


def pair_exposures(
    exposures: Sequence[GameExposure], *, base_deck_id: str, variant_deck_id: str
) -> tuple[list[PairRecord], int, int, int]:
    """Pairs, unpaired base games, unpaired variant games, seedless games.

    Two games pair when seed, tested seat and the other seats' decks all agree.
    Duplicate keys within one arm pair off in game-id order; the rest are unpaired
    and reported, never silently dropped.
    """
    base_index, base_seedless = _arm_index(exposures, base_deck_id)
    variant_index, variant_seedless = _arm_index(exposures, variant_deck_id)
    pairs: list[PairRecord] = []
    unpaired_base = unpaired_variant = 0
    for key in sorted(set(base_index) | set(variant_index)):
        seed, seat, opponents = key
        base_games = base_index.get(key, [])
        variant_games = variant_index.get(key, [])
        for (base_id, base_credit), (variant_id, variant_credit) in zip(
            base_games, variant_games, strict=False
        ):
            pairs.append(
                {
                    "seed": seed,
                    "seat": seat,
                    "opponents": list(opponents),
                    "base_game_id": base_id,
                    "variant_game_id": variant_id,
                    "base_credit": base_credit,
                    "variant_credit": variant_credit,
                    "difference": variant_credit - base_credit,
                }
            )
        unpaired_base += len(base_games) - min(len(base_games), len(variant_games))
        unpaired_variant += len(variant_games) - min(len(base_games), len(variant_games))
    pairs.sort(key=lambda pair: (pair["seed"], pair["seat"], pair["opponents"]))
    return pairs, unpaired_base, unpaired_variant, base_seedless + variant_seedless


def _censoring_issues(
    *,
    censored: int,
    played: int,
    failed_base: int,
    failed_variant: int,
    max_censored_share: float,
) -> tuple[str | None, list[str]]:
    """Refusal reason and warnings when censoring spoils a comparison series."""
    warnings: list[str] = []
    reason: str | None = None
    if played > 0 and censored / played > max_censored_share:
        reason = "CENSORING_LIMIT"
        warnings.append(
            f"censored pair share {censored}/{played} ({censored / played:.1%}) "
            f"exceeds max_censored_share={max_censored_share:.1%}"
        )
    fail_p = sign_test_p_value(failed_base, failed_variant)
    if fail_p <= ASYMMETRIC_CENSORING_P_MAX:
        reason = reason or "ASYMMETRIC_CENSORING"
        warnings.append(
            f"one-sided censoring between arms (base failed {failed_base}, "
            f"variant failed {failed_variant}, sign test p={fail_p:.4f})"
        )
    return reason, warnings


def _check_provenance(
    exposures: Sequence[GameExposure], *, allow_mixed: bool
) -> tuple[dict[str, list[str]], list[str]]:
    """Collect provenance values across exposures and fail closed on mixed origins."""
    warnings: list[str] = []
    provenance: dict[str, list[str]] = {}
    for label, field, values in (
        (
            "engine commits",
            "engine_commit",
            sorted({v for v in (game["engine_commit"] for game in exposures) if v}),
        ),
        (
            "pilot versions",
            "pilot",
            sorted({v for v in (game["pilot"] for game in exposures) if v}),
        ),
        (
            "decision policies",
            "decision_policy",
            sorted({v for v in (game["decision_policy"] for game in exposures) if v}),
        ),
    ):
        provenance[field] = values
        if len(values) > 1:
            if not allow_mixed:
                raise ValueError(f"mixed {label} in one comparison: {', '.join(values)}")
            warnings.append(f"mixed {label} pooled: {', '.join(values)}")
    return provenance, warnings


def _summarize(
    pairs: Sequence[PairRecord],
    *,
    base_deck_id: str,
    variant_deck_id: str,
    threshold_pp: float,
    significance_level: float,
    alpha: float,
    exposures: Sequence[GameExposure],
    allow_mixed: bool,
    series: bool,
) -> tuple[PairedComparison, Answer | None]:
    """The comparison result over ``pairs`` and the decision at level ``alpha``.

    ``exposures`` are the finished games the pairs were built from; their engine
    commits, pilots and policies are the provenance of the result, and a mix of any
    of them refuses the comparison unless ``allow_mixed`` (a comparison across two
    pins or two pilots is not a comparison of two decks).
    """
    clustered = [(pair["seed"], pair["difference"]) for pair in pairs]
    interval, detectable, se = cluster_difference_stats(clustered)
    n = len(pairs)
    difference = sum(pair["difference"] for pair in pairs) / n if n else None
    base_rate = sum(pair["base_credit"] for pair in pairs) / n if n else None
    variant_rate = sum(pair["variant_credit"] for pair in pairs) / n if n else None
    variant_only = sum(1 for pair in pairs if pair["difference"] > 0)
    baseline_only = sum(1 for pair in pairs if pair["difference"] < 0)
    sign_p = sign_test_p_value(variant_only, baseline_only) if n else None
    # The same counts over the seed clusters: the net difference of each seed.
    # The seat rotations of one seed share a library shuffle, so in a zero-spread
    # look the seed — not the pair — is the independent unit; this is the
    # qualified standard of the engine lane (full_game_comparison, the
    # zero-spread confirmation in aggregate_comparison / effective_p_value).
    seed_nets: dict[int, float] = {}
    for pair in pairs:
        seed_nets[pair["seed"]] = seed_nets.get(pair["seed"], 0.0) + pair["difference"]
    seeds_variant = sum(1 for net in seed_nets.values() if net > 0)
    seeds_base = sum(1 for net in seed_nets.values() if net < 0)
    seed_sign_p = sign_test_p_value(seeds_variant, seeds_base) if n else None

    answer: Answer | None = None
    decision_ci: list[float] | None = None
    if difference is not None and se is not None:
        threshold = threshold_pp / 100.0
        if se == 0.0:
            # No spread between the seed clusters: the cluster t test has nothing
            # to stand on, so the sign test over the discordant seeds is the only
            # evidence there is. Seeds whose pairs cancel out are not discordant;
            # all-tied seeds give p = 1 and never decide.
            if seed_sign_p is not None and seed_sign_p < alpha:
                answer = "ABOVE" if difference > threshold else "NOT_ABOVE"
        else:
            df = len({seed for seed, _ in clustered}) - 1
            half = student_t_quantile(1.0 - alpha / 2.0, df) * se
            decision_ci = [_pp(difference - half), _pp(difference + half)]
            if difference - half > threshold:
                answer = "ABOVE"
            elif difference + half <= threshold:
                answer = "NOT_ABOVE"

    pair_games = {
        game_id for pair in pairs for game_id in (pair["base_game_id"], pair["variant_game_id"])
    }
    involved = [game for game in exposures if game["game_id"] in pair_games]
    provenance, warnings = _check_provenance(involved, allow_mixed=allow_mixed)
    if any(game["engine_commit"] is None for game in involved):
        warnings.append("some paired games carry no engine commit")
    pods: Counter[tuple[str, ...]] = Counter(tuple(pair["opponents"]) for pair in pairs)
    result: PairedComparison = {
        "schema": SCHEMA,
        "data_class": DATA_CLASS,
        "estimand": ESTIMAND,
        "status": "NO_PAIRS" if n == 0 else ("DECIDED" if answer else "NOT_DECIDED"),
        "answer": answer,
        "stop_reason": "NO_PAIRS" if n == 0 else ("DECIDED_" + answer if answer else "SINGLE_LOOK"),
        "base_deck_id": base_deck_id,
        "variant_deck_id": variant_deck_id,
        "question": {
            "threshold_pp": threshold_pp,
            "significance_level": significance_level,
            "method": _METHOD_SERIES if series else _METHOD_LOGS,
        },
        "pairs_completed": n,
        "pairs_censored": 0,
        "unpaired_base": 0,
        "unpaired_variant": 0,
        "games_failed_base": 0,
        "games_failed_variant": 0,
        "failure_classes": {"base": {}, "variant": {}},
        "base_rate": None if base_rate is None else round(base_rate, 6),
        "variant_rate": None if variant_rate is None else round(variant_rate, 6),
        "difference_pp": None if difference is None else _pp(difference),
        "difference_ci95_pp": (
            None if interval is None else [_pp(interval.low), _pp(interval.high)]
        ),
        "decision_alpha": round(alpha, 6) if n else None,
        "decision_level_pct": round((1.0 - alpha) * 100.0, 4) if n else None,
        "decision_ci_pp": decision_ci,
        "detectable_difference_pp": None if detectable is None else _pp(detectable),
        "variant_only_wins": variant_only,
        "baseline_only_wins": baseline_only,
        "tied_pairs": n - variant_only - baseline_only,
        "sign_test_p_value": None if sign_p is None else round(sign_p, 6),
        "seeds": [],
        "seeds_completed": sorted({pair["seed"] for pair in pairs}),
        "pods": [
            {"opponents": list(pod), "pairs": count}
            for pod, count in sorted(pods.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "tested_seats": sorted({pair["seat"] for pair in pairs}),
        "engine_commits": provenance["engine_commit"],
        "pilots": provenance["pilot"],
        "decision_policies": provenance["decision_policy"],
        "engine_pin": canonical_xmage_engine_pin(),
        "looks_planned": 1,
        "looks_used": 1,
        "pairs_played": n,
        "execution": {},
        "warnings": warnings,
        "pairs": list(pairs),
    }
    return result, answer


def compare_logs(
    games_dir: str | Path,
    *,
    base_deck_id: str,
    variant_deck_id: str,
    threshold_pp: float = DEFAULT_THRESHOLD_PP,
    significance_level: float = DEFAULT_SIGNIFICANCE_LEVEL,
    allow_mixed: bool = False,
) -> PairedComparison:
    """Pair the finished games of two decks in a logs folder and answer the question.

    One look at the full significance level; for a series that stops by itself use
    :func:`run_comparison_series`.

    Provenance in this mode: ``games_failed_base``/``games_failed_variant`` count
    the failed or unfinished games naming each deck (the load report's
    ``skipped_with_deck``). Such a game belongs to no pair, so ``pairs_censored``
    stays 0 here and a warning names the skipped games instead of letting the
    counters claim a false zero. ``seeds`` names the completed seeds (attempted
    seeds are a series concept), and ``engine_pin`` is the current canonical
    pin — the recorded provenance of the paired games themselves is in
    ``engine_commits``.
    """
    if base_deck_id == variant_deck_id:
        raise ValueError("base and variant must be two different decks")
    if not 0.0 < significance_level < 1.0:
        raise ValueError("significance_level must be within (0, 1)")
    report: LoadReport = load_exposures(games_dir)
    pairs, unpaired_base, unpaired_variant, seedless = pair_exposures(
        report["exposures"], base_deck_id=base_deck_id, variant_deck_id=variant_deck_id
    )
    result, answer = _summarize(
        pairs,
        base_deck_id=base_deck_id,
        variant_deck_id=variant_deck_id,
        threshold_pp=threshold_pp,
        significance_level=significance_level,
        alpha=significance_level,
        exposures=report["exposures"],
        allow_mixed=allow_mixed,
        series=False,
    )
    if seedless:
        result["warnings"].append(
            f"{seedless} game(s) of the two decks carry no seed and cannot pair"
        )
    failed_base = report["skipped_with_deck"].get(base_deck_id, 0)
    failed_variant = report["skipped_with_deck"].get(variant_deck_id, 0)
    result["games_failed_base"] = failed_base
    result["games_failed_variant"] = failed_variant
    if failed_base or failed_variant:
        result["warnings"].append(
            f"{failed_base} failed or unfinished game(s) name the base deck and "
            f"{failed_variant} the variant deck; in logs mode they belong to no "
            "pair, so pairs_censored stays 0 — a skipped game is never scored"
        )
    if pairs:
        result["warnings"].append(
            "engine_pin names the current canonical pin; the paired games were "
            "recorded under the engine commits listed in engine_commits"
        )
    result["seeds"] = list(result["seeds_completed"])
    result["unpaired_base"] = unpaired_base
    result["unpaired_variant"] = unpaired_variant
    if result["status"] == "DECIDED":
        result["stop_reason"] = "DECIDED_" + str(answer)
    elif result["status"] == "NOT_DECIDED":
        result["stop_reason"] = "SINGLE_LOOK"
    result["execution"] = {"mode": "logs", "executor": "studio-paired-comparison-1"}
    return result


def run_comparison_series(
    *,
    base_deck_id: str,
    variant_deck_id: str,
    seeds: Sequence[int],
    tested_seats: Sequence[int],
    budget_pairs: int,
    look_every_pairs: int,
    threshold_pp: float = DEFAULT_THRESHOLD_PP,
    significance_level: float = DEFAULT_SIGNIFICANCE_LEVEL,
    max_censored_share: float = DEFAULT_MAX_CENSORED_SHARE,
    allow_mixed: bool = False,
    play: PairPlayer,
    execution: Mapping[str, object] | None = None,
) -> PairedComparison:
    """Play a paired series that stops by itself once the question is answered.

    ``play(arm, seed, seat)`` plays one game of one arm and reports its exposure
    (``None`` when the game failed or did not finish: the pair is censored). Units
    run seed by seed, seat by seat, base before variant, exactly the pod grouping
    of the engine lane's ``plan_comparison_cases``. Looks sit at fixed cumulative
    pair counts (``sequential_look_seed_counts`` over the budget); the level of a
    look is its O'Brien-Fleming increment (``sequential_look_alphas``). The series
    ends at the first deciding look (unless censoring exceeds ``max_censored_share``
    or is one-sided across arms), else at the budget with ``NOT_DECIDED``.
    """
    if base_deck_id == variant_deck_id:
        raise ValueError("base and variant must be two different decks")
    if budget_pairs < MIN_BUDGET_PAIRS:
        raise ValueError(f"budget_pairs must be at least {MIN_BUDGET_PAIRS}")
    if budget_pairs > MAX_BUDGET_PAIRS:
        raise ValueError(f"budget_pairs must be at most {MAX_BUDGET_PAIRS}")
    if look_every_pairs < 1:
        raise ValueError("look_every_pairs must be at least 1")
    if not 0.0 < significance_level < 1.0:
        raise ValueError("significance_level must be within (0, 1)")
    if not 0.0 <= max_censored_share <= 1.0:
        raise ValueError("max_censored_share must be within [0, 1]")
    if not seeds or not tested_seats:
        raise ValueError("seeds and tested_seats must not be empty")
    units = [(seed, seat) for seed in seeds for seat in tested_seats]
    if budget_pairs > len(units):
        raise ValueError(
            f"budget of {budget_pairs} pairs exceeds the {len(units)} planned units "
            "(seeds x tested seats); plan more seeds"
        )
    units = units[:budget_pairs]
    look_counts = sequential_look_seed_counts(budget_pairs, look_every_pairs)
    alphas = sequential_look_alphas(significance_level, look_counts)

    pairs: list[PairRecord] = []
    exposures: list[GameExposure] = []
    censored = 0
    failed: Counter[str] = Counter()
    failure_classes: dict[str, Counter[str]] = {"base": Counter(), "variant": Counter()}
    misseated = 0
    answer: Answer | None = None
    looks_used = 0
    attempted = 0
    attempted_seeds: list[int] = []
    for index, (seed, seat) in enumerate(units):
        attempted_seeds.append(seed)
        played: dict[str, PlayedGame] = {}
        credits: dict[str, float | None] = {}
        for arm, deck_id in (("base", base_deck_id), ("variant", variant_deck_id)):
            game = play(arm, seed, seat)
            played[arm] = game
            exposure = game["exposure"]
            if exposure is None:
                failed[arm] += 1
                failure_classes[arm][game["failure_class"] or "Unfinished"] += 1
                credits[arm] = None
                continue
            exposures.append(exposure)
            _check_provenance(exposures, allow_mixed=allow_mixed)
            credit = _credit_at(exposure, seat, deck_id)
            if credit is None:
                # The game finished but does not seat the arm's deck at the tested
                # seat: the pairing plan was not played. Censor the pair loudly.
                misseated += 1
                failed[arm] += 1
                failure_classes[arm]["Misseated"] += 1
            credits[arm] = credit
        if credits["base"] is None or credits["variant"] is None:
            censored += 1
        else:
            base_exposure = played["base"]["exposure"]
            variant_exposure = played["variant"]["exposure"]
            if base_exposure is None or variant_exposure is None:
                censored += 1  # unreachable: both credits came from these exposures
            else:
                pairs.append(
                    {
                        "seed": seed,
                        "seat": seat,
                        "opponents": [
                            row["deck_id"] for row in base_exposure["seats"] if row["seat"] != seat
                        ],
                        "base_game_id": base_exposure["game_id"],
                        "variant_game_id": variant_exposure["game_id"],
                        "base_credit": credits["base"],
                        "variant_credit": credits["variant"],
                        "difference": credits["variant"] - credits["base"],
                    }
                )
        attempted = index + 1
        if attempted in look_counts:
            looks_used += 1
            _, answer = _summarize(
                pairs,
                base_deck_id=base_deck_id,
                variant_deck_id=variant_deck_id,
                threshold_pp=threshold_pp,
                significance_level=significance_level,
                alpha=alphas[looks_used - 1],
                exposures=exposures,
                allow_mixed=allow_mixed,
                series=True,
            )
            blocker_reason, _ = _censoring_issues(
                censored=censored,
                played=attempted,
                failed_base=failed["base"],
                failed_variant=failed["variant"],
                max_censored_share=max_censored_share,
            )
            if answer is not None and blocker_reason is None:
                break
    result, _ = _summarize(
        pairs,
        base_deck_id=base_deck_id,
        variant_deck_id=variant_deck_id,
        threshold_pp=threshold_pp,
        significance_level=significance_level,
        alpha=alphas[looks_used - 1] if looks_used else significance_level,
        exposures=exposures,
        allow_mixed=allow_mixed,
        series=True,
    )
    result["pairs_censored"] = censored
    result["games_failed_base"] = failed["base"]
    result["games_failed_variant"] = failed["variant"]
    result["failure_classes"] = {
        arm: dict(sorted(counts.items())) for arm, counts in failure_classes.items()
    }
    result["seeds"] = sorted(set(attempted_seeds))
    result["looks_planned"] = len(look_counts)
    result["looks_used"] = looks_used
    result["pairs_played"] = attempted
    if misseated:
        result["warnings"].append(
            f"{misseated} finished game(s) did not seat the compared deck at the tested seat"
        )
    blocker_reason, blocker_warnings = _censoring_issues(
        censored=censored,
        played=attempted,
        failed_base=failed["base"],
        failed_variant=failed["variant"],
        max_censored_share=max_censored_share,
    )
    if blocker_reason is not None:
        result["warnings"].extend(blocker_warnings)
        if result["pairs_completed"] > 0:
            result["status"] = "NOT_DECIDED"
            result["answer"] = None
            result["stop_reason"] = blocker_reason
    elif result["status"] == "DECIDED":
        result["stop_reason"] = "DECIDED_" + str(result["answer"])
    elif result["status"] == "NOT_DECIDED":
        result["stop_reason"] = "BUDGET_EXHAUSTED"
    result["execution"] = {
        "mode": "series",
        "executor": "studio-paired-comparison-1",
        **dict(execution or {}),
    }
    return result


def recorded_game_player(
    data_folder: str | Path,
    *,
    series_id: str,
    base_deck: RulesDeckInput,
    variant_deck: RulesDeckInput,
    opponents: Sequence[RulesDeckInput],
    paths_by_deck_id: Mapping[str, Path],
) -> PairPlayer:
    """A :data:`PairPlayer` that plays real recorded games on the Studio engine path.

    The table of a game is ``pod_decks`` of the engine lane: the contender sits in
    the tested seat, the opponents keep their order around it, so a pair differs
    only in the tested seat. Each game is one recorded game (``play_recorded_game``)
    and its exposure is read back from its log, exactly as the outcomes read logs.
    """
    from .play import play_recorded_game

    contenders = {"base": base_deck, "variant": variant_deck}

    def play(arm: str, seed: int, seat: int) -> PlayedGame:
        ordered = pod_decks(contenders[arm], opponents, seat + 1)
        paths = [paths_by_deck_id[deck.deck_id] for deck in ordered]
        game_id = f"{series_id}-{arm}-s{seed}-t{seat}"
        summary = play_recorded_game(data_folder, paths, seed=seed, game_id=game_id)
        if summary.get("status") != "finished":
            failure = summary.get("failure_class")
            return {
                "exposure": None,
                "failure_class": failure if isinstance(failure, str) else "Failed",
            }
        log = summary.get("log")
        exposure = game_exposures(log) if isinstance(log, str) else None
        if exposure is None:
            return {"exposure": None, "failure_class": "UnfinishedLog"}
        return {"exposure": exposure, "failure_class": None}

    return play


def format_comparison(result: PairedComparison) -> str:
    """Compact text view: the question, the answer, the counts and the provenance."""
    question = result["question"]
    lines = [
        f"{result['variant_deck_id']} vs {result['base_deck_id']}  "
        f"[{result['data_class']}]  status {result['status']}",
        f"question: is the difference greater than {question['threshold_pp']} pp?  "
        f"stop reason {result['stop_reason']}",
        f"pairs {result['pairs_completed']}  censored {result['pairs_censored']}  "
        f"unpaired base {result['unpaired_base']} / variant {result['unpaired_variant']}  "
        f"failed games base {result['games_failed_base']} / variant "
        f"{result['games_failed_variant']}  looks {result['looks_used']}/"
        f"{result['looks_planned']}",
    ]
    if result["difference_pp"] is not None:
        ci95 = result["difference_ci95_pp"]
        ci95_text = f"95% CI [{ci95[0]}, {ci95[1]}]" if ci95 is not None else "95% CI -"
        dci = result.get("decision_ci_pp")
        level = result.get("decision_level_pct")
        alpha_used = result.get("decision_alpha")
        decision_ci_text = (
            f"  {level:g}% decision CI (alpha {alpha_used}) [{dci[0]}, {dci[1]}]"
            if dci is not None and level is not None and alpha_used is not None
            else ""
        )
        lines.append(
            f"win rate base {_fmt_rate(result['base_rate'])}  variant "
            f"{_fmt_rate(result['variant_rate'])}  difference {result['difference_pp']} pp "
            f"{ci95_text}{decision_ci_text}  (discordant {result['variant_only_wins']} : "
            f"{result['baseline_only_wins']}, sign test p {result['sign_test_p_value']})"
        )
    lines.append(
        f"seeds {len(result['seeds_completed'])}  pods {len(result['pods'])}  "
        f"tested seats {result['tested_seats']}  engine "
        f"{', '.join(c[:10] for c in result['engine_commits']) or '-'}  pin "
        f"{result['engine_pin'][:10]}  pilots {', '.join(result['pilots']) or '-'}"
    )
    lines += [f"WARNING {warning}" for warning in result["warnings"]]
    return "\n".join(lines)


def _fmt_rate(rate: float | None) -> str:
    return "-" if rate is None else f"{rate:.3f}"


def comparison_games_folder(data_folder: str | Path) -> Path:
    """The folder the recorded games of a comparison series land in."""
    return games_folder(data_folder)
