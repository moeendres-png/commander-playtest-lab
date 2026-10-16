"""Paired comparisons keep a variant's unchanged cards in the baseline's library slots.

The engine builds each library in decklist order and shuffles it with the game
seed, so a variant that lists its cards in another order is dealt unrelated
hands. Aligning the variant to the baseline's slots keeps the paired games
identical until a changed card matters.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FullGameConformanceResult,
)
from commander_lab.engine.rules.full_game_batch import XmageFullGameBatchRunner
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonSpec,
    aggregate_comparison,
    align_to_baseline_slots,
    plan_comparison_cases,
)
from commander_lab.models import RulesDeckInput

XMAGE_COMMIT = "0" * 40


_FILLER = tuple(f"Filler {index}" for index in range(99))


def _deck(deck_id: str, mainboard: tuple[str, ...], index: int = 1) -> RulesDeckInput:
    """A legal 100-card deck: the given cards first, shared filler after them."""
    padded = (*mainboard, *_FILLER[: 99 - len(mainboard)])
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=padded,
        deck_hash=(f"{index:x}" * 64)[:64],
    )


def _resized(deck: RulesDeckInput, mainboard: tuple[str, ...]) -> RulesDeckInput:
    """The deck with another card count; alignment itself does not need 99 cards."""
    return deck.model_copy(update={"mainboard": mainboard})


def _aligned(baseline: tuple[str, ...], variant: tuple[str, ...]) -> tuple[str, ...]:
    deck, _ = align_to_baseline_slots(_deck("base", baseline), _deck("variant", variant, 2))
    return tuple(deck.mainboard[: len(variant)])


def test_a_swapped_card_takes_the_slot_of_the_card_it_replaces() -> None:
    # The variant file lists the new card first, as a sorted export would.
    assert _aligned(("A", "B", "C", "D"), ("X", "A", "B", "D")) == ("A", "B", "X", "D")


def test_several_swaps_fill_the_freed_slots_in_list_order() -> None:
    # C and D leave, Y and Z arrive (Y listed before Z): Y takes C's slot.
    assert _aligned(("A", "B", "C", "D", "E"), ("E", "Y", "A", "Z", "B")) == (
        "A",
        "B",
        "Y",
        "Z",
        "E",
    )


def test_a_basic_land_swap_replaces_one_copy_of_the_stack() -> None:
    baseline = ("Plains", "Plains", "Plains", "Island", "Sol Ring")
    variant = ("Plains", "Plains", "Island", "Island", "Sol Ring")
    # One Plains leaves (its first copy, all copies are alike) and one Island
    # arrives in that slot; every other card keeps its slot.
    assert _aligned(baseline, variant) == ("Island", "Plains", "Plains", "Island", "Sol Ring")


def test_a_larger_variant_appends_its_surplus_after_the_baseline_slots() -> None:
    deck, alignment = align_to_baseline_slots(
        _resized(_deck("base", ()), ("A", "B")), _resized(_deck("variant", (), 2), ("B", "A", "X"))
    )
    assert deck.mainboard == ("A", "B", "X")
    assert (alignment.swapped_slots, alignment.appended, alignment.dropped) == (0, 1, 0)


def test_a_smaller_variant_drops_the_removed_slot() -> None:
    deck, alignment = align_to_baseline_slots(
        _resized(_deck("base", ()), ("A", "B", "C")), _resized(_deck("variant", (), 2), ("C", "A"))
    )
    assert deck.mainboard == ("A", "C")
    assert (alignment.swapped_slots, alignment.appended, alignment.dropped) == (0, 0, 1)


def test_an_unchanged_variant_takes_the_baseline_order_and_nothing_else() -> None:
    deck, alignment = align_to_baseline_slots(
        _deck("base", ("A", "B", "C")), _deck("variant", ("C", "B", "A"), 2)
    )
    assert deck.mainboard == _deck("base", ("A", "B", "C")).mainboard
    assert (alignment.swapped_slots, alignment.appended, alignment.dropped) == (0, 0, 0)


@pytest.mark.parametrize(
    ("baseline", "variant"),
    [
        (("A", "B", "C", "D"), ("D", "Q", "A", "R")),
        (("Plains",) * 6 + ("A",), ("Plains",) * 4 + ("B", "B", "A")),
        (("A", "B"), ("X", "Y")),
        (("A", "B", "C"), ("Z", "B", "A")),
    ],
)
def test_alignment_never_changes_which_cards_the_variant_plays(
    baseline: tuple[str, ...], variant: tuple[str, ...]
) -> None:
    deck, _ = align_to_baseline_slots(_deck("base", baseline), _deck("variant", variant, 2))
    assert Counter(deck.mainboard) == Counter(_deck("variant", variant, 2).mainboard)


def test_alignment_keeps_the_variant_identity_and_everything_but_the_list_order() -> None:
    variant = _deck("variant", ("X", "A", "B", "D"), 2)
    aligned, _ = align_to_baseline_slots(_deck("base", ("A", "B", "C", "D")), variant)
    assert aligned.model_dump(exclude={"mainboard"}) == variant.model_dump(exclude={"mainboard"})


def _spec() -> DeckComparisonSpec:
    baseline = _deck("base", ("A", "B", "C", "D"), 1)
    variant = _deck("variant", ("X", "A", "B", "D"), 2)
    opponents = tuple(_deck(f"opp-{index}", ("Q", "R", "S", "T"), 3 + index) for index in range(3))
    return DeckComparisonSpec(
        comparison_id="cmp-slots",
        contenders=(baseline, variant),
        opponents=opponents,
        seeds=(1, 2),
        rotate_seats=False,
        xmage_commit=XMAGE_COMMIT,
    )


def test_planned_cases_seat_the_aligned_variant_and_leave_other_decks_alone() -> None:
    spec = _spec()
    cases = plan_comparison_cases(spec)
    assert len(cases) == 4
    for case in cases:
        tested = case.decks[0]
        if tested.deck_id == "variant":
            assert tested.mainboard[:4] == ("A", "B", "X", "D")
            assert tested.deck_hash == spec.contenders[1].deck_hash
        else:
            assert tested.mainboard[:4] == ("A", "B", "C", "D")
        assert [deck.mainboard[:4] for deck in case.decks[1:]] == [("Q", "R", "S", "T")] * 3
    # The spec itself is not rewritten.
    assert spec.contenders[1].mainboard[:4] == ("X", "A", "B", "D")


class _TranscriptRunner:
    """The variant plays the baseline's game on seeds 1-3 and another one on seed 4."""

    command = ("python", "-c", "pass")

    def run(self, *, scenario: FutureXmageScenario, decks: object, pilots: object) -> object:
        differs = scenario.candidate_id == "variant" and scenario.seed == 4
        digest = f"{scenario.seed:02x}" * 32 if not differs else "ff" * 32
        return FullGameConformanceResult(
            scenario=scenario,
            engine_version="1.4.61",
            xmage_commit=XMAGE_COMMIT,
            decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
            decision_count=100,
            terminal=True,
            winner_seats=(scenario.seat,) if differs else (scenario.seat % 4 + 1,),
            result_payload={
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                "seed": scenario.seed,
                "terminal": True,
                "turn_number": 9,
                "transcript": [],
            },
            semantic_transcript_sha256=digest,
            raw_result_sha256="b" * 64,
            shutdown_disposition="graceful_shutdown",
        )


def test_report_counts_games_the_change_never_touched_and_records_the_alignment(
    tmp_path: Path,
) -> None:
    spec = DeckComparisonSpec(
        comparison_id="cmp-identical",
        contenders=_spec().contenders,
        opponents=_spec().opponents,
        seeds=(1, 2, 3, 4),
        rotate_seats=False,
        xmage_commit=XMAGE_COMMIT,
    )
    report = XmageFullGameBatchRunner(_TranscriptRunner(), tmp_path).run(  # type: ignore[arg-type]
        plan_comparison_cases(spec)
    )
    comparison = aggregate_comparison(spec, report)
    paired = comparison.paired[0]
    assert paired.pairs_completed == 4
    assert paired.identical_pairs == 3
    assert paired.variant_only_wins == 1 and paired.baseline_only_wins == 0
    (alignment,) = comparison.slot_alignment
    assert alignment.deck_id == "variant"
    assert (alignment.swapped_slots, alignment.appended, alignment.dropped) == (1, 0, 0)
