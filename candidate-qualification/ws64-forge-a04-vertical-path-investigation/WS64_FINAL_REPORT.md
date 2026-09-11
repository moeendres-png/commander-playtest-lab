# WS64 — Forge A04 Vertical Path Investigation — Final Report (bounded, fail-closed)

- Branch: `ws64/forge-a04-vertical-path-investigation-20260911`
- CPL audit base: `63930f13e8308c8a1d17fff5fd5a82c62ef5519d` / `e9eb007cc24bae8b0f35afae83f87ae4cadbde38`
- Accepted Forge pin (only engine pin): `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / `2c18327f79e330f2ed167067166ffd42d61b0849`
- WS63 diagnostic terminal/head: diagnostic authority only; NOT adopted.
- Code HEADs: `3a80c4e9` (fix) + `8cac11e9` (tracing/runner, no semantics). Validated HEAD: `8cac11e9` (clean committed; all validation runs on it).
- Terminal verdict: **WS64_A04_VERTICAL_PATH=PASS** — **PROVIDER_TRANSPORT_DEFECT** repaired; **A04 READY**; **C01/G04 retained**; **NEW_FORGE_PIN_REQUIRED=NO**.
- `BEHAVIOR_CREDIT=0/107` · `FULL107=NOT_RUN` · `ARCHITECTURE_FREEZE=NOT_CLAIMED` · `PRODUCTION_PROVIDER=NOT_SELECTED`

## Work completed

1. **Milestone A (exact reproduction).** Re-ran the credited WS62 A04 fixture unchanged (same intent, materialization, decks, structural-cap 2048, successor provider/Forge): 1282/1282 frames, 0 frame divergences, same offered digest, same verdict/reason/forge/seed. Material failure reproduced exactly (X=3, 3 G paid, stack 32, 0 replacement frames, GY 32).
2. **Milestone B (ACT→CAST identity trace, 12 items).** Qualification-only full-tape tracing on the clean accepted pin (behavior-preserving milestones): ACT o6 MINTED-32 → native SA 1545 (same object through playChosen, X announce v=3, payment X=3) → 3×Forest native payment → stack card 32 castSA 1545 X=3 → resolving X=3 fizzled=false → Moved first iteration n=1 own etbCounter (X=3, unlinked=false) → PutCounter SA 1993 (ETB, cost {0}, resolve-time calcX=3). Compared against WS63 native R2 lineage: MATCH through resolving SA; divergence isolated after (see root cause).
3. **Milestone C (root cause: PROVIDER_TRANSPORT_DEFECT).** `chooseCounterType` threw unconditionally, including singleton P1P1 for the ETB PutCounter. Human/AI return singletons automatically; Forge catches the throw and puts 0 counters, leaving CounterMap empty so DS/HS never contest. ENGINE/EVIDENCE/HARNESS defects ruled out with evidence (9/9 engine suites green; 0-divergence repro; harness single-match exact).
4. **Milestone D (authority).** Rules Core exclusively owns legality/X/costs/stack/replacement/zones/outcomes. Repair is transport-only (singleton auto-return + fail-closed multi/null) with observation-only counter tracing. No solver/arithmetic/synthesis/injection/manual transport/fallback/skip/card-name legality. Multi counter-type stays fail-closed.
5. **Milestone E (A04 acceptance).** Post-fix vertical proof: X=3, native payment, ACT→cast continuity, Moved n=1→n=2→n=1, both replacers engine-offered (HS 8 + DS 27), external HS-first ordering among offered options only, battlefield P1P1=8 on cardId 32, no synthesis, hidden PASS, replay 0 divergences.
6. **Milestone F (C01/G04 impact).** C01 re-proven identical (875/34, target SA binding, life 39, Frog exiled, Elves countered, hidden PASS). G04 transport invariant (conditional concession, no direct orchestration) + engine G04 4/4 on accepted pin.
7. **Milestone G (WS63 delta).** Accepted pin passes after CPL-only correction; NEW_FORGE_PIN_REQUIRED=NO; 3347084 not adopted (separate qualification required). WS63 empty-Moved phrasing corrected as truncated-tape artifact; its no-engine-defect conclusion is confirmed and closed.
8. **Milestone H (readiness).** Fixed denominator 15/20 reported only (First Wave NOT executed): 15/15 READY, 0/15 NOT_READY, 0/15 UNKNOWN.

## New findings

- F1. WS62 "0 CALLED" was a truncated-tape artifact (first-256 prefix missed the Stonecoil window at ~452+). Full tape proves 1 pre-fix call (singleton own etbCounter), not 0. Forensic bar refined, not relaxed.
- F2. Provider `chooseRanged`/`announceRequirements` X path is sound (v=3 reaches the exact cast SA 1545); the break is strictly downstream at counter-type transport.
- F3. `calculateAmount` timing matters: choose-time 0 (replacementEffect not yet attached) vs resolve-time 3. Root-cause proof rests on resolve-time calcX=3 plus the counterType CALLED event, not the choose-time artifact.
- F4. Post-fix terminal blocks move with survival (declare_attacker vs discard) — a healthy sign (Serpent alive as attacker option), still HARNESS class.

## Changes

- Committed code (validated HEAD `8cac11e9`): `ws64_provider_overlay.py` (counterType singleton parity + counter-observation tracing), `ws64_build.sh` (clean successor build + WS64 overlay), `ws64_fulltape_runner.py` (full-tape harness delta only).
- Evidence (descendant, does not promote validated HEAD): source lock, repro + comparison, 3 traces + full diagnostic tape, root cause, remediation, build receipt, postfix journal + intent + summary, replay journal + comparison, C01 journal + impacts, WS63 delta, hidden/replay, readiness, this report, state.
- No Forge edits in validated state (temporary diagnostics fully reverted + rebuilt clean). No other tree paths touched.

## Tests / Evidence

- Exact repro: 1282/1282, 0 divs, same digests (DIRECTLY_VERIFIED).
- Pre-fix full-tape diagnostic (clean Forge): 646 events incl. SA/X/payment/Moved/counterType chain (DIRECTLY_VERIFIED).
- Post-fix: 1235 frames, replacement o0 HS among HS+DS, calls n=1/2/1, P1P1=8, hidden PASS, replay 0 divs (DIRECTLY_VERIFIED).
- C01 post-fix: 875/34 identical, all retained items, hidden PASS (DIRECTLY_VERIFIED).
- Engine on accepted pin: 9/9 (A04 3/3, C01 2/2, G04 4/4) (DIRECTLY_VERIFIED).
- Static: forbidden grep PASS; concession/stack-SA markers invariant (CODE_DERIVED).
- Labels: only allowed set; never RUNTIME_VERIFIED.

## PASS / FAIL / UNKNOWN

**WS64_A04_VERTICAL_PATH=PASS** (bounded). No UNKNOWN verdicts in scope.

## Remaining blockers

None for A04/C01/G04 entry prerequisites. Post-window terminal blocks (declare_attacker/discard) are HARNESS intent gaps outside the A04/C01 windows, not entry blockers. First Wave execution itself is out of scope here.

## Outputs

`candidate-qualification/ws64-forge-a04-vertical-path-investigation/` (code + evidence + state + this report).

## Dependencies unblocked

- A04 vertical proof complete on accepted pin (unblocks First-Wave A04 execution).
- C01/G04 entry prerequisites retained (unblock their First-Wave execution).
- No new Forge pin required (unblocks planning without requalification).

## Exact next action

Coordinator: accept WS64 evidence (validated HEAD `8cac11e9`); schedule First-Wave execution for entry-prerequisite-met scenarios outside this workstream (this workstream claims no behavior credit); do not adopt 3347084; do not start Full107/Freeze/provider selection from WS64.

---
WS64_A04_VERTICAL_PATH=PASS
ROOT_CAUSE=PROVIDER_TRANSPORT_DEFECT
ACCEPTED_FORGE_PIN=a9a95db6662c2d28814390a9c0c2f986e39aa8b4
NEW_FORGE_PIN_REQUIRED=NO
A04_ENTRY_PREREQUISITE=READY
C01_ENTRY_PREREQUISITE=READY
G04_ENTRY_PREREQUISITE=READY
FORGE_RQC3_FIRST_WAVE_ENTRY_PREREQUISITES_READY=YES
READY_COUNT=15/15
NOT_READY_COUNT=0/15
UNKNOWN_COUNT=0/15
VALIDATED_HEAD=8cac11e9e5ec111a9d9901923f5a1c2d80165936
BEHAVIOR_CREDIT=0/107
FULL107=NOT_RUN
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
