# WS219 Final Handoff — Bounded Candidate Freshness Qualification (Quorune + Argentum)

## Source Lock

- Commander-Lab audit base (WS215): commit `67db073367853da7295ae06642f38a73db464dba`, tree `a41ad3959caee03db59ffa15bdd44413d58ca766`, branch `ws219/candidate-freshness-quorune-argentum-20260915`, worktree `/home/moeen/code/ws219-candidate-freshness-quorune-argentum`. Verified via `git rev-parse HEAD` + `HEAD^{tree}`.
- Quorune: `NullPriority/quorune` commit `64ef65691b2952e29dfb2422687123d3ff5fc1b4`, tree `3dbb9619ec75bdebec74636a0a0b037cd0d85028`, read-only root `/home/moeen/code/ws219-ref-quorune-64ef6569`. License Apache-2.0.
- Argentum Engine: `wingedsheep/argentum-engine` commit `3f46367d87c88bcf156a843a9e69fd29e1693872`, tree `2adf51caa8f9c6a9908ea961fa988ebb5eb1959f`, read-only root `/home/moeen/code/ws219-ref-argentum-3f46367d`. License MIT.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.
- Requirement lock: `REQUIREMENT_LOCK.json` (catalog `df3b3548…`, contract `afdfa148…`, fixture manifest `e7f34ea4…`, card domain `39b832bc…`, taxonomy `1d214722…`, authority `f6efd4b5…`, mission `c8041f79…`).

## Work Completed

- Read canonical AF00-AF11, Full-Rules contract, Common Fixture Manifest (175 fixtures), frozen 29-card denominator, evidence classifications, hidden/RNG/replay/Commander obligations; locked hashes.
- Deep read-only audits of both candidates (architecture, rules kernel, command/legal-action model, hidden info, determinism/RNG/replay/record, Commander/multiplayer cardinality, card lowering, unsupported handling, licenses, test inventory) via parallel explore agents + direct verification.
- Frozen-29 census per candidate with bounded probes: `probes/ws219_quorune_frontier_check.py` (31623 frontier records; 8 trusted/21 residual) + `probes/ws219_argentum_card_check.py` (13915 card names; 11 defs/18 missing) + Partner-gate + OVERLOAD greps.
- Micro-rules census (17 areas each), Commander/multiplayer census (2P/3P/4P/5P + 6P, priority/APNAP/combat/extra-turns/elimination/tax/zone/damage/Partner/mulligan/start), legal-action surface (incl. AI-excludability), hidden-info, RNG/replay (incl. WS218 Tape v1 gap) for both.
- AF00-AF11 matrices per candidate (classification + evidence + paths + runtime + gap + burden).
- Early-stop adjudication: proven material AF06/AF07 blockers for both; stopped expensive full-suite runtime (correctly) after bounded probes.
- Sealed all 22 required outputs under `research/candidate-freshness/ws219/**`; validated scope/mutation/evidence honesty.

## New Findings

- Quorune: deterministic seat-projected command-replayed fail-closed partial Commander engine (4P primary, 2-6 constructible, Partner-family typed, ~31.5% exact lowering). Terminal: 0/29 frozen SUPPORTED (8 trusted with zero behavior tests; 21 residual); universal layers/replacement/cost/trigger grammar blocked (2136 cards sole-blocked by layers).
- Argentum: immutable pure-state fail-closed broad engine (~13.9k card names, 22 enumerators, mandatory-principal visibility, SplitMix64). Terminal: 18/29 frozen MISSING (all 4 Partner commanders + OVERLOAD/split gaps); Partner init hard-block (`GameInitializer.kt:38-44`); OVERLOAD absent; replacement non-draw parity partial; Slot-only snapshot (not clean-process replay); gym→ai coupling.
- Comparative: Argentum leads 5-0 on SUPPORTED but is terminally blocked on Partner-commander init; Quorune leads on Partner-family + replay design but has zero behavior tests. Neither meets hard gates (no material blocker + denominator support + next-step plan).
- Comparator context only: XMage 2P-5P qualified at WS215 (replay pending WS218); Forge WS217 divided-allocation + new Core pin (replay unqualified). No reruns, no mutations.

## Changes

- ONLY under `research/candidate-freshness/ws219/**` (+ state file): 22 outputs + 2 probe scripts. No production code, no manifests, no configs, no candidate files modified. Full file list in Outputs.

## Tests / Evidence

- No candidate suite executed (honest NOT_RUN). Inventory: Quorune 343 test files / 266 quorune modules; Argentum 587 rules-engine + 85 game-server + gym/ai + 3528 mtg-sets scenarios.
- DIRECTLY_VERIFIED: source-lock commits/trees, license SHAs, Quorune frontier counts (31623; 8/21 of 29), Argentum card census (13915 names; 11/18 of 29), Argentum Partner gate, preflight/admission fail-closed design, principal-mandatory designs.
- CODE_DERIVED: all architecture/rules/hidden/RNG/replay/legality analyses (no runtime).
- No RUNTIME_VERIFIED behavior claimed. Import/construction gets zero behavior credit. Green-suite ≠ AF gate (no suites run).
- Early-stop evidence: further runtime at these pins would only re-confirm fail-closed residuals, not invent missing lowering/grammar/cards.

## PASS / FAIL / UNKNOWN

