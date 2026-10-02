# Phase 2 — current-main reconciliation and shared-chain integration

`FORGE-CURRENT-BOUNDARY-SCENARIO-LANE-20261001` (issue #455, PR #464)

Phase 1 (contract `1.0.9-successor`, Lab `ffa0e910`) is preserved unchanged in
`receipts/` and in the workstream state file as historical evidence for its own
source epoch. Phase 2 merged current main and integrated the producer into the
shared current-boundary evidence chain.

## Source reconciliation

* Merge commit: `3d9d14e3f8979deaea4a96240883eefc12d5c72b`
  (`Merge current main (99a5ecd0, contract 1.0.15) into forge scenario lane`).
* Merged main: `99a5ecd012d5a9c22d700464e41cd18328d94451`, contract
  `commander-lab.full107/1.0.15-successor`.
* The merge was a normal merge; the branch added only new dedicated files, so
  there were no conflicts and no rebase was performed.
* The pinned Forge identities did not move:
  Rules-Core `bb0a740d…` (tree `4989b5bb…`), bridge `20e3e1f7…`
  (tree `000066890d…`), ScenarioBootstrap source sha256 `9ae04d53…`.

## Re-derived census (not copied from Phase 1)

The 107-row structural classifier was re-run against the current effective
materialization before any engine execution:

```text
contract   commander-lab.full107/1.0.15-successor
denominator 107
counts     94 UNSUPPORTED_DIMENSION / 4 CONSTRUCTIBLE_NOT_OBSERVABLE / 9 CREDIT_ELIGIBLE
```

The two class memberships are identical to Phase 1. The per-row diff is in
`receipts/PHASE2_CENSUS_DIFF.json`; six rows changed semantically, all AF05
hidden-information rows whose fixtures were rewritten after the Phase-1 epoch:

| Row | Change |
| --- | --- |
| `HIDDEN_09` | knowledge/face-down blockers replaced by action-cost and priority activation blockers |
| `HIDDEN_10` | new action-cost + choose-object mechanics |
| `HIDDEN_13` | new action-cost + choose-object mechanics |
| `HIDDEN_14` | new action-cost + priority activation mechanics |
| `HIDDEN_17` | new action-cost + choose-face-down mechanics |
| `HIDDEN_18` | knowledge/face-down blockers replaced by activation blockers |

No other row's class, unsupported-dimension set, unobservable-dimension set or
requested neutral state changed. Three rows in the runtime batch
(`MICRO_COSTS`, `MICRO_MODES`, `WS05-CMD-START-2`) differ only in
`materialization_digest`/`materialization_version`; their requested-state digest,
obligation digest, decision script and all semantic fields are byte-identical.

## Impact adjudication

See `receipts/PHASE2_IMPACT_ADJUDICATION.json`. In summary:

| Phase-1 receipt | Classification | Exact reason |
| --- | --- | --- |
| `SCENARIO_CAPABILITY_MATRIX.json` | `UNCHANGED_VALID` | Derived from the pinned bridge source blob, which is byte-identical; all assertions still present |
| `LIVE_REJECTION_PROBE.json` | `UNCHANGED_VALID` | Engine bytes unchanged; fresh live probe reproduces the same rejections |
| `STRUCTURAL_CENSUS.json` | `SUPERSEDED_BY_STRONGER_EVIDENCE` | Re-derived under contract 1.0.15; 101 rows unchanged, 6 rows `INVALIDATED_BY_CONTRACT` |
| `EXECUTION_RECEIPT.json` | `UNCHANGED_VALID` for its epoch; current credit requires fresh execution | No Phase-1 receipt was reused as current credit; the 16 rows were re-executed and the new epoch carries fresh runner-bound receipts |

## Wave revisit (state vs decision vs observation)

`receipts/PHASE2_WAVE_BLOCKERS.json` is the machine-readable form. Every wave
row still fails closed; selectors alone did not remove any ScenarioBootstrap
state-construction limitation:

| Row | Blocker classes | Exact blockers |
| --- | --- | --- |
| `MICRO_COPY` | STATE_CONSTRUCTION | `stack_state`, `semantic_objects.zone:stack` |
| `MICRO_COSTS` | STATE_CONSTRUCTION + DECISION_EXECUTION + OBSERVATION | `action_cost_state`, `temporal_state.active_player`, `decision_execution.priority.semantic_action`, `decision_execution.target.semantic_objects`, `semantic_objects.controlled_since_turn_began` |
| `MICRO_MODES` | STATE_CONSTRUCTION + DECISION_EXECUTION | `action_cost_state`, `temporal_checkpoint.exact_hand_after_draw`, `decision_execution.priority.semantic_action`, `decision_execution.choose_mode.semantic_mode_key` |
| `MICRO_REPLACEMENT` | STATE_CONSTRUCTION + OBSERVATION | `combat_state`, `temporal_state.combat_step`, `semantic_objects.controlled_since_turn_began` |
| `MICRO_ZONE_CHANGES` | STATE_CONSTRUCTION | `stack_state`, `semantic_objects.zone:stack` |
| `WS05-MP-BLOCK-4` | STATE_CONSTRUCTION + DECISION_EXECUTION | `combat_state`, `temporal_state.combat_step`, `decision_execution.declare_blocker.blocker_assignment` |
| `WS05-MP-COMBAT-4` | STATE_CONSTRUCTION + DECISION_EXECUTION + OBSERVATION | `combat_state`, `temporal_state.combat_step`, `decision_execution.declare_attacker.attacker_assignment`, `semantic_objects.controlled_since_turn_began` |

The shared midgame selector lane (`#450` and successors) owns the
decision-execution side for `MICRO_COSTS`, `MICRO_MODES` and
`WS05-MP-COMBAT-4` on the XMage candidate; that does not make the Forge
ScenarioBootstrap seam able to construct their states, and this lane does not
build a second selector.

## Shared-chain integration

The lane is now the Forge-candidate producer in the canonical current-boundary
chain:

* `forge_scenario_lane.positive_receipt` writes canonical
  `commander-lab.positive-fixture-receipt/1.0.0` receipts — candidate `forge`,
  the admitted Rules-Core commit, the live runner digest, the exact effective
  requested-state and obligation digests, the observation digests, the
  checkpoint verdict and its fixture-declared variance source when one applies.
* `forge_scenario_lane.execute_and_persist` binds the pinned clean Forge
  checkout, derives the capability matrix (drift fails closed), executes every
  structurally receivable row plus the declared blocker wave, and writes
  receipts only for obligations observed from engine facts.
* `scripts/run_current_boundary_qualification.py --candidate all` calls the
  producer for the Forge candidate after the clean runner identity is captured
  and persists `FORGE_SCENARIO_EXECUTIONS.json` in the epoch.
* `scripts/assemble_current_boundary_evidence.py` recognizes the
  `forge-scenario-lane:` prefix and credits only receipts that pass
  `positive_fixture_credit` (fixture membership, candidate commit, runner
  digest, exact requested-state digest, exact obligation digest, positive
  behaviour assertion). The credit reason names the producer and states that a
  fixture-declared cause variance is never presented as exact.

No second assembler or parallel evidence chain was created.

## Observed rows promoted by the producer

The canonical producer executed 16 rows on the pinned Forge engine and wrote
six receipts (all six pass `positive_fixture_credit`):

| Row | Checkpoint | Assertion class |
| --- | --- | --- |
| `WS05-CMD-DMG-SPLIT` | EXACT | BEHAVIOUR_OBSERVED |
| `WS05-CMD-PARTNER-DMG` | EXACT | BEHAVIOUR_OBSERVED |
| `WS05-CMD-PARTNER-ZONE` | EXACT | BEHAVIOUR_OBSERVED |
| `WS05-MP-ELIM-5` | ALLOWED_VARIANCE | BEHAVIOUR_OBSERVED_FIXTURE_DECLARED_CAUSE_VARIANCE |
| `WS05-MP-ELIM-OWNED-3` | ALLOWED_VARIANCE | BEHAVIOUR_OBSERVED_FIXTURE_DECLARED_CAUSE_VARIANCE |
| `WS05-MP-ELIM-PRIO-3` | ALLOWED_VARIANCE | BEHAVIOUR_OBSERVED_FIXTURE_DECLARED_CAUSE_VARIANCE |

`MICRO_LAYERS`, `WS05-CMD-START-2` and `WS05-CMD-START-3` construct exactly
(checkpoint EXACT) but have no lane observation contract for their required
events, so they remain `OBLIGATION_NOT_OBSERVABLE` with no receipt.

The seven wave rows remain named terminal blockers (table above).

## Wrong-reason controls

The focused suite preserves and extends the controls: transport alone, parse /
construction alone, checkpoint mismatch, missing decision execution, wrong
decision, missing terminal fact, stale identity, dirty checkout, unsupported
dimension, stale receipt digests, wrong candidate commit, wrong runner digest,
and a construction-only row granted no receipt. A fixture-declared cause
variance is labelled, never silently promoted to EXACT.
