# WS213 GENERIC_ACTION_REGRESSION

Full WS204 battery re-run on the repinned engine: `mvn -B -ntp verify`
(engine-bridge) → **105/105, 0 failures, 0 errors, 0 skipped**.

- 88/88 WS204-sealed tests preserved byte-identical in intent
  (`XmageFullGameActionProjectionTest` 17,
  `XmageFullGameGenericActionSubmissionTest` 4,
  `XmageFullGameGenericBridgeTest` 3, `Ws204DecisionKindCensusTest` 1, plus
  the 63-test baseline incl. D1–D4 projection/choice/redaction suites,
  fail-closed inventory, contract, state observation).
- 17 additive WS213 tests: `XmageFullGameRulesSeedBindingTest` 4,
  `XmageFullGameCombatDamageTest` 4, `XmageFullGameConcedeActionTest` 5,
  `XmageFullGameHiddenInformationTest` 1, `XmageFullGamePlayerCountTest` 3.
  (One combat responder race found and repaired during the run; 3/3 stable
  re-runs; no production change involved.)
- Proven on the new pin: offered-option origin, exact proposal validation,
  actor binding, revision/stale rejection, unknown/replay rejection,
  action-type match, numeric bounds, no requested-option filtering, no XMage
  AI authority, no GUI default, no second legality engine.
- Runtime negatives in every matrix run: wrong-actor REJECTED,
  unknown-action REJECTED (`ILLEGAL_ACTION`), pending unadvanced.

No coverage reduced, no denominator weakened, no assertion softened.

Machine companion: `GENERIC_ACTION_REGRESSION.json`.
