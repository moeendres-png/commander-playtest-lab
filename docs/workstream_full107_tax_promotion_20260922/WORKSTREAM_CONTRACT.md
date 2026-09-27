# Workstream Contract — FULL107 TAX-2/TAX-4 DIRECT promotion (2026-09-22)

## Objective

Promote WS05-CMD-TAX-2/TAX-4 in `FULL107_MAPPING.json` from NOT_RUN_BLOCKED
to DIRECT on executed evidence (frozen-record construction MATCH +
scripted commander-cast execution with engine-owned tax payment + required
events + terminal postconditions, green locally and on CI via the merged
executor workstream PR #220). Nothing else changes classification.

## Source Lock

- Base: `origin/main` `7a28b58116979e2f2c36dc82c483c1a2d8aea9e1`.
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Evidence (READ-ONLY, merged): executor `XmageFullGameTaxExecutionTest`
  (TAX-2 2P + TAX-4 4P green locally and in CI conformance on PR #220).
- This branch: `cpl/full107-tax-promotion-20260922`.
- This worktree: `/home/moeen/code/ws-full107-tax-promotion-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- Identity-register EXACT verdicts for TAX-2/TAX-4 with evidence pointers.
- Generator NATIVE TAX-cells rule for exactly these two fixtures + mapping
  regen (DIRECT 2→4, NOT_RUN_BLOCKED 35→33).
- Correspondence-guard update (EXACT set +2, generator rules).
- Scoped validation (guard incl. negative control, mapping repro,
  retention predicates, WS17 manifests, ruff) + commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine/pin changes; new executions; any other
  reclassification; provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees/branches read-only. Executor workstream closed (PRs #220/#221).

## Hard Gates

- DIRECT only with EXACT register verdict + executed evidence (construction
  MATCH, scripted procedure, required events, terminal postconditions,
  green locally and on CI).
- Generator stays the single mapping source (reproducible rerun identical).
- Guard green; predicates 47/47; manifests verify; ruff clean.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no mock injection; no equivalent credited as exact;
no PASS beyond executed cells; no digest fabrication; no main edits; no
bypass.

## Evidence Requirements

Adjudication note with frozen-field citations + procedure-to-native_procedure
mapping; mapping diff proving only the two TAX entries + counts change.

## Stop Conditions

Complete when the corrected mapping + guard are integrated on main with
green post-merge CI, or a genuine blocker (fail closed + escalate).
