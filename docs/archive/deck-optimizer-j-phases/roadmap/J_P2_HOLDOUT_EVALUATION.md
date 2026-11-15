# Roadmap J-P2 One-Time Holdout Evaluation

Evaluation status: `COMPLETED_INDEPENDENTLY_NO_POST_HOLDOUT_TUNING`

## Frozen candidate

- candidate commit: `4ca5a994882e0da6c55916b392972cdf3a5fc9c7`
- candidate tree: `82249e61488af5758a9ad1c5f0bf24eaf222eaca`
- package: `1.15.0`
- evaluation timestamp UTC: `2026-08-10T08:06:01Z`

## Holdout identity

- set: `J_HOLDOUT_v1`
- cases: `12`
- decks: Korvold + RogShai
- pod sizes: 3 / 4 / 5
- set hash: `724e84f1ea34bea9ec6b37929d945724c77c408a464b3a9dd05235738a00d5d6`
- member: `data/evals/holdout/pilot_decisions_j_v1.json`
- member SHA256: `a5875cd1a8edf6bbf79248b3e4ba26151579f628eaeefd4ef2369abb309da8d1`
- mutable: `false`
- used_for_tuning: `false`

## Execution evidence

- GitHub Actions run: `31368555983`
- GitHub Actions artifact: `9055115957`
- artifact digest: `sha256:5f2f1c9b6b4100d8c5b3184e5eaeb4190f3e663950a8547402b7d7205ef9667a`
- raw results file: `J_P2_J_HOLDOUT_v1_RESULTS.json`
- raw results SHA256: `c03af9292359d287c9bcc83fc2ff6d431204f06bddb21063cf19909ee3009ae4`

The workflow checked out the frozen candidate directly, verified commit/tree, verified the sealed registry state and holdout member hash, executed the 12 cases, rechecked the holdout member and repository truth, and uploaded the raw evidence. The evaluation branch/workflow is evidence infrastructure and is not part of the P2 product PR.

## Result

- cases passed: **12 / 12**
- cases failed: **0 / 12**
- pass rate: **1.0**
- critical cases passed: **12 / 12**
- critical pass rate: **1.0**

## Evidence boundary

This result is `structural_model_estimates` / pilot-decision holdout evidence. It is **not** an empirical Commander win rate, **not** real-playtest evidence, and **not** XMage/Forge external-rules-engine evidence.

The holdout was not used for tuning. No P2 model, pilot, heuristic weight, opponent assumption, decklist, inventory, purchase, or physical-allocation change may be made in response to this result. `J_HOLDOUT_v1` is now consumed as an independent P2 evaluation set and cannot be represented as unseen again. Reopening model tuning requires a new independent holdout version or explicit loss-of-independence labeling.
