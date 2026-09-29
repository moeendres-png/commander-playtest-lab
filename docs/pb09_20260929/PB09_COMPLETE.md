# PB-09 — Pristine-Upstream Forge Qualification: COMPLETE

Executor for this continuation: Space Bunny MAX (`opencode-go/space-bunny-free`, native `max`),
operator-directed after the previous profile's quota was exhausted. The model selection itself is
launcher-side; this record states the profile the work ran under, not a project-wide activation claim.

## Source lock

| Identity | Value |
|---|---|
| Lab main consumed | `ca9356e3da662ce9e246e7f896f1a99772d59065` (PR #292) |
| PB-09 branch / worktree | `muse-xhigh/pb09-pristine-forge-20260929` @ `105f6d27`, `/home/moeen/code/csn-final-bakeoff/muse/pb09-lab` |
| Pristine upstream engine | `Card-Forge/forge@a37a865a53280dd8ad6fad3384d69611e8c5a42f`, tree `4471ff068dd23127fc5878bdffa0c0e6de8e6c28` |
| Harness (bridge) commit | `ddf01c91faf1bcba1cd2bc0a0c1b742fc2b35c9b` in the pristine clone |
| Harness build commit | `ddf01c91…`, `engine_build_dirty=false` |
| Bridge identity reported | `engine_source_commit=a37a865a…`, `engine_source_pristine=true`, `engine_commit_verified=true` |
| Lab runner commit | `f522713184fbf2c588867a645d135595f6e49774` |
| Lab adapter commit | `forge-protocol2-bridge` (pristine-transplanted, `ddf01c91`) |
| Evidence | `docs/pb09_20260929/evidence/forge-pristine-20260929/rerun/` (gitignored runtime output) |

## Engine purity

`git status --short -- forge-core forge-game forge-gui forge-ai forge-gui-desktop forge-lda` is empty.
The build itself records `engine_source_pristine=true`, proven by `git diff --quiet` between the
engine base commit and the built commit over all engine module paths. No Rules semantics were
modified; every adaptation is provider glue.

## Pristine FULL107 (executed, real runtime)

`PASS 5 / FAIL 0 / UNKNOWN 58 / BLOCKED 44 / TOTAL 107`, with `CRASH 0`, `TIMEOUT 0`,
`PROTOCOL_FAILURE 0`.

PASS rows (all real engine execution, not construction):
- `PLAYER_COUNT_2P`, `PLAYER_COUNT_3P`, `PLAYER_COUNT_4P`, `PLAYER_COUNT_5P` — real Commander
  lifecycle under Protocol 2.0.0 with engine-owned legality.
- `WS05-CMD-START-2` — CR 103.8a first-player draw skip observed on the current boundary.

BLOCKED: 30 rows lack a current-boundary execution seam (Lab execution path), 14 micro-rules rows
require a constructed mid-game state. All 44 are honestly BLOCKED, none credited.

## Capability results (adversarially checked)

- **Hidden information**: `PRINCIPAL_SCOPED`, `distinct_state_views=4`, `engine_leak_indicators=[]`
  — own hand visible, opponents redacted. The fork-only decision-view seams that pristine lacks are
  not required for this probe.
- **Rules RNG**: `UNCONTROLLED_ENGINE_RNG`, `rng_credit=false`. This is the correct result: the
  pristine engine installs a seed through its public deterministic hook and echoes the value back,
  but exposes no seed accessor, so the Lab refuses to treat the echo as an engine acknowledgement.
  A wrong-reason `ACKNOWLEDGED_ENGINE_SEED` in the first run was found and fixed (see below).
- **Multiplayer**: 2P/3P/4P/5P lifecycle PASS; 6P is a bounded secondary target not yet exercised
  for this candidate.

## Lab-fork vs pristine-upstream delta (PB-09 classification)

| Delta | Classification |
|---|---|
| `MyRandom` seed readback (`bindSeed`/`getRootSeed`/`isExplicitSeed`/`getCallCount`/`clearBinding`) | `LAB_FORK_ADDED_CAPABILITY` |
| Immutable decision-view seams (`CombatDamageDecisionView`, `AmountDistribution*`, `DividedAllocation*`) | `LAB_FORK_ADDED_CAPABILITY` (fail closed on pristine) |
| Concession legality/action (`PlayerController.canConcede`/`concede`) | `HARNESS_DIFFERENCE` (re-expressed over pristine reads) |
| Build versioning `${revision}` vs literal `2.0.14` | `HARNESS_DIFFERENCE` |
| Bridge unit tests (fork-API dependent) excluded on pristine | `QUALIFICATION_COVERAGE_DIFFERENCE` (documented) |

## Wrong-reason defects found and fixed

1. **Runtime-identity mislabelling**: `runtime_identity` hard-labeled the engine commit with the
   Lab fork pin even when the run was bound to a different candidate. Fixed; the field now names
   the actually-bound engine and keeps the harness commit separate. Provenance fix.
2. **Echoed seed credited as engine RNG**: `classify_seed_binding` derived `ACKNOWLEDGED_ENGINE_SEED`
   from value equality alone. A pristine provider that installs a seed via a public hook and echoes
   it earned `rng_credit=true` with no engine proof. Credit now additionally requires the provider's
   own engine-side confirmation; an echo without it is `UNCONTROLLED`. 8 regression tests, fail-before
   proven.
3. **Canonical evidence contamination**: the first PB-09 run executed before the output-isolation fix
   and wrote pristine results into the canonical `qualification/` tree. Restored to canonical main;
   PB-09 evidence now exists only under `docs/pb09_20260929/`.

## Harness changes (owned)

- `FORGE_EXPECTED_ENGINE_COMMIT` override in the launcher and the native-suite identity, so a
  non-fork candidate can be qualified without renaming the fork pin (default unchanged).
- `COMMANDER_LAB_OUT_DIR` override in the runner, so a non-canonical candidate writes its evidence
  beside its own workstream (default unchanged).
- Runtime identity binds the actually-bound engine commit.
- `classify_seed_binding` engine-confirmation requirement + `_engine_confirmed_seed` driver helper.

All Lab-side changes carry their own regression coverage; the default behaviour of existing
fork runs is byte-identical.

## Remaining (not in PB-09's technical reach)

- 44 BLOCKED rows: 30 need a Lab execution seam, 14 need a constructed mid-game micro-rules harness
  — Lab/harness work, not a pristine-candidate defect.
- 58 UNKNOWN rows: per-scenario hidden channels, decision families, replay twins, actual-card
  denominator — all require harness work or a subsequent phase.
- 6P bounded secondary not exercised for pristine.

`PB09_TECHNICAL_QUALIFICATION = COMPLETE`
`PRISTINE_FORGE_RUNTIME_OBSERVED = YES`
`PRODUCTION_PROVIDER = NOT SELECTED`
`ARCHITECTURE_FREEZE = NOT CLAIMED`
