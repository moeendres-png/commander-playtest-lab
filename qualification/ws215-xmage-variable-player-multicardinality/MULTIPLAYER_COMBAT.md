# WS215 MULTIPLAYER_COMBAT — PASS (4P/5P multi-defender + partition)

Combat legality stays engine-owned (Lab never computes defenders,
blockers, or damage). Observed natively through the production session
with Lions develop games (fresh JVMs, seed 424242, budget 600):

- 4P: 6 `declare_attacker` frames naming **4 distinct native defenders**
  (`defender_id` metadata per attacker option); exact defender binding
  per attack; 5 `declare_blocker` frames with blocker→attacker pairs
  (partition structure offered by the engine and answered legally);
  4 block-pair frames offered (up to 1v1 partition each).
- 5P: 4 `declare_attacker` frames naming **5 distinct native defenders**;
  2 `declare_blocker` frames with pairs; same gates.
- 2P/3P: same mechanism (2/3 defenders, block pairs incl. a 6-attacker
  frame in 2P).
- Existing WS213/WS206 damage-allocation semantics untouched (no
  Damage Assignment Order anywhere; current CR 510 honored by the pin).
  Commander combat damage recorded by the native watcher (see
  `COMMANDER_DAMAGE.md`).
- No illegal defender/blocker offer observed; no failure in any combat
  run; games continued natively past combat (damage, deaths, zone
  choices followed).

Fixtures `WS05-MP-COMBAT-4`, `WS05-MP-COMBAT-5`, `WS05-MP-BLOCK-4`:
RERUN → PASS.

Machine companion: `MULTIPLAYER_COMBAT.json`.
