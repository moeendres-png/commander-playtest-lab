# XMage multiplayer-candidate repin: impact adjudication

- **Change:** the live XMage pin moves from `b19596980f2734496ea1896504253e1bdd2756dd` to `f79e4168902e65063034b21be6f4585397fd43b3` (Mage PR #24).
- **Machine-readable lock:** `qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json`.
- **Not:** Production Provider selection, Architecture Freeze or a denominator change.

## Modified engine paths (the complete production delta)

| Finding | Engine path | Behaviour change |
|---|---|---|
| F-18 | `GameImpl.checkStateBasedActions`, commander graveyard/exile SBA | Owners are asked in APNAP order, and moves are applied after every owner has chosen. The prompts are unchanged. |
| F-19 | `RhysticStudy`, `MysticRemora` draw effects | The payer is asked first (only if able); the controller's "may draw" comes only if unpaid. |
| F-20 | `GameImpl.leave`; `Initiative` triggers | When its holder leaves, the initiative passes to the active player, or to the next player in turn order (CR 726.4). The initiative's triggers are controlled by the current holder (726.2). |
| F-21 | new `Game.getPlayerIdsInApnapOrder` / `getOpponentsInApnapOrder`; `SacrificeAllEffect` (incl. `SacrificeOpponentsEffect`); Grave Pact; six tempting-offer cards | These simultaneous choices go in APNAP order, departed players are skipped, and range of influence is kept. **`Game.getOpponents` is unchanged.** |

No other production file changed. Full `Mage.Tests` on the combined source passed: 7001 run, 0 failures, 0 errors, 125 skipped.

## Evidence matrix

| Evidence | Crosses a modified path? | Disposition |
|---|---|---|
| Native Mage suites at the prior pin (RG-02, RG-06A, RG-07, RG-08 and all other `Mage.Tests`) | some (the SBA loop and effects are exercised broadly) | **SURVIVES_IMPACT_ADJUDICATION**: re-executed on the candidate, 7001 / 0 failures. |
| Lab engine-bridge suite (B3 through B4-D, full-game lane, restoration, hidden information, multiplayer probes #311–#331, staple decisions) | yes (commander-zone, Rhystic, initiative, sacrifice, tempting-offer probes) | **SURVIVES**: re-executed on the candidate via an isolated Maven repo, 538 run / 0 failures / 1 skipped. Two companion tests and `XmageStapleDecisionTest`'s Rhystic flow encoded pre-fix orders and were corrected to the ruled order. |
| Previously disabled F-18/F-19/F-20/F-21 Lab regressions (46 tests incl. fingerprint) | yes | **Re-enabled**: red on the prior-pin artifacts, green on the candidate. |
| Lab Python suite | no engine execution | **SURVIVES**: 2187 passed, 8 skipped, 0 failed. Main has 3 fewer skips; those are the superseded current-pin checks. |
| WSR22 FULL107 current-boundary XMage evidence (`qualification/final-current-boundary-20260927/*`, `source_lock.py`) | FULL107 rows involving commander deaths, "each player" sacrifices, tempting offers or initiative departures may now resolve differently | **HISTORICAL_ONLY** for `b19596980f27`. It is not credited to the new pin and not rewritten. Any current-boundary credit on the new pin **REQUIRES_REQUALIFICATION** in a successor current-boundary run (separate workstream; denominator unchanged). |
| AF00/AF01-style engine identity | yes (the engine commit changes) | Re-established for the new pin by `XmageProvider.ENGINE_COMMIT`, `JsonlBridgeTest` and the runtime fingerprint (`XmageCandidateEngineFingerprintTest`). Sealed AF01 artifacts stay historical (`test_wsr22_current_boundary` still accepts only their recorded commits). |
| Semantic replay tapes (WS218, sealed to `db134b97`) | — | **HISTORICAL_ONLY** (already historical before this repin). |
| Replay determinism on the new pin | choice/event order changes only in the four modified families | The current bridge replay and determinism tests pass on the candidate. Any recorded tape containing a modified family must be re-recorded: **REQUIRES_REQUALIFICATION** if one is ever credited. None is currently credited. |
| Hidden information | the ask order changes, but no new information is exposed | **SURVIVES**: the hidden-information suites (full-game and multiplayer discards) re-executed green. |
| 2026-09-25 repin guard (`test_residual_xmage_repin_20260925.py`) | — | **HISTORICAL_ONLY**: current-pin checks skip as superseded; historical checks remain active. |
| CI workflows (external-engine-integration, conformance, real-4p-smoke, meta-qualification) | build the pinned engine from source | Run on this PR at the new pin: the **exact-head gate**. |

**INVALIDATED:** none. No evidence is rewritten, and no historical claim changes meaning.

**UNKNOWN:**
- current-boundary FULL107 standing at the new pin, until the successor current-boundary run;
- PR #316's new `pb03-runtime-qualification.yml` hard-codes the prior pin. If it merges after this repin it must adopt the live pin, which is its owner's call (noted on #316).
