# Workstream Contract — FULL107 decision-script executor slice (2026-09-22)

## Objective

Establish a genuinely executable, rules-authoritative vertical slice for
the 7 NATURAL_GAME_START FULL107 denominator fixtures (4 PLAYER_COUNT,
PILOT_MULLIGAN, 2 WS05-CMD-MULL): drive live db134b97 games from fixture
decision_scripts through projected legal actions only (fail closed on
zero/multiple match, forbidden fallbacks prohibited), collect audit
events, assert required/forbidden events, and report per-fixture
PASS/FAIL/UNKNOWN/NOT_RUN. No behavioral PASS without execution.

## Source Lock

- Base: `origin/main` `51c224a021e0ce0a9362accc2cd41387ca4ba6ac` (post #209/#211).
- Frozen definition: `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`
  (READ-ONLY; 135 records, denominator 107).
- This branch: `cpl/full107-decision-executor-20260922`.
- This worktree: `/home/moeen/code/ws-full107-decision-executor-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR
  + Foundry push only.

## In Scope

1. Milestone 1 (investigation): fixture-deck importability (99×Mountain +
   mock commanders) via XmageDeckImporter; executor transport mapping
   (decision_script → projected legal actions; audit events →
   required/forbidden assertions).
2. Milestone 2 (only if M1 proves feasible without fixture deviation):
   implement `run_full107_fixture` + per-fixture tests for the 7
   natural-start fixtures; validate live on db134b97.
3. If M1 fails: exact pivot handoff (synthetic-deck bridge extension vs
   real-deck equivalents — the latter needs Coordinator adjudication).
   No fixture deviation without adjudication.

## Out of Scope

- NATIVE_STATE_LOAD fixtures (blocked: injection capability),
  provider/freeze decisions, FULL107 PASS claims beyond executed cells,
  other workers' surfaces (esp. consumer-migration worktree).

## Ownership

Single writer: this session on this branch/worktree only.

## Hard Gates

- Only provider-offered legal options ever selected; forbidden fallbacks
  (first/random/default/AI/GUI/skip/parent) prohibited by construction.
- `UNKNOWN != PASS`; construction/import alone never qualifies behavior.
- No second rules engine; pilots principal-scoped.
- Impact-qualified tests only; no expensive unrelated reruns.

## Stop Conditions

Slice executed + classified, or M1 infeasibility proven (pivot handoff),
or genuine terminal blocker (authority/external). Milestone completion
is a checkpoint, not campaign end.
