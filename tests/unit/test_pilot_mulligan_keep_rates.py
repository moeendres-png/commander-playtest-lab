"""Keep-rate targets for the pilot mulligan decision (#850).

The pilot used to mulligan ~51% of all opening hands (4-land hands 68% of the
time). These tests pin the fixed behavior: ordinary Commander hands are kept.

(a) keep-rate ranges on seeded samples from the repo decks,
(b) hand-built boundary hands,
(c) wrong-reason control: the old formula fails (a),
(d) each extra mulligan lowers the keep threshold (-0.55).
"""

from __future__ import annotations

import random
from pathlib import Path

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game_pilot_views import card_view_fields
from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)

ROOT = Path(__file__).resolve().parents[2]
DECKS = (
    ROOT / "data/decks/rogshai_current.json",
    ROOT / "data/decks/opponents/kaervek/current/deck.json",
    ROOT / "data/opponents/hosts_of_mordor_precon.json",
    ROOT / "data/opponents/lorehold_spirit_precon.json",
)
SEED = 7
HANDS = 2000


def _pilot(strength: PilotStrength):
    return build_pilot(
        PilotConfig(strength=strength, mode=PilotDecisionMode.DETERMINISTIC),
        strategy="generic",
    )


def _view(action_id: str, name: str, **fields) -> PilotActionView:
    base = card_view_fields(name)
    base.update(fields)
    return PilotActionView(
        action_id=action_id,
        action_kind="card",
        card_name=name,
        floor_value=0.5,
        immediate_impact=0.3,
        **base,
    )


def _keep_rates(deck_path: Path, *, seed: int = SEED, hands: int = HANDS):
    deck = load_rules_deck_snapshot(deck_path)
    library = list(deck.mainboard)
    pilot = _pilot(PilotStrength.NEAR_OPTIMAL_HEURISTIC)
    rng = random.Random(seed)
    kept = [0] * 8
    total = [0] * 8
    for _ in range(hands):
        hand = rng.sample(library, 7)
        views = [_view(f"hand-{i}", name) for i, name in enumerate(hand)]
        lands = sum(bool(v.metadata.get("is_land", False)) for v in views)
        total[lands] += 1
        keep, _ = pilot.should_keep_opening_hand(
            views,
            mulligans=0,
            free_first=True,
            commander_names=deck.commander_names,
            rng=random.Random(0),
        )
        if keep:
            kept[lands] += 1
    rates = [kept[n] / total[n] if total[n] else 0.0 for n in range(8)]
    return rates, sum(kept) / sum(total)


def test_keep_rate_ranges_on_seeded_deck_samples() -> None:
    """(a) Per-land keep-rate bands hold on every repo deck, for the pilot the games use.

    The hand is judged by what its lands can cast, not by the land count alone (#989 phase 2):
    ordinary three- and four-land hands are kept, dead hands are not, and a 2-land hand is kept
    when it can use its lands.
    """
    for deck_path in DECKS:
        rates, overall = _keep_rates(deck_path)
        assert rates[3] >= 0.70, f"{deck_path.name}: 3-land kept {rates[3]:.1%}"
        assert rates[4] >= 0.85, f"{deck_path.name}: 4-land kept {rates[4]:.1%}"
        assert 0.25 <= rates[2] <= 0.90, f"{deck_path.name}: 2-land kept {rates[2]:.1%}"
        assert rates[5] >= 0.60, f"{deck_path.name}: 5-land kept {rates[5]:.1%}"
        dead = max(rates[0], rates[1], rates[7])
        assert dead <= 0.05, f"{deck_path.name}: dead-hand kept {dead:.1%}"
        assert rates[6] <= 0.35, f"{deck_path.name}: 6-land kept {rates[6]:.1%}"
        # Of every 100 hands about 20 hold 0, 1, 6 or 7 lands and are sent back.
        assert 0.55 <= overall <= 0.85, f"{deck_path.name}: overall {overall:.1%}"


