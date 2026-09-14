# WS213 WS207_SETUP_CONSUMPTION

Consumed read-only (never rewritten): overlay, `SEED_CATALOG.json`,
`SETUP_MATRIX.json`, deck tables, setup prefs, predicates.

- Re-tagged deck tables verified card-identical to the sealed WS207 tables
  for all 12 WS213 constructions (`test_ws213_driver.py`).
- Qualified constructions re-driven with catalog seeds + setup prefs +
  production binding: all neutral predicates MET (`runs/SETUP_CHECKS.json`
  7/7: A03 [Skeletons/Swamp/Mountain], F01 [Forest@0], CLONE_FIRST/NO_HUMILITY
  [Bear@1]; C01/C03/D06 vacuous-empty predicates with twin+binding proof).
- Setup twins 7/7 TRUE (500/500); setup binding explicit + supported in
  every run; opening twins 12/12 MATCH.
- Other setup states remain UNKNOWN (A04, B01, E01, G02, G03, H01-aggregate,
  I01, J02): no fresh qualifying evidence; no zone/life/counter/
  commander-damage/ledger writes and no teleportation anywhere in WS213.
- E02/G04 carried BLOCKED statuses are retired by runtime mechanism proof
  (see COMBAT_E02 / CONCESSION_G04), not by setup injection.

Machine companion: `WS207_SETUP_CONSUMPTION.json`.
