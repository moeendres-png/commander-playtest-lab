# WS215 RULES_RNG_CARDINALITY — PASS (all counts)

WS213 production contract preserved for every player count (no
`RandomUtil` Rules authority anywhere in the session):

```java
game.setRulesSeed(orchestrationSeed);
game.setRequireExplicitSeed(true);
```

after construction, before start/init or any Rules-random consumption
(initial shuffle, choosing-player pick, opening hands).

Per-count live proof (every status/result/create payload carries
`rules_seed_binding` read natively at payload time):

- 2P/3P/4P/5P: `explicit_seed == rules_seed == orchestration seed`,
  `rules_seed_matches = true`, `rules_seed_explicit = true`,
  `require_explicit_seed = true`, `seed_supported = true`,
  `rules_random_calls > 0` post-start (e.g. 4P develop: hundreds of calls).
- Fresh-process same-seed twins per count per mode (neutral + develop):
  all 8 pairs MATCH on the full decision-row transcript hash
  (offsets, classes, seats, selected types, numerics).
- Distinct-seed controls per count per mode: all 8 DIVERGE (seed
  influence live; e.g. 4P neutral `b17378f33952` vs `e1fdfadead93`).

Harness determinism repairs (production and qualification):

- TD01: harness selections rank by stable Rules-visible content, never by
  raw engine-UUID order. The CR 103.2 starting-player choice (offered to
  the seed-chosen seat) is answered deterministically; production
  `_decide_targets` tiebreak changed to `(score, card_name, action_id)`.
- TD02 (liveness guard): pool mana matching no unpaid colored requirement
  is never spent (it loops the native payment request). Production
  `_decide_mana` pays pool only for generic-only costs or exact colored
  matches, else uses mana abilities/cancel, else fails closed. Unit tests:
  `test_mana_pool_shortcut_*` (3) PASS.

`RULES_SEED_BINDING (WS213) = PASS` retained and extended to N.

Machine companion: `RULES_RNG_CARDINALITY.json`.