def test_strength_selectivity_order() -> None:
    """WEAK keeps the most, NEAR_OPTIMAL_HEURISTIC the fewest; none mulligans half."""
    deck = load_rules_deck_snapshot(DECKS[0])
    library = list(deck.mainboard)
    rng = random.Random(SEED)
    hands = [rng.sample(library, 7) for _ in range(HANDS)]
    keep_rates = {}
    for strength in (
        PilotStrength.WEAK,
        PilotStrength.AVERAGE,
        PilotStrength.STRONG,
        PilotStrength.NEAR_OPTIMAL_HEURISTIC,
    ):
        pilot = _pilot(strength)
        kept = 0
        for hand in hands:
            views = [_view(f"hand-{i}", name) for i, name in enumerate(hand)]
            keep, _ = pilot.should_keep_opening_hand(
                views,
                mulligans=0,
                free_first=True,
                commander_names=deck.commander_names,
                rng=random.Random(0),
            )
            kept += keep
        keep_rates[strength] = kept / len(hands)
    assert (
        keep_rates[PilotStrength.WEAK]
        >= keep_rates[PilotStrength.AVERAGE]
        >= keep_rates[PilotStrength.STRONG]
        >= keep_rates[PilotStrength.NEAR_OPTIMAL_HEURISTIC]
    )
    assert all(rate > 0.50 for rate in keep_rates.values())


def _land(name: str, index: int) -> PilotActionView:
    return _view(f"land-{index}", name, metadata={"is_land": True})


def _spell(
    name: str, index: int, *, cost: float, roles: set[CardRole] | None = None
) -> PilotActionView:
    role_set = frozenset(roles or set())
    return _view(
        f"spell-{index}",
        name,
        mana_cost=cost,
        roles=role_set,
        role_strengths={role: 1.0 for role in role_set},
        metadata={"is_land": False},
    )


def _decide(pilot, cards) -> bool:
    keep, _ = pilot.should_keep_opening_hand(
        cards,
        mulligans=0,
        free_first=True,
        commander_names=(),
        rng=random.Random(0),
    )
    return keep


def test_hand_built_boundary_hands() -> None:
    """(b) Obvious keeps and obvious mulligans."""
    pilot = _pilot(PilotStrength.AVERAGE)
    # 7 lands, 0 spells -> mulligan (nothing to do with the mana).
    assert not _decide(pilot, [_land("Plains", i) for i in range(7)])
    # 0 lands -> mulligan (cannot cast anything).
    assert not _decide(pilot, [_spell(f"spell-{i}", i, cost=2.0) for i in range(7)])
    # 3 lands + two 2-drops + one 5-drop -> keep (the #850 motivating case:
    # the old 0.45 expensive penalty mulliganed this).
    assert _decide(
        pilot,
        [
            _land("Plains", 0),
            _land("Island", 1),
            _land("Mountain", 2),
            _spell("two-drop-a", 3, cost=2.0),
            _spell("two-drop-b", 4, cost=2.0),
            _spell("five-drop", 5, cost=5.0),
            _spell("filler", 6, cost=3.0),
        ],
    )
    # 4 lands + 3 spells -> keep (the #850 headline: 4-land hands were
    # mulliganed 68% of the time).
    assert _decide(
        pilot,
        [
            _land("Plains", 0),
            _land("Island", 1),
            _land("Mountain", 2),
            _land("Forest", 3),
            _spell("spell-a", 4, cost=2.0),
            _spell("spell-b", 5, cost=3.0),
            _spell("spell-c", 6, cost=4.0),
        ],
    )


