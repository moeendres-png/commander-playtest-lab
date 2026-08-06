# Phase 12.9 – Counterfactual Replay

Status: `counterfactual_replay_ready_with_limitations`

Version: `1.9.0`

The implementation identifies hashed replay branchpoints, lists only recorded legal candidates, enforces state and replay-prefix hashes, supports explicit hidden-information and seed policies, compares structural alternatives, calculates model-dependent decision regret, extends Replay Debugger, and exports Golden Scenario fixtures.

## Validation

- 243 tests passed.
- One real external-engine differential test was skipped because no XMage/Forge command is configured.
- The included Korvold example uses a recorded structural pilot-decision candidate set.

## Truth boundary

Counterfactuals are model alternatives. They do not establish what historically would have happened. Tactical Oracle remains distinct from an external engine. No external-engine counterfactual was executed.
