# WS200 Source Lock

- Repository: moeendres-png/commander-playtest-lab
- Branch: ws200-foundry-rotation-observability
- Audit base SHA: e69ee5950b52dbf90c9ccd17a0918bba29dbdd6e (WS199 terminal)
- Audit base tree: fe4db92d739a64b6f33d5c2eef05f3a79c4de3e7
- Source branch authority: ws199/foundry-session-telemetry-capture-20260914 (terminal published authority)
- ARCHITECTURE_FREEZE = NOT_CLAIMED
- PRODUCTION_PROVIDER = NOT_SELECTED

## WS199 conclusions preserved (all verified in live source before mutation)

- Exact-session telemetry capture works only with an exact OpenCode session ID.
- Automatic TUI session-ID discovery is UNAVAILABLE.
- Missing/ambiguous session identity stays PENDING with a hint; never blocks engineering.
- Raw export is LOCAL_ONLY (run dir only, never committed, never printed).
- Only aggregate allowlisted telemetry is persisted, each field AUTOCAPTURED.
- Missing token/cache fields stay absent; compaction count unavailable from pinned CLI.
- No token threshold, no automatic rotation, no model/provider switching.

## Starting architecture verified (live source, read-first)

- `tools/foundry/autonomy.py`: pure (imports `re` + `collections.abc` only);
  `ROTATION_RECOMMENDATIONS = (NO_ROTATION, REVIEW_PROMPT,
  ROTATE_TO_FRESH_CONTINUATION)`; `rotation_render(data)` reads
  `state.rotation_guidance` + export-missing disclaimer; no I/O/Git/network/telemetry.
- `tools/foundry/context_capsule.py`: DERIVED/INDEX capsule from exact state +
  live Git facts + identity checks; renders autonomy fields + rotation via
  `rotation_render(data)`; fail-closed `CAPSULE_REJECT`.
- `tools/foundry/launcher.py`: launch-context carries persisted
  `rotation_recommendation`; `LAUNCH_READY` never gated by it; WS199
  fail-open session-end telemetry; Go default + explicit Zen override intact.
- Schema `rotation_guidance` optional with the 3 recommendations; absent = valid.
