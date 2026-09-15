# WS218 DIVERGENCE_TAXONOMY

18 fail-closed classes (`semantic_replay/divergence.py`): SOURCE_LOCK_MISMATCH,
DOMAIN_LOCK_MISMATCH, INITIAL_STATE_MISMATCH, ACTOR_MISMATCH,
DECISION_CLASS_MISMATCH, DECISION_REVISION_MISMATCH, OBSERVATION_MISMATCH,
LEGAL_SET_MISMATCH, CHOSEN_OPTION_MISSING, CHOSEN_OPTION_AMBIGUOUS,
RULES_RNG_CALL_DRIFT, RULES_RNG_RESULT_DRIFT, EVENT_DIGEST_MISMATCH,
STATE_DIGEST_MISMATCH, EARLY_TERMINATION, EXTRA_DECISION,
TERMINAL_OUTCOME_MISMATCH, MALFORMED_TAPE. Existing vocabulary reused
(`STALE_DECISION`/`ILLEGAL_ACTION`/`PILOT_RESPONSE_INVALID` remain the
engine-side rejections beneath the tape mapping; no duplicate semantics).
No WARN_AND_CONTINUE: every divergence raises `ReplayDivergence` and aborts
without partial mutation (verified: no negative partially mutates then
PASSes; tamper loop asserts fail-closed).

Machine companion: `DIVERGENCE_TAXONOMY.json`.
