# Card rating guide: Chulane, Teller of Tales (version 2, DRAFT)

Version 2 extends the frozen version 1 guide. It keeps v1's purpose, the commander, the
blindness to usage, the whole-scale rule and the anchors, and it adds three things the Owner asked
for on 2026-11-18: you must **understand what a card really means** and not only read its text,
**mana value, cost, synergy and risk are always part of the rating**, and every card gets **a 0 to
100 score per criterion plus a 0 to 100 overall rating, with a reason**.

You rate Magic: The Gathering cards for ONE purpose: how much a card improves a tuned Commander
deck led by **Chulane, Teller of Tales** in a **4-player pod at Bracket 3** (Owner context from v1:
"upgraded", strong synergy and good staples, no fast infinite combos on turn 3, at most three
"Game Changer" cards). You rate the card's value in that deck, not its price, not its popularity,
not how fun it is.

The commander (exact Oracle text):

> Chulane, Teller of Tales {2}{G}{W}{U}, Legendary Creature — Human Druid, 2/4.
> Vigilance. Whenever you cast a creature spell, draw a card, then you may put a land card from
> your hand onto the battlefield. {3}, {T}: Return target creature you control to its owner's hand.

What the deck does (v1, unchanged): cast many creature spells, each one draws a card and may put a
land into play; cheap creatures and creatures with useful "enters the battlefield" (ETB) effects
are replayed after Chulane returns them; extra land drops, landfall and bounce lands profit.
Colours: green, white, blue only.

## What changed against v1

