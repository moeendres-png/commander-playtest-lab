# XMage Residual Re-Pin / Integration — Terminal State and Handoff

Branch: `sol/xmage-residual-repin-integration-20260925`

Base: `548167fa25b8345621d4638d7c140449fa73ac31`

Old pin: `db134b9737e951367d65ef5806ad986319cc73ab`

Candidate pin: `b19596980f2734496ea1896504253e1bdd2756dd`

WORKTREE = NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

ARCHITECTURE_FREEZE = NOT CLAIMED

PRODUCTION_PROVIDER = NOT SELECTED

## Objective

Consume the cumulative M1-M4 Mage residual candidate in Commander Lab, preserve
historical provenance, integrate the available native seams without inventing
unsupported state, and obtain fresh runtime evidence for every materially
impacted current bridge/full-game boundary.

## Source Lock

- Commander Lab base: `548167fa25b8345621d4638d7c140449fa73ac31`.
- Runtime-validated branch implementation head:
  `68cb50ab700fdca88400ac43ced997ffbc09fc41`.
- GitHub PR merge-ref actually executed by the final green Actions runs:
  `60f35068d978b96e9a8cf68049a00d8a465c1e40`.
- PR: #242, Draft, open, mergeable, not merged.
- Mage candidate: `b19596980f2734496ea1896504253e1bdd2756dd`.
- Previous Lab pin retained in sealed historical evidence:
  `db134b9737e951367d65ef5806ad986319cc73ab`.
- Current machine authority remains
  `config/rules_engines.json -> primary_engine.commit`.

This terminal-state documentation commit is documentation-only. Runtime
qualification is bound to the implementation head and its PR merge-ref above;
no runtime result is relabeled onto later documentation-only bytes.

## Work Completed

- Forward-repinned the sole current XMage machine authority and all enumerated
  active bootstrap/runtime/test/workflow pin consumers to the cumulative M1-M4
  Mage candidate.
- Migrated bridge provider self-identity and Phase-6 provider identity to the
  new exact pin.
- Replaced Phase-6 direct Commander-damage map mutation with XMage's native
  `CommanderInfoWatcher.restoreDamageStateForGameLoad(...)` path.
- Added bridge-runtime qualification for
  `Library.restoreOrderForGameLoad(...)`.
- Added bridge-runtime qualification for
  `BecomesFaceDownCreatureEffect.restoreFaceDownStateForGameLoad(...)`.
- Preserved the global `starting_state_injection_supported=false` contract.
- Added current-vs-historical pin guards.
- Preserved sealed WS218 semantic replay tapes, WS232 retention artifacts and
  earlier source locks at their original pin rather than rewriting provenance.
- Adjudicated WS232 correctly: a pin change invalidates its current-use
  retention predicate; the historical artifacts remain sealed and the
  successor workstream supplies fresh current evidence.
- Opened isolated Draft PR #242. No direct `main` mutation and no merge.

## New Findings

1. The Lab frozen requested-state contract does not contain enough lossless
   information to synthesize an arbitrary full library permutation or an
   unambiguous face-down subtype for all frozen records.
2. Therefore broad frozen-state library/face-down promotion would require
   invented semantics and remains fail closed.
3. The new Mage primitives are nevertheless directly runtime reachable through
   the Lab bridge and are qualified on the exact re-pinned engine.
4. PR workflows execute the GitHub pull-request merge-ref, so final CI evidence
   is source-bound to both the branch implementation head and the exact merge
   ref recorded above.

## Changes

Material implementation and current-contract changes include:

