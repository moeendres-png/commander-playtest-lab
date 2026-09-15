# WS215 COMMANDER_DAMAGE — mechanism observed; thresholds UNKNOWN

Commander damage stays engine-owned (native `CommanderInfoWatcher`; no
ledgers in the Lab). Observed in Lions develop games:

- Watcher plumbing live in every actor view (`commander_status` with
  per-commander `commander_damage_to_player` rows and
  `casts_from_command`): damage accounting present and updating —
  e.g. 2P terminal-path run peaks at **8** commander combat damage dealt
  by a recast Isamaru; 4P/5P runs show accumulating totals.
- Combat damage by commanders resolves natively (declare_attacker →
  declare_blocker → damage → deaths → zone choices → recasts). The 2P
  natural terminal (seat 1 at −30) integrates combat loss with
  multiplayer cleanup.
- Threshold verdicts NOT observed in bounded windows and therefore NOT
  claimed:
  - `WS05-CMD-DMG-SAME-21` (21 same-commander loss): UNKNOWN — peak
    observed single-commander total 8 < 21; longer windows needed.
  - `WS05-CMD-DMG-SPLIT` (no pooling across commanders): UNKNOWN — no
    player was hit by two distinct commanders in the windows.
  - `WS05-CMD-DMG-CONTROL` (identity across control changes): UNKNOWN —
    no control-changing effect resolved in the windows.
- Claiming any threshold without observation would be fabrication.

Machine companion: `COMMANDER_DAMAGE.json`.
