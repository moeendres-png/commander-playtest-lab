# J-P5 Optimizer / Statistics Closeout

Status: `J_P5_COMPLETE_CANDIDATE` pending final post-holdout CI/Windows/Release gates and merge.

## Truth boundary

All reported effects are `structural_model_estimates`. They are model-internal comparisons under the configured simulator, pilots, opponents, seats, pod sizes, and seeds. They are not empirical Commander winrates or human-play estimates. Confidence intervals quantify Monte Carlo/model uncertainty only.

## Holdout integrity

- Holdout: `J_P5_OPTIMIZER_HOLDOUT_v1`
- Holdout SHA-256: `b75e8622097221b00ad51322e2ad13fe5158cfd8647e92d2cb21a0d65b447203`
- Development Freeze SHA-256: `2f5ba17af552350f9c2ab36f9af3099ea4b2db4dbd5c09ef35ab601dc7366ca9`
- First evaluation artifact SHA-256: `ec2edda02627170a35df367497604eb3287090891c8f9635109647eed02f926b`
- Evaluation count: `1`
- Post-holdout tuning performed: `false`
- Finalist reselection after holdout: `false`
- Automatic canonical deck mutation: `false`

The holdout was evaluated only after the pre-holdout CI, Security, Windows Runtime Hygiene, and Release gates passed on the renewed frozen state. Technical pre-holdout Ruff/Mypy and Windows byte-identity fixes were completed before outcome consumption and were not based on holdout results.

## Holdout results

### Korvold finalist

Theorycraft only: `Goblin Bombardment -> God-Eternal Bontu`.

- constraints: valid
- central placement effect: `-0.052083333333333336`
- model-internal effect size: `-0.08612877519761604`
- Monte Carlo SE: `0.06171843192419334`
- model-internal interval: `[-0.16692708333333287, 0.07291666666666667]`
- scenario q25: `-0.09375`
- worst scenario effect: `-0.5`
- paired randomization p: `0.4964751762411879`
- Holm-adjusted model-internal p: `0.7223638818059097`
- holdout recommendation gate: `FAIL / first_evaluation_not_supportive`
- recommendation confidence: `not_supported_by_holdout`

Result: no recommendation to change the canonical Korvold list.

### RogShai finalist

Theorycraft only: `Flare of Duplication -> Rootborn Defenses`.

- constraints: valid
- central placement effect: `0.052083333333333336`
- model-internal effect size: `0.11726829444155105`
- Monte Carlo SE: `0.04532966880828721`
- model-internal interval: `[-0.03125, 0.13541666666666666]`
- scenario q25: `0.0`
- worst scenario effect: `-0.125`
- paired randomization p: `0.36118194090295486`
- Holm-adjusted model-internal p: `0.7223638818059097`
- holdout recommendation gate: `FAIL / first_evaluation_not_supportive`
- recommendation confidence: `not_supported_by_holdout`

Result: no recommendation to change the canonical RogShai list.

A failed holdout recommendation gate means the frozen variant was not robustly supported by this structural-model holdout. It is not empirical evidence that the real deck is worse.

## J-P5 method validation

- hard constraint enforcement: PASS; constraints precede scoring and use current Drive-derived candidate/free-inventory projections
- paired comparison / common random numbers: PASS
- card ablation: PASS as structural explanatory evidence
- package ablation: PASS as structural explanatory evidence
- commander denial: PASS
- swap matrix: PASS; both bounded development matrices completed
- local search: PASS
- beam search: PASS
- Pareto: PASS on the ten frozen robust-objective axes
- sensitivity: PASS; pod-size, pilot-strength, seat/opponent assumptions represented in development/holdout evidence
- multiple comparisons: PASS; Holm FWER used for ranked families / two frozen holdout finalists as specified
- counterfactual replay: PASS as model-alternative evidence, not historical fact
- Shapley approximation: PASS only as secondary explanatory/triage evidence, not primary winner-selection evidence
- recommendation traceability: PASS; holdout outputs bind candidate change, constraints, baseline/variant identities, paired seed set, central/worst-case effects, sensitivity, holdout status, model limits, and recommendation confidence
- challenge set: PASS for safety discrimination; noisy raw means are not allowed to promote statically bad variants through the recommendation gate

## Methodological result

J-P5 validates the optimizer as a constrained structural decision-support system, not as an oracle for real-game winrate. The strongest evidence from the independent optimizer holdout is conservative: neither frozen finalist earned recommendation support. This is a successful validation outcome because the system correctly permits `no recommendation` instead of forcing a winner.

## Mutation status

- canonical deck changes: `0`
- inventory changes: `0`
- purchase changes: `0`
- physical allocation changes: `0`
- Kaervek changes: `0`

Final J-P5 completion is contingent only on post-holdout regression/quality gates, merge, recovery, and Drive roundtrip. No optimizer/search retuning is permitted after this point.
