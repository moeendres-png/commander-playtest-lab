# HANDOFF — WS-CSN-CAPABILITY-DELTA-20260929

Workstream: `research/csn-engine-capability-delta-20260929`
Executor: `opencode-go/space-bunny-free` at native `max`
State: **scope COMPLETE** for the audit and the selected cluster; one follow-up
dispatch issued; two owned surfaces deliberately left for their current owners.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Source Lock

| Field | Value |
|---|---|
| Lab repository | `https://github.com/moeendres-png/commander-playtest-lab.git` |
| Base HEAD | `2e28866f2bab2981f0b8da2d9a7a493cd3f424cf` (`Merge PR #298: fix XMage unlimited-block capacity`) |
| Base TREE | `0c7b0603cdc0f0958add7e9bf9f23c0f023ec1ff` |
| Workstream branch | `research/csn-engine-capability-delta-20260929` |
| Workstream HEAD | `cb017b74cfa1af9004036bd48e2c518d3194a56b` |
| Workstream TREE | `fbf9069cd14bf5b8506328073009e140def58386` |
| Worktree | `/home/moeen/code/ws-csn-capability-delta-20260929` |
| PR | **#304** — https://github.com/moeendres-png/commander-playtest-lab/pull/304 |
| XMage pin | `b19596980f2734496ea1896504253e1bdd2756dd` (Lab compatibility fork, MIT, **not** pristine upstream) |
| XMage artifact executed | `org.mage:mage:1.4.61`; runtime proof `xmage_code_source=…/org/mage/mage/1.4.61/mage-1.4.61.jar` |
| Forge Rules-Core pin | `a37a865a53280dd8ad6fad3384d69611e8c5a42f` (GPL-3.0) — **read-only, not executed, not re-attributed** |
| Forge bridge source | `4753bb7c72ea60d653121e0bab989077b4009f9c` — untouched |
| Toolchain | JDK 21.0.12.1, Maven 3.9.12 offline, Python 3.12, mypy 2.3.1 |

No pin was changed. The pre-existing `main` worktree was stale at `e91819ae…`
and was not used as an edit surface.

## 2. Work Completed

**Audit.** Fresh source lock; active-ownership census over all 43 open PRs
against every candidate surface; current-boundary blocker census by mechanism;
internal history archaeology; external research over pinned XMage, upstream
`magefree/mage`, pristine Forge, Manabrew, phase.rs and a donor sweep; a
13-capability machine-readable matrix.

**Finding.** All 44 `BLOCKED` rows of the 107-row denominator cite one coarse
capability bit. `XmageNativeStateRestoration` already implements the missing
capability — engine-native placement, engine-authoritative revalidation, strict
native readback compare with digests — and had **exactly one production call
site, always `null`**, plus a per-dimension manifest whose **only caller was a
test**. The project's own `PB03_ROOT_CAUSE_AND_REMEDIATION.md` had already
recorded: *"Nothing consumes that manifest at the qualification boundary."*

**Implementation.** A new Protocol-2 `midgame` lane that composes the existing
seam, edits **no file owned by any open PR**, adds **zero Rules semantics**,
and publishes the per-dimension manifest. A Python consumer reads that manifest
and refuses to fall back to the coarse bit. A probe drives a real pinned
process and writes a machine-readable receipt.

## 3. New Findings

1. **The blocker is a route, not a capability.** Independently confirmed from
   upstream: `Mage/src/main/java/mage/game/Game.cheat(...)` and
   `GameOptions {stopOnTurn, stopAtStep, skipInitShuffling, globalEmblemCards}`
   are main-source production classes whose only verified upstream caller is
   `CardTestPlayerAPIImpl` under `Mage.Tests`. Upstream has the same gap.
2. **A second production mid-game route exists and is self-deprecated.**
   `Mage.Server GameController.saveGame()` + `GameReplay.loadGame()` is reachable
   through `ClientCallbackMethod.REPLAY_GAME → User#ccReplayGame →
   ReplayManagerImpl#replayGame`. Its own javadoc reads *"Replay system, outdated
   and not used. TODO: delete"*. A dependency on it would be a dependency on a
   class scheduled for deletion.
