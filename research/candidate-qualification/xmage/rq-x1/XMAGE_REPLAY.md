# RQ-X1 — Semantic Replay (CODE_DERIVED, key cites DIRECTLY_VERIFIED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`.

SHORT ANSWER: no Semantic Replay exists. What exists: (a) human-readable log
display, (b) an outdated, self-declared-unused snapshot-stepper, (c) in-memory
bookmarks/rollback for undo and AI fork. No decision journal, no persisted
event journal, no deterministic reexecution, no seed+options re-drive.
`REPLAY_SUPPORTED = FALSE` (provider statement) is CONFIRMED as an engine
fact at this pin. A log is not a replay; a snapshot is not a reexecution.

## 1. Candidate inventory with classification

| Candidate | Location | Classification | Why |
|---|---|---|---|
| `informPlayers` strings / `GameLog` HTML formatter / client `saveGameLog` / `SaveGameHistoryDataCollector` (`gamesHistory/…game_logs.html+chat+deck.dck`) | `GameImpl:3223-3246`; `mage/util/GameLog.java:1-198`; `GameEndDialog:61,90`; `mage/collectors/services/SaveGameHistoryDataCollector.java:58-395` | LOG_DISPLAY | rendered human text + timestamps + colors; no structured choices, no RNG positions; sim-suppressed; collector header self-marks "not production ready yet, use for load tests only" |
| `GameEvent` bus (`EventType` turn/zone/damage/…, roll/flip events) | `mage/events/GameEvent.java:16-951`; fired e.g. `PlayerImpl:3370-3494,3132-3183` | NONE (as persisted replay) | in-memory trigger/replacement mechanism; nothing journals it to file/DB; `GameStates` stores snapshots, not events |
| `saved/<gameId>.game` (GZIP Java serialization of `Game+GameStates`) + `GameReplay` pager + `ReplaySession` viewer + `replayInit/Start/Stop/Next/Previous/SkipForward` RMI plumbing | `GameController:999-1019`; `game/GameReplay.java:20,32-75`; `game/ReplaySession.java:15-69`; `MageServerImpl:898-964`; `Mage.Common/.../MageServer.java:147-157`; `ClientCallbackMethod:69-73` ("replay (unsupported)") | NONE (snapshot-stepper, not reexecution) | deserializes STORED `GameState.copy()`s and renders `GameView`s; never re-applies decisions through the engine; header: "Replay system, outdated and not used. TODO: delete" (DIRECTLY_VERIFIED, `GameReplay.java:20`); config flag default false with "not working correctly yet" (DIRECTLY_VERIFIED, `Mage.Server/config/config.xml:26`) |
| `GameStates` (`List<GameState>`: `save()=add(copy())`, `rollback()=truncate`) + `bookmarkState/restoreState/rollbackTurns` + `gameStatesRollBack` (turnNum→copy) | `mage/game/GameStates.java:13-61`; `GameImpl:834-845,983-1067,3623,3979-4102` | NONE (undo primitive, not replay) | `rollback()` TRUNCATES later states; snapshots carry no RNG position, no decision list; `savedStates` fields `transient`, re-inited on `readObject` |
| `Game.copy()/GameState.copy()/deepCopyObject/Copier` fork | `GameImpl:191-283` (`createSimulationForAI/ForPlayableCalc`, `simulation=true`; explicitly drops `savedStates/gameStates/…/playerList`) | NONE (AI/rollback fork) | fork shares the GLOBAL RNG, so simulations perturb the stream they forked from |
| `TableRecord(table_history byte[] proto)` + card/user DB tables | `record/TableRecord.java:10-27`; `TableRecorderImpl:17-20`; `MatchView` | LOG_DISPLAY (post-game result proto for stats) | not a per-action journal |
| Server DB layer | ORMLite `CardInfo/ExpansionInfo/DatabaseBuild/DatabaseVersion`, `AuthorizedUser`, `UserStats` | NONE | no game/action/decision/RNG table exists (searched `DatabaseTable|DatabaseField`, `hibernate.cfg|persistence.xml`, `games_history|game_actions` — only card/user tables) |
| Live `Command.execute()` / permission dialogs | `GameController:1027-1049,1117`; `PlayerAction` | NONE | in-memory, never journaled |
| `journal/Journal`, `recording/Recording`, `GameStateSaver`, `saveGame/loadGame` (as state APIs) | repo-wide search | NONE (absent) | only card names ("Venser's Journal…", "Cursed Recording"); `GameStateSaver` zero hits; `saveGame/loadGame` beyond snapshot path = test deck-loader helper only |

## 2. Separation: log display vs decision journal vs deterministic reexecution vs Semantic Replay

- Log display: PRESENT (rich, timestamped, per-game HTML + chat + deck dump).
- Decision journal (ordered record of authoritative Decision Options +
  selections sufficient to re-drive): ABSENT. The wire HAS the options and
  selections transiently (see decision-seam files) but nothing persists them.
- Deterministic reexecution (re-apply journal on engine → identical states):
  ABSENT and affirmatively defeated — RNG position is not captured
  (`XMAGE_RULES_RNG.md`), snapshots truncate, `UUID.randomUUID` identity
  entropy makes cross-run object identity differ, and AI playouts share the
  stream.
- Semantic Replay (seed + Decision-Option journal → identical semantic
  trajectory, the project requirement): ABSENT. Seed-only would additionally
  require version-pinned RNG + consumption stability; source demonstrates the
  opposite (global shared stream, ≥3 entropy sources, iteration-order draws,
  variable consumption).

## 3. What a mirror would have to build (adapter-side, non-rules)

Because the transient wire already carries options+selections, a mirror COULD
record a decision journal WITHOUT engine changes (capture `GameClientMessage`
payloads + `sendPlayerUUID/String/Boolean/Integer` echoes + `GameView`
snapshots per decision). That journal is `ADAPTER_REQUIRED_NON_RULES` work,
not engine work. But replaying it deterministically still requires RNG
capture/control the engine does not offer: at minimum, record every
`RandomUtil` consumption (a global tap — engine modification) or interpose
determinism per game (engine modification). E
...[truncated 2112 chars]