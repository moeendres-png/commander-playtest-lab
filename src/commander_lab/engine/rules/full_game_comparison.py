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

import hashlib
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commander_lab.agents.card_knowledge import is_basic_land_name
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
# Two-sided 95% normal quantile for the paired-difference interval (#870).
# The wrong-reason control in tests/unit/test_comparison_precision.py patches
# this to 1.0; keep the name stable.
DIFFERENCE_Z95 = 1.96
# One-sided 80% normal quantile for the detectable difference (#870).
DIFFERENCE_Z80 = 0.8416
# A non-decided verdict counts as underpowered when the detectable difference
# is above this win-share fraction (#870).
UNDERPOWERED_ABOVE = 0.10
# Assumed per-pair standard deviation of win-share differences for *planning*
# (#873): before any games are played there is no sample sd, so the plan
# assumes one. Per pair, d = variant_share - baseline_share is in {-1, 0, +1};
# with each contender winning a 4P game independently at p = 0.25,
# Var(d) = 2*p*(1-p) = 0.375, sd ~= 0.61. 0.63 is the slightly conservative
# planning value (it is also the example sd in #870's tests).
PLANNED_PAIR_SD = 0.63


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


class SwapSpecError(ValueError):
    """A ``--swap`` text that cannot be applied to the baseline deck."""


def parse_swaps(text: str) -> tuple[tuple[str, str], ...]:
    """``"Out=>In"`` or several swaps of one variant, ``"A=>B;C=>D"``.

    Card names contain commas and slashes but never ``;`` or ``=>``.
    """
    swaps: list[tuple[str, str]] = []
    for part in text.split(";"):
        if not part.strip():
            continue
        out_name, arrow, in_name = part.partition("=>")
        if not arrow or not out_name.strip() or not in_name.strip() or "=>" in in_name:
            raise SwapSpecError(f"swap must read 'Out Card=>In Card', got {part.strip()!r}")
        swaps.append((out_name.strip(), in_name.strip()))
    if not swaps:
        raise SwapSpecError("swap text names no card")
    return tuple(swaps)


def apply_swaps(deck: RulesDeckInput, swaps: Sequence[tuple[str, str]]) -> RulesDeckInput:
    """The deck with each card replaced by its partner, in the same library slot.

    A card name matches exactly, or ignoring case when that is unambiguous. The
    first copy in list order is replaced, so one swap changes one copy. The
    commanders are not part of the mainboard and cannot be swapped here. The
    card coming in must not already be in the deck (basic lands excepted: a
    singleton deck has one copy of anything else) and must not be a commander.
    Of several swaps in one variant, the paired games keep the unchanged
    cards' slots; which freed slot an incoming card takes is fixed by
    :func:`align_to_baseline_slots` when the games are planned.
    """
    commanders = {name.casefold() for name in deck.commander_names}
    mainboard = list(deck.mainboard)
    for out_name, in_name in swaps:
        if in_name.casefold() == out_name.casefold():
            raise SwapSpecError(f"swap exchanges a card for itself: {out_name}")
        if in_name.casefold() in commanders:
            raise SwapSpecError(f"swap-in card is a commander of {deck.deck_id}: {in_name}")
        if not is_basic_land_name(in_name) and any(
            card.casefold() == in_name.casefold() for card in mainboard
        ):
            raise SwapSpecError(
                f"swap-in card is already in the mainboard of {deck.deck_id}: {in_name}"
            )
        matches = [index for index, card in enumerate(mainboard) if card == out_name]
        if not matches:
            folded = {card for card in mainboard if card.casefold() == out_name.casefold()}
            if len(folded) > 1:
                raise SwapSpecError(
                    f"swap-out card is ambiguous in {deck.deck_id}: {out_name} (matches "
                    f"{', '.join(sorted(folded))}); use the exact spelling"
                )
            if folded:
                matches = [
                    index for index, card in enumerate(mainboard) if card == next(iter(folded))
                ]
        if not matches:
            raise SwapSpecError(
                f"swap-out card is not in the mainboard of {deck.deck_id}: {out_name}"
            )
        mainboard[matches[0]] = in_name
    return deck.model_copy(update={"mainboard": tuple(mainboard), "deck_hash": None})


