# Fail-before and wrong-reason controls

## 1. Fail-before: the existing current-boundary path does not consume the seam

The pre-lane Lab path cannot send a scenario at all:

* `src/commander_lab/qualification/current_boundary/game_driver.py`
  `_create_request()` builds `{game_id, deck_handles, format, external_control,
  [seed]}` — it contains no `scenario` key, and the driver never references
  `neutral_initial_state`.
* `scripts/run_current_boundary_qualification.py` never references
  `neutral_initial_state` or `ScenarioBootstrap`.
* The runner's own residual classification marks the seven-row wave `BLOCKED`:
  the micro rows are deferred to "the engine-native restoration harness" and the
  mid-game rows are labelled a "LAB EXECUTION-PATH gap … this run did not
  exercise the injection seam". Both statements are true of the existing path
  and both are superseded by this lane's runtime receipts.

These facts are asserted by
`tests/qualification/test_forge_scenario_lane.py::test_fail_before_current_runner_has_no_scenario_seam`
and `::test_fail_before_shared_runner_blocks_the_wave`.

The fail-before fails for the intended reason: it is a missing scenario
execution seam in the current Lab path, not a missing file, wrong path, broken
import, malformed fixture or unrelated CI issue. The lane then exercises the
same rows against the real pinned engine and produces per-field blockers.

## 2. Wrong-reason controls

| Control | Test |
| --- | --- |
| Successful transport alone cannot produce row credit | `test_control_transport_only_cannot_pass` |
| Successful scenario parse/construction alone cannot produce credit | `test_control_successful_construction_alone_cannot_pass` |
| Checkpoint mismatch cannot produce credit | `test_control_checkpoint_mismatch_cannot_pass`, `test_checkpoint_mismatch_cannot_be_credited` |
| An unsupported scenario field fails closed | `test_control_unsupported_field_fails_closed_in_probe`, `test_stack_unsupported_dimension_can_never_be_exact` |
| Missing decision execution cannot produce credit | the driver stops at any decision class it does not execute and records `FAIL_CLOSED_UNSATISFIED`; the obligation evaluator requires engine facts, so a construction-only run cannot pass (`test_obligation_requires_engine_facts`) |
| Wrong decision cannot produce credit | decisions are selected only from engine-offered option ids; `DecisionUnsatisfied` is raised when no offered option matches, and `test_commander_damage_obligation_observed_and_missing` shows the wrong terminal fact (engine-applied loss) yields `observed=False` |
| Missing semantic terminal/event fact cannot produce credit | `test_control_successful_construction_alone_cannot_pass` (exact checkpoint, no obligation facts → `OBLIGATION_NOT_OBSERVABLE`) |
| Candidate/source identity mismatch invalidates credit | `test_bridge_identity_mismatch_invalidates_credit` (executing bridge module tree ≠ bound tree → `ScenarioLaneError`, no receipt) |
| Dirty checkout invalidates credit | `test_dirty_checkout_is_refused` |
| Stale receipt invalidates credit | receipts embed the full source identity (Lab commit/tree, Rules-Core commit/tree, bridge commit/module tree, source blob hashes, provider version echo). Any later identity change is visible; the lane's binding raises before execution, and Phase-2 impact adjudication must re-run rather than reuse a stale receipt. |
| Capability-matrix source drift | `test_capability_matrix_fails_closed_on_source_drift`, `test_capability_matrix_detects_hook_removal` |

## 3. Decision-execution discipline

* Every executed decision is recorded with its offered option ids and the chosen
  option id; the policy is named (`keep_all`, `requested_starting_seat`,
  `pass_when_offered`, `native_declared_cost_part_order`).
* No first option, random option, default yes/no, internal AI, GUI default,
  silent skip or parent fallback exists in the lane. Unknown decision classes
  stop the drive and fail that row closed.
* Decision families outside this lane's implemented set are recorded as
  `decision_execution.<family>.<selector>` blockers — never reconstructed from
  card text and never fabricated.
