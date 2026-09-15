# WS229 REPLAY_IMPACT (implemented + proven)

## Extension contract used (no version bump)

WS228 allowed "version it explicitly OR prove compatibility under the
existing extension contract". WS229 proves compatibility:

- `TapeReplayStep` gains five OPTIONAL fields, all default None:
  `numeric_choices`, `numeric_legs_min/max`, `numeric_total_min/max`.
- Every WS218 tape validates unchanged (all new fields default; the
  version-pinning test `test_tape_schema_is_versioned_and_strict` passes
  untouched; `TAPE_SCHEMA_VERSION` stays `semantic-replay-tape/1.0.0`).
- Scalar steps record byte-identical bytes: no scalar construction site
  changed shape; event digests for scalar/non-numeric steps are
  byte-stable by construction (vector key included ONLY when present;
  proven by `test_scalar_event_digest_is_byte_stable` against the
  hand-computed WS218 formula) and joint vectors bind into the digest
  (`test_joint_event_digest_binds_vector`).
- Validators: vector fields all-or-nothing; lengths match; per-leg and
  total coherence; scalar/vector mutual exclusion.

## Recorder / consumer

- Recorder captures the joint domain + chosen vector from the
  authoritative frame/response at both step sites
  (`_joint_numeric_of`; malformed joint context DIVERGES instead of
  recording a weakened step). Scalar capture untouched.
- Consumer enforces legs/totals equality before use and replays the
  vector (`numeric_choices`) into the response; scalar checks untouched.
- Canonicalization: descriptor-first (never materialized member lists);
  `legal_set_digest` confirmed options-only TODAY with bounds carried in
  dedicated fields + equality checks — no digest change required, so no
  numeric-step digest shape change beyond the additive vector binding
  (F_RULES_02 adjudication records this confirmation).

## Tamper evidence

- Tape-level: incoherent vectors (length/leg/total/mixing) rejected by
  the model validator (unit tests).
- Recorder-level: malformed joint context raises `ReplayDivergence`
  (DECISION_CLASS_MISMATCH), never records.
- Transport-level (the replay submit path is the same submit path):
  N-16/N-22 rows prove forged vectors/numbers cannot enter.
- WS218 dual-replay positives: numeric-bearing dual scenarios remain
  future (no numeric-bearing recorded scenario exists yet); scalar
  digest stability keeps all existing dual positives green by
  construction. No replay behavior credit claimed beyond executed rows.

## No injection

No state or outcome injection: the vector extension carries only the
authoritative domain + the chosen values, exactly like the scalar
fields. RNG/seed/observation/digest contracts untouched.
