# Meta-Qualification v1 — Workstream Contract

## Objective

Implement qualification-of-the-qualification without creating a second Rules Engine.
The first bounded slice proves that the existing semantic replay/comparator stack can
detect representative defects injected into a real recorded XMage game.

## Source Lock

- repo: `moeendres-png/commander-playtest-lab`
- base commit: `c5f9418e755a02ffec0e02c34b4a739baf10f5f0`
- base tree: `610f93d81e3b7154731d95472be6dcac05057eac`
- branch: `sol/meta-qualification-v1-20260927`
- current pre-Freeze authority: `qualification/CURRENT_PRE_FREEZE_CONTRACT.json`

## In Scope

- machine-readable meta-verification contract;
- semantic mutation catalogue;
- real-tape mutation runner;
- machine-readable result schema;
- tests proving mutation detection and explicit NOT_RUN accounting.

## Out of Scope

- Rules-Core implementation changes;
- Architecture Freeze;
- Production Provider selection;
- historical evidence promotion;
- arbitrary live-engine fault seams not yet implemented.

## Hard Gates

1. Existing replay/comparator infrastructure is reused.
2. Every attempted mutation must be detected by the expected divergence class at the expected record.
3. Surviving mutations are visible.
4. Runtime-required but unexecuted mutations remain NOT_RUN.
5. Kill rate and catalogue coverage are reported separately.
6. Rules-authority freshness conflict remains fail closed.

## Stop Condition

This slice is complete only when CI executes the real-tape mutation tests successfully.
Hidden-information live fault injection remains a named next-slice obligation until a
runtime bridge fault seam exists.
