# AF09: the replay-export refusal and a proven clean-process twin (adjudication)

Status: **ADJUDICATED**. `PRODUCTION_PROVIDER = NOT_SELECTED`, `ARCHITECTURE_FREEZE = NOT_CLAIMED`.

Adjudicated by the Claude campaign session acting as the sole project executor and
temporary technical Coordinator (owner instruction, 2026-10-02). A newer direct owner
or Coordinator ruling supersedes this record.

## Question

The PB-03 runner asks each candidate for a single-process replay export in a live
game (`RNG_REPLAY_<CANDIDATE>.json`). Both candidates refuse it fail-closed
(`unsupported_message`). Until now the AF09 gate turned that refusal into a blocking
limitation, so AF09 could not reach PASS even with a proven clean-process twin and
all five replay/RNG rows PASS.

Does the refusal block AF09 once the clean-process twin carries the obligation?

## Ruling

**No.** The refusal stays recorded, worded as a refusal, and is never credit. It no
longer blocks AF09 once a proven clean-process twin carries the obligation.

Rationale:

1. **The AF09 contract is the twin.** `docs/af09_replay_twins_20261001/README.md`
   defines it: two genuinely fresh processes bound by fixture, build and Lab source
   identity; the seed and its acknowledgement; the external decision tape; the
   semantic event tape; checkpoint state hashes; terminal facts; and the observed,
   distinct process identities. The 2026-09-30 Coordinator adjudication names only
   FULL107 rows as AF09's blocking rows. A single-process export is not part of
   that contract.
2. **An export payload is not replay proof.** The assembler already states this:
   "payload presence is recorded, not replay proof". If its absence blocked AF09
   permanently, a capability that could never earn PASS would decide the verdict
   on its own.
3. **The refusal is never inverted into credit.** It stays in the AF09 evidence:
   "the single-process replay export refusal stays recorded as an absent
   capability; it is not a satisfied obligation and this verdict does not rest on
   it, only on the proven clean-process twin".

## Where the refusal still blocks

The refusal remains a blocking limitation whenever:

- no `clean_process_twin` is present;
- the twin is not verified;
- any element of the twin contract is missing or empty: `fixture_identity`,
  `process_identity`, `decisions`, `rules_rng`, `semantic_events`,
  `checkpoint_state_hashes` or `terminal_outcome`.

PASS needs, in addition, all five replay/RNG rows (`REPLAY_CLEAN_PROCESS`,
`REPLAY_DECISION_TAPE`, `REPLAY_EVENT_TAPE`, `REPLAY_STATE_HASHES`,
`RNG_RULES_TAPE`) to be PASS through their own runner-bound positive receipts. A
failed row is still FAIL, and an open row is still UNKNOWN.

## Twin source

The twin comes from the `RNG_REPLAY` artifact, or else from the production midgame
lane's `MIDGAME_REPLAY_TWIN_EXECUTIONS.json`. The assembler supplies the midgame
document (`midgame_replay_twin_document`) only when all of these hold:

- the column is the fresh XMage column of this epoch;
- the document names the column's engine commit and the assembling runner digest;
- its twin's executed build reports that same engine commit.

That document never credits a row on its own.

## Implementation

- `gate_derivations.clean_process_twin_missing`;
- `gate_derivations.af09_rng_replay(..., midgame_twin=...)`;
- `assemble_current_boundary_evidence._describe_replay_evidence(..., twin_proven=...)`;
- `assemble_current_boundary_evidence.midgame_replay_twin_document`.

Tests in `test_current_boundary_gate_derivations.py` and
`test_current_boundary_assembler_integrity.py` pin each branch above.
