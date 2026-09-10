# RQ-X1 — XMage Decision Seam (CODE_DERIVED, key cites DIRECTLY_VERIFIED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`. All paths relative to
`/tmp/rq-xmage-src`. All findings CODE_DERIVED (source inspection, no
execution) except where marked DIRECTLY_VERIFIED.

## 1. Where player decisions originate

The engine drives everything from the single GAME thread via
`GameImpl.playPriority()` (`Mage/src/main/java/mage/game/GameImpl.java:1723-1855`):
iterate `PlayerList`, set `priorityPlayerId`, call `player.priority(game)`;
on action reset pass state, on all-passed resolve the stack top or return.
Triggered abilities are collected in APNAP order in
`GameImpl.checkTriggered()` (`:2348` iterates
`state.getPlayerList(state.getActivePlayerId())`) and each player picks order
via `player.chooseTriggeredAbility(abilities, game)` (`GameImpl.java:2367-2376`).

The decision contract is the `Player` interface:
`Mage/src/main/java/mage/players/Player.java`, 1281 lines (DIRECTLY_VERIFIED).
Its header (`:42-52`) mandates every new dialog be implemented in
`PlayerImpl`, `HumanPlayer`, `ComputerPlayer`,
`ComputerPlayerControllableProxy`, `StubPlayer`, and `TestPlayer`.

## 2. Native request/prompt classes (wire events)

`HumanPlayer` (`Mage.Server.Plugins/Mage.Player.Human/src/mage/player/human/HumanPlayer.java`,
2960 lines, DIRECTLY_VERIFIED) never invents options. Every dialog follows one
pattern:

1. ENGINE computes the exact legal set (via `PlayerImpl` helpers, `Target`
   legality, `Choice` sets, `Modes.getAvailableModes`, engine min/max).
2. `HumanPlayer` sends the set over a typed `fire*Event` on `GameImpl`
   (`GameImpl.java:3058-3221`: `firePriorityEvent`, `fireSelectEvent`,
   `firePlayManaEvent`, `firePlayXManaEvent`, `fireAskPlayerEvent`,
   `fireGetChoiceEvent`, `fireGetModeEvent`, `fireSelectTargetEvent` ×3,
   `fireGetAmountEvent`, `fireGetMultiAmountEvent`, `fireChooseChoiceEvent`,
   `fireChoosePileEvent`). All are no-ops when `game.isSimulation()`.
3. The GAME thread blocks in `waitForResponse()` (`HumanPlayer.java:312`);
   the async CALL thread delivers the client echo via
   `setResponseString/UUID/Boolean/Integer/ManaType`
   (`HumanPlayer.java:2662-2720`) gated by `waitResponseOpen()` (latest-answer-
   wins, 30 s timeout, `synchronized(response)` + `notifyAll`).
4. `HumanPlayer` revalidates the echo against the CURRENT legal set
   (`possibleTargets.contains(responseId)` ×5 — DIRECTLY_VERIFIED count;
   `ChoiceImpl.setChoice` membership check; mode-map re-filter; amount range
   reject) and loops the prompt on mismatch.

`PlayerResponse` (`.../human/PlayerResponse.java:27-32`) carries only
`String/UUID/Boolean/Integer/ManaType(+manaPlayerId)` — no request id, no
state revision (see §6).

## 3. Available choice/options representation

- `Choice` / `ChoiceImpl` (`Mage/src/main/java/mage/choices/`):
  `setChoices(Set<String>)`, `setKeyChoices(Map<String,String>)`,
  `setChoice` accepts only members of the prebuilt set
  (`ChoiceImpl.java:134-146,184-198`); `setRandomChoice()` picks within the
  set (`:275-292`). Concrete sets (`ChoiceColor`, `ChoiceCreatureType`,
  `ChoiceCardType`, `ChoiceBasicLandType`, `ManaChoice`, `TwoChoiceVote` via
  `VoteHandler.getPossibleVotes`) are populated by CARD/ENGINE code, never by
  the client.
- Targets: `TargetImpl` (`mage/target/TargetImpl.java`) stores
  `LinkedHashMap<UUID,Integer> targets + zoneChangeCounters`; `choose` /
  `chooseTarget` (`:415-538`) go through the target controller with
  `possibleTargets/canChoose/isChoiceCompleted` gates.