- `config/rules_engines.json`
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java`
- `engine-bridge/src/main/java/org/commanderlab/xmage/Phase6DifferentialAdapter.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageNativeStateRestorationTest.java`
- current bootstrap, runner, pin-authority and cardinality consumers
- current XMage integration/full-game/real-4P workflows
- successor re-pin qualification guards
- living architecture/source-lock/impact-adjudication documentation

The implementation diff from base contains 28 changed files across 29 commits
before this documentation-only closeout.

## Tests / Evidence

Final PR-head requalification on branch head
`68cb50ab700fdca88400ac43ced997ffbc09fc41` / executed merge-ref
`60f35068d978b96e9a8cf68049a00d8a465c1e40`:

- **CI** run `36114548042`: SUCCESS.
  - Ruff lint: PASS.
  - Ruff format: PASS.
  - Mypy strict: PASS, no issues in 261 source files.
  - Python suite: **1548 passed, 7 skipped, 1 warning**.
  - Two WS232 skips are intentional successor invalidation of historical
    pin-stability evidence, not fabricated PASS.
  - Compile, secret scan and wheel build: PASS.
  - CI evidence artifact ID: `10854387176`.
- **External XMage Integration** run `36114548068`: SUCCESS.
  - Exact Mage pin checkout/build: PASS.
  - Bridge main/test compilation: PASS.
  - Maven bridge suite: **225 tests, 0 failures, 0 errors, 1 skip**.
  - `XmageNativeStateRestorationTest`: **20/20 PASS**, including the two
    new ordered-library and face-down runtime-reachability tests.
  - B3, B4-A, B4-B, B4-C, B4-D regressions: PASS.
  - Provider-bound Phase-6 differential: 2 passed, 1 expected configured-backend skip.
  - Deterministic reconstruction replay, illegal-action rejection,
    capability descriptor and exact provider-pin binding: PASS.
  - B4-F artifact ID: `10854706571`.
  - B4-D compatibility artifact ID: `10854536716`.
- **XMage Full Game Conformance** run `36114548085`: SUCCESS.
  - Bridge Maven verification: 225 tests / 0 failures / 0 errors / 1 skip.
  - Real seeded 4P game-over/replay: PASS.
  - 4P decision count: **4476**.
  - `semantic_replay_match=true`; raw result equality is not claimed
    (`raw_result_match=false`).
  - 2P bounded smoke: PASS, 25 decisions, clean shutdown.
  - 3P bounded smoke: PASS, 25 decisions, clean shutdown.
  - 5P bounded smoke: PASS, 45 decisions, clean shutdown.
  - 6P bounded smoke: PASS, 55 decisions, clean shutdown.
  - Unsupported callback seen: false for all bounded smoke runs.
  - 7P boundary: **FAIL_CLOSED** before unsupported execution.
  - Technical-evidence/hidden-information boundary checks: PASS.
  - Artifact ID: `10855265305`.
- **XMage Real 4P Technical Smoke** run `36114548040`: SUCCESS.
  - Real-deck setup/loader tests: **14 passed**.
  - Exact deck preflight: PASS.
  - Bridge verification: PASS.
  - Bounded real 4P smoke: PASS, **40 decisions**, clean shutdown.
  - This remains technical usability evidence only; it is not a claim that
    every card behavior was exercised.
  - Artifact ID: `10854627237`.
- **H4 Docker Materialization** run `36114548024`: SUCCESS.
  - Preflight, h4-xmage and h4-forge jobs: SUCCESS.
  - XMage image uses the manifest-authoritative candidate pin; real container
    handshake/provenance and negative controls passed.
  - H4 workflow success does not select a provider or grant broader provider
    qualification beyond its recorded evidence boundary.
  - XMage artifact ID: `10855526116`.
- **Production Qualification** run `36114548025`: SUCCESS.
- **Core Workflow Acceptance** run `36114548073`: SUCCESS.
- **Windows Runtime Hygiene** run `36114548019`: SUCCESS.
- PR review state at terminal implementation head: no reviews, no inline review
  threads and no PR conversation comments.

All eight final implementation-head PR workflows are green.

## PASS / FAIL / UNKNOWN

### PASS

- Current Lab XMage pin migration to
  `b19596980f2734496ea1896504253e1bdd2756dd`.
- Active consumer consistency.
- Bridge/provider identity consistency.
- Native Commander-damage restore integration.
- Direct ordered-library native state-load primitive reachability.
- Direct face-down native state-load primitive reachability.
- External integration B3/B4-A/B4-B/B4-C/B4-D.
- Phase-6 differential execution on the new pin.
- Full-game 4P semantic replay.
- 2P/3P/5P/6P bounded technical execution.
- 7P fail-closed cardinality boundary.
- Hidden-information/technical-evidence boundary.
- Real 4P technical smoke.
- H4 manifest-authoritative XMage materialization.
- Repository quality/security/Windows/qualification/acceptance gates.

### FAIL

- None remaining in the commissioned re-pin/integration scope.

### UNKNOWN / intentionally not promoted

- General arbitrary frozen-state full-library restoration from existing Lab
  records: contract lacks a lossless full permutation.
- General arbitrary frozen-state face-down restoration from existing Lab
  records: contract lacks an unambiguous native face-down subtype.
- These paths remain fail closed and are not counted as PASS.
- Production Provider selection remains NOT SELECTED.
- Architecture Freeze remains NOT CLAIMED.

## Remaining Blockers

No blocker remains for **PR #242's commissioned re-pin and targeted
requalification scope**.

The broader hidden-state contract gaps above are separate successor capability
work, not a reason to invalidate the re-pin. They must not be solved by
fabricated data, heuristics or capability inflation.

## Outputs

- Draft PR #242:
  `https://github.com/moeendres-png/commander-playtest-lab/pull/242`
- Source lock:
  `docs/workstream_xmage_residual_repin_20260925/SOURCE_LOCK.md`
- Impact adjudication:
  `docs/workstream_xmage_residual_repin_20260925/IMPACT_ADJUDICATION.md`
- Terminal state/handoff: this file.
- GitHub Actions artifacts listed in the evidence section.

## Dependencies Unblocked

- Commander Lab can now consume the cumulative M1-M4 Mage candidate under a
  fresh, source-bound technical qualification record.
- Later hidden-state contract work may target the now-proven native library and
  face-down restore primitives without reopening the engine remediation.
- Later architecture/candidate adjudication may use this re-pinned Lab evidence
  without treating the old WS232/WS218 artifacts as current-pin evidence.

## Exact Next Action

Coordinator review/adjudication of Draft PR #242. If the Coordinator authorizes
integration, mark it ready/merge under the normal repository policy and verify
the resulting `main` merge SHA and post-merge checks. This workstream itself
must not merge the PR and must not claim Architecture Freeze or Production
Provider selection.

## Terminal Status

`XMAGE_RESIDUAL_REPIN_LAB_INTEGRATION = COMPLETE`

No further implementation or test rerun is justified unless the pin, code,
contract, harness, workflow, base branch or merge result materially changes.