class SlotAlignment(_StrictModel):
    """How a variant's library order was lined up with the baseline's.

    ``played_mainboard_sha256`` is the SHA-256 of the mainboard in the order the
    engine received it: the variant's ``deck_hash`` describes its own file, but
    the games were played from this list.
    """

    deck_id: str
    baseline_deck_id: str
    played_mainboard_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    swapped_slots: int = Field(ge=0)
    appended: int = Field(ge=0)
    dropped: int = Field(ge=0)


def align_to_baseline_slots(
    baseline: RulesDeckInput, variant: RulesDeckInput
) -> tuple[RulesDeckInput, SlotAlignment]:
    """Seat the variant's changed cards in the baseline's library slots.

    The engine builds the library in decklist order and shuffles it with the
    game seed, so two decks that list the same cards in the same slots deal the
    same hands and draws until a changed card is reached. A variant whose list
    is merely sorted differently, or which puts a new card in another place,
    shifts every later slot and makes the paired games unrelated from the first
    shuffle on. This keeps every unchanged card in its baseline slot, moves the
    variant's added cards into the slots of the removed cards (added cards in
    name order, slots in baseline order) and appends any surplus. The result
    depends only on the two card multisets, never on how the variant file lists
    its cards. The multiset of cards is exactly the variant's, so the deck is
    the same deck; only its list order changes.
    """
    baseline_cards = list(baseline.mainboard)
    removed = Counter(baseline_cards) - Counter(variant.mainboard)
    added_budget = Counter(variant.mainboard) - Counter(baseline_cards)
    added = sorted(added_budget.elements(), key=lambda card: (card.casefold(), card))
    queue = iter(added)
    pending = next(queue, None)
    placed: list[str] = []
    swapped = dropped = 0
    for card in baseline_cards:
        if removed[card] > 0:
            removed[card] -= 1
            if pending is not None:
                placed.append(pending)
                pending = next(queue, None)
                swapped += 1
            else:
                dropped += 1
        else:
            placed.append(card)
    surplus: list[str] = [] if pending is None else [pending, *queue]
    placed.extend(surplus)
    if Counter(placed) != Counter(variant.mainboard):
        raise ValueError("slot alignment changed the variant's cards")
    aligned = variant.model_copy(update={"mainboard": tuple(placed)})
    return aligned, SlotAlignment(
        deck_id=variant.deck_id,
        baseline_deck_id=baseline.deck_id,
        played_mainboard_sha256=hashlib.sha256("\n".join(placed).encode()).hexdigest(),
        swapped_slots=swapped,
        appended=len(surplus),
        dropped=dropped,
    )


def aligned_contenders(
    spec: DeckComparisonSpec,
) -> tuple[tuple[RulesDeckInput, ...], tuple[SlotAlignment, ...]]:
    """The contenders as they are played: variants slot-aligned to the baseline."""
    baseline = spec.contenders[0]
    played = [baseline]
    alignments: list[SlotAlignment] = []
    for variant in spec.contenders[1:]:
        aligned, alignment = align_to_baseline_slots(baseline, variant)
        played.append(aligned)
        alignments.append(alignment)
    return tuple(played), tuple(alignments)


def case_id(contender_id: str, seed: int, tested_seat: int) -> str:
    return f"{contender_id}|seed={seed}|seat={tested_seat}"


def plan_comparison_cases(spec: DeckComparisonSpec) -> tuple[FullGameBatchCase, ...]:
    """Every (contender, seed, tested seat) game, grouped pod by pod.

    Grouping by pod (seed, seat) with all contenders next to each other means a
    partly finished batch already holds complete pairs. Variants are played with
    their cards in the baseline's library slots (:func:`align_to_baseline_slots`),
    so paired games stay identical until a changed card matters.
    """
    cases: list[FullGameBatchCase] = []
    played, _ = aligned_contenders(spec)
    for seed in spec.seeds:
        for seat in spec.tested_seats:
            for contender in played:
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


