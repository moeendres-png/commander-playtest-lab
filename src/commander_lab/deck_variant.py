"""Deck-variant prefilter: compare a variant against a baseline before real games (#852).

``compare_variant`` is a deterministic, side-effect-free comparison: card diff,
readiness, mana deltas, commander castability, and a go/no-go verdict. The card
data it reads (project manifest, XMage card facts, pilot knowledge) is
versioned repository data, so identical arguments always produce identical
output.

The verdict is a *filter* (cheap screening before anyone spends hours of full
games on a variant), never a ranking of variants.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from commander_lab.deck_profile import structural_profile
from commander_lab.deck_readiness import CardReadinessStatus, check_deck
from commander_lab.mana_analysis import DEFAULT_CASTABILITY_SEED, ManaAnalyzer
from commander_lab.models import RulesDeckInput

ROOT = Path(__file__).resolve().parents[2]

#: Commander-cast turns the prefilter watches (probability and expected turn).
PREFILTER_TURNS: tuple[int, ...] = (3, 4, 5, 6)

#: A commander-cast probability drop larger than this on any watched turn
#: (play or draw, any commander) is a WARN.
CASTABILITY_DROP_WARN_THRESHOLD = 0.05

FilterVerdict = Literal["BLOCKED", "WARN", "PASS_TO_GAMES"]

VERDICT_BLOCKED: FilterVerdict = "BLOCKED"
VERDICT_WARN: FilterVerdict = "WARN"
VERDICT_PASS: FilterVerdict = "PASS_TO_GAMES"

FILTER_DISCLAIMER = (
    "This verdict is a prefilter: go/no-go screening before real games, "
    "not a ranking of deck variants."
)


@dataclass(frozen=True)
class CommanderCastabilityDelta:
    """Per-commander castability for baseline and variant, turns 3-6."""

    name: str
    baseline_probability: dict[str, dict[int, float]]
    variant_probability: dict[str, dict[int, float]]
    probability_delta: dict[str, dict[int, float]]  # variant - baseline
    baseline_expected_turn: dict[str, float | None]
    variant_expected_turn: dict[str, float | None]
    expected_turn_delta: dict[str, float | None]  # variant - baseline


@dataclass(frozen=True)
class VariantComparison:
    """Everything the prefilter knows about one variant vs the baseline."""

    baseline_deck_id: str
    variant_deck_id: str
    trials: int
    seed: int
    added: tuple[tuple[str, int], ...]  # (oracle_name, count), sorted by name
    removed: tuple[tuple[str, int], ...]  # (oracle_name, count), sorted by name
    baseline_ready: bool
    variant_ready: bool
    baseline_not_ready_cards: tuple[str, ...]
    variant_not_ready_cards: tuple[str, ...]
    land_count_delta: int  # variant - baseline
    colored_source_delta: dict[str, int]  # variant - baseline, changed colors only
    flexible_source_delta: int
    definitely_tapped_land_delta: int
    conditionally_tapped_land_delta: int
    t1_untapped_source_delta: dict[str, int]  # variant - baseline, changed colors only
    castability: tuple[CommanderCastabilityDelta, ...]
    verdict: FilterVerdict
    verdict_reason: str


def _card_names(deck: RulesDeckInput) -> tuple[str, ...]:
    return (*deck.commander_names, *deck.mainboard, *deck.sideboard)


def _multiset_diff(
    baseline: RulesDeckInput, variant: RulesDeckInput
) -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]]:
    """(added, removed) as sorted (oracle_name, count) pairs."""
    base_counts = Counter(_card_names(baseline))
    variant_counts = Counter(_card_names(variant))
    added = tuple(
        sorted(
            (name, variant_counts[name] - base_counts.get(name, 0))
            for name in variant_counts
            if variant_counts[name] > base_counts.get(name, 0)
        )
    )
    removed = tuple(
        sorted(
            (name, base_counts[name] - variant_counts.get(name, 0))
            for name in base_counts
            if base_counts[name] > variant_counts.get(name, 0)
        )
    )
    return added, removed


def _not_ready_cards(deck: RulesDeckInput) -> tuple[str, ...]:
    report = check_deck(deck)
    return tuple(
        sorted(card.name for card in report.cards if card.status is not CardReadinessStatus.OK)
    )


def _castability_delta(
    name: str,
    baseline_probability: dict[str, dict[int, float]],
    variant_probability: dict[str, dict[int, float]],
    baseline_expected: dict[str, float | None],
    variant_expected: dict[str, float | None],
) -> CommanderCastabilityDelta:
    watched = {
        mode: {turn: round(variant_probability[mode][turn], 4) for turn in PREFILTER_TURNS}
        for mode in ("play", "draw")
    }
    watched_base = {
        mode: {turn: round(baseline_probability[mode][turn], 4) for turn in PREFILTER_TURNS}
        for mode in ("play", "draw")
    }
    delta = {
        mode: {
            turn: round(watched[mode][turn] - watched_base[mode][turn], 4)
            for turn in PREFILTER_TURNS
        }
        for mode in ("play", "draw")
    }
    expected_base: dict[str, float | None] = {}
    expected_var: dict[str, float | None] = {}
    for mode in ("play", "draw"):
        base_expected = baseline_expected[mode]
        var_expected = variant_expected[mode]
        expected_base[mode] = None if base_expected is None else round(base_expected, 2)
        expected_var[mode] = None if var_expected is None else round(var_expected, 2)
    expected_delta: dict[str, float | None] = {}
    for mode in ("play", "draw"):
        base_turn = expected_base[mode]
        var_turn = expected_var[mode]
        expected_delta[mode] = (
            None if base_turn is None or var_turn is None else round(var_turn - base_turn, 2)
        )
    return CommanderCastabilityDelta(
        name=name,
        baseline_probability=watched_base,
        variant_probability=watched,
        probability_delta=delta,
        baseline_expected_turn=expected_base,
        variant_expected_turn=expected_var,
        expected_turn_delta=expected_delta,
    )


def _verdict(
    *,
    baseline_ready: bool,
    variant_ready: bool,
    baseline_not_ready_cards: tuple[str, ...],
    variant_not_ready_cards: tuple[str, ...],
    colored_source_delta: dict[str, int],
    castability: tuple[CommanderCastabilityDelta, ...],
    commander_changed: bool,
) -> tuple[FilterVerdict, str]:
    if not variant_ready:
        names = ", ".join(variant_not_ready_cards)
        return (
            VERDICT_BLOCKED,
            f"variant not ready: unknown card(s) {names}. {FILTER_DISCLAIMER}",
        )
    if not baseline_ready:
        names = ", ".join(baseline_not_ready_cards)
        return (
            VERDICT_BLOCKED,
            f"baseline not ready: unknown card(s) {names}. {FILTER_DISCLAIMER}",
        )
    reasons: list[str] = []
    if commander_changed:
        reasons.append("commander line-up changed between baseline and variant")
    for cmd in castability:
        for mode in ("play", "draw"):
            for turn in PREFILTER_TURNS:
                drop = cmd.probability_delta[mode][turn]
                if drop < -CASTABILITY_DROP_WARN_THRESHOLD:
                    base = cmd.baseline_probability[mode][turn]
                    var = cmd.variant_probability[mode][turn]
                    reasons.append(
                        f"{cmd.name} {mode} T{turn}: cast probability "
                        f"{base:.3f} -> {var:.3f} (Δ {drop:+.3f})"
                    )
    lost = sorted(
        f"{color} ({delta:+d})" for color, delta in colored_source_delta.items() if delta < 0
    )
    if lost:
        reasons.append(f"color(s) lose mana source(s): {', '.join(lost)}")
    if reasons:
        return VERDICT_WARN, f"{'; '.join(reasons)}. {FILTER_DISCLAIMER}"
    return (
        VERDICT_PASS,
        f"no red flags in card diff, readiness, mana or castability. {FILTER_DISCLAIMER}",
    )


def compare_variant(
    baseline: RulesDeckInput,
    variant: RulesDeckInput,
    *,
    trials: int,
    seed: int = DEFAULT_CASTABILITY_SEED,
) -> VariantComparison:
    """Compare *variant* against *baseline*; deterministic for identical arguments."""
    added, removed = _multiset_diff(baseline, variant)

    baseline_not_ready = _not_ready_cards(baseline)
    variant_not_ready = _not_ready_cards(variant)

    baseline_profile, _ = structural_profile(baseline)
    variant_profile, _ = structural_profile(variant)

    analyzer = ManaAnalyzer(ROOT)
    mana_delta = analyzer.compare_decks(baseline_profile, variant_profile)
    land_count_delta = sum(1 for card in variant_profile.cards if card.is_land) - sum(
        1 for card in baseline_profile.cards if card.is_land
    )

    baseline_cast = analyzer.commander_castability(baseline_profile, trials=trials, seed=seed)
    variant_cast = analyzer.commander_castability(variant_profile, trials=trials, seed=seed)
    baseline_commanders = tuple(baseline_profile.commander_names)
    variant_commanders = set(variant_profile.commander_names)
    castability = tuple(
        _castability_delta(
            name,
            baseline_cast.probability[name],
            variant_cast.probability[name],
            baseline_cast.expected_turn[name],
            variant_cast.expected_turn[name],
        )
        for name in baseline_commanders
        if name in variant_cast.probability
    )
    commander_changed = set(baseline_commanders) != variant_commanders

    verdict, reason = _verdict(
        baseline_ready=not baseline_not_ready,
        variant_ready=not variant_not_ready,
        baseline_not_ready_cards=baseline_not_ready,
        variant_not_ready_cards=variant_not_ready,
        colored_source_delta=mana_delta.colored_source_delta,
        castability=castability,
        commander_changed=commander_changed,
    )

    return VariantComparison(
        baseline_deck_id=baseline.deck_id,
        variant_deck_id=variant.deck_id,
        trials=trials,
        seed=seed,
        added=added,
        removed=removed,
        baseline_ready=not baseline_not_ready,
        variant_ready=not variant_not_ready,
        baseline_not_ready_cards=baseline_not_ready,
        variant_not_ready_cards=variant_not_ready,
        land_count_delta=land_count_delta,
        colored_source_delta=dict(mana_delta.colored_source_delta),
        flexible_source_delta=mana_delta.flexible_source_delta,
        definitely_tapped_land_delta=mana_delta.definitely_tapped_land_delta,
        conditionally_tapped_land_delta=mana_delta.conditionally_tapped_land_delta,
        t1_untapped_source_delta=dict(mana_delta.t1_untapped_source_delta),
        castability=castability,
        verdict=verdict,
        verdict_reason=reason,
    )


def comparison_to_dict(comparison: VariantComparison) -> dict[str, Any]:
    """JSON-safe dict for one VariantComparison (stable key order via sort_keys)."""

    def _castability(cmd: CommanderCastabilityDelta) -> dict[str, Any]:
        return {
            "name": cmd.name,
            "baseline_probability": {
                mode: {str(turn): cmd.baseline_probability[mode][turn] for turn in PREFILTER_TURNS}
                for mode in ("play", "draw")
            },
            "variant_probability": {
                mode: {str(turn): cmd.variant_probability[mode][turn] for turn in PREFILTER_TURNS}
                for mode in ("play", "draw")
            },
            "probability_delta": {
                mode: {str(turn): cmd.probability_delta[mode][turn] for turn in PREFILTER_TURNS}
                for mode in ("play", "draw")
            },
            "baseline_expected_turn": dict(cmd.baseline_expected_turn),
            "variant_expected_turn": dict(cmd.variant_expected_turn),
            "expected_turn_delta": dict(cmd.expected_turn_delta),
        }

    return {
        "baseline_deck_id": comparison.baseline_deck_id,
        "variant_deck_id": comparison.variant_deck_id,
        "trials": comparison.trials,
        "seed": comparison.seed,
        "added": [{"oracle_name": name, "count": count} for name, count in comparison.added],
        "removed": [{"oracle_name": name, "count": count} for name, count in comparison.removed],
        "baseline_ready": comparison.baseline_ready,
        "variant_ready": comparison.variant_ready,
        "baseline_not_ready_cards": list(comparison.baseline_not_ready_cards),
        "variant_not_ready_cards": list(comparison.variant_not_ready_cards),
        "land_count_delta": comparison.land_count_delta,
        "colored_source_delta": dict(comparison.colored_source_delta),
        "flexible_source_delta": comparison.flexible_source_delta,
        "definitely_tapped_land_delta": comparison.definitely_tapped_land_delta,
        "conditionally_tapped_land_delta": comparison.conditionally_tapped_land_delta,
        "t1_untapped_source_delta": dict(comparison.t1_untapped_source_delta),
        "castability": [_castability(cmd) for cmd in comparison.castability],
        "verdict": comparison.verdict,
        "verdict_reason": comparison.verdict_reason,
    }