3. **XMage's Rules RNG is split and one branch is unseedable — new, not in any
   prior project report.** `RandomUtil` is a single process-wide static
   `java.util.Random`; `GameState` has no per-game RNG field;
   `PlayerImpl.putCardsOnTopOfLibrary(..., anyOrder=true)` uses bare
   `java.util.Collections.shuffle`, which builds a clock-seeded `Random` and
   ignores `setSeed` entirely. Consequence: "in any order" library effects are
   not seed-controlled, and per-game seed isolation does not hold under
   concurrency. phase.rs issue **#6337** is the same defect class, filed.
4. **Pristine Forge has no mid-game injection seam at all.** Exhaustive filename
   search over 58,949 pinned paths found no scenario format, no
   `forge.game.scenario`, no `TestPlayer`; `forge-game/src/test` holds two files.
   This **reverses** the usual expectation: the Lab's Forge-fork additions are
   not redundant with upstream here.
5. **Forge's `PlayerController` is the cleanest decision-seam abstraction found
   anywhere** — `orderBlockers`, `orderBlocker`, `orderAttackers`,
   `assignCombatDamage`, `divideShield`, `orderSimultaneousSa`,
   `confirmReplacementEffect`, `chooseStartingPlayer`, `willPutCardOnTop`,
   `orderMoveToZoneList`. `REFERENCE_ONLY` (GPL-3.0).
6. **Forge commander damage persists across a save/load generically.**
   `GameState` serialises `|IsCommander` and `|Damage:<n>` per card, restored via
   `handleMarkedDamage()` and `Player.addCommander(c)`. In-code gap: merged
   commanders unsupported. Forge issue **#10142** (commander damage reset after
   restart) is **open at a newer commit than our pin**.
7. **phase.rs is dual MIT OR Apache-2.0** (both licence files at the tree root)
   and ships a **production-compiled** `pub mod scenario` builder with
   `at_phase`, `with_commander`, seeded construction and a
   `build() -> GameRunner` handle, plus a **"Load Game State"** control in the
   shipped UI. Still `REFERENCE_ONLY` — a different engine.
8. **The one successful Lab-side reuse find from DR-CLOSURE-01 was this
   mechanism all along.** `PHASE1_REUSE_INVESTIGATION.md` recorded
   `Game.cheat(...)` as "the exact typed setup primitive v1 already uses"; the
   native tests were never routed.
9. **The model prior was right about the Lab's own seam and wrong about XMage's
   `Collections.shuffle`** — the internal belief that library ordering was
   correctly RNG-routed turned out to hold only for `anyOrder = false`.

## 4. Changes

Base `2e28866f…` → `cb017b74…`.

Modified:
- `engine-bridge/src/main/java/org/commanderlab/xmage/Main.java` — one added
  `midgame` lane dispatch. No existing branch's behaviour changed.

Added:
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageMidgameJsonlBridge.java`
  — Protocol-2 surface. Reuses `XmageDeckImporter`, `XmageFullGameSession`
  (restoration-aware constructor), `XmageFullGameDecisionController`,
  `XmageFullGamePlayer`, `XmageFullGameStateRedactor`,
  `XmageFullGameActionProjection`, `XmageNativeStateRestoration`,
  `XmageFullGameDecisionController.PROTOCOL_VERSION`. Commander colours come
  from `CardRepository`/`CardInfo`, not a Lab table. **No new Rules semantics.**
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageMidgameLaneTest.java`
  — 10 native tests.
- `src/commander_lab/qualification/current_boundary/midgame_lane.py` — the
  manifest consumer and row classifier.
