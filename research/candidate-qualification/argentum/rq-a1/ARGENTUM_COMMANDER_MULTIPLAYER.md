# RQ-A1 — Argentum Commander / Multiplayer

Verdict first: **Free-for-All exists AND Commander exists in-engine; they are not the same claim, and each is evidenced separately.** Commander = single-commander only; partner/background/companion absent. Multiplayer = 2–4 players runtime-evidenced; 5–6 players code-plausible but test-absent.

## 1. Commander — verdict: IN-ENGINE SUPPORTED (single commander)

Not inferred from FFA. Not validator-only. Each layer cited:

| Layer | Evidence (path relative to `/tmp/rq-argentum-src`) |
|---|---|
| Format definition | `mtg-sdk/.../sdk/core/Format.kt:82` — `data class Commander(commanderDamageThreshold=21, deckSize=100, startingLife=40, startingHandSize=7, …)`; `usesCommanders = threshold != null` (`:29`); KDoc: "Commander, at any table size… the same instance runs a 1v1 game and a six-player Free-for-All" (config claim, not a test) |
| Game setup | `rules-engine/.../core/GameInitializer.kt:37-41,169-181,302-376` — `PlayerConfig.commanderCardName` required for `Format.Commander`; "Phase 1 supports a single commander; partner / Background pairings are Phase 4 territory"; instantiates with `CommanderComponent(ownerId)` → `Zone.COMMAND`; `CommanderRegistryComponent` list-shaped for future partners |
| Commander marker | `rules-engine/.../state/components/identity/CommanderComponent.kt` — `CommanderComponent(ownerId, castsFromCommandZone=0)`; KDoc wires setup, cast permission, tax (CR 903.8), 903.9a SBA, damage tracking (token copies excluded per 903.10a) |
| Cast permission | `handlers/actions/spell/CastSpellHandler.kt:253-254,696,958,1119,2496-2507,4375` (`hasCommanderCastPermission`, `castingFromCommandZone`); `handlers/actions/spell/CastZoneResolver.kt`; `legalactions/enumerators/CommandZoneAbilityEnumerator.kt` (incl. Momir/Vanguard path) |
| Commander tax | `mechanics/mana/CostCalculator.kt:152-153,173-199` — `calculateCommanderTax()` = `2 × castsFromCommandZone` generic when cast from `Zone.COMMAND` with matching component |
| 903.9a replacement/choice | `mechanics/sba/permanent/CommanderZoneChoiceCheck.kt` (yes/no `CommanderZoneChoiceContinuation` + `CommanderZoneChoiceAskedComponent` dedupe; skipped under `alwaysDivertToCommand`); `handlers/effects/ZoneMovementUtils.kt:758-777` (synchronous divert incl. token-copy exclusion); `ZoneTransitionService.kt` strips the asked-marker on next zone change |
| Commander damage + loss | `mechanics/combat/CombatDamageManager.kt:1787-1800` (`accumulateCommanderDamage`, skips tokens, requires `CommanderComponent`); `GameState.kt:345-347,1308-1332` (`commanderDamage`, `recordCommanderDamage`); `mechanics/sba/player/CommanderDamageLossCheck.kt` (CR 704.5c, per-commander threshold from format) |
| Deck-construction validation (separate surface) | `game-server/.../deck/DeckValidator.kt:21-29,67-93,212-287,315-330,346-448` — 100-card singleton, `CommanderEligibility.isLegalCommander`, color-identity containment; "Partner / Background pairs are not yet supported" |
| Engine tests | `core/CommanderSetupTest`; `mana/CommanderTaxTest`; `handlers/effects/CommanderZoneRedirectTest`, `CommanderZoneMarkerStripTest`; `mechanics/sba/CommanderDamageLossCheckTest`, `CommanderZoneChoiceCheckTest`; `event/CommandZoneTriggerDetectionTest`; `multiplayer/CommanderPodTest` (4-seat: per-seat zones, per-pair damage, 21-damage single-seat elimination with pod continuing, 3-commanders-in-graveyard choice routing); `scenarios/LiminalHoldCommanderTest` |
| Server tests | `lobby/CommanderPodLobbyTest`, `FreeForAllLobbyTest`, `QuickGameLobbyCommanderAiTest`, `deck/GeneratedCommanderDeckLegalityTest`, `deck/DeckValidatorTest` |

