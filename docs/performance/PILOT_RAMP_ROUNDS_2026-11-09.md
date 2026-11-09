# Pilot: ramp terms decay with the game round (2026-11-09)

Refs #1070. A pilot change, so the hashes of every game with a ramp option move by design and the 36-seed
reference needs a new chain after the merge (section 5). Evidence class `LOCAL_OBSERVED`, exploratory fixed
seat, no CI credit, not a win-rate estimate: **the win rate stays UNDECIDED**.

## 1. Finding

`docs/performance/CHULANE_BASELINE_4P_2026-11-09.md` section 4 lists ramp cards that were castable and never
cast (Wood Elves 14 of 18 games, Rampant Growth 7 of 8, Talisman of Curiosity 8 of 12). The two ramp terms
in `BasePilot._base_components` decayed with `state.turn`, which is the engine's counter over every
player's turn. In a four-player pod it is about four times the number of turns the actor has taken, so
`1.7 - turn * 0.14` (mana efficiency) and `1.4 - turn * 0.12` (tempo) were spent by the actor's third turn.
From then on any dearer spell outranked a castable ramp spell.

Of the 73 (game, ramp card) pairs in the baseline in which a ramp card was castable within the actor's first
five turns, 42 were cast that same turn, 16 later and 15 never (21 %). Of the 31 pairs that were not cast at
once, 15 lost to a dearer spell, 10 to an equally dear or cheaper spell and 6 to a land play or a pass.

## 2. Change

`_game_round(state)` = `(turn - 1) // pod_size + 1`, used by exactly these two ramp terms. A one-seat pod is
unchanged. The other uses of `state.turn` in `pilots.py` (engine development up to turn 7, Rograkh up to
turn 2, Kaervek from turn 6) still read the raw counter; they were not part of the finding and are left
for a later look.

## 3. Measurement

Same jar (`bridge_main_5bd29ab6f`), same pods and seeds as the baseline (`mixed`, `precon`, `optimized`,
seeds 1-12, Chulane in seat 1, one JVM per game, 36 games), only the pilot differs. Summary files:
`docs/performance/measurements-2026-11-09/chulane_{mixed,precon,optimized}_seeds1-12_ramp_rounds_summary.json`.
All 36 games reached a terminal state. Semantic hashes equal to the baseline: 2 of 36 (expected).

| Chulane seat, 36 games | Baseline | With the change |
|---|---|---|
| Ramp castable in the first five own turns: cast the same turn | 42 of 73 (58 %) | 50 of 68 (74 %) |
| ... never cast | 15 of 73 (21 %) | 6 of 68 (9 %) |
| Ramp first castable later: never cast | 56 of 174 (32 %) | 47 of 157 (30 %) |
| Spells per own turn | 2.03 (924 / 456) | 2.01 (935 / 466) |
| Commander first cast, round (median / mean) | 6 / 5.83 | 5 / 5.49 |
| Most untapped sources in own turn 4 / 5 / 6 / 8 | 3.50 / 4.00 / 5.17 / 6.97 | 3.64 / 4.19 / 5.28 / 6.31 |
| Cancelled mana payments (seat counter) | 2 | 5 |
| Main phase passed with a castable spell | 1 | 2 |
| Needless chump blocks / attacks into a killer | 26 / 0 | 17 / 0 |
| Wipes cast / counters cast | 9 / 29 | 17 / 31 |
| Chulane wins (counts, not an estimate) | 5 | 4 |

Reading, within what these counts allow: the early ramp that used to be skipped is now cast, the number of
spells per own turn does not drop, and the commander comes down about a round earlier. The sources at turn
8 and the extra cancelled payments (one new card in the per-card list: Fleetfoot Panther in `mixed` seed 11;
Bennie Bracks and Wavesifter as before) and idle passes (`mixed` seeds 2 and 10) are not analysed: the
games diverge from the first ramp decision on, so one-to-one comparison is not possible, and the 12 games
per pod are too few to call a difference of one or two events a shift.

In the stateless rows of the real-request corpus (`tests/unit/test_pilot_real_request_corpus.py`) exactly
two priority answers change, both at round 5 of a four-player pod: Relic of Sauron instead of a land play and
Seize the Spoils instead of Naktamun Lorespinner. The other two changed rows are the earlier deliberate
ones (unfunded Chandra casts now declined); the test names all four.

## 4. Tests

`tests/unit/test_pilot_ramp_rounds.py` (14 tests): the round mapping, equal ramp terms for equal rounds
across pod sizes, a favoured ramp spell on the actor's fourth turn of a four-player pod, the bonus still
running out late, a non-ramp control that must not move with the turn, and the pilot's choice at own turn 4.
Three existing fixtures were adapted because a ramp-role card now wins early rounds as intended
(`test_full_game_pilot_judgment.py`: a ramp creature replaced by a plain two-drop in a test about the bigger
spell; `test_pilots.py`: two fixture values lowered).

## 5. After the merge

Hashes change by design: new 36-seed reference chain (twin run `identical 36/36`, `check-reference`, new
reference note), as after every pilot phase. Not part of this change: seat rotation, a paired candidate
comparison, a win claim.
