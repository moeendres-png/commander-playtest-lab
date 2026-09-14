# WS78B Evidence Index

Source lock: `7725570b6b8690daed6e645dc1611f5e196de8c5`, branch
`ws78b/natural-session-baseline-20260914`, tree clean at start
(DIRECTLY_VERIFIED). `CANONICAL_FOUNDRY_CHANGES = NONE` (final diff limited
to this namespace; verify with `git status --short` + `git diff --stat`).

## Natural inputs (read-only; never modified)

| # | Artifact | Content authority | Class |
|---|---|---|---|
| 1 | `/tmp/foundry-ws191-20260914-021713/launch-context.json` | model/provider/xhigh/forge/base `aa5c`, session `""` | DIRECTLY_VERIFIED |
| 2 | `/tmp/foundry-ws191-20260914-021713/metrics.jsonl` | 1 launch line, no token/cost keys | DIRECTLY_VERIFIED |
| 3 | `/tmp/foundry-ws191-20260914-021713/state-patch-01..03.json` | adjudication→port→COMPLETE narrative | DIRECTLY_VERIFIED |
| 4 | `/tmp/foundry-ws191-20260914-021713/ws191-results.json` | 7 validated claims + 1 UNKNOWN | DIRECTLY_VERIFIED |
| 5 | `/tmp/foundry-ws191-20260914-021713/ws191-source-lock.json` | Forge lineage `aa5c`→`7360737b` | DIRECTLY_VERIFIED |
| 6 | `/tmp/foundry-ws191-20260914-021713/ws191-evidence-report.md` | handoff fragment, verdicts UNKNOWN | DIRECTLY_VERIFIED |
| 7 | `/tmp/foundry-ws191-20260914-021713/ws191-handshake.py` | no-mock 4-message methodology | DIRECTLY_VERIFIED |
| 8 | `/tmp/foundry-ws191-20260914-021713/ws191-handshake-transcript.jsonl` | exit 0, engine_commit `aa5c` | DIRECTLY_VERIFIED |
| 9 | `/tmp/foundry-ws191-20260914-021713/ws191-handshake-stderr.log` | engine init 7938 ms | DIRECTLY_VERIFIED |
| 10 | `/tmp/foundry-ws191-20260914-021713/bridge-cp.txt` | build classpath (not telemetry) | DIRECTLY_VERIFIED |
| 11 | `/tmp/foundry-ws191-20260914-021713/ws191-artifact-index.json` | 3674 entries; 3648 node_modules (99.3%), 3662 config-dir (99.7%), 12 run outputs | CODE_DERIVED counts over DIRECTLY_VERIFIED bytes |
| 12 | `/tmp/foundry-ws196-20260914-022551/launch-context.json` | model/provider/high/cpl/base `7725570b`, session `""` | DIRECTLY_VERIFIED |
| 13 | `/tmp/foundry-ws196-20260914-022551/metrics.jsonl` | 1 launch line, no token/cost keys | DIRECTLY_VERIFIED |
| 14 | `/tmp/foundry-ws196-20260914-022551/ws196-checkpoint-patch.json` | COMPLETE-pending-review | DIRECTLY_VERIFIED |
| 15 | `.../ws191-forge-aa5c-h4f/WORKSTREAM_STATE.yaml` | validated_head `7360737b`, tier xhigh | DIRECTLY_VERIFIED |
| 16 | `.../ws196-cross-repo-tool-routing/WORKSTREAM_STATE.yaml` | validated_head `691dbe50`, tier high | DIRECTLY_VERIFIED |
| 17 | `git show 691dbe50` (in-repo) | 6 files +530/−0, 00:36:23Z; 12-test file (435 lines); README +17; implementer +11; launcher +53; fixtures +7/+7 | DIRECTLY_VERIFIED (CODE_DERIVED test count) |
| 18 | `tools/foundry/session_stats.py`, `metrics.py` | export-only aggregation; provenance classes | DIRECTLY_VERIFIED |

## Outputs (this namespace; research only)

`RESEARCH.md`, `BASELINE_METRICS.json`, `BASELINE_METRICS.md`,
`QUOTA_ECONOMICS.md`, `SESSION_ROTATION_POLICY.md`, `OPTIMIZATION_PLAN.md`,
`MEASUREMENT_LIMITATIONS.md`, `EVIDENCE_INDEX.md` (this file), `HANDOFF.md`.

## Rotation-policy stress test (both sessions; summary)

- Stall trigger (60–90 min without milestone): neither session stalls
  (WS191 patches at +6.2/+2.6 min, handshake/results sealed by +17.7 min;
  WS196 commits at +10.3 min) → policy would NOT rotate either: correct,
  both completed. Trigger itself remains MODELED (no stall-recovery
  evidence in this sample).
- Context-size trigger: unverifiable in both (no exports). WS196 completed
  despite the ~127k report → policy must not rotate on size alone while
  milestones advance (added as explicit tie-break).
- Checkpoint-density trigger (~3 patches/2 commits): WS191 reaches it
  exactly at completion (seal + hand off: correct action); WS196 never
  reaches it (no false positive).
- Verdict: policy is consistent with both sessions but calibrated by
  healthy cadence only; stall/context legs await export-backed data.

## Classification ledger

`WS78B_NATURAL_BASELINE` measured per-field above.
`WS191_SESSION_MEASUREMENT`: 7 claims + COMPLETE; turns/tools/tokens/cost
UNKNOWN. `WS196_SESSION_MEASUREMENT`: 1 commit + 12 authored tests +
COMPLETE; execution/turns/tools/tokens/cost UNKNOWN.
`TOKEN_USAGE_EVIDENCE`: UNKNOWN (verified absence). `CACHE_USAGE_EVIDENCE`:
UNKNOWN (never inferred). `WALL_CLOCK_EVIDENCE`: lower bounds only
(1064 s / 685 s + commit timestamp); true walls UNKNOWN. `MILESTONE_RATE`:
CODE_DERIVED visible-window ratios; true rates UNKNOWN.
`SESSION_ROTATION_THRESHOLD`: MODELED. `ACCOUNTING_CONSISTENCY`:
`ACCOUNTING_UNKNOWN`. `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
`PRODUCTION_PROVIDER = NOT_SELECTED`.
