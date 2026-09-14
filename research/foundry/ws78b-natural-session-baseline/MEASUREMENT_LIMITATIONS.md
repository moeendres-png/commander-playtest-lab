# WS78B Measurement Limitations (missing telemetry vs zero values)

Every UNKNOWN below is missing telemetry (verified absent), never a measured
zero. A zero is claimed only where a log shows zero (e.g. handshake
`failures: []`, test `0 failures` inside one milestone's output).

## Absent-by-construction (DIRECTLY_VERIFIED)

1. **Session identifiers**: both `launch-context.json` files carry
   `"session": ""`. There is no non-secret OpenCode session key in either
   run root, hence no `opencode export` target and no `session_stats.py`
   input. All export-derived fields (turns, tool calls, tokens, cost,
   wall time) are UNKNOWN for structural reasons, not oversight.
2. **Metrics lines**: each `metrics.jsonl` holds exactly 1 launch record
   with zero token/cost/timing keys beyond `started_utc`. The launcher's
   end-of-session telemetry for these runs either did not run or did not
   persist here — the run roots are the authority, and the fields are
   absent in them.
3. **Compaction**: the pinned CLI 1.18.30 export shape carries no
   compaction marker (`session_stats.py` reports it unavailable, never
   inferred — DIRECTLY_VERIFIED source read). Compaction counts are
   UNAVAILABLE_FROM_PINNED_CLI until the format or wrapper changes.

## Missing logs (absent, not negative)

4. **WS196 test execution**: 12 hermetic tests authored (CODE_DERIVED blob
   count; categories: 3 profile-resolution, discovery-free, unit,
   fail-closed, 2 permission, gates, TUI/headless parity, Go/Zen default,
   agent-docs). No run log exists in the WS196 run root → verdict UNKNOWN.
   This is not a failure signal; it is an evidence gap the export/test-log
   gate must close.
5. **Turn/tool/error/retry/timeout/no-progress counts**: no per-turn record
   exists for either session → all UNKNOWN. In particular, tool errors are
   UNKNOWN at session scope even though individual milestones report zero
   failures inside their own outputs (those zeros are milestone-local,
   DIRECTLY_VERIFIED only for that command's output).
6. **Latency**: only one DIRECTLY_VERIFIED timing exists (bridge engine
   init 7938 ms, stderr). Session latency/no-progress patterns are UNKNOWN;
   anecdote is not converted.
7. **Context growth**: UNKNOWN for both. The WS196 ~127k report is
   provenance only. Cache-read ratio UNKNOWN; cache hits never inferred
   from context shape.
8. **Cost/quota**: all three accounting legs absent → `ACCOUNTING_UNKNOWN`.

## Asymmetric verifiability (provenance boundary)

9. **WS191 Forge identity** `7360737b…`: task-provenance + run-root bytes
   (`ws191-source-lock.json`, results, state file). Independent
   revalidation from this CPL worktree is NOT_RUN (separate repository, no
   declared reference root). The 7 milestones are session-reported
   DIRECTLY_VERIFIED bytes, not independently re-executed claims — the
   baseline treats run-root bytes as measurement authority and says so.
10. **WS196 CPL identity** `691dbe50…`: DIRECTLY_VERIFIED in-repo (`git
    log`, `git show`, state `validated_head`). Strongest leg of the
    baseline.
11. **Evidence-report verdicts**: WS191's own `ws191-evidence-report.md`
    fragment marks every test verdict `UNKNOWN` (Coordinator review
    pending). The baseline counts session-reported PASS outputs, not
    adjudicated verdicts — stated explicitly so a future adjudication can
    revise counts without invalidating this file's provenance claims.

## Sensitivity: alternative milestone formulations (all CODE_DERIVED)

- WS191 strict locally-reproducible count: 0 (Forge NOT_RUN here) — shows
  the baseline's dependence on run-root authority for cross-repo sessions.
- WS191 session-reported claims: 7 (+1 explicitly UNKNOWN historical).
- WS191 test-execution formulation: 59 + 3 + 5 + 4 = 71 passing test
  executions + compile + handshake + delta ≈ 240 test-execs/hr over the
  visible 1064 s (denominator lower bound; true rate UNKNOWN).
- WS196: 1 commit (DIRECTLY_VERIFIED) vs 12 authored tests (CODE_DERIVED)
  vs executed UNKNOWN — report the range, never collapse it.
- Denominator sensitivity: WS196 launch→commit 621 s gives 5.8 commits/hr
  vs 5.3 over the full 685 s window — narrow, robust. WS191's true wall is
  only bounded below, so its 23.7 claims/hr is an upper bound on the
  visible-window rate, not a session rate.

## Smallest telemetry improvements that eliminate current UNKNOWNs

1. Export gate (kills turns/tools/tokens/cost/wall UNKNOWNs in one move).
2. Per-milestone JUnit/test-log capture (kills execution-verdict UNKNOWNs
   like WS196's).
3. CALLER_SUPPLIED retry/intervention/no-progress counts (launcher already
   has the `human_interventions` field; use it).
4. Quota snapshot at session start/end (operator-provided; Leg 3).
5. Compaction observability: needs CLI/wrapper support; until then record
   UNAVAILABLE_FROM_PINNED_CLI explicitly per session instead of silence.
