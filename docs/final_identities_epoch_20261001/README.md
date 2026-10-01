# Final candidate identities: current-boundary epoch on `main` `77f99951`

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`. No ranking and no recommendation.

This epoch supersedes `qualification/current-boundary-epochs/4cad91897216-a43e80d96595/` (R-5, `docs/r5_completion_20261001/`) as the current one. The earlier epoch stays read-only and source-bound to the identities it ran on.

## Source lock

| Role | Identity |
|---|---|
| Lab `main` (producer) | `77f99951cf04c66a405ff1a3470d5d0da19ad81d`, tree `06b8661b9700b2e95f3291c518f1b476399a9c95` (#446 + #447) |
| XMage candidate (repin v3) | `37e4df6c914f1e189e24f0ef59fa91734c922436`, tree `dac695ab2862e965cdaa30b0ce67052840dc7a5e` |
| Forge Rules-Core authority (R-1) | `bb0a740d2bef725194798383c2452213ecdd0b37`, tree `4989b5bb35b8279e82f79c1ca99dc698d63d093a` |
| Forge build/materialization source = #11 head | `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c`, tree `000066890decca5ed7b1b889be0ea46d77903aee` |

**XMage `37e4df6c` = `9375f35a` plus three fixes:**
- **F-43** (mage#29, #430): combat-damage source revalidation after a player leaves;
- **F-44** (mage#33, #433): no trigger of a player who left while ordering them;
- **F-45** (mage#35, #442): a copied spell moved to its owner's library.

Main source changed: `GameImpl`, `CombatGroup`, `PlayerImpl`. Mage.Tests 7034/0/0 (run 36825867998, tree-identical). Mage.Verify's 15 card and 3 set errors are pre-existing on `4e59e8b9`.

**Forge `20e3e1f7` = #11 plus:**
- **#13:** R-3/AF01;
- **#16:** #15 no-default hardening and the structured CR 601.2h cost-order projection.

All 19 changed files are under `forge-protocol2-bridge/`. Exact-head Test build #229/#230 and iOS #184/#185 are green. #11 was fast-forwarded to `20e3e1f7`.

**Run:** PB-03 `workflow_dispatch` **36840176563** on `77f99951`, artifact `11152063287` (sha256 `735196d65a5fd56c2c469e8ee679b9f2709fb05a968b23c6f8c3f47a06e8b093`). All 60 entries of the epoch's `CURRENT_BOUNDARY_SHA256SUMS` verified after download.

Lab #444 (merge `3af638b6`) landed on `main` after this run. It adds the parallel lane's v3 lineage lock and Forge bridge gate lock, and rewords the authority notes. It leaves `primary_engine.commit`, `secondary_engine.commit` and `secondary_engine.bridge_source` unchanged, so the engine identities above are still the live pins.

#444 does change Lab producer code. In `XmageFullGameDecisionController` and `XmageFullGamePlayer`, the frame of a departed player's combat damage assignment (F-43 Lab integration) may now unwind natively instead of ending the lane fail-closed. This epoch therefore does **not** cover the bridge on `3af638b6`. PB-03 run 36845107390 on `3af638b6` is the fresh check for that commit. The epoch stays bound to its producer commit `77f99951`.

## Result

| | XMage | Forge |
|---|---|---|
| FULL107 PASS / FAIL / UNKNOWN / BLOCKED | **19 / 0 / 48 / 40** | **5 / 0 / 58 / 44** |
| R-4 demotions (PASS without a current receipt) | 0 | 0 |
| AF00 | PASS | PASS |
| AF01 (20 v2 invariants) | PASS 20/20 | PASS 20/20 |
| AF02, AF03 | PASS, PASS | PASS, PASS |
| AF04 | PASS (R-2 live provenance) | UNKNOWN (R-2) |
| AF05–AF09 | UNKNOWN | UNKNOWN |
| AF10 | PASS (219 native tests) | PASS (217 native tests) |
| AF11 | post-selection only | post-selection only |

There are 24 positive direct receipts: 14 XMage midgame rows and 5 lifecycle rows per candidate. Each engine reports its exact source itself. No result was carried forward.

## Remaining (unchanged, for the Coordinator)

These are the residuals listed in `docs/r5_completion_20261001/README.md`:
- the causal-route rows;
- fixtures whose script starts inside a cast;
- MICRO_COSTS (CR 307.1);
- NEGATIVE_* `DECISION_TIMEOUT`;
- the HIDDEN_* materialization policy;
- Forge has no midgame lane;
- AF05–AF09 are blocked by FULL107 rows;
- AF11 comes after selection.

Under the all-PASS rule neither candidate is eligible today.
