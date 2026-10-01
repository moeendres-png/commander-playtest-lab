# F-42: a player who concedes during its own "may" choice still decides

- **Issue:** #403
- **Surface:** XMage full-game lane. A concession (WS213) while the conceder's own non-priority choice is pending (CR 800.4a).
- **Classification:** bridge defect, whose stale answer the engine then counts.
- **Pin:** `9375f35a` (repin v2), with the F-39 native concede follow-up.

## Rules predicate

CR 800.4a: a player who left the game makes no choices.

With Tempt with Discovery ("Each opponent may search … For each opponent who does, search your library …"), P1 searches once for itself and once for each **remaining** opponent who accepts.

## Evidence (4P/5P, before the fix)

P1 casts Tempt with Discovery. The first opponent asked concedes while its `choose_use` frame ("may search") is open.

- The frame stays addressed to the departed player, whose `isInGame()` is `false`.
- Answering "Yes" is accepted. P1 then searches once more than the rule allows: 3 extra searches at 4P instead of 2.

## Root cause

F-39's follow-up retires the conceder's stale frame through XMage's native `signalPlayerConcede(true)`. `GameImpl.setConcedingPlayer` sends that signal only to the **priority player** (or the player controlling it), because XMage stops only that dialog.

A conceder whose own choice is pending during another player's spell is not the priority player. Its stale frame was never retired, and the engine counted its answer.

## Fix

After the native concession, `XmageFullGameSession.submitConcede` calls `XmageFullGameDecisionController.cancelPendingForDepartedPlayer`.

- It retires a pending frame whose own player is no longer in the game, for the observed classes whose callbacks unwind natively: `target`, `choose_object`, `mana_payment`, `choose_use`, and (follow-ups below) `declare_blocker`, `declare_attacker`, `mode`, `announce_x`, `amount`, `choice`, `target_amount`, `pile`, `trigger_order` and `mulligan`.
- The retirement is recorded as `engine_decision_cancelled` with reason `player_left_game`.
- A retired `choose_use` returns `false`, which is what XMage's own player returns once it cannot respond. No pilot response is accepted, and nothing is chosen on the player's behalf beyond that native no-response.
- Priority keeps its F-39 path.
- **Every other class fails closed.** An external audit of #404 pointed out that a per-class allow-list alone left any unlisted class answerable. The rule is now systemic:
  - a departed player's pending frame of any class without a qualified native unwind ends the lane fail-closed with `PLAYER_LEFT_GAME_UNSUPPORTED_DECISION`;
  - the frame is removed and the event is recorded with reason `player_left_game_unsupported_class`;
  - `request` never publishes a new non-priority frame for a player who left. Priority keeps the F-39 path, because after a self-loss the engine still gives the player one priority round (`XmageCausalEliminationReconstructionTest`).

  Test: P1 concedes at its own Fact or Fiction pile choice, which fails closed. It is 2/2 red before, when the pile frame stayed answerable for P1, and 2/2 green after.

## Follow-up: object choices (`choose_object`)

The same defect held for a pending object choice of a departed player:

- **Innocent Blood** (each player sacrifices): the departed player's sacrifice choice was still exposed to it and answered.
- **Council's Judgment** (will of the council vote): the departed player's vote frame was still exposed and answered.

`choose_object` shares the target callback (`chooseTargetInternal`), which returns `false` when retired: no sacrifice and no vote, as CR 800.4a requires. It is now in the retirable set.

## Tests

`XmageMultiplayerLeaverMayChoiceTest` (4P/5P) asserts that:

- no frame is exposed to the departed player after it leaves;
- every remaining opponent is asked once;
- P1 searches exactly once per remaining opponent who accepted;
- the retirement is recorded.

Each case runs at 4P and 5P:

| Case | What it asserts | Before the fix | After |
|---|---|---|---|
| Tempt with Discovery | P1 searches exactly once per remaining opponent who accepted | 2/2 red | 2/2 green |
| Innocent Blood | every remaining player sacrificed exactly its chosen creature | 2/2 red | 2/2 green |
| Council's Judgment | only the most-voted permanent is exiled | 2/2 red | 2/2 green |

