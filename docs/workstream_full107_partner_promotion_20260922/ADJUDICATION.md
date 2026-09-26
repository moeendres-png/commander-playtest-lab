# Adjudication — PARTNER-ZONE / PARTNER-TAX DIRECT promotion (2026-09-22)

Evidence: merged executor work (`XmageFullGamePartnerExecutionTest`, 6
tests green locally — bridge 186/186 — and on CI in PR #224 conformance
`mvn verify`). Frozen records: `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`
(OBLIGATION_PRESERVED). Both frozen scripts are empty; no decisions were
invented at any point.

## PARTNER-ZONE — EXACT

- Requested state: P1 Rograkh (cmd:P1-A, 0 casts) + Kediss (cmd:P1-B, 0
  casts, partner_with cmd:P1-A); P2–P4 Rograkh; Bears×4 (one per seat);
  life 40; turn 1 precombat main P1 active/priority; seed 424242.
- Construction MATCH on every compared field (exact commander scaffolding
  with deterministic filler, exact-identity vehicle, pre-start assembly,
  cast-count restore, SBA/layers revalidation).
- Partner legality: engine Commander validator accepts the Rograkh+Kediss
  pair at import (and rejects the Isamaru counter-pair with
  COMMANDER_VALIDATION_FAILED — negative control).
- Required events `game_start_command_zone:cmd:P1-A/B`: both partners
  present as separate UUIDs at game start (pre-decision) and post-arrival.
- Terminal: both partners begin in command zone as separate commander
  identities (5 distinct UUIDs, no duplicates).

## PARTNER-TAX — EXACT

- Same state with P1 Rograkh prior casts 2.
- Histories restored and read back (2 vs 0); tax figures computed through
  the engine cost pipeline on COMMAND-zoned ability copies
  (`copyWithZone`, the sanctioned zoning mechanism): Rograkh `{0}+{4}`,
  Kediss `{1}+{R}`; purity proven by readback-equality around enumeration.
- Required events `tax:cmd:P1-A:+4` / `tax:cmd:P1-B:+0` derived from
  figures + counts (CR 903.8 arithmetic, same evidence class as WS05
  London counts and TAX-2 derivations).
- Independence: distinct counts, distinct figures, distinct UUIDs;
  swapped histories swap figures (negative); zero-history figures show no
  tax (negative); altered terminal expectation mismatches (negative).
- Terminal: partners track counts/tax independently.

## Standing gaps (documented, uniform with all DIRECTs)

- `requested_state_digest` frozen-hex reproduction blocked on the missing
  canonicalization spec (see PARTNER workstream DIGEST_GATE_ADJUDICATION);
  credit rests on field-level readback MATCH. Uniform conditional: a
  future digest mandate re-opens all DIRECTs.

## Result

DIRECT 4→6 (PARTNER-ZONE/TAX join MULL-2/4, TAX-2/4); NOT_RUN_BLOCKED
33→31; SUPPORTING 13 and UNKNOWN 57 unchanged. Only the two PARTNER
entries plus derived counts change.
