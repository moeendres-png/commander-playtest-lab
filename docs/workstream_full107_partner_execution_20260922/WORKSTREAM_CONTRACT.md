# Workstream Contract — FULL107 Partner execution (2026-09-22)

## Objective

Execute WS05-CMD-PARTNER-ZONE and WS05-CMD-PARTNER-TAX faithfully on the
pinned engine using the integrated WS2 restoration subset; verify Partner
legality, independent cast histories, and per-commander tax figures through
native readback and engine computation; adjudicate the digest-equality
evidence gate; promote both fixtures to DIRECT only on satisfied evidence
through the generator + correspondence guard.

## Source Lock

- Base: `origin/main` `316c09d4562fed407ebfb8770a52f2d046947758`
  (tree `6f56b07a1d44abbf9f0660c1a03f1997d0ba3589`).
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- Depends on: WS2 restoration + executor cast routing (merged through #220).
- This branch: `cpl/full107-partner-execution-20260922`.
- This worktree: `/home/moeen/code/ws-full107-partner-execution-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- PARTNER-ZONE: two-commander construction, engine Partner-legality proof
  (Commander validator at import), command-zone membership from game start,
  full readback MATCH, terminal postcondition.
- PARTNER-TAX: independent histories restore + readback; per-commander tax
  figures via the engine's own cost pipeline on ability copies (purity
  proven by readback-equality); independence demonstration (distinct
  counts/figures/identities + swapped-history detection); required events
  and terminal postcondition.
- Four negative controls: wrong Partner identity (import rejection),
  swapped histories (figure swap detected), incorrect tax, mismatched
  terminal expectation.
- Digest-equality adjudication (field-level vs frozen-digest standard).
- Mapping promotion (register + generator + mapping + guard) after proof.
- Contract/state/docs; scoped validation; commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine-repo edits; pin changes; scripted casts for
  unscripted fixtures (PARTNER scripts are empty; no decisions invented);
  other reclassifications; provider/freeze decisions; CARD_02/START-2
  (recorded as next frontier, separate workstream).

## Ownership

Single writer: this session on this branch/worktree only. Five completed
workstreams closed; their branches/worktrees read-only, never reopened.

## Hard Gates

- Exact frozen states/procedures/events/postconditions; no inferred
  requirements; no invented decisions (empty scripts stay empty).
- Engine owns legality/costs/tax/payment/SBAs/layers; no outcome
  injection, fabricated actions, first-option selection, silent skips,
  internal AI, reflection, or legality bypass.
- No digest fabrication; no silent contract weakening (gate adjudicated
  in writing).
- Bridge suite green, guard green, predicates 47/47, manifests verify,
  ruff clean; mapping repro identical.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: readback-of-counts alone never proves tax
behavior; partial evidence never earns DIRECT.

## Evidence Requirements

Execution transcripts (construction MATCH, tax figures, independence
proofs, terminal readback), negative-control results, digest-gate
adjudication, mapping diff proving only the two PARTNER entries + counts.

## Stop Conditions

Complete when both fixtures are executed, adjudicated, promoted, and
integrated on main with green post-merge CI plus a CARD_02/START-2
checkpoint — or a genuine technical/authority blocker (fail closed).
