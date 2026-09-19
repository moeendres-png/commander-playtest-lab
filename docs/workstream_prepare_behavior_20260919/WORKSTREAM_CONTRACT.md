# Workstream Contract — Prepare-Behavior Qualification (2026-09-19)

## Objective

Close the material `RULES_COVERAGE=UNKNOWN` gap from the sealed physical-pool
sync (`695e2031`): qualify actual-card Prepare-mechanic behavior for the 11
SOS prepare-relevant identities in `tests/fixtures/physical_pool_prepare_sos.json`
on the pinned engine `xmage-1.4.61`, 4-player primary, with honest
DIRECTLY_VERIFIED / CODE_DERIVED / NOT_RUN / UNKNOWN classifications.
Successor to `cpl/physical-pool-rules-sync-20260919` (read-only base); does not
touch the active `cpl/three-deck-optimization-20260919` worktree.

## Source Lock

- Base: `cpl/physical-pool-rules-sync-20260919` @
  `695e2031f380ea627416544d888d5c5f1287ca94` (verified clean at worktree creation).
- This branch: `cpl/prepare-behavior-qualification-20260919`.
- This worktree: `/home/moeen/code/ws-prepare-behavior-20260919`.
- Engine pin: `xmage-1.4.61` (`engine-bridge/pom.xml`).
- Reference (read-only, never edited): `moeendres-png/mage` worktree
  `/home/moeen/code/mage-d3q6` (Prepare cards present, e.g.
  `Mage.Sets/src/mage/cards/b/BlazingFiresinger.java`).
- `origin/main` = `aebcfda37d61eb435dde6cd11792ef80019dcd10` (no main changes).

## In Scope

- Construction/import verification: all 11 fixture identities resolve to real
  xmage-1.4.61 card implementations with Prepare semantics (no name-inferred
  identity; fail closed on missing/ambiguous).
- Runtime behavior probes via the owned Lab + engine-bridge harness only:
  enters-prepared, exile-copy creation, controller-only cast, cast-unprepares,
  cast-a-copy (cast triggers see a CAST), cost-vs-value ({0} cost), zone-change
  reset, target legality/fizzle, APNAP ordering (4P primary).
- Positive + adversarial regression tests (owned surfaces only).
- Evidence package with honest verdicts per card × path.

## Out of Scope

- `moeendres-png/forge`, `moeendres-png/mage` source edits (read-only reference).
- Active worktree `cpl/three-deck-optimization-20260919` (no reads of its
  untracked deck work; no writes there).
- Stale-consumer migration (15 entries — separate product scope).
- Drive publication, push, merge, PR creation.
- Architecture Freeze / Production Provider claims (explicitly NOT claimed).
- FULL107 (NOT_RUN), 2–5P conformance beyond 4P primary (recorded NOT_RUN unless
  cheaply executable without Core changes).

## Ownership

Single writer: this session on this branch/worktree/state only. Mutation surface:
`docs/workstream_prepare_behavior_20260919/`, owned new tests under
`tests/` + `engine-bridge/src/test/` (additive only), owned evidence files.
Forbidden: any file owned by another workstream, `tools/foundry/safe_push.py` +
`tests/foundry/*` (PR #206), decks/allocations/archives.

## Dependencies

- Sealed sync package `695e2031` (loader, manifest, fixture).
- Pinned xmage-1.4.61 artifacts (Maven cache / network as available).
- Existing `engine-bridge` full-game harness
  (`XmageFullGameJsonlBridge`, `XmageGameManager`, decision controllers).

## Hard Gates

- Rules Authority preserved: engine alone determines legality; probes only
  select among engine-authorized options; no second Rules Engine in
  harness/tests; unsupported paths fail closed.
- No first/random/default/AI/GUI/silent-skip/parent fallbacks in probes.
- Principal-scoped hidden information (no cross-principal leaks in
  observations/logs/evidence).
- Explicit-seed Rules RNG only on production-reachable paths.
- UNKNOWN stays UNKNOWN; NOT_RUN stays NOT_RUN; no behavior PASS from
  import/construction alone.

## Forbidden Shortcuts

Per `AGENTS.md` §2 plus: no requested-option filtering reconstructing legality;
no manual outcome injection; no `sa.resolve()` substitutes; no green-workflow
equality with Qualification PASS; no relabeling 795-base results.

## Evidence Requirements

Per card × rule path: expected (Oracle text + CODE_DERIVED engine mapping),
observed (DIRECTLY_VERIFIED runtime output or NOT_RUN with cause), verdict
(PASS/FAIL/UNKNOWN). Fail-before + pass-after where a defect is repaired on an
owned surface; engine defects reported as reproducible issues, never patched
cross-repo here.

## Persistence

After each validated milestone: coherent tree, scoped validation, state update,
focused local commit. End with full handoff (§13): Source Lock; Work Completed;
New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN; Remaining Blockers;
Outputs; Dependencies Unblocked; Exact Next Action.

## Stop Conditions

Stop only when: every in-scope card × path has a classified verdict with cited
evidence, or a genuine terminal blocker is proven (engine defect requiring owner
fix with reproducible issue filed in-evidence; Rules authority gate requiring
Sol High CR/Release-Notes adjudication; irreconcilable source-lock violation).
Remediable probe failures are diagnostic — repair on owned surfaces and continue.
