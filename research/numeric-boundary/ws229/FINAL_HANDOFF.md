# WS229 Final Handoff — Numeric Decision Boundary Remediation & S6 Qualification

Terminal machine status target: COMPLETE (set in state file at publication).
F-RULES-02 and F-RULES-02b are CLOSED by this workstream; all five
F-RULES-03 findings are dispositioned. Behavior credit only for executed
rows (see matrices); nothing promoted by fiat.

## Source Lock

Repo moeendres-png/commander-playtest-lab, branch
ws229/xmage-numeric-decision-boundary-20260915. Audit base WS226
fb156d2b / tree 52359f47. Read-only authority WS228 25051fa4 / tree
ef56cede (consumed via local object store, never entered). Engine pin
XMage 1.4.61. ARCHITECTURE_FREEZE = NOT_CLAIMED; PRODUCTION_PROVIDER =
NOT_SELECTED. Full detail: SOURCE_LOCK.md + INPUT_AUTHORITY_MATRIX.json.

## Work Completed

- Entry gate R1-R7: 7/7 GREEN on exact WS226 bytes; WS228 retained
  (S6_ENTRY_GATE.json).
- U4 spike first: joint-frame transport required (sequential shim
  rejected on authority grounds); native isGoodValues gate identified
  (U4_SPIKE.md).
- H1-H7 implemented per the sealed blueprint: range-native scalar
  descriptors, joint vector multi_amount, BasePilot fail-closed numeric
  defaults + concrete strategies, replay vector extension under the
  existing schema, joint bridge transport (controller/player/projection),
  five F-RULES-03 dispositions, prompt-text sniffing deleted.
- Positive matrix executed (5 PASS + 1 PARTIAL with pinned blocker);
  N-01..N-23 executed (23/23 PASS); honest 17-class matrix sealed.
- Live evidence: announce_x/amount incl span>16 + card-driven MAX_VALUE
  fire; joint with binding total (single-frame proof); target_amount
  companion qualified, card-driven fire UNKNOWN (pinned blocker).
- Impact regressions green: replay digest stability, hidden-info +
  name-canary suites, cardinality (JVM lifecycle + 2P/3P live smokes +
  6P fail-closed), manifest integrity GREEN, standing NO_CHANGE.
- Pre-existing post-cancel activation dynamics proven identical on base
  (stash experiment) — not a WS229 effect.

## New Findings

1. The engine emits max=Integer.MAX_VALUE for X-spells (card-driven
   observation) — the U1 pathological case is real, and O(1) handling
   is therefore load-bearing, not theoretical.
2. Controller transport accepted scalar numbers on boundless frames and
   truncated fractional numerics; both now fail closed (N-22 lane,
   strict-int lanes) — found while executing the matrix, fixed in scope.
3. `putCardsOnBottomOfLibrary` provably funnels through
   `choose(Outcome, Cards, TargetCard, ...)` (pinned bytecode) — the
   structured bottom flag rests on callback identity, not text.
4. Native `MultiAmountType.isGoodValues` takes original messages — the
   joint frame is gated natively with zero coupled-bounds arithmetic left.
5. Targeted bottom prompts (tuck choices) now rank generically instead of
   taking the bottom-card path — intended correction, documented.

## Changes

- `src/commander_lab/engine/rules/full_game.py` (numeric descriptor +
  joint paths, F-RULES-03 Lab dispositions, membership hardening),
  `src/commander_lab/agents/pilots.py` (fail-closed Base defaults +
  concrete strategies), `src/commander_lab/semantic_replay/*` (vector
  extension, recorder/consumer, conditional digest binding),
  `engine-bridge/.../XmageFullGame{Player,DecisionController,ActionProjection}.java`
  (joint transport, forced-move records, bottom flag, strict ints),
  five full-game test drivers (joint answers), rewritten combat-damage
  tests, one migrated matrix row (scalar multi -> joint contract).
- New suites: `XmageNumericDomainWs229Test` (12),
  `XmageDecisionRejectionWs229Test` (16),
  `tests/unit/test_ws229_numeric_domain.py` (55).
- Evidence namespace `research/numeric-boundary/ws229/` (27 files,
  incl machine-generated EVIDENCE_SEAL.json).
- No `qualification/**`, standing, manifest, or protocol-version change.

## Tests / Evidence (classifications)

- DIRECTLY_VERIFIED: everything executed above (exact commands/counts in
  VALIDATION.md).
- CODE_DERIVED: authority proofs (bytecode accept loops, joint lattice,
  bottom funnel, requiresNumeric gate, feasibility preservation where
  still referenced).
- SYNTHETIC: none (no probes this workstream; WS228 probe retained).
- UNKNOWN (honest): card-driven amount/multi_amount/target_amount fires;
  4P gate + 5P smoke reruns; WS218 numeric dual-replay positives.
