# WS232 Final Handoff — Retention Predicates & N-Scoped Requalification (S8)

Terminal machine status target: COMPLETE (set in state file at publication).

## Source Lock

Repo moeendres-png/commander-playtest-lab, branch
ws232/xmage-retention-nscoped-requalification-20260915. Audit base WS229
6e3fd950 / tree 819103b8 (verified at entry; unchanged throughout — the
Coordinator addendum's independently advanced `main` was explicitly NOT
adopted: no rebase, no base refresh). Engine pin XMage 1.4.61 /
db134b9737e951367d65ef5806ad986319cc73ab / protocol 2.0.0. Replay tape
schema semantic-replay-tape/1.0.0. G01 authority inherited sealed.
ARCHITECTURE_FREEZE = NOT_CLAIMED. PRODUCTION_PROVIDER = NOT_SELECTED.
Full detail: SOURCE_LOCK.md/json + INPUT_AUTHORITY_MATRIX.json.

## Work Completed

- Entry derivation gate: 135 = 72/47/16/0 recomputed from source
  (29/13/5 retained partition; 141 N-scoped cells; 16 S9 UNKNOWNs) —
  no SOURCE_AUTHORITY_DRIFT (WORKLOAD_DERIVATION.json).
- S8 contract reconstructed from the WS220 successor source
  (S8_CONTRACT_RECONSTRUCTION.md).
- 47 machine retention predicates (RETENTION_PREDICATE_SCHEMA/PREDICATES/
  RESULTS): 47/47 STATIC_PASS, behavior discharge joined per N cell,
  6/6 predicate unit tests green.
- N-scoped runtime through the unmodified Rules Core (1457 fresh-process
  games, PROCESS_ISOLATION_PLAN.md, test-only spotlight runner):
  actual-card 79/87 PASS (8 structural UNKNOWNs), micro 27/39
  (12 UNKNOWNs: copy/control/prevention structural, layers order-pair
  absent), replay/RNG 15/15 (record + dual replay per N).
- WS229 U5 closed: card-driven amount (Damnations exact-X), joint
  multi_amount (Gearhulk single-frame [4]), card-driven target_amount
  (Arc divide + companion), numeric-bearing replay (Arc tape dual PASS),
  5P post-WS229 impact GREEN.
- Successor disposition sealed (N_SCOPED_DISPOSITION 121/20; matrices;
  UNKNOWN_16 preserved); standing NO_CHANGE (generator-proven); manifest
  integrity GREEN; privacy intact; Rules authority solely XMage.

## New Findings

1. Integer.MAX_VALUE anchor re-observed card-driven (Blaze/Finale
   announce [0, 2^31-1]); O(1) range handling load-bearing in practice.
2. Paid-X fizzle dynamics: deterministic benefit-MAX is unpayable;
   resolution-bounded X discipline (lawful cap 4) yields resolving
   divides/damage. Pre-existing pilot-economy dynamics, stash-consistent.
3. Look-then-bottom pilot-domain gap (Dig): hand-domain bottom answers
   fail closed on looked-card bottoms (FINDING_PILOT_BOTTOM_GAP.md).
   Not a Rules defect; chartered below, not fixed here (boundary).
4. Last-tap payment wall (5-6-mana spells abort with an untapped source
   unoffered) and even-divide impls (Fireball/Fall need no discretionary
   divide): documented observations; Arc Lightning is the clean
   target_amount vehicle.
5. Sequential-distribute impls (Travel Preparations/Common Bond/Hunger)
   never touch the joint path; Gearhulk does. Card text does not imply
   the Rules-Core path — only runtime proves it.
6. Elesh application without kill-window; Gideon 6/6 type-application;
   Sovereign ETB-tapped: three distinct continuous-effect evidences.

## Changes

- New namespace `qualification/ws232-retention-nscoped-requalification/**`
  (evidence, matrices, tapes, runs, test-only tooling, docs).
- `tests/qualification/test_ws232_retention_predicates.py` (6 tests).
- `WS17_SHA256SUMS` + `qualification/SHA256SUMS` refreshed (same-commit).
- NO `src/**`, engine-bridge production, standing-input, historical-seal,
  or `tools/foundry/*` change (addendum tooling work explicitly untouched).

## Tests / Evidence (classifications)

- DIRECTLY_VERIFIED: all runtime above (exact pointers in matrices/index).
- CODE_DERIVED: authority proofs (importer enforcement, getPlayable
  bytecode shape, bottom-domain read, joint lattice).
- SYNTHETIC: none. UNKNOWN: 20 disposition cells + 16 S9 rows (honest
  terminals with causes). FULL107: NOT_RUN.

## PASS / FAIL / UNKNOWN

- S8 hard gates 1-26: met (see VALIDATION.md; gate-by-gate below).
- Disposition: 121 PASS / 20 UNKNOWN. S8 qualification verdict: PASS
  (Semantic Completion: every required cell terminally classified with
  adequate evidence; UNKNOWNs explicit, none silent).
