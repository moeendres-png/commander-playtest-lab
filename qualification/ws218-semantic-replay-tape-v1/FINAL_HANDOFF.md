# WS218 FINAL_HANDOFF — Semantic Replay Tape v1

## Source Lock

- Lab `moeendres-png/commander-playtest-lab`, branch
  `ws218/semantic-replay-tape-v1-20260915`, HEAD `67db073367853da7295ae06642f38a73db464dba`
  (tree `a41ad3959caee03db59ffa15bdd44413d58ca766`; audit base unchanged).
- XMage production authority `db134b9737e951367d65ef5806ad986319cc73ab`
  (1.4.61). Forge divided core `c4d67145a6f9902e031a11dde5c33c60f51ed08d`
  (read-only). WS217 `e152688a33bf69a840b74ae86149d881e64538ec` (Forge
  future-consumer reference; replay NOT CLAIMED there).
- Read-only post-lock input: WS220 terminal `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b`
  (tree `6bc707b37f8fb39950f4ade2db11e7ccef03dab6`), consumed via Git
  objects only; branch/worktree/lock unchanged; no rebase.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Work Completed

1. Authority/design matrix from WS213/WS215/session/controller/transcript/
   RNG/observations/protocol/capability/D5/batch/WS217 sources
   (`INPUT_AUTHORITY_MATRIX`, `REPLAY_GAP_MAP`, `IDENTITY_INVENTORY`,
   `DESIGN_OPTIONS`, `CHOSEN_REPLAY_ARCHITECTURE` — Python-side tape over
   the production JSONL lane, no Java changes).
2. Versioned contract `semantic-replay-tape/1.0.0` + canonical `1.0.0` +
   option identity `1.0.0` + state digest `1.0.0` + divergence taxonomy
   (18 fail-closed) + source/domain locks + RNG/event/checkpoint contracts
   (`src/commander_lab/semantic_replay/` 10 modules).
3. Recorder (fresh JVM, production policy, fingerprint/record + native
   submit + RNG/event/post verify, bounded prefix + interleaved native
   concessions + survivor drain to complete terminals, atomic sealed writes)
   and fresh-process consumer (14-step algorithm, exactly-one CURRENT-id
   resubmission, no pilot/policy import, no injection, no second engine).
4. Positives: 2P 611 / 3P 155 / 4P 257 / 5P 158 Lions tapes, each dual
   fresh-process replay PASS (12 JVMs); RNG-after-start, targets, numeric
   (2P multi_amount), commander casts/zone, combat + damage, concessions.
5. Tamper matrix 19/19 fail closed (exact/allowed classes, leak-free).
   Hidden/process/capability evidence sealed. WS220 R1–R12 adjudicated
   (all PASS; R10 raw pinned non-normative; provider-neutrality proven
   with Forge DIVIDED_ALLOCATION sketch, no integration).
6. One minimal production repair inside scope: `full_game.py:513` 3-tuple
   unpack crash on optional neutral targets (long-run unblock; narrowing
   itself untouched for S6) + regression test.

## New Findings

- Identical-Plains play-ability ambiguity (smoke step 20) required joining
  ability sources to hand occurrences (systemic, not first-pick).
- Conceding the pending actor wedges drain; interleaved concede (never the
  pending actor) + final survivor drain reaches terminals cleanly at all N.
- Numeric (`multi_amount`) needs long windows (turn ~20, 600-step prefix);
  bounded 100–250 step windows miss it (honest coverage note, not a gap).
- `raw_result_sha256`-lineage must never be normative (R10); semantic
  allowlists pinned instead; bit-exact stays false by design.

## Changes

- `src/commander_lab/semantic_replay/` (new, 10 modules).
- `src/commander_lab/engine/rules/full_game.py:513` (crash fix only).
- `tests/unit/test_semantic_replay_tape.py` (new, 11) +
  `tests/.../test_xmage_full_game_decision_matrix.py` (+1 guard).
- `qualification/ws218-semantic-replay-tape-v1/` (contracts, tapes, runs,
  tamper inputs, WS220 impact, validation, handoff).
- `src/commander_lab/semantic_replay/capability.py` (tape-lane truth).

## Tests / Evidence

See `VALIDATION.md/.json`. 46/46 impacted PASS; bridge BUILD SUCCESS;
12 fresh-JVM positives; 19/19 tampers; scans clean. Classifications:
fresh-JVM evidence RUNTIME_VERIFIED; contracts CODE_DERIVED + pins;
WS220 mapping CODE_DERIVED; retained UNKNOWNs stay UNKNOWN.

## PASS / FAIL / UNKNOWN

