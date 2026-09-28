# WSR27/WSR28/WSR30 Current-Boundary Consumption — Durable State

Bounded state for the current qualification-remediation stream. The campaign
state remains `WORKSTREAM_STATE.yaml` (WSR22 successor); this file records the
WSR27/WSR28/WSR30 remediation line only. Not a qualification report.

## Source lock

| Item | Value |
| --- | --- |
| Lab repository | `moeendres-png/commander-playtest-lab` |
| Lab branch | `wsr27/final-candidate-remediation-20260928` |
| Lab base | `origin/main` = `933d5df564b5dc77d678935bc79c6554459c347b` (PR #279 merge) |
| Lab commit 1 | `5b652b44` — AF03 colour probe isolates colour identity |
| Lab commit 2 | `f25cbeb2` — provider principal binding consumed; START-2 observation fixed |
| Forge Rules Core | `ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree `fc3387bf37aab19d780b2939a235309ed32b0492` |
| Forge bridge/evidence head | `e15f37d6b2b`, tree `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b` |
| Forge PR | #5, DRAFT, base `master` |
| Forge worktree (built) | `/tmp/opencode/forge-pr4` — ephemeral; recreate from the pushed branch if absent |
| Runner default Forge workspace | `/home/moeen/code/ws-forge-full107-cdq-20260926` (WSR20 tip `18bba95a452`) — do NOT mutate; override with `FORGE_WORKSPACE` |

## Completed at this head

- Forge `dac21f81a9d` / `e15f37d6b2b` (Draft PR #5):
  - PB-06 requester binding: `observer_player_id` + per-player `is_actor` from
    the validated observer context; public view marks nobody.
  - PB-08 creation seed acknowledgement from `MyRandom.getRootSeed()/
    isExplicitSeed()`; reject/divergence fails closed with `SEED_UNSUPPORTED`;
    unseeded launches clear a stale explicit binding.
  - Tests `Wsr30RequesterBindingTest` (7) + `Wsr30SeedAcknowledgementTest` (6);
    fail-before with each production change surgically removed; pass-after 13/13;
    full bridge suite **301/301**.
- Mechanical equivalence (Lab's own `verify_engine_identity`):
  `e15f37d6b2b` vs `ef958ee9` → `engine_equivalent: true`,
  `justification: RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL`, all six Rules-Core
  module main-source trees byte-identical, `differing_modules: []`.
- Lab `f25cbeb2`:
  - START-2 observation now reads `observer_player_id` and derives
    `hand_count`/`library_count` from the marked principal's `zones.hand` /
    `zones.library_size`; no provider identifier is persisted.
  - Scoping validator distinctness comparison excludes provider
    requester-binding metadata, so varying only the marker cannot fabricate
    distinct views; the marker is still consumed by the actor and
    opponent-content checks.
  - Tests: impacted slices 51 passed; `tests/qualification` 365 passed,
    2 skipped; mypy strict and ruff clean.
- Both Lab commits are pushed; `5b652b44` is preserved remotely.

## Not done (do not read as done)

- `source_lock.FORGE_BRIDGE_EVIDENCE_*` still names PR #4 head `d5bd22d1bf`
  (tree `575cbbd6de...`, PR 4). The repin to PR #5 head is the first step of
  the regeneration block below and must be committed with the regenerated
  evidence, not before it.
- No qualification evidence has been regenerated against `e15f37d6b2b`.
  `AF03_FORGE.json`, `HIDDEN_INFO_FORGE.json`, `RNG_REPLAY_FORGE.json`,
  `PROVIDER_BLOCKERS.json` and `PROVIDER_READINESS_PACKET_20260928.md` still
  describe the `d5bd22d1bf` run.
- AF05/PB-06 and AF09/PB-08 Lab rows are expected to move (Forge side is now
  bound and acknowledged) but are unproven until the run.
- XMage generic B4-D lane remains not principal-scoped (identical views to
  every requester); untouched here.
- `WS05-CMD-START-2` should become observable for Forge after `f25cbeb2`; it
  remains UNKNOWN for XMage until that candidate is scoped.
- The START-2 row credits PASS on observed absence of draw frames/events plus
  a present zone-count snapshot; it does not compare counts before/after
  because no baseline is taken. Recorded as a qualification-design finding,
  not changed here.

## Exact next action (single uninterrupted block)

1. Update `FORGE_BRIDGE_EVIDENCE_COMMIT`/`_TREE` to
   `e15f37d6b2b` / `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b`, `_PR` to 5, and
   update `tests/qualification/test_current_boundary_pb09_engine_identity.py`
   (`BRIDGE_HEAD`, `BRIDGE_TREE`, PR, and the bridge-equivalence test) to match.
2. Ensure the Forge worktree at the exact head is built:
   `mvn -o -pl forge-protocol2-bridge -am test-compile -DskipTests` (and the
   `target/cp-wsr22.txt` classpath manifest exists).
3. Run, from a clean Lab tree at the commit holding both the repin and this
   state:
   `FORGE_WORKSPACE=/tmp/opencode/forge-pr4 PYTHONPATH=$PWD/src <venv>/bin/python scripts/run_current_boundary_qualification.py --candidate forge`
   (long-running: live FULL107 rows + native suite receipts).
4. Review generated evidence against `e15f37d6b2b`, commit the regenerated
   artifacts with the repin, and re-run the impacted Lab tests.
5. Then continue to the XMage principal-scoping defect and the remaining
   blocker graph.

## Evidence classifications

- DIRECTLY_VERIFIED: bridge test runs, fail-before/pass-after, mechanical
  Rules-Core equivalence, Lab test suites.
- CODE_DERIVED: mechanism claims about the projection and seed binding.
- UNKNOWN / absent: all Lab runtime evidence at the new head.
- No authority gate was reached; `PRODUCTION_PROVIDER = NOT SELECTED` and
  `ARCHITECTURE_FREEZE = NOT CLAIMED` are unchanged.
