"""Paired deck comparison on real XMage full games (#731).

A comparison asks one practical deck-building question: does a variant deck do
better than a baseline deck against the same opponents? Every contender (the
baseline and each variant) plays the *same* pods: the same seeds, the same
opponents and the same seat rotation. Only the deck in the tested seat differs,
so the comparison is paired (common random numbers) and seat or starting-player
advantages cancel out instead of masquerading as deck strength.

The batch runner plays the games; this module only plans cases and aggregates
the records it gets back. A failed game is censored: it is reported in its own
count and never counted as a loss or a win. A game is a pair member only when
both contenders completed it.

Results are exploratory full-game evidence about this pilot policy on this
engine pin. They are not official campaign results, not holdout evidence and
not Structural confirmatory evidence, and nothing here mutates a deck.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)

from .full_game import FullGameConformanceResult, FullGamePilotBinding
from .full_game_batch import FullGameBatchCase, FullGameBatchReport

COMPARISON_SCHEMA_VERSION: Literal["xmage-full-game-deck-comparison-1.0.0"] = (
    "xmage-full-game-deck-comparison-1.0.0"
)
COMPARISON_EVIDENCE_CLASS: Literal["exploratory_xmage_full_game"] = "exploratory_xmage_full_game"
DEFAULT_PILOT_IDENTITY = "GenericCommanderPilot"
DEFAULT_PILOT_VERSION = "1.0.0"
DEFAULT_DECISION_POLICY_VERSION = "xmage-full-game-policy-1.0.0"
DEFAULT_BRIDGE_VERSION = "xmage-engine-bridge-0.1.0-SNAPSHOT"
# Two-sided 95% normal quantile for the Wilson interval.
_Z95 = 1.959963984540054


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeckComparisonSpec(_StrictModel):
    """What to compare and under which pods.

    ``contenders[0]`` is the baseline; every other contender is a variant that
    is compared against it. ``opponents`` fill the other seats of every pod, so
    a pod has ``len(opponents) + 1`` players.
    """

    comparison_id: str = Field(min_length=1)
    contenders: tuple[RulesDeckInput, ...] = Field(min_length=2)
    opponents: tuple[RulesDeckInput, ...] = Field(min_length=1, max_length=5)
    seeds: tuple[int, ...] = Field(min_length=1)
    rotate_seats: bool = True
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    bridge_version: str = DEFAULT_BRIDGE_VERSION
    pilot_identity: str = DEFAULT_PILOT_IDENTITY
    pilot_version: str = DEFAULT_PILOT_VERSION
    decision_policy_version: str = DEFAULT_DECISION_POLICY_VERSION
    strategy: str = "generic"

    @model_validator(mode="after")
    def coherent(self) -> DeckComparisonSpec:
        contender_ids = [deck.deck_id for deck in self.contenders]
        opponent_ids = [deck.deck_id for deck in self.opponents]
        if len(set(contender_ids)) != len(contender_ids):
            raise ValueError("contenders need distinct deck ids")
        if len(set(opponent_ids)) != len(opponent_ids):
            raise ValueError("opponents need distinct deck ids")
        if set(contender_ids) & set(opponent_ids):
            raise ValueError("a contender cannot also be an opponent")
        if any(deck.deck_hash is None for deck in (*self.contenders, *self.opponents)):
            raise ValueError("every comparison deck needs a deck_hash")
        if len(set(self.seeds)) != len(self.seeds) or min(self.seeds) < 0:
            raise ValueError("seeds must be distinct non-negative integers")
        return self

    @property
    def player_count(self) -> int:
        return len(self.opponents) + 1

    @property
    def tested_seats(self) -> tuple[int, ...]:
        return tuple(range(1, self.player_count + 1)) if self.rotate_seats else (1,)

    @property
    def pod_count(self) -> int:
        return len(self.seeds) * len(self.tested_seats)


def _binding(seat: int, deck: RulesDeckInput, spec: DeckComparisonSpec) -> FullGamePilotBinding:
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck.deck_id,
        strategy=spec.strategy,
        commander_names=deck.commander_names,
        config=PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        pilot_identity=spec.pilot_identity,
        pilot_version=spec.pilot_version,
        decision_policy_version=spec.decision_policy_version,
    )


def pod_decks(
    contender: RulesDeckInput, opponents: Sequence[RulesDeckInput], tested_seat: int
) -> tuple[RulesDeckInput, ...]:
    """Seat-ordered decks of one pod: the contender sits in ``tested_seat``.

    Opponents keep their relative order and are rotated with the contender, so
    every opponent also visits every other seat across the rotation and a pod
    for seat k differs between contenders only in the tested seat.
    """
    count = len(opponents) + 1
    if not 1 <= tested_seat <= count:
        raise ValueError("tested seat outside the pod")
    order: list[RulesDeckInput] = [contender, *opponents]
    shift = tested_seat - 1
    return tuple(order[(index - shift) % count] for index in range(count))


def case_id(contender_id: str, seed: int, tested_seat: int) -> str:
    return f"{contender_id}|seed={seed}|seat={tested_seat}"


def plan_comparison_cases(spec: DeckComparisonSpec) -> tuple[FullGameBatchCase, ...]:
    """Every (contender, seed, tested seat) game, grouped pod by pod.

    Grouping by pod (seed, seat) with all contenders next to each other means a
    partly finished batch already holds complete pairs.
    """
    cases: list[FullGameBatchCase] = []
    for seed in spec.seeds:
        for seat in spec.tested_seats:
            for contender in spec.contenders:
                decks = pod_decks(contender, spec.opponents, seat)
                if contender.deck_hash is None:
                    raise ValueError("full-game comparison contender has no deck hash")
                scenario = FutureXmageScenario(
                    candidate_id=contender.deck_id,
                    deck_hash=contender.deck_hash,
                    opponent_deck_ids=tuple(
                        deck.deck_id for index, deck in enumerate(decks, start=1) if index != seat
                    ),
                    player_count=spec.player_count,
                    seat=seat,
                    scenario_id=spec.comparison_id,
                    seed=seed,
                    xmage_commit=spec.xmage_commit,
                    bridge_version=spec.bridge_version,
                    pilot_identity=spec.pilot_identity,
                    pilot_version=spec.pilot_version,
                    decision_policy_version=spec.decision_policy_version,
                )
                cases.append(
                    FullGameBatchCase(
                        case_id=case_id(contender.deck_id, seed, seat),
                        scenario=scenario,
                        decks=decks,
                        pilots=tuple(
                            _binding(index, deck, spec) for index, deck in enumerate(decks, start=1)
                        ),
                    )
                )
    return tuple(cases)


class WinInterval(_StrictModel):
    low: float = Field(ge=0.0, le=1.0)
    high: float = Field(ge=0.0, le=1.0)


def wilson_interval(successes: float, trials: int, z: float = _Z95) -> WinInterval:
    """Wilson score interval; a shared win counts fractionally."""
    if trials <= 0:
        return WinInterval(low=0.0, high=1.0)
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return WinInterval(low=max(0.0, centre - half), high=min(1.0, centre + half))


def sign_test_p_value(variant_only: int, baseline_only: int) -> float:
    """Exact two-sided binomial sign test on the discordant pairs."""
    n = variant_only + baseline_only
    if n == 0:
        return 1.0
    k = min(variant_only, baseline_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / float(2**n)
    return min(1.0, 2 * tail)


def sequential_looks_planned(seed_count: int, look_every: int) -> int:
    """Planned interim looks ``L = ceil(seed_count / look_every)`` (#832)."""
    if seed_count < 1:
        raise ValueError("seed_count must be at least 1")
    if look_every < 1:
        raise ValueError("look_every must be at least 1")
    return -(-seed_count // look_every)


def sequential_look_alpha(significance_level: float, looks_planned: int) -> float:
    """Per-look significance threshold for a sequential comparison (#832).

    With ``looks_planned`` interim looks, a look may declare VARIANT_BETTER or
    BASELINE_BETTER only when the sign-test p-value is below
    ``significance_level / looks_planned``. This Bonferroni split is simple and
    valid: it keeps the overall Type I error at most ``significance_level``.
    The final look uses the same threshold.
    """
    if not 0.0 < significance_level < 1.0:
        raise ValueError("significance_level must be within (0, 1)")
    if looks_planned < 1:
        raise ValueError("looks_planned must be at least 1")
    return significance_level / looks_planned


def sequential_look_decided(paired: PairedVariantResult) -> bool:
    """Whether one variant's interim result stops the sequential run (#832).

    ``paired`` must come from an aggregation at the per-look alpha (see
    :func:`sequential_look_alpha`): only a decided verdict, VARIANT_BETTER or
    BASELINE_BETTER, stops the run. NO_CLEAR_DIFFERENCE and INSUFFICIENT never
    stop it; more seeds might still decide the comparison.
    """
    return paired.verdict in ("VARIANT_BETTER", "BASELINE_BETTER")


def sequential_stop_now(paired: Sequence[PairedVariantResult]) -> bool:
    """Stop once every variant has a decided interim verdict (#832)."""
    return bool(paired) and all(sequential_look_decided(result) for result in paired)


class ContenderSummary(_StrictModel):
    deck_id: str
    games_planned: int = Field(ge=0)
    games_completed: int = Field(ge=0)
    games_failed: int = Field(ge=0)
    wins: float = Field(ge=0.0)
    games_without_winner: int = Field(ge=0)
    win_share: float | None
    win_share_interval_95: WinInterval
    mean_turns: float | None
    mean_decisions: float | None
    failure_classes: dict[str, int]


class PairedVariantResult(_StrictModel):
    variant_deck_id: str
    baseline_deck_id: str
    pairs_completed: int = Field(ge=0)
    pairs_censored: int = Field(ge=0)
    variant_win_share: float | None
    baseline_win_share: float | None
    win_share_difference: float | None
    variant_only_wins: int = Field(ge=0)
    baseline_only_wins: int = Field(ge=0)
    sign_test_p_value: float = Field(ge=0.0, le=1.0)
    verdict: Literal["VARIANT_BETTER", "BASELINE_BETTER", "NO_CLEAR_DIFFERENCE", "INSUFFICIENT"]


class DeckComparisonReport(_StrictModel):
    schema_version: Literal["xmage-full-game-deck-comparison-1.0.0"] = COMPARISON_SCHEMA_VERSION
    comparison_id: str
    player_count: int
    seeds: tuple[int, ...]
    tested_seats: tuple[int, ...]
    contenders: tuple[ContenderSummary, ...]
    paired: tuple[PairedVariantResult, ...]
    significance_level: float
    evidence_class: Literal["exploratory_xmage_full_game"] = COMPARISON_EVIDENCE_CLASS
    rules_authority: Literal["xmage"] = "xmage"
    official_campaign_eligible: Literal[False] = False
    holdout_consumed: Literal[False] = False
    structural_decision_authority: Literal[False] = False
    canonical_data_mutated: Literal[False] = False
    truth_boundary: str = (
        "Paired real XMage full games under the Commander Lab pilot policy; "
        "failed games are censored, never losses. Exploratory deck-building "
        "evidence for this pilot and engine pin only."
    )


def _tested_outcome(record_result: FullGameConformanceResult, seat: int) -> tuple[float, bool]:
    winners = record_result.winner_seats
    if not winners:
        return 0.0, True
    return (1.0 / len(winners) if seat in winners else 0.0), False


def aggregate_comparison(
    spec: DeckComparisonSpec,
    report: FullGameBatchReport,
    *,
    significance_level: float = 0.05,
    max_censored_fraction: float = 0.2,
) -> DeckComparisonReport:
    """Turn batch records into per-contender and paired variant results.

    A variant whose pods were censored (a game of either contender failed) in
    more than ``max_censored_fraction`` of cases gets no verdict.
    """
    if not 0.0 < significance_level < 1.0:
        raise ValueError("significance_level must be within (0, 1)")
    by_case = {record.case_id: record for record in report.records}
    # outcome[(contender, seed, seat)] = win share in that game, or None if censored.
    outcome: dict[tuple[str, int, int], float | None] = {}
    summaries: list[ContenderSummary] = []
    for contender in spec.contenders:
        planned = completed = failed = no_winner = 0
        wins = 0.0
        turns: list[int] = []
        decisions: list[int] = []
        failures: dict[str, int] = {}
        for seed in spec.seeds:
            for seat in spec.tested_seats:
                planned += 1
                key = (contender.deck_id, seed, seat)
                record = by_case.get(case_id(*key))
                if record is None or record.status != "completed" or record.result is None:
                    outcome[key] = None
                    if record is not None:
                        failed += 1
                        name = record.failure_class.value if record.failure_class else "unknown"
                        failures[name] = failures.get(name, 0) + 1
                    continue
                completed += 1
                share, without_winner = _tested_outcome(record.result, seat)
                no_winner += int(without_winner)
                wins += share
                outcome[key] = share
                turn = record.result.result_payload.get("turn_number")
                if isinstance(turn, int) and not isinstance(turn, bool):
                    turns.append(turn)
                decisions.append(record.result.decision_count)
        summaries.append(
            ContenderSummary(
                deck_id=contender.deck_id,
                games_planned=planned,
                games_completed=completed,
                games_failed=failed,
                wins=wins,
                games_without_winner=no_winner,
                win_share=(wins / completed) if completed else None,
                win_share_interval_95=wilson_interval(wins, completed),
                mean_turns=(sum(turns) / len(turns)) if turns else None,
                mean_decisions=(sum(decisions) / len(decisions)) if decisions else None,
                failure_classes=dict(sorted(failures.items())),
            )
        )

    baseline = spec.contenders[0].deck_id
    paired: list[PairedVariantResult] = []
    for variant in spec.contenders[1:]:
        pairs: list[tuple[float, float]] = []
        censored = 0
        for seed in spec.seeds:
            for seat in spec.tested_seats:
                left = outcome[(baseline, seed, seat)]
                right = outcome[(variant.deck_id, seed, seat)]
                if left is None or right is None:
                    censored += 1
                    continue
                pairs.append((left, right))
        variant_only = sum(1 for left, right in pairs if right > left)
        baseline_only = sum(1 for left, right in pairs if left > right)
        p_value = sign_test_p_value(variant_only, baseline_only)
        if not pairs:
            verdict: Literal[
                "VARIANT_BETTER", "BASELINE_BETTER", "NO_CLEAR_DIFFERENCE", "INSUFFICIENT"
            ] = "INSUFFICIENT"
            variant_share = baseline_share = difference = None
        else:
            variant_share = sum(right for _, right in pairs) / len(pairs)
            baseline_share = sum(left for left, _ in pairs) / len(pairs)
            difference = variant_share - baseline_share
            if censored > max_censored_fraction * (len(pairs) + censored):
                # Too many failed games: failures that depend on the deck
                # (long games hitting the decision cap) would bias the pairs.
                verdict = "INSUFFICIENT"
            elif p_value < significance_level and variant_only > baseline_only:
                verdict = "VARIANT_BETTER"
            elif p_value < significance_level and baseline_only > variant_only:
                verdict = "BASELINE_BETTER"
            else:
                verdict = "NO_CLEAR_DIFFERENCE"
        paired.append(
            PairedVariantResult(
                variant_deck_id=variant.deck_id,
                baseline_deck_id=baseline,
                pairs_completed=len(pairs),
                pairs_censored=censored,
                variant_win_share=variant_share,
                baseline_win_share=baseline_share,
                win_share_difference=difference,
                variant_only_wins=variant_only,
                baseline_only_wins=baseline_only,
                sign_test_p_value=p_value,
                verdict=verdict,
            )
        )

    return DeckComparisonReport(
        comparison_id=spec.comparison_id,
        player_count=spec.player_count,
        seeds=spec.seeds,
        tested_seats=spec.tested_seats,
        contenders=tuple(summaries),
        paired=tuple(paired),
        significance_level=significance_level,
    )


__all__ = [
    "COMPARISON_EVIDENCE_CLASS",
    "ContenderSummary",
    "DeckComparisonReport",
    "DeckComparisonSpec",
    "PairedVariantResult",
    "WinInterval",
    "aggregate_comparison",
    "case_id",
    "plan_comparison_cases",
    "pod_decks",
    "sequential_look_alpha",
    "sequential_look_decided",
    "sequential_looks_planned",
    "sequential_stop_now",
    "sign_test_p_value",
    "wilson_interval",
]
