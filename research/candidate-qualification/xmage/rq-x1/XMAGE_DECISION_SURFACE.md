# RQ-X1 — Decision-Surface Matrix (CODE_DERIVED, key cites DIRECTLY_VERIFIED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`.

Allowed labels: `NATIVE_EXPLICIT` | `NATIVE_BUT_GUI_COUPLED` |
`NATIVE_BUT_AI_COUPLED` | `INDEX_BASED` | `OBJECT_ID_BASED` |
`SEMANTIC_ID_AVAILABLE` | `ADAPTER_REQUIRED` | `UNKNOWN`.
Multiple labels only with evidence. All findings CODE_DERIVED unless marked
DIRECTLY_VERIFIED. "Native" here means engine-internal capability — NOT
project-provider support (see §3 on historical statements).

Representation key (from `XMAGE_SELECTION_NATIVE_EXECUTION.md`):
targets/abilities/modes/players/objects travel as **UUID sets/maps**;
`Choice` strings are **string-keyed within engine sets**; amounts are
**min/max-bounded integers**; ordering is **sequential choice from candidate
set**; votes/piles booleans/indices are bounded by engine-built structures.

## Matrix

| # | Decision | Classification | Evidence (file:line @ pin) |
|---|---|---|---|
| 1 | Starting player | NATIVE_EXPLICIT, OBJECT_ID_BASED | `GameImpl.java:1321-1366`: `TargetPlayer("starting player")` + `choosingPlayer.choose(Outcome.Benefit, targetPlayer)`; fallback first `canRespond` player; random only for choosing-player fallback (`:1565-1569`) |
| 2 | Mulligan | NATIVE_EXPLICIT | `Mulligan.java:25-76` APNAP `chooseMulligan()` loop; `LondonMulligan.java:49-117`; `HumanPlayer.java:386-419` boolean dialog; `GameCommanderImpl.java:172-224` hooks (currently `super`) |
| 3 | Priority (act vs pass) | NATIVE_EXPLICIT, OBJECT_ID_BASED | `GameImpl.playPriority:1723-1855`; playable set `PlayerImpl:1875,4290,4506`; `HumanPlayer.priority:1207-1461` echoes ability UUID or passes |
| 4 | Cast | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.chooseAbilityForCast` (`Player.java:452`, DIRECTLY_VERIFIED); `HumanPlayer:2411-2448` UUID-map pick; `Player.cast` (`Player.java:436`) |
| 5 | Activate | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.activateAbility` (`Player.java:521`); `HumanPlayer:2326-2375` UUID-map pick; priority clickable set |
| 6 | Pass (incl. F4–F11 skips) | NATIVE_BUT_GUI_COUPLED | Pass state is engine (`PlayerImpl:2650-2663`); SKIP EVALUATION reads `UserData`/`UserSkipPrioritySteps` inside `HumanPlayer.priority:1208-1368` — GUI preference inside the decision path |
| 7 | Mana-source selection | NATIVE_EXPLICIT, OBJECT_ID_BASED | `HumanPlayer.playMana:1627-1675` (`firePlayManaEvent`, UUID/`special`/pool echo); `getUseableManaAbilities`; AI `testPay` sorted producers (`ComputerPlayer:407-452`) |
| 8 | Mana payment | NATIVE_EXPLICIT, OBJECT_ID_BASED | unpaid `ManaCost` + `cost.testPay(netMana)` gate; conditional mana + as-though checks before `activateAbility` |
| 9 | Alternate costs | NATIVE_EXPLICIT | `ApprovingObject` + `MageObjectReference` (`ApprovingObject.java:14-20`); `getCastableSpellAbilities` enumerates cost variants; `cast(ability,game,noMana,approvingObject)` (`Player.java:436`) |
| 10 | Additional costs | NATIVE_EXPLICIT | cost pipeline in `PlayerImpl` cast/activate paths; engine-paid, engine-validated (no client contribution) |
| 11 | X (announceX) | NATIVE_EXPLICIT | `Player.announceX(min,max,…)` (`Player.java:761`, DIRECTLY_VERIFIED); `HumanPlayer:1709-1740` min/max dialog + range reject; AI clamped random (`ComputerPlayer:189-220`) |
| 12 | Modes | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.chooseMode` (`Player.java:768`); `HumanPlayer:2497-2608` modeMap UUID match + `canChoose` re-filter; AI first-choosable |
| 13 | Targets | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.choose/chooseTarget` (`Player.java:673-683`); `TargetImpl.possibleTargets/canChoose`; `possibleTargets.contains` ×5 (DIRECTLY_VERIFIED) |
| 14 | Optional targets | NATIVE_EXPLICIT, OBJECT_ID_BASED | `required=false` + toggle-off (`HumanPlayer:744-746,814-816`) + `isChosen` done-path |
| 15 | Numbers (`getAmount`) | NATIVE_EXPLICIT | `Player.getAmount(min,max,…)` (`Player.java:777`); dialog + range reject (`HumanPlayer:2178-2209`) |
| 16 | Colors | NATIVE_EXPLICIT | card-populated `ChoiceColor` (`ChoiceColor.java:15,46-50`); membership-checked `setChoice` |
| 17 | Card names | NATIVE_EXPLICIT | card-populated choice sets (e.g. `ChoiceBasicLandType`, name-choice cards); same `Choice` machinery |
| 18 | Creature types | NATIVE_EXPLICIT | `ChoiceCreatureType.java:20`; AI subtype heuristic selects only (`ComputerPlayer:839-888`) |
| 19 | Ordering (library/grave/top/bottom) | NATIVE_EXPLICIT, NATIVE_BUT_GUI_COUPLED | candidate set engine (`PlayerImpl:1068,1165,1211`); grave multi-card order gated by `userData.askMoveToGraveOrder()` + `chooseUse` (`PlayerImpl:5254-5274`) — preference inside path |
| 20 | Trigger ordering | NATIVE_EXPLICIT, NATIVE_BUT_GUI_COUPLED | game-built list (`GameImpl:2367-2376`); auto-order elision + `UserData.isAutoOrderTrigger` + trigger lists (`HumanPlayer:1516-1579`); AI first (`:955`) |
| 21 | Replacement ordering/choice | NATIVE_EXPLICIT, NATIVE_BUT_GUI_COUPLED | `ContinuousEffects:891-899` map, affected player picks; `autoSelectReplacementEffects` auto-pick (`HumanPlayer:534-546`); sim returns 0 |
| 22 | Attackers | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.selectAttackers` (`Player.java:770`); `canAttack` filter (`HumanPlayer:1801-1803`); per-attacker defender binding (`Combat:1483-1511`) |
| 23 | Defender per attacker | NATIVE_EXPLICIT, OBJECT_ID_BASED | `addAttackerToCombat(attackerId,defenderId)` rejects non-defenders (`Combat:1484-1486`); `selectDefender` per click |
| 24 | Blockers | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.selectBlockers` (`Player.java:772`); per-defending-player loop (`Combat:651-708`); `declareBlocker` validation (`PlayerImpl:2918-2935`) |
| 25 | Combat damage assignment/division | NATIVE_EXPLICIT | `CombatGroup:277-412`: `getMultiAmountWithIndividualConstraints` (multi-blocker), `getAmount` loop (divided), `chooseUse` (unblocked-as-though, `:176`) |
| 26 | Division / distribution (`TargetAmount`, multi-amount) | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.chooseTargetAmount` (`Player.java:683`); `getMultiAmount(+WithIndividualConstraints)` (`Player.java:791,818`); remaining-amount + parse/validity gates |
| 27 | Discard | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.discard*` family (`Player.java:549-559`); `getToDiscard→TargetDiscard.choose` (`PlayerImpl:889-901`); random branch is RNG not choice |
| 28 | Sacrifice | NATIVE_EXPLICIT, OBJECT_ID_BASED | `canPaySacrificeCost` (`Player.java:190`) + cost-target legality; AI ranking selects only |
| 29 | Search (library) | NATIVE_EXPLICIT, OBJECT_ID_BASED | `Player.searchLibrary` (`Player.java:466-476`); bounded `newTarget.choose` (`PlayerImpl:2986-3017`); per-searcher private dialog |
| 30 | Hidden-zone selection (choose from hidden) | NATIVE_EXPLICIT, OBJECT_ID_BASED | same search/choose-from-hand/library machinery; server sends candidate `CardsView` only to the chooser (`GameController:864-877`) |
| 31 | Reveal | NATIVE_EXPLICIT | `Player.revealCards` (`Player.java:610-632`); display-only, no legal set; global `state.revealed` + log broadcast |
| 32 | Scry | NATIVE_EXPLICIT | `Player.scry` (`Player.java:1188`); `TargetCard(Scry)+chooseTarget` (`PlayerImpl:5571-5584`) |
| 33 | Surveil | NATIVE_EXPLICIT | `Player.doSurveil/surveil` (`Player.java:1226-1228`); same target pattern (`PlayerImpl:5590-5610`) |
| 34 | Piles (fact-or-fiction) | NATIVE_EXPLICIT | `Player.choosePile` (`Player.java:693`); effect-built piles; boolean echo (`HumanPlayer:2645-2649`); AI left pile |
| 35 | Voting | NATIVE_EXPLICIT | `VoteHandler.getPossibleVotes` (`VoteHandler.java:120`); `TwoChoiceVote`; routed through generic choose/chooseUse dialogs |
| 36 | Secret choices (ask/choose privacy) | NATIVE_EXPLICIT | all query events addressed to chooser only (`GameController:188-230`); others get "Waiting for X" |
| 37 | Simultaneous choices (APNAP) | NATIVE_EXPLICIT | `Step/Phase/Turn` scaffolding; `checkTriggered` APNAP loop; `ZonesHandler.chooseOrder`; `handleSimultaneousEvent` (`GameState:808-820`) |
| 38 | May / optional use | NATIVE_EXPLICIT | `Player.chooseUse` (`Player.java:687-689`); boolean prompt; AI always-yes heuristic; Test scripted Yes/No |
| 39 | Optional replacement | NATIVE_EXPLICIT | `chooseUse` gate + `chooseReplacementEffect` index (`Player.java:764`); same machinery as #21 |
| 40 | Copy choices (which object/copyable values) | NATIVE_EXPLICIT, OBJECT_ID_BASED | copy target = UUID-bound target; modal copy choices via `chooseUse`/`Choice` (e.g. `[no copy]/[only copy]` tokens in TestPlayer mirror engine prompts) |
| 41 | Commander replacement (command-zone vs destination) | NATIVE_EXPLICIT | `GameImpl:2467 chooseUse(command)`; `GameCommanderImpl` command-zone init (`:95-137`); commander tax via repeated-cast path (J-P3B native test PASS lineage) |
| 42 | Concession | NATIVE_EXPLICIT | `Player.concede→setConcedingPlayer→lost` (`PlayerImpl:2705-2709`; `GameImpl:848-914` queue); `GameController:590-599` userId→playerId mapping; quit/timeout funnel (`PlayerImpl:2681-2702`) |