- PASS: tape schema/locks/identity/legal-set/duplicates/digests/
  canonicalization/RNG/events/checkpoints/consumer/divergence/positives
  2P–5P/tampers/hidden/process/capability/R1–R12/provider-neutrality-shape.
- UNKNOWN (unchanged, with cause): APNAP, extra-turn, CR800.4-control,
  damage thresholds, partner tax/damage, zone exile/hand/library branches
  (bounded successors; never replay-claimed).
- NOT_SUPPORTED: 6P (unchanged). NOT_RUN: FULL107. NOT_CLAIMED: Freeze,
  Provider, bit-exact/raw, Forge integration.

## Remaining Blockers

None in-scope. Successor-bound only: S6 numeric disposition + per-class
negatives, S7 honeycards, S8/S9 trigger-rich closers, Forge consumption,
FULL107, Freeze/Provider.

## Outputs

- `src/commander_lab/semantic_replay/`, tests, `qualification/
  ws218-semantic-replay-tape-v1/` (see artifact list), local commits on the
  WS218 branch (no push yet at handoff time; publication per prompt after
  Semantic Completion).

## Dependencies Unblocked

- AF09 replay lane closable on the tape contract; S10 hard gates
  (R10 allowlist, checkpoint + dual-mode + taxonomy) sealed; Forge
  successor has a neutral mapping sketch; S6/S7/S8 have exact bounded specs.

## Exact Next Action

- Coordinator: review handoff + sealed evidence + WS220 impact; publish via
  canonical `safe_push.py` (dry-run first; no raw push/PR/merge/main
  mutation); then charter S6/S7/S8/S9/Forge-consumption successors as
  directed. Do not start WS209/Forge integration from this session.

## Terminal fields

WS218_SEMANTIC_REPLAY_TAPE_V1 = COMPLETE
SEMANTIC_REPLAY_STATUS = PASS (tape lane; twins unchanged as determinism control; bit-exact still false)
REPLAY_SUPPORTED = TRUE (tape lane only; bridge replay_supported still false)
TAPE_SCHEMA_VERSION = semantic-replay-tape/1.0.0
SOURCE_LOCK_VALIDATION = PASS
DOMAIN_LOCK_VALIDATION = PASS
SEMANTIC_OPTION_IDENTITY = PASS (semantic-option-identity-1.0.0)
LEGAL_SET_MATCHING = PASS (multiset compare before every choice)
DUPLICATE_ACTION_DISAMBIGUATION = PASS (occurrence join; identical=>AMBIGUOUS)
RULES_RNG_REPLAY = PASS (engine-owned, calls coordinates, regenerate-not-inject)
EVENT_REPLAY = PASS
STATE_CHECKPOINTS = PASS (evidence only; no restore)
PRINCIPAL_OBSERVATION_DIGESTS = PASS (scoped; tape scan clean)
REPLAY_2P = PASS (611 steps, B+C PASS, numeric+damage+commander+concede)
REPLAY_3P = PASS (155 steps, B+C PASS)
REPLAY_4P = PASS (257 steps, B+C PASS)
REPLAY_5P = PASS (158 steps, B+C PASS)
TAMPER_SOURCE = FAIL_CLOSED (SOURCE_LOCK_MISMATCH)
TAMPER_DECK = FAIL_CLOSED (DOMAIN_LOCK_MISMATCH)
TAMPER_SEED = FAIL_CLOSED (RULES_RNG_RESULT_DRIFT)
TAMPER_ACTOR = FAIL_CLOSED (ACTOR_MISMATCH)
TAMPER_DECISION = FAIL_CLOSED (CLASS/REVISION covered)
TAMPER_LEGAL_SET = FAIL_CLOSED (LEGAL_SET_MISMATCH)
TAMPER_OPTION = FAIL_CLOSED (MISSING + AMBIGUOUS)
TAMPER_RNG = FAIL_CLOSED (CALL_DRIFT + RESULT_DRIFT)
TAMPER_EVENT = FAIL_CLOSED (EVENT_DIGEST_MISMATCH)
TAMPER_STATE = FAIL_CLOSED (STATE_DIGEST_MISMATCH)
TAMPER_TERMINAL = FAIL_CLOSED (TERMINAL_OUTCOME_MISMATCH)
HIDDEN_INFORMATION_REPLAY = PASS (scoped; leak scans clean; S7 cited)
PROCESS_ISOLATION = PASS (fresh JVM each; one-game enforced; atomic writes)
NO_STATE_INJECTION = PASS (scan; checkpoints evidence-only)
NO_SECOND_RULES_ENGINE = PASS (consumer has no pilot/policy)
FULL107 = NOT_RUN
RAW_GIT_PUSH_USED = NO
ARCHITECTURE_FREEZE = NOT_CLAIMED
PRODUCTION_PROVIDER = NOT_SELECTED
