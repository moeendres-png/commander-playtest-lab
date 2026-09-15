# WS218 PROCESS_ISOLATION

One isolated JVM per game enforced by the bridge
(`full_game_process_already_used`; second `create_full_game` in the same
process refused — proven live). Every record (A) and every replay (B, C)
spawns a new bridge process (`_RawFullGameClient` Popen `... full-game`);
8 fresh JVMs per count-pair across 2P–5P (4 records + 8 replays), all PASS
with distinct per-process engine/player/object UUIDs and identical semantic
digests. Atomic writes (tmp+replace); interruptions leave complete artifacts
intact and mark `.incomplete` (never sealed). No shared mutable engine
state across record/replay.

Machine companion: `PROCESS_ISOLATION.json`.
