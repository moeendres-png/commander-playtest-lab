# Pilot against published real-player numbers (2026-11-09)

Refs #1070. Measurement only: no pilot, bridge, fork, pin, deck or sealed record changes, so nothing here
needs requalification or a new reference. Evidence class `LOCAL_OBSERVED`, exploratory fixed seat, no CI
credit, not a win-rate estimate: **the win rate stays UNDECIDED**.

## 1. Sources and what they are

Real numbers: aggregate public pages of Playgroup.gg ("Live Play Data", Commander games, mostly 4-player
pods), published under CC BY 4.0, attribution Playgroup.gg, retrieved 2026-11-09 (robots.txt allows
retrieval, no scraping prohibition on the legal page). Raw game events are not public; only per-card and
per-deck aggregates. Pages used: `https://playgroup.gg/cards/<slug>` for 22 ramp and card-advantage staples
(staples that many decks play, no deck reference) and `https://playgroup.gg/commander/precons` (Last Updated 2026-11-08). The numbers are in
`docs/performance/measurements-2026-11-09/playgroup_card_stats_2026-11-09.csv`. Limits: the pages do not define
"turn" (own turn or game turn), the sample is self-selected tracker users, win-rate gaps are correlational.

Our numbers: the 36 games of `docs/performance/CHULANE_BASELINE_4P_2026-11-09.md` pods (`mixed`, `precon`,
`optimized`, seeds 1-12) on `main` `e3927abc0` (pilot with the ramp-rounds change of #1149), same jar, all four
seats evaluated, hashes equal to the earlier run of the same code (36 of 36).

## 2. Ramp: share cast on the turn the card first became castable

Real: cast on the turn the card was drawn. Ours: cast on the own turn it was first castable (biased in our
favour, because a missing mana does not count against us). Pairs are games times seats.

| Card | Real | Ours (pairs) | Never cast |
|---|---|---|---|
| Sol Ring | 83 % | 91 % (47) | 1 |
| Llanowar Elves | 73 % | 71 % (17) | 1 |
| Arcane Signet | 52 % | 61 % (59) | 7 |
| Fellwar Stone | 50 % | 46 % (39) | 9 |
| Rampant Growth | 43 % | 50 % (14) | 6 |
| Nature's Lore | 37 % | 43 % (14) | 8 |
| Sakura-Tribe Elder | 45 % | 67 % (24) | 3 |
| Wood Elves | 43 % | 14 % (14) | 9 |
| Thought Vessel | 51 % | 25 % (12) | 3 |
| Elvish Mystic | 72 % | 47 % (17) | 3 |
| Gilded Lotus | 32 % | 11 % (9) | 7 |
| Farseek | 45 % | 25 % (8) | 2 |
| Thran Dynamo | 36 % | 18 % (11) | 7 |
| Talisman of Curiosity | 46 % | 33 % (12) | 5 |

Cheap staples are in the real range. Seven ramp cards below the real range (Wood Elves, Thought Vessel, Gilded Lotus, Farseek,
Thran Dynamo, Talisman of Curiosity, Hedron Archive) together: 25 % against 41 % real (79 pairs, gap 16 +- 5
points). In the windows inspected (`mixed` seed 7, seat 3) the pilot spent the mana on the commander (utility
12.2 and 12.7 against 5.9 and 6.1 for the stone) or on a wipe (16.1 against 6.1); raising the ramp strength of
dear stones from 0.6 to 1.0 adds about 0.7 and does not flip those windows. No change is proposed from
4 to 14 pairs per card.

One real sequencing defect: a bounce land is played before spells. In 28 windows with a castable spell the
pilot played a bounce land first; in 5 of them no spell was cast afterwards (for example `mixed` seed 7,
Chulane, own turn 4: Simic Growth Chamber returned the only Forest, Wood Elves was no longer castable). 5 lost
turns in 36 games.

## 3. Wins against real precon rates

Real: Playgroup precon list, normalized to a 4-player baseline of 25 %, at least 20 games from at least 10
pilots. Sim: wins of the deck over the games it sat in (counts, not an estimate).

| Deck | Real | Sim before #1149 | Sim now |
|---|---|---|---|
| Animated Army | 21.6 % (656 games) | 2 of 24 | 5 of 24 |
| Lorehold Spirit | 27.3 % (535) | 12 of 24 | 12 of 24 |
| Token Triumph | 26.5 % (197) | 3 of 12 | 4 of 12 |
| Eldrazi Unbound | 24.7 % (285) | 1 of 12 | 2 of 12 |
| The Hosts of Mordor | 19.6 % (396) | 10 of 12 | 6 of 12 |
| Chulane (candidate) | - | 5 of 36 | 4 of 36 |
| Kaervek (verified list) | - | 2 of 24 | 3 of 24 |

With 12 games a 25 % rate is known to about +- 12 points. Hosts of Mordor (10 of 12 before) and Lorehold
Spirit (12 of 24) are far above their real rates; the ramp change moved Animated Army and Hosts of Mordor
towards them. Turn order: real 4-player pods give seat 1 about 29 % and the last seat about 21 % (FAQ of the
turn-order page, no counts); in the sim every seat starts equally often (9 of 36) and wins by turn-order
position are 7, 9, 9, 11 of 36, no first-player advantage visible (too few games for more).

## 4. Not claimed, next

Not claimed: why Lorehold Spirit and Hosts of Mordor win so often in the sim, a card verdict, a win rate.
Candidates for a next measurement: behaviour signatures per deck (tokens, ring, combat, commander timing)
for these two decks; a small draft change that casts spells before a bounce land.
