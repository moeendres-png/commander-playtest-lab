# Engine Capability / Reuse Matrix — WS-CSN-CAPABILITY-DELTA-20260929

Machine-readable companion: `ENGINE_CAPABILITY_REUSE_MATRIX.json`.
Source lock: `SOURCE_LOCK.md`. Decision: `IMPLEMENTATION_DECISION.md`.
Historical archaeology: `HISTORICAL_ARCHAEOLOGY.md`. Licensing: `EXTERNAL_PROVENANCE_LEDGER.md`.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. The delta in one sentence

The current-boundary XMage column fails **44 of 107** rows closed, and
**every single one of those 44 failure reasons cites the same thing**: the
provider reported `starting_state_injection_supported = false`. That is a
*route* problem, not a *capability* problem. The Lab's own Java bridge already
contains an engine-native mid-game starting-state materialiser that builds those
positions from XMage public APIs, revalidates them with engine-authoritative
state-based actions plus layers, and proves them with a strict native readback
compared field-by-field. It was constructed from exactly **one** production
site, always with a `null` restoration, so it had been reachable only from
JUnit. Independently, the same class already publishes a per-dimension manifest
of exactly which starting-state dimensions it can construct — and that manifest
had **exactly one caller, a test**.

| Current-boundary XMage outcome | Count |
|---|---|
| `PASS` | 4 |
| `FAIL` | 0 |
| `BLOCKED` | 44 |
| `UNKNOWN` | 59 |
| `SAME_SEMANTICS` rows (Forge vs XMage) | **0** |

## 2. Structural proof of the delta (all `DIRECTLY_VERIFIED`)

| Claim | Evidence |
|---|---|
| The restoration seam exists and is engine-native | `engine-bridge/.../XmageNativeStateRestoration.java` (1381 lines) — javadoc: "Translates an explicit requested starting state … into engine-native state through public engine APIs only, then validates with engine-authoritative state-based actions plus layers and proves the result with a strict native readback" |
| It was reachable only from tests | `grep -rn "new XmageFullGameSession"` — 1 production site (`XmageFullGameJsonlBridge.java:183`, no restoration) and ~40 JUnit sites, all passing one |
| The dimension manifest was reachable only from tests | `grep -rn "dimensionsPayload"` — 1 definition, 1 caller: `XmageNativeStateRestorationTest.java:801` |
| The causal reconstruction classes were reachable only from tests | `XmageCausalStackReconstruction`, `XmageCausalEliminationReconstruction`, `XmageControlDivergenceReconstruction`, `XmageTemporalProgressionDriver`, `XmageHiddenStateRestoration` — every caller is under `src/test/java` |
| The coarse bit is what the pipeline reads | `FULL107_XMAGE_RESULTS.json` — all 44 `BLOCKED` rows, `failure_reason` = "…this candidate reports starting_state_injection_supported=False" |
| The project already recorded the consequence | `docs/pre_freeze_completion_20260927/PB03_ROOT_CAUSE_AND_REMEDIATION.md`: "**Nothing consumes that manifest at the qualification boundary.**" |
| The existing native suites already prove the mechanisms | `XmagePb03Tier1RowsTest` (12), `XmagePb03Tier2StackTest` (8), `XmagePb03Tier2CmdZoneTest` (10), `XmagePb03Tier2ControlTurnTest` (2), `XmageFull107ResidualRequalificationTest` (3) — all mapping 1:1 onto blocked fixture families |

## 3. Capability matrix (condensed)

Full fields — CR domain, actual cards, per-engine status, exact symbols,
runtime evidence, licensing, provenance, integration classification, leverage,
ownership conflict, next action — are in the JSON. Condensed:

