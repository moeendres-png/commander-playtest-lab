"""A bounce land is played after the spells, not before them (Refs #1070).

The pilot scored every land play the same and above most casts, so a bounce land (Simic Growth
Chamber: enters tapped, returns a land you control to its owner's hand) was played before the
spells. Played first it takes a land, and its mana, out of the turn: ``mixed`` seed 7, Chulane,
own turn 4, Simic Growth Chamber returned the only Forest and Wood Elves could no longer be cast.
Recorded real pod games: 28 windows with a castable spell in which a bounce land came first, and
in 5 of them no spell was cast afterwards.

These tests pin the card reading, the held land (with the rule switched off as a control that the
fixture reproduces the old order), and the limits of the rule: a basic land and a tapped land that
returns nothing are still played first, a bounce land is played when no spell is on offer, and the
land drop is never traded for a pass the pilot did not prefer.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.card_knowledge import card_facts
from commander_lab.engine.rules.full_game_pilot.priority import _PriorityDecisions
from commander_lab.engine.rules.full_game_pilot_lands import returns_a_land
from commander_lab.models import PilotDecision, PilotUtilityBreakdown
from tests.unit.test_full_game_pilot_mana_and_may import (
    _PASS,
    _TAPS,
    _option,
    _policy,
    _request,
    _state,
)


def _cast(name: str, *, white: int = 0, generic: int = 2) -> dict[str, Any]:
    return _option(
        "cast",
        "activated_ability",
        f"{name} — Cast {name}",
        source_name=name,
        source_object_id="hand-0",
        ability_type="spell",
        mana_cost_white=white,
        mana_cost_generic=generic,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )


def _land(name: str) -> dict[str, Any]:
    return _option(
        "play",
        "activated_ability",
        f"{name} — Play {name}",
        source_name=name,
        source_object_id="hand-1",
        ability_type="play_land",
    )


def _answer(*options: dict[str, Any]) -> list[str]:
    request = _request("priority", [_PASS, *_TAPS, *options], state=_state(step="precombat_main"))
    return list(_policy().decide(request)["selected_option_ids"])


def _rule_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _PriorityDecisions, "_bounce_lands_that_wait_for_a_spell", staticmethod(lambda options: [])
    )


@pytest.mark.parametrize(
    "name",
    [
        "Simic Growth Chamber",
        "Gruul Turf",
        "Rakdos Carnarium",
        "Selesnya Sanctuary",
        "Azorius Chancery",
    ],
)
def test_bounce_lands_are_read_from_their_text(name: str) -> None:
    facts = card_facts(name)
    assert facts is not None
    assert returns_a_land(facts)


@pytest.mark.parametrize(
    "name",
    [
        "Forest",
        "Command Tower",
        "Evolving Wilds",
        "Karoo",  # sacrifices itself unless an untapped Plains is returned: not read here
        "Sol Ring",
    ],
)
def test_other_cards_are_not_bounce_lands(name: str) -> None:
    facts = card_facts(name)
    assert facts is not None
    assert not returns_a_land(facts)


@pytest.mark.parametrize(
    ("spell", "white", "generic"),
    [
        ("Savannah Lions", 1, 0),
        ("Arcane Signet", 0, 2),
        ("Grizzly Bears", 0, 2),
        ("Wood Elves", 0, 3),
        ("Serra Angel", 2, 3),
    ],
)
def test_a_bounce_land_waits_while_a_spell_can_be_cast(
    spell: str, white: int, generic: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = (_cast(spell, white=white, generic=generic), _land("Azorius Chancery"))
    assert _answer(*options) == ["cast"]
    # Control: without the rule the same window plays the land first, the defect measured.
    _rule_off(monkeypatch)
    assert _answer(*options) == ["play"]


def test_a_bounce_land_is_played_when_no_spell_is_on_offer() -> None:
    assert _answer(_land("Azorius Chancery")) == ["play"]


def test_a_basic_land_is_still_played_before_a_spell() -> None:
    assert _answer(_cast("Grizzly Bears"), _land("Plains")) == ["play"]


def test_a_tapped_land_that_returns_nothing_is_still_played_before_a_spell() -> None:
    assert _answer(_cast("Grizzly Bears"), _land("Evolving Wilds")) == ["play"]


def _pilot_passes(monkeypatch: pytest.MonkeyPatch, *, pass_utility: float | None = None) -> None:
    """The pilot chooses to pass; ``pass_utility`` sets what passing is worth against a land."""

    def choose(self: Any, state: Any, actions: Any, rng: Any) -> PilotDecision:
        pass_id = next(action.action_id for action in actions if action.action_kind == "pass")
        return PilotDecision(
            pilot_name=self.pilot_name,
            strength=self.config.strength,
            mode=self.config.mode,
            selected_action_id=pass_id,
        )

    monkeypatch.setattr(GenericCommanderPilot, "choose_action", choose)
    if pass_utility is None:
        return
    real = GenericCommanderPilot.evaluate_action

    def evaluate(self: Any, state: Any, action: Any) -> PilotUtilityBreakdown:
        breakdown = real(self, state, action)
        if action.action_kind == "pass":
            return breakdown.model_copy(update={"total_utility": pass_utility})
        return breakdown

    monkeypatch.setattr(GenericCommanderPilot, "evaluate_action", evaluate)


def test_the_land_drop_is_not_lost_when_the_pilot_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    # The spell stays on offer and the pilot passes over it; the held land is played in place of
    # the pass because, as before, it is worth more than passing.
    _pilot_passes(monkeypatch)
    assert _answer(_cast("Grizzly Bears"), _land("Azorius Chancery")) == ["play"]


def test_a_pass_the_pilot_preferred_to_a_land_stays_a_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _pilot_passes(monkeypatch, pass_utility=99.0)
    assert _answer(_cast("Grizzly Bears"), _land("Azorius Chancery")) == ["pass"]
