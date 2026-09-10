# RQ-C1 Redundancy Adjudication

Adjudicator: `foundry-adjudicator` at XHIGH (read-only draft-plan review) +
implementer verification at authoring time. Verdicts persisted here.

Rule: two cases are redundant only when they share the Rules question AND the
decision surface AND the hidden/identity/RNG boundary. Shared cards alone are
never redundancy (see challenged pairs below: all KEEP).

## Challenged pairs (all KEEP, complementary)

| Pair | Verdict | Reason |
| --- | --- | --- |
| A03 vs E03 | KEEP | optional-replacement+cost vs deathtouch-lethal+SBA; different decisions and boundaries |
| D03 vs H02 | KEEP | stack/legality/survival vs layer-7 timestamp dependence; different axes |
| C02 vs I03 | KEEP | cost-timing isolation vs token/trigger interleave; same card, different axes; assertions kept separate |
| H01 vs K02 | KEEP | layers copy-vs-Humility vs legend-rule controller gating; different layers |
| D04 vs H01 | KEEP | copy-choice+trigger vs copy-vs-Humility layers; different questions |
| B04 vs K01 vs I03 | KEEP | source-movement fan-out vs mass-APNAP accounting vs token lifecycle; three trigger boundaries sharing Artist harness as cost optimization |
| D01 vs D06 | KEEP | choose-two (6 combinations, fixed count) vs choose-one-or-more (31 subsets, variable count + 5 target types); distinct modal cardinalities stressing fixed-count vs variable-count mode logic; identical coarse matrix rows, distinct Rules questions |
| D03 vs D05 (division authority) | KEEP | rules-determined even division (Fireball, no chooser) vs chooser-divided partitions (Rolling Thunder); opposite division authority is the point |
| G02 vs G03 | KEEP | movement/tax vs damage/loss; G03 ships with PRE_DECISION-construction seeding redesign |

## Cuts (1)

- RQ-C1-D02 Boros Charm (choose-one modal): REJECTED_REDUNDANT per XHIGH
  adjudication. Choose-one cardinality subsumed by D01 (choose-two) + D06
  (choose-one-or-more); planeswalker-target nuance hits no listed candidate
  gap. ID RQ-C1-D02 reassigned to the added Twincast spell-copy scenario
  (no collision; reassignment recorded here).

## Adds (1, net 40)

- RQ-C1-D02 Twincast + Lightning Bolt (spell-copy on the stack with new
  targets): fills the permanent-copy-only gap (D04/H01/K02 are 707.2-class;
  nothing was 707.10-class). Falsifies copy-which INDEX without target offer
  and stack-identity confusion.

## Redesigns (2, not rejections)

- G03 commander-damage seeding: PRE_DECISION_CONSTRUCTION ledger seeding +
  native final hit (WS51 gate; mid-combat injection forbidden).
- K02 legend rule: redrafted from same-controller transit to cross-controller
  coexistence (same-controller-only gating is itself the asserted
  discriminator); same-controller dies-fire half gated as second path.

## Corrections during authoring (2)

- B04/G02 destroyer Doom Blade -> Murder: Doom Blade cannot target Kokusho
  (black) and should not target black commanders; Murder text UNVERIFIED,
  must be Oracle-confirmed before execution.
- D06 artifact Ornithopter: text UNVERIFIED general knowledge; any vanilla
  artifact substitutes; Oracle-confirm before execution.

## Incidence verification (mechanic/decision/rules-axis)

Full incidence data: `RQ_C1_DECISION_SURFACE_MATRIX.csv` (40 x 29 decision
kinds) and `RQ_C1_RULES_AXIS_MATRIX.csv` (40 x 14 reverser axes). No two
scenarios share identical rows in both matrices (verified by validator:
pairwise row-equality check would fail the build; see `validate_rqc1.py`).
Minimum axis depth: every reverser axis appears in >= 2 scenarios; every
required corpus axis A-K has >= 2 families except H (2: H01/H02, both
VERY_HIGH) and K (2: K01/K02, both HIGH+).

## Deferred (not removed)

- Random-order RNG: no useful executable actual-card case identified; DEFERRED
  with rationale (forced-order cases would be synthetic, not Rules RNG).
- Text-changing layer 3 (Artificial Evolution), partner/random-fan-out (Vial
  Smasher), phasing coin (Frenetic Efreet), commander mana (Command Tower),
  extra turns (Time Warp): DEFERRED second-wave candidates (see Q6 consumption).