class DifferenceInterval(_StrictModel):
    """95% normal interval of a paired win-share difference.

    Unlike :class:`WinInterval` this is a difference of two win shares, so
    ``low`` and ``high`` may be negative and are not limited to 0..1.
    """

    low: float
    high: float


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


def _paired_difference_stats(
    differences: Sequence[float],
) -> tuple[DifferenceInterval | None, float | None]:
    """95% interval and 80%-power detectable difference of the mean difference.

    Normal approximation on the sample standard deviation of the per-pair
    differences ``d_i`` (variant share minus baseline share): the interval is
    ``mean(d) +/- 1.96 * sd / sqrt(n)`` and the detectable difference
    ``(1.96 + 0.8416) * sd / sqrt(n)`` (#870). Returns ``(None, None)`` for
    fewer than 2 pairs or zero spread: with no variation the run saw nothing
    to put an interval on.
    """
    n = len(differences)
    if n < 2:
        return None, None
    mean = sum(differences) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in differences) / (n - 1))
    if sd == 0.0:
        return None, None
    half_width = DIFFERENCE_Z95 * sd / math.sqrt(n)
    return (
        DifferenceInterval(low=mean - half_width, high=mean + half_width),
        (DIFFERENCE_Z95 + DIFFERENCE_Z80) * sd / math.sqrt(n),
    )


def planned_detectable_difference(pairs: int, sd: float = PLANNED_PAIR_SD) -> float:
    """Win-share difference ``pairs`` planned pairs can detect at 80% power (#873).

    The #870 detectable-difference arithmetic ``(Z95 + Z80) * sd / sqrt(n)``
    with the assumed per-pair sd for planning; no games have been played yet,
    so there is no sample sd to use.
    """
    if pairs < 1:
        raise ValueError("pairs must be positive")
    return (DIFFERENCE_Z95 + DIFFERENCE_Z80) * sd / math.sqrt(pairs)


