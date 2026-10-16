# Execution record — TAX-2 / TAX-4 native-procedure runs (2026-09-22)

Harness: `XmageFullGameTaxExecutionTest` (2 tests green locally; bridge
178/180 in the full suite). Engine xmage `1.4.61` / pin `db134b97`
unchanged. Seeds: 424242 (manifest seed) both runs.

## Common path (both fixtures)

1. Construction: frozen record → restoration plan → pre-start assembly →
   natural arrival (keeps + passes to turn 1 precombat main) → cast-count
   restore → engine revalidation → readback MATCH (fail closed otherwise).
2. Mana: no pre-pump. The scripted cast is selected with an empty pool;
   the engine parks on `mana_payment` decisions answered with
   homogeneity-gated least-UUID Mountain activations plus explicit
   pool-spend selections. Cancel is never selected.
3. Cast: exact-one projected cast offer for Rograkh (activated_ability +
   spell + command-zone source metadata) submitted through the protected
   proposal path; engine owns timing, tax, payment, and resolution.
4. Required events from native facts: `commander_cast_from_command:P1`
   (Rograkh on stack), `mana_paid:4` (four Mountains tapped, pool spent),
   `commander_tax:+4_generic` (0-cost spell, third cast, {4} paid).
5. Resolution driven with passes (both actors, unexpected classes fail
   closed) until Rograkh is on P1's battlefield; terminal postcondition
   (cast count 3) verified via watcher readback.

## Per-fixture results

- WS05-CMD-TAX-2 (2P): PASS — all required events + terminal postcondition.
- WS05-CMD-TAX-4 (4P): PASS — same path at four seats.

## Production change enabling execution

`XmageFullGamePlayer.priority()`: selected `SpellAbility` options are cast
through the engine (`cast(spell, game, false, approvingObject)`, in-thread,
bookmark rollback on failure) instead of falling into `activateAbility()`.
Offering untouched (engine-enumerated); non-spell paths byte-identical.
Retention R25 re-baselined (13 MICRO binds; 47/47 green).

## Residuals (executor scope, fail closed)

- Casts needing targets/modes/choices, shortfall payments, stack spells,
  hand/library identity, control divergence, non-main temporal points:
  unexecuted per WS2 dimensions + v1 cast bound.
- Mapping promotion of TAX-2/TAX-4 to DIRECT is NOT claimed here; it needs
  a separate adjudication (register + generator + mapping + guard update).
