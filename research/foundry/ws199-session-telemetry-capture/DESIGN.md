# WS199 Session Telemetry Capture — Design

Source lock: `e6361c32` (WS198 terminal). Pinned CLI 1.18.30.

## Attribution finding (DIRECTLY_VERIFIED)

- `opencode export --help` exposes `opencode export [sessionID]` plus
  optional `--sanitize`. `opencode session list --format json` exists.
- TUI launches (`opencode --auto`) emit no reliable automatic session ID to
  Foundry; `FOUNDRY_SESSION` is the workstream label, never an OpenCode ID;
  headless `--format json` event parsing would be intrusive and TUI-inapplicable.
- Verdict: `AUTOMATIC_SESSION_ID_DISCOVERY = UNAVAILABLE`. Canonical design is
  explicit exact-ID capture, fail-open with `TELEMETRY_PENDING`/`TELEMETRY_HINT`.

## Capture shape

Single canonical `tools/foundry/session_capture.py`:

- exact `--session-id` required (strict token shape, no auto-select);
- identity precedence: explicit flag > `FOUNDRY_OPENCODE_SESSION_ID` >
  `<run_dir>/opencode-session-id`;
- raw `<run_dir>/raw-export-<sid>.json` (refused inside any Git worktree);
- `--sanitize` probed via `export --help`, used when advertised, never required;
- reuses `session_stats.summarize` (no second parser);
- validates exported `session_id == requested` (attribution mismatch refuses);
- ownership: `--task-id` vs `launch-context.json` workstream mismatch refuses;
- allowlisted aggregates only, each `AUTOCAPTURED`; absent stays absent;
  `compaction_count` stays unavailable; never zero-sentinel, never content;
- status `<run_dir>/telemetry-status.json`; stdout/stderr carry status lines only.

## Launcher level

`--opencode-session-id` (optional, persisted to run dir), `session_end_telemetry()`
after lock release: exact ID → bounded capture attempt; absent → PENDING + hint.
Child exit code, lock lifetime, Ctrl+C/130 handling, Go default, Zen override,
safe-push routing, TUI/headless parity, canonical routing unchanged. The WS198
TUI positional refusal stays intact.

## Milestones

No per-commit export. Operator runs the capture command after a checkpoint, at
session end (automatic when exact ID known), and at closure. No latency or spam
impact on normal engineering.

## No rotation policy

WS199 collects facts. No thresholds, no automatic compact/restart/kill, no
model/provider change.
