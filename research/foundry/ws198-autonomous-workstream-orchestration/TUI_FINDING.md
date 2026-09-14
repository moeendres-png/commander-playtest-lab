# WS198 TUI Finding — Exit-0 False Success (WS92/WS93 shape)

Classification: DIRECTLY_VERIFIED (pinned OpenCode 1.18.30, live reproduction
in this worktree). WS92/WS93 operator report taken as provenance (those
workstreams not modified, not re-run from WS198).

## Observed shape

TUI argv `opencode --auto <literal prompt>` → CLI binds the positional to
`[project]` (TUI syntax `opencode [project]`, verified via `opencode --help`):

```text
Error: Failed to change directory to /home/moeen/code/ws198-foundry-autonomy/probe-task
```

with child process exit **0**. Foundry emitted `LAUNCH_END: exit=0` after
~0.5 s although no agent task executed. Reproduced here with
`opencode --auto probe-task` (instant, rc=0, identical stderr shape).

## Verified CLI semantics (1.18.30 `--help`, DIRECTLY_VERIFIED)

- TUI: `opencode [project]`; initial-message injection via `--prompt` (string).
- Headless: `opencode run [message..]` (bare message correct).
- `opencode --auto --prompt probe-task` → TUI starts, no directory error.
- Operator workaround `opencode --auto -- --prompt probe-task` → TUI starts
  (valid; `--` passthrough incidental).

## Systemic fix (smallest correct)

`launcher.canonicalize_tui_extras` (fail-closed, TUI-only, before lock):

- drops one leading `--` launcher-argparse artifact → canonical child form
  `opencode --auto --prompt "<task>"` (launcher spelling `-- --prompt "<task>"`);
- refuses any remaining bare positional → `LAUNCH_REFUSED` (never execs, so
  the exit-0 false success cannot reach `LAUNCH_END`);
- honors `--prompt`/`--agent`/`--session`/etc. value-flag values.

Headless untouched (`run [message..]` bare message). `validate_child_options`
docstring corrected (bare `--` text was never universally safe prompt input)
and now scans past `--` (closes `-- --model x` selection bypass).
`--ui-mode` help documents both prompt forms.

## Detection ruling

Post-hoc detection of this class without heuristic stderr parsing is NOT
reliably possible: child exit 0 is the CLI contract, and elapsed/shape
heuristics would be fabrication-prone. Systemic answer = prevention at
construction + `ui_mode` in run telemetry (start+end records, AUTOCAPTURED)
for future audit joins. `LAUNCH_END: exit=0` certifies process exit only —
documented in AUTONOMY.md §9.

## Regression tests

`tests/foundry/test_ws198_autonomy.py`: CLI-shape stub reproduces the exact
failure (directory error + exit 0); launcher refuses before exec (stub never
invoked, rc=1); `--prompt` form reaches child canonically; headless bare
message unchanged. Hermetic, no ambient binary.
