"""Tests for #851: London mulligan bottoming from land-heavy hands.

The pilot should bottom a land (not a spell) when the kept hand is
land-heavy, and a spell (never a land) when the hand is mana-normal.
"""

from __future__ import annotations

from commander_lab.agents.live_routing import build_pilot
from commander_lab.agents.pilots import (
    BasePilot,
    PilotConfig,
    PilotDecisionMode,
)
from commander_lab.engine.rules.full_game_pilot.state import PilotActionView
from commander_lab.models.pilots import CardRole


def _pilot() -> BasePilot:
    config = PilotConfig(strength="average", mode=PilotDecisionMode.DETERMINISTIC)
    return build_pilot(config, strategy="generic")


def _land(name: str, idx: int) -> PilotActionView:
    return PilotActionView(
        action_id=f"land-{idx}",
        action_kind="card",
        card_name=name,
        mana_cost=0.0,
        floor_value=0.0,
        immediate_impact=0.0,
        metadata={"is_land": True},
    )


def _spell(
    name: str,
    idx: int,
    *,
    mana_cost: float = 2.0,
    roles: frozenset[CardRole] = frozenset(),
) -> PilotActionView:
    strengths = {role: 1.0 for role in roles}
    return PilotActionView(
        action_id=f"spell-{idx}",
        action_kind="card",
        card_name=name,
        mana_cost=mana_cost,
        roles=roles,
        role_strengths=strengths,
        floor_value=0.5,
        immediate_impact=0.3,
        metadata={"is_land": False},
    )


def _bottomed_names(
    pilot: BasePilot, views: tuple[PilotActionView, ...], count: int
) -> tuple[str, ...]:
    bottomed_ids = pilot.choose_bottom_cards(views, count, commander_names=())
    by_id = {v.action_id: v for v in views}
    return tuple(by_id[i].card_name for i in bottomed_ids)


def test_six_lands_one_spell_bottoms_a_land() -> None:
    pilot = _pilot()
    views = (*(_land(f"Land{i}", i) for i in range(6)), _spell("Good Spell", 6))
    assert _bottomed_names(pilot, views, 1)[0].startswith("Land")


def test_five_lands_two_spells_bottoms_a_land() -> None:
    pilot = _pilot()
    views = (
        *(_land(f"Land{i}", i) for i in range(5)),
        _spell("Good Spell A", 5),
        _spell("Good Spell B", 6),
    )
    assert _bottomed_names(pilot, views, 1)[0].startswith("Land")


def test_three_lands_four_spells_bottoms_a_spell_never_a_land() -> None:
    pilot = _pilot()
    views = tuple(_land(f"Land{i}", i) for i in range(3)) + tuple(
        _spell(f"Spell{i}", 3 + i) for i in range(4)
    )
    bottomed = _bottomed_names(pilot, views, 1)
    assert bottomed[0].startswith("Spell")


def test_two_lands_five_spells_bottom_two_spells() -> None:
    pilot = _pilot()
    views = tuple(_land(f"Land{i}", i) for i in range(2)) + tuple(
        _spell(f"Spell{i}", 2 + i) for i in range(5)
    )
    bottomed = _bottomed_names(pilot, views, 2)
    assert len(bottomed) == 2
    assert all(name.startswith("Spell") for name in bottomed)


def test_twin_stability_same_cards_different_order() -> None:
    pilot = _pilot()
    views_a = (
        _land("Island", 0),
        _land("Mountain", 1),
        _land("Plains", 2),
        _land("Forest", 3),
        _land("Swamp", 4),
        _spell("Lightning Bolt", 5),
        _spell("Counterspell", 6),
    )
    views_b = tuple(reversed(views_a))
    assert _bottomed_names(pilot, views_a, 1) == _bottomed_names(pilot, views_b, 1)
    assert _bottomed_names(pilot, views_a, 2) == _bottomed_names(pilot, views_b, 2)


def test_expensive_spell_may_go_before_third_land() -> None:
    # #851 item 3: a MV>=6 spell with no ramp/draw role may be bottomed
    # before a 3rd land.
    pilot = _pilot()
    views = (
        _land("Island", 0),
        _land("Mountain", 1),
        _land("Plains", 2),
        _spell("Expensive Finisher", 3, mana_cost=7.0),
        _spell("Good Spell", 4),
    )
    bottomed = _bottomed_names(pilot, views, 1)
    assert bottomed[0] == "Expensive Finisher"


def test_count_two_from_six_lands_takes_two_lands() -> None:
    # #851 item 2: count > 1 removes against the shrinking hand.
    pilot = _pilot()
    views = (*(_land(f"Land{i}", i) for i in range(6)), _spell("Good Spell", 6))
    bottomed = _bottomed_names(pilot, views, 2)
    assert len(bottomed) == 2
    assert all(name.startswith("Land") for name in bottomed)


def _old_opening_card_value(card: PilotActionView) -> float:
    """The pre-#851 rule: constant 2.2 for every land."""
    if bool(card.metadata.get("is_land", False)):
        return 2.2
    value = card.floor_value + card.immediate_impact
    if card.mana_cost <= 2:
        value += card.strength(CardRole.RAMP) * 1.4
        value += card.strength(CardRole.DRAW) * 0.8
        value += card.strength(CardRole.SELECTION) * 0.7
        value += card.strength(CardRole.REMOVAL) * 0.45
        value += card.strength(CardRole.COUNTER) * 0.35
        value += card.strength(CardRole.PROTECTION) * 0.35
    value -= max(0.0, card.mana_cost - 4.0) * 0.45
    value -= card.turn_cycle_risk * 0.25
    return value


def test_wrong_reason_control_old_rule_bottoms_spells() -> None:
    # #851 (f): with the old constant-2.2 land value, (a) and (b) would
    # bottom a spell, proving the new tests fail on the old code.
    six_one = (*(_land(f"Land{i}", i) for i in range(6)), _spell("Good Spell", 6))
    five_two = (
        *(_land(f"Land{i}", i) for i in range(5)),
        _spell("Good Spell A", 5),
        _spell("Good Spell B", 6),
    )
    for views in (six_one, five_two):
        scored = sorted(
            views,
            key=lambda c: (_old_opening_card_value(c), -c.mana_cost, c.card_name),
        )
        # Old rule: the cheapest card by value is a spell (land is 2.2).
        assert not bool(scored[0].metadata.get("is_land", False))
