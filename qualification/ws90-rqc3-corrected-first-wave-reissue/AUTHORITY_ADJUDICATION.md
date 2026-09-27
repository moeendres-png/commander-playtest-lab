# WS90 Authority Adjudication (persisted read-first XHIGH findings)

Status: binding WS90 adjudication input. Read-only `foundry-adjudicator` at XHIGH completed before edits (`PASS` for adjudication completeness). This file persists its verdicts. It grants zero behavior credit and executes no candidate.

Evidence classes: branch/HEAD identity `DIRECTLY_VERIFIED`; file/commit/blob reads `CODE_DERIVED` as provenance; WS79 Rules text `EXTERNALLY_RULE_VALIDATED` as text provenance only; corrected authority binding `TECHNICALLY_CONFORMANT` where proven; missing behavior `NOT_RUN`/`UNKNOWN` (never upgraded).

## 1. Denominator

Historical denominator is exactly `A03 A04 B01 C01 C03 D06 E01 E02 F01 G02 G03 G04 H01 I01 J02` (15). Verified via `RQ_C3_FIRST_WAVE_EXECUTION_PACK.json` scenario IDs, `RQ_C3_FINAL_REPORT.md:71-73`, `validate_rqc3.py FW_EXPECTED`, `WS60_FINAL_REPORT.md:11`, and WS79 provenance blobs `0db015ff…` / `3707d896…`. No substitution, no REMAINING92, no 107.

## 2. Invalidated H01 fields

Six interlocked fields superseded: `expected_rules_events` step 2 (`COPY_CHOICE` under pre-existing Humility), `external_decision_script` copy-choices entry (`all battlefield creatures offered`), `authority_provenance.rules` (`613.1a/f/g, 613.4b, 613.7, 707.2` without `CR 614.12/614.12a`), both `assertion_authority` rows (`1/1 with no abilities` as sufficient oracle), `semantic_objective` framing (layering before applicability), and the `decision_kinds` union contribution for the HUMILITY_FIRST ordering. The visible `1/1 with no abilities` fact remains true but non-discriminating alone.

## 3. Unaffected 14

All except H01: `A03 A04 B01 C01 C03 D06 E01 E02 F01 G02 G03 G04 I01 J02`. `H01_IMPACT_LEDGER.json` (`HIST-RQC3-VALIDATOR` UNAFFECTED, `WS60-AGGREGATE-14-15`, `WS73-RQC3-PRESERVATION`, `MAIN-CROSS-CANDIDATE-MATRIX` UNAFFECTED) and `H01_RULES_ADJUDICATION.md:161-165` confirm no H01-rule (`614.12`) coupling in their oracles. B01 has a separate WS66 fixture defect (absolute `42/41/41/41` unsatisfiable; relative-delta correction required) independent of H01 and out-of-scope for WS90 drift.

## 4. Byte-equivalence

The 14 semantic bodies are preserved byte-equivalently (full-object canonical JSON equality). Pack-level bytes necessarily change (new schema, `reissue_provenance`, H01 replacement, manifest reseal, engine pin `7135d5e→cfc36f` pointer). Those are provenance-only normalizations outside the 14 semantic bodies, proven separate by per-field fingerprints in `NON_H01_EQUIVALENCE.json`. Historical files themselves immutable.

## 5. One H01 slot

Corrected H01 remains exactly one First-Wave slot (denominator stays 15). Removing (14) or splitting (17) would violate the no-substitution contract without Coordinator re-authorization (none exists). Slot oracle is the family `HUMILITY_FIRST (binding) + CLONE_FIRST (control) + NO_HUMILITY (control)`.

## 6. Required subcases

All three WS79 cases required. A alone is non-discriminating under Humility. A: no copy offered/taken, Clone-as-Clone `1/1`, post-Humility printed `0/0` SBA death (`704.5f`), falsify on any copy or post-Humility `2/2` Bear. B: copy offered/taken (Bear), `1/1` under later Humility with Bear underneath, post-Humility `2/2` retained, falsify on missing copy or identity loss. C: normal copy (default Bear), falsify on suppression or non-copy `0/0` entry. No fourth case.