def _old_opening_hand_score(cards: list[PilotActionView]) -> float:
    """The pre-#850 formula, copied verbatim (wrong-reason control)."""
    lands = sum(bool(card.metadata.get("is_land", False)) for card in cards)
    early_ramp = sum(card.strength(CardRole.RAMP) for card in cards if card.mana_cost <= 2)
    early_velocity = sum(
        card.strength(CardRole.DRAW) + card.strength(CardRole.SELECTION)
        for card in cards
        if card.mana_cost <= 2
    )
    early_interaction = sum(
        card.strength(CardRole.REMOVAL)
        + card.strength(CardRole.COUNTER)
        + card.strength(CardRole.PROTECTION)
        for card in cards
        if card.mana_cost <= 2
    )
    expensive = sum(card.mana_cost >= 5 for card in cards)
    land_score = 2.4 - abs(3 - lands) * 1.1
    if lands < 2 or lands > 5:
        land_score -= 2.5
    score = land_score
    score += min(2.0, early_ramp * 0.8)
    score += min(1.5, early_velocity * 0.55)
    score += min(1.2, early_interaction * 0.35)
    score -= expensive * 0.45
    return score


def test_old_formula_fails_the_keep_rate_ranges() -> None:
    """(c) The pre-#850 scoring cannot pass (a): guards against a vacuous test."""
    deck = load_rules_deck_snapshot(DECKS[0])
    library = list(deck.mainboard)
    rng = random.Random(SEED)
    kept = [0] * 8
    total = [0] * 8
    for _ in range(HANDS):
        hand = rng.sample(library, 7)
        views = [_view(f"hand-{i}", name) for i, name in enumerate(hand)]
        lands = sum(bool(v.metadata.get("is_land", False)) for v in views)
        total[lands] += 1
        # Old AVERAGE threshold was 2.3.
        if _old_opening_hand_score(views) >= 2.3:
            kept[lands] += 1
    four_land = kept[4] / total[4]
    overall = sum(kept) / sum(total)
    assert four_land < 0.85, f"old formula unexpectedly keeps 4-land at {four_land:.1%}"
    assert overall < 0.70, f"old formula unexpectedly keeps overall {overall:.1%}"


def test_extra_mulligans_lower_the_threshold() -> None:
    """(d) After the free first mulligan a fresh seven is worth less, so the bar falls."""
    pilot = _pilot(PilotStrength.AVERAGE)
    # 2 lands, one cheap spell and four expensive ones: worth about 1.9 mana less than a fresh
    # seven. The fresh-hand bar allows a margin of 1.0; once a mulligan has cost a card the bar
    # falls by 1.2 more.
    hand = [
        _land("Plains", 0),
        _land("Island", 1),
        _spell("cheap", 2, cost=3.0),
        *(_spell(f"big-{i}", i + 3, cost=6.0) for i in range(4)),
    ]
    decisions = []
    scores = []
    for mulligans in (0, 1, 2, 3):
        keep, score = pilot.should_keep_opening_hand(
            hand,
            mulligans=mulligans,
            free_first=True,
            commander_names=(),
            rng=random.Random(0),
        )
        decisions.append(keep)
        scores.append(score)
    assert len(set(scores)) == 1
    assert -2.2 < scores[0] < -1.0
    # mulligans=0: a fresh seven is worth more; from the first mulligan on, keep.
    assert decisions == [False, True, True, True]


def test_colourless_lands_for_coloured_spells_are_sent_back() -> None:
    """A hand whose lands cannot make the colours of its spells is worse than a fresh seven.

    Three lands and cheap spells look like a keep to a land counter; the colours say the
    spells cannot be cast.
    """
    pilot = _pilot(PilotStrength.AVERAGE)
    forests = [_land("Forest", i) for i in range(3)]
    blue = [
        _view(f"spell-{i}", name, **card_view_fields(name))
        for i, name in enumerate(("Counterspell", "Mana Leak", "Brainstorm", "Opt"))
    ]
    green = [
        _view(f"spell-{i}", name, **card_view_fields(name))
        for i, name in enumerate(("Rampant Growth", "Cultivate", "Llanowar Elves", "Farseek"))
    ]
    assert not _decide(pilot, forests + blue)
    assert _decide(pilot, forests + green)
