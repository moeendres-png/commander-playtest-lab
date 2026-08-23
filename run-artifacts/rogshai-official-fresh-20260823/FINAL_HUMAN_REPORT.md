# Official Fresh RogShai Optimizer-v2 Campaign — Final Human Report

## Decision

**MORE_DECISION_INFORMATION_REQUIRED**

The official fresh run is valid and complete under its preregistered stopping rules. It does **not** demonstrate that Current Control is optimal. It demonstrates that the only non-control candidate that reached the Structural decision lane — **Preordain → Opt** (`1a269d2c444692f8c7c99de7c92f94bd6fa627fe0d85529ad10a930669d37d90`) — was not distinguishable from Current Control by the current Structural model and therefore was not promoted.

## Immutable identity

- main commit: `ff3f6c3d6d0a269c992780c9f0a3ae9aba63f401`
- tree: `cb5ad938eea9145c4dcf15d69e1580cfa68ef6c1`
- package: `1.23.1`
- optimizer runtime: `optimizer-v2-runtime-0.3.0`
- decision runtime: `optimizer-v2-decision-runtime-1E-2F-1.1.0`
- structural semantic model: `structural-capability-fidelity-2026-08-23-v2`
- manifest: `d43525cf6b770a8cd83b53f701993b504a33a9c39aba2ff9630e6c09876713e8`
- seed: `2026082302`
- operative domain: **4-player Commander only**

## Calibration

Calibration passed: 9/9 synthetic fixtures, 7/7 direction fixtures, 2/2 equivalence fixtures, 0 false promotions, 0 false eliminations, 192 paired scenarios, 0 failures and 0 retries.

## Search

Search status: **SEARCH_HEALTHY**. It generated/evaluated 133 unique legal decks, removed 4 duplicates, rejected 19 illegal proposals, occupied 56 hypothesis QD cells with a 99-entry hypothesis archive, and occupied one decision-QD cell. Nine construction policies, ten operators and seventeen packages were represented. Candidate-card exposure was 561/795 (70.57%); 234 pool cards were not represented in evaluated decks.

Fidelity remained the dominant decision-width limit: 17 generated candidates were Structural-decision-safe and 116 were routed to External Rules evidence. Screening leakage into the Decision QD lane was false. Current Control remained an exact anchor/comparator.

## Confirmatory

Before evaluator construction, Current Control (`e2ebecc4f095703434f9b30bedfddebecb7a5b3e57a00e0d83e6da7549bda5f2`) was excluded as a challenger. Exactly one non-control candidate entered confirmatory:

- remove: **Preordain**
- add: **Opt**
- fidelity: `APPROXIMATED_DECISION_SAFE`
- changed slots: 1

Planned looks were 128 → 256 → 512 → 1024 → 2048. The candidate produced paired effect `0.0` at 128, 256, 512 and 1024; terminal 99% interval `[0.0, 0.0]`, MCSE `0.0`, four seed-block means all `0.0`, all four seat effects `0.0`, and every reported opponent-group effect `0.0`. At 1024 the preregistered status became **FUTILITY_BELOW_SESOI**. The 2048 look was therefore not consumed.

This is **Structural model non-discrimination**, not empirical real-game equivalence between Opt and Preordain.

## Critical Diagnostics / Challenger Freeze / Holdout

No confirmatory promotion existed and `single_challenger_hash = null`. Therefore:

- Critical Diagnostics partition: **NOT RUN / unopened**
- Final Challenger Freeze: **not created / ineligible**
- Sealed Holdout: **NOT OPENED**, 0 games
- historical holdout reuse: false

Opening any of those stages would have violated the preregistered eligibility gates.

Exploratory near-frontier diagnostics are retained only as exploratory Structural evidence. For the sole candidate, commander-denial diagnostic degradation was +0.625 average placement under the synthetic denial profile; parent-child ablation was 0.0; pilot sensitivity was 0.0; and mana/curve summaries were essentially unchanged because the deck delta was only Preordain → Opt.

## Integrity

Calibration, exploratory and confirmatory execution audits report 0 simulation failures and 0 retries. Core paired scenarios consumed: 13,984 = 192 calibration + 11,872 exploratory + 1,920 confirmatory. Resume verification returned `resumed_without_reexecution` with identical frontier and candidate-ledger identities. No stale/cross-manifest cache evidence was observed.

Canonical RogShai, inventory, allocation, purchases, opponent truth and Kaervek remained unchanged.

## Main limitation and next useful information

The run did not suffer the previous Search/Fidelity collapse. Instead, the main decision bottleneck is now visible: most interesting generated hypotheses require Tactical or External Rules evidence, while the only safe Structural finalist fell into a model equivalence class.

The highest-value next evidence is therefore **not another identical Structural-only campaign**. It is: (1) targeted Tactical/External evidence for high-value routed hypotheses, (2) a focused Opt-vs-Preordain semantic/tactical differential test, and (3) outcome-independent coverage work for the 234 unexposed cards if broader search coverage is desired.

No P0 correctness patch is required before the next run. Any software/semantic-model change would, however, require a new exact-main recovery and a completely fresh, cross-campaign-disjoint manifest.
