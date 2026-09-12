# WS65 — Forge RQ-C3 Corrected First Wave — Final Report (15/15 behavior execution)

- Branch: `ws65/forge-rqc3-first-wave-20260911`
- CPL audit base: `b303e6f18bbb937e977503e62273d4a72e26c2af` / `7c27dd7b621f5720acbfbf846d10e6263cda2faa`
- Accepted Forge pin (only engine pin): `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / `2c18327f79e330f2ed167067166ffd42d61b0849` (`moeendres-png/forge`)
- Exact Forge checkout: `/tmp/ws65-forge-src-a9a95db` (fresh offline `mvn` compile)
- RQ-C3 authority: `897d72f0b57bb8febe045870acaa3d2dba4bde56` (read-only export `/tmp/ws65-rqc3-authority-20260911/`)
- Terminal verdict: **FORGE_RQC3_FIRST_WAVE_EXECUTION=PARTIAL**
- `FIRST_WAVE_PASS_COUNT=9/15` · `FIRST_WAVE_FAIL_COUNT=0/15` · `FIRST_WAVE_UNKNOWN_COUNT=6/15`
- `DECISION_KIND_RUNTIME_COVERAGE=17/20` (missing: Commander movement, concession, copy choices)
- `BEHAVIOR_CREDIT=9/107` · `FULL107=NOT_RUN` · `ARCHITECTURE_FREEZE=NOT_CLAIMED` · `PRODUCTION_PROVIDER=NOT_SELECTED`

## Work completed

1. **Phase 0 — frozen executable surface.** Machine-readable inherited-surface manifest
   (`WS65_EXECUTABLE_SURFACE.json`: sha256 of all five provider overlays + bootstrap/state
   inputs). Fresh provider built from this worktree against the exact Forge checkout via new
   `ws65_build.sh` (mechanical equivalent of `ws64_build.sh`, path/provenance-only delta).
   HARD GATE PASS: all three generated digests byte-equal WS64-qualified digests
   (`aac55ccd…`, `b6b0870f…`, `761e451a…`). Runtime handshake
   `HANDSHAKE_RESULT PASS provider=forge forge_commit=a9a95db real_session_capable=true`;
   old pin absent from classpath (fail-closed gates).
2. **Phase 1 — authority extraction.** `WS65_SCENARIO_AUTHORITY.json` materialized from exact
   RQ-C3 source files (15/15, decision-kind union validates 20/20) with per-scenario execution
   interpretations; validated programmatically against sources.
3. **Phase 2–5 — actual-card execution.** All 15 attempted, each in fresh processes, with
   authoritative engine-offered options only, principal-scoped hidden info, recorded seeds,
   and semantic replay for every PASS (9/9 replay PASS, 0 divergences). 61,914 frames censused.
4. **Harness additions only** (no production-semantic edits): `ws65_runner.py`
   (ws64-verbatim delegation + concession family + target_done DONE-close override for an
   inherited ws62 arity bug, inherited files untouched) and per-scenario fixtures/intents.
5. **Four bounded remediation packets** (no repairs inside WS65): Ghalta-entry silent drop,
   payCombatCost gap, Clone-under-Humility non-engagement, Covenant X-mauling (+ concession
   emitter gap folded into the G04 assessment; five packet files total).

## Scenario adjudication (PASS / FAIL / UNKNOWN)

| ID | Verdict | Credit | Basis |
|----|---------|--------|-------|
| A03 | PASS | 1 | Bolt→Skeletons; regen {B} in response; singleton shield automatic (0 external frames); survival vs lethal; life 40s; hidden PASS; replay 0 divs |
| A04 | PASS | 1 | Verbatim WS64 rerun; X=3; HS-first of 2 offered; P1P1=8; replay 0 divs |
| B01 | PASS | 1 | Elves cast; 5 triggers; P0 externally orders its two (frame 356, 2 offered perms); APNAP resolution via sequential life; delta +2/+1/+1/+1; setup ledger documented; replay 0 divs |
| C01 | PASS | 1 | Verbatim WS64 rerun; both cost routes offered; pitch route; PAY life; exact-2-blue exile choice; counter resolves; life 39; hidden P0-scoped; replay 0 divs |
| C03 | PASS | 1 | X=5; 2 targets + DONE; 7 native mana; 2/2 split remainder lost; 38/38; replay 0 divs |
| D06 | PASS | 1 | Sequential mode picks among legal-only modes (AG-2 native); 3 targets; BBGG+2; all destroyed; replay 0 divs |
| E01 | UNKNOWN | 0 | Declarations accepted; payCombatCost fail-closed by design (UNSUPPORTED_DECISION_KIND) |
| E02 | PASS | 1 | Tyrant t22; double block; 2/1/4 via combatDamage frames; zero ordering frames (AG-3); life 36; replay 0 divs |
| F01 | PASS | 1 | WSEARCH rerun; Forest-11 of 78+NONE; shuffle journaled; hidden +/− controls; replay 0 divs |
| G02 | UNKNOWN | 0 | Reduced Ghalta CZ cast silent-drops twice (payment accepted, no stack); UNKNOWN causality |
| G03 | UNKNOWN | 0 | Bounded attempt reproduces G02 silent drop at entry; window unreachable |
| G04 | UNKNOWN | 0 | Control Magic state established (supplemental); concession never emitted (0/61914); Covenant X-mauling blocks loss path |
| H01 | UNKNOWN | 0 | Humility established (P4, immaterial deviation); copy never engages (0 frames); WCOPY control proves transport; ENGINE defect lead |
| I01 | PASS | 1 | Counter (native P1P1=1) + Pacifism built; Blink exile+return native; Aura to owner GY; clean 2/2; replay 0 divs |
| J02 | UNKNOWN | 0 | Delina CZ cast works; 1-14 band complete (token 2/2, EOC exile, P2 35); scripted 17/decline unmet (FIXTURE_AUTHORITY_GAP); replay deterministic |

## New findings

- F1. Cost-reduced commander casts silent-drop post-payment (reproduced ×2; non-reduced Delina CZ cast works on the same build — defect is reduction-specific).
- F2. `payCombatCost` (attack tax) has no overlay transport; fail-closed by design terminates the session.
- F3. Optional ETB-copy replacement never engages under Humility (no confirm/choice/milestone); WCOPY-successor verbatim control (same mechanic, no Humility) works — Humility differentiates.
- F4. Additional-cost (life) X is misbilled as mana-X (Covenant X=39 → 12 taps then rollback); mana-X (Fireball X=5) bills exactly.
- F5. Inherited ws62 `answer_target_done` arity bug (missing `labels` arg) breaks every multi-target DONE-close; bypassed in `ws65_runner` without touching inherited files.
- F6. Lands must be played before spells within a phase for the Play-land ACT to surface (ordering discipline discovered via G02).
- F7. Battlefield views carry printed names (WCOPY Image stays "Phantasmal Image") — names cannot prove copies.
- F8. Absolute B01 life totals (42/41/41/41) are mathematically unreachable in fully-native construction (minimum 10 setup triggers); the credited behavior is the ordering Decision + APNAP + delta, all evidenced.
- F9. Delina d20 is unjournaled (frames carry seed only); band inferable only by elimination (roll-again offer presence).

## Changes

- Committed harness/evidence only: `ws65_build.sh`, `ws65_runner.py` (+ target_done override),
  `WS65_SOURCE_LOCK.md`, `WS65_EXECUTABLE_SURFACE.json`, `WS65_BUILD_RECEIPT.json`,
  `WS65_SCENARIO_AUTHORITY.json`, per-scenario `RQ-C3-*/` packets (fixture, intent, gzipped
  journals, receipts, adjudications), matrices/credit/hidden/RNG/taxonomy JSONs, remediation
  packets, this report, state.
- No Forge edits. No provider/overlay semantic edits. No shared bootstrap edits.

## Tests / Evidence

- 9/9 credited replays PASS with 0 divergences (fresh processes).
- 61,914-frame census (zero concession frames; hidden PASS everywhere; zero observation violations).
- 4 differential controls: WCOPY-successor (copy transport sound), Delina CZ cast (Ghalta defect
  reduction-specific), Fireball mana-X (Covenant X-mauling differential), Ghalta retry (systematic).
- Labels used: only DIRECTLY_VERIFIED, CODE_DERIVED, TECHNICALLY_CONFORMANT,
  EXTERNALLY_RULE_VALIDATED, MODELED, SYNTHETIC, UNKNOWN. Never RUNTIME_VERIFIED.

## PASS / FAIL / UNKNOWN

**FORGE_RQC3_FIRST_WAVE_EXECUTION=PARTIAL** (9 PASS, 0 FAIL, 6 UNKNOWN).

## Remaining blockers

- Five remediation packets OPEN (Ghalta-entry, payCombatCost, Clone-Humility, Covenant-X, concession-emitter); each needs out-of-WS65 repair + impact requalification.
- Decision kinds 17/20 (Commander movement, concession, copy choices lack runtime demonstration).
- FULL107 NOT_RUN. No architecture freeze. No production provider.

## Outputs

`candidate-qualification/ws65-forge-rqc3-first-wave/` (this report + all artifacts above).

## Dependencies unblocked

- 9/107 cumulative Forge behavior credit with replayable evidence.
- 5 precise, reproducible defect packets with exact reproducers for downstream remediation.
- Qualified WS65 harness reusable for the remaining 6 scenarios post-remediation.

## Exact next action

Coordinator: accept PARTIAL (9/15) with 0 FAIL; schedule out-of-WS65 remediation for the five
packets followed by targeted re-execution of E01/G02/G03/G04/H01/J02; do not start Full107,
Freeze, or provider selection from WS65.

---
FORGE_RQC3_FIRST_WAVE_EXECUTION=PARTIAL
FIRST_WAVE_PASS_COUNT=9/15
FIRST_WAVE_FAIL_COUNT=0/15
FIRST_WAVE_UNKNOWN_COUNT=6/15
DECISION_KIND_RUNTIME_COVERAGE=17/20
BEHAVIOR_CREDIT=9/107
FULL107=NOT_RUN
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
