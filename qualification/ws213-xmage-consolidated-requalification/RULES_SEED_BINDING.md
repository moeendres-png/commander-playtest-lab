# WS213 RULES_SEED_BINDING

Contract (production `XmageFullGameSession` constructor, post-construction,
pre-`start`/`init`):

```java
game.setRulesSeed(seed);
game.setRequireExplicitSeed(true);
```

- `setRulesSeed` replaces the per-game `GameRandom` stream, zeroes the
  consumption counter, sets `rulesSeedExplicit=true` (WS212 `GameImpl:299`).
- `setRequireExplicitSeed(true)` arms the `init` gate that throws
  `IllegalStateException("WS54: game init requires an explicit Rules seed
  (setRulesSeed) in credited mode")` before companion handling, initial
  shuffle, choosing-player pick, hands, coin/die (`GameImpl:1311`).
- The window (construction → players/decks → binding) consumes zero Rules
  randomness on the pin (constructors, `useDeck` insertion, `addPlayer`).
- `RandomUtil.setSeed` is retired from the session: no import, no call, no
  non-Rules purpose retained. Source-guarded by
  `XmageFullGameRulesSeedBindingTest.productionSessionRetiredRandomUtilAuthority`
  and the revised WS207 guard test.
- WS207's qualification-only reflective hook is retired (production owns the
  binding); WS207 sealed evidence is untouched.

Proof (RUNTIME_VERIFIED):
- Every status/result/create payload carries `rules_seed_binding` read live
  from the native game: `explicit_seed`, `rules_seed`, `rules_seed_matches`,
  `rules_seed_explicit`, `require_explicit_seed`, `rules_random_calls`,
  `seed_supported` (= matches && explicit).
- Matrix: all runs bind the catalog/neutral seed with `explicit=true`,
  `supported=true`, and post-start `rules_random_calls > 0` (e.g. A03: 392).
- Negative (Java, `unboundGameWithRequiredSeedFailsClosed…`): unbound game +
  armed requirement → `start` throws the WS54 gate with zero Rules
  consumption (`getRulesRandomCalls` unchanged). Missing seed fails closed.

Machine companion: `RULES_SEED_BINDING.json`.
