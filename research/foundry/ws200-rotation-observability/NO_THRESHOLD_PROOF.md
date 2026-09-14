# WS200 No-Threshold Proof

Claim: no numeric token/context/cache/cost/turn/tool-call/time value can
change a rotation recommendation. Evidence:

1. **Construction (CODE_DERIVED):** `recommend_rotation(data,
   git_facts, previous_observation)` and `observe_rotation(...)` take no
   telemetry parameter. Telemetry display fields live only in
   `TELEMETRY_DISPLAY_FIELDS` (a render allowlist) and
   `render_telemetry_info(telemetry)`, which returns a string and is never
   called by the recommendation path. No comparison operator (`>`, `<`,
   `>=`, `<=`) touches a telemetry value anywhere in `autonomy.py`.
2. **Adversarial invariance (DIRECTLY_VERIFIED by tests):**
   `test_telemetry_values_never_change_recommendation` and
   `test_telemetry_values_never_change_review_prompt` render the capsule
   with zero, nominal, and 1e9-1e12 synthetic aggregates for all nine
   display fields (`tokens_input/output/reasoning/cache_read/cache_write`,
   `cost_usd`, `model_turns`, `tool_calls`, `elapsed_seconds`) plus
   `tool_errors`, and assert the identical `rotation:` line for identical
   state/Git facts. Six malformed/untrusted shapes (PENDING, FAILED,
   empty session, foreign session, missing metrics, non-AUTOCAPTURED
   provenance) assert the disclaimer path with no verdict change.
3. **Absence path (DIRECTLY_VERIFIED):** `test_capsule_derive_telemetry_absent_tui_style`
   derives text+JSON capsules in a throwaway repo with no run dir, no
   session ID, no telemetry-status file; derivation succeeds with the
   disclaimer and invents no figures.
4. **Static audit:** final diff searched for `os.kill`,
   `process.terminate`, `process.kill`, SIGTERM/SIGKILL rotation paths,
   automatic restart/`/compact`/provider-model override — absent (existing
   child-cleanup behavior untouched and unlabeled). Threshold vocabulary
   (`SESSION_ROTATION_THRESHOLD`, `SESSION_FEELS_LONG`,
   `CONTEXT_PROBABLY_FULL`, `MODEL_SEEMS_STUCK`) absent from code.

Result: THRESHOLD_FREE = PASS. TOKEN_THRESHOLD, CONTEXT_PERCENT_THRESHOLD,
WALL_CLOCK_THRESHOLD, COMMIT_COUNT_THRESHOLD, CACHE_THRESHOLD,
COST_THRESHOLD = ABSENT (all six).
