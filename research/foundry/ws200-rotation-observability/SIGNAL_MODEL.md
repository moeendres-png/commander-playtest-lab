# WS200 Signal Model (facts, not scores)

Observation = pure function of authoritative state/Git milestone facts.
Every surfaced datum carries provenance: `state-derived`,
`git-derived`, or `state-derived+git-derived`; telemetry is
`AUTOCAPTURED` or unavailable/unknown. Authorities are never conflated.

## Fingerprint inputs (the only repeat-detection basis)

1. live HEAD (`git-derived`)
2. `validated_head` (`state-derived`)
3. `exact_next_action` (`state-derived`)
4. `remaining_scope` identity, ordered (`state-derived`)
5. failure identity = `failure_class` + `current_failure` (`state-derived`)
6. `state_written_against_head` (`state-derived`)

Descriptive noise excluded by construction: worktree dirtiness,
`commits_since_base`, validated-ancestry booleans, and all telemetry
never enter the fingerprint (tested).

## Recommendation rules (deterministic, threshold-free)

| # | Condition | Verdict | Reason code |
|---|-----------|---------|-------------|
| 1 | persisted `ROTATE_TO_FRESH_CONTINUATION` | preserve it | `PERSISTED_ROTATE_REQUEST` |
| 2 | persisted `REVIEW_PROMPT` | `REVIEW_PROMPT` | `PERSISTED_ROTATION_REVIEW_REQUEST` |
| 3 | `status` in (`BLOCKED`,`STALE`) AND recorded failure identity | `REVIEW_PROMPT` | `EXPLICIT_STALL_STATE` |
| 4 | current fingerprint == explicitly supplied previous fingerprint | `REVIEW_PROMPT` | `REPEATED_CHECKPOINT_WITHOUT_MATERIAL_PROGRESS` |
| 5 | otherwise | `NO_ROTATION` | (none) |

Rules are ordered; rule 1 preserves existing WS198 semantics without
broadening them. Rule 3 requires BOTH an explicit stall status AND a
failure identity, so ordinary active engineering (ACTIVE + failure under
investigation, BLOCKED/STALE without failure, HEAD ahead, dirty tree,
drift, remaining scope, completion-ready terminal) stays `NO_ROTATION`
and never becomes review noise (parametrized tests).

## Checkpoint density (descriptive observability only)

Capsule collects `commits_since_base` (`git rev-list --count
base..HEAD`, fail-open omit), validated-ancestry booleans, and dirtiness
into the observation. They render as facts and never affect the verdict;
no "more/fewer than N checkpoints means rotate" statement exists.

## REVIEW_PROMPT semantics

"At the next safe checkpoint, inspect whether continuing the same
session remains the best execution context. A fresh compact continuation
may be preferable." It never kills, stops, discards, auto-rotates,
compacts, switches provider/model, or invalidates evidence. Every
instance carries its exact reason code + source class. Session rotation
is NOT workstream rotation: same WS/branch/worktree/state stays
authoritative; `do_not_rerun` items are never rerun.
