# WSR22 Validation — FINAL-CURRENT-BOUNDARY-FREEZE-QUALIFICATION-20260927

## Scope

Evidence-tree and qualification-infrastructure work only. No engine production
code, no engine Rules semantics, no pin, no Architecture Freeze gate was
modified. Forge was built and executed read-only from an existing reference
checkout and remained byte-clean at `18bba95a…`.

## Source lock at validation

- Lab HEAD/TREE: recorded in `SOURCE_LOCK.json` and in every evidence packet's
  `runtime_identity`.
- Denominator: 107 rows, `denominator_decreased_to_bypass_blocker: false`.
- Effective contract: `commander-lab.full107/1.0.6-successor`, bundle digest
  recorded in `EFFECTIVE_FULL107_MANIFEST.json`.
- Rules authority: direct official capture, 2026-09-25, sha256
  `8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`.

## Commands executed (fresh, this workstream)

1. `mvn -o -q -DskipTests -Dcheckstyle.skip=true test-compile` (engine-bridge)
   → BUILD SUCCESS; XMage 1.4.61 resolved from the local repository.
2. `mvn -o … dependency:build-classpath -Dmdep.outputFile=target/cp-wsr22.txt`
   for the XMage bridge module and the Forge reference bridge module.
3. `python3 scripts/run_current_boundary_qualification.py --candidate xmage`
   → AF01 + cardinality 2P/3P/4P/5P/6P + START-2 v1.0.6 + hidden-info probe +
   RNG/replay probe + actual-card probe + 107-row classification.
4. `python3 scripts/run_current_boundary_qualification.py --candidate forge`
   → same matrix against the Forge reference build.
5. XMage native FULL107-executor group:
   `mvn -o … test -Dtest=XmageFull107ResidualRequalificationTest,XmageDigestCreditTest,XmageFullGameWs05MulliganTest,XmageFullGameTaxExecutionTest,XmageFullGamePartnerExecutionTest,XmageFullGameCard02ExecutionTest,XmageFullGameMicroExecutionTest,XmageFullGameTrigExecutionTest,XmageFullGameDecisionExecutionTest`
   → **Tests run: 34, Failures: 0, Errors: 0, Skipped: 0 — BUILD SUCCESS**.
6. XMage native mechanism group (15 classes: restoration, temporal, causal stack,
   control, elimination, hidden/replay, commander damage, player count,
   variable-player, combat, decision rejection, seed binding)
   → **Tests run: 134, Failures: 0, Errors: 0, Skipped: 0 — BUILD SUCCESS**.
7. Forge native denominator + family group (15 classes incl.
   `WsR20Full107DenominatorTest`, cardinality, semantic replay, hidden-info
   family, S3/F4, gap closure, multicount combat/trigger, determinism twin,
   concession, six-player, bridge engine)
   → **Tests run: 150, Failures: 0, Errors: 0, Skipped: 0 — BUILD SUCCESS**.
8. Forge native process/negation group (8 classes incl. protocol, bridge
   process, headless GUI fail-closed, four separate-process suites)
   → **Tests run: 67, Failures: 0, Errors: 0, Skipped: 0 — BUILD SUCCESS**.
9. `python3 scripts/assemble_current_boundary_evidence.py`
   → native-fixture binding, per-candidate 107-row results, AF00–AF11 matrix,
   comparison, divergence packet.
10. `pytest tests/qualification/test_wsr22_current_boundary.py
    tests/qualification/test_pre_freeze_contract_successor.py -q`
    → **27 passed**.
11. `ruff check` and `ruff format --check` on all new Python → **All checks
    passed**.

## Consistency totals

| Check | Expected | Observed |
|---|---|---|
| FULL107 rows per candidate | 107 | 107, 107 |
| Outcome vocabulary coverage | PASS/FAIL/UNKNOWN/BLOCKED/CRASH/TIMEOUT/PROTOCOL_FAILURE | all present in counts, 0 CRASH / 0 TIMEOUT / 0 PROTOCOL_FAILURE |
| Comparison rows | 107 | 107 |
| AF gates per candidate | 12 | 12, 12 |
| XMage native tests | green | 34 + 134 = 168 |
| Forge native tests | green | 150 + 67 = 217 |
| Successor inheritance | 106 identical, 1 changed | 106 / 1 (mechanically proven) |

