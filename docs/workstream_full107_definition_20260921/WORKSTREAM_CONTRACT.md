# Workstream Contract — FULL107 Definition Import + Mapping (2026-09-21)

## Objective

Import the FULL107 provider-denominator definition (107 items) from
the immutable WS47 v1.0.5 coordinator input and produce the Forge-side
107-item mapping: 59 items mappable today (30 S1 families + 29 S3
cards) vs 48 undefined, plus a costed execution plan and an
adjudication package for Sol High. Execution itself is a separate
workstream.

## Source Lock

- Base: post-merge main `069762bc074efa78153931ba637f392766d2cb44`
  (own branch fast-forwarded; prepared work preserved).
- Definition source (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze`
  @ `5a2e4f462fd45bba25f2271153212aab9faf09f5` (immutable; never mutated).
- This branch: `cpl/full107-definition-import-20260921`.
- This worktree: `/home/moeen/code/ws-full107-definition-import-20260921`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR
  + Foundry push only (no direct main edits, no bypass).

## In Scope

- Locate + pin the FULL107 definition (WS47 v1.0.5 files/SHAs).
- 107-item mapping table: item → Forge evidence (seal + method) or
  UNDEFINED with reason; counts must reconcile (59/48 per R18 estimate
  or corrected with rationale).
- Execution plan (per-undefined-item cost) + adjudication package
  (divergence protocol refs: common-denominator contract,
  same-deck/same-seed fixture needs, hidden-info/RNG/replay criteria).
- Outputs under `docs/workstream_full107_definition_20260921/` +
  machine-readable `FULL107_MAPPING.json`.
- Scoped validation + local commit + §13 handoff.

## Out of Scope

- FULL107 execution (separate WS); any verdict upgrades; provider
  selection; Freeze; merges/pushes; engine/pin changes; WS47 edits.

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees read-only. WS47 source read-only (immutable binding).

## Hard Gates

- Definition bytes pinned by SHA before mapping starts; mapping items
  cite seals + methods (DIRECTLY_VERIFIED vs SEAL-DERIVED, never mixed).
- UNDEFINED stays UNDEFINED (no aspirational mapping); counts reconcile
  exactly to 107.
- No Rules adjudication by this workstream (package goes to Sol High).

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no mapping by name-similarity without seal
method; no definition paraphrase as substitute for pinned bytes.

## Evidence Requirements

Pinned definition ref + mapping table + reconciliation proof +
adjudication package.

## Stop Conditions

Complete when mapping reconciles to 107 with plan + package committed,
or a genuine terminal blocker (definition not locatable →
fail closed + escalate).