| ID | Mechanism | CR | Lab before | Pinned XMage | Upstream XMage | Pristine Forge | Phase.rs | Class | Status now |
|---|---|---|---|---|---|---|---|---|---|
| **CAP-01** | Mid-game starting-state materialisation + exact construction proof | 103.8, 110.2, 702.91a, 400.3, 903.6, 903.10a, 613, 704.5 | constructed, test-only | PRESENT | PRESENT (`Game.cheat(...)`, `GameOptions`) but upstream caller is test-only | PARTIAL (`GameSnapshot`, `GameState` text `\|IsCommander`/`\|Damage:`) | `pub mod scenario` builder, production | `ENGINE_NATIVE_REUSE` | **IMPLEMENTED + RUNTIME VERIFIED** |
| **CAP-02** | Per-dimension starting-state manifest over Protocol 2.0.0 | evidence policy | published, unconsumed | PRESENT | no upstream analogue | none | none | `EXTRACT_AND_GENERALIZE` | **IMPLEMENTED + RUNTIME VERIFIED** |
| **CAP-03** | 4-player multi-defender attacker declaration | 508.1, 509.1, 510.1, 103.8 | BLOCKED | PRESENT | PRESENT + `test2x2Block`, `testCanBlockMultiple` | PRESENT (`orderBlockers`, `orderAttackers`) | `multiple_attackers_mixed_blocking` | `ENGINE_NATIVE_REUSE` | **IMPLEMENTED + RUNTIME VERIFIED** |
| **CAP-04** | Commander damage matrix restore | 903.10a, 510.1c | BLOCKED (RG-02B proven in JUnit) | PRESENT | PARTIAL | PRESENT and generic | `commander.rs` CR 903.10a map | `ENGINE_NATIVE_REUSE` | **REACHABLE ON THE LANE** |
| **CAP-05** | Commander zone replacement | 701.7, 903.8, 614.6 | BLOCKED (8 rows) | PARTIAL (causal stack is JUnit-only) | PARTIAL | PRESENT | issues 2377 / 2863 | `EXTRACT_AND_GENERALIZE` | correctly rejected with a code |
| **CAP-06** | Control/owner divergence | 301.2, 613, 702.2b | BLOCKED | deliberately rejected; RG-04 probe-proven cause | `prepareControllableProxy` + `ControlChangeTest` | effect-driven only | controller tests | `PORT_FROM_DONOR` | correctly rejected with a code |
| **CAP-07** | Life-0 elimination as a requested state | 104.1, 800.4a | BLOCKED | rejected — engine re-derives starting life | elimination only via real damage | not verified | `sba.rs` `zero_life_player_loses` | `EXTRACT_AND_GENERALIZE` | **CONSTRUCTION_MISMATCH REPRODUCED** |
| **CAP-08** | Seeded per-game Rules RNG | 1.3, 103.3, 702.91a | PARTIAL; PB-08 BLOCKED | **DEFECTIVE** — `RandomUtil` is one process-wide static; `putCardsOnTopOfLibrary(anyOrder=true)` uses bare `Collections.shuffle` and ignores the seed | same defect | instrumentable | issue 6337 is a filed instance of the same class | `REFERENCE_ONLY` → `NEW_IMPLEMENTATION_REQUIRED` | dispatch packet, not implemented |
| **CAP-09** | Divided-as-you-choose allocation + blocker ordering | 510.1c, 510.1d, 601.2d, 701.9d | BLOCKED | PRESENT (`CombatGroup.blockerDamage` → `getMultiAmountWithIndividualConstraints`) | PRESENT + trample/deathtouch tests | PRESENT and explicit | **GAP** (no test named for menace / 510.1c order / 601.2d) | `ENGINE_NATIVE_REUSE` | partially reachable |
| **CAP-10** | Per-scenario hidden-information channels | 401, 408, 400.3 | UNKNOWN / PB-06 | PARTIAL (redactor + honeycards) | `LastKnownInformationTest` | not verified | `visibility.rs` | `ENGINE_NATIVE_REUSE` | owned elsewhere; lane already returns counts-only per seat |
| **CAP-11** | Clean-process semantic replay twin | evidence policy | BLOCKED / PB-08 | ABSENT on the pinned lanes | PRESENT but self-deprecated (`GameReplay`: "outdated and not used. TODO: delete") | `GameSnapshot` in-memory only | `PersistedGameState` + `persist.rs` + shipped "Load Game State" | `REFERENCE_ONLY` → `NEW_IMPLEMENTATION_REQUIRED` | not implemented |
| **CAP-12** | Player control-change / turn stealing | 707, 800.3, 800.2 | ABSENT from the bridge | ABSENT (default `prepareControllableProxy` inherited) | PRESENT | not verified | `turn_control.rs` | `ENGINE_NATIVE_REUSE` | separate dispatch |
| **CAP-13** | CR 601.2c library ordering; `chooseRingBearer` | 601.2c, 701.38a | INHERITED (never a decision) | PARTIAL — real `TargetCard` loop for `anyOrder=false`; RNG for `anyOrder=true`; ring bearer resolved internally | same | PRESENT (`willPutCardOnTop`, `orderMoveToZoneList`) | none found | `ENGINE_NATIVE_REUSE` | folded into CAP-08 dispatch |

