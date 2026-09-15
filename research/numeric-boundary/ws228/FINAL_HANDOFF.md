# WS228 Final Handoff — Numeric Decision Boundary Preflight

Terminal machine status target: COMPLETE (set in state file at publication).
Research-only workstream: NO production changes; F-RULES-02 stays OPEN;
no behavior credit claimed.

## Source Lock

Repo moeendres-png/commander-playtest-lab, branch
ws228/numeric-boundary-preflight-20260915. Audit base WS223
48885e8e / tree d02d6c0e. Read-only inputs: WS220 1a6ffcda (F-RULES-02/S6
authority, reconstructed from source), WS225 8b3ab80d (standing context),
WS226 terminal fb156d2b / tree 52359f47 (post-lock, fetched + identity
verified, delta-revalidated). Engine pin XMage 1.4.61. ARCHITECTURE_FREEZE
= NOT_CLAIMED; PRODUCTION_PROVIDER = NOT_SELECTED. Full detail:
SOURCE_LOCK.md + INPUT_AUTHORITY_MATRIX.json.

## Work Completed

- Reconstructed F-RULES-02 + S6 from WS220 source (not summaries).
- Traced numeric decisions end to end (Core -> callback -> bridge context
  -> protocol frame -> Lab routing -> pilot views -> native submission),
  per-transition authority/fields/bounds/validation/failure
  (NUMERIC_DOMAIN_TRACE.json). First narrowing proven: full_game.py:750-754.
- Proved Core-authorized domain model from pinned engine bytecode:
  announce_x/amount accept ANY int in [min,max] (HumanPlayer accept loops);
  multi_amount is a joint lattice (isGoodValues); bridge sequentializer
  proven feasibility-preserving (DOMAIN_AUTHORITY_ANALYSIS.md).
- Inventoried callsites: 1 shared chooser, 2 invocation sites, 4 classes
  (NUMERIC_CALLSITE_INVENTORY.json). Classified multi_amount's joint→
  sequential gap separately (F-RULES-02b, structural, not legality-breaking).
- Reproduced the defect with a research-only probe: span<=16 full,
  span>=17 {min,mid,max}, boundary 16/17 exact, all 4 classes
  (F_RULES_02_REPRODUCTION.md + LIVE_PROBE_RESULTS.json, 32 cases green).
- Produced the canonical 17-class matrix (incl ability->choice mapping,
  F-RULES-03 five narrowings placed) + evidence gaps (no fabricated
  runtime proof).
- Evaluated 4 design families; chose B (range-native pilot decision) with
  explicit no-second-engine argument, neutrality, replay mapping (no
  schema change for scalars), O(1) performance disposition.
- Produced implementation-ready S6 positive (6) + negative (23) matrices,
  test plan, blueprint, and the S6 entry contract on base fb156d2b.
- Executed the WS226 delta contract: 14/14 material paths byte-identical
  (DELTA_REVALIDATION_PASS); coordinator's numeric fact independently
  confirmed; retention predicates designed for S6 entry.

## New Findings

1. F-RULES-02 reproduced EXACTLY as chartered (boundary 16/17, 4 classes).
2. Bridge + projection are lossless/fail-closed already — Lab is the only
   narrowing point; S6 needs no bridge change for scalars.
3. Native multi_amount is JOINT while the bridge sequentializes
   (F-RULES-02b) — S6 restores the joint pilot-facing shape.
4. Pilot shortlist (3-8) would silently re-narrow full enumeration at the
   ranking stage — one reason B is preferred over A.
5. `ability` is not a decision class (choice with choice_domain) — S6
   negative matrix covers it via choice rows.
6. Replay tape already has the needed numeric fields — S6 adds at most one
   typed vector field under WS218 versioning.

## Changes

