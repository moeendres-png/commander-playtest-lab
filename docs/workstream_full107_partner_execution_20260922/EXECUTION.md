# Execution record — PARTNER-ZONE / PARTNER-TAX runs (2026-09-22)

Harness: `XmageFullGamePartnerExecutionTest` (6 tests green locally;
bridge 186/186 in the full suite). Engine xmage `1.4.61` / pin `db134b97`
unchanged. Seeds: 424242 (manifest seed) all runs. Both frozen scripts are
empty — no decisions invented; execution is construction + arrival +
readback (+ cost enumeration for TAX).

## PARTNER-ZONE (4P, empty script)

- Construction: P1 Rograkh + Kediss (partner-linked) + Bears×1; P2–P4
  Rograkh + Bears×1; life 40; seed 424242. Scaffolding import success IS
  the engine Partner-legality proof (Commander validator accepts the
  Rograkh+Kediss pair; the Isamaru negative proves it rejects
  non-partners).
- Game-start check (pre-decision): P1 command zone holds Rograkh + Kediss
  as separate UUIDs; P2–P4 hold Rograkh. Required events
  `game_start_command_zone:cmd:P1-A/B` logged from this check.
- Arrival (keeps + passes) → cast-count restore (all 0) → SBA/layers
  revalidation → readback MATCH.
- Terminal: both partners present as separate identities from start
  through arrival (5 distinct command-zone UUIDs, no duplicates).

## PARTNER-TAX (4P, empty script)

- Same construction with P1 Rograkh prior casts 2; readback MATCH.
- Tax figures through the engine cost pipeline on COMMAND-zoned ability
  copies (`copyWithZone`, the sanctioned zoning mechanism): Rograkh
  `{0}+{4}`, Kediss `{1}+{R}`. Required events `tax:cmd:P1-A:+4` /
  `tax:cmd:P1-B:+0` derived from figures + counts (CR 903.8 arithmetic).
- Purity: readback MATCH before AND after enumeration (no game mutation).
- Independence: distinct counts (2 vs 0), distinct figures, distinct
  UUIDs; swapped histories swap figures (negative); zero-history figures
  show no tax (negative).

## Production change

`XmageNativeStateRestoration.enumerateCommanderCastCost`: engine cost
pipeline on a COMMAND-zoned ability copy; pure query. The only main-source
change in this workstream (additive method; no existing line touched).

## Negative controls (all green)

- Wrong Partner identity → `COMMANDER_VALIDATION_FAILED` at import.
- Swapped histories → compare MISMATCH naming casts; figures swap.
- Incorrect tax → zero-history figures differ from taxed requirement.
- Mismatched terminal expectation → compare MISMATCH.

## Residuals

- Mapping promotion of both fixtures to DIRECT: separate adjudication
  after CI proof (register + generator + mapping + guard).
- Digest-hex reproduction still blocked on the WS47 canonicalization spec
  (see DIGEST_GATE_ADJUDICATION.md); field-level standard applies.