- No production FAILs (no Rules-semantics defect found; the bottom gap
  is a fail-closed pilot limitation, not a semantic FAIL).

## Remaining Blockers

None for WS232 scope. Successor scope (S9 + pilot-domain remediation):
pilot bottom-domain fix (looked-card bottoms); layer-order pair scenarios
if S9 wants MICRO_LAYERS runtime; trigger-rich closers for the 16 S9
UNKNOWNs. No S9 work starts here.

## Outputs

SOURCE_LOCK, INPUT_AUTHORITY_MATRIX, S8_CONTRACT_RECONSTRUCTION,
WORKLOAD_DERIVATION, RETENTION_PREDICATE_SCHEMA/PREDICATES/RESULTS,
N_SCOPED_DISPOSITION/SUMMARY, ACTUAL_CARD_29_MATRIX, MICRO_RULE_13_MATRIX,
REPLAY_RNG_5_MATRIX, PROCESS_ISOLATION_PLAN, RUNTIME_RUN_INDEX,
U5_AMOUNT/MULTI/TARGET_CARD_DRIVEN (+json), NUMERIC_REPLAY (+json),
CARDINALITY_IMPACT, FINDING_PILOT_BOTTOM_GAP, UNKNOWN_16_PRESERVATION,
HIDDEN_INFO_IMPACT, RULES_AUTHORITY_AUDIT, STANDING_IMPACT (+json),
MANIFEST_INTEGRITY, VALIDATION, EVIDENCE_SEAL, FINAL_HANDOFF.

## Dependencies Unblocked

S9 depends on S8: use the terminal WS232 HEAD/TREE in this handoff plus
N_SCOPED_DISPOSITION (20 open N-cells) + UNKNOWN_16 + bottom-gap note.

## Exact Next Action

Final validation -> final focused commit(s) -> state COMPLETE +
validated_head -> clean worktree -> safe_push dry-run -> safe_push ->
fetch/prune -> HEAD/TREE equality -> handoff -> terminate (same writer
session). No raw push. No PR. No merge. No main mutation.

## Terminal fields

WS232_S8_RETENTION_NSCOPED = COMPLETE
SOURCE_LOCK = ws232/xmage-retention-nscoped-requalification-20260915 @ 6e3fd950
COMMON_FIXTURE_TOTAL = 135
RETAINED_TOTAL = 47
RETAINED_ACTUAL_CARD = 29
RETAINED_MICRO_RULE = 13
RETAINED_REPLAY_RNG = 5
RETENTION_PREDICATES = 47/47 STATIC_PASS (+ N-scoped discharge)
N_SCOPED_2P = 40 PASS / 7 UNKNOWN
N_SCOPED_3P = 40 PASS / 7 UNKNOWN
N_SCOPED_5P = 41 PASS / 6 UNKNOWN
ACTUAL_CARD_29 = 79 PASS / 8 UNKNOWN (cells: 87)
MICRO_RULE_13 = 27 PASS / 12 UNKNOWN (cells: 39)
REPLAY_RNG_5 = 15 PASS / 0 UNKNOWN (cells: 15)
U5_AMOUNT_CARD_DRIVEN = CLOSED_PASS (Damnations exact-X resolution)
U5_MULTI_AMOUNT_CARD_DRIVEN = CLOSED_PASS (Gearhulk single-frame [4])
U5_TARGET_AMOUNT_CARD_DRIVEN = CLOSED_PASS (Arc divide + companion)
NUMERIC_BEARING_REPLAY = CLOSED_PASS (Arc tape 502 steps, dual PASS)
POST_WS229_5P = GREEN
UNKNOWN_16_PRESERVED = TRUE (S9 set intact)
S8_VERDICT = PASS (Semantic Completion; 20 explicit UNKNOWNs)
RULES_AUTHORITY = XMAGE_ONLY
HIDDEN_INFORMATION = INTACT (0 findings namespace-wide)
PROCESS_ISOLATION = FRESH_PROCESS_PER_GAME (bridge-enforced)
MANIFEST_INTEGRITY = GREEN
STANDING_IMPACT = NO_CHANGE (generator-proven)
BEHAVIOR_CREDIT_CHANGE = NONE
FULL107 = NOT_RUN
RAW_GIT_PUSH_USED = NO
ARCHITECTURE_FREEZE = NOT_CLAIMED
PRODUCTION_PROVIDER = NOT_SELECTED
PENDING_SOURCE_LOCK_HARDENING_IMPACT = NONE
(Justification: WS232's lock was verified from local git state at entry
and never rebased/refreshed; no evidence was produced or consumed through
tools/foundry/source_lock.py — no live-remote fallback, ref/OID parsing,
or URL-rewrite path was exercised; publication uses blob-verified
safe_push.py only. The pending hardening therefore cannot reinterpret any
WS232 publication evidence.)
