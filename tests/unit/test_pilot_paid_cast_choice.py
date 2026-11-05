"""Rank paid optional casts by visible funding without changing the engine's options."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.unit.test_pilot_optional_costs import _answer, _ask, _board

_CHANDRA = {"ability_type": "activated_nonmana", "source_name": "Chandra, Torch of Defiance"}
_RED = "{T}: Add {R}."


@pytest.mark.parametrize("name", ["Fellwar Stone", "Talisman of Creativity"])
@pytest.mark.parametrize("lands", [(), (_RED,)])
def test_paid_cast_with_a_visible_mana_shortfall_is_declined(
    name: str, lands: tuple[str, ...]
) -> None:
    request = _ask(
        f"Cast {name}? (You still pay the costs)",
        _board(*lands),
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == "no"


@pytest.mark.parametrize("pooled", [True, False])
def test_funded_paid_cast_keeps_the_usual_preference(pooled: bool) -> None:
    board = _board(pool={"red": 2}) if pooled else _board(_RED, _RED)
    request = _ask(
        "Cast Fellwar Stone? (You still pay the costs)",
        board,
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == "yes"


def test_paid_cast_needs_the_printed_colour_as_well_as_the_amount() -> None:
    request = _ask(
        "Cast Lightning Bolt? (You still pay the costs)",
        _board("{T}: Add {U}.", "{T}: Add {U}."),
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == "no"


@pytest.mark.parametrize(
    "prompt",
    [
        "Cast A Card Nobody Printed? (You still pay the costs)",
        "Cast Treasure Cruise? (You still pay the costs)",
        "Cast Shriekmaw? (You still pay the costs)",
        "Cast Snuff Out? (You still pay the costs)",
        "Cast Wear? (You still pay the costs)",
        "Cast Fellwar Stone without paying its mana cost?",
        "Cast spell without paying its mana cost?",
        "Draw a card?",
    ],
)
def test_unknown_cost_reductions_and_other_may_prompts_keep_the_usual_preference(
    prompt: str,
) -> None:
    assert _answer(_ask(prompt, _board(), _CHANDRA, outcome="benefit", offset=1)) == "yes"


def test_unreadable_funding_keeps_the_usual_preference() -> None:
    request = _ask(
        "Cast Fellwar Stone? (You still pay the costs)",
        _board(unreadable=True),
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == "yes"


@pytest.mark.parametrize("funded", [False, True])
def test_token_metadata_does_not_hide_the_paid_spell_price(funded: bool) -> None:
    from commander_lab.agents.card_knowledge import card_facts

    facts = card_facts("Magma Opus")
    assert facts is not None and facts.keywords == {"Treasure"}
    board = _board(*[_RED] * 7, "{T}: Add {U}.") if funded else _board()
    request = _ask(
        "Cast Magma Opus? (You still pay the costs)",
        board,
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == ("yes" if funded else "no")


@pytest.mark.parametrize(
    "keywords",
    [frozenset({"Unknown payment mechanic"}), frozenset({"Treasure", "Unknown payment mechanic"})],
)
def test_unknown_keyword_is_not_treated_like_a_token_tag(
    monkeypatch: pytest.MonkeyPatch, keywords: frozenset[str]
) -> None:
    from commander_lab.agents.card_knowledge import card_facts
    from commander_lab.engine.rules.full_game_pilot import payment

    facts = card_facts("Fellwar Stone")
    assert facts is not None
    unknown = replace(facts, keywords=keywords)
    monkeypatch.setattr(payment, "card_facts", lambda name: unknown)
    request = _ask(
        "Cast Fellwar Stone? (You still pay the costs)",
        _board(),
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == "yes"


@pytest.mark.parametrize("opponent", [True, False])
def test_public_cost_reducer_keeps_the_usual_preference(opponent: bool) -> None:
    board = _board()
    player = board["players"][1 if opponent else 0]
    player["battlefield"] = [
        {
            "name": "Helm of Awakening",
            "tapped": False,
            "abilities": ["All spells cost {1} less to cast."],
        }
    ]
    request = _ask(
        "Cast Fellwar Stone? (You still pay the costs)",
        board,
        _CHANDRA,
        outcome="benefit",
        offset=1,
    )
    assert _answer(request) == "yes"


def test_shortfall_ranking_preserves_both_engine_options(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.test_full_game_pilot_mana_and_may import _policy

    policy = _policy()
    pilot_class = type(policy._pilots[1].pilot)
    original = pilot_class.choose_action
    seen = []

    def record_options(self, state, actions, rng):
        seen.extend(action.metadata["boolean_value"] for action in actions)
        return original(self, state, actions, rng)

    monkeypatch.setattr(pilot_class, "choose_action", record_options)
    policy.decide(
        _ask(
            "Cast Fellwar Stone? (You still pay the costs)",
            _board(),
            _CHANDRA,
            outcome="benefit",
            offset=1,
        )
    )
    assert sorted(seen) == [False, True]