## Footnotes

- No row carries `INDEX_BASED`: ability/mode/target selection is UUID-keyed,
  never positional. (`TestPlayer` mode scripting uses 1-based indices, but
  that is a HARNESS-ONLY shorthand, not the engine wire.)
- No row carries `SEMANTIC_ID_AVAILABLE`: there is no second stable semantic
  action id — identity is UUID (+ZCC server-side). Any external
  option-set/decision identity must be adapter-built (non-rules).
- No row carries `ADAPTER_REQUIRED` for the NATIVE path (UUID-echoing adapter
  needs no legality reconstruction). `ADAPTER_REQUIRED_NON_RULES` applies to
  the identity envelope (request/option-set/stale/ack — see
  `XMAGE_SELECTION_NATIVE_EXECUTION.md` §5), never to legality.
- No row is `UNKNOWN`: every listed kind has a located engine method and
  Human/AI/Test implementation at this pin.

## Historical-statement adjudication (project-provider boundary, NOT engine)

The eight historical `*_SUPPORTED = FALSE` statements (mulligan, global legal
actions, global action submission, target/mode selection, trigger order, seed,
replay) describe PROJECT-PROVIDER support state at the J-P3B boundary, and
this audit FINDS NO ENGINE EVIDENCE contradicting any of them as provider
statements. As ENGINE-capability claims they would all be REJECTED except
seed/replay:

- Engine HAS: mulligan flow, target selection, mode selection, trigger
  ordering, per-decision legal sets, per-decision submission transport
  (all NATIVE_EXPLICIT above).
- Engine LACKS natively: global legal-action enumeration (no `getAllLegal-
  Actions` API exists — playability is computed per-dialog and per-priority-
  click set), global action submission contract (transport exists per-dialog,
  no unified external action API), external seed control (global `setSeed`
  only, no per-game seed), semantic replay (snapshot-stepper only, outdated).
- The Deep Research error, if it presented provider-support gaps as
  engine-incapability, is therefore: REJECTED for mulligan/targets/modes/
  trigger-order (engine HAS them), CONFIRMED for global enumeration/seed/
  replay (engine LACKS them in externally usable form). The research report
  itself was not found in-repo (see `XMAGE_FINAL_AUDIT.md`), so claim-level
  diffing stays at the statement level above.
