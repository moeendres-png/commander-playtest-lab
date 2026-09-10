# WS53 — Native Progression Design (Objective B replacement)

## Rejected architecture (WS51 RESTORE_PATH_REJECTED, retained)

`restore at/after a decision-bearing step` → `continue as if native step entry already
occurred`. Proving instance BLOCK-4 (`WS05-MP-BLOCK-4`, turn-1 combat/declare_blockers):
`devModeSet` positioning skips the restored step's `onPhaseBegin` entry pipeline
(`orderBlockers`/`orderAttackersForDamageAssignment` stay null → blocked combat deals zero
silently; `AttackerUnblocked` triggers lost); the provisional mirror converts a loud NPE into
silent semantic loss. No CPL-side completion exists short of a second Rules engine.

## Replacement (this workstream, XHIGH Q4 CONFIRM)

`construct / restore only before the decision boundary` → `Forge advances natively` →
`Forge enters the decision-bearing lifecycle itself` → `Forge emits authoritative Decision
frame` → `external pilot selects authoritative option` → `exact native binding executes` →
`native events/state continue`. The engine performs the missing lifecycle behavior; the
harness never reproduces it manually. Forbidden mirroring (flags, attacker/blocker state,
damage-order maps, triggers, resolution routines, imported outcomes) is absent by
construction: the WS53 runner only answers engine-emitted frames and PASS-waits on
engine-offered declines.

## Boundary choice: NATURAL_GAME_START (strongest boundary, zero restore)

- Fixture `PILOT_MULLIGAN`, entry mode `NATURAL_GAME_START`: real shuffle (seed 424242),
  `chooseStartingPlayer` ritual seat-1, London mulligan flow per record script, then natural
  turn progression. No state load, no `devModeSet`, no hook, no mirror on the credited path.
- XHIGH confirmed this is the strongest native-progression boundary (WS51 F5 explicitly allows
  "natural start per WS50"); the earliest-practical-boundary rule does not obligate a
  restore-seeded alternative. A restore-strictly-before-decision variant would need Coordinator
  approval + strictly-pre-decision proof; not pursued here.
- Structural PASS prefix (412 passes over 440 frames) is probative waiting on engine-offered
  PASS declines (legal waiting moves, bounded by `--structural-cap`, per-frame journaled),
  not skipped entry. Termination is harness cap-termination at the first game-turn-13 priority
  frame after all intent is consumed (`HARNESS_BOUNDED_CLOSE`, deterministic; calibrated from
  the uncapped run which blocked at the next unscripted declare with zero remaining).

## Forcing declare_blocker natively (XHIGH Q4 material correction)

WS50-C shape (attacker-only + discards) has zero `declare_blocker` frames and cannot witness
the BLOCK-4 class. WS53 solves blocking natively within NATURAL_GAME_START constraints:

- P1 turn 1: plays Mountain MINTED-22, casts commander Rograkh MINTED-100 ({0}, free).
- P2 turn 2: casts commander Rograkh MINTED-201 ({0}, free). Round-1 non-P1 MAIN1 frames
  offer zero ACTs (priority passes to all seats each phase; nothing actionable for P2 on P1's
  turn) — the runner waits structurally (turn-scoped intent, `turns` field).
- Game-turn 5: P1 attacks P2 with MINTED-100 → Forge natively enters declare-blockers →
  P2 blocks with MINTED-201 (nontrivial exact binding, frame 170).
- Game-turn 6: P2 SKIP (explicit engine-offered decline; keeps 201 untapped — attacking taps,
  tapped creatures cannot block natively).
- Game-turn 9: P1 attacks P2 again → P2 blocks with MINTED-201 again (frame 313; same pair,
  distinct game state, distinct intent entry — subject-scoping + turn-scoping).
- Game-turn 10: P2 attacks P1 with MINTED-201 (P1's 100 tapped from its game-turn-9 attack →
  correctly NO block frame: native legality, not harness skip).
- All combat 0-power → no damage, no deaths, no triggers; `attackers_declared`/
  `blockers_declared` native events emitted and engine-accepted continuations throughout.

## Ten-point witness mapping (proven in WS53_NATIVE_PROGRESSION_WITNESS.json)

1. Fixture/construction before decision entry: natural game start (turn 0), first declare at
   frame 165 (game-turn 5). 2. Forge enters declare-attackers/blockers itself (milestone
   events on native tape). 3. Forge emits authoritative declaration frames (f165/f170/f208/
   f308/f313/f351 with complete option sets incl. SKIP). 4. External pilot receives complete
   authoritative option sets (journaled offered_options). 5. Nontrivial options selected
   (MINTED-201→MINTED-100 twice; MINTED-100→P2 twice; MINTED-201→P1; explicit SKIP).
   6. Selection binds exactly one native object (Repair-01 path + priority_binding records).
   7. Forge performs native lifecycle effects (attackers/blockers_declared events). 8. Resulting
   combat state produced by Forge (post-frame observations: tapped attackers, untapped
   blockers, unchanged life). 9. No mirror/manual completion (runner answers frames only;
   restore path allowlisted out). 10. Deterministic replay identical (REPLAY1 0 divergences).

## Distinguishing native progression from the rejected restore path

- No `NATIVE_STATE_LOAD` record on the credited path (code-level allowlist: only
  `WS53-C-NATIVE` credited; `--allow-diagnostic-restore` required otherwise, journal stamped
  `diagnostic_only`, never credited).
- BLOCK-4's signature (59 frames, zero declare frames, turn-4 lurch) is inverted here: 440
  frames WITH SIX declare frames (4 attacker + 2 blocker), all engine-entered.
- The previously skipped entry effects (declaration decision, attackers/blockers_declared
  events, milestone entry markers) are all present on the native tape.