In every case the red message was "no choose_use/choose_object frame is exposed to P4/P5 after it left". That was measured before F-41, when the first opponent asked was the last seat; since F-41 (turn order is seat order) it is P2.

The other leave suites stay green:

- `XmageMultiplayerLeaverStackTest`
- `XmageMultiplayerLeftPlayerDecisionTest`
- `XmageFullGameConcedeActionTest`
- `XmageMultiplayerControllerLeavesTest`

## Follow-up: a defender concedes at its own block prompt

- **Found by probe:** `XmageMultiplayerLeaveAtBlockTest`, 3–6P. P1 attacks P2 and P3, and P3 concedes while its `declare_blocker` frame is open.
- **Before:** the systemic rule above ended the lane fail-closed with `PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: declare_blocker`. That was safe, but a concession at a block prompt is an ordinary game event, and CR 800.4a says the game goes on for everyone else.
- **Fix:** `declare_blocker` is now a qualified class.
  - In `selectBlockers`, a cancelled frame, or a defender no longer in the game, ends that defender's declaration.
  - This is not a choice made on the defender's behalf: its creatures left the game with it (800.4a), so "no block" is the only possible outcome.
- **Test:** 4/4 red before (`PLAYER_LEFT_GAME_UNSUPPORTED_DECISION`), 4/4 green after. After the fix:
  - combat finishes;
  - P2 still declares its blocks, takes 1 from Hellrider's trigger and 1 from the Goblin;
  - nobody else is affected, and the game goes on.

## Follow-up 2: every decision class a player can concede at

`XmageMultiplayerLeaverDecisionClassTest` (4P/5P) has the active player concede while one of its own decisions is open. `XmageMultiplayerLeaverMulliganTest` covers the mulligan at game start.

**Before:** every class outside the first allow-list ended the lane fail-closed (`PLAYER_LEFT_GAME_UNSUPPORTED_DECISION`), and each game stopped for everyone.

**After:** each class now returns what XMage's own `HumanPlayer` returns once it cannot respond (read at the pinned engine), except `trigger_order`:

| Class | Unwind | Why it decides nothing for the departed player |
|---|---|---|
| `declare_attacker` | no further attackers | its creatures left with it |
| `mode` | no mode (`null`) | the cast is abandoned; the card left with it |
| `announce_x`, `amount` | the minimum | the spell or effect is its own and gone |
| `choice` (including cast-ability choice) | `false` / `null` | the same |
| `target_amount` | `false` | the cast is abandoned |
| `pile` | `false` | both piles are its own cards and left with it |
| `mulligan` | keep | its hand left with it |
| `trigger_order` | **none (`null`)** | see below |

**`trigger_order` is a rules defect, not only an availability gap.** XMage's own player returns the *first* ability once it cannot respond. `GameImpl.checkTriggered` then puts that ability on the stack for a player who has left, and it resolves.
- **Measured:** P1 casts Grizzly Bears with Impact Tremors and Purphoros out, and concedes while ordering the two triggers. Impact Tremors' trigger, controlled by the departed P1, dealt 1 damage to every remaining opponent.
- **Rule:** CR 800.4a says objects on the stack that a departed player controls, and that are not represented by cards, cease to exist.
- **Bridge fix:** the bridge answers "none" (`null`). `checkTriggered` plays nothing for `null`, and it stops asking a player who cannot respond. Now no ability of the departed player reaches the stack, and every opponent stays at 40.
- **Engine-side note for the repin lane:** native XMage has the same defect for its own players. `checkTriggered` plays the chosen ability without re-checking `canRespond()` after `chooseTriggeredAbility` returns.

**Still fail-closed:**
- `multi_amount` (combat damage assignment among blockers). A control test pins this.
- `replacement_effect`.

