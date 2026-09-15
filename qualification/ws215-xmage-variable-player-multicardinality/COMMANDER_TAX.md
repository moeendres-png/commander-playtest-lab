# WS215 COMMANDER_TAX — PASS (2P/3P/4P/5P recasts)

Commander tax stays engine-owned (no counters, costs, or ledgers in the
Lab). Observed natively in Lions develop games (fresh JVMs, all counts):

- Commanders die in combat → zone-choice frames → return to command zone
  (YES branch) → recast offers with tax-charged costs → accepted recasts
  with native mana payments succeeding.
- Native `CommanderPlaysCountWatcher` (`casts_from_command`) confirms:
  4P final `casts = 2` for the returned commander; 5P final `casts = 2`;
  3P two commanders at `casts = 2`; 2P `casts = 2` plus a natural terminal.
- Every recast executed without failure; payments drawn from the native
  mana system (26–104 mana frames per run, all satisfied or cleanly
  cancelled per the liveness guard).
- Partner independence of tax ledgers not separately exercised
  (see `COMMANDER_PARTNER.md`).

Fixtures `WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`: RERUN → PASS.

Machine companion: `COMMANDER_TAX.json`.
