# Adjudication — CARD_02 DIRECT promotion (2026-09-22)

Evidence: merged executor work (`XmageFullGameCard02ExecutionTest`, green
locally — bridge 196/196 — and on CI in PR #231 conformance `mvn verify`).
Frozen record: `SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`
(OBLIGATION_PRESERVED). Impact analysis since #231: main gained only
close-outs, the START-2 blocker record (with a deterministic
repository-readiness guard in card materialization — same cards resolved,
no behavioral delta on this path), and docs. No engine/pin/frozen/mapping
change touches CARD_02 evidence: NON-MATERIAL, no rerun or redesign
(CI re-verifies on this branch regardless).

## Fixture correspondence

- Requested state: 4P Rograkh commanders (casts 0), no battlefield
  objects, turn 1 precombat main P1 active/priority, seed 424242 (manifest
  + session arg + engine readback chain). `deck_state` absent (NATIVE —
  nothing to deviate from).
- Construction MATCH on every compared field plus construction digest
  equality to the frozen hex (same gate as the six DIRECTs).
- Script (single step, cast-commander P1, matches-only-offered,
  fail-closed both directions, all fallbacks prohibited, semantic
  `cast_commander` + `commander_id` cmd:P1-A + `from_zone` command):
  exact-one projected cast offer submitted via the protected proposal
  path. `from_zone` holds by single-source uniqueness (scaffolding
  libraries carry no Rograkh; exactly one Rograkh spell offered).
- Procedure NATIVE_CAST_COMMANDER + NATIVE_RESOLVE_TOP_OF_STACK: engine
  cast with fresh count (no tax, no payment decisions — fail-closed had
  any appeared), passes to resolution.
- Required events from native facts: `commander_cast` (Rograkh on stack),
  `spell_resolved` + `creature_entered` (Rograkh on P1 battlefield,
  stack clear).
- Terminal: Rograkh on P1 battlefield; watcher count cmd:P1-A = 1;
  no tax (pool untouched at 0, zero tapped permanents).
- Engine xmage 1.4.61 / pin db134b97, unchanged.

## Standing gaps (documented, uniform with all DIRECTs)

- Frozen-hex comparison via the recovered spec; field-level match first.
  Uniform conditional: a future digest mandate re-opens all DIRECTs.

## Result

DIRECT 6→7 (CARD_02 joins MULL-2/4, TAX-2/4, PARTNER-ZONE/TAX);
NOT_RUN_BLOCKED 31→30; SUPPORTING 13 and UNKNOWN 57 unchanged. Only
CARD_02 plus derived counts change; its stale injection reason is removed.
