# Phase 1 Step 2 — Reuse-First Investigation (per missing dimension)

Source lock: `2231ff4b`; engine `org.mage:mage:1.4.61`
(pin `db134b9737e951367d65ef5806ad986319cc73ab` — matches research pin).
Inspected: `XmageNativeStateRestoration.java` (v1),
`XmageFullGameSession.java`, `XmageGameManager.java`, engine `Game`/`GameState`/
`SpellStack`/`CommanderPlaysCountWatcher` API via `javap` on the pinned jar,
frozen records (`SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`, 135 records).

Ranked by blocked-fixture leverage (ordinal/Pareto, no fake decimals):

## 1. stack_spells / stack_objects — 11 fixtures (highest leverage, highest risk)

Fixtures: `WS05-MP-PRIO-3/5`, `WS05-MP-ELIM-STACK-3`, 8x `WS05-CMD-ZONE-*`.
Native API: `SpellStack.push(game, stackObject)` exists, but pushing a
fabricated `Spell` bypasses costs/timing/targets/modes — it manufactures a
resolved outcome rather than reconstructing one. No engine-native
stack-reconstruction path preserving object/ability/target/mode/cost semantics
was found in the pinned API surface. The compliant unblock path is
executor-driven real casts (`NATIVE_CAST_SPELL`, cf. `WS05-MP-TRIG-3` native
procedure), which is executor scope, not restoration scope.
Classification: `REFERENCE_ONLY` for restoration; unblock requires a separate
executor-driven follow-up workstream.
Disposition: remain fail closed (`UNSUPPORTED_STACK`); no code change here.

## 2. commander_damage — 5 fixtures

Fixtures: `WS05-CMD-DMG-SAME-21/SPLIT/CONTROL`, `WS05-CMD-PARTNER-DMG`,
`WS05-CMD-ELIM-4`. Native API survey: only `CommanderPlaysCountWatcher` offers
a game-load restore path (already reused for cast counts). No
`CommanderDamageWatcher` or damage-history restore API exists in the pinned
jar (`unzip -l` shows only `CommanderPlaysCountWatcher`,
`CommanderInfoWatcher`; `PlayerImpl` carries commander IDs, not damage
history). Manufacturing damage history would reimplement the Rules in the lab.
Classification: `REFERENCE_ONLY`; requires engine-side remediation.
Disposition: remain fail closed (`UNSUPPORTED_DAMAGE_MATRIX` — already coded);
separate engine-side follow-up dispatch at Final Adjudication.

## 3. temporal points outside turn-1 precombat main — 7 fixtures

Fixtures: combat `declare_attackers` x2, `declare_blockers` x1,
`postcombat_main` x2, `beginning/draw` x2. Per the derived-state rule, arrival
must come from normal engine progression, not clock-field assignment
(`GameState.setTurnNum` exists but is not a correctness-preserving arrival
mechanism). `TurnMods`/phase-step entry ops exist only as frozen-record spec
(`NATIVE_ENTER_DECLARE_*`), not as qualified bridge operations. Building a
progression driver is executor scope and needs its own qualification.
Classification: `NEW_IMPLEMENTATION_REQUIRED` (deferred: genuine progression
driver workstream with per-step evidence).
Disposition: remain fail closed (`UNSUPPORTED_TEMPORAL_POINT` / step-variant;
already coded; START-2's fail-closed record stands).

## 4. hand_identity — 4 fixtures (IMPLEMENTED in this phase)

Fixtures: `WS05-MP-PRIO-3/5` (also need stack — not unblocked by hand alone),
`WS05-MP-TRIG-3/5` (hand only — unblocked by hand + executor cast).
Native API: `Game.cheat(uuid, library, hand, battlefield, graveyard, command,
exile)` — the exact typed setup primitive v1 already uses, with a dedicated
hand slot currently passed as empty (`List.of()`). This is the same qualified
mechanism as battlefield placement, not a new primitive.
Classification: `WRAP` (extend the existing cheat call with per-player hand
lists) + `HARDEN` (principal-scoped readback/compare + honeycard adversarial
tests + no-leak assertions on logs/digests/observations).
Why safe: hidden content never enters global pilot observation (redactor
already counts-only for opponent hands); readback identity is engine-direct in
tests, never pilot-facing; digest projection covers only requested objects.
A–E proofs required (see `PHASE1_HAND_EXTENSION.md`).

## 5. control_divergence — 2 fixtures

Fixtures: `WS05-MP-ELIM-CONTROL-3`, `WS05-CMD-DMG-CONTROL` (also damage).
v1 already rejects with `UNSUPPORTED_CONTROL_DIVERGENCE` after proving by probe
that layers re-derive control from owners + continuous effects. Compliant
restoration requires resolving real control-change effects (executor scope).
Classification: `REFERENCE_ONLY`.
Disposition: remain fail closed; no code change.

## 6. already-supported subset — 4 fixtures (no restoration change)

`WS05-MP-ELIM-OWNED-3`, `WS05-MP-ELIM-PRIO-3`, `WS05-MP-ELIM-TURN-3`,
`WS05-MP-ELIM-5`: frozen records show command+battlefield (+graveyard-free)
objects with owner==controller, untapped, no counters/attachments/facedown,
no damage/poison, turn-1 precombat main. Missing-dimension scan returns `[]`.
These are stale-mapping cells, not restoration gaps → Phase 2 exact execution
against existing v1, no code change here.

## 7. Other dimensions (library identity, revealed, facedown, attachments, counters, tapped, poison, stack)

Zero blocked fixtures require facedown/counters/attachments/tapped/poison/
library-identity alone (matrix scan confirms absence). Per the "do not expand
for theoretical completeness" rule, no work is done on dimensions no blocked
fixture requires. They remain fail closed with existing codes.

## Provenance / license

No foreign implementation text copied. All conclusions derived from the pinned
dependency's public API signatures plus current project source. Ledger entry:
`ENGINE_NATIVE_REUSE` (hand slot of `Game.cheat`) + `WRAP` (existing class).
