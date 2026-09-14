# WS200 Impact Adjudication (against actual WS199 result)

WS199 actual: exact-session capture works end-to-end when the operator supplies
the exact OpenCode session ID; automatic discovery is UNAVAILABLE for TUI
launches; missing/ambiguous identity stays PENDING with a hint; raw stays
LOCAL_ONLY; aggregates are AUTOCAPTURED allowlisted counts; no threshold, no
rotation, no kill, no model/provider switch (355 Foundry + 22 WS78 PASS).

## Impact on WS200 plan (rotation observability)

- WS200 remains USEFUL and UNBLOCKED. Its threshold-free advisory design
  (checkpoint density / stall patterns from state/Git facts) never depended on
  token data, so WS199's explicit-ID outcome does not invalidate it.
- WS199 aggregates become OPTIONAL enrichment only: when a WS199 capture exists
  for the run, WS200 surfacing may cite export-verified counts with
  AUTOCAPTURED provenance; when absent (the common TUI case), WS200 must carry
  the export-missing disclaimer and must never estimate, never threshold, never
  require telemetry for advisory rendering.
- No WS200 scope change is justified: token/context accounting, automatic
  rotation, process control, and provider/model switching stay out of scope.
  WS199 introduces no new rotation signal that would permit thresholds.

## Updated execution-ready WS200 specification

See `WS200_SPEC.json` (this directory). Deltas vs the WS198 plan-time draft:

- source-lock basis rebound to WS199 terminal reality (re-verify HEAD at launch);
- inputs add WS199 `session_capture.py` + `telemetry-status.json` as optional
  enrichment with explicit absent-handling;
- evidence requirements add: aggregates-if-present provenance check;
  absent-telemetry disclaimer test;
- hard gates add: telemetry-absent advisory path; no capture-required gate.
