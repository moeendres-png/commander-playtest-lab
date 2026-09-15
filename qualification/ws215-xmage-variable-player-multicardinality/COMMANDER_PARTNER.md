# WS215 COMMANDER_PARTNER — zone PASS; tax/damage UNKNOWN

Partner semantics stay engine-owned. Observed in RogShai neutral
lifecycles (all counts, fresh JVMs):

- `WS05-CMD-PARTNER-ZONE` (multiple commanders start in command zone):
  RERUN → PASS. Every seat starts with exactly 2 commanders
  (Rograkh + Ishai) in the command zone in all 2P/3P/4P/5P runs
  (`command_zone_start` snapshots).
- `WS05-CMD-PARTNER-TAX` (independent tax ledgers): UNKNOWN — Ishai was
  never cast in the bounded windows (color-screwed early boards; only
  {0}-cost Rograkh casts observed: 7–17 offers per run), so independent
  partner tax ledgers were not exercised. Mechanism engine-owned.
- `WS05-CMD-PARTNER-DMG` (independent damage ledgers): UNKNOWN — no
  player was hit by both partners in the windows.
- Claiming either without observation would be fabrication.

Machine companion: `COMMANDER_PARTNER.json`.