## 4. What the runtime probe actually measured

Command:
`python scripts/run_midgame_capability_probe.py --out qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json`

Real pinned process (`org.mage:mage:1.4.61`, `engine_commit=b1959698…`,
`xmage_code_source=…/mage-1.4.61.jar`), one game per JVM, Protocol 2.0.0,
seed `424242`, 16 previously blocked or blocked-adjacent rows, every decision
submitted from the engine's own offered option set.

| Outcome | Count | Rows |
|---|---|---|
| `ENGINE_NATIVE_REACHABLE` | **8** | `WS05-MP-COMBAT-4`, `WS05-MP-COMBAT-5`, `WS05-CMD-ELIM-4`, `WS05-CMD-DMG-SPLIT`, `WS05-CMD-PARTNER-ZONE`, `WS05-CMD-TAX-2`, `MICRO_COMBAT`, `CARD_02` |
| `ENGINE_STATE_ACCEPTED` (state materialised, obligation not executed) | 3 | `WS05-MP-BLOCK-4`, `WS05-MP-TURN-5`, `MICRO_REPLACEMENT` |
| `CONSTRUCTION_MISMATCH` | 1 | `WS05-MP-ELIM-PRIO-3` — `life P2: requested 0 observed 40` |
| `ENGINE_REJECTED` (engine's own code) | 4 | `WS05-MP-PRIO-3` (`UNSUPPORTED_ZONE`), `WS05-CMD-DMG-CONTROL` (`UNSUPPORTED_CONTROL_DIVERGENCE`), `WS05-CMD-ZONE-GY-YES` (`UNSUPPORTED_ZONE`), `MICRO_ZONE_CHANGES` (`UNSUPPORTED_ZONE`) |

Two of these are independent confirmations of existing project findings on the
new production surface: the life-0 re-derivation (already terminal in
`PHASE2_CLOSEOUT.md`) and the stack-placement / control-divergence rejections
(already terminal in the dimension manifest).

Note that `WS05-MP-ELIM-PRIO-3` was **not** in the probe's reachable set on the
first run and is now correctly a mismatch rather than a reachability claim.
Neither the coarse global bit nor the classification was adjusted to make it
pass.

## 5. Answering the mandated current-day delta questions

1. **Which current Lab rules/bridge code duplicates functionality already present natively in XMage?** None was found that could simply be deleted. The Lab's semantic code is thin: it composes engine APIs and projects engine-authored options. The one true duplication is *capability reporting*: the Lab published a global `false` while the engine seam published a per-dimension truth beside it.
2. **Which UNKNOWN/BLOCKED cases could be solved by exposing an already-existing XMage API rather than changing Rules semantics?** All 44 BLOCKED rows and the 15 `UNKNOWN` rows whose reason is "the remaining families are not offered in the opening phase" — 59 of 107 rows, one mechanism.
3. **Which capabilities now present in the `b1959698…` Mage lineage are still not consumed by Commander Lab?** `dimensionsPayload()`; `XmageCausalStackReconstruction`; `XmageCausalEliminationReconstruction`; `XmageControlDivergenceReconstruction`; `XmageTemporalProgressionDriver`; `XmageHiddenStateRestoration`; and the restoration-aware `XmageFullGameSession` constructor. All six were test-only before this workstream; two are now production-reachable.
4. **Which capabilities proven or added in recent Mage residual work are already obsolete as blockers in older reports?** RG-02 (commander damage restore), RG-06A (ordered library / face-down), RG-07 (exact-N target offering), RG-08 (replacement timing) are all in `b1959698…` and were already `DIRECTLY_VERIFIED` on `main`; they were never the cause of the 44 blocked rows. The actual cause was the unreachable route, which no residual workstream addressed.
5. **Which Forge capabilities exist in pristine upstream `a37a865a…` versus only in the Lab-modified fork?** Verified in pristine upstream: `PlayerController.orderBlockers/orderBlocker/orderAttackers/assignCombatDamage/divideShield/orderSimultaneousSa/confirmReplacementEffect/chooseStartingPlayer/willPutCardOnTop/orderMoveToZoneList/declareAttackers/declareBlockers`; `GameSnapshot`; `GameState` text save with `|IsCommander` and `|Damage:<n>`; `MulliganService` with player-rotation-based algorithms; a headless-capable `forge-game` + `forge-ai` + `PlayerControllerAi` stack. Not found in pristine upstream: any scenario file format, any `forge.game.scenario`, any `TestPlayer`, and a headless load entry point — `forge-game/src/test` contains two files. Forge has **no** pristine equivalent of the mid-game injection seam, so the Lab's own fork additions are not redundant with upstream here.
6. **Which Lab Forge additions should be unnecessary because upstream already has a generic mechanism?** None verified in this workstream, and I did not attempt it: PB-09 identity is open and Forge evidence is not admissible for capability ranking until it closes. Recorded as **not investigated**, deliberately.
7. **Which old upstream XMage/Forge PRs or issues contain fixes/tests relevant to our unresolved interactions?** Verified upstream *regression tests* (stronger than issue numbers): `DamageDistributionTest#test2x2Block`, `CanBlockMultipleCreaturesTest#testCanBlockMultiple`/`#testMultipleBlockWithTrample`, `combat/rollback/*` (7 files), `lki/LastKnownInformationTest#testPersistTriggersInTime`, `mulligan/LondonMulliganTest`, `multiplayer/ControlChangeTest`, `multiplayer/PlayerLeftGameRange{1,All}Test`, `cards/continuous/CommandersCastTest`, `cards/continuous/CommandersGameRestartTest`, `turnmod/ExtraTurnsTest`. Verified Forge issues: `#10142` (commander damage reset after restart, **open**), `#6389` (cloned Grothama), `#9156` (Duel Commander limitations). Honest gap: no verifiable XMage issue/PR numbers were obtained for multi-defender assignment, CR 103.8a draw, non-GUI mulligan control, exact-N target offering, or replacement-ordering prompts. No numbers were invented.
8. **Which Manabrew techniques improve our evidence without importing its Rules semantics?** Seeded, instrumented RNG with a per-call ordinal counter and opt-in backtrace on a specific bound; identity-neutral canonical ordering of choice spaces via a stable cross-engine `parityId`; snapshot-by-snapshot diff against a persisted baseline with a first-mismatch reporter; matrix mode with a master seed. All are **methodology**; the harness is AGPL-3.0-or-later and must be reimplemented, never copied.
9. **Which phase.rs tests/bugs expose interactions not represented in our corpus?** `triggers_ordering_parity_tests.rs` (including `ordering_parity_sweep`, `n_d_intervening_if_case_a_prompts`, `n_d2_commander_intervening_if_is_fed_by_a_sibling_membership_write`, `s5_multiplayer_three_players`); `combat.rs` `multiple_attackers_mixed_blocking`, `bushido_becomes_blocked_fires_once_when_double_blocked`, `becomes_blocked_by_creature_fires_for_each_blocker`, `per_defender_cap_limits_only_that_defender`; `commander.rs` CR 903.10a; issues **#6337** (non-deterministic HashMap tie-break — the same determinism defect class as our CAP-08), **#6914** (Kediss extra damage), **#9021** (Duel Commander limits), **#6416** (extra turn out of sequence).
10. **Other engines with uniquely useful generic tests or implementations?** Beyond XMage/Forge/Manabrew/phase.rs, essentially none. `Baldugar/mtg-forge-ts` is the only lead that claims the exact triad (programmatic headless API + save/load + deterministic replay) in one place, at 0 stars with no source read — labelled `HYPOTHESIS`. `Cockatrice` is a tabletop, not a rules engine. `wanqizhu/mtg-python-engine` (MIT) is dormant. `phase.rs`'s production `GameScenario` builder is the one genuinely reusable external *design*, and it is reference-only here.
11. **Where can we delete or simplify local semantic code?** `config/rules_engines.json` and both capability payloads may stop treating `starting_state_injection_supported` as the starting-state truth once the current-boundary pipeline classifies against the per-dimension manifest. No other deletion was justified: every other piece of Lab semantic code is a thin composition or an option projection, and deleting one would remove the external-decision seam rather than a duplicate.
12. **Which single integration cluster yields the largest gain without colliding?** The one implemented: production-reachable mid-game starting-state materialisation plus the per-dimension manifest consumer, on a new `midgame` lane. One mechanism, 59 of 107 rows, no edit to any file owned by an open PR.

## 6. Ownership census — free complement actually used

`engine-bridge` main sources and `current_boundary` were enumerated against the
union of files touched by all 43 open PRs. **Owned and untouched by this
workstream**: `XmageNativeStateRestoration.java` (PRs #284/#294),
`XmageFullGameSession.java` (#284), `XmageFullGameJsonlBridge.java` (#284),
`JsonlBridge.java` (#300/#284), `XmageGameManager.java` (#300/#284),
`game_driver.py` (#300/#289), `full107.py` (#300/#289), `bridge_launcher.py`
(#299/#289), `engine/rules/full_game.py` (#284).

**Used (free)**: `Main.java` (one added lane branch), plus five new files. The
new lane reuses every owned class by *composition* rather than by editing it,
which is precisely why this cluster could be delivered while #284, #289, #299
and #300 are all open.

## 7. Classification discipline

- `DIRECTLY_VERIFIED` — observed in a real pinned process: capability manifest,
  16-row probe, 4-player combat declaration, exact construction verdict,
  principal-scoped counts.
- `CODE_DERIVED` — read from source without executing it: the 41-construction
  call-site census, the `dimensionsPayload` caller census, the upstream/Forge
  symbol inventories.
- `EXTERNALLY_RULE_VALIDATED` — **not claimed for any row**. No row in this
  workstream was compared against the current official Comprehensive Rules text
  or Oracle text by a second party. The CR references in the matrix are the
  mechanisms the frozen records themselves name, not a fresh official adjudication.
- `UNKNOWN` — CAP-08 per-game RNG isolation, CAP-11 replay twin, and whether an
  XMage deserialised `Game` can be *resumed* rather than merely viewed.
- `CODE_DERIVED != RUNTIME_VERIFIED` is respected throughout: every
  `ENGINE_NATIVE_REACHABLE` row carries an engine-produced digest and a
  field-level mismatch list, and every non-reachable row carries the engine's own
  rejection code.

## Review remediation (2026-09-29)

The authoritative record of the six closed review findings and the WS17
artifact/hash repair is `docs/engine_capability_reuse_delta_20260929/REVIEW_REMEDIATION_20260929.md`.
Probe counts in this document that predate that remediation are marked historical;
the current receipt is the 29-row receipt at the remediated head and every digest in
it was regenerated because the arrival observation and the digest scope changed.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