- Added research/numeric-boundary/ws228/** only: 19 output files +
  probes/numeric_boundary_probe.py. Zero modifications elsewhere
  (verified by git status/diff).

## Tests / Evidence (classifications)

- SYNTHETIC probe: 32/32 verdicts green (F_RULES_02_REPRODUCED=true).
- DIRECTLY_VERIFIED: pytest matrix 20 passed; full_game 7 passed; JVM
  boundary 4/4; JVM projection 17/17 (incl live-cited negative rows).
- CODE_DERIVED: bytecode accept-loop + joint-lattice proofs; full trace.
- UNKNOWN (honest, S6-owned): actual-card live firing; maxima
  distribution (U1); joint transport (U4); cheapest-reach scenarios (U5).

## PASS / FAIL / UNKNOWN

- PREFLIGHT_COMPLETE: PASS. LIVE_DEFECT_REPRODUCED: PASS.
  DESIGN_READY: PASS. DELTA_REVALIDATION_PASS: PASS.
- F_RULES_02_FIXED / S6_PASS / behavior credit: NOT CLAIMED (explicitly
  out of scope; production unchanged).

## Remaining Blockers

None for preflight. S6 entry requires retention predicates green on base
fb156d2b (expected green — all NO_IMPACT).

## Outputs

research/numeric-boundary/ws228/: SOURCE_LOCK.md,
INPUT_AUTHORITY_MATRIX.json, F_RULES_02_REPRODUCTION.md,
NUMERIC_DOMAIN_TRACE.json, NUMERIC_CALLSITE_INVENTORY.json,
DECISION_CLASS_MATRIX.json, CURRENT_EVIDENCE_GAPS.json, LIVE_PROBE_PLAN.md,
LIVE_PROBE_RESULTS.json, DOMAIN_AUTHORITY_ANALYSIS.md, DESIGN_OPTIONS.md,
CHOSEN_DESIGN.md, PROVIDER_NEUTRALITY.md, REPLAY_IMPACT.md,
PERFORMANCE_BOUNDARY.md, POSITIVE_MATRIX.json, NEGATIVE_MATRIX.json,
S6_TEST_PLAN.md, S6_IMPLEMENTATION_BLUEPRINT.md,
WS226_DELTA_REVALIDATION.json, RETENTION_PREDICATES.json, VALIDATION.md,
FINAL_HANDOFF.md + probes/numeric_boundary_probe.py.

## Dependencies Unblocked

S6 (Numeric disposition + per-class live negatives) is unblocked with an
implementation-ready contract on base fb156d2b; S8 retention has machine
predicates; no other workstream is blocked or touched.

## Exact Next Action

S6 successor: start from S6_BASE fb156d2b, run RETENTION_PREDICATES.json
(R1-R7); on all-green implement H1-H7 per S6_IMPLEMENTATION_BLUEPRINT.md,
gated by POSITIVE_MATRIX.json + NEGATIVE_MATRIX.json; see S6_TEST_PLAN.md
for runs/evidence/cost. U4 joint-transport spike first if it affects H6.

## Terminal fields

WS228_NUMERIC_BOUNDARY_PREFLIGHT = COMPLETE
F_RULES_02_REPRODUCED = YES (probe-level; defect OPEN until S6)
FIRST_NARROWING_LOCATION = src/commander_lab/engine/rules/full_game.py:750-754 (_decide_numeric values construction)
CORE_AUTHORIZED_DOMAIN_MODEL = contiguous-inclusive-int-interval [min,max] unit-stride (announce_x/amount/companions); joint lattice legs+totals (multi_amount)
ANNOUNCE_X_STATUS = DEFECT_REPRODUCED (PARTIAL: small ok, span>16 narrowed)
AMOUNT_STATUS = DEFECT_REPRODUCED (same)
MULTI_AMOUNT_STATUS = DEFECT_REPRODUCED + F-RULES-02b structural (joint→sequential, feasibility-preserving)
NUMERIC_CALLSITE_COUNT = 1 chooser / 2 invocations / 4 classes
DECISION_CLASS_MATRIX = 17 classes sealed
LIVE_DEFECT_PROOF = LIVE_PROBE_RESULTS.json (32 cases) + VALIDATION.md runs
CHOSEN_DESIGN = B range-native pilot decision (descriptor + choose_number(s) + membership validation)
NO_SECOND_RULES_ENGINE = ARGUED (projection-of-authoritative-interval; DOMAIN_AUTHORITY_ANALYSIS.md)
PROVIDER_NEUTRALITY = PRESERVED (ints/descriptors only; checklist in PROVIDER_NEUTRALITY.md)
REPLAY_DESIGN_COMPATIBILITY = COMPATIBLE (fields exist; vector field at most; versioned)
LARGE_DOMAIN_DISPOSITION = O(1) by design; no cap; U1 distribution collected in S6
S6_POSITIVE_MATRIX_READY = YES (6 cases)
S6_NEGATIVE_MATRIX_READY = YES (23 cases)
S6_IMPLEMENTATION_BLUEPRINT = SEALED (H1-H7 on base fb156d2b)
WS226_DELTA_REVALIDATION_REQUIRED = EXECUTED_PASS (14/14 NO_IMPACT; predicates sealed for S6 entry)
PRODUCTION_CODE_MODIFIED = NO
RULES_SEMANTICS_CHANGED = NO
BEHAVIOR_CREDIT_CHANGE = 0
FULL107 = NOT_RUN
RAW_GIT_PUSH_USED = NO (safe_push only)
ARCHITECTURE_FREEZE = NOT_CLAIMED
PRODUCTION_PROVIDER = NOT_SELECTED
