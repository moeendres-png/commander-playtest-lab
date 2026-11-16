"""Reminder text and controller-only draws in the Oracle-text role rules.

Parenthesised reminder text explains a keyword or a token; it is not a rule of
the card. The cantrip, card_advantage and hate rules read the text without it
(the same stripping the ramp rules use). card_advantage counts only a draw for
the card's own controller. The fixtures are the public Oracle texts of real cards.
"""

from __future__ import annotations

import pytest

from commander_lab.studio import roles

ON_THE_JOB = (
    "Instant",
    "Creatures you control get +2/+1 until end of turn. Investigate. "
    '(Create a Clue token. It\'s an artifact with "{2}, Sacrifice this token: Draw a card.")',
)
IN_TOO_DEEP = (
    "Enchantment — Aura",
    "Split second (As long as this spell is on the stack, players can't cast spells or "
    "activate abilities that aren't mana abilities.)\n"
    "Enchant creature, planeswalker, or Clue\n"
    'Enchanted permanent is a colorless Clue artifact with "{2}, Sacrifice this artifact: '
    'Draw a card" and loses all other abilities. '
    "(It's no longer a creature or planeswalker.)",
)
FORCED_FRUITION = (
    "Enchantment",
    "Whenever an opponent casts a spell, that player draws seven cards.",
)
GLADEMUSE = (
    "Creature — Beast",
    "Whenever a player casts a spell, if it's not their turn, that player draws a card.",
)
LORE_WEAVER = (
    "Creature — Human Wizard",
    "Partner with Ley Weaver (When this creature enters, target player may put Ley Weaver "
    "into their hand from their library, then shuffle.)\n{5}{U}{U}: Target player draws two cards.",
)
AQUITECTS_WILL = (
    "Kindred Sorcery — Merfolk",
    "Put a flood counter on target land. That land is an Island in addition to its other "
    "types for as long as it has a flood counter on it. If you control a Merfolk, draw a card.",
)
OPT = (
    "Instant",
    "Scry 1. (Look at the top card of your library. You may put that card on the bottom.)\n"
    "Draw a card.",
)
HARMONIZE = ("Sorcery", "Draw three cards.")
MULLDRIFTER = (
    "Creature — Elemental",
    "Flying\nWhen this creature enters, draw two cards.\nEvoke {2}{U} (You may cast this spell for its evoke cost. "
    "If you do, it's sacrificed when it enters.)",
)
RULE_OF_LAW = ("Enchantment", "Each player can't cast more than one spell each turn.")


def _roles(card: tuple[str, str]) -> set[str]:
    return set(roles.classify_oracle_roles(*card))


@pytest.mark.parametrize(
    ("card", "role"),
    [
        (OPT, "cantrip"),
        (HARMONIZE, "card_advantage"),
        (MULLDRIFTER, "card_advantage"),
        (RULE_OF_LAW, "hate"),
    ],
)
def test_true_positives_stay(card: tuple[str, str], role: str) -> None:
    assert role in _roles(card)


def test_clue_reminder_is_not_a_cantrip() -> None:
    found = _roles(ON_THE_JOB)
    assert "cantrip" not in found
    assert "card_advantage" in found  # the Investigate keyword itself stays a claim


def test_split_second_reminder_is_not_hate() -> None:
    assert "hate" not in _roles(IN_TOO_DEEP)


@pytest.mark.parametrize("card", [FORCED_FRUITION, GLADEMUSE])
def test_draw_for_another_player_is_not_card_advantage(card: tuple[str, str]) -> None:
    assert "card_advantage" not in _roles(card)


def test_targeted_draw_stays_card_advantage_but_reminder_is_ignored() -> None:
    # the controller may target themselves; Partner-with reminder text is not a rule
    assert "card_advantage" in _roles(LORE_WEAVER)
    assert "card_advantage" in _roles(
        ("Instant", "Target player draws two cards and loses 2 life.")
    )


def test_conditional_own_draw_spell_is_cantrip() -> None:
    assert "cantrip" in _roles(AQUITECTS_WILL)


def test_each_player_and_target_player_draw_alone_do_not_count() -> None:
    assert "card_advantage" not in _roles(
        ("Enchantment", "At the beginning of your upkeep, each player draws two cards.")
    )
    assert "card_advantage" not in _roles(
        ("Creature — Wizard", "{T}: Each player draws two cards.")
    )
    assert "card_advantage" in _roles(("Creature — Wizard", "{T}: You draw two cards."))
    assert "card_advantage" in _roles(("Creature — Wizard", "{T}: Draw two cards."))


def test_strip_reminder_handles_nesting_and_unbalanced() -> None:
    assert roles.strip_reminder("a (b (c) d) e") == "a   e"
    assert roles.strip_reminder("a (b) c) d") == "a   c) d"
    assert roles.strip_reminder("no parens") == "no parens"


def test_card_name_with_parentheses_is_only_removed_not_misread() -> None:
    # a parenthesised name part is dropped like reminder text; no rule depends on it
    found = _roles(
        (
            "Creature — Beast",
            "B.F.M. (Big Furry Monster) can't be blocked except by three or more creatures.",
        )
    )
    assert found == set()
