# WS55 — FORGE MANDATORY DECISION-BREADTH — TERMINAL REPORT

- Branch: `ws55/forge-mandatory-decision-breadth-20260910`
- Source base: WS53 terminal `9493bb56` (FORGE_CONVERGENCE_NATIVE_PROGRESSION_PASS)
- Forge pin: `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29ce4de31a964972461db2b48b4221e07f` (read-only, untouched)
- RQ-C1 donor: `714ad417` / tree `709a5944` (read-only requirements input; expected outcomes NOT used as Rules truth)
- Principal disposition: **FORGE_MANDATORY_DECISION_BREADTH_PARTIAL** (bounded scope, §12)
- `BEHAVIOR_CREDIT = 0/107` · `FULL107 = NOT_RUN` · `ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Work completed

1. **Source lock + mechanical denominator (Checkpoint A).** CPL/Forge/RQ-C1
   HEAD+TREE verified; `ws55_derive_first_wave.py` derives
   `FIRST_WAVE_REQUIRED_DECISION_KINDS = 22` with manifest×matrix×scenario
   triple agreement (fails loud otherwise).
2. **Static inventory (Checkpoint B).** `WS55_DECISION_TAXONOMY.json` maps all
   22 kinds to Forge native methods + converged-provider status (CODE_DERIVED
   with file:line citations).
3. **XHIGH adjudication (Checkpoint C).** Read-only adjudication returned 10
   verdicts + 3 Sol-High authority gates; the implementer corrected one
   load-bearing adjudicator error (combat-damage surface already present via
   the ws40 base generator — code reality over subagent assumption).
4. **Provider remediation (Checkpoint D).** WS55 chained overlay J1–J13:
   optional-costs, order-costs (+Human mirror), combat ordering trio,
   multi-mode sequential, trigger-N + hid labels, deck/config env, ranged
   integers, trigger confirm/exec mirrors, audit milestones, zone-move
   ordering, pitch-cost mirrors. Build green; static gates 32/32.
5. **Breadth witnesses (Checkpoints E/F).** 16 evidence journals + 9 replays
   (all 0-div), 5 negatives (all fail-closed PASS), per-frame hidden-info
   adversary PASS throughout. 20/22 kinds runtime-proven with non-first
   competing selections; exact native binding; native consequences.
6. **WS53 impact (Checkpoint G).** Targeted requalification only:
   WS53-C replay 0-div + R1f witness PASS on the final provider; impact
   ledger 6 NO_IMPACT / 7 TARGETED_REQUALIFICATION_REQUIRED (all satisfied
   fresh) / 0 INVALIDATED / 0 UNKNOWN.
7. **Readiness + report.** 15-scenario seam matrix: 11 READY, 1 CONDITIONAL
   (E02, config flag), 3 NOT_READY (A04, C01, G04) with explicit blockers.

## 2. New findings

- **F1. Engine offers X over `[min, MAX_INT]`** (uncapped): exact enumeration
  infeasible; conformant ranged-integer path built (bounds verbatim +
  by-value submit + native validation). Descriptor `min=0:max=2147483647`
  journaled.
- **F2. Ordering is configuration-gated**: `orderBlockers` family fires only
  with `GameRules orderCombatants=true` (default false headless). Exposed as
  journaled fixture config; E02 readiness conditional on it.
- **F3. PRINTS MATTER**: UNKNOWN-edition PaperCards break ability enumeration
  (zero ACTs); native CardDb prints required. Real-print resolution used for
  all custom decks.
- **F4. Unviable ACTs listed, silently declined** (unpayable/untargetable
  options offered; selection is a silent no-op, no frame/event). Provider
  must not filter; harness must script viable options (workflow: assert
  `spell_resolved` for scripted casts).
- **F5. Counter events yield zero** (Serpent X=2 dies; TravelPrep damage =
  base): replacements never applicable; ordering never offered (audited).
- **F6. Regen-destroy bypasses generic ordering** (shield applied, RIP
  exiled the other creature, zero audit calls).
- **F7. Stack-spell candidacy empty** (`CANDIDATES:raw=0` for FoW vs a live
  stack spell): pitch fizzles silently. Battlefield/player targeting proven.
- **F8. Sorcery-speed land plays need empty stack** (correctly withheld
  mid-cast); multi-cast turns need MAIN1/MAIN2 sequencing; runner gained
  script-order fairness + `requires_stack` scoping.
- **F9. Multi-target DONE discipline** (Fireball/TravelPrep) + target_done
  family; Fireball omits P2 from its offered set (engine-authoritative,
  recorded EBO-2).
- **F10. Identical options need native identity**: hid-tagged ORDER labels
  make Warden-twins exactly orderable ([3,8] o1, P1 43).
- **F11. A03 "may" = regen ACTIVATION** (priority ACT o3/6); shield
  application is mandatory (no may-frame by engine design). Suture Priest
  may goes through confirmTrigger (NO o1).
- **F12. Copy routes through optional-replacement confirm** (YES/NO both
  proven; decline dies natively). Commander movement via 903.9a SBA confirm
  (YES→command zone / NO→graveyard; 903.9b has no second offer).
- **F13. Engine prunes unusable modes** (Cryptic Counter absent with empty
  stack) — offered set stays authoritative; sequential mirror handles it.

## 3. First-wave required decision denominator

`FIRST_WAVE_REQUIRED_DECISION_KINDS = 22`: Commander movement, X, activate,
alternate cost, attackers, blockers, cast, combat damage assignment,
concession, copy choices, defender per attacker, hidden-zone selection, mana
payment, mana source, may, modes, ordering, pass, replacement ordering,
search, targets, trigger ordering. (15 scenarios; per-scenario kinds in
`WS55_FIRST_WAVE_DECISION_REQUIREMENTS.json`.)

## 4. Current / final decision breadth

20/22 `PROVEN_NATIVE_EXTERNALIZABLE` (see `WS55_DECISION_BREADTH_MATRIX.json`
for per-kind evidence). Two terminal non-proven:
- `replacement ordering` → `ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE`
  (FIRST_WAVE_BLOCKING): seam exists + audited; engine never calls it
  across 3 shapes (F5/F6).
- `concession` → `ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE`
  (NONBLOCKING_FOR_CURRENT_GATE): never offered by nature; no seam exists;
  no option injected.
- Sub-gaps inside proven kinds: spell-stack targeting (raw=0, C01-blocking);
  FoW-pitch payment mirrors implemented but runtime NOT_REACHED behind it;
  DONE discipline implemented, exercised only where offered.

## 5. Selection → Native → Execution

Per-family bindings in `WS55_NATIVE_BINDING_MATRIX.json`. Non-first picks
include: ACT o8/o2 (Rograkh-land, dash), mana o1, targets o2/o3, damage
(Bear,1)o2, order o1 ×3 families, modes o1/o1, copy-choice o1, trigger o1
×2, confirm NO o1 ×2, search o2, zone-inserts non-first. Zero/multi/stale
fail closed (harness strict matcher + Broker tripwires).

## 6. Priority / Cast / Activate

Priority externalized as authoritative flow (WS53 417 + all breadth runs):
correct-player priority, PASS distinct, consecutive passes progress, no AI.
CAST via ACT exact binding (Repair-01 rerun). ACTIVATE via regen ACT o3/6
(distinct from cast spells; same exact-binding path).

## 7. Mana / Costs

Mana sources enumerated natively (lands + creature abilities); payment runs
the native `payManaCost`/`payManaFromAbility` path with the restrictions
gate. No external solver. CostTap/AddMana/mandatory-life exact mirrors
retained; orderCosts mirrors Human auto-return; CostExile/CostPayLife
bounded mirrors implemented (NOT_REACHED at runtime).

## 8. Modes / Targets / Division

Modes: single (old path o1) + multi sequential (new path o1/o1) with native
resolutions; engine prunes unusable modes (offered set authoritative).
Targets: candidates + DONE discipline (DONE entry family added); multi-target
Fireball proven. Division (`chooseAmountDistribution`) present via ws40 Core
views, runtime NOT_REACHED (non-first-wave).

## 9. May / Optional Choices

confirmTrigger (Priest NO o1), copy-replacement YES/NO both, regen
activation, commander YES/NO both. No defaults anywhere; both responses
selectable where offered.

## 10. Trigger Ordering

Exactly-2 legacy path (B01 shape) + identical-twins hid-exact ([3,8] o1,
P1 43) + distinct-pair with observable resolution order. N>2 generalized
(bound, NOT_REACHED). `orderAndPlaySimultaneousSa` guards intact.

## 11. Replacement Ordering

Seam exists (multi-choice + audit milestone, static-gated) but the engine
never calls it in witnessed shapes (F5/F6). A04 NOT_READY. No provider-only
repair is conformant (nothing to expose); no engine change proposed (root
cause is event-level behavior, RQ-C2 scope).

## 12. Combat

Attackers (o1 defender), per-attacker defenders, double-blocks, ordering
(config-gated perms + legacy lethal damage), Core-view damage splits on both
paths — all through WS53 native progression (engine-entered declares,
declared events, no restore/mirror). E02 READY_CONDITIONAL on
`orderCombatants=1`.

## 13. Search / Hidden-Zone Decisions

79-option fetchList, MINTED-11 o2 to battlefield, native shuffle, 0 leaks;
libraries counts-only; entitled-only option exposure; per-frame adversary
PASS on every journal.

## 14. Generic Choice / Ordering

Generic choosers keep native identity/authority (OPT labels project
engine refs). Zone-move ordering (orderMoveToZoneList) proven via RIP ETB
6/6 insertion frames with non-first positions.

## 15. Copy Choices

Object-to-copy choice (o1) + optional-replacement YES/NO + retained values
engine-side. Provider computes no copy semantics.

## 16. Commander Movement

903.9a SBA confirm YES→command zone / NO→graveyard (both proven, no
default). 903.9b flag path verified single-choice. Commander tax
implications untouched (no second cast).

## 17. Multiplayer / Voting / Secret Choices

4-player FFA topology throughout; per-player principal identity + APNAP
order preserved from Forge; hidden/public nature preserved. Voting/piles/
secret stay fail-closed (FUTURE_COVERAGE, correct). Concession: no seam
exists (initiated-only); G04 NOT_READY (AG-1).

## 18. Negative Controls

5 provider fail-closed probes PASS (bad-option ×2, stale, ranged-OOB,
replay-mismatch) + harness zero/multi blocks (twins 2-match, P2-absent
0-match, unscripted declare/confirm) + kind-family binding. Details in
`WS55_NEGATIVE_CONTROLS.json`.

## 19. Hidden Information

Per-frame adversary PASS on all 16 evidence journals + WS53 replay (0
violations); planted-name audits (searched Forest-11) 0 leaks; frame
serialization carries hidden identities to entitled actors only; journals
are harness-internal. Details in `WS55_HIDDEN_INFO_ADVERSARY.json`.

## 20. Native Setup Boundaries

All credited witnesses NATURAL_GAME_START (declared card-list decks via
native prints, forCommander registration, real shuffle/mulligans; zero
state load/devModeSet/mirror). E01/E02/J02 PRE_STEP and G03 PRE_DECISION
shapes are compatible (natural entry used; no restore). Matrix in
`WS55_SETUP_BOUNDARY_MATRIX.json`.

## 21. RQ-C1 First-Wave Readiness

11 DECISION_SEAM_READY, 1 CONDITIONAL (E02: requires orderCombatants=1),
3 NOT_READY (A04: replacement ordering engine-unoffered; C01: spell-stack
targeting raw=0 + pitch-payment behind it; G04: concession non-offered +
AG-1). Rules authority stays RQ-C2-pending for all 15 (no behavior verdicts
here). Full matrix in `WS55_FIRST_WAVE_READINESS.json`.

## 22. Forge Engine Gaps

EG-1 (ordering config-gated), EG-2/EBO-1 (zero counters), EG-3
(regen-dedicated path), EG-4 (stack candidacy raw=0), EG-5 (unviable ACTs
listed + silent decline), EG-6 (uncapped X bounds) + AG-1/2/3 for Sol High.
Details in `WS55_ENGINE_GAPS.md`. No engine change performed or requested
by WS55.

## 23. Provider Changes

J1–J13 overlay + runner extensions + 32/32 static gates + build script.
Details in `WS55_PROVIDER_CHANGES.md`. No WS48/WS53/shared file modified.

## 24. WS53 Historical Impact

6 NO_IMPACT / 7 TARGETED_REQUALIFICATION_REQUIRED (all satisfied fresh:
R1f PASS, WS53-C replay 0-div, trigger-label/handler/cost additions) /
0 INVALIDATED / 0 UNKNOWN. Ledger in `WS55_WS53_IMPACT_LEDGER.json`.

## 25. Changes

All under `candidate-qualification/ws55-forge-mandatory-decision-breadth/`:
5 implementation files (overlay, runner, gates, build, derive), 16 intent
files, 11 persistence/report JSONs/MDs, `WORKSTREAM_STATE.yaml`,
`ev-breadth/` (evidence journals, replays, negatives, gates). No other tree
paths touched (verified via `git status` at each commit).

## 26. Tests / Evidence

- Build: `ws55_build_breadth.sh` → WS55-BREADTH-BUILD-OK; digests
  provider `68d3cf6f…`, state `b6b0870f…` (= WS53, untouched).
- Static: `ws55_static_gates.py` → 32/32 PASS (DIRECTLY_VERIFIED/CODE_DERIVED).
- R1f witness rerun → PASS; WS53-C replay → 0 divergences.
- 16 breadth evidence journals (TRANSCRIPT_COMPLETE, hidden PASS) + 9
  replays (0 divergences) + 5 negatives (fail-closed PASS).
- Evidence classes used: DIRECTLY_VERIFIED (runtime), CODE_DERIVED
  (static/source reads), TECHNICALLY_CONFORMANT (Human-mirror
  implementations where runtime unreachable). No
  EXTERNALLY_RULE_VALIDATED claimed from Forge behavior.

## 27. PASS / FAIL / UNKNOWN

Principal verdict: **FORGE_MANDATORY_DECISION_BREADTH_PARTIAL** — substantial
breadth proven (20/22 kinds, 11 + 1-conditional scenarios) with three
first-wave blocking gaps explicitly classified (A04 engine-unoffered
ordering; C01 spell-stack targeting + pitch-payment; G04 non-offered
concession + authority gate). No UNKNOWN remains in required scope
(J12-payment sub-paths are NOT_REACHED-behind-targets, documented).

## 28. Remaining Blockers

1. A04 replacement ordering: engine never offers (EG-2/EG-3); needs
   engine-behavior investigation (RQ-C2/Forge-remediation), not provider work.
2. C01 spell-stack targeting: `getAllCandidates` raw=0 (EG-4); J12 cost
   mirrors wait behind it.
3. G04 concession: no seam by nature + AG-1 Rules gate (Sol High).
4. E02 conditional: Coordinator must confirm `orderCombatants` execution
   config with RQ-C2 (Rules-variant selection).
5. AG-2/AG-3 Rules questions (Sol High) gate outcome assertions, not seams.

## 29. Outputs

`candidate-qualification/ws55-forge-mandatory-decision-breadth/` (local
commits only; no push/merge/rebase): source lock, denominator, taxonomy,
adjudication, breadth/binding/readiness/setup/negatives/hidden-info/impact
matrices, engine-gaps, provider-changes, 5 implementation files, 16 intents,
74 ev-breadth files, WORKSTREAM_STATE.yaml, this report.

## 30. Dependencies Unblocked

`FORGE_RQC1_FIRST_WAVE_DECISION_SEAM_READY = NO` — 11 scenarios are
seam-ready (plus E02 conditional on execution config). Forge may enter the
candidate-neutral first-wave execution only after Coordinator confirmation
that RQ-C2/Sol Rules authority is ready AND disposition of A04/C01/G04/E02
blockers above. WS55 does NOT start the first wave.

## 31. Exact Next Action

**Coordinator:** (1) confirm RQ-C2/Sol Rules-authority readiness; (2) rule on
AG-1/AG-2/AG-3; (3) set the first-wave execution config for
`orderCombatants` (with RQ-C2); (4) disposition A04/C01/G04 as
engine-behavior vs engine-change work; then commission first-wave execution
as a separate workstream. No Full107, no credit, no Freeze, no provider
selection follows from WS55.

`BEHAVIOR_CREDIT = 0/107`

`FULL107 = NOT_RUN`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
