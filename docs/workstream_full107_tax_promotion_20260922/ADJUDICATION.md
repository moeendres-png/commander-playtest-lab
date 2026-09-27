# Adjudication — WS05-CMD-TAX-2 / TAX-4 DIRECT promotion (2026-09-22)

Evidence: merged executor work (`XmageFullGameTaxExecutionTest`: TAX-2 2P +
TAX-4 4P green locally — bridge 180/180 — and on CI in PR #220 conformance
`mvn verify`). Frozen records: `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`
(OBLIGATION_PRESERVED).

## Fixture correspondence (per fixture)

- Requested state: command-zone Rograkh commanders (P1 prior casts 2,
  others 0), battlefield Bears + Mountains (TAX-2: P1 Bear+4M, P2 Bear;
  TAX-4 adds P3/P4 Bears), life 40 all seats, temporal turn 1 precombat
  main with P1 active/priority, seed 424242 (manifest). `deck_state` is
  null (NATIVE fixtures carry no decks — nothing to deviate from).
- Construction: WS2 restoration (exact commander scaffolding + validated
  import, exact-identity vehicle, pre-start assembly, cast-count restore,
  SBA/layers revalidation) with readback MATCH on every compared field.
- Procedure ↔ `native_procedure`: CONSTRUCT_AND_VALIDATE → restoration +
  MATCH; OFFER_PRIORITY → engine priority offers; SUBMIT_SELECTED (cast_
  commander/cmd:P1-A, matches-only-offered, fail-closed both directions) →
  exact-one projected cast offer submitted via the protected proposal path;
  scripted passes → keeps/passes transport; RESOLVE_TO_TERMINAL → passes
  to battlefield presence + count-3 terminal postcondition.
- Required events from native facts: `commander_cast_from_command`
  (Rograkh on stack), `mana_paid:4` (four Mountains tapped, pool spent
  through engine-owned payment decisions; cancel never selected),
  `commander_tax:+4_generic` (0-cost spell, third cast per watcher,
  {4} paid — CR 903.8 arithmetic, same evidence class as WS05 London
  counts). Forbidden fallbacks prohibited; mana selection is the
  documented homogeneity-gated least-UUID rule among outcome-identical
  Mountain activations (same class as the WS05 bottom rule).
- Engine xmage 1.4.61 / pin db134b97, unchanged.

## Standing gaps (documented, same as MULL DIRECT)

- `requested_state_digest` compare protocol has no in-repo implementation;
  credit rests on field-level readback MATCH (no digest fabricated).
- Libraries/hands are unspecified fillers, uncompared by construction.

## Result

DIRECT 2→4 (TAX-2/TAX-4 join MULL-2/MULL-4); NOT_RUN_BLOCKED 35→33;
SUPPORTING 13 and UNKNOWN 57 unchanged. Only the two TAX entries plus
derived counts change.
