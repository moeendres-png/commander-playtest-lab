# WS218 positive replay evidence (representative production-lane sessions)

All tapes: Lions technical decks, seed 424242, starting life 40,
`seed_mod_N` chooser, London mulligan, deterministic pilot derivation,
one game per fresh JVM. Each tape: record process A + replay process B +
independent replay process C (all fresh JVMs); B and C both PASS against
A's tape (semantic equality). RNG consumed after start in every tape.
Concessions force bounded complete terminals natively (exact-principal
offer/execute; no ring repair).

- REPLAY_2P (`runs/REPLAY_2P.json`, `tapes/ws218-tape-2p.json`): 611 steps
  (610 decisions + 1 concede); classes choose_object/mulligan/target/
  priority/mana/declare_attacker/declare_blocker/choose_use/multi_amount/
  concede; RNG 196→784; turn 20; life 34 vs 13 (combat damage);
  multi_amount numeric (5); commander casts + command-zone moves; B+C PASS.
- REPLAY_3P (`runs/REPLAY_3P.json`): 155 steps; combat + commander moves +
  targets + mana + 2 concedes; RNG 294→1176; B+C PASS.
- REPLAY_4P (`runs/REPLAY_4P.json`): 257 steps; combat + commander moves +
  targets + mana + 3 concedes; RNG 392→1568; B+C PASS.
- REPLAY_5P (`runs/REPLAY_5P.json`): 158 steps; targets + mana + 4 concedes
  over the 5P ring; RNG 490→1960; B+C PASS.

Collective coverage: nontrivial target/object (all), numeric (2P
multi_amount), Commander casts + zone choices (2P/3P/4P), combat attackers/
blockers + damage (2P/3P/4P), elimination/concession terminals (all),
RNG-after-start (all). No legal decisions fabricated for replay (all
choices are native offers answered by the production policy at record).
5P combat/commander absent in the 150-step window (honest bound; covered at
2P–4P, not claimed at 5P).