- `scripts/run_midgame_capability_probe.py` — real-process probe.
- `tests/qualification/test_current_boundary_midgame_lane.py` — 14 unit tests.
- `qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json` — receipt.
- `docs/engine_capability_reuse_delta_20260929/{SOURCE_LOCK.md,
  ENGINE_CAPABILITY_REUSE_MATRIX.json, ENGINE_CAPABILITY_REUSE_MATRIX.md,
  HISTORICAL_ARCHAEOLOGY.md, EXTERNAL_PROVENANCE_LEDGER.md,
  IMPLEMENTATION_DECISION.md, HANDOFF.md}`.

Not touched, mechanically verified: `XmageNativeStateRestoration.java`,
`XmageFullGameSession.java`, `XmageFullGameJsonlBridge.java`, `JsonlBridge.java`,
`XmageGameManager.java`, `XmageFullGamePlayer.java`, `game_driver.py`,
`full107.py`, `bridge_launcher.py`, `engine/rules/full_game.py`,
`config/rules_engines.json`, and every file under
`qualification/final-current-boundary-20260927/`.

## 5. Tests / Evidence

| Evidence | Command | Result | Classification |
|---|---|---|---|
| Native lane suite | `mvn -o -Dtest=XmageMidgameLaneTest -DfailIfNoTests=false test` | 10 run, 0 failures, 0 errors | `DIRECTLY_VERIFIED` |
| Native suite regression | `mvn -o test` | 412 run, 0 failures, 0 errors, 1 skipped, BUILD SUCCESS | `DIRECTLY_VERIFIED` |
| Protocol-2 process probe (historical, pre-remediation) | `python scripts/run_midgame_capability_probe.py --out qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json` | 16 rows: 8 reachable, 3 state-accepted, 1 mismatch, 4 engine-rejected; `engine_commit=b1959698…` | `DIRECTLY_VERIFIED` |
| Python unit | `pytest tests/qualification/test_current_boundary_midgame_lane.py -q` | 14 passed | `DIRECTLY_VERIFIED` |
| Lint | `ruff check` + `ruff format --check` on all new files | `All checks passed` | `DIRECTLY_VERIFIED` |
| Types | `mypy --strict --python-version 3.12 …/midgame_lane.py` | `Success: no issues found` | `DIRECTLY_VERIFIED` |
| Capability manifest | `get_capabilities` on the live `midgame` process | `per_dimension_supported=true`, 11 supported + 10 unsupported dimensions enumerated, `global_supported=false` | `DIRECTLY_VERIFIED` |
| 4-player combat declaration | `WS05-MP-COMBAT-4` over the lane | two obligate 2/2 attacks declared against two different opponents by selecting engine-offered labels; construction proved against spec digest `8496df0e…`; principal-scoped counts with exactly one real identity | `DIRECTLY_VERIFIED` |
| Exact construction credit | `WS05-CMD-TAX-2` at precombat main | **zero** mismatches | `DIRECTLY_VERIFIED` |
| Fail-closed controls | 5 negative controls | `missing_requested_starting_state`, `seed_required`, `midgame_starting_state_rejected` (with `UNSUPPORTED_TAPE`/`UNSUPPORTED_CONTROL_DIVERGENCE`/`UNSUPPORTED_ZONE` codes), `unsupported_message`, `MIDGAME_NOT_CREATED` | `DIRECTLY_VERIFIED` |
| Structural call-site census | `grep -rn "new XmageFullGameSession"`, `grep -rn dimensionsPayload` | 1 production site (null restoration) vs ~40 JUnit sites; manifest's only caller is a test | `CODE_DERIVED` |
| Upstream/Forge/Manabrew/phase.rs symbol inventories | raw file fetches at the named commits | see `ENGINE_CAPABILITY_REUSE_MATRIX.md` §3 | `DIRECTLY_VERIFIED` (for the files read) |
| Official-rules validation | — | **not performed** | `UNKNOWN` |

## 6. PASS / FAIL / UNKNOWN

**PASS**
- Mid-game starting-state materialisation is production-reachable over
  Protocol 2.0.0 on the pinned engine. `DIRECTLY_VERIFIED`.
