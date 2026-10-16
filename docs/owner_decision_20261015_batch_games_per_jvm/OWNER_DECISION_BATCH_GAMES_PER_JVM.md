# Owner decision 2026-10-15: batch runs may play several games per JVM

**Decided by:** Owner (project chat, 2026-10-15), accepting the Coordinator's recommendation.
**Owner's words:** "setze deine recommendation um". In English: implement your recommendation.

## The recommendation that was accepted

Several games per bridge JVM are an opt-in for batch measurement runs only. Each process
is replaced after N games, and twin runs check that no state leaks from one game to the next.

## Measured basis

These numbers come from a local study on XMage pin `38cb21a8`: the 5 four-player coverage
pods with seeds 1–4, 20 games, each played once in fresh processes and once in one warm process.
- All 20 games had identical semantic transcripts in both modes.
- Child CPU dropped by 58 %, wall time by 23 %.

## What changes

- **Bridge:** the system property `commanderlab.fullGame.gamesPerJvm=N` (default 1) lets a
  `full-game` process accept up to N `create_full_game` requests.
  - Each one needs the previous game to be shut down with `shutdown_game`.
  - Without the property, a process still plays exactly one game.
- **Runner:** `XmageFullGameRunner.run_batch` plays a list of games in one process.
  - It shuts each game down before the next one starts.
  - After a failed game it discards the process and continues in a fresh one.
  - Every result still rests on the graceful shutdown of the process that played it.
- **Coverage runner:** `scripts/run_collection_coverage_games.py --games-per-jvm N`.
  - The two twin runs of a pod play in different processes and in reverse order, so state
    left over from an earlier game shows up as a diverged twin.

## What does not change

Evidence lanes, qualification and the full-game batch evidence runner
(`full_game_batch.py`) keep one game per process; they never set the property. Results
from batched runs are measurements, not qualification evidence.
