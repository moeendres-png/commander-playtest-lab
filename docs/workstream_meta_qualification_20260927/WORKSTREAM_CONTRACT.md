# Meta-Qualification v1 — Workstream Contract

## Objective

Implement qualification-of-the-qualification without creating a second Rules Engine.
The bounded v1 slice must demonstrate that the existing semantic replay/comparator
stack and a production-bound live hidden-information oracle detect representative
faults rather than merely remaining green.

## Source Lock

- repo: `moeendres-png/commander-playtest-lab`
- integration base commit: `60fc3c8afbe5245ddc3a9f6262b86736e2a0a635`
- integration base tree: `0fe5be6d46949c74b37aba83169e38a7ecfe2068`
- historical post-#254 drift detector: `c5f9418e755a02ffec0e02c34b4a739baf10f5f0 / 610f93d81e3b7154731d95472be6dcac05057eac`
- branch: `sol/meta-qualification-v1-20260927`
- current pre-Freeze authority: `qualification/CURRENT_PRE_FREEZE_CONTRACT.json`
- current rules authority receipt status: `CURRENT_OFFICIAL_SOURCE_DIRECTLY_VERIFIED`

## In Scope

- machine-readable meta-verification contract;
- semantic mutation catalogue;
- real-tape mutation runner;
- live XMage hidden-information fault injection;
- machine-readable result schema;
- exact-head evidence artifact;
- tests proving detector class / first-divergence correspondence and fail-closed accounting.

## Out of Scope

- Rules-Core implementation changes;
- Architecture Freeze;
- Production Provider selection;
- historical evidence promotion;
- SBA, trigger, replacement, layers and Commander production fault seams beyond v1.

## Hard Gates

1. Existing replay/comparator infrastructure is reused.
2. Every attempted mutation must be detected by the expected detector.
3. Replay mutations must diverge at the expected record.
4. Hidden-information mutation must execute against the pinned live XMage boundary.
5. Surviving or unexecuted mutations remain visible and may not be promoted.
6. Final v1 evidence requires 8/8 KILLED, 0 SURVIVED, 0 NOT_RUN and catalogue coverage 1.0.
7. Current official Rules-authority receipt must remain directly verified and fail closed on drift.
8. CI, Production Qualification, Core Workflow Acceptance, Windows Runtime Hygiene and all XMage workflows triggered by the owned bridge test must pass on the same exact PR head.

## Stop Condition

This v1 slice is complete only when all hard gates pass on one exact current-main-based
PR head and the resulting merge is re-read from `main`. Final run IDs and merge receipt
are recorded in PR #262 disposition metadata so no post-gate source commit is required.
