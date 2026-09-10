# WS55 — Provider / Harness Changes

All changes are WS55-owned, qualification-only, inside
`candidate-qualification/ws55-forge-mandatory-decision-breadth/` plus the
ephemeral generated provider (built, never committed). No pinned Forge
source, shared script, or WS48/WS53-owned file was modified. Rules-Core
authority preserved: every new branch enumerates engine options, binds
exactly, fails closed; no legality reconstructed; no engine AI/GUI.

## `ws55_provider_overlay.py` (chained after the WS53 overlay)

- J1 `chooseOptionalCosts`: sequential multi-select over the engine list
  with DONE discipline; exact `OptionalCostValue` binding. (Implemented,
  static-gated, runtime NOT_REACHED — no kicker-class witness.)
- J2 `orderCosts`: exact Human mirror (auto-return unless full-control +
  ≥2 parts, with `recordAutomatic`); else permutation frames (n≤5).
  (Auto path exercised by pitch payments; permutation branch NOT_REACHED.)
- J3 `orderBlockers`/`orderBlocker`/`orderAttackers`: permutation/insertion
  frames over the engine `CardCollection` (same objects, positional
  binding, n≤5, 0/1 auto-mirror). orderBlockers PROVEN (W-combat-B o1 +
  legacy damage); insertion/symmetric paths NOT_REACHED.
- J4 multi-mode: sequential externalization within the single native call
  (remaining-modes + DONE iff ≥min; min/num/allowRepeat bounds; mutable
  return). PROVEN (Cryptic o1/o1 + resolutions).
- J5 trigger ordering N (n≤5, multiset-validated) + hid-tagged labels
  (`hidfirst/hidsecond`, `hK`) for identical-twins binding. Exactly-2 path
  byte-identical. PROVEN (distinct o1 + twins [3,8] o1).
- J6 deck-list env (`COMMANDER_LAB_FORGE_DECK_MAIN/_COMMANDER`): native
  CardDb prints (UNKNOWN-print precedent fallback); absent = legacy
  Mountain/Rograkh path byte-identical. All breadth runs use it; setup
  stays NATURAL_GAME_START.
- J7 order-combatants fixture config (`..._ORDER_COMBATANTS=1`).
- J8 ranged integers (`chooseRanged` + NUMRANGE descriptor + by-value
  SUBMIT + native parse/range validation; state/observation capture
  included). PROVEN (MAX_INT descriptor, X=1 damage, X=0 bounds; OOB/
  missing/malformed fail closed).
- J9 `confirmTrigger` YES/NO over engine trigger identity (cost-trigger
  auto-true mirror) + choiceless `playTrigger`/`playSaFromPlayEffect`
  native-execution mirrors. confirmTrigger PROVEN (Priest NO o1).
- J10/J13 audit milestones (replacement call counts, target candidate
  counts). Load-bearing for non-offer evidence.
- J11 `orderMoveToZoneList` sequential insertion (any n, same objects).
  PROVEN (RIP ETB 6/6 with non-first positions).
- J12 pitch-cost mirrors: `CostExile` single-zone Hand/Battlefield shape
  (native list building, exact card binding, cancel iff non-mandatory) +
  `CostPayLife` non-mandatory confirm-or-cancel (native canPayLife gate,
  Human latch mirrored). Implemented + static-gated; runtime NOT_REACHED
  (FoW blocked upstream at spell-target candidacy).

## `ws55_breadth_runner.py` (extends WS53 runner by import)

- New families/kinds: combatDamage, amountDistribution, optional_costs,
  order_costs, order_combat, confirm (scripted), order_zone, cost_exile,
  mode_pick (+DONE), target_done, priority_cost (alt-cost variants with
  cost-text matching + `requires_stack` scoping), trigger_order N + hid
  matching (uniform sequence rule), replacement order_pick extension.
- Kind-family binding: each broker kind answered only by its own family.
- Script-order fairness for priority (first-due entry decides).
- Stack-aware scoping (`requires_stack` from native observations).
- SUBMIT by-value plumbing for NUMRANGE + value-aware journal identities.
- Negatives: bad-option (any kind), stale duplicate submit, ranged OOB.
- Diagnostic accept-any for order_zone (stamped diagnostic_only).

## `ws55_static_gates.py`

- 32 gates: Repair-01 preservation (4), WS55 surfaces (15), retained
  fail-closed stubs (9), no-AI/GUI/hacks (3), Core-view damage (2),
  no-lethal-arithmetic (1). PASS 32/32 on the final provider.

## `ws55_build_breadth.sh`

- Pinned generate→overlays→javac order incl. the WS55 overlay; no-AI/GUI
  import gates; digest recording. `WS55-BREADTH-BUILD-OK`.

## `ws55_derive_first_wave.py`

- Mechanical N=22 derivation (manifest × matrix × scenario files,
  triple-agree, fails loud otherwise).
