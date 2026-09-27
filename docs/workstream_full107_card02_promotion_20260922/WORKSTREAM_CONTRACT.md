# Workstream Contract — FULL107 CARD_02 DIRECT promotion (2026-09-22)

## Objective

Promote CARD_02 in `FULL107_MAPPING.json` from NOT_RUN_BLOCKED to DIRECT
on the merged execution evidence (PR #231: exact construction, readback
MATCH, frozen digest equality, scripted cast with engine-owned resolution,
required events, terminal postconditions; green locally and on CI).
Nothing else changes classification. START-2 untouched.

## Source Lock

- Base: `origin/main` `3353f1c5f2fb9ff76afd6ce9b9ecf7474a4ba6fc`.
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- Evidence (READ-ONLY, merged): `XmageFullGameCard02ExecutionTest`
  (green locally and in CI conformance on PR #231).
- This branch: `cpl/full107-card02-promotion-20260922`.
- This worktree: `/home/moeen/code/ws-full107-card02-promotion-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- Impact analysis since #231 (no material change; no rerun/redesign).
- CARD_02 adjudication vs frozen fixture + recovered digest spec.
- Identity-register EXACT verdict with evidence pointer.
- Generator CARD_02 rule (no hand-edits) + mapping regen (DIRECT 6→7,
  NOT_RUN_BLOCKED 31→30; stale injection reason removed for CARD_02).
- Correspondence-guard update (EXACT set, NATIVE-executed-subset rule,
  CARD_02 shape rule, digest-language rule intact).
- Definition STATE amendment line.
- Scoped validation + commit + push + PR + merge + post-merge verify +
  COMPLETE state + handoff.

## Out of Scope

- Frozen WS47 mutation; engine-repo edits; pin changes; new executions;
  START-2 in any form; other reclassifications; provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees/branches read-only.

## Hard Gates

- DIRECT only with EXACT register verdict + executed evidence (green
  locally and on CI) + frozen digest equality.
- Generator stays the single mapping source (reproducible rerun identical).
- Diff proves only CARD_02 plus derived counts change.
- Guard green; predicates 47/47; manifests verify; ruff clean.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no mock injection; no equivalent credited as exact;
no PASS beyond executed cells; no digest fabrication; no main edits; no
bypass; no generator bypass via hand-edit.

## Evidence Requirements

Adjudication note with frozen-field citations + impact analysis;
mapping diff proving the single entry + counts.

## Stop Conditions

Complete when CARD_02 is DIRECT on main with green post-merge CI plus a
resumable handoff — or a genuine contradictory gate (fail closed).
