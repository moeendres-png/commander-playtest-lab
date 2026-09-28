# XMage generic-lane Rules RNG — handoff

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
This workstream changes one candidate's provider bridge. It ranks no candidate.

## Source lock

| Item | Identity |
|---|---|
| Lab audit base | `origin/main` `afe09c61d4ad90f89c28ff75ac7439a20b89cfdd`, tree `0d5b3f0d9020cc99131dd92a41a9615c61bbac8a` |
| Branch | `claude/optimistic-bohr-6asye6` |
| XMage engine pin (unchanged) | `moeendres-png/mage@b19596980f2734496ea1896504253e1bdd2756dd`, xmage `1.4.61` |
| Build toolchain (local) | OpenJDK 21.0.10, Maven 3.9.11; CI uses Temurin 17 |

## Why this work

The pre-Freeze provider readiness packet (`docs/pre_freeze_completion_20260927/PROVIDER_READINESS_PACKET_20260928.md` §6.3, §7 PB-08) records XMage Rules RNG as **fully uncontrolled** on the generic lane: `seed_supported: false`, no seed sent, binding `UNCONTROLLED_ENGINE_RNG`. Its remediation line names "a seed-capable generic lane or an engine-level binding". The engine-level binding already existed (`Game.setRulesSeed` / `setRequireExplicitSeed`, WS54) and was already used by the full-game lane (WS213); only the generic lane never bound it.

