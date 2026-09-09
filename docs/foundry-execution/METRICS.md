# Minimal Session Metrics

No dashboard. One JSONL record per task or session, appended with
`tools/foundry/metrics.py`. Reuse OpenCode session stats or export output as the
values when available; never invent token counts, tool-call counts, or timings.

## Recorded fields

`task_id`, `task_class`, `reasoning_effort`, `source_sha`, `final_sha`,
`completed`, `human_interventions`, `build_attempts`, `test_attempts`,
`tool_calls`, `token_usage`, `elapsed_seconds`, `reverts`, `scope_violations`,
`failure_class`, `evidence_status`.

Every field is optional except presence in the schema: record what is technically
available without fragile inference. `tool_calls`, `token_usage`, and
`elapsed_seconds` are omitted entirely when OpenCode does not expose them.

## Usage

```bash
python3 tools/foundry/metrics.py --metrics docs/foundry-execution/metrics.jsonl \
  --set task_id='"WS48-probe-01"' \
  --set task_class='"bounded single-file bug"' \
  --set reasoning_effort='"high"' \
  --set source_sha='"<40-hex>"' \
  --set final_sha='"<40-hex>"' \
  --set completed=true \
  --set human_interventions=0 \
  --set build_attempts=2 \
  --set test_attempts=3 \
  --set failure_class='"NONE"' \
  --set evidence_status='"DIRECTLY_VERIFIED"'
```

The core project effectiveness notion is verified engineering progress per human
coordination per model effort — not commit count. This file plus the JSONL log
are the whole mechanism until measured need justifies more.
