# XMage multiplayer-candidate repin v2: impact adjudication

- **Change:** the live XMage pin moves from `f79e4168902e65063034b21be6f4585397fd43b3` to `9375f35ac7c9a540ebcb8b262b8645b8c6b1b326`, the same candidate branch (moeendres-png/mage#24).
- **Machine-readable lock:** `qualification/xmage-mp-candidate-repin-v2-20260930/SUCCESSOR_SOURCE_LOCK.json`.
- **Not:** Production Provider selection, Architecture Freeze or a denominator change.
- **Supersedes the draft Lab PR #360** (F-22/F-23 repin to `fcfde9da`). The `9375f35a` head contains `fcfde9da` unchanged, so #360's Lab test enablements are ported here with attribution. #360 itself is not modified.

## Modified engine paths (the complete production delta over `f79e4168`)

| Finding | Engine path | Behaviour change |
|---|---|---|
| F-22 (mage#26) | `GameImpl.checkStateBasedActions`, battle protector selection | A battle protector who left the game is unsuitable. XMage's native protector choice is re-run and considers only current opponents. |
| F-23 (mage#26) | new `Game.getOpponentsInGame(UUID)`; current-state consumers (counts, comparisons, conditions, random opponent), `VoteHandler`, `MyriadAbility` | Departed players no longer take part in current-state gameplay decisions and values. **`Game.getOpponents` is unchanged** (turn/range snapshot semantics are kept). |
| F-28 (mage#27) | `Combat.checkBlockRequirementsAfter` (four `mustBlockAny`/`mustBlockAllAttackers` sites) | "Blocks if able" requirements count only attackers attacking the blocker's controller (CR 802.4a). Before, block declaration could livelock. |
| F-29 (mage#28) | `Combat.selectBlockers`, `resumeSelectBlockers` | Defending players declare blockers in APNAP order (CR 802.4). Before, they used hash-set order, which differed between identical games. |
| F-34 (donor `2786665809`) | `GameImpl.leave` | A leaving player's control of other players' turns ends (CR 800.4a). The controlled player takes its own decisions back. |

- Two-player games are unaffected by F-28 and F-29: the only defending player is always the blocker's controller.
- Full `Mage.Tests` on `9375f35a`: **7020 run, 0 failures, 0 errors, 125 skipped**. At the prior pin: 7001 run, 125 skipped. The new native tests account for the difference.

## Evidence matrix

| Evidence | Crosses a modified path? | Disposition |
|---|---|---|
| Native Mage suites | some (combat, SBA, leave, opponent queries) | **SURVIVES_IMPACT_ADJUDICATION**: re-executed on `9375f35a`, 7020 / 0 failures. |
| Lab engine-bridge suite (all lanes, multiplayer probes, whole-game replay twins) | yes (combat blocks, departures, votes, myriad) | **SURVIVES**: re-executed against `9375f35a` via an isolated Maven repo. The result is in the successor lock. |
| Previously disabled F-22, F-23, F-28, F-29 Lab regressions | yes | **Re-enabled**: `XmageMultiplayerBattleTest` (leave case), `XmageMultiplayerVoteTest` (left player), `XmageMultiplayerForcedBlockTest`, `XmageMultiplayerBlockOrderTest`. All are red or hanging on `f79e4168` and green on `9375f35a`. |
| F-34 Lab test `XmageMultiplayerControllerLeavesTest` | yes | Branches on engine state by design. On `9375f35a` the frame is re-addressed to the controlled player. |
| Full-game-lane evidence from multi-defender combats on `f79e4168` or earlier | block declaration order (F-29) | **HISTORICAL_ONLY** for replay: the block order was hash-ordered. Outcomes stay rules-valid, but a tape would not replay deterministically. Nothing of this kind is currently credited. |
| WSR22 FULL107 current-boundary evidence (`b19596980f27`) | — | **HISTORICAL_ONLY**, unchanged. Credit on the new pin **REQUIRES_REQUALIFICATION** in a successor current-boundary run. |
| v1 repin guard (`test_xmage_mp_candidate_repin_20260929.py`) and the 2026-09-25 guard | — | **HISTORICAL_ONLY**: their current-pin checks skip as superseded, and their historical checks stay active. |
| AF00/AF01-style engine identity | yes (the engine commit changes) | Re-established by `XmageProvider.ENGINE_COMMIT`, `JsonlBridgeTest` and the runtime fingerprints (F-21 primitives, F-23 `getOpponentsInGame`, F-28/F-29 `Combat` methods). |
| CI workflows | build the pinned engine (cache keyed by the new commit) | Run on this PR at the new pin: the **exact-head gate**. |

**INVALIDATED:** none.

**UNKNOWN:** current-boundary FULL107 standing at the new pin, until a successor current-boundary run.