**Results:**
- `XmageMultiplayerLeaverDecisionClassTest`: 12/12 red before, 12/12 green after; `trigger_order` was red on damage even with a native-style unwind. The 2 `multi_amount` control cases stay fail-closed.
- `XmageMultiplayerLeaverMulliganTest`: 2/2 red before, 2/2 green after.
- The Fact or Fiction pile case in `XmageMultiplayerLeaverMayChoiceTest` now asserts that the game goes on.

## Follow-up 3 — why `multi_amount` stays fail-closed (measured, 2026-09-30)

A local probe (not merged) unwound `multi_amount` the way XMage's own player does once it can no longer respond (`MultiAmountType.prepareDefaultValues`).

**Scenario:** P1's Craw Wurm attacks P2 and is double-blocked by Grizzly Bears and Runeclaw Bear. P1 concedes at its own damage assignment (4P and 5P).

**Result:** the lane went on, but both blockers were in P2's graveyard at combat damage. The departed player's creature dealt combat damage after it had left the game, against CR 800.4a.

The Player seam cannot express "no damage" here:
- the vector must total the attacker's power;
- a `null` answer makes `CombatGroup` re-ask five times and then use the same default.

So the fail-closed path is the rules-correct behaviour at pin `9375f35a`. Qualifying this class needs an engine-side fix: `CombatGroup` must not assign damage for a creature whose controller has left. That fix is for the repin lane.

The control test `anUnqualifiedClassStillFailsClosed` now accepts the fail-closed code in both of the forms it is reported in. It is either the controller's `PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: multi_amount`, or the same code wrapped as `XMAGE_FULL_GAME_FAILED: DecisionException: …`, once the engine thread has surfaced it first. CI on the #420 head saw the wrapped form at 4P.

## Follow-up 4 — `multi_amount` for combat damage, requalified at pin `4e59e8b9` (F-43, 2026-10-01)

**What changed in the engine.** Follow-up 3 needed an engine-side fix. F-43 (mage#29) delivers it: after each player callback, `CombatGroup` re-resolves the exact damage source. When the source left with its controller, it deals no cached damage, gets no retry and gets no default vector. It was first measured at the candidate `4e59e8b9` (F-44 + F-43). The repin v3 lands on `37e4df6c`, which adds F-45 (mage#35); the measurement was repeated there.

**Bridge change, deliberately narrow.**
- `XmageFullGamePlayer` marks a `multi_amount` frame as qualified for a departed-player unwind **only** when its dialogue is one of CombatGroup's three combat damage titles (`Assign combat damage`, `… (with trample)`, `Assign blocker combat damage`).
- Only such a frame is retired when its player leaves. The callback then answers `null`; no default vector is chosen for the departed player. The engine continues in one of two ways:
  - **The source left with the player:** F-43 drops its damage.
  - **The source still exists** (another player held assignment authority): CombatGroup asks the departed player again, and the controller fails closed (`PLAYER_LEFT_GAME_UNSUPPORTED_DECISION`).
- Every non-combat `multi_amount` stays fail-closed.
- `XmageCombatDamageLeaverUnwindQualificationTest` binds the three titles to the pinned `CombatGroup` bytecode and requires `revalidateCombatDamageSource` to be on the classpath.

**Measured (the scenario of follow-up 3).** P1's Craw Wurm is double-blocked by Grizzly Bears and Runeclaw Bear, and P1 concedes at its own damage assignment.

| | 4P and 5P result |
|---|---|
| Live pin `37e4df6c` (repin v3) | Same as at `4e59e8b9`: 14/14 and 3/3 green (bridge suite 903 / 0 / 0 / 1). |
| Intermediate candidate `4e59e8b9` | The game goes on. Both blockers survive with 0 damage, the Wurm left with P1, and every other player is at 40 (`combatDamageAssignmentOfALeaverDealsNoDamage`). |
| The same bridge code on exact `9375f35a` | The engine asks the departed player again and the lane fails closed; nothing is dealt for P1. |

**Still fail-closed:** `replacement_effect`; non-combat `multi_amount`.
