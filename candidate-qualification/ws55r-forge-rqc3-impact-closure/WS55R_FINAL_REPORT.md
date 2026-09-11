# WS55R — FORGE RQ-C3 DECISION-BREADTH IMPACT CLOSURE — TERMINAL REPORT

- Branch: `ws55r/forge-rqc3-impact-closure-20260911`
- Source base: WS55 terminal `47a1e714` (`FORGE_MANDATORY_DECISION_BREADTH_PARTIAL`)
- Forge pin: `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29ce4de31a964972461db2b48b4221e07f` (read-only, untouched)
- RQ-C3 authority: `897d72f0b57bb8febe045870acaa3d2dba4bde56` / tree `1b8c8a46f1b81277f73a0ec808055dde25fadbe5` (read-only requirements input)
- Terminal disposition: **FORGE_RQC3_ENGINE_CHANGE_REQUIRED** (bounded scope)
- `BEHAVIOR_CREDIT = 0/107` · `FULL107 = NOT_RUN` · `ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Work completed

1. **Source lock + corrected denominator.** CPL/Forge/RQ-C3 HEAD+TREE
   verified; `ws55r_derive_rqc3.py` derives
   `CORRECTED_FIRST_WAVE_REQUIRED_DECISION_KINDS = 20` with
   requirements×delta×execution-pack triple agreement (fails loud otherwise).
2. **Impact ledger (22 families, mechanical).** `ws55r_impact_ledger.py`
   asserts every membership/delta premise and emits 17 NO_IMPACT / 2
   RECLASSIFIED_NONBLOCKING (may, ordering) / 3
   TARGETED_REQUALIFICATION_REQUIRED (concession, hidden-zone selection,
   replacement ordering) / 0 INVALIDATED / 0 UNKNOWN. All NO_IMPACT evidence
   preserved with zero reruns.
3. **A04 exact-fixture probe.** Doubling Season + Hardened Scales + Stonecoil
   Serpent X=3 assembled natively (T25 DS cast + 5 G; T29 Serpent cast + X=3
   by value + 3 G; resolution observed). Ordering never offered (zero
   milestones/frames in 1282 frames); Serpent died 0/0. Smallest
   engine-change packet specified (base ETB materialization + ETB
   AddCounter routing). No engine patch.
4. **C01 exact-fixture requalification.** Five Islands + FoW + blue nonland
   Turn to Frog + opposing Elves spell assembled natively (T22 response).
   Stages 1-5 PASS (both cost variants genuinely offered side-by-side;
   pitch variant exactly bound, d713/o3); stages 6-11 NOT_REACHED fail
   closed (engine-side post-selection abort, zero target/cost callbacks in
   837 frames; spell in hand; life 40; Elves resolved natively). First
   failing boundary source-derived (stack-spell candidacy mechanism).
5. **G04 architecture determination.** `Player.concede()` API + SBA
   `onPlayerLost` 800.4 chain exist natively, but initiation is GUI-only;
   `PlayerController` has no concession method — no offer set exists.
   Honest gap classification; nothing fabricated, nothing injected.
6. **E02 reclassification.** Corrected 5-kind E02 all NO_IMPACT-proven on
   both damage paths → DECISION_SEAM_READY unconditionally. No rerun (no
   shared implementation change).
7. **Hidden-info gates.** In-run adversary PASS on all new journals (837 +
   1282 frames); fresh C01 planted-leak audit PASS (18030 checks, 0
   violations; stack publicity intact); WS55 adversary preserved.
8. **Determinism.** Both evidence journals replayed 0-div
   (WS55R_C01_REPLAY, WS55R_A04_REPLAY).
9. **Readiness + report.** 15-scenario corrected matrix: 12 READY, 3
   NOT_READY (A04, C01, G04), 0 UNKNOWN verdicts. Sol gates AG-1/2/3
   persisted unresolved (out of scope by design).

## 2. New findings

- **F1. Exact A04 fixture fails at base placement, not just ordering.**
  X=3 paid yet 0 counters placed — the ETB CounterMap never reaches any
  replacement, so DS+HS have nothing to apply to (stacked causes (a)+(b)).
- **F2. C01 fails AFTER authoritative selection, not at offer.**
  Both cost variants are genuinely offered (normal 3UU + pitch); the
  external pitch pick is exactly bound and engine-accepted — then the
  engine aborts pre-target with silent rollback. Offer-side seams (cast,
  variants, mana publication) are PROVEN; only target-engagement fails.
- **F3. Candidacy mechanism ignores the stack.** `getAllCandidates`
  enumerates Players + Cards-in-zone only — stack spells are unresolvable
  by construction for `TargetType$ Spell` (source-derived root).
- **F4. Concession API exists but no Decision seam.** Authoritative
  initiation + native cleanup transition exist; offer/identity/projection
  do not (GUI-owned initiation). Initiation-only is not externalizable.
- **F5. Long natural games need bigger harness budgets.** 5-land fixtures
  exceed WS55's 1024-frame/512-priority budgets; WS55R-owned runner copy
  raises them (4096/2048, stamped) with zero semantic change.
- **F6. Positional native ids are deck-deterministic.** Same deck spec +
  qualification seed → identical MINTED ids across runs (diag→evid
  iteration sound; replays 0-div).

## 3. RQ-C3 impact (ledger summary)

17 NO_IMPACT (all proofs preserved, no reruns) · 2 RECLASSIFIED_NONBLOCKING
(may: A03/701.19a; ordering: E02/510.1c — proofs preserved as non-required
capability; historical 20/22 is NOT 20/20) · 3
TARGETED_REQUALIFICATION_REQUIRED (A04 exact fixture — now CLOSED as
ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE; C01 pitch context — now CLOSED as
stages 1-5 PASS / 6-11 NOT_REACHED; G04 architecture — now CLOSED as honest
gap) · 0 INVALIDATED · 0 UNKNOWN. Full matrix in
`WS55R_RQC3_IMPACT_LEDGER.json`.

## 4. Corrected denominator

`CORRECTED_FIRST_WAVE_REQUIRED_DECISION_KINDS = 20`: Commander movement, X,
activate, alternate cost, attackers, blockers, cast, combat damage
assignment, concession, copy choices, defender per attacker, hidden-zone
selection, mana payment, mana source, modes, pass, replacement ordering,
search, targets, trigger ordering. Removed vs RQ-C1: may, ordering.
Extended: hidden-zone selection (C01+F01). Retained blocking: alternate
cost, combat damage assignment, replacement ordering, concession. (15
scenarios; per-scenario kinds in `WS55R_CORRECTED_DENOMINATOR.json`.)

## 5. A04

Exact fixture assembled natively; X=3 by value paid; resolution observed;
ordering never offered (1282 frames, zero milestones). Verdict
ENGINE_DECISION_NOT_EXTERNALLY_REACHABLE with two-layer root cause and
smallest engine-change packet. No provider repair conformant. Details in
`WS55R_A04_REPLACEMENT_ORDERING.json` + journal `ev-ws55r/WS55R_A04_EVID.json`
(+ 0-div replay).

## 6. C01

Native-progression equivalent fixture (T22 response, five untapped Islands,
blue nonland Frog, opposing Elves spell). Stages 1-5 PASS (offer + variants
+ mana publication + exact pitch binding d713/o3); 6-11 NOT_REACHED fail
closed (post-selection engine abort, no target/cost callbacks; life 40;
exile empty; Elves resolved natively). First failing boundary + candidacy
mechanism source-derived. All provider FORBIDDEN items verified absent.
Details in `WS55R_C01_COST_PITCH.json` + journal
`ev-ws55r/WS55R_C01_EVID.json` (+ 0-div replay).

## 7. G04

Native API + transition exist; Decision offer does not (GUI-owned
initiation). Honest gap; no fabrication, no injection, no provider seam
(implementing one would be orchestration, out of scope). AG-1 persists
independently. Details in `WS55R_G04_CONCESSION.json`.

## 8. E02

Unconditional READY (5 corrected kinds proven both damage paths; ordering
removed from union). No rerun. Details in
`WS55R_E02_RECLASSIFICATION.json`.

## 9. Selection → Native → Execution

C01: o3 pitch-variant bound exactly (host MINTED-3 + pitch sentence,
single-match); forwarded verbatim to engine play path; engine completed
nothing observable (no callbacks). A04: DS 27 + Serpent 32 + X=3 + 8 mana
sources bound exactly across d812-817/d953-957; native resolutions (DS
battlefield; Serpent graveyard via SBA). Zero/multi/stale fail closed
throughout (harness strict matcher + Broker tripwires; e.g., DIAG2 P2-land
0-match block).

## 10. Negative controls

Preserved WS55 negatives (5 provider PASS + harness blocks) with NO rerun
(NO_IMPACT, no shared change). New implicit negatives: unscripted
replacement offer would fail closed (base.answer_replacement raises);
wrong-turn/actor entries 0-match fail closed (observed in iteration);
stale/duplicate/ranged guards untouched. No fallback/default/internals
anywhere (verified absent in both evidence journals' kind censuses).

## 11. Hidden information

Per-frame adversary PASS on all new journals (837 + 1282 frames, 0
violations); WS55 adversary preserved (no rerun); fresh C01 planted-leak
audit PASS (18030 non-owner checks, 0 leaks; stack publicity intact at 24
observations); A04 ordering checkpoint vacuous (no offer → no projection);
replays inherit. Details in `WS55R_HIDDEN_INFO.json`.

## 12. Forge engine gaps

EG-1 nonblocking (ordering removed) · EG-2 CONFIRMED exact-fixture (packet
layer a) · EG-3 context only · EG-4 CONFIRMED corrected-fixture (post-
selection abort; candidacy mechanism) · EG-5 CONFIRMED as pitch
presentation (correctly unfiltered) · EG-6 reused conformantly (X=3) ·
G04 initiated-only gap. No engine change performed or applied. Details in
`WS55R_ENGINE_GAPS.md`.

## 13. Sol gates

AG-1 (G04 equivalence) persists — seam gap independent. AG-2 (D06 modes)
persists — outcome-level only. AG-3 (E02 splits) persists — outcome-level
only. C-1 correction preserved. None resolved (out of scope by design);
none blocks unrelated work. Details in `WS55R_SOL_GATES.md`.

## 14. Corrected 15-scenario readiness

12 DECISION_SEAM_READY (A03, B01, C03, D06, E01, E02, F01, G02, G03, H01,
I01, J02) · 3 DECISION_SEAM_NOT_READY (A04 replacement ordering; C01
spell-stack target + pitch payment; G04 concession + AG-1) · 0 conditional
· 0 UNKNOWN verdicts. Rules authority RQ-C3-pending for behavior (no
behavior verdicts here). Full matrix in
`WS55R_CORRECTED_FIRST_WAVE_READINESS.json`.

## 15. Changes

All under `candidate-qualification/ws55r-forge-rqc3-impact-closure/`:
6 implementation files (derive ×2, ledger script, full runner copy with
2 stamped config deltas, inspect helper, hidden audit), 12 intent files
(C01 ×5 + A04 ×6 + EVID ×2... precisely: C01 DIAG1-4+EVID; A04
DIAG1-5+EVID), 12 persistence/report JSONs/MDs, `WORKSTREAM_STATE.yaml`,
`ev-ws55r/` (5 C01 + 6 A04 journals + 2 replays). No other tree paths
touched (verified via `git status` at each commit). No provider/shared/
Forge file modified (WS55 build reused byte-identical).

## 16. Tests / Evidence

- Mechanical: derive (20 kinds triple-agree) + ledger (premises asserted,
  17/2/3/0/0) — both scripts rerunnable, fail loud.
- Runtime: C01 EVID 837 frames (stages 1-5 PASS, 6-11 NOT_REACHED) +
  replay 0-div; A04 EVID 1282 frames (exact fixture assembled, ordering
  unoffered, 0 counters) + replay 0-div; 9 diag journals (iteration audit
  trail); hidden adversary PASS all; planted-leak PASS 18030/0.
- Source: G04 chain (API/transition/initiation/offer-absence), C01
  candidacy mechanism, A04 ETB layers — all file:line cited at the pin.
- Evidence classes: DIRECTLY_VERIFIED (runtime), CODE_DERIVED
  (static/source), no EXTERNALLY_RULE_VALIDATED claimed from behavior.

## 17. PASS / FAIL / UNKNOWN

Terminal verdict: **FORGE_RQC3_ENGINE_CHANGE_REQUIRED** — all 20 kinds
classified (18 proven incl. partial hidden-zone, 2 engine-blocked);
A04/C01 have precise engine-side root causes (C01's exact abort predicate
and A04's base-layer inner cause recorded UNKNOWN as non-blocking
micro-gaps); G04 needs engine-offer or architecture ruling; zero UNKNOWN
verdicts; hidden-info gates green. No provider-side path can close any of
the three gaps conformantly.

## 18. Remaining blockers

1. A04 replacement ordering: engine never offers under exact fixture
   (packet specified; Forge-remediation/RQ-C2 scope).
2. C01 spell-stack targeting + pitch payment: post-selection engine abort
   (candidacy mechanism; Forge-remediation scope).
3. G04 concession: no offered action (engine-offer addition or Coordinator
   architecture ruling).
4. AG-1/2/3 Rules questions (Sol High) gate outcome assertions, not seams.

## 19. Outputs

`candidate-qualification/ws55r-forge-rqc3-impact-closure/` (local commits
only; no push/merge/rebase): source lock, denominator + derive script,
impact ledger + script, A04/C01/G04/E02/hidden-info/gaps/gates/readiness
files, full runner copy, inspect + audit scripts, 12 intents, 13 journals
(11 run + 2 replay), WORKSTREAM_STATE.yaml, this report.

## 20. Dependencies unblocked

`FORGE_RQC3_FIRST_WAVE_DECISION_SEAM_READY = NO` — 12 scenarios are
seam-ready. Forge may enter RQ-C3 first-wave execution only after
Coordinator disposition of the three engine gaps (A04/C01/G04) plus
RQ-C3/Sol Rules-authority confirmation. WS55R does NOT start the first
wave. The A04 engine-change packet and C01 boundary record are ready-made
inputs for Forge-remediation scoping.

## 21. Exact next action

**Coordinator:** (1) confirm RQ-C3/Sol Rules-authority readiness; (2) rule
on AG-1/2/3; (3) disposition A04/C01/G04 as engine-change work (packets in
WS55R_A04_REPLACEMENT_ORDERING.json / WS55R_C01_COST_PITCH.json /
WS55R_G04_CONCESSION.json); then commission RQ-C3 first-wave execution as
a separate workstream. No Full107, no credit, no Freeze, no provider
selection follows from WS55R.

`BEHAVIOR_CREDIT = 0/107`

`FULL107 = NOT_RUN`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
