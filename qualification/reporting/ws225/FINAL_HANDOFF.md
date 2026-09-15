# WS225 Final Handoff — Qualification Standing & Candidate Admission Governance

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws225/qualification-standing-candidate-admission-20260915`
- Audit base: `189dcfc09e74bebbf22172e709b459428b25d583` (tree `4bb67f8c7412b20def4d2c16bc86d5c51426dd62`, terminal published WS221)
- Sibling evidence consumed ONLY by exact pointer (no ancestry claimed):
  WS218 `3cdade1dfb16c820465690680b0b0be8af7007ef`,
  WS219 `077c836d27dd22f359c217d65dc6f300c41b65dc`,
  WS220 `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b` (ancestor line via WS221),
  Forge WS217 `e152688a33bf69a840b74ae86149d881e64538ec` (external repo) +
  Core seam `c4d67145a6f9902e031a11dde5c33c60f51ed08d` (via WS217 seal).
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Work Completed

Objective A — one generated trace model: relational JSON rows
(`FIXTURE_EVIDENCE_TRACE.json`, 652 rows) joining candidate × fixture/gate →
verdict (7-term only) × evidence class (vocab-v1) × runtime status ×
provenance (commit/path/digest) × impact disposition × current/stale.
`G_AF_MAPPING.json` reconstructs the exact G↔AF relation (1:1, many-to-many,
deliberately unmapped with rationale; rejected alternative documented).
`standing_generator.py` is deterministic (same digest on rerun) and
fail-closed: PASS requires every mandatory item PASS + RUNTIME_VERIFIED +
current; UNKNOWN/PARTIAL/NOT_RUN poison gates; PASS-without-runtime demotes
to UNKNOWN; unmapped classes, stale locks, predicate-less retention, and
unsealed cross-branch pointers evaluate to UNKNOWN. BLOCKED is a flag, never
a verdict. Direct-evidence bundles cover the five zero-fixture AF gates
(F-QUAL-01 made explicit). WS17 rollup adjudicated option B (historical;
additive `WS225_ROLLUP_STATUS.json`; sealed bytes untouched). Freeze
readiness is computable per candidate without claiming Freeze. FULL107
investigated: zero normative references in any live contract/schema/test —
historical/regression artifact, NOT_RUN preserved, no deletion, no conflict
to adjudicate (retirement needs Coordinator ratification).

Objective B/C — provider-neutral admission bar (S0–S5 funnel, cheap terminal
blockers), stage contract with machine evaluation rules, H01–H12
harness-porting checklist (de-XMage-shaping review H12), fair-comparison
contract (same treatment; mechanics may differ, standards may not).
WS219 dry run reaches `DO_NOT_PROMOTE_CURRENT_PIN` for both pins for the
sealed WS219 reasons (Quorune S3: 0/29; Argentum S3: 5/29 + Partner/OVERLOAD).
Incumbency-bias test: one code path for all four; XMage is S5-pending (not
admitted — no privilege); Forge terminal S1 (no age exception); AF11 UNKNOWN
for XMage and Forge symmetrically (unselected topology).

## New Findings

- WS219 `REQUIREMENT_LOCK.json` claims fixture_count 175, but the locked
  manifest bytes (sha `e7f34ea4…ca3bd4`, identical then and now) contain 135
  fixtures. Manifest bytes are authority: denominator is 135; the 175 figure
  is not relied upon anywhere in WS225.
- Lab diff 67db0733→189dcfc0 touches no engine/pilot/bridge behavior (sole
  src change is `robustness.py` lane message text; WS221 governance-only),
  which grounds the WS225 retention predicate for all 119 XMage PASS rows.
- F-HIDE-02 (name-blind oracle) coexists with sealed HIDDEN sentinel PASS
  rows; recorded as an improvement note, not an invalidation (WS224-adjacent).
- No published post-lock drift: origin ws218/ws219/ws220/ws221 tips match the
  consumed pointers; ws222/ws223/ws224 have no published remote state.

## Changes

Added (reporting only; no engine/pilot/runtime/CI/G01/hidden-info sources):
`qualification/reporting/ws225/` (36 files: contracts, mapping, join rules,
schemas, generator, overrides/direct-evidence/facts inputs, 4 standings,
trace, freeze view, blockers, G01 status, admission assessments, WS219
dry run, bias test, FULL107 role, WS17 adjudication, drift, validation,
this handoff, 6 narrative companions),
`qualification/aggregate/WS225_ROLLUP_STATUS.json`,
`tests/qualification/test_ws225_standing.py` (26 tests).
Refreshed `WS17_SHA256SUMS` + `qualification/SHA256SUMS` same-commit
(36 new files appended + inner-manifest line; verification green).

## Tests / Evidence

- `tests/qualification/`: 55/55 PASS (26 new WS225 fail-closed/admission/
  symmetry tests + all pre-existing incl. manifest-integrity gate).
- Generator determinism: two independent runs, identical outputs digest
  (`cd9a36407830a1b9…` at seal time; see VALIDATION.json).
- Regeneration test: committed views byte-equal a fresh generator run
  (view/source agreement enforced in CI-testable form).
- Classifications: standings are CODE_DERIVED views over RUNTIME_VERIFIED /
  DIRECTLY_VERIFIED / SOURCE_DERIVED / TECHNICALLY_CONFORMANT sealed inputs;
  no new runtime claimed; no behavior credit changed.

## PASS / FAIL / UNKNOWN

- Generator + full qualification-test directory: PASS.
- XMage current: G02–G09/G11 + AF02–AF07/AF09–AF10 PASS (traced); G01 FAIL;
  G10/AF08 UNKNOWN (16 preserved); G12/AF01/AF11 UNKNOWN; G13 FAIL; G14/G15
  NOT_APPLICABLE. NOT freeze-ready.
- Forge current: AF00 PASS; AF04 FAIL (preserved); AF03/AF10/AF11 UNKNOWN
  (seam-scoped supporting only); fixtures NOT_RUN; replay not Lab-qualified.
- Quorune/Argentum: fixtures NOT_RUN; AF00 PASS; admission DO_NOT_PROMOTE
  (S3 terminal, sealed reasons). No qualification rerun performed or needed.
- G01: FAIL (current; WS222-owned). AF09-XMage-replay: PASS (WS218 tape lane
  2P–5P, explicit scope). FULL107: historical artifact.

## Remaining Blockers

G01 sealed freshness (WS222) · 16 WS05 UNKNOWNs (G10/AF08) · RSP handshake
runtime all candidates (AF01) · production topology selection (G12/AF11) ·
135-fixture RSP campaign all candidates incl. XMage (admission S5) ·
Forge whole-boundary remediation + frozen census + replay proof ·
Quorune/Argentum upstream implementation per WS219 plans · FULL107
retirement ratification (S14/Coordinator).

## Outputs

`qualification/reporting/ws225/`: SOURCE_LOCK, INPUT_AUTHORITY_MATRIX,
CURRENT_LAYER_INVENTORY, G_AF_MAPPING(+md), FIXTURE_EVIDENCE_TRACE,
EVIDENCE_JOIN_CONTRACT, CURRENT_STANDING_SCHEMA, standing_generator.py,
EVIDENCE_OVERRIDES, GATE_DIRECT_EVIDENCE, CANDIDATE_FACTS, XMAGE/FORGE/
QUORUNE/ARGENTUM_STANDING, FREEZE_READINESS_VIEW, OPEN_BLOCKERS, G01_STATUS,
CANDIDATE_ADMISSION_BAR(+md), ADMISSION_STAGE_CONTRACT,
HARNESS_PORTING_CHECKLIST(+md), FAIR_COMPARISON_CONTRACT(+md),
INCUMBENCY_BIAS_TEST, WS219_ADMISSION_DRY_RUN, ADMISSION_ASSESSMENTS,
FULL107_ROLE(+md), WS17_AGGREGATE_ADJUDICATION(+md), POST_LOCK_DRIFT,
VALIDATION, FINAL_HANDOFF (this file); plus
`qualification/aggregate/WS225_ROLLUP_STATUS.json`.

## Dependencies Unblocked

Coordinator: Freeze decision is now mechanically auditable per candidate;
S2 (standing) and S12 (admission bar + checklist) hard gates satisfied
(computed dispositions sealed; bar published; Quorune/Argentum dry run
assessed). Future work: S8 retention format reserved; cheap recompute after
any sibling integration (`standing_generator.py` + manifest refresh).

## Exact Next Action

Final validation → commit → state COMPLETE + validated_head → safe_push
(dry-run then actual) → fetch + verify HEAD/tree/clean → terminate session.

## Terminal Fields

WS225_QUALIFICATION_STANDING_CANDIDATE_ADMISSION: COMPLETE
STANDING_GENERATOR: qualification/reporting/ws225/standing_generator.py (deterministic; digest in VALIDATION.json)
G_AF_TRACE: qualification/reporting/ws225/G_AF_MAPPING.json
FIXTURE_EVIDENCE_TRACE: qualification/reporting/ws225/FIXTURE_EVIDENCE_TRACE.json (652 rows)
EVIDENCE_VOCAB_V1_ENFORCED: YES (generator + 26 tests; harness semantics preserved)
WS17_ROLLUP_STATUS: DEPRECATED_HISTORICAL (option B; living views generated)
FREEZE_READINESS_COMPUTABLE: YES (FREEZE_READINESS_VIEW.json; freeze not claimed)
XMAGE_CURRENT_STANDING: G02-G09/G11 + AF02-AF07/AF09-AF10 PASS; G01 FAIL; G10/AF08 UNKNOWN x16; G13 FAIL
FORGE_CURRENT_STANDING: AF00 PASS; AF04 FAIL preserved; AF03/AF10/AF11 UNKNOWN; COMBAT_ORDER blocked-as-obsolete; replay not Lab-qualified
QUORUNE_CURRENT_STANDING: fixtures NOT_RUN; DO_NOT_PROMOTE_CURRENT_PIN (S3: 0/20/9)
ARGENTUM_CURRENT_STANDING: fixtures NOT_RUN; DO_NOT_PROMOTE_CURRENT_PIN (S3: 5/6/18)
CANDIDATE_ADMISSION_BAR: published (S0-S5; provider-neutral; machine stage contract)
HARNESS_PORTING_CHECKLIST: published (H01-H12 incl. de-XMage-shaping review)
INCUMBENCY_BIAS_CHECK: NO_INCUMBENCY_BIAS_DETECTED (same code path; XMage S5-pending; Forge S1-terminal)
WS219_DRY_RUN: both pins DO_NOT_PROMOTE_CURRENT_PIN for sealed evidence reasons (match=true)
G01_CURRENT_STATUS: FAIL (current; WS222-owned; no unpublished state consumed)
AF09_XMAGE_REPLAY_STATUS: PASS (WS218 tape lane 2P-5P; campaign-scale proof stays with G14)
FULL107_ROLE: HISTORICAL_REGRESSION_ARTIFACT (NOT_RUN preserved; no normative role; no deletion)
POST_LOCK_DRIFT: none published (remotes match consumed pointers; siblings unpublished)
RULES_SEMANTICS_CHANGED: NO
BEHAVIOR_CREDIT_CHANGE: 0
RAW_GIT_PUSH_USED: NO
ARCHITECTURE_FREEZE: NOT_CLAIMED
PRODUCTION_PROVIDER: NOT_SELECTED
