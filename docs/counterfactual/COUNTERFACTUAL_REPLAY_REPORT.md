# Phase 12.9 – Counterfactual Replay completion revision

Status: `counterfactual_replay_ready_with_limitations`

Original release: `1.9.0`; completed and revalidated in package `1.10.1`.

The implementation now identifies hashed replay branchpoints, accepts only recorded legal alternatives, verifies replay-prefix and state hashes, computes explicit public-state/action deltas, and supports four hidden-information policies. Structural futures use deterministic seed policies. Tactical mode actually invokes the bounded `TacticalRuleOracle`; its result remains `tactical_oracle` and is never promoted to external-engine evidence.

The Replay Debugger retains branch markers, action comparisons, state differences, same-seed repeats, batched alternative futures and Golden Scenario export.

Counterfactuals remain model alternatives. They do not prove how a historical game would have unfolded.