## 7. Required decision kinds

Positive union remains 20 IFF the slot includes B/C as required executions; H01-A contributes a negative (`MUST-NOT-OCCUR`) requirement, not a positive union member. A-only slot would fall to 19. All other 19 kinds unchanged; no `may`/generic ordering/DAO. `trigger ordering [B01]` remains required (B01 UNKNOWN is incompleteness, not removal).

## 8. Copy choices carrier

No other scenario provides `copy choices` (historical union sole carrier `H01`; census of all `per_scenario` confirms). It remains in the positive union if and only if an H01 control (B and/or C) is a required execution. WS90 implements the family slot, so `copy choices: carriers [RQ-C3-H01]` with provenance `via H01-B/C only`.

## 9. Pure test harness

The 13 `Ws60*.java` files under `engine-bridge/src/test/` are pure test harness (no production JAR path): `Ws60Checks, Ws60Decks, Ws60Driver, Ws60EventTape, Ws60Pilot, Ws60Rqc3FirstWaveTest, Ws60Scenarios, Ws60Scenarios2, Ws60Scenarios3, Ws60Scenarios4, Ws60Scenarios5, Ws60Suite, Ws60Views`.

## 10. Production deltas

Exactly 4 files under `engine-bridge/src/main/.../xmage/` altered on WS60 branch: `XmageDecisionOptionIdentity.java`, `XmageFullGameDecisionController.java`, `XmageFullGamePlayer.java`, `XmageKnowledgeLedger.java` (commits `ef9e2005`, `4857b4f4`, `4e0d068d`). No `mage/` engine edits.

## 11. Per-delta classification

None `CURRENTLY_PRESENT`; none `ALREADY_SUPERSEDED` by an equivalent current-main capability (grep `granted_library|lookOwner|commanderStatus|redactObjectIds|stablePermanentOrder` on HEAD: zero hits except `stableId`); each `STILL_REQUIRED_FOR_EXECUTION` as functionality (verbatim restore forbidden without requalification on `cfc36f`); none `UNSAFE_LEGACY` (read-only projections, no Rules reconstruction); none `UNKNOWN`. Details in `WS60_HARNESS_IMPACT.json` (D1–D5).

## 12. Current bridge sufficiency

NO. WS88 `VALIDATION.json:capability_truth {legal_actions_supported false, action_submission_supported false}` and `config/rules_engines.json:missing_required_capabilities [legal_actions_supported, action_submission_supported]` with truth boundary `target, mode, choice and combat classes are incomplete` prove the integrated bridge is a B4-D lifecycle bridge, not a full First-Wave executor. Fresh First-Wave execution on `cfc36f` is `NOT_RUN`.

## 13. Missing classes

Every First-Wave class beyond bounded targetless/nonmodal + pass is missing as qualified capability: `targets, modes, choice-family (copy choices, generic choice), hidden-zone selection/search, attackers/defender per attacker/blockers/combat damage assignment (full combat), X announcement, replacement/trigger ordering, activate, alternate cost, mana payment/source (beyond bounded bills), Commander movement, concession (scripted loss is harness, not qualified submission)`, and globally complete `cast` (only bounded targetless/nonmodal + Rograkh proven). Only bounded `pass` has qualified submission.

## 14. Rules-Core legal decisions

YES as architecture (`XmageFullGamePlayer.java:50-60` hand-to-controller-or-fail-closed; `XmageFullGameDecisionController.java:13-19` only engine-supplied option IDs; `FULL_GAME_FAIL_CLOSED PASS`, `PRODUCTION_REACHABLE_DEFAULT_DECISIONS 0`, `PILOT_RULES_LOGIC 0`); UNKNOWN as instantiated qualification on `cfc36f` for the corrected H01 family (`full_cr61412_future_state_support UNKNOWN`; engine-internal `WS81H01CorrectedTest` proves engine behavior, not bridge-executed First-Wave with external decisions, hidden-info scoping, RNG journaling, twin replay).

