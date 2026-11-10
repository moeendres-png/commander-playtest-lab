# Pilot: no tap of a mana ability that has no counters to add (2026-11-10)

Refs #1070. Draft, **not merged: a pilot change needs the Owner's explicit go.** Evidence class
`LOCAL_OBSERVED`, exploratory, no CI credit, counts and not win-rate estimates: **the win rate stays
UNDECIDED**. Follows from the round-robin of five real precons of `WIN_CONCENTRATION_2026-11-09.md`, in which
Eldrazi Unbound cancelled 2.79 casts per game against under 1 for every other deck.

## 1. The defect

A cast whose mana payment ends in "Cancel mana payment" spends the taps it already made and casts nothing. In
the 60 round-robin games (`main` `c7168078a`, all four seats, seeds 1-12) there were 167 such cancels, 134 of them
Eldrazi Unbound's. 78 of the 167 were the pilot tapping a mana ability that adds mana "for each counter" of a
kind its source no longer had:

- Everflowing Chalice, `{T}: Add {C} for each charge counter on {this}` (34 cancels);
- the storage lands (Mage-Ring Network), `{T}, Remove any number of storage counters from {this}: Add {C} for
  each storage counter removed this way` (44 cancels). The plain `{T}: Add {C}` of the same land was on offer
  in each of them.

The engine offers such an ability in a payment whatever the counters, taps the source and adds nothing. The
pilot's payment ranking saw a source that "adds mana" and, for equal-looking sources, broke the tie by label
order. The counters are board-public (`counters` on the battlefield entry), so this is a pilot-side read, not an
engine verdict.

## 2. The change

`src/commander_lab/engine/rules/full_game_pilot/common.py` and `payment.py`. Three small readers:
`counter_fuelled_mana_supply` (the counters of the kind a rule names, "for each X counter" or "where X is the
number of X counters", read off the permanent; `None` for any other rule and when the counters are not
reported), `mana_ability_yields_nothing` (a payment option whose source and rule give a supply of exactly 0) and
`permanent_mana_is_counter_starved` (every mana rule of a permanent is such a rule and all of them are at 0).

- A payment option that yields nothing is not put up for selection (`_choose_mana_option`, next to the
  existing "spends its own source" guards).
- A permanent whose whole mana is counter-fuelled and starved is not counted in `_available_mana` and
  `_mana_budget`.

Nothing else moves: a Chalice or a storage land with a counter, the plain ability of a storage land, a rule
that is not counter-fuelled and a permanent whose counters are not reported are read as before (an unreadable
rule is never turned into a zero). No card list, no weight, no new pilot term.

`tests/unit/test_pilot_counter_fuelled_mana.py`: 16 tests (reading the three rule shapes, unreported counters,
payment with Chalice and Mage-Ring Network, the budget, and the controls above). Three of them fail on the
code without the change. The 1319 pilot, payment, mana and ratchet unit tests pass (the Any-ratchet is
unchanged: the new signatures use `object` and `Mapping`).

## 3. Measurement

The same 60 games as the wipes and attack-target notes (five pods of four, seeds 1-12, deck order shifted by
`seed % 4`), same jar (sha256 `36167ba7...64a7`, pin `f4d12f6e80`), before = `main` `c7168078a`, after = this
branch. Cancels are read the way `pilot_decision_report` reads them (`_cancelled_cast_attempts`). Data:
`measurements-2026-11-10/counter_fuelled_mana_before_after_summary.json`.

| | Before | After |
|---|---|---|
| Cancelled casts, 60 games | 167 | 104 |
| ... Eldrazi Unbound | 134 | 73 |
| ... Token Triumph / Hosts of Mordor / Animated Army / Lorehold Spirit | 21 / 6 / 4 / 2 | 20 / 8 / 2 / 1 |
| Cancels after a storage-land ability without counters | 44 | 0 |
| Cancels after a Chalice tap without counters | 34 | 0 |
| Games with the same hash | | 26 of 60 |
| Games with the same winner | | 44 of 60 |

The 34 games whose hash changed are 18 with fewer cancels, 15 with as many and 1 with more; 10 of the 34 had
no cancel before (a wasted tap that did not end the cast still changes the sequence of taps). 12 of the 26
games that kept their hash had a cancel before, from causes this change does not touch (below). The 63 cancels
fewer are the 78 removed less 15 that appear elsewhere: in a game that has moved on, a later cast meets one
of the causes below instead. A trace of two changed games (pod 0 seed 8, pod 2 seed 6) shows the guard
firing only on a Chalice or a Mage-Ring Network entry with `counters: []`, 95 and 496 times.

Wins by deck over the 60 games (counts, not an estimate; one count is worth about +-3, the difference of two
counts about +-4), before to after: Eldrazi Unbound 17 to 14, Hosts of Mordor 17 to 16, Lorehold Spirit 12 to
15, Animated Army 9 to 11, Token Triumph 5 to 4. Inside the noise of 34 diverging games; no direction is
claimed. In particular this does not explain the win concentration of the round-robin (Token Triumph stays far
below, Eldrazi Unbound and Hosts of Mordor above their real rates): a deck that wastes fewer casts is not shown
to win less or more.

The 36-seed acceptance pod (seeds 1-36, `scripts/benchmark_xmage_full_games.py run ... --seeds 1-36 --workers 2
--games-per-jvm 9 --fast`, run once, `measurements-2026-11-10/real36_counter_fuelled_mana_b6f5de864_run1.json`)
against the reference of `823903239` (`compare`): `identical 33/36`, different in seeds 1, 18 and 25. Seed 1 keeps
its winner and its 2488 decisions, seed 18 keeps its winner (2904 to 2298 decisions), seed 25 changes the winner
(seat 3 to seat 1, 2675 to 2849 decisions); 35 of 36 winners are the same. 36 of 36 games finished. That pod
holds few of these cards, like it held few bounce lands; elapsed 422.4 s to 436.0 s with two workers, not a
speed claim. A twin run of the new reference has not been made (it follows a merge).

Chulane list (`data/decks/chulane_current.txt`): none of the cards above is in it. The change is about the
fidelity of the opponent decks, not about the owner deck.

## 4. What is left (not part of this change)

The 104 cancels after the change, by the cause read from the chosen labels:

| Cause | Cancels |
|---|---|
| Eldrazi Temple mana (`Spend this mana only to cast colorless Eldrazi spells or activate abilities of colorless Eldrazi`) tapped for a spell it cannot pay | 42 |
| Shrine of the Forsaken Gods (`{T}: Add {C}{C}. Spend this mana only to cast colorless spells.`) | 17 |
| Jaspera Sentinel (`{T}, Tap an untapped creature you control: Add one mana of any color`) left untapped | 19 |
| Other: single cases, Myriad Construct 8, Faithless Looting 3 (the wrong colour in the pool), Bitter Downfall 3 (one source), Teshar 2, Geode Golem 2, Crashing Drawbridge 2, six cards once | 26 |

The spend-restricted mana is the largest block and is a separate, larger reading (which spells a restriction
admits); it is not done here.

## 5. Not claimed

That the games get better (hash and cancel counts cannot say), a win rate, a card verdict, that the remaining
cancels are all pilot defects. After a merge the 36-seed reference is stale (`common.py` and `payment.py` are
watched files) and is replaced by a new reference run like the one after #1152.
