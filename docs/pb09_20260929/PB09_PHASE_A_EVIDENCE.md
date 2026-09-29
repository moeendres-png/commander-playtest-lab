# PB-09 — Pristine-Upstream Forge Runtime Baseline: Phase A evidence

Date: 2026-09-29. Execution profile for this continuation: `opencode-go/deepseek-v4.1-flash`
(operator-directed; recorded as the session's reported model identity, not as a project-wide
launcher activation claim).

## Source lock (verified by read, not inherited)

| Identity | Value |
|---|---|
| Lab main consumed | `afe09c61d4ad90f89c28ff75ac7439a20b89cfdd` / tree `0d5b3f0d9020cc99131dd92a41a9615c61bbac8a` |
| PB-09 Lab branch | `muse-xhigh/pb09-pristine-forge-20260929` @ `8c6b0b57` + this commit |
| Pristine upstream Forge | `Card-Forge/forge@a37a865a53280dd8ad6fad3384d69611e8c5a42f` / tree `4471ff068dd23127fc5878bdffa0c0e6de8e6c28` |
| Lab Fork Rules Core | `moeendres-png/forge@ef958ee9` / tree `fc3387bf` (reference only) |
| Bridge/evidence transplanted | `e15f37d6` (PR #5) `forge-protocol2-bridge/pom.xml + src` only |
| Pristine checkout | `/home/moeen/code/csn-final-bakeoff/muse/forge-upstream-pristine` (detached at `a37a865a`) |
| Fork reference checkout | `/home/moeen/code/csn-final-bakeoff/muse/forge-fork-ref` |

## Headline result

`PRISTINE_FORGE_RUNTIME_REACHABLE = YES`

Direct evidence (executed, transcript captured in `evidence/pristine-smoke-transcript.json`):
the transplanted bridge launched inside the pristine checkout and, over stdio JSONL,
`start_engine` → `ok`, `get_capabilities` → `ok`, `get_provider_version` → `ok`, process exit 0.

Build-derived identity is now available (this closes the operator-supplied weakness of the
historical PB-09 run at the identity level):

```
engine_build_commit: a37a865a53280dd8ad6fad3384d69611e8c5a42f
engine_build_tree:   4471ff068dd23127fc5878bdffa0c0e6de8e6c28
engine_build_source: build:bridge.properties:git
engine_build_dirty:  true            # harness present; engine modules unmodified (see purity proof)
engine_commit_source: env:FORGE_ENGINE_SHA
engine_commit_verified: false        # honest: dirty worktree, not a clean pristine build
```

### Engine purity proof

`git status --short -- forge-core forge-game forge-gui forge-ai forge-gui-desktop forge-lda`
is empty: every engine module is byte-identical to `a37a865a`. The only worktree changes are
root `pom.xml` (module wiring) and the added `forge-protocol2-bridge/` harness module.
`forge-bridge`/adapter changes are provider glue; no game/Rules semantics were modified.

## LAB_FORK_ADDED_CAPABILITY vs PRISTINE_UPSTREAM (adapter-visible, proven by build)

Every difference below was discovered by compiling the fork-authored bridge against pristine
upstream. None was repaired by changing engine code; each is recorded as candidate evidence.

1. **Seed readback / explicit-seed control** — upstream `forge.util.MyRandom` exposes only
   `getRandom()` / `setRandom(Random)` (documented upstream as the deterministic-simulation
   hook). The fork added `bindSeed`, `getRootSeed`, `isExplicitSeed`, `getCallCount`,
   `clearBinding`.
   *Pristine handling:* the adapter installs a seeded provider through the upstream setter
   (`PristineSeedBinding`) — seeding is real — but reports
   `explicit_seed=false`, `rules_root_seed=null`, `rules_calls=null`,
   `engine_readback=UNAVAILABLE_UPSTREAM_PRISTINE`. A divergent install can no longer be
   detected, so the creation acknowledgement refuses instead of faking it.
   *Classification:* `LAB_FORK_ADDED_CAPABILITY` (engine-level seed proof).

2. **Immutable decision-view seams** — `CombatDamageDecisionView`/`CombatDamageSelection`,
   `AmountDistributionDecisionView`/`Selection`, `DividedAllocationDecision*` exist only in
   the fork (e.g. `CombatDamageDecisionView` added by fork commit `2081f2ca`).
   *Pristine handling:* fail closed. `assignCombatDamage` throws
   `BridgeUnsupportedDecision`; the divided-allocation target path throws; the three
   fork-only overrides were removed.
   *Classification:* `LAB_FORK_ADDED_CAPABILITY` (decision-representation seam).

3. **Concession legality seam** — the fork added `PlayerController.canConcede()`/`concede()`;
   pristine has neither.
   *Pristine handling:* re-expressed in the adapter over pristine reads
   (`player.isInGame()`, `!getGame().isGameOver()`, `player.concede()` +
   `checkGameOverCondition()`), mirroring upstream `PlayerControllerHuman.concede`.
   *Classification:* `HARNESS_DIFFERENCE` (no engine change required).

4. **Build versioning** — fork uses CI-friendly `${revision}`; pristine pins `2.0.14`.
   *Pristine handling:* literal `2.0.14` in the transplanted bridge pom.
   *Classification:* `HARNESS_DIFFERENCE`.

5. **Harness test sources** — fork-authored bridge tests reference the fork-only APIs above.
   They cannot compile upstream without engine changes, so the pristine harness module
   excludes test compilation via a documented `maven.test.skip` property. The runtime
   boundary is therefore qualified by executed evidence, not by the fork's unit suite.
   *Classification:* `QUALIFICATION_COVERAGE_DIFFERENCE` (recorded, not hidden).

## Honest limits of this evidence

- This is Phase A (runtime reachability + identity). **No FULL107 row credit is claimed.**
  The pristine FULL107 matrix is NOT_RUN in this record.
- `engine_build_dirty=true` and `engine_commit_verified=false` mean the identity is
  build-derived but from a harness-bearing worktree. A clean pristine build (harness
  materialized outside the engine worktree, or a committed harness commit) is required
  before any row-level credit binds to a clean source identity.
- Capability payload excerpt (pristine): `legal_actions_supported=false`,
  `action_submission_supported=false`, `event_log_supported=false`,
  `mulligan_supported=false`, `concede_supported=true`, `max_players=6`,
  `commander_supported=true`, `commander_damage_visible=true`, `commander_tax_visible=true`.
  These are provider-reported capabilities, not qualification results.

## NEXT (Phase B, exact)

1. Commit the harness wiring so build identity is clean (`engine_build_dirty=false`).
2. Generate a clean pristine identity receipt (commit/tree of the harness commit + pristine engine).
3. Run the current-boundary runner against the pristine candidate with `FORGE_WORKSPACE`
   pointed at the pristine checkout, produce the 107-row matrix with explicit
   PASS/FAIL/UNKNOWN/BLOCKED, and bind every row to the two identities.
4. Adversarially falsify each new PASS (seed acknowledgement must NOT be claimed for
   pristine; divided-allocation/combat rows must show BLOCKED, not PASS).
5. Publish as a Draft PR.

`PRODUCTION_PROVIDER = NOT SELECTED` · `ARCHITECTURE_FREEZE = NOT CLAIMED`
