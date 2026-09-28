# Session-statistics input and publication contract

```sh
python3 tools/foundry/session_stats.py --export /private/session.json --output /private/summary.json
```

The export remains LOCAL_ONLY. Use a completed, quiescent export generated separately
from this command. The utility neither invokes a provider nor reads authentication data.

## Valid summaries

Existing output fields and metric provenance remain unchanged. The parser requires a
session identifier, nonempty messages list, and a parts array on every message. Empty
parts arrays are valid. Each part must have a nonempty string type. Tool parts require
a tool identifier and one of pending/running/completed/error; only error counts as error.
Other part kinds are not interpreted as tool calls. No metric is inferred from text,
outputs, patches, or step-finish tokens. Compaction count remains unavailable.

Optional numeric values may be absent or null: they remain omitted, never estimated.
Supplied tokens/cache counts must be finite, nonnegative whole numbers; cost must be
finite and nonnegative. Booleans are not measurements. Supplied timestamps must be
nonnegative and representable, with updated >= created if both exist. Optional model,
tokens, cache and time containers must be objects if present. Output identifiers must
be scalar, nonempty strings without control characters; nested content is never coerced
into an identifier. Duplicate JSON keys and NaN/Infinity constants are rejected.

## Fail closed

An invalid export produces exit 1, a `SESSION_STATS_INVALID` diagnostic on stderr,
no stdout summary, and no newly published output file. Diagnostics exclude offending
values, raw decoder messages, tool errors and private input paths. Valid success is
exit 0. Always check the exit code; an existing file is not evidence of a fresh success.

The output must not alias the raw export (including symlinks/hardlinks). File output is
written to a same-directory temporary file and atomically replaced after a complete
write. Failure before replacement leaves the old output intact. A cleanup failure emits
a generic warning. Parent directories are not created implicitly. This is atomic
visibility, not an fsync-backed durability guarantee or protection against concurrent
path replacement by another writer.

## Trust and compatibility

This validates the documented repository export shape, not the authenticity or
completeness of an export. Valid metadata identifiers (including tool names) are intentionally
retained: this is not a general secret scanner. Do not place secrets in those fields.
An omitted message cannot be detected without a separate authenticated manifest.
Unrecognized non-tool part kinds are ignored for current counters; future export shape
changes require explicit compatibility validation. No live CLI/provider compatibility
claim is gained from synthetic tests, and no qualification credit is assigned.

Regression commands:

```sh
python3 -m pytest -q -o addopts= tests/foundry/test_session_stats_integrity.py tests/foundry/test_telemetry.py
python3 -m pytest -q -o addopts= tests/foundry
ruff check tools/foundry/session_stats.py tests/foundry/test_session_stats_integrity.py
ruff format --check tools/foundry/session_stats.py tests/foundry/test_session_stats_integrity.py
```
