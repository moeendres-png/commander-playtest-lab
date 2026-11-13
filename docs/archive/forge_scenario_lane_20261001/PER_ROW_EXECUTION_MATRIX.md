# Per-row execution matrix (issue #455, epoch 20261001)

Machine-readable authority: `receipts/STRUCTURAL_CENSUS.json` (all 107 rows) and
`receipts/EXECUTION_RECEIPT.json` (16 attempted rows, full per-row pipeline).

Every attempted row carries the 18-step pipeline independently:
fixture identity, obligation identity, requested-state identity + dimensions,
Lab source identity, Rules-Core identity, bridge identity, runner identity,
transport result, scenario parse result, native bootstrap result, readback,
checkpoint equivalence (field-level), pending decision frame, external decision
selection, semantic events, terminal facts (drive + obligation), receipt
eligibility, final classification. Nothing is collapsed into one boolean.

## Structural census over the effective 107-row denominator

Contract: `commander-lab.full107/1.0.9-successor`.

| Class | Rows |
| --- | --- |
| `UNSUPPORTED_DIMENSION` (≥1 requested field not representable) | 94 |
| Constructible but not observable on the generic readback | 4 |
| Credit-eligible (constructible + observable at requested checkpoint) | 9 |

The 9 credit-eligible rows: `MICRO_LAYERS`, `WS05-MP-ELIM-OWNED-3`,
`WS05-MP-ELIM-PRIO-3`, `WS05-MP-ELIM-5`, `WS05-CMD-DMG-SPLIT`,
`WS05-CMD-PARTNER-DMG`, `WS05-CMD-PARTNER-ZONE`, `WS05-CMD-START-2`,
`WS05-CMD-START-3`.

The 4 constructible-but-not-observable rows: `MICRO_CONTROL`,
`WS05-MP-TURN-3`, `WS05-MP-TURN-5`, `WS05-MP-ELIM-CONTROL-3`.

## Runtime attempt (16 rows, exact pinned Forge bridge)

| Fixture | Classification | Checkpoint | Receipt |
| --- | --- | --- | --- |
| MICRO_COPY | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| MICRO_COSTS | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| MICRO_MODES | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| MICRO_REPLACEMENT | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| MICRO_ZONE_CHANGES | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| WS05-MP-BLOCK-4 | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| WS05-MP-COMBAT-4 | `UNSUPPORTED_DIMENSION` | `UNSUPPORTED_DIMENSION` | not eligible |
| MICRO_LAYERS | `OBLIGATION_NOT_OBSERVABLE` | `EXACT` | not eligible (no observation contract) |
| WS05-MP-ELIM-OWNED-3 | `EXECUTED_OBLIGATION_OBSERVED` | `ALLOWED_VARIANCE` (fixture-declared cause) | **eligible** |
| WS05-MP-ELIM-PRIO-3 | `EXECUTED_OBLIGATION_OBSERVED` | `ALLOWED_VARIANCE` (fixture-declared cause) | **eligible** |
| WS05-MP-ELIM-5 | `EXECUTED_OBLIGATION_OBSERVED` | `ALLOWED_VARIANCE` (fixture-declared cause) | **eligible** |
| WS05-CMD-DMG-SPLIT | `EXECUTED_OBLIGATION_OBSERVED` | `EXACT` | **eligible** |
| WS05-CMD-PARTNER-DMG | `EXECUTED_OBLIGATION_OBSERVED` | `EXACT` | **eligible** |
| WS05-CMD-PARTNER-ZONE | `EXECUTED_OBLIGATION_OBSERVED` | `EXACT` | **eligible** |
| WS05-CMD-START-2 | `OBLIGATION_NOT_OBSERVABLE` | `EXACT` | not eligible (no observation contract) |
| WS05-CMD-START-3 | `OBLIGATION_NOT_OBSERVABLE` | `EXACT` | not eligible (no observation contract) |

### Executed obligations (engine facts only)

* `WS05-CMD-DMG-SPLIT` / `WS05-CMD-PARTNER-DMG`: the engine's own
  `commander_damage_received` map showed 11 + 10 (respectively 12 + 9) from two
  distinct partner commanders to P2, aggregate ≥ 21, no single commander ≥ 21,
  and no loss applied. Terminal facts recorded per row.
* `WS05-MP-ELIM-*`: the declared zero-life seat is `lost` in the engine's own
  terminal outcome, its controlled permanents are gone, and the live-player ring
  excludes it. The requested pre-cause coordinates (life 0, pre-loss
  permanents/priority) are a fixture-declared
  `NATIVE_CAUSE_DECLARED_PLAYER_LOSS` transition; the variance source is recorded
  per field as `CAUSE_ADVANCE`, never as EXACT.
* `WS05-CMD-PARTNER-ZONE`: both partner commander identities observed in their
  command zone at the first observable checkpoint.

### Executed but not observed by this lane (exact gaps, not PASS)

* `MICRO_LAYERS`: checkpoint `EXACT`, but the required layer events
  (`layer6_remove_abilities`, `layer7b_set_pt`, `layer7c_modify_pt`) have no
  observation contract on the generic projection (only terminal P/T is
  projected). Executing it needs a layer-event observation contract.
* `WS05-CMD-START-2` / `WS05-CMD-START-3`: checkpoint `EXACT`, but the required
  draw-step events are already owned by the shared START-2 path; this lane does
  not duplicate that contract.

### The seven-row wave: exact blockers (no credit, no fixture weakening)

| Fixture | Exact blockers proven this run |
| --- | --- |
| MICRO_COPY | `stack_state` + stack-zone objects; live engine rejection `scenario must not inject stack` |
| MICRO_ZONE_CHANGES | `stack_state` + stack-zone objects; live engine rejection `scenario must not inject stack` |
| MICRO_COSTS | `temporal_state.active_player` (P2 active at turn 1 is unreachable), `action_cost_state` (mid-cast cost state has no field), `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_objects`; live silent-ignore proof |
| MICRO_MODES | `action_cost_state`, `decision_execution.priority.semantic_action`, `decision_execution.choose_mode.semantic_mode_key`, `temporal_checkpoint.exact_hand_after_draw`; live execution showed the requested hand cannot survive the natural draw step (field-level `hands.p1` mismatch) |
| MICRO_REPLACEMENT | `combat_state`, `temporal_state.combat_step` (bootstrap-placed attackers are summoning-sick); live silent-ignore proof |
| WS05-MP-BLOCK-4 | `combat_state`, `temporal_state.combat_step`, `decision_execution.declare_blocker.blocker_assignment`; live silent-ignore proof |
| WS05-MP-COMBAT-4 | `combat_state`, `temporal_state.combat_step`, `controlled_since_turn_began`, `decision_execution.declare_attacker.attacker_assignment`; live silent-ignore proof |

These seven rows are **not** blocked by an unexercised Lab execution path of the
kind the pre-lane classification described: the seam was exercised, and the
remaining blockers are exact fields the pinned bootstrap does not model.
