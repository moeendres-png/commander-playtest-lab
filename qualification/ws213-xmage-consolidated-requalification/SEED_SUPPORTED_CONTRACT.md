# WS213 SEED_SUPPORTED_CONTRACT

`seed_supported` is never a bare boolean. On the full-game lane it is `true`
if and only if the live native game for that run satisfies:

```
game.getRulesSeed() == orchestrationSeed && game.isRulesSeedExplicit()
```

evaluated at payload time (`XmageFullGameSession.rulesSeedBindingPayload`,
attached to every status/result/create payload). The static lane capability
(`seed_supported: true`) cites this per-run proof in its notes.

Negatives (all covered):
- Unbound game + armed requirement → WS54 fail-closed before any Rules
  consumption (Java test).
- Source guards prove no `RandomUtil` code path remains in the session.
- B4 compat lane (`XmageProvider`) keeps `seed_supported: false`: that
  surface has no session binding and claims none.

Machine companion: `SEED_SUPPORTED_CONTRACT.json`.
