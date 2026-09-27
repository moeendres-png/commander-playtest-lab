# Workstream Contract — FULL107 PARTNER-ZONE/TAX DIRECT promotion (2026-09-22)

## Objective

Promote WS05-CMD-PARTNER-ZONE and WS05-CMD-PARTNER-TAX in
`FULL107_MAPPING.json` from NOT_RUN_BLOCKED to DIRECT on executed
evidence (merged PR #224: construction MATCH, partner legality, tax
figures, independence, negatives; green locally and in CI conformance).
Nothing else changes classification.

## Source Lock

- Base: `origin/main` `a75c47b978f151542a535adc3f91fbdccc09c035`.
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Evidence (READ-ONLY, merged): `XmageFullGamePartnerExecutionTest`
  (6 tests green locally and in CI conformance on PR #224).
- This branch: `cpl/full107-partner-promotion-20260922`.
- This worktree: `/home/moeen/code/ws-full107-partner-promotion-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- Identity-register EXACT verdicts with evidence pointers.
- Generator PARTNER rule for exactly these two fixtures + mapping regen
  (DIRECT 4→6, NOT_RUN_BLOCKED 33→31).
- Correspondence-guard update (EXACT set, NATIVE-executed-subset rule,
  partner shape rule).
- Definition STATE amendment line.
- Scoped validation (guard incl. negative control, mapping repro,
  retention predicates, WS17 manifests, ruff) + commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine/pin changes; new executions; any other
  reclassification; provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only. Execution
workstream closed after its close-out; all other worktrees read-only.

## Hard Gates

- DIRECT only with EXACT register verdict + executed evidence (green
  locally and on CI).
- Generator stays the single mapping source (reproducible rerun identical).
- Guard green; predicates 47/47; manifests verify; ruff clean.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no mock injection; no equivalent credited as exact;
no PASS beyond executed cells; no digest fabrication; no main edits; no
bypass.

## Evidence Requirements

Adjudication note with frozen-field citations; mapping diff proving only
the two PARTNER entries + counts change.

## Stop Conditions

Complete when the corrected mapping + guard are integrated on main with
green post-merge CI plus a CARD_02/START-2 checkpoint — or a genuine
blocker (fail closed + escalate).