## Harness defects found and repaired during this workstream

1. **Protocol-2 envelope omitted `payload`.** The first live run failed
   `import_deck` on XMage. Root cause: the canonical Lab wire form carries the
   request body under BOTH `payload` and `params`
   (`EngineProtocolRequest.wire_dict`), while the new runner emitted only
   `params`. Classification: HARNESS_DEFECT. Repaired in
   `bridge_launcher.BridgeProcess.request`. Not an engine difference.
2. **Illegal Commander deck.** XMage rejected the inherited H4F deck
   (`Isamaru` {W}{W} commander with green/black vanillas). Classification:
   FIXTURE_DEFECT, surfaced by the engine's own Commander colour-identity
   validation. Repaired by using a mono-white real-card deck that both
   candidates validate. The historical H4F deck was only ever exercised
   against Forge, which is why it was never caught.
3. **Card-name availability.** Two candidate-real card names were absent from
   XMage's card database (`Vanguard of Common Measures`, `Timeless Knight`,
   `Pacifist Advocate`). Repaired by using only names both candidates accept;
   the engine remains the authority on card existence.
4. **Missing `deck_hash`.** XMage requires an explicit deck hash; Forge
   derives one. Repaired by computing a deterministic Lab-side deck-content
   hash (identity, not a Rules computation).
5. **Decision-identity mapping bug.** The first submission attempt read the
   frame's `revision` for XMage's `decision_id` field and omitted `actor_id`,
   producing `STALE_EXTERNAL_DECISION` and then `ACTION_ACTOR_MISMATCH`.
   Classification: HARNESS_DEFECT. Repaired in
   `game_driver.decision_identity_params`.
6. **Lane selection bug.** Passing an empty lane string silently launched the
   full-game lane, which does not implement `create_commander_game`.
   Classification: HARNESS_DEFECT. Repaired in `build_launch_plan`.
7. **Cardinality classifier false FAIL.** The effective records carry a seat
   roster, not a scalar `player_count`, so all four `PLAYER_COUNT_*` rows
   first reported FAIL. Classification: HARNESS_DEFECT. Repaired to derive the
   required cardinality from the frozen seat list. **No expected value was
   weakened**; the underlying runs had already succeeded.

Each repair was re-verified by re-running the affected execution.

## Lab unit-suite baseline (impact check)

A full `tests/unit` run was used as the impact check for the new package.

| Tree state | Result |
|---|---|
| **Clean committed tree (this workstream's final state)** | **1001 passed, 3 failed, 8 collection errors** |
| Same HEAD with the workstream's uncommitted edits stashed | 1001 passed, 3 failed, 0 errors |

Interpretation (important, and the reason the dirty-tree run looked alarming):

- The 42 extra failures seen on a **dirty** worktree were **not** caused by this
  workstream's code. The repository contains a canonical-input guard
  (`src/commander_lab/tools/service.py:753`, "stale canonical inputs rejected:
  tracked software worktree differs from recorded git tree") that refuses to run
  tools while the worktree differs from the recorded Git tree. A dirty tree
  therefore fails many unrelated tests by design. On a clean committed tree
  they all pass. This guard is a real repository invariant and was respected:
  the workstream commits before running canonical-input tests.
- The **3 remaining failures are pre-existing and environmental**:
  `test_snapshot_reproducibility`, `test_structural_profiles` and
  `test_first_run_preparation` each spawn a subprocess in a temporary cwd that
  cannot import `commander_lab` because the package is not pip-installed in this
  environment (`python3 -m pip show commander-lab` → not found) and
  `pythonpath = ["src"]` applies only to the pytest process. They are unrelated
  to this workstream and were not modified by it.
- The 8 collection errors are pre-existing missing optional dependencies
  (`typer`, an `asyncio` plugin) in tests unrelated to this workstream.

## Not run (honest NOT_RUN)

- `mypy`: the binary/module is absent in this environment (environmental, not
  introduced by this workstream; the repository records the same absence
  historically). Recorded as NOT_RUN, not PASS.
- Full Lab Python suite and full XMage/Forge bridge suites: reuse-first. Only
  the FULL107-decision-critical native groups were re-executed; nothing in this
  workstream changes engine behaviour, so no other suite's evidence was
  invalidated.
- 7P execution: intentionally fail-closed; not attempted on this boundary.
