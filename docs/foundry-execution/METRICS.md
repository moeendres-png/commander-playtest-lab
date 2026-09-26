# Session Metrics with Provenance (Checkpoint E)

No dashboard. One JSONL record per task or session, appended with
`tools/foundry/metrics.py`. Never invent token counts, tool-call counts, or
timings; missing measurements stay absent.

## Provenance (required discipline, `--provenance FIELD=CLASS`)

- `AUTOCAPTURED` — read deterministically by project tooling (launcher,
  safe_push, session_stats) from an authoritative source.
- `CALLER_SUPPLIED` — provided by a human/operator (e.g. intervention counts).
- `UNAVAILABLE_FROM_PINNED_CLI` — the pinned CLI exposes no such signal.
- `UNKNOWN` — provenance not established.

## Autocapture matrix (verified 2026-09-10, CLI 1.18.30)

| Metric | Source | Provenance |
|---|---|---|
| task/workstream ID, profile, model, effort | launcher plan | AUTOCAPTURED |
| source/final SHA | launcher git reads | AUTOCAPTURED |
| start/end UTC, elapsed, exit status | launcher clock/child | AUTOCAPTURED |
| model turns, tool calls (+by tool), tool errors, patches | `session_stats.py` over `opencode export` JSON | AUTOCAPTURED |
| tokens in/out/reasoning/cache, cost USD | same export `info` block | AUTOCAPTURED |
| push result / reject reason | safe_push `--metrics` | AUTOCAPTURED |
| human interventions | operator report | CALLER_SUPPLIED |
| build/test attempts | caller or wrapper counts | CALLER_SUPPLIED |
| compaction count | no marker in export format | UNAVAILABLE_FROM_PINNED_CLI |
| per-turn model internals | not exposed | UNAVAILABLE_FROM_PINNED_CLI |

Raw `opencode export` files are LOCAL_ONLY (they contain session content):
`session_stats.py` emits counts only, and raw exports are never committed.

## Recorded fields

`task_id`, `task_class`, `repo_profile`, `model`, `reasoning_effort`,
`source_sha`, `final_sha`, `started_utc`, `ended_utc`, `elapsed_seconds`,
`exit_status`, `completed`, `human_interventions`, `model_turns`, `tool_calls`,
`tool_calls_by_tool`, `tool_errors`, `token_usage`, `tokens_input`,
`tokens_output`, `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write`,
`cost_usd`, `patch_count`, `build_attempts`, `test_attempts`,
`checkpoint_commit_count`, `safe_push_count`, `failed_safe_push_count`,
`push_result`, `reject_reason`, `state_validation_failures`,
`writer_lock_conflicts`, `reverts`, `scope_violations`, `failure_class`,
`evidence_status`, `provenance`.

## Usage

Manual records may target any caller-owned path (parents are created
automatically):

```bash
python3 tools/foundry/metrics.py --metrics /tmp/my-run/metrics.jsonl \
  --set task_id='"WS50-slice-03"' \
  --set task_class='"bounded single-file bug"' \
  --set reasoning_effort='"high"' \
  --set source_sha='"<40-hex>"' \
  --provenance task_id=CALLER_SUPPLIED \
  --provenance reasoning_effort=CALLER_SUPPLIED
```

Launcher sessions record start/end automatically under the run directory
(`<run_dir>/metrics.jsonl`, outside the Git worktree so execution leaves
the tree clean; sealed into evidence, never committed raw). Enrich a
finished session with export counts:

```bash
opencode export <sessionID> > /tmp/proven-session.json  # LOCAL_ONLY
python3 tools/foundry/session_stats.py --export /tmp/proven-session.json
```

The core project effectiveness notion is verified engineering progress per human
coordination per model effort — not commit count. These records feed the
HIGH-vs-XHIGH comparison; the benchmark itself remains NOT_RUN by design.
