# Pilot game mining: what is left of P1-P11, ranked (2026-10-30)

Refs #1029, #989. Source: Muse's report (`handover/2026-10-26/pilot-next/report.md` on
`muse/claude-handover`, commit `ba265d69c`, taken on `6fb26071b`, pin v13) reviewed, brought to
today's `main` (`692847dab`, pin `2ec507b721`, v14) and re-counted on a fresh 24-seed dump. Report
only: no pilot code changed. Pod profile casual/mid. Evidence class `LOCAL_OBSERVED`, no CI credit.

## 1. Review of the report

- Arithmetic: 11 (P1-P11) + 13 (further research items) + 7 (measured and dropped) + 1 (in flight) +
  3 (merged without a P row) = 35 rows, as the report says.
- Status claims checked against the merged PR bodies: #1010 (own upkeep/draw instants 186 → 29,
  spells per player round 1.22 → 1.34 with CI +0.07..+0.17, postcombat deployment not implemented,
  "next: hold mana for instants") and #1027 (Bitter Downfall cancels 23 → 0, all cancels 43 → 20,
  decisions 72,021 → 70,874 on 24 seeds) agree with the report. The 70,874 decisions are also the
  size of Muse's main dump, so the dump is the one #1027 measured.
- The Phase 4a control: Muse could not reproduce the exact integers 186/313 (other seeds, the
  denominator is not defined in #1010) and says so; the contrast reproduces on both sides (pre 68.5 %
  early instants, post 8.3 %). Accepted as "reproduced in profile, integers explained".
- Counts: the counting script was not in the repository. It is now `scripts/pilot_dump_reach.py`
  (rules in English, test on the recorded fixture, slices of one run accepted). On the 24 seeds
  below it returns the same numbers as Muse's script (checked class by class, all reach rows).

## 2. What changed since the report (merged after `6fb26071b`)

| PR | What | Touches |
|---|---|---|
| #1031 | mana held back for a counterspell or removal in hand (Phase 4a-2): counter and cheap-removal casts +10 %, win rate UNDECIDED | P2 remainder, report block D ("in flight") is now merged |
| #1041 | mana budget excludes self-tap and sacrifice | payment volume |
| #1044 | real archetype deltas for the graveyard and artifact pilots | deck-level, not a P row |
| #1036, #1037, #1038 | dead Korvold special cases removed, card catalog fails closed, mulligan refit on the 173 decks (evaluation, baseline unchanged) | P11 (evaluation only) |
| #1062 | a commander cast is priced with its commander tax (25 of 99 answers with a taxed option change, all Rograkh) | priority, not a P row |

Rows of the report that move: P2 stays "partly" with the mana-hold part merged (the rest is
postcombat deployment of sorcery-speed permanents); block D is closed; everything else keeps the
status of the report.

## 3. Reach on today's `main`

24 real-pod games, seeds 1-24, bridge jar `035a5b4e…` (pin `2ec507b721`), `pilot_request_corpus.py
record --all --seeds N` per seed; counted with `scripts/pilot_dump_reach.py` over the 24 slices.
File: `docs/performance/measurements-2026-10-30/pilot_dump_reach_main_692847dab_24seeds.json`.
66,699 decisions (2,779 per game), 54.96 MB. The report's numbers (other pin, other pilot) next to
them; the games differ, so the columns show scale and rank, not a trend.

| Row | Report (24 games) | Today (24 games) |
|---|---|---|
| P4 fast path: mana_payment decisions | 11,570 (16.3 %) | 10,539 (15.8 %) |
| P0-2 / P1: target decisions, with ≥ 2 options | 1,134 / 884 | 1,089 / 842 |
| P1-2: postcombat candidates, wipes offered | 1,186, 45 | 1,135, 50 |
| P1-3 / P2: opponent-turn pass with an instant offered | 363 | 366 |
| P8: declare_attacker + declare_blocker | 1,337 + 555 = 1,892 | 1,283 + 514 = 1,797 |
| P0-3: trigger_order (all with a choice) | 184 | 242 |
| P3: choose_use with a cost word / all | 79 / 644 | 101 / 656 |
| P10 / P1-4: announce_x + multi_amount (X > 0) | 80 + 68 (32) | 55 + 41 (38) |
| P11 / P1-5: mulligan decisions | 139 | 139 |
| Phase 4a window: own upkeep/draw instants of all instant casts | 19 of 230 (8.3 %) | 14 of 206 (6.8 %) |

Not countable from a dump (unchanged): P5 profiling, P6 instrumentation, P9 replication, P1-1 combo
recognition, P1-6 relative noise, P2-1 roles, P2-2 external priors (and Owner-blocked), P2-3 risk,
P0-1 unset inputs, and the content of the hand for mana-hold decisions.

## 4. Ranking (reach × feasibility)

Feasibility: Python only, testable on recorded requests, measurable on paired real games. Win rate is
only reported when paired power carries it, otherwise "UNDECIDED, could only see effects of at
least X" (24 pairs: win rate effects from about 25 points; 0.07 spells per player round).

1. **P4 fast path** (10,539 decisions, 15.8 %): a fixed rule for the most common payment shape.
   First step: shape census on the recorded rows. Dead end: the most common shape covers < 20 % of
   the rows or agreement with the solver is < 99 %. It is a speed change; answers that change are a
   correctness question, not a gain.
2. **P0-2 threat ladder** (842 target decisions with a choice): ladder for one dimension (clocks).
   Dead end: < 5 % of the choices change.
3. **P1-2 postcombat default for sorcery-speed permanents** (1,135 candidates, 50 wipe offers): the
   piece #1010 left out; the mana-hold part is done (#1031). Paired games are mandatory.
4. **P8 remainder** (1,797 decisions): only "attack at all" as one gate. Dead end: ≥ 80 % of paired
   games bit-identical, as #1022 (42 of 48) and attack planning already showed.
5. **P0-3 trigger order as a class rule** (242, all with a choice, up from 184): small and fully
   replayable on the recorded rows; the rule must stay class based, no card lists.

Next row: P3 costed may-abilities (101), P10 X breakpoints (55 + 41), P11 development score (needs P6).

My pick for the next pilot phase is P0-3, then P1-2: P0-3 is cheap to prove on recorded rows
and its reach grew by a third; P1-2 is the largest open timing item. P4 first would be the biggest
reach but changes nothing about play and carries a correctness risk, so it waits for a decision.