- No AF gate PASSES at qualification standard in this workstream (all runtime NOT_RUN by early-stop design).
- Proven material FAIL-closed blockers (design-correct, qualification-terminal): Quorune AF06/AF07; Argentum AF07 (+AF04/AF06/AF08/AF09 consequences).
- All runtime-dependent cells: UNKNOWN (never PASS per policy).

## Remaining Blockers

- Quorune upstream: lower 21 residual frozen cards; 29 behavior tests; close universal layers/replacement/cost/target/trigger/combat gaps; then per-count/MUST/MICRO/HIDDEN/REPLAY campaign.
- Argentum upstream: 18 cardDefs + Partner Phase-4 + OVERLOAD + split wiring; 6 behavior tests; replacement-domain parity; emblems/side-lists; byte-blob clean-process replay; gym→ai seam; then full campaign.
- Both: RSP 1.1 adapter (out of scope here by design); WS218 Tape v1 runtime proof.

## Outputs

`research/candidate-freshness/ws219/`: SOURCE_LOCK.json, REQUIREMENT_LOCK.json, QUORUNE_SOURCE_AUDIT.md, QUORUNE_AF_MATRIX.json, QUORUNE_MICRO_RULES_MATRIX.json, QUORUNE_FROZEN_CARD_MATRIX.json, QUORUNE_MULTIPLAYER_COMMANDER.json, QUORUNE_LEGAL_ACTION_SURFACE.json, QUORUNE_HIDDEN_INFO.json, QUORUNE_RNG_REPLAY.json, QUORUNE_RUNTIME_EVIDENCE.json, QUORUNE_ADMISSION.md, ARGENTUM_SOURCE_AUDIT.md, ARGENTUM_AF_MATRIX.json, ARGENTUM_MICRO_RULES_MATRIX.json, ARGENTUM_FROZEN_CARD_MATRIX.json, ARGENTUM_MULTIPLAYER_COMMANDER.json, ARGENTUM_LEGAL_ACTION_SURFACE.json, ARGENTUM_HIDDEN_INFO.json, ARGENTUM_RNG_REPLAY.json, ARGENTUM_RUNTIME_EVIDENCE.json, ARGENTUM_ADMISSION.md, CROSS_CANDIDATE_MATRIX.json, QUALIFICATION_BURDEN.json, VALIDATION.json, FINAL_HANDOFF.md, probes/ws219_quorune_frontier_check.py, probes/ws219_argentum_card_check.py.

## Dependencies Unblocked

- Coordinator can decide promotion without further measurement at these pins (both DO_NOT_PROMOTE_CURRENT_PIN).
- Any future re-qualification has exact per-card/per-family blocker lists + bounded next-step plans + probe scripts to re-run.

## Exact Next Action

- Coordinator: accept WS219 seal; publish via `safe_push.py` dry-run then actual to `ws219/candidate-freshness-quorune-argentum-20260915` (no raw push, no PR, no merge); do NOT start promoted-candidate implementation from this session.

## Terminal Fields

WS219_CANDIDATE_FRESHNESS: COMPLETE
QUORUNE_SOURCE_LOCK: 64ef65691b2952e29dfb2422687123d3ff5fc1b4
QUORUNE_AF00: DIRECTLY_VERIFIED
QUORUNE_AF01: CODE_DERIVED
QUORUNE_AF02: CODE_DERIVED
QUORUNE_AF03: CODE_DERIVED
QUORUNE_AF04: CODE_DERIVED
QUORUNE_AF05: CODE_DERIVED
QUORUNE_AF06: UNKNOWN
QUORUNE_AF07: UNKNOWN
QUORUNE_AF08: CODE_DERIVED
QUORUNE_AF09: CODE_DERIVED
QUORUNE_AF10: UNKNOWN
QUORUNE_AF11: CODE_DERIVED
QUORUNE_FROZEN_CARD_SUPPORT: 0 SUPPORTED / 20 PARTIAL / 9 MISSING of 29
QUORUNE_ADMISSION: DO_NOT_PROMOTE_CURRENT_PIN
ARGENTUM_SOURCE_LOCK: 3f46367d87c88bcf156a843a9e69fd29e1693872
ARGENTUM_AF00: DIRECTLY_VERIFIED
ARGENTUM_AF01: CODE_DERIVED
ARGENTUM_AF02: CODE_DERIVED
ARGENTUM_AF03: CODE_DERIVED
ARGENTUM_AF04: CODE_DERIVED
ARGENTUM_AF05: CODE_DERIVED
ARGENTUM_AF06: UNKNOWN
ARGENTUM_AF07: UNKNOWN
ARGENTUM_AF08: CODE_DERIVED
ARGENTUM_AF09: CODE_DERIVED
ARGENTUM_AF10: UNKNOWN
ARGENTUM_AF11: CODE_DERIVED
ARGENTUM_FROZEN_CARD_SUPPORT: 5 SUPPORTED / 6 PARTIAL / 18 MISSING of 29
ARGENTUM_ADMISSION: DO_NOT_PROMOTE_CURRENT_PIN
RECOMMENDED_NEXT_CANDIDATE_ACTION: DO_NOT_PROMOTE either candidate at current pins; no bounded followup spend justified — require upstream implementation per admission plans before any re-qualification.
PRODUCTION_CODE_MODIFIED: NO
QUALIFICATION_MANIFEST_MODIFIED: NO
RAW_GIT_PUSH_USED: NO
ARCHITECTURE_FREEZE: NOT_CLAIMED
PRODUCTION_PROVIDER: NOT_SELECTED
