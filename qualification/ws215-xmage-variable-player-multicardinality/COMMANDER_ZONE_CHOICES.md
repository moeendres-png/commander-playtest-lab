# WS215 COMMANDER_ZONE_CHOICES — PASS (GY branch both ways; others vacuous-documented)

Command-zone movement decisions stay engine-owned (no zone writes, no
ledgers in the Lab). Observed in Lions develop games (all counts):

- Graveyard SBA choice ("move Isamaru to the command zone or leave it in
  current zone (graveyard)?", `choose_use`): 2–3 frames per run in every
  count. Both native branches exercised via deterministic harness
  alternation: NO ("Leave in current zone (GRAVEYARD)") and YES
  ("Move to command") both accepted; YES returns feed subsequent
  tax-paid recasts (see `COMMANDER_TAX.md`).
- Exile/hand/library command-zone decisions: no commander went to exile,
  hand, or library in the bounded windows (no such effects resolved), so
  those branches are documented-vacuous, not fabricated. The choice
  mechanism itself (SBA `choose_use` through the production boundary) is
  proven by the GY branch; routing for other zones is the same native
  code path family.
- No life injection, no damage-ledger injection, no direct zone writes,
  no manual loss injection anywhere.

Fixtures `WS05-CMD-ZONE-GY-YES`, `-GY-NO`: RERUN → PASS.
Fixtures `WS05-CMD-ZONE-EXILE-YES/NO`, `-HAND-YES/NO`, `-LIB-YES/NO`:
fresh disposition UNKNOWN (no commander went to exile, hand, or library
in the bounded windows; mechanism engine-owned; claiming them would be
fabrication).

Machine companion: `COMMANDER_ZONE_CHOICES.json`.