- Historical FULL107: NOT_RUN.

## PASS / FAIL / UNKNOWN

- S6_ENTRY_GATE: PASS. U4_SPIKE: decided (joint transport).
- F-RULES-02: CLOSED. F-RULES-02b: CLOSED. F-RULES-03 (5): DISPOSITIONED.
- POSITIVE matrix: 5 PASS + P-T1 PARTIAL (blocker pinned).
- NEGATIVE matrix: 23/23 PASS.
- REPLAY/HIDDEN_INFO/CARDINALITY/MANIFEST: GREEN. STANDING: NO_CHANGE.
- No numeric-domain narrowing remains; scalar interval lossless; large
  domains O(1); BasePilot numeric fail closed; no clamp/default/fallback;
  Core sole legality authority.

## Remaining Blockers

None for WS229 scope. U5 scenario engineering (card-driven amount/
multi_amount/target_amount fires; 4P/5P rerun appetite; numeric dual-
replay scenarios) is S8 scope with the exact blockers pinned in
TARGET_AMOUNT_LIVE.md and VALIDATION.md.

## Outputs

research/numeric-boundary/ws229/: SOURCE_LOCK.md,
INPUT_AUTHORITY_MATRIX.json, S6_ENTRY_GATE.json, U4_SPIKE.md,
NUMERIC_DOMAIN_CONTRACT.json, SCALAR_IMPLEMENTATION.md,
JOINT_MULTI_AMOUNT_IMPLEMENTATION.md, F_RULES_02_ADJUDICATION.md,
F_RULES_02B_ADJUDICATION.md, F_RULES_03_DISPOSITIONS.md,
DECISION_CLASS_MATRIX_FINAL.json, POSITIVE_MATRIX_RESULTS.json,
NEGATIVE_MATRIX_RESULTS.json, ANNOUNCE_X_LIVE.md, AMOUNT_LIVE.md,
MULTI_AMOUNT_LIVE.md, TARGET_AMOUNT_LIVE.md, LIVE_FRAME_CAPTURES.json,
LARGE_DOMAIN_PERFORMANCE.json, REPLAY_IMPACT.md, HIDDEN_INFO_IMPACT.md,
CARDINALITY_IMPACT.md, MANIFEST_INTEGRITY.md, STANDING_IMPACT.md,
VALIDATION.md, EVIDENCE_SEAL.json (machine-generated via
tools/foundry/evidence.py artifact-index), FINAL_HANDOFF.md.

## Dependencies Unblocked

S6 numeric disposition complete; S8 inherits the U5 blockers + the U1
empirical anchor (MAX_VALUE observed); no other workstream touched.

## Exact Next Action

Final validation -> final commit -> state COMPLETE + validated_head ->
clean worktree -> safe_push dry-run -> safe_push -> fetch/prune ->
HEAD/TREE equality -> handoff -> terminate (same writer session).

## Terminal fields

WS229_NUMERIC_BOUNDARY_S6 = COMPLETE
F_RULES_02 = CLOSED
F_RULES_02B = CLOSED
F_RULES_03_DISPOSITIONS = 5/5 CLOSED
S6_ENTRY_GATE = PASS (R1-R7 7/7)
U4_JOINT_TRANSPORT = IMPLEMENTED (sequentializer deleted)
SCALAR_INTERVAL = LOSSLESS (no narrowing at any span)
LARGE_DOMAIN = O(1) (span 10^9 unit + span 2^31-1 live)
BASEPILOT_NUMERIC = FAIL_CLOSED (choose_number/choose_numbers raise)
CLAMP_DEFAULT_FALLBACK = ABSENT (all invalid returns raise)
ANNOUNCE_X_LIVE = PASS (incl span>16 + card-driven MAX_VALUE fire)
AMOUNT_LIVE = PASS (incl span>16)
MULTI_AMOUNT_LIVE = PASS (joint, binding total, single-frame proof)
TARGET_AMOUNT_LIVE = PARTIAL (companion qualified; card-driven UNKNOWN, blocker pinned)
NEGATIVE_MATRIX = 23/23 PASS (N-01..N-23 executed, no fallback)
DECISION_CLASSES = 17/17 evidenced (ability stays a choice_domain)
REPLAY = GREEN (scalar digests byte-stable; vector extension compatible)
HIDDEN_INFO = GREEN (UUID/name-canary suites pass)
CARDINALITY = GREEN (2P/3P live smokes + lifecycle + 6P fail-closed)
MANIFEST_INTEGRITY = GREEN
STANDING_IMPACT = NO_CHANGE
FULL107 = NOT_RUN
RAW_GIT_PUSH_USED = NO (safe_push only)
ARCHITECTURE_FREEZE = NOT_CLAIMED
PRODUCTION_PROVIDER = NOT_SELECTED