## 15. Pilot legality

NO reconstruction. `Ws60Pilot.java:14-20` (only frame + entitled `pilot_state`; never live engine objects; never outside offered set) + `:1793 PilotGapException` (unmapped choice fails closed) + `0 out-of-option over 73548 frames` + production comments (`engine alone selected eligible set`). Scenario bindings gate WHEN, never WHAT IS legal. No `sa.resolve()`, `AbilitySub`, first/random-option, default yes/no, or AI substitutes. Full 10-item audit in `WS60_HARNESS_IMPACT.json` (all absent).

## 16. Reusable techniques (not transferable evidence)

Hidden-info: per-viewer scoping, grant window, `known-library-empty` + `composition-memory-owner-only`, global confinement, cost-text leak inspection, `structuralPrivacy` captures, planted-negative `NOT_RUN` discipline. Replay: twin same-seed re-execution, normalized-log equality (`H01 0 divergences 3632/3632`), event-tape multiset equality, terminal views equality + replica re-evaluation, explicit seed authority, UUID policy, content-ordered sequencing. All bound to `audit_head 2c30040f`, engine `7135d5e`, old oracle; zero rows transfer (`H01 INVALIDATED_BY_ORACLE_CHANGE`; aggregates `REQUALIFICATION_REQUIRED`).

## 17. Forge inputs from WS89

UNKNOWN. No WS89 package on main (`git ls-tree HEAD -- qualification/ | grep ws89|forge` only `evidence/candidates/forge.json`; `Glob **/*WS89*` none; Forge `BLOCKED_ORACLE_AND_BYTE_EXACT_CR`, `RUNTIME_NOT_RUN`, `PROTOCOL_ADAPTER_MISSING`, `DIRECT_PILOT_BOUNDARY_FAIL`). Generic prerequisites stated in `FORGE_EXECUTION_READINESS.md`; exact WS89 deliverables not invented.

## 18. Architecture gate

None triggered; none claimed. `architecture_freeze NOT_CLAIMED`, `production_provider NOT_SELECTED`, `first_wave_current_ranking INVALID_PENDING_REQUALIFICATION`, `behavior_credit_change 0`, `HISTORICAL_EVIDENCE_REWRITTEN NO`, `provider_decision NO_PROVIDER_READY`. No Freeze/Provider/evidence-policy/scope/Rules-boundary change in WS90. Straying into those opens an `AUTHORITY_GATE` to Sol High per `AGENTS.md §8`.

## Technical adjudication (persisted for state)

- `root_cause_class: FIXTURE_DEFECT` (old H01 oracle fixture + assertion authority + union entry encoded Rules-incorrect `COPY_CHOICE` and non-discriminating terminal; not engine/provider/harness/pipeline/infra defect).
- `first_failing_boundary: HISTORICAL_ORACLE_BOUNDARY — RQ-C3-H01 COPY_CHOICE applicability (CR 614.12 with pre-existing Humility)`; downstream blocking boundary `B4-D legal_actions/action_submission` on `cfc36f`.
- `AUTHORITY_REMEDIATION PASS; BEHAVIOR UNKNOWN (INVALID_PENDING_REQUALIFICATION, FULL107 NOT_RUN)`.
- `H01 oracle defect SHARED (provider-neutral); execution gaps PROVIDER_SPECIFIC`.
- `minimal_repair_surface: (1) H01 A/B/C reissue + discriminator; (2) union/validator recomputation; (3) B01 WS66 provenance; (4) D1–D5 re-implementation on cfc36f (no cherry-pick, no engine edits); (5) fresh twin execution + audits; (6) Forge only after WS89`.
- `repair_priority: P0 H01+union/validator; P1 bridge D1–D4 + B01 provenance; P2 twin execution + audits; P3 Forge/Full107 (blocked on WS89 + P2)`.
- `hypotheses_rejected: [current-bridge-sufficient, pilot-reconstructs-legality, second-copy-carrier-exists, denominator-change-needed]`.
- `AUTHORITY_GATE: []`.