- Modes: `Modes.getAvailableModes` filtered by `mode.getTargets().canChoose`
  (`HumanPlayer.java:2518-2534`); the wire carries a `Map<UUID,String> modeMap`
  and the response is matched by `mode.getId().equals(responseId)`
  (`:2598-2608`).
- Amounts: `fireGetAmountEvent(...,min,max)` + out-of-range reject loop
  (`HumanPlayer.java:1715-1732,2184-2203`); multi-amount via
  `MultiAmountType.parseAnswer + isGoodValues` (`:2242-2249`).

## 4. Per-decision-kind verdict: who produces the exact legal set

`ENGINE` = Rules Core builds the exact legal set; client/AI/adapter only
selects within it. Full method inventory (signatures + lines) is in the
sealed exploration record; summary verdicts:

| Decision kind | Verdict | Engine-side legal-set source |
|---|---|---|
| Priority: pass vs cast/activate | ENGINE | `PlayerImpl.getPlayableActivatedAbilities` (`:1875`) + `getPlayable` (`:4290`) + `getPlayableObjects` (`:4506`); `HumanPlayer.java:1420` consumes that set |
| Cast (which spell ability) | ENGINE | `PlayerImpl.getCastableSpellAbilities` → `HumanPlayer.java:2424,2463`; echo must be a member (`:2439,2485`) |
| Activate ability | ENGINE | same playable set + `activateAbility(map)` picker (`HumanPlayer.java:2326-2375`) |
| Targets (spell/ability/effect) | ENGINE | `TargetImpl.possibleTargets/canChoose/isChoiceCompleted`; server rejects non-members |
| TargetAmount distribution | ENGINE | remaining-amount bookkeeping both sides (`ComputerPlayer.java:234-235`, `HumanPlayer.java:1077-1122`) |
| Modes | ENGINE | available-modes + target-legality filter |
| X / numeric / multi-amount | ENGINE (min/max/totals) | card-supplied bounds; range/parse revalidation |
| Colors / creature types / card types / names / basic lands | ENGINE | card-populated `Choice*` sets; membership-checked |
| Ordering (top/bottom/Xth, grave order) | ENGINE (candidate set; any permutation legal) | `PlayerImpl` `TargetCard(order)` loops (`:1068,1165,1211`) |
| Attackers / blockers | ENGINE | `Permanent.canAttack/canBlock` + combat filters; `HumanPlayer.selectAttackers:1791`, `selectBlockers:2061` |
| Discard / sacrifice / costs | ENGINE | `getToDiscard→TargetDiscard.choose` (`PlayerImpl.java:889-901`); `canPaySacrificeCost` (`Player.java:190`); cost-target legality |
| Search library | ENGINE | `PlayerImpl.searchLibrary:2943-3038` — `newTarget.choose` bounded by `count(filter)` (`:2986-3017`) |
| Reveal / lookAt | ENGINE (no choice; display-only) | `revealCards` (`:1948`) / `lookAtCards` (`:1998`) |
| Scry / surveil | ENGINE | `TargetCard(Scry/Surveil)+chooseTarget` (`PlayerImpl.java:5571-5603`) |
| Voting (`TwoChoiceVote`/`VoteHandler`) | ENGINE | `VoteHandler.getPossibleVotes` (`VoteHandler.java:120`) |
| May / optional use | ENGINE (boolean prompt) | card calls `chooseUse`; HumanPlayer prompt (`:427`), AI, Test all select only |
| Replacement-effect choice | ENGINE (game-built list) | `ContinuousEffects.java:891-899` builds map; affected player picks index |
| Trigger ordering | ENGINE (game-built list) | `GameImpl:2371` passes `abilities`; HumanPlayer auto-order elision or dialog (`:1507-1624`) |
| Piles (fact-or-fiction) | ENGINE (effect-built piles) | `fireChoosePileEvent→getBoolean` (`HumanPlayer.java:2645-2649`) |
| Mana payment (which source) | ENGINE | unpaid `ManaCost` + `getUseableManaAbilities`; `firePlayManaEvent` (`:1647`); AI `testPay` sorted producers |
| Coin / dice / planar | ENGINE (RNG) | `PlayerImpl.flipCoins:3130` / `rollDice:3345` via `RandomUtil` global (see `XMAGE_RULES_RNG.md`) |
| Ring-bearer, legendary keep, companion, starting player, command-zone | ENGINE | `PlayerImpl.chooseRingBearer:5710`, `GameImpl:2957/1298/1342/2467` |
| Mulligan keep/mulligan | ENGINE (prompt; boolean, no legal set) | `mulliganDownTo` computes size; `fireAskPlayerEvent` (`HumanPlayer.java:386-419`) |
| Draft pick / sideboard / construct | ENGINE (framework list) | `firePickCardEvent/fireSideboardEvent/fireConstructEvent` (`HumanPlayer.java:2276-2285`) |

