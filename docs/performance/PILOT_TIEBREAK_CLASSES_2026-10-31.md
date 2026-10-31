# Pilot: ties in targets, modes, trigger orders and colour picks (2026-10-31)

Refs #1090, #1070. Pilot-only change in `full_game_pilot/choices.py` (Python, no bridge, fork, pin
or sealed record), so no requalification. Win rate stays UNDECIDED.

## 1. Finding

Where the pilot's own ranking left the best two options with the same score, the alphabet decided:
the target ranking sorts by `(score, card name, action id)` in reverse, and the deterministic pilot
takes the largest action id on a tie of score and mana cost, which for a semantic option is its
label. Lands, land searches, planeswalkers (#1015) and discards (#1078) were already fixed.

## 2. Reach, counted before the change

A new full dump of the 24 real games (seeds 1 to 24, `54372d570`, bridge `bridge_v14`, 65 167
decisions) was replayed as played. The replay reproduced all 65 167 recorded answers, so the counts
below are the pilot's own scores while it answers, not read off the answers. Ties are the best two
options with equal score and different labels.

| Class | Requests with 2+ options | Tied at the top |
|---|---|---|
| target (not decided by the land search) | 928 requests, 772 rankings | 191 |
| trigger_order | 207 | 48 |
| mode | 48 | 17 |
| choice (colour pick without a need) | 626 | 32 |
| replacement_effect | 3 | 3 |

Every class is above the 1 % line of the draft. `choose_object` and `target_amount` share the
target ranking and have more ties (counted with the control below).

## 3. Change

- Targets: a group of equal scores that holds different card names is put in id order and shuffled
  with the decision's own seeded rng. Groups of one name keep their order; a land search or a
  discard keeps the ranking those steps made.
- Semantic options (`mode`, `trigger_order`, `replacement_effect`, the colour-pick fallback): the
  options that tie with the pilot's pick in rounded score and mana cost are reopened with
  `rng.choice` when their labels differ. A pilot with a temperature already chooses at random and
  is left alone.

The rng is the decision's own (`decision_offset`, class, seat), so a twin run draws the same and no
other decision's rng stream moves.

## 4. Controls

- Replay of the same 24 games with the new pilot (answers as played): 223 of 65 167 answers change,
  by class: target 128, choose_object 41, trigger_order 24, choice 15, mode 10, target_amount 5.
  All 223 are requests with a tie in the pilot's own ranking at some position; none changes
  without one. The other tied requests keep their answer (the rng picks the old one, or the tie
  sits below the options taken). The 11 other classes do not change at all: 0 of 62 469 answers,
  among them priority 0 of 49 390, mana payment 0 of 10 244, attack 0 of 1307, block 0 of 598 and
  mulligan 0 of 139; the 3 replacement effects tie and keep their answer.
- Unit tests `tests/unit/test_pilot_tiebreak_classes.py`: tied options are not taken in name order,
  the same seed gives the same pick for either offer order, a clear winner, equal names, a dearer
  option and a stochastic pilot are untouched.
- The fixture `tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz` was recorded again, and the
  tests that pin its counts follow (399 decisions, 7 trigger options, 4 costed prompts, 15.0 %
  fast path).

## 5. 36 seeds, twin run (`LOCAL_OBSERVED`, no CI credit)

Lab commit `3578aaa38` (the tests-only commits after it do not touch the watched paths), pin
`2ec507b721`, `bridge_v14`, 2 workers, `docs/performance/measurements-2026-10-31/` files
`real36_pilot_tiebreak_3578aaa38_run1.json` and `_run2.json`.

- 36 of 36 games finished; the twin runs have the same hash in 36 of 36 seeds (`compare`:
  `identical 36/36`).
- Against the reference of `b19a2562f`: hash equal in 0 of 36 seeds, which is expected (a tie shows
  up in nearly every game), and the same winner in 24 of 36.
- Decisions per game: mean 2693.5 before, 2688.6 after (paired difference mean -4.9, SD 597.7, 16 of
  36 shorter); median 2579.5 to 2639.0; range 1618 to 4176 before, 1847 to 4054 after.
- Winners by seat: 6/3/21/6 before, 4/4/20/8 after. That is one pod with its own four decks and 36
  seeds, not a fairness or strength measure.

A hash comparison cannot say whether the games got better. The change removes a name bias (the
same permanent, mode or trigger first every time); it does not add judgement. Where tied options
differ in value, the ranking that scores them is the next lever.

## 6. Not done

- The scores that tie are the pilot's; no ranking was improved here (for example a land against a
  creature as a target scoring alike).
- Priority ties (645 in the audit of 2026-10-25) and `choose_use` ties are not part of this change.
- The 36-seed reference of `REFERENCE_36_SEEDS_2026-10-31.md` is stale for the pilot after this
  merge; a new reference note follows from the run files above.
- The counting script is `reviews/gesamtpruefung-2026-10-30b/raw/tie_reach_1090.py` in the project
  folder, not in the repository.