def pairs_needed(difference: float, sd: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Pairs needed to detect a win-share ``difference`` at the given power (#870).

    Normal approximation: ``ceil(((1.96 + 0.8416) * sd / difference) ** 2)``
    from the per-pair standard deviation ``sd``. ``alpha`` and ``power``
    document the 95%/80% levels the constants encode; other levels would need
    other quantiles.
    """
    if difference <= 0.0:
        raise ValueError("difference must be positive")
    if sd < 0.0:
        raise ValueError("sd must be non-negative")
    return math.ceil(((DIFFERENCE_Z95 + DIFFERENCE_Z80) * sd / difference) ** 2)


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
    # Mean finishing-order score over completed games with a score (#875).
    # None when no game had one (results without lost_on_turn).
    mean_finishing_score: float | None = None


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
    # Completed pairs whose two games have the same semantic transcript: the
    # changed cards never mattered there. They are ties, so they carry no
    # information for the verdict; this count shows how often the change was felt.
    identical_pairs: int = Field(default=0, ge=0)
    sign_test_p_value: float = Field(ge=0.0, le=1.0)
    verdict: Literal["VARIANT_BETTER", "BASELINE_BETTER", "NO_CLEAR_DIFFERENCE", "INSUFFICIENT"]
    # 95% normal interval of the mean paired win-share difference (#870).
    # The pairs are treated as independent although the seat rotations of one
    # seed share a shuffle, so the interval is slightly narrow; the sign-test
    # verdict is unchanged. None for fewer than 2 pairs or zero spread.
    win_share_difference_interval_95: DifferenceInterval | None = None
    # Smallest win-share difference this run could have detected at 80% power
    # (#870). None when the interval is None.
    detectable_difference_80pct_power: float | None = None
    # True exactly when the verdict is NO_CLEAR_DIFFERENCE or INSUFFICIENT and
    # the detectable difference is above UNDERPOWERED_ABOVE (#870): the run
    # was too small to rule out a meaningful edge, so the verdict is not
    # evidence of no effect.
    underpowered: bool = False
    # Finishing-order outcome (#875): paired mean difference of the per-game
    # finishing scores, with a 95% interval from the #870 arithmetic. This is
    # exploratory: win share stays the verdict, ranks within a pod are not
    # independent of each other, and the pair is the unit. None (and zero
    # pairs) when a game in the pair has no score, e.g. results recorded
    # before #874 added lost_on_turn.
    placement_difference: float | None = None
    placement_difference_interval_95: DifferenceInterval | None = None
    placement_pairs: int = Field(default=0, ge=0)


class DeckComparisonReport(_StrictModel):
    schema_version: Literal["xmage-full-game-deck-comparison-1.0.0"] = COMPARISON_SCHEMA_VERSION
    comparison_id: str
    player_count: int
    seeds: tuple[int, ...]
    tested_seats: tuple[int, ...]
    contenders: tuple[ContenderSummary, ...]
    paired: tuple[PairedVariantResult, ...]
    slot_alignment: tuple[SlotAlignment, ...] = ()
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


def finishing_scores(
    outcomes: Sequence[Mapping[str, object]], player_count: int
) -> dict[int, float | None]:
    """Finishing-order score per seat from one game's outcomes (#875).

    Rank rules: winner(s) rank first; players who lost are ranked by
    ``lost_on_turn`` (a later loss is better); equal turns share the average
    rank; players who neither won nor lost share the averaged ranks between
    the winners and the losers. Score ``s = (N - rank) / (N - 1)``: 1.0 for a
    sole winner, 0.0 for the first player out.

    Returns ``None`` for every seat when any lost seat has ``lost_on_turn``
    null, i.e. results recorded before #874 added the field. Seats are keyed
    exactly as they appear in ``outcomes``; the bridge records them 0-based
    (``winner_seats`` in ``full_game.py`` adds 1 for the same reason).
    """
    rows: list[tuple[int, bool, bool, object]] = []
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            continue
        seat = outcome.get("seat")
        if not isinstance(seat, int) or isinstance(seat, bool):
            continue
        rows.append(
            (
                seat,
                outcome.get("won") is True,
                outcome.get("lost") is True,
                outcome.get("lost_on_turn"),
            )
        )
    if any(
        lost and (not isinstance(turn, int) or isinstance(turn, bool)) for _, _, lost, turn in rows
    ):
        return {seat: None for seat, _, _, _ in rows}
    if player_count < 2:
        return {seat: None for seat, _, _, _ in rows}
    winners = [seat for seat, won, _, _ in rows if won]
    middle = [seat for seat, won, lost, _ in rows if not won and not lost]
    losers = [
        (seat, turn)
        for seat, won, lost, turn in rows
        if lost and not won and isinstance(turn, int) and not isinstance(turn, bool)
    ]
    ranks: dict[int, float] = {}
    w, m = len(winners), len(middle)
    if w:
        average = (1 + w) / 2
        for seat in winners:
            ranks[seat] = average
    if m:
        average = w + (1 + m) / 2
        for seat in middle:
            ranks[seat] = average
    # Losers, latest loss first; equal turns share the average rank.
    ordered = sorted(losers, key=lambda item: item[1], reverse=True)
    rank = w + m + 1
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        average = rank + (j - i - 1) / 2
        for k in range(i, j):
            ranks[ordered[k][0]] = average
        rank += j - i
        i = j
    n = player_count
    return {seat: (n - rank) / (n - 1) for seat, rank in ranks.items()}


def _tested_placement(
    record_result: FullGameConformanceResult, player_count: int, tested_seat: int
) -> float | None:
    """Finishing-order score of the 1-based tested seat, or None.

    The bridge records outcome seats 0-based; ``winner_seats`` adds 1 for the
    same reason (see ``full_game.py``).
    """
    raw = record_result.result_payload.get("outcomes")
    if not isinstance(raw, list):
        return None
    return finishing_scores(raw, player_count).get(tested_seat - 1)


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
    # placement[(contender, seed, seat)] = finishing-order score of the tested
    # seat in that game, or None when the game has no score (#875).
    placement: dict[tuple[str, int, int], float | None] = {}
    transcript_of: dict[tuple[str, int, int], str] = {}
    summaries: list[ContenderSummary] = []
    for contender in spec.contenders:
        planned = completed = failed = no_winner = 0
        wins = 0.0
        turns: list[int] = []
        decisions: list[int] = []
        failures: dict[str, int] = {}
        place_scores: list[float] = []
        for seed in spec.seeds:
            for seat in spec.tested_seats:
                planned += 1
                key = (contender.deck_id, seed, seat)
                record = by_case.get(case_id(*key))
                if record is None or record.status != "completed" or record.result is None:
                    outcome[key] = None
                    placement[key] = None
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
                place_score = _tested_placement(record.result, spec.player_count, seat)
                placement[key] = place_score
                if place_score is not None:
                    place_scores.append(place_score)
                transcript_of[key] = record.result.semantic_transcript_sha256
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
                mean_finishing_score=(sum(place_scores) / len(place_scores))
                if place_scores
                else None,
            )
        )

    baseline = spec.contenders[0].deck_id
    paired: list[PairedVariantResult] = []
    for variant in spec.contenders[1:]:
        pairs: list[tuple[float, float]] = []
        place_pairs: list[tuple[float, float]] = []
        censored = identical = 0
        for seed in spec.seeds:
            for seat in spec.tested_seats:
                left = outcome[(baseline, seed, seat)]
                right = outcome[(variant.deck_id, seed, seat)]
                if left is None or right is None:
                    censored += 1
                    continue
                pairs.append((left, right))
                identical += int(
                    transcript_of[(baseline, seed, seat)]
                    == transcript_of[(variant.deck_id, seed, seat)]
                )
                left_place = placement[(baseline, seed, seat)]
                right_place = placement[(variant.deck_id, seed, seat)]
                if left_place is not None and right_place is not None:
                    place_pairs.append((left_place, right_place))
        variant_only = sum(1 for left, right in pairs if right > left)
        baseline_only = sum(1 for left, right in pairs if left > right)
        p_value = sign_test_p_value(variant_only, baseline_only)
        # Per-pair differences: identical pairs and shared wins are 0 or
        # fractional, and they narrow the interval like any other pair (#870).
        differences = [right - left for left, right in pairs]
        interval_95, detectable = _paired_difference_stats(differences)
        # Finishing-order differences on the same pairs (#875): a pair joins
        # only when both games have a score.
        place_differences = [right - left for left, right in place_pairs]
        place_interval_95, _ = _paired_difference_stats(place_differences)
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
        underpowered = (
            verdict in ("NO_CLEAR_DIFFERENCE", "INSUFFICIENT")
            and detectable is not None
            and detectable > UNDERPOWERED_ABOVE
        )
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
                identical_pairs=identical,
                sign_test_p_value=p_value,
                verdict=verdict,
                win_share_difference_interval_95=interval_95,
                detectable_difference_80pct_power=detectable,
                underpowered=underpowered,
                placement_difference=(sum(place_differences) / len(place_differences))
                if place_differences
                else None,
                placement_difference_interval_95=place_interval_95,
                placement_pairs=len(place_pairs),
            )
        )

    return DeckComparisonReport(
        comparison_id=spec.comparison_id,
        player_count=spec.player_count,
        seeds=spec.seeds,
        tested_seats=spec.tested_seats,
        contenders=tuple(summaries),
        paired=tuple(paired),
        slot_alignment=aligned_contenders(spec)[1],
        significance_level=significance_level,
    )


__all__ = [
    "COMPARISON_EVIDENCE_CLASS",
    "DIFFERENCE_Z80",
    "DIFFERENCE_Z95",
    "UNDERPOWERED_ABOVE",
    "ContenderSummary",
    "DeckComparisonReport",
    "DeckComparisonSpec",
    "DifferenceInterval",
    "PairedVariantResult",
    "SlotAlignment",
    "SwapSpecError",
    "WinInterval",
    "aggregate_comparison",
    "align_to_baseline_slots",
    "aligned_contenders",
    "apply_swaps",
    "case_id",
    "finishing_scores",
    "pairs_needed",
    "parse_swaps",
    "plan_comparison_cases",
    "pod_decks",
    "sequential_look_alpha",
    "sequential_look_decided",
    "sequential_looks_planned",
    "sequential_stop_now",
    "sign_test_p_value",
    "wilson_interval",
]
