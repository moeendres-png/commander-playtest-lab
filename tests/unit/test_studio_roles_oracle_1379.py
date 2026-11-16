"""Tests for the #1379 extension of ``roles.classify_oracle_roles``.

Each new rule class (flicker, recursion, graveyard_hate, tutor, tax,
utility_land) and each widened rule (card_draw phrasings, basic-land-type
searches, mana abilities whose tap cost carries an extra component, shroud
as protection) has a positive case and a negative case whose text is close
to the rule but must not fire it. The review follow-up cases pin the
context guards: a draw phrase inside a trigger condition, a negation or an
opponent's draw is not the controller's card draw; a mana or search phrase
that sits only in a token's reminder text belongs to the token, not to the
card that creates it; and a spell's own "this spell costs more" formula is
not a tax effect. All texts are short synthetic Oracle phrasings in the
style of real cards; no card data is read.
"""

from __future__ import annotations

import pytest

from commander_lab.studio import roles


@pytest.mark.parametrize(
    ("type_line", "oracle_text", "expected_roles"),
    [
        # flicker: exile, then return the same object to the battlefield
        (
            "Creature — Cat Beast",
            "When this creature enters, you may exile another target permanent you control, "
            "then return that card to the battlefield under its owner's control.",
            ("flicker",),
        ),
        (
            "Creature — Cat Beast",
            "Whenever you cast a noncreature spell, exile up to one target nonland permanent "
            "you control, then return that card to the battlefield under its owner's control.",
            ("flicker",),
        ),
        (
            "Sorcery",
            "Exile target creature. Return that card to the battlefield at the beginning "
            "of the next end step.",
            ("flicker", "removal"),
        ),
        # flicker negative: temporary exile until the source leaves is removal, not flicker
        (
            "Enchantment",
            "When this enchantment enters, exile target nonland permanent an opponent "
            "controls until this enchantment leaves the battlefield.",
            ("removal",),
        ),
        # recursion: from a graveyard to the battlefield or the hand
        (
            "Sorcery",
            "Return target creature card from your graveyard to the battlefield.",
            ("recursion",),
        ),
        (
            "Instant",
            "Return up to two target cards from your graveyard to your hand.",
            ("recursion",),
        ),
        (
            "Enchantment — Saga",
            "Each player returns two land cards from their graveyard to the battlefield.",
            ("recursion",),
        ),
        (
            "Sorcery",
            "Put target creature card from a graveyard onto the battlefield under your control.",
            ("recursion",),
        ),
        # recursion negative: returning a permanent from the battlefield is bounce
        (
            "Instant",
            "Return target creature to its owner's hand.",
            ("bounce",),
        ),
        # graveyard hate: exiling cards out of graveyards as the effect (the
        # pre-existing coarse removal rule also fires on "exile target ...")
        (
            "Artifact",
            "{T}, Sacrifice this artifact: Exile target player's graveyard.",
            ("graveyard_hate", "removal"),
        ),
        (
            "Sorcery",
            "Exile all cards from all graveyards.",
            ("graveyard_hate",),
        ),
        (
            "Instant",
            "Exile target card from a graveyard. You gain 1 life.",
            ("graveyard_hate", "lifegain", "removal"),
        ),
        (
            "Enchantment",
            "When this enchantment enters, exile all graveyards.",
            ("graveyard_hate",),
        ),
        # graveyard hate negative: exiling cards from your own graveyard as a cost (escape)
        (
            "Creature — Zombie",
            "Escape—Exile three other cards from your graveyard. (You may cast this card "
            "from your graveyard for its escape cost.)",
            (),
        ),
        # tutor: search, revealed into the hand; onto the battlefield; onto the library top
        (
            "Sorcery",
            "Search your library for a Forest or Plains card, reveal it, put it into "
            "your hand, then shuffle.",
            ("tutor",),
        ),
        (
            "Sorcery",
            "Search your library for a creature card with mana value 3 or less, put it "
            "onto the battlefield, then shuffle.",
            ("tutor",),
        ),
        (
            "Instant",
            "Search your library for a card, then shuffle and put that card on top of "
            "your library.",
            ("tutor",),
        ),
        # tutor negative: a land onto the battlefield is land ramp, not a tutor
        (
            "Sorcery",
            "Search your library for a basic land card, put it onto the battlefield "
            "tapped, then shuffle.",
            ("land_ramp", "ramp"),
        ),
        # land ramp by basic land type name (a "Forest card" is a land card)
        (
            "Sorcery",
            "Search your library for a Forest card, put it onto the battlefield, then shuffle.",
            ("land_ramp", "ramp"),
        ),
        # tax: spells cost more
        (
            "Artifact",
            "Noncreature spells cost {1} more to cast.",
            ("tax",),
        ),
        (
            "Creature — Human Soldier",
            "Spells your opponents cast cost {1} more to cast.",
            ("tax",),
        ),
        # tax negative: costing less is cost reduction, not tax
        (
            "Artifact",
            "Spells you cast cost {1} less to cast.",
            ("cost_reduction",),
        ),
        # mana ability whose tap cost carries an extra component
        (
            "Artifact",
            "{T}, Sacrifice this artifact: Add three mana of any one color.",
            ("mana_rock", "ramp"),
        ),
        (
            "Creature — Elf Druid",
            "{T}, Tap an untapped creature you control: Add one mana of any color.",
            ("mana_dork", "ramp"),
        ),
        # ... but a Treasure token's reminder text grants the token the ability, not the card
        (
            "Creature — Cat Warrior",
            "When this creature enters, create a Treasure token. (It's an artifact with "
            '"{T}, Sacrifice this artifact: Add one mana of any color.")',
            (),
        ),
        # card draw phrasings: "draw that many cards" and bare "draw cards"
        (
            "Creature — Merfolk",
            "When this creature enters, shuffle the cards from your hand into your "
            "library, then draw that many cards.",
            ("card_draw",),
        ),
        (
            "Sorcery",
            "Draw cards equal to the greatest mana value among permanents you control.",
            ("card_advantage", "card_draw"),
        ),
        # card draw negative: the draw step is not drawing
        (
            "Enchantment",
            "At the beginning of your draw step, you lose 1 life.",
            (),
        ),
        # shroud is protection
        (
            "Creature — Sliver",
            "All Slivers have shroud.",
            ("protection",),
        ),
        # utility land: a land with an activated ability that is not a mana ability
        (
            "Land",
            "{T}: Add {C}.\n{T}, Sacrifice this land: Destroy target land.",
            ("removal", "utility_land"),
        ),
        # utility land negative: a plain dual land has no role
        (
            "Land — Plains Island",
            "({T}: Add {W} or {U}.)",
            (),
        ),
        # utility land negative: a fetch land's only ability searches (land ramp instead)
        (
            "Land",
            "{T}, Sacrifice this land: Search your library for a basic land card, put "
            "it onto the battlefield, then shuffle.",
            ("land_ramp", "ramp"),
        ),
        # card draw guard: a draw phrase inside a trigger condition is a payoff
        # trigger, not this card drawing (the counter is the only role here)
        (
            "Creature — Bird",
            "Whenever you draw a card, put a +1/+1 counter on this creature.",
            ("counters",),
        ),
        (
            "Creature — Faerie",
            "Whenever an opponent draws a card, you gain 1 life.",
            ("lifegain",),
        ),
        (
            "Enchantment",
            "Whenever a player draws a card, that player loses 1 life.",
            (),
        ),
        # card draw guard: a negation draws nothing
        (
            "Enchantment",
            "Players can't draw cards.",
            (),
        ),
        # card draw guard: a draw whose only drawer is an opponent is not the
        # controller's draw, even as a plain effect after a trigger clause
        (
            "Creature — Eldrazi",
            "When this creature leaves the battlefield, target opponent draws a card.",
            (),
        ),
        # card draw guard: the draw inside an "if you would draw" replacement
        # condition does not happen; the replacement effect is the role
        (
            "Enchantment",
            "If you would draw a card, you may pay {1}. If you do, return target "
            "permanent to its owner's hand.",
            ("bounce",),
        ),
        # card draw positives the guard must not eat: a targeted draw (the
        # controller may target themselves), the real draw after a replaced
        # opponent draw, a draw as the effect of an enters trigger, and a
        # symmetric draw that includes the controller
        (
            "Instant",
            "Target player draws two cards and loses 2 life.",
            ("card_advantage", "card_draw"),
        ),
        (
            "Creature — Faerie",
            "If an opponent would draw a card, instead you draw a card.",
            ("card_draw",),
        ),
        (
            "Creature — Merfolk",
            "When this creature enters, draw a card.",
            ("card_advantage", "card_draw"),
        ),
        (
            "Sorcery",
            "Each player draws a card.",
            ("card_draw",),
        ),
        # cantrip, card_advantage (repeatable / investigate) and hate (#1413 / B-3)
        (
            "Instant",
            "Draw a card if an opponent has cast a blue or black spell this turn.",
            ("cantrip", "card_draw"),
        ),
        (
            "Creature — Human Wizard",
            "Whenever you cast a creature spell, draw a card.",
            ("card_advantage", "card_draw"),
        ),
        (
            "Creature — Elf Scout",
            "Whenever a land enters the battlefield under your control, investigate.",
            ("card_advantage",),
        ),
        (
            "Instant",
            "Your opponents can't cast spells this turn.",
            ("hate",),
        ),
        (
            "Enchantment",
            "Each player can't cast more than one noncreature spell each turn.",
            ("hate",),
        ),
        (
            "Artifact — Clue",
            "{2}, Sacrifice this artifact: Draw a card.",
            ("card_draw",),
        ),
        # card draw positive the negation guard must not eat: the "can't" in
        # the clause negates attacking, not the granted draw ability
        (
            "Enchantment — Aura",
            "Enchanted creature can't attack or block and has \"{7}: This Aura's "
            'controller sacrifices it and draws a card. Activate only as a sorcery."',
            ("card_draw",),
        ),
        # ramp guard: the only "add" sits in a token's reminder text while the
        # card's own tap abilities do something else entirely
        (
            "Artifact",
            "{2}, {T}: Draw a card, then discard a card.\n"
            "{4}, {T}, Sacrifice this artifact: Create a Treasure token. "
            "(It's an artifact with \"{T}, Sacrifice this artifact: Add one mana "
            'of any color.")',
            ("card_draw",),
        ),
        (
            "Creature — Human Artificer",
            "{T}: Tap target creature.\n"
            "When this creature dies, create a Powerstone token. "
            "(It's an artifact with \"{T}: Add {C}. This token can't be sacrificed.\")",
            ("tapper",),
        ),
        # land ramp guard: the search sits only in a token's reminder text
        (
            "Artifact",
            "When this artifact enters, create a Lander token. "
            "(It's an artifact with \"{2}, {T}, Sacrifice this token: Search your "
            "library for a basic land card, put it onto the battlefield tapped, "
            'then shuffle.")',
            (),
        ),
        # ramp positive the reminder removal must not eat: the mana ability is
        # the card's own text, the parenthesis belongs to a keyword
        (
            "Creature — Elf Druid",
            "Flying (This creature can't be blocked except by creatures with "
            "flying or reach.)\n{T}: Add {G}.",
            ("evasion", "mana_dork", "ramp"),
        ),
        # tax guard: a spell's own escalating cost formula taxes nobody
        (
            "Instant",
            "This spell costs {3} more to cast if it targets a creature.",
            (),
        ),
        (
            "Sorcery",
            "This spell costs {1} more to cast for each target beyond the first.",
            (),
        ),
        # tax positive the guard must not eat
        (
            "Enchantment",
            "Creature spells cost {2} more to cast.",
            ("tax",),
        ),
    ],
)
def test_classify_oracle_roles_1379_extensions(
    type_line: str, oracle_text: str, expected_roles: tuple[str, ...]
) -> None:
    assert roles.classify_oracle_roles(type_line, oracle_text) == expected_roles
