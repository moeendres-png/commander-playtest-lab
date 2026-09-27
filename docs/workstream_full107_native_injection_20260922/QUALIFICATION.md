# WS2 Qualification — native-state-restoration subset v1 (2026-09-22)

Source lock: `origin/main` `54fb222e`; frozen WS47 `5a2e4f46`; engine xmage
`1.4.61` / pin `db134b97` (unchanged). Suite: bridge 178/178 green
(163 pre-existing + 15 new in
`engine-bridge/src/test/java/org/commanderlab/xmage/XmageNativeStateRestorationTest.java`).

## Supported dimensions (each independently qualified)

| Dimension | Evidence |
|---|---|
| Command-zone commanders (1–2, incl. declared Partner pairs) | CARD_02, PARTNER-TAX MATCH; importer Commander-legality enforced (Rograkh+Kediss accepted); ambiguity fail-closed (`COMMANDER_IDENTITY_AMBIGUOUS`) |
| Prior commander cast counts (engine game-load restore path) | TAX-2 (P1=2) MATCH; single-restore batching (per-call replace semantics proven) |
| Battlefield/graveyard/exile placement of real cards (silent setup) | TAX-2, grave/exile MATCH; typed cheat slot order verified (`library,hand,battlefield,graveyard,command,exile`) |
| Owner-equals-controller attribution, 1:1 readback | all MATCH verdicts compare controller fields |
| Life totals (pre-start assembly) | all MATCH (40); setLife proven sticky across start |
| Turn-1 precombat-main arrival + active/priority binding | all MATCH compare turn/phase/step/active/priority; arrival via keeps + priority passes only |
| Explicit Rules-seed binding + replay determinism | `rules_seed` + explicit flag in every MATCH; TAX-2 twice → identical constructed digests |
| Layers authority post-placement | MICRO_LAYERS differential P/T (P1 Bears 2/2, others 1/1 under Humility+Anthem) |
| State-based-action authority (no false credit) | ELIM-OWNED-3 (life 0) assembles, loses P2 under SBAs, verdict NO_CREDIT with mismatches |
| Readback/compare sensitivity | tamper test (life 39 vs 40) → MISMATCH with field diffs |
| NATURAL-game construction validation (WS1 gap closure) | MULL-2 shape: command binding, 99/7 counts, seed binding at mulligan pending |
| Global flag preserved | `starting_state_injection_supported=false` asserted on provider payload + dimensions descriptor |

Fail-closed rejections (all throwing coded `RestorationException` before any
game mutation): hand/library identity, stack spells (also via frozen
ZONE-LIB-YES parse), facedown (via frozen parse path), attachments/counters,
tapped, control divergence, damage matrices, poison, non-main temporal
points, unknown card names, duplicate players, vehicle shortage, ambiguous
commanders.

## Engine-behavior findings (probe-proven, load-bearing for the design)

- Cheat slot order is `(library, hand, battlefield, graveyard, command,
  exile)`; command slot stays empty (commanders arrive via game creation).
- `applyEffects()` re-derives battlefield control from owners (direct
  `setControllerId` does not survive layers); control divergence is therefore
  rejected — reachable compliantly only via resolved control-change effects.
- `CommanderPlaysCountWatcher.restoreStateForGameLoad` REPLACES history:
  all commanders restored in one call.
- `setLife` pre-start survives game start; commanders auto-place in the
  command zone at init; exile/graveyard/battlefield setup persists.
- Battlefield placement applies effects with engine semantics (ETB-capable);
  fixtures with ETB triggers will park on trigger decisions (executor scope).

## Coverage statement

11 denominator fixtures assemble under v1 (MICRO_LAYERS, MICRO_COMBAT,
CARD_02, WS05-MP-ELIM-OWNED-3/PRIO-3/TURN-3/ELIM-5, WS05-CMD-TAX-2/TAX-4,
WS05-CMD-PARTNER-TAX/PARTNER-ZONE); life-0 ELIM shapes assemble but cannot
earn construction credit under SBA authority (proven). Everything else stays
fail-closed per the dimensions descriptor. No mapping classification changed
in this workstream; the next dependency is the native-procedure and
decision-script executor.