- The per-dimension manifest is reachable and truthful. `DIRECTLY_VERIFIED`.
- Four-player Commander combat declaration is reachable with real cards.
  `DIRECTLY_VERIFIED`.
- Unsupported dimensions stay rejected with the engine's own codes.
  `DIRECTLY_VERIFIED`.
- Principal-scoped observation holds on the new lane (counts only; exactly one
  real identity per observation). `DIRECTLY_VERIFIED`.
- No Rules semantic was added and no owned file was edited.
  `DIRECTLY_VERIFIED`.
- No native regression. `DIRECTLY_VERIFIED`.

**FAIL**
- None in the delivered scope.

**UNKNOWN**
- `EXTERNALLY_RULE_VALIDATED` for any row. No row was adjudicated against the
  current official Comprehensive Rules or Oracle text in this workstream.
- Whether an XMage deserialised `Game` can be *resumed* rather than merely
  viewed (CAP-11 / `GameReplay`).
- `Baldugar/mtg-forge-ts`' programmatic API + save/load + deterministic replay
  claims — no source read; `HYPOTHESIS`.
- `prepareControllableProxy` cross-seat contamination when both it and
  `setResponse*` are mounted on one production `Player` — flagged, untested.
- Whether the new lane can re-run the whole 107-row denominator within its
  arrival bound. Rows needing a causal-stack or control-change route
  (`WS05-MP-PRIO-3`, `WS05-MP-PRIO-5`, `WS05-CMD-ZONE-*`, `MICRO_ZONE_CHANGES`,
  `WS05-CMD-DMG-CONTROL`, the 6 `WS05-MP-ELIM-*` rows, `WS05-MP-TURN-3`) are
  **not** reachable through placement alone. `CODE_DERIVED`, not yet measured
  end to end.

**Explicitly NOT claimed**
- The current boundary still reads `BLOCKED 44 / UNKNOWN 59`. Nothing was
  promoted.
- `SAME_SEMANTICS` is still 0 of 107.
- Provider comparison remains inadmissible while PB-09 is open.

## 7. Remaining Blockers

Exact mechanisms, not prose.

