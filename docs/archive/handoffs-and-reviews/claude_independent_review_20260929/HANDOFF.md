# Handoff — XMage two-player first-draw rule (CR 103.8a) — 2026-09-29

Workstream `CLAUDE-XMAGE-2P-DRAW-SKIP-20260929`
Branch `claude/xmage-2p-draw-skip-20260929`
State file `.foundry/claude-xmage-2p-draw-skip-20260929.json`

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## Source lock

| Item | Identity |
|---|---|
| Lab base | `origin/main` `afe09c61d4ad90f89c28ff75ac7439a20b89cfdd` (tree `0d5b3f0d`) |
| XMage pin | `b19596980f2734496ea1896504253e1bdd2756dd` (unchanged) |
| Maven artifacts used | `~/.m2 org.mage:*:1.4.61`, verified by this workstream (see below) |
| Rules authority | `MagicCompRules 20260925.txt`, fetched live; sha256 `8d860e45…`, identical to the project receipt |

## Defect

Both XMage bridge lanes built every table as `CommanderFreeForAll`:
- `XmageGameManager` covers the Protocol-2 compatibility lane.
- `XmageFullGameSession` covers the full-game external-pilot lane.

At the pin, `CommanderFreeForAll.init` sets `startingPlayerSkipsDraw = false` unconditionally, and its match type declares `minPlayers = 3`. Every two-player Lab game therefore drew a card for the starting player on turn 1, against:

- **CR 103.8a:** "In a two-player game, the player who plays first skips the draw step … of their first turn."
- **CR 903.2:** a Commander game may be two-player.

CR 103.8c (other multiplayer games: no skip) was already satisfied.

The Lab had documented this as an engine blocker in the disabled `XmageFullGameStart2ExecutionTest`. It is in fact a game-type choice made by the Lab bridge. The engine's own two-player Commander type, `CommanderDuel` (min = max = 2), inherits `startingPlayerSkipsDraw = true` and skips the entire draw step through the engine's own turn modification.

## Change (reuse class: `ENGINE_NATIVE_REUSE`)

- **`XmageCommanderGames.create`:** picks the engine type by table size. Two players get `CommanderDuel`; three to six get `CommanderFreeForAll` with `setNumPlayers`. No rule is implemented in the Lab; the type choice is the only difference. Both types share `GameCommanderImpl`, and at the pin the game type has no other rules effect (`getGameType()` is used only for logging).
- **`pom.xml`:** adds `org.mage:mage-game-commanderduel`. Its classes are bytecode-identical to the pin source recompiled with `javac --release 8`.
- **Type widening:** `XmageFullGameSession` and `XmageGameManager` fields, plus the restoration helper signatures, move from `CommanderFreeForAll` to `GameCommanderImpl`. Eight tests that read the session game were widened the same way.
- **`XmageFullGameReplacementTest` (RG-08 Dredge):** the expected hand and graveyard counts had hard-coded a "transport discard −1". That discard existed only because P1 drew illegally on turn 1 and hit cleanup at 8 cards. The expectations are now derived from the observed number of P1 cleanup discards, and each 2P test asserts that count is 0. With d = 1 the formulas reproduce the old expected values exactly.
- **New `XmageFirstTurnDrawRuleTest` (9 cases):**
  - 2P full-game: no decision point inside the turn-1 draw step; P1's post-mulligan 7/92 is unchanged through turn-1 main; P2 then draws on turn 2 (8/91).
  - 3–6P full-game: the starting player draws on turn 1 (8/91).
  - Compatibility lane at 2–5P: engine game type, plus exactly one engine skip-DRAW turn modification for the 2P starter and none in multiplayer.
- **`XmageFullGameStart2ExecutionTest`:** stays disabled, now as provenance. Its frozen v1.0.5 record requests turn-1 draw-step priority, which CR 103.8a removes.

## Tests and evidence

| Check | Result | Class |
|---|---|---|
| engine-bridge full suite, base `afe09c61` | 329 run / 0 fail / 1 skip | RUNTIME_VERIFIED |
| engine-bridge full suite, branch | 338 run / 0 fail / 1 skip | RUNTIME_VERIFIED |
| Mutation: 2P forced back to `CommanderFreeForAll` | 4 Dredge + 2 new 2P cases FAIL (killed) | RUNTIME_VERIFIED |
| Protocol-2 JSONL A/B, PR #289 driver, `first_turn_draw_skip`, seed 424242 | main 2P: after 2 passes the state is turn 1 **DRAW step**, P1 **8/91**; branch 2P: turn 1 **precombat main**, P1 **7/92**; 3P on both builds: still upkeep | RUNTIME_VERIFIED |
| `~/.m2` `mage-1.4.61.jar` versus the pin build | 4456 class/txt files identical | DIRECTLY_VERIFIED |
| Python suite | branch failure set ⊂ pristine-main failure set (environmental; Python 3.14 locally) | RUNTIME_VERIFIED |

Command: `cd engine-bridge && mvn -o -Dcheckstyle.skip=true test`.

Rules behaviour classification:
- The 2P skip, the 2P second-player draw and the multiplayer draw are `DIRECTLY_VERIFIED` at runtime on the pinned engine.
- Rule text: CR 103.8a/103.8c from the official 2026-09-25 document. The expectations are rule-derived, not engine-parity.

## Impact on existing evidence (for impact adjudication)

- **PR #289's XMage `WS05-CMD-START-2` PASS** was produced by a bridge with the defect. Its own record (hand 8, library 91) is the violation. See `EVIDENCE_INTEGRITY_REVIEW.md` F-01.
- On a bridge containing this change, the same driver observes 7/92 at precombat main. The START-2 classifier still does not compare counts or the step (F-01/F-02), so a PASS from it remains non-discriminating until #289's owner fixes it.
- XMage 2P rows of the main current-boundary column (`PLAYER_COUNT_2P`), 2P native receipts and the historical RG-08 8/8 measurement were produced under the illegal draw. They need impact adjudication and re-execution on a head containing this change.
- RG-08 is requalified here under correct rules: 8/8 native.
- 3–6P behaviour is unchanged, verified by test.

## Findings recorded, not fixed (other owners or out of scope)

See `EVIDENCE_INTEGRITY_REVIEW.md`:
- F-01/F-02: the START-2 classifier and the driver's observation point (PR #289).
- F-03: `XmageBridgePlayer.chooseMulligan` returns keep with no fail-closed guard.
- F-04: tautological AF00.
- F-05: native-receipt freshness ignores Lab adapter drift.
- F-06: stale `dfb490e2` full-game AF01 artifact.
- F-07/F-08: narrow PLAYER_COUNT rows and PB-06 labels.
- F-09: PR #284's authored assertion strings.

Additional observation (INFERENCE):
- The compatibility-lane `startGame` comment says it reaches precombat main under an engine stop hook. Runtime state at return is turn-1 **upkeep** in both control modes.
- `Phase6DifferentialAdapter` still subclasses `CommanderFreeForAll` (historical Phase-6 lane, not changed).
- Upstream XMage's `CommanderFreeForAll` never skips even at 2 players. The Lab now avoids that path, and an upstream report is optional.

## Authority gates

None raised. The rule text is unambiguous (103.8a/103.8c/903.2). No pin, denominator, evidence-policy or provider change was made.

## Exact next action

1. Merge this branch after CI (Coordinator or owner decision; the PR is draft).
2. PR #289 owner: make `start2_row` compare P1 hand and library with the post-mulligan baseline and require a persisted observation at or after turn-1 `PRECOMBAT_MAIN`, then regenerate the XMage column on a head containing this change.