Explicit negatives (case-insensitive search over `rules-engine/src/main`): `partner` only soulbond/combat-fan-out/Phase-4 comments; `background` only Phase-4 comments; `companion` only Kotlin `companion object`; in-engine color-identity only land-mana fallback + token color-indicator reads (no play-time deck gate — validator-only by design).

Commander-adjacent products exist as data: `2024/.../blc/BloomburrowCommanderSet.kt`, `2026/.../trc/StarTrekCommanderSet.kt` (set definitions, not behavior proof).

## 2. Multiplayer — verdict: 2–4 EVIDENCED, 5–6 UNEVIDENCED

- No max-player check: `GameInitializer.kt:155` requires `size >= 2`, no upper bound. `turnOrder`/`teams`/`apnapOrder` are unbounded structures.
- `range-of-influence`: NOT_FOUND (only false positives).
- Turn order: `GameState.turnOrder` + team-aware shuffling/starting-team logic; `teams/teamOf/teammatesOf/sharedTurnTeam/isActiveTurnFor/apnapOrder/activePlayers`.
- APNAP with >2: evidenced — `TriggerMatcher.sortByApnapOrder`, `CombatDefenders.defendingPlayersInApnapOrder`, `DeclareBlockersHandler` multi-defender sequencing, `ForEachExecutor`/`AnyPlayerMayPayExecutor` APNAP fans.
- Attack modes: `AttackMode.MULTIPLE` (CR 802, default) vs `LEFT`/`RIGHT` (CR 803) (`mtg-sdk/.../sdk/core/AttackMode.kt` + `GameState.attackMode`); `AttackModeTest` covers all three.
- Simultaneous choices/voting: NOT_FOUND as true simultaneity; sequential-APNAP stand-ins only (`SecretBidContinuation`, `ChoosePileExecutor`, `AnyPlayerMayPayExecutor`, `ForEachExecutor`).
- Elimination: evidenced — `PlayerLeavesGameProcessor` (CR 800.4a–c/e–h) with two documented simplifications (remaining players' LTB triggers off mass removals; static-ability exile of leaver-controlled objects); `GameEndCheck` (810.8a team win vs last-standing).

| Players | Verdict | Cite |
|---|---|---|
| 2 | Evidenced | `LeaveTheGameTest` (concede→`winnerId`); `OpponentDeciderChoiceTest(playerCount=2)`; `MultiplayerMulliganTest initGame(2)`; `AttackModeTest initGame(2)` |
| 3 | Evidenced | `DefendingPlayerAttackRestrictionTest (1..3)`; `OpponentDeciderChoiceTest(playerCount=3)`; `ReplacementTeamAwarenessTest (1..3)` |
| 4 | Evidenced (primary) | `MultiplayerSmokeTest (1..4)`; `MultiDefenderCombatTest initGame(4)`; `CommanderPodTest List(4)`; `LeaveTheGameTest initGame(4)`; `AttackModeTest initGame(4)`; all `TwoHeadedGiant*Test (1..4)`; `TeamVsTeamTest`; `AgateBladeAssassinMultiplayerTest (1..4)` |
| 5 | NOT_FOUND in tests; code-plausible only | No 5-seat test; unbounded player-list code + "any table size" comment do not constitute evidence |
| 6 | NOT_FOUND in tests; config-comment only | "Six-player Free-for-All" is a `Format.Commander` KDoc claim; zero 6-seat runtime evidence |

Team variants evidenced: Two-Headed Giant (shared life+turns, win/lose as team — 7 test files: `TwoHeadedGiant{Setup,SharedLife,SharedTurn,SecondHeadTurn,Combat,TeamPriority,TeamLoss}Test`) and Team-vs-Team (individual turns/life — `TeamVsTeamTest`).

## 3. Commander × multiplayer matrix (runtime evidence)

|  | 2P | 3P | 4P | 5P | 6P |
|---|---|---|---|---|---|
| FFA (non-Commander) | test-evidenced | test-evidenced | test-evidenced | absent | absent |
| Commander pod | config + 1v1-capable code (`Format.Commander` "runs a 1v1 game") | absent | test-evidenced (`CommanderPodTest`) | absent | absent |
| Two-Headed Giant | n/a (4 seats / 2 teams evidenced) | — | evidenced | — | — |

No 2–5P technical conformance evidence exists yet in the qualification sense (presence of tests ≠ conformance); 4P is the best-evidenced count. A 4P result must not be read as establishing any other count.