1. **Rows whose frozen state needs a causal route, not a placement.**
   Mechanism: `XmageCausalStackReconstruction` and
   `XmageControlDivergenceReconstruction` exist and are JUnit-proven but have no
   production route. Rows: `WS05-MP-PRIO-3`, `WS05-MP-PRIO-5`, `WS05-MP-PRIO-3`
   companions, `WS05-CMD-ZONE-{GY,EXILE,HAND,LIB}-{YES,NO}` (8),
   `MICRO_ZONE_CHANGES`, `WS05-CMD-DMG-CONTROL`, `WS05-MP-ELIM-*` (6),
   `WS05-MP-TURN-3`. Owner constraint: wiring needs
   `XmageFullGameSession.java` (PR #284) or a new entry mode in the new lane.
   **Owner: free only via the new lane; the session file is #284's.**
2. **Life-0 elimination cannot be requested.** The engine re-derives starting
   life to 40 during game start. Rows: `WS05-MP-ELIM-PRIO-3`,
   `WS05-MP-ELIM-5`, `WS05-MP-ELIM-OWNED-3`. Correct route is
   `XmageCausalEliminationReconstruction` (real damage → SBA), not placement.
3. **Rules-RNG split and per-game isolation (CAP-08).** XMage upstream change
   required. Gates `PB-08`, `RNG_RULES_TAPE`, `REPLAY_*` and the new lane's own
   `rules_seed` claim. Dispatch packet in
   `EXTERNAL_PROVENANCE_LEDGER.md` §8.
4. **Replay twin (CAP-11).** No engine replay export on the pinned lanes.
   Gated on (3). Gated on ownership (#289 owns `replay_obligations.py`).
5. **Per-scenario hidden-information channels (CAP-10, PB-06).** Owned by #289
   (`hidden_obligations.py`). The new lane already returns counts-only per seat
   with exactly one real identity, which is the shape those channels need.
6. **PB-09.** Open, Coordinator-owned, PR #299 live. Not touched.
7. **Negative-shortcut rows (7 `UNKNOWN`).** No per-shortcut negative harness
   exists on this lane. Owned by #289 (`shortcut_campaign.py`).
8. **Bridge boundary: the new lane is not yet wired into the current-boundary
   runner.** `game_driver.py`/`full107.py`/`bridge_launcher.py` are owned by
   #300/#289/#299. Not attempted.

## 8. Outputs

- Branch `research/csn-engine-capability-delta-20260929`, HEAD
  `cb017b74cfa1af9004036bd48e2c518d3194a56b`, TREE
  `fbf9069cd14bf5b8506328073009e140def58386`, pushed.
- **PR #304** — https://github.com/moeendres-png/commander-playtest-lab/pull/304
  (open, not draft, **not merged**; merging is left to the Coordinator because
  the change is adjacent to four live provider workstreams).
- `docs/engine_capability_reuse_delta_20260929/` — `SOURCE_LOCK.md`,
  `ENGINE_CAPABILITY_REUSE_MATRIX.json`, `ENGINE_CAPABILITY_REUSE_MATRIX.md`,
  `HISTORICAL_ARCHAEOLOGY.md`, `EXTERNAL_PROVENANCE_LEDGER.md`,
  `IMPLEMENTATION_DECISION.md`, `HANDOFF.md`.
- `qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json`.
- Build/run recipe: `mvn -o -DskipTests package` in `engine-bridge/`, then
  `mvn -o dependency:build-classpath -Dmdep.outputFile=target/cp-wsr22.txt`, then
  `python scripts/run_midgame_capability_probe.py --out <receipt.json>`.
- Runtime receipts: surefire reports under `engine-bridge/target/surefire-reports/`,
  native suite log (412/0/0/1), probe JSON.

## 9. Dependencies Unblocked

- **59 of 107 rows** (44 `BLOCKED` + 15 `UNKNOWN`) now have a production-reachable
  route to their mechanism, pending only the boundary runner rerun.
- A truthful per-dimension capability surface exists for the first time, so
  starting-state classification can be per-dimension instead of per-boolean.
- The 12-row accept/reject census gives the boundary owners a measured partition
  to plan requalification against, including which rows need a causal route.
- A principal-scoped, counts-only, exactly-one-real-identity observation surface
  exists on a production lane — the shape PB-06's per-scenario channels need.
- A real-process probe and receipt format for the mid-game lane, reusable by any
  follow-up dispatch.
- The engine-side RNG defect is now written down with a concrete packet, so it
  can be filed upstream independently of the Lab's own schedule.

## 10. Exact Next Action

**Wire `XmageCausalStackReconstruction` and
`XmageCausalEliminationReconstruction` onto the existing `midgame` lane as a
second entry mode, as a new file in the same package, touching no file owned by
an open PR — so that `WS05-MP-PRIO-3`, the eight `WS05-CMD-ZONE-*` rows,
`MICRO_ZONE_CHANGES` and the six `WS05-MP-ELIM-*` rows stop being rejected at
`create_midgame_game` with `UNSUPPORTED_ZONE` / `UNSUPPORTED_CONTROL_DIVERGENCE`
and instead reach their own decisions through external control, then extend
`run_midgame_capability_probe.py` to report the new partition.**

Owner: this workstream's successor. It is the same mechanism cluster, is on a
free surface, and is the single largest remaining unlock before the boundary
runner can be rerun by its owners.

## Review remediation (2026-09-29)

The authoritative record of the six closed review findings and the WS17
artifact/hash repair is `docs/engine_capability_reuse_delta_20260929/REVIEW_REMEDIATION_20260929.md`.
Probe counts in this document that predate that remediation are marked historical;
the current receipt is the 29-row receipt at the remediated head and every digest in
it was regenerated because the arrival observation and the digest scope changed.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
