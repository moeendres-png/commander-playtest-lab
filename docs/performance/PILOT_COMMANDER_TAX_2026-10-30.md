# Pilot: commander tax in the view of a commander cast (#1040)

Measurement first, then a Python-only change of the pilot view. No bridge, fork, pin or sealed
record is touched, so nothing here needs requalification. Data rule: the decks of the real pod
are the project's own; no collection data is used.

## Measurement (before the change)

12 real-pod seeds, pin v13, the pilot of `5d85d2dc4`, `LOCAL_OBSERVED`
(`measurements-2026-10-30/commander_visibility_12seeds_tax_blind_pilot.json`):

| | |
|---|---|
| decision requests / priority requests | 37144 / 28083 |
| commander casts from the command zone offered / with tax (`casts_from_command >= 1`) | 176 / 110 |
| priority requests with a taxed commander option | 99 |
| answers that change when the cast is priced with its tax | 25 (all in 11 of 12 seeds) |
| control: answers that change without a taxed option | 0 |

The engine's cost facts of a commander cast leave out the tax, and the pilot priced a third cast
like the first. All 25 changed answers belong to one commander (Rograkh, a {0} creature): the
pilot stops recasting it for 2, 4 or 6 extra mana when a land, a planeswalker or another spell is
on offer (Narset, Ishai, Finale of Revelation, Swiftfoot Boots and others).

## Change

`full_game_pilot/state.py`: `_priority_action` adds `2 * casts_from_command` to `mana_cost` of an
option whose source is in the actor's own command zone (`_commander_casts` reads the actor's
own `commander_status` entry only, so no other player's commander taxes this view). Tests:
`test_commander_cast_view_carries_the_tax_of_earlier_casts` and
`..._has_no_tax_before_the_first_cast_or_for_other_cards` (first cast, other card, other owner).
The commander-visibility script now compares the live pilot with the same pilot with the tax
hidden; replaying the 12 dumps gives the same 25 changed answers and 0 in the control, so the
code does what the measurement priced.

## Paired result, 36 real-pod seeds, same jar and decks (`real36_tax_visible_1040_run1.json`)

- 36 of 36 games finish. 31 of 36 hashes differ from the reference run `real36_v14_...run1`
  (`5d85d2dc4` pilot): the changed answers shift the whole game stream, as with every pilot step.
  In the other 5 seeds no answer changed.
- Behaviour signature: the 25 answers above (commander cast replaced by another play), all in the
  deck of the commander named above; the replay of the 12 dumps changes no other answer (priority requests only are replayed, the only class the tax enters).
- Winners by seat 4/1/22/9 before, 4/3/19/10 after. That is one pod with its own four decks, 36
  games, not a strength measure: the win rate is UNDECIDED (36 paired games give no power for a
  win-rate claim).
- Median decisions per game 2819 -> 2709.

The 36-seed reference `REFERENCE_36_SEEDS_2026-10-29.md` is stale for the pilot after this
change (the staleness check says so); a fresh twin-run reference is a separate step.

The fixture `real_pod_v1` is re-recorded (2 seeds, the new pilot), and the counts in
`test_measure_commander_visibility.py` follow it.
