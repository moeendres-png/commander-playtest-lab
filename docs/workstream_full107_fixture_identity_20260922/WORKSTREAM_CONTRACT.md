# Workstream Contract — FULL107 fixture-identity adjudication (2026-09-22)

## Objective

Adjudicate the seven NATURAL_GAME_START denominator fixtures against frozen
WS47 bytes and actual runtime setups; correct classifications that lack exact
fixture correspondence (PLAYER_COUNT_2/3/4/5P DIRECT → SUPPORTING: the cited
gates run Isamaru+Plains at other seeds, not the bound Rograkh+Mountain
fixture); preserve genuinely exact execution (WS05-CMD-MULL-2/4 DIRECT stands);
keep PILOT_MULLIGAN SUPPORTING. Add a mechanical regression test preventing
unsupported DIRECT promotions. No PASS/FAIL awarded beyond executed cells.

## Source Lock

- Base: `origin/main` `b094b0522713836a01c539ba558717bf70ae18b0`
  (tree `eb7161d6216becbbedf0d3bc71ed7c1707bfdeb3`).
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- This branch: `cpl/full107-fixture-identity-20260922`.
- This worktree: `/home/moeen/code/ws-full107-fixture-identity-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- 7-record adjudication (deck_state / digest / script / obligations /
  engine / count / evidence) with per-fixture verdicts.
- Generator rule change for the PLAYER_COUNT gate-equivalence + mapping regen.
- `tests/unit/test_full107_direct_correspondence.py` regression guard.
- Scoped validation (pytest file + mapping repro + ruff) + commit + push + PR.

## Out of Scope

- Frozen WS47 mutation; engine/pin changes; NATIVE injection (Workstream 2);
  executor harness; provider/freeze decisions; reclassification beyond the
  four PLAYER_COUNT entries; digest-protocol implementation (WS2 hardening).

## Ownership

Single writer: this session on this branch/worktree only. All other
full107 worktrees/branches read-only. Prior PRs #214/#215 merged, untouched.

## Hard Gates

- DIRECT only with EXACT verdict in the identity register (exact decks +
  seed + procedure + assertions, engine-pinned).
- Generator stays the single mapping source (reproducible rerun identical).
- No NATIVE_STATE_LOAD entry may be DIRECT (injection does not exist yet).
- Regression test green; mapping repro byte-identical; ruff clean.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no mock-card injection; no digest fabrication; no
gate-deck equivalence credited as fixture identity; no main edits; no bypass.

## Evidence Requirements

Adjudication record with frozen-field citations; test file; mapping diff
proving only the four PLAYER_COUNT entries + counts change.

## Stop Conditions

Complete when the corrected mapping + guard are integrated on main with
green post-merge CI, or a genuine blocker (fail closed + escalate).
