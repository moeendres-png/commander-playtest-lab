# WS215 COMMANDER_MULLIGAN — PASS (free-first + paid London)

London mulligan with 1 free (engine `LondonMulligan(1)`) observed natively
in 2P and 4P Lions develop games with forced takes (fresh JVMs):

- Free path: first take by an actor → redraw 7, no bottom frame, keeps 7
  ("mulligans for free" native inform). `WS05-CMD-MULL-2` and the free
  half of `WS05-CMD-MULL-4`: RERUN → PASS.
- Paid path: same actor takes again → paid take → native bottom-1
  hand-target decision ("... to put on the bottom of your library")
  offered and answered legally → keeps 6. Mulligan offers are exactly
  keep/mulligan (min=max=1); takes recorded per actor; no failure.
- Multiplayer free mulligan is the same native mechanism at every count
  (identical construction `LONDON.getMulligan(1)` for 2–5P); 2P and 4P
  observed, 3P/5P share the code path with per-count lifecycles proven.
- No harness bottom-choice smuggling: bottoming arrives as a native
  hand-target decision through the generic boundary.

Fixtures `WS05-CMD-MULL-2`, `WS05-CMD-MULL-4`: RERUN → PASS.

Machine companion: `COMMANDER_MULLIGAN.json`.
