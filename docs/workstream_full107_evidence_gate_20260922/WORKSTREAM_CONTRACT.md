# Workstream Contract — FULL107 digest + event evidence integrity (2026-09-22)

## Objective

Investigate the discrepancy between the frozen
`REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST` credit condition
and the field-level correspondence standard: trace digest generation
across frozen history; recover the exact algorithm + preimage if possible
without guessing and implement the comparison for all six DIRECTs; else
fail closed (preserve tests/field evidence, correct unsupported
qualification claims via evidence-only changes, identify the successor
authority decision). Independently inspect PARTNER-TAX event assertions
(emitted vs facts vs derived). Add regression tests against silent
replacement of mandatory credit requirements.

## Source Lock

- Base: `origin/main` `728229f32aed2e6434a93aec73ec693de9e977a0`
  (tree `3a3e486b9bd4f14efefb68eac65a3e2f0bcf91a1`).
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- This branch: `cpl/full107-evidence-gate-20260922`.
- This worktree: `/home/moeen/code/ws-full107-evidence-gate-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- Digest trace (frozen branch tree/history, WS47 lineage docs, main-repo
  history for generation/validation code).
- Recoverability determination with evidence (no guessing).
- Either: digest comparison implementation + six-DIRECT verification; or
  fail-closed corrections (evidence-only mapping/register/reason changes,
  regression tests, successor authority statement).
- PARTNER-TAX event triage (emitted/facts/derived) with per-obligation verdicts.
- Contract/state/docs; scoped validation; commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine-repo edits; pin changes; new executions
  (CARD_02/START-2 stay queued); new DIRECT promotions; provider/freeze
  decisions; reopening closed workstreams' implementation (read-only
  reuse).

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees/branches read-only.

## Hard Gates

- No invented digest equality; no silent contract weakening; no frozen mutation.
- Field-level runtime evidence preserved regardless of outcome.
- Any claim correction goes through the normal protected process with
  green gates.
- Bridge suite green, guard green, predicates 47/47, manifests verify.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no preimage guessing; no same-named-digest
collisions; no redefining PASS to evade a mandatory condition.

## Evidence Requirements

Digest-trace record (files/commits/bytes examined, verdict per lead);
recoverability determination; either comparison implementation + six-way
verification or fail-closed correction set + successor authority
statement; PARTNER-TAX event triage table; regression tests.

## Stop Conditions

Complete when the gate is closed (comparison implemented or fail-closed
corrections integrated) with green post-merge CI — or a genuine
technical/authority blocker (fail closed).
