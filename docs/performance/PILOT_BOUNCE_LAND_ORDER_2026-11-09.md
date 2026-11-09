# Pilot: bounce land after the spells (2026-11-09)

Refs #1070. Draft, **not merged**: a pilot change needs the Owner's explicit go. Evidence class
`LOCAL_OBSERVED`, exploratory, no CI credit, not a win-rate estimate: **the win rate stays UNDECIDED**.
Follows from section 2 of `PILOT_CALIBRATION_REAL_PLAYERS_2026-11-09.md` (the one real sequencing defect).

## 1. The defect

A bounce land (Simic Growth Chamber, Gruul Turf, Rakdos Carnarium, Selesnya Sanctuary, Azorius Chancery)
enters tapped and returns a land you control to its owner's hand. The pilot scores every land play the same,
above most casts, so the bounce land came first. Played first it takes a land, and its mana, out of the turn:
`mixed` seed 7, Chulane, own turn 4, Simic Growth Chamber returned the only Forest and Wood Elves could no
longer be cast. In the 36 Chulane-pod games (all four seats, `mixed`, `precon`, `optimized`, seeds 1-12) there
were 28 own turns in which a bounce land was played first although a spell was castable, and in 5 of them no
spell was cast afterwards.

## 2. The change

`src/commander_lab/engine/rules/full_game_pilot/priority.py` and `full_game_pilot_lands.py`. While a spell is on
offer in a priority window, the bounce-land plays are not put up for selection (`returns_a_land` reads the card
text: "When this land enters, return a land you control to its owner's hand"). They come back once no spell is
left on offer. If the pilot chooses to pass with the bounce land held back, the pilot's own utility of the land
against passing decides, as before, so the land drop is not lost to this rule. Basic lands, tapped lands that
return nothing and Karoo-style lands are untouched. No card list, no weight, no new pilot term.

`tests/unit/test_pilot_bounce_land_order.py`: 20 tests (card reading, held land with the rule switched off as a
control that the fixture reproduces the old order, no spell on offer, basic land and Evolving Wilds still first,
pass in place of a held land, a pass the pilot preferred stays a pass). The 1246 pilot-related unit tests pass.

## 3. Measurement

Same 36 games as the calibration note, same jar (sha256 `36167ba7...64a7`, pin `f4d12f6e80`), before = `main`
`cdda035af`, after = this branch. All four seats. Data: `measurements-2026-11-09/bounce_land_order_before_after_summary.json`.

| | Before | After |
|---|---|---|
| Own turns with a bounce land played first and a spell castable | 28 | 0 |
| ... of which no spell cast afterwards that turn | 5 | 0 |
| Games with the same hash | | 14 of 36 |
| Games with the same winner | | 28 of 36 |
| Main phase passed with an unplayed land (all seats, after) | | 0 |

The 22 games whose hash changed are exactly the 22 games that had such a turn before (no game without one
changed, no game with one stayed equal), so nothing else moved. On the first affected own turn of each of the 22
games, where the game state is the same before and after, 33 spells were cast before and 36 after. Over the whole
changed games the Chulane seat's spells per own turn went from 2.01 to 1.93 (paired difference -0.115 with a
standard error of 0.106, mean rounds +0.07 +- 0.34): inside the noise of 22 diverging games, not claimed in
either direction. Wins by deck (counts, not an estimate), before to after: Lorehold Spirit 12 to 11, Hosts of
Mordor 6 to 7, Animated Army 5 to 6, Chulane 4 to 6, Token Triumph 4 to 3, Kaervek 3 to 2, Eldrazi Unbound 2 to 1.

## 4. If it is merged

`check-reference` reports the 36-seed reference stale (the two watched files above). The chain is the one of
`REFERENCE_36_SEEDS_2026-11-09.md`: two 36-seed runs with the same jar, `identical 36/36`, new reference note,
`REFERENCE_DOC` and the test strings. No bridge, fork, pin or sealed record is touched, so no requalification.

## 5. Not claimed

That the games get better (hash and spell counts cannot say), a win rate, a card verdict. The `Karoo` family
("sacrifice unless you return an untapped Plains") is not read; no deck of the pods has one.
