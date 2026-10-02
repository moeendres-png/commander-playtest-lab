# MICRO_COSTS: control-history fixture erratum (CR 302.6)

Status: **ADJUDICATED**. Recorded in `FULL107_SUCCESSOR_CONTRACT_v1_0_18.json`. The
carried MICRO_COSTS erratum's class becomes `FIXTURE_DEFECT_CORRECTION_CR307_1_CR302_6`.
`PRODUCTION_PROVIDER = NOT_SELECTED`, `ARCHITECTURE_FREEZE = NOT_CLAIMED`.

Adjudicated by the Claude campaign session acting as sole project executor and
temporary technical Coordinator (owner instruction, 2026-10-02). A newer owner or
Coordinator ruling supersedes it.

## Finding

The 1.0.7 CR 307.1 erratum made P2 the active player of turn 1, so that P2 can cast
the sorcery Hex. It did not touch the record's control history. The record still
requests `controlled_since_turn_began: true` for every battlefield permanent:

| Object | Controller |
|---|---|
| `obj:P1-commander` | P1 |
| `obj:micro-cmd-b` | P1 |
| `obj:cost-a` | P1 |
| `obj:cost-c` | P3 |
| `obj:cost-d` | P4 |

CR 302.6 asks whether a permanent has been under its controller's control
continuously since that player's most recent turn began. On P2's turn 1, P1, P3 and
P4 have had no turn in this game, so no legal history gives their permanents that
status.

Until #484 the vehicle never checked this. Its placement primitives cleared summoning
sickness unconditionally, so the impossible value passed unverified. The first-turn
setup ruling (`PLACEMENT_POINT_ADJUDICATION.md`) stops that, and the checkpoint now
verifies the request:

- the three Bears failed closed with `controlled_since_turn_began ... requested true
  observed false`;
- the battlefield commanders went unverified until this change, which added them to
  the verification.

## Correction

- The five requests above are corrected to `false`, the only reachable value.
- P2's permanents keep `true`. They are the turn-1 active player's, and their turn
  began with them on the battlefield.
- Nothing else in the record changes.
- **Obligation unchanged.** The obligation digest is unchanged: Hex's six targets,
  the `cost_determined:base_plus_3_generic` event and the commander-tax
  postcondition. None of them depends on summoning sickness.
- **Lineage.** The original CR 307.1 step and the temporal correction are kept
  byte for byte. The CR 302.6 step is appended with each corrected object's
  predecessor value. The requested-state digest changes explicitly
  (`predecessor_invalidity.controlled_since_turn_began`).
- **Evidence.** No evidence transfers; the row needs fresh direct evidence.

## Other rows

A survey of the effective materialization, covering the denominator and the AF07
corpus, finds three more records that request an unreachable `true`:

- MICRO_PREVENTION: P2's Forest on P1's turn 1;
- MICRO_PRIORITY: the same;
- MICRO_STACK: the same.

None of them runs on the restoration lane today. All three are native micro rows,
and the gap is recorded here for the workstream that will route them (#456). Once
one is routed through the restoration, the checkpoint verification refuses it
fail-closed. The restoration never accepts or sets the value.