## 5. GUI/client contribution to legality: NONE

The client receives `possibleTargets` / `Choice` / `modeMap` / `min-max` and
cannot expand them: the server rejects out-of-set echoes and re-prompts.
Client-side preferences (`UserData` F4–F11 skips, `suppressAbilityPicker`,
`useFirstManaAbility`, `autoOrderTrigger`, `autoSelectReplacementEffects`,
`askMoveToGraveOrder`) only auto-pass or auto-pick WITHIN the legal set —
but they sit inside the `HumanPlayer` rules path (see reverser §6 in
`XMAGE_ARCHITECTURE_REVERSERS.md`). No production-reachable GUI legality.

## 6. AI contribution to legality: NONE (selection only)

`ComputerPlayer` (`Mage.Server.Plugins/Mage.Player.AI/.../ComputerPlayer.java`,
1368 lines) documents itself as "Full and minimum implementation of all choose
dialogs". Every branch selects within engine sets:

- Targets: `PossibleTargetsSelector` over `possibleTargets`, good/bad ranking
  (`:120-176`); `chooseTargetAmount` kill-priority (`:231-331`).
- X/numbers: clamped random within engine min/max (`makeChoiceAmount :189-220`).
- May: always-yes heuristic `outcome != AIDontUseIt` (`:778`).
- Choice strings: narrow heuristic + `setRandomChoice` fallback (`:786-837`).
- Piles/replacement/triggers: first-option (`choosePile→true :904`,
  `chooseReplacementEffect→0 :920`, `chooseTriggeredAbility→get(0) :955`).
- Modes: first-choosable (`:926-940`).
- Priority (base): pass (`:388`); `ComputerPlayer6/7/MCTS` add real sims but
  still select from `getPlayable*`.
- Mulligan/draft/sideboard: trivial heuristics.

AI randomness (`ComputerPlayer.java:212,1019,1044`; `ComputerPlayer6:682`;
`SimulatedPlayerMCTS` ~20 sites) consumes the SAME global `RandomUtil`
stream as Rules RNG — a contamination vector for determinism, not a legality
source. No AI legality anywhere.

## 7. Test-player position (harness only, not production)

`TestPlayer` (`Mage.Tests/.../TestPlayer.java`, 4727 lines, DIRECTLY_VERIFIED)
is a `Player` facade over a `ComputerPlayer` fallback: scripted
`addChoice/addTarget/addModeChoice` stacks matched by name/regexp against
engine sets (`setChoiceByAnswers`, `PossibleTargetsSelector.getAny()`), with
strict-fail or AI-fallback on miss. Unscriptable kinds delegate purely to
`computerPlayer`: `choosePile`, `chooseMulligan`, all `discard*`,
`searchLibrary`, library top/bottom ordering, `chooseRingBearer`,
`chooseAbilityForCast/chooseLandOrSpellAbility`, scry/surveil ordering.
`StubPlayer` (mostly `return false/null/min/0`) is tests-only. Neither is a
production decision path; neither contributes legality.

## 8. Adapter-reconstruction verdict

A text-only adapter (log scraping, label matching) would have to RECOMPUTE
legality via `Target.possibleTargets/canChoose`, `Choice.getChoices`,
`Modes.getAvailableModes`, `getPlayable*` — i.e. re-host the ENGINE. The
native wire already carries exact sets, so a UUID-echoing adapter does NOT
reconstruct legality (see `XMAGE_SELECTION_NATIVE_EXECUTION.md`). Dropping or
abstracting the payloads is what would force reconstruction.

## 9. Simulation guard (anti-fallback evidence)

`HumanPlayer.canCallFeedback()` (`:381`) returns false during legality
simulation or `checkPlayableState`; every dialog early-returns without
prompting in those modes (`:387,428,625,688,775,857,947,1041,1509,1638,1684,
1710,1792,2062,2179,2228,2296,2327,2412,2452,2499,2638`). The engine never
consults the GUI/AI/client when computing playability — structural evidence
against second-engine claims in the dialog path.