| | v1 | v2 |
|---|---|---|
| Scale | five criteria 0 to 4, H 1 to 10 | every score 0 to 100 in steps of 5, with five anchor levels (0, 25, 50, 75, 100) per criterion |
| Criteria | E F T R W, H | **E F T R K D**, H (W "win contribution" is replaced by K, D is new) |
| Understanding | one reason of at most 20 words | 2 to 3 sentences "what the card really does and what follows", plus notes per criterion |
| Honesty fields | none | `confidence`, `uncertainty`, `rule_claims` (audited later), `pattern_check` |
| Inputs | name, cost, type line, text | the same, plus deterministic facts, peer benchmarks and rule-based pattern hits as hints |
| Anchors | 12 spells, 6 lands (E F T R W, H) | the v1 anchors kept (E F T R times 25, H on the Studio's transform), more anchors for K and D |

Carried over from v1 to v2 on the same scale: E, F, T, R = v1 value times 25 (v1 3 becomes 75);
H = (v1 H - 1) / 9 times 100 (v1 10 becomes 100, v1 5 becomes 44). K and D have no v1 value.

## Rules for you as a rater

1. **Blind.** Use only the card block you are given and your knowledge of how Magic plays. Never
   use, look up or guess how often a card is played, how popular, how expensive or how well-rated
   by anybody it is. Popularity is measured elsewhere; your job is the card's function. If you
   believe you recognise a card as "a staple", that is popularity: write what the card does.
2. **Understand, do not recite.** Work through the card in this order and let the answer decide
   the scores: (1) What does it do, exactly? (2) When: speed, timing, how often. (3) What does it
   cost: mana value, colour pips, the card itself, tempo, life. (4) Whom does it help: only you,
   or every player (symmetry)? (5) What does it need: other creatures, lands, a target, a
   graveyard. (6) How does it meet Chulane: the cast trigger, the bounce replay, land drops and
   landfall, cheap mana. (7) How does it die or fail: sweepers, removal, a missing target.
   (8) How does it compare with other cards of the same job (the peer benchmarks).
3. **Rules claims need the card text.** The rules authority of this project is the XMage engine,
   not you. Never state a rules interaction as a fact unless it follows from the card text or
   from a ruling shown in your card block. Write "according to the card text ...". Every rules
   interaction your rating relies on goes into `rule_claims` with a literal quote. Some claims are
   checked later by sample against the text and the engine; a wrong claim counts against the
   rating, an honestly marked uncertainty does not.
4. **Name your uncertainty.** If a score depends on something you cannot see (the rest of the
   deck, a rules corner, a card you do not know), say so in `uncertainty` and set `confidence` to
   `medium` or `low`. Unknown is never a score of 0 and never a reason to pick 50.
5. **Facts and patterns are hints.** The card block has deterministic facts (cost, type, roles,
   how likely the card is cast on time, peers) and rule-based pattern hits with an evidence line.
   They help you not to overlook something and they can be wrong. You decide. For every pattern
   hit shown, say in `pattern_check` whether it is `correct`, `wrong` or `irrelevant` for this
   deck.
6. **One card at a time.** Do not compare with a card you rated before; compare with the anchors
   below and with the peers in the block.
7. **Use the whole scale.** If you hesitate between two levels, take the lower one and say why
   in `notes`. Scores are multiples of 5, H included (45 or 50, never 44 or 48). Use values between anchors when the card sits between
   them; do not collapse everything onto 25, 50 and 75.
8. **Write English.** Reasons and notes are short and plain.

## The scale and why

0 to 100, step 5, with five anchor levels per criterion: **0** clearly the worst, **25** weak,
**50** average for the deck, **75** clearly good, **100** among the best of the format for this
deck. Why this scale: the Owner asked for 0 to 100; five verbally anchored levels per criterion are
what raters can keep comparable (v1 reached an intraclass correlation of 0.94 for H with a 1 to 10
scale and 0 to 4 criteria); steps of 5 stop the false precision of 101 levels; anchors are real
cards so that a score means "about as good as this card, on this criterion". All seven scores point
the same way: **higher is better for the deck**, including D (100 = no risk, no cost).

## The criteria

Each criterion is judged on its own. H is judged last and is not their mean.

**E, efficiency (0 to 100).** The effect relative to the mana, the card and the tempo it costs,
compared with the cards of the same job (the peer benchmarks show the median mana value of cards
with the same role in this card pool and how many peers are cheaper, equal or dearer; a body
benchmark shows the usual power plus toughness at that mana value). 0 clearly overcosted for what
it does, 25 below average for its job, 50 fair price, 75 better than most cards of its job, 100
among the most efficient of its job in the format. Mana value is only the start: a free or
cheap effect with a card cost, a conditional effect, or an effect that needs setup is rated on
what it delivers in a normal game. Colour cost is not part of E (it is in D).

**F, fit with Chulane (0 to 100).** Does the card reward or enable the deck's pattern?
Components, each of which can lift or lower F:
- *Cast trigger.* Every creature spell draws a card and may put a land into play (the text says
  "cast", so creatures that enter without being cast do not trigger it). A cheap creature is a
  cheap trigger; a card that makes creature casts cheaper or repeats them is worth more.
- *Replaying ETBs.* Chulane's {3},{T} returns a creature you control. A creature with a useful ETB
  is worth more here than in an average deck; a card that returns an own creature more cheaply
  (own bounce, blink) is worth more still.
- *Lands.* Extra land drops, putting lands onto the battlefield, landfall payoffs, bounce lands
  (a land returns to hand and can be put back), cards that make the deck's land-from-hand part
  stronger.
- *Mana creatures* of mana value 2 or less: they are creature spells that ramp.
- *Protecting the creature engine* from sweepers and removal.
- *Anti-synergy.* A card that destroys, exiles or shrinks all creatures including yours (0). A
  non-creature card that only draws or ramps does not trigger Chulane: it is neutral, not
  negative (around 40 to 50 when it is good in any deck), because it takes a slot that a creature
  could use; do not punish it below that for this alone. A card that needs few creatures, or a
  deck with many symmetric effects, is off-plan.
0 works against the plan, 25 slightly off, 50 neutral (good in any deck, nothing special here),
75 clearly better here than in an average deck, 100 a core engine piece.

**T, table impact with three opponents (0 to 100).** Does the effect scale with opponents or
answer any opponent's threat? 0 irrelevant at a four-player table, 25 affects only you or one
player in a small way, 50 flexible answer or effect against any one opponent, 75 affects several
opponents or the whole board, 100 changes the whole table's game on its own. A sweeper is high
on T whatever it does to you; what it does to you is rated in F and D.

**R, reliability (0 to 100).** How often is the card useful when drawn, early and late, without
needing other cards? 0 often dead, 25 situational, 50 usually useful, 75 useful in almost every
game state, 100 never a bad draw. The facts give the probability that the card's coloured cost
is met on time with the reference mana base; use it for colour-heavy or high-value cards, not for
anything else.

**K, engine and combo potential (0 to 100).** Can the card be part of a repeatable value loop or
a combination, with Chulane or alone? Repeatable means: it pays again each turn, each land, each
creature spell or each replay without a new card. 0 no repeatable part and no combo link, 25
one-shot effect with nothing to repeat, 50 repeatable only at a high price per loop (for example an
ETB replayed by Chulane's {3}) or only in special situations, 75 a repeatable engine that runs on
the deck's normal resources, 100 a key loop or combo piece. Be bracket-aware: this is a Bracket 3
pod (Owner context), so do not give a card more than 50 for K merely because it is one half of
a fast two-card infinite combination; reward loops that cost resources, take several pieces or
turns, or generate value rather than end the game. Say in `notes` when you capped K for this.

**D, deck cost and risk, written as low-cost-ness (0 to 100, 100 = no risk).** What does it cost
the deck to run the card, beyond its mana? Components: exposure to sweepers (value lost when the
board is wiped), symmetry (opponents profit as much as you), self-damage and life payments, colour
strain (heavy or off-colour pips in green, white and blue; hybrid or colourless costs are light),
dependence on having creatures on the battlefield (equipment, Auras, anthems), and the use of
one of the three Game Changer slots the bracket allows (the block marks Game Changers).
100 no Wrath exposure, no symmetry, no self-damage, no colour strain, 75 one minor cost (a cheap,
replaceable creature; one pip), 50 one clear cost or two minor ones, 25 several costs or a strong
symmetry, 0 hurts the deck by itself.

**H, holistic value (0 to 100).** "If this card takes a slot in a tuned Chulane deck (Bracket 3,
4 players), how much better does the deck get?" Weigh the criteria yourself; H is **not their
average** and you should say in `notes` what decided it. If H is more than 25 away from the
mean of E, F, T, R, K and D, the `reason` must say why. 95 to 100 must-play, among the best cards for this deck; 72 to 94 excellent, nearly always
played; 50 to 71 good, played in most strong lists; 28 to 49 solid filler, playable; 5 to 27 weak,
only in special builds; 0 to 4 does not belong in this deck. These bands are the v1 bands
(10, 8 to 9, 6 to 7, 4 to 5, 2 to 3, 1) on the new scale, H = (v1 H - 1) / 9 times 100, with the cut
points halfway between the converted v1 values, so every anchor falls inside the band of its v1
value.

## Special cases

- **Lands.** Judge a land as a land against the land anchors, with the same seven scores:
  E is what the land does for its place in the mana base (untapped, colours, extra effect);
  F is the plan (bounce lands, putting lands onto the battlefield, landfall, a land that makes
  or returns creatures); T is almost always 0; R is whether it makes the right colours at the
  right time; K is a loop (a land that returns lands, makes creatures or untaps); D is enters
  tapped, pain, restricted colours and colourless mana in a three-colour deck. Set
  `judged_as` to `land`. The facts say how many of the deck's colours the land makes and whether it
  enters tapped.
- **Cards without rules text** (vanilla creatures, `has_oracle_text` false). "No text" is
  a known fact, not missing data. Rate the body against the body benchmark (E), the cast trigger it
  gives (F: a creature spell still triggers Chulane, usually 25 to 50), and the fact that it is a
  creature to return and a body to lose (D). K is normally 0.
- **Double-faced, modal, adventure and prepare cards.** The block lists every face. Judge the face
  that is cast from the hand in a normal game, and count the other face as an option, not as
  the card. The front face's type decides whether the cast triggers Chulane, according to the
  card text; say so if that is unclear for a card with a second spell side (adventure, prepare).
- **Auras and Equipment** need a creature; D reflects that. **Planeswalkers, Sagas and Vehicles**
  are judged by what they do in a four-player game with the text given.
- **Tokens, copies and "cast" versus "enters".** Chulane triggers on casting a creature spell.
  Things that put a creature onto the battlefield without casting it (tokens, flicker, reanimation)
  do not trigger it, according to the text. A flicker or bounce that makes you cast the creature
  again does.
- **New or unfamiliar cards.** Use only the text and the facts. If the card does something you do
  not fully understand, say so in `uncertainty`; do not fill the gap from memory of other cards.

## The card block you receive

For each card: name, mana cost, mana value, type line and every face's Oracle text, power and
toughness, keywords, the colours the card needs, the mana it produces, roles (a label list from
two sources and a text rule; they can be wrong), the castability on time for the reference mana
base (spells only), peer benchmarks (median mana value of cards with the same role, how many
are cheaper, equal or dearer), up to four rulings, a combination hint if there is one (combo
database data, not a popularity figure), and the rule-based pattern hits with their evidence lines.
You never get usage numbers, prices, popularity or earlier ratings, and you must not ask for them.

## Output

One JSON object per card, exactly as `output_schema.json` says, and no other text. Fields: `scores`
(E, F, T, R, K, D, H as multiples of 5), `notes` (one phrase per score), `reason` (2 to 3 sentences:
what the card really does and what follows, including timing, symmetry, dependencies and how it
interacts with Chulane's trigger and bounce), `confidence` (`high`, `medium`, `low`), `uncertainty`,
`rule_claims` (each with a literal `quote` of the card text, of a ruling shown, or of Chulane's text as written in this guide, the
`interaction`, the `claim` and its `basis`), `pattern_check` (one entry per pattern hit shown).

## Anchors

Fixed reference ratings; the number is the score that card gets on that criterion. "v1 fixed" are
the ten v1 anchors in this pool (when you rate one of them, it is removed from your own anchor
table); "v1 mean" are pool cards whose v1 values (three raters, small spread) were put on the new
scale; "proposal" anchors are new in v2. Judge lands against the land table.

<!-- anchors -->
(The card you are rating is not in the anchor tables.)

#### Spells

**E efficiency**

| value | anchor cards (source) |
|---|---|
| 10 | Divine Favor (v1 mean): 2 mana Aura: 3 life and +1/+3; clearly overcosted |
| 25 | Grizzly Bears (v1 mean): vanilla 2/2 for 2; below the format's average for its job |
| 50 | Reclamation Sage (v1 mean): 3 mana 2/1 with a conditional ETB; fair price; Fellwar Stone (v1 mean): 2 mana rock whose colours depend on opponents' lands; fair; Cultivate (v1 fixed) |
| 75 | Kor Skyfisher (v1 mean): 2 mana 2/3 flier with a bounce ETB; better than most; Mind Stone (v1 mean): 2 mana rock that cashes in for a card later; Counterspell (v1 fixed); Farseek (v1 fixed) |
| 100 | Arcane Signet (v1 mean): 2 mana rock, any colour of the identity, no drawback; Sol Ring (v1 fixed); Swords to Plowshares (v1 fixed); Llanowar Elves (v1 fixed) |

**F Chulane synergy**

| value | anchor cards (source) |
|---|---|
| 0 | Winds of Rath (v1 mean): destroys all own creatures: works against the plan |
| 25 | Pacifism (v1 mean): creature-slot removal; no link to cast triggers, lands or bounce; Counterspell (v1 fixed) |
| 50 | Arcane Signet (v1 mean): good in any deck, nothing special here; Sol Ring (v1 fixed); Swords to Plowshares (v1 fixed); Farseek (v1 fixed); Cultivate (v1 fixed) |
| 75 | Elvish Mystic (v1 mean): 1 mana creature: casting it triggers Chulane, it ramps, it can be replayed; Llanowar Elves (v1 fixed) |
| 100 | Shrieking Drake (v1 mean): 1 mana creature whose ETB bounces an own creature: replays ETBs, re-triggers Chulane; Tireless Provisioner (v1 mean): creature, landfall engine, extra land drops pay off twice |

**T table impact**

| value | anchor cards (source) |
|---|---|
| 0 | Grizzly Bears (v1 mean): no effect on any opponent |
| 25 | Elvish Mystic (v1 mean): only you, small; Sol Ring (v1 fixed); Llanowar Elves (v1 fixed); Farseek (v1 fixed); Cultivate (v1 fixed) |
| 50 | Pacifism (v1 mean): answers one opponent's creature; Swords to Plowshares (v1 fixed); Counterspell (v1 fixed) |
| 75 | Hornet Queen (v1 mean): a board that deters attacks from all three opponents |
| 90 | Koma, Cosmos Serpent (v1 mean): uncounterable, makes a threat every upkeep, answers anything; no pool card reaches 100 on T |

**R reliability**

| value | anchor cards (source) |
|---|---|
| 0 | Mechanized Production (v1 mean): dead without a very specific artifact setup |
| 50 | Gilded Lotus (v1 mean): 5 mana rock: usually useful, but late and slow |
| 75 | Kor Skyfisher (v1 mean): useful in almost every game state; needs a permanent to return; Counterspell (v1 fixed); Farseek (v1 fixed); Cultivate (v1 fixed); Llanowar Elves (v1 fixed) |
| 100 | Arcane Signet (v1 mean): never a bad draw; Sol Ring (v1 fixed); Swords to Plowshares (v1 fixed) |

**K engine and combo potential**

| value | anchor cards (source) |
|---|---|
| 50 | Mistmeadow Council (proposal): own ETB (draw): can repeat through Chulane's {3},{T} bounce, but at a high price per loop |
| 75 | Tireless Provisioner (proposal): repeatable value engine: every land drop (Chulane gives extra ones) pays out; Primeval Bounty (proposal): every creature spell, so every Chulane replay, pays out again |
| 100 | Shrieking Drake (proposal): 1 mana self-bounce: with another ETB creature it re-casts and re-triggers Chulane for almost nothing |

**D low deck cost (100 = no risk)**

| value | anchor cards (source) |
|---|---|
| 0 | Winds of Rath (proposal): destroys the own creature engine; Wrath-style, symmetric |
| 25 | Rites of Flourishing (proposal): symmetric: every opponent draws and lands as much as you |
| 50 | Rampaging Baloths (proposal): 6 mana, GG, Wrath-exposed, but leaves tokens behind |
| 75 | Elvish Mystic (proposal): dies to every sweeper but costs 1 and is replaceable; one pip |
| 100 | Arcane Signet (proposal): no Wrath exposure, no symmetry, no self-damage, no colour strain |

**H holistic**

| value | anchor cards (source) |
|---|---|
| 25 | Gilded Lotus (v1 mean): v1 H 3.3: slow, expensive, special builds |
| 30 | Negate (v1 mean): v1 H 3.7: narrow counter |
| 45 | Cultivate (v1 fixed) |
| 50 | Reality Shift (v1 mean): v1 H 5.7: playable, 2 mana exile with a drawback |
| 55 | Farseek (v1 fixed) |
| 65 | Kor Skyfisher (v1 mean): v1 H 6.7: good, played in most strong lists |
| 65 | Counterspell (v1 fixed) |
| 75 | Avacyn's Pilgrim (v1 mean): v1 H 7.7: excellent |
| 80 | Llanowar Elves (v1 fixed) |
| 90 | Swords to Plowshares (v1 fixed) |
| 100 | Sol Ring (v1 fixed) |

#### Lands (judge a land as a land)

**E efficiency**

| value | anchor cards (source) |
|---|---|
| 0 | Maze's End (v1 mean): tapped, colourless, a Gate tutor with a high price |
| 10 | Reliquary Tower (v1 mean): colourless, no effect worth a slot |
| 25 | Sungrass Prairie (v1 mean): needs {1} each time it taps for mana; a filter; Selesnya Guildgate (v1 fixed) |
| 35 | Tranquil Cove (v1 mean): tapped dual with 1 life |
| 50 | Adarkar Wastes (v1 mean): untapped dual with 1 damage per colour tap; Evolving Wilds (v1 fixed) |
| 75 | Prairie Stream (v1 mean): check land: untapped early with two basics; Azorius Chancery (v1 mean): bounce land: two mana for one land card; Simic Growth Chamber (v1 fixed) |
| 100 | Command Tower (v1 fixed) |

**F Chulane synergy**

| value | anchor cards (source) |
|---|---|
| 15 | Maze's End (v1 mean): no link to the plan |
| 25 | Selesnya Guildgate (v1 fixed) |
| 35 | Tranquil Cove (v1 mean): no link to the plan |
| 40 | Adarkar Wastes (v1 mean): no link to the plan; colours only |
| 50 | Command Tower (v1 fixed); Prairie Stream (v1 mean): good in any deck |
| 75 | Evolving Wilds (v1 fixed) |
| 100 | Azorius Chancery (v1 mean): returns a land to the hand: a second land drop per turn cycle, landfall twice; Simic Growth Chamber (v1 fixed) |

**R reliability**

| value | anchor cards (source) |
|---|---|
| 35 | Maze's End (v1 mean): tapped and colourless |
| 50 | Reliquary Tower (v1 mean): colourless: hurts WUG costs; Sungrass Prairie (v1 mean): needs {1} to make coloured mana |
| 75 | Selesnya Guildgate (v1 fixed); Azorius Chancery (v1 mean): tapped, and needs another land to bounce; Evolving Wilds (v1 fixed); Simic Growth Chamber (v1 fixed) |
| 90 | Adarkar Wastes (v1 mean): untapped, two colours |
| 100 | Prairie Stream (v1 mean): two colours, untapped from turn 3; Command Tower (v1 fixed) |

**D low deck cost (100 = no risk)**

| value | anchor cards (source) |
|---|---|
| 25 | Maze's End (proposal): tapped, colourless, and a bounce cost in the effect |
| 50 | Reliquary Tower (proposal): colourless land strains a three-colour mana base; Tranquil Cove (proposal): enters tapped; Azorius Chancery (proposal): tapped and loses a land drop's tempo if no land to bounce |
| 75 | Adarkar Wastes (proposal): 1 damage per coloured tap |
| 90 | Prairie Stream (proposal): small risk of entering tapped early; no pool land without any cost is outside the pilot |

**H holistic**

| value | anchor cards (source) |
|---|---|
| 0 | Maze's End (v1 mean): v1 H 1.0 |
| 20 | Selesnya Guildgate (v1 fixed) |
| 25 | Tranquil Cove (v1 mean): v1 H 3.3 |
| 45 | Evolving Wilds (v1 fixed) |
| 60 | Prairie Stream (v1 mean): v1 H 6.3 |
| 75 | Azorius Chancery (v1 mean): v1 H 7.7 |
| 80 | Simic Growth Chamber (v1 fixed) |
| 100 | Command Tower (v1 fixed) |


Output rules: scores are multiples of 5 from 0 to 100 for E, F, T, R, K, D, H (higher is better, D = low deck cost, H is your own judgement, not the mean); notes: one phrase (at most 15 words) per score; reason: 2 to 3 sentences, what the card really does and what follows; confidence: high|medium|low; uncertainty: text (empty only for high); rule_claims: list of {quote (literal from the card block), interaction, claim, basis}; pattern_check: one entry per pattern hit shown {rule_id, verdict: correct|wrong|irrelevant}; judged_as: land|spell; schema: rubric-v2-card-rating-1; oracle_id and card copied from the block.
