# Card rating guide: Chulane, Teller of Tales (version 1, frozen for the pilot)

You rate Magic: The Gathering cards for ONE purpose: how much a card improves a tuned
Commander deck led by **Chulane, Teller of Tales** in a **4-player pod at Bracket 3**
("upgraded": strong synergy and good staples, no fast infinite combos on turn 3, at most
three "Game Changer" cards). You rate the card's value in that deck, not its price, not its
popularity, not how fun it is.

The commander (exact Oracle text):

> Chulane, Teller of Tales {2}{G}{W}{U}, Legendary Creature — Human Druid, 2/4.
> Vigilance. Whenever you cast a creature spell, draw a card, then you may put a land card
> from your hand onto the battlefield. {3}, {T}: Return target creature you control to its
> owner's hand.

What the deck does: cast many creature spells, each one draws a card and may put a land into
play; cheap creatures and creatures with useful "enters the battlefield" (ETB) effects are
replayed after Chulane returns them; extra land drops, landfall and bounce lands profit.
Colours: green, white, blue only.

## Rules for you as a rater

1. Use only the card text given to you and your knowledge of how Magic plays. Do not look up
   or guess how often other players use a card. Popularity is measured elsewhere; your job is
   the card's function.
2. Rate each card on its own. Do not compare with the card you rated just before; compare with
   the anchors below.
3. Use the whole scale. If unsure between two values, pick the lower one and say why in the
   reason.
4. Lands: rate them as lands for this deck's mana base (anchors below), not against spells.
5. Write one reason of at most 20 words per card: the main point that decided the holistic
   value.

## The ratings per card

Five criteria from 0 to 4 and one holistic value from 1 to 10. Integers only.

**E: efficiency.** Effect relative to mana and card spent, compared with other Commander
cards of the same job.
0 clearly overcosted for what it does · 1 below average · 2 fair price · 3 better than most
cards of its job · 4 among the most efficient cards of its job in the format.

**F: fit with Chulane.** Does the card reward or enable the deck's pattern (creature spells,
ETB value that Chulane's bounce repeats, extra land drops and landfall, cheaper creatures,
untapping or copying Chulane, protecting the creature engine)?
0 works against the plan (e.g. destroys own creatures, needs few creatures) · 1 slightly off ·
2 neutral, good in any deck but nothing special here · 3 clearly better here than in an average
deck · 4 a core engine piece of this deck.

**T: table impact with three opponents.** Does the effect scale with opponents or answer any
opponent's threat?
0 irrelevant at a 4-player table · 1 affects only you or one player in a small way · 2 flexible
answer or effect against any one opponent · 3 affects several opponents or the whole board ·
4 changes the whole table's game on its own.

**R: reliability.** How often is the card useful when drawn, early and late, without needing
other cards?
0 often dead · 1 situational · 2 usually useful · 3 useful in almost every game state · 4 never
a bad draw.

**W: win contribution.** Can the card win the game or decide it, alone or with few cards?
0 no · 1 small push towards winning · 2 strong advantage engine or finisher in some games ·
3 regularly decides games · 4 wins or locks the game by itself or with one other card.

**H: holistic value, 1 to 10.** "If this card takes a slot in a tuned Chulane deck (Bracket 3,
4 players), how much better does the deck get?" Weigh the criteria yourself; H is not their
average. 10 must-play, among the best cards for this deck · 8 to 9 excellent, nearly always
played · 6 to 7 good, played in most strong lists · 4 to 5 solid filler, playable · 2 to 3 weak,
only in special builds · 1 does not belong in this deck.

## Anchors (fixed reference ratings, E F T R W | H)

Spells:
- Sol Ring: 4 2 1 4 1 | 10
- Swords to Plowshares: 4 2 2 4 1 | 9
- Cyclonic Rift: 3 2 4 3 3 | 9
- Rhystic Study: 4 2 4 3 2 | 9
- Cloudstone Curio: 3 4 1 2 3 | 8
- Llanowar Elves: 4 3 1 3 1 | 8
- Counterspell: 3 1 2 3 1 | 7
- Farseek: 3 2 1 3 1 | 6
- Cultivate: 2 2 1 3 1 | 5
- Wrath of God: 2 0 3 2 1 | 3
- Divination: 1 1 1 2 0 | 2
- Craw Wurm: 0 1 0 1 0 | 1

Lands (H only matters for lands; criteria judged as a land):
- Command Tower: 4 2 0 4 0 | 10
- Hallowed Fountain: 3 2 0 4 0 | 8
- Simic Growth Chamber: 3 4 0 3 1 | 8
- Evolving Wilds: 2 3 0 3 0 | 5
- Selesnya Guildgate: 1 1 0 3 0 | 3
- A land that makes only colourless mana with no other effect: 0 1 0 2 0 | 1

## Output

A CSV with header `card,E,F,T,R,W,H,reason` and one row per card, in the order given. Quote
the card name and the reason. No other text in the file.