At the audit base, the current-boundary pipeline and XMage PB-03 test surfaces had active writers (PRs #284, #285, #289, #292), and Forge Aftermath had its own (#287, Forge #6). No open branch edited the generic-lane bridge sources, so this surface could be owned without racing anyone.

## Finding: the generic lane never shuffled a library

The first discriminating test failed. On the generic lane, every library stayed in decklist order after `start_game`, every opening hand was the first seven cards of the list, and the per-game Rules stream reported `rules_random_calls == 0`.

Root cause: `XmageBridgePlayer.shuffleLibrary` was overridden as a no-op ("B3/B4 compatibility bridge testing is not seeded gameplay evidence"). That is a silent skip of Rules randomness:

- CR 103.3 (opening shuffle), mulligan shuffles and every "search … then shuffle" effect never happened;
- anyone who knows a decklist knew every library order, which is a hidden-information leak on the lane the current-boundary pipeline uses;
- the engine's `SHUFFLE_LIBRARY` replacement check and `LIBRARY_SHUFFLED` event were suppressed, so shuffle replacements and triggers could never fire.

`XmageBridgePlayerFailClosedTest` asserted the no-op as intended "lifecycle" behavior.

**Impact on existing evidence (for adjudication, not adjudicated here):** any generic-lane observation that depended on library order, opening hands or shuffle events was produced under this defect. That includes the committed current-boundary XMage column and the B3/B4 regression artifacts. Most of them do not depend on hand contents: B4-C casts the commander from the command zone, and the full bridge suite passed after the fix except for the test that pinned the no-op.

## Changes

| File | Change | Reuse class |
|---|---|---|
| `engine-bridge/.../XmageBridgePlayer.java` | Deleted the `shuffleLibrary` no-op. Shuffling now uses `PlayerImpl.shuffleLibrary`, which applies the replacement check, draws from the Rules RNG and fires the event | `ENGINE_NATIVE_REUSE` |
| `engine-bridge/.../XmageRulesSeedBinding.java` (new) | The WS213 binding and its proof payload, moved out of `XmageFullGameSession`. `bind` checks the engine readback and fails closed | `EXTRACT_AND_GENERALIZE` |
| `engine-bridge/.../XmageFullGameSession.java` | Uses the shared helper. Payload fields are unchanged; binding now also verifies the readback | — |
| `engine-bridge/.../XmageGameManager.java` | Optional `rulesSeed` is bound after construction and before start. Create and start results carry the binding proof. Adds `seedControlled(handle)`. Event log records `seed_controlled` only, never the value | `WRAP` |
| `engine-bridge/.../JsonlBridge.java` | Accepts `seed`, `rules_seed`, `options.seed`, `options.rules_seed`. Each must be an integral JSON number in int64 range and all must agree, else `invalid_seed`. Create and start responses acknowledge `rules_seed` from engine readback. `get_game_state` reports `seed_controlled` only, and `state.seed` stays `null` | — |
| `engine-bridge/.../XmageProvider.java` | `seed_supported: true` with a truthful note | — |
| `scripts/run_external_b3_regression.py` | `seed_supported` removed from B3's forbidden-claims set, because it is orthogonal to B3's lifecycle scope. B3 now fails if any of its unseeded runs reports seed control | — |
| `scripts/run_external_b4f_capability_closeout.py` | `seed_supported` removed from the expected-false set. The descriptor keeps `seed_control: NOT_PROVEN`, because B4-F's own evidence is unseeded | — |
| Tests | New `XmageGenericLaneRulesSeedTest`. `JsonlBridgeTest` now expects `seed_supported: true`. The no-op assertion in `XmageBridgePlayerFailClosedTest` is removed | — |

Unseeded generic games are still accepted. They run on the engine's non-credited default seed, report `seed_controlled: false` and carry no `rules_seed` field, so the Lab classifier (`classify_seed_binding`) can never mark them as controlled.

## Tests and evidence

| Evidence | Result | Class |
|---|---|---|
| `XmageGenericLaneRulesSeedTest` before the shuffle fix | 3/6 FAIL: libraries in decklist order, `rules_random_calls == 0`, different seeds gave identical openings | `DIRECTLY_VERIFIED` (defect) |
| `XmageGenericLaneRulesSeedTest` after | 7/7 PASS. Same seed reproduces every library, hand and starting seat for 2, 3, 4 and 5 players. A different seed changes the shuffle. Start consumes the Rules stream. Unseeded games are never controlled. The bridge acks from readback. The seed never appears in any of four observers' state. Malformed or conflicting seeds give `invalid_seed`. The bridge player declares no `shuffleLibrary` | `DIRECTLY_VERIFIED` |
| Mutation: binding disabled | same-seed test FAILS (engine readback diverges) | `DIRECTLY_VERIFIED` |
| `mvn verify` (engine-bridge, 335 tests) | 1 error, the test that pinned the no-op; fixed. Affected classes rerun 35/35 | `DIRECTLY_VERIFIED` |
| B3, B4-A, B4-B, B4-C, B4-D process regressions (real bridge jar) | PASS | `DIRECTLY_VERIFIED` |
| Phase-6 differential; B4-F replay, illegal-action, capability closeout, provider-pin validation | PASS (Phase-6: 2 passed, 1 skipped) | `DIRECTLY_VERIFIED` |
| Python suites touching seed and capability surfaces (10 files + CI provider-truth set) | 186 passed | `DIRECTLY_VERIFIED` |
| Full Python suite, attributed against an `origin/main` baseline worktree | see `PYTEST_ATTRIBUTION.md` (this directory) | `DIRECTLY_VERIFIED` |

Engine-side audit at the pin (`CODE_DERIVED`): core Rules randomness in `Mage/` routes through `game.getRulesRandom()`. `Library.shuffle()` without an argument, which uses the global `RandomUtil`, is deprecated and has no production caller. The remaining `RandomUtil` calls in `Mage.Sets` are booster generation, plus `MagesContest`, which is an AI bid heuristic rather than a Rules outcome.

## PASS / FAIL / UNKNOWN

- Generic-lane explicit seed bound to and acknowledged from the native Rules RNG, 2–5P: **PASS** (bridge runtime tests).
- Generic-lane library shuffling is Rules-owned again: **PASS**.
- Current-boundary XMage AF09 / PB-08 on a head containing this change: **NOT_RUN** (owned by the current-boundary pipeline line).
- Clean-process replay twin (`REPLAY_CLEAN_PROCESS`): **UNKNOWN**, unchanged.
- Card-level random effects under a bound seed: **UNKNOWN** (not individually exercised).

## Remaining blockers and out-of-scope findings

- `XmageBridgePlayer.chooseMulligan` returns keep on the no-controller path. This is a default decision the comment acknowledges; on the externally controlled path it is still not published as a decision (`mulligan_supported: false`). It belongs to AF04 and was left alone.
- Committed receipts, `SOURCE_LOCK.json` contract blobs and the WS80 and WS232 inventories reference the changed bridge files. They are provenance for their own heads and were not rewritten.

## Authority gates

None raised. Whether historical generic-lane evidence survives the shuffle fix is ordinary impact adjudication for the evidence owner. It changes no policy.

## Exact next action

On a head containing this change, re-run the XMage current-boundary column (`scripts/run_current_boundary_qualification.py`) as the current-boundary owner. Expected result: AF01 Rules-RNG reads `seed_supported: true`, and `create_commander_game` acknowledges the engine-readback `rules_seed`. XMage `rules_rng_binding` should then move from `UNCONTROLLED_ENGINE_RNG` to controlled, which unblocks building the XMage clean-process replay twin on the generic lane.
