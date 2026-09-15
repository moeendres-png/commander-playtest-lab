# WS215 MULTIPLAYER_PRIORITY — PASS (3P/5P live ring)

Native priority progression observed in fresh-JVM lifecycles; the Lab owns
no priority logic.

- 3P neutral (150 decisions, turn 1→6): priority frames answered by all
  three seats in live-ring rotation; ring resets across turn boundaries;
  ≥2 distinct priority actors every run; no failure.
- 5P neutral (150 decisions, turn 1→4): priority frames answered by all
  five seats in live-ring rotation; same gates.
- 2P/4P: same observation (ring of 2 / 4).
- Actors rotate in engine turn order; passes resolve natively; turns
  advance only through native priority passing (neutral pilots pass
  everything offered; develop pilots cast into the same ring).

Fixtures `WS05-MP-PRIO-3`, `WS05-MP-PRIO-5`: RERUN → PASS.

Machine companion: `MULTIPLAYER_PRIORITY.json`.
