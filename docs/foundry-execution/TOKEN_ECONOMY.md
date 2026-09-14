# Foundry Token Economy (WS78)

Operator workflow for token/credit-efficient Foundry workstreams. Quality,
evidence, privacy, and fail-closed safety outrank savings everywhere here.

`TOKEN_ECONOMY_BENCHMARK = NOT_RUN` — no real-session token/cache figures have
been measured yet (see Benchmarking). Byte/line figures below are STRUCTURAL
context-size metrics, never token claims.

## Operator workflow

1. Launch the validated Foundry session for the prepared workstream
   (contract + state already authored by the Coordinator).
2. Type `/work` in the TUI.
3. Muse derives a compact execution capsule from `FOUNDRY_STATE_PATH` plus
   live Git facts via `tools/foundry/context_capsule.py` and executes/resumes
   the bounded workstream through Semantic Completion.
4. Muse reads the full state, contract, and evidence only when the capsule is
   insufficient for the next action.
5. After an interrupted TUI session, relaunch and type `/work` again.

## What consumes cached vs dynamic context (conceptual)

Stable, cache-friendly prefix (same bytes every turn once warm):

- root `AGENTS.md`, `opencode.json` instructions, the selected agent
  definition, the `/work` command text, skill IDs/descriptions.

Dynamic per-turn content (never assumed cached):

- the derived capsule values (HEAD, cleanliness, next action),
- bounded tool-output previews,
- the running conversation.

A stable prefix is *eligible* for provider prompt caching; only exported
session metrics prove a cache hit for a real session. Never claim hits.

## What WS78 changed (and deliberately did not)

- Added `tools/foundry/context_capsule.py`: deterministic read-only capsule
  (identity, audit base, live HEAD/tree/cleanliness, validated head/status,
  objective, exact next action, hard/authority gates). DERIVED/INDEX only;
  fail-closed (`CAPSULE_REJECT`) on missing/invalid state or contradictory
  source-lock identity; never prints environment values; `--full` opts into
  full-state inspection.
- Added `.opencode/commands/work.md`: selects `foundry-implementer`, injects
  the capsule through `` !`python3 tools/foundry/context_capsule.py` `` shell
  interpolation (command semantics per OpenCode docs: `!`command`` output
  becomes prompt content, run in the project root), stays under 2 KB, embeds
  no policy/state/contract text (locked by `test_ws78_token_economy.py`).
- `opencode.json` pins the already-effective `tool_output` defaults
  (`max_lines: 2000`, `max_bytes: 51200`, verified as the pinned CLI 1.18.30
  behavior) and the launcher injection bundle carries them
  (`build_content_bundle` + strict `_validated_tool_output`). Representative
  Foundry outputs (status/diff/log/test/ruff previews: tens of bytes to a few
  KB) sit far below these bounds, so lowering them would save nothing typical
  while risking diagnostics — defaults kept, further tuning stays `UNKNOWN`.
- `compaction.prune` is intentionally unset in project config (the safe
  default `false` applies at the project layer; locked by test). No exact-pin
  proof was established that pruning removes only expendable pressure, so WS78
  does not enable it and claims nothing for it. Observed 2026-09-13:
  `opencode debug config` in the launch environment resolves effective
  `compaction: {auto:true, prune:true, reserved:10000}` from the
  operator-global `~/.config/opencode/opencode.json` — pre-existing operator
  scope outside this workstream, neither set nor overridden here (the launcher
  bundle carries no `compaction` key). No `reserved` / `tail_turns` /
  `preserve_recent_tokens` tuning in project config.
- Instruction layers kept as-is (`AGENTS.md`, `instructions` entry for
  `ROUTING_AND_EFFORT.md`, `foundry-implementer.md`): no always-on prose was
  provably redundant while keeping its invariant machine-enforced elsewhere,
  and stable policy is cheap when cached. One additive line only: the agent
  now prefers reading a saved full-output file (offset/limit, search) over
  rerunning an expensive command after a truncation preview.
- Session resume is explicit only: `opencode run --session <OpenCode session
  ID>` (verified on the pinned 1.18.30 binary) for headless reruns;
  `opencode session list` / `export [sessionID]` discover IDs. Never blind
  `--continue` (it can select another live session). `FOUNDRY_SESSION` is a
  workstream label, not an OpenCode session ID — never pass it as
  `--session`. TUI resume is relaunch-plus-`/work`. Automatic capture of the
  OpenCode session ID into run metadata is a follow-up, not implemented here.

## Truncation recovery

Oversized tool output is bounded for model context while the complete text is
stored separately by OpenCode; the preview names the saved file. When a
preview is insufficient, read/search the saved file (`Read` with
offset/limit, `Grep`) instead of rerunning the command. Truncation bounds are
pinned in `opencode.json` and covered by the injection bundle, so the
recovery path cannot silently drift.

## Authoritative metrics

Use `tools/foundry/session_capture.py` (exact-session export → aggregate →
`metrics.jsonl` with AUTOCAPTURED provenance; reuses
`tools/foundry/session_stats.py`) plus `tools/foundry/metrics.py` (JSONL
records with provenance). Raw export files are `LOCAL_ONLY` under the run
directory: never commit or paste them. Record only aggregates:

- `session_id`, `model`/`provider`/`variant`/`agent`/`cli_version`,
  `tokens_input`, `tokens_output`, `tokens_reasoning`,
  `tokens_cache_read`, `tokens_cache_write`, `cost_usd`, model turns, tool
  calls (by tool), tool errors, `patch_count`, timings.

Capture workflow: `python3 tools/foundry/session_capture.py --run-dir
<run_dir> --session-id <OpenCode-sessionID>` after a checkpoint or at
session end; the launcher attempts the same bounded capture when the exact
ID is supplied (`--opencode-session-id` / env / run-dir file) and otherwise
emits a non-blocking `TELEMETRY_PENDING`/`TELEMETRY_HINT`. Exact ID only —
never newest-session guessing under concurrent workers. Missing fields stay
absent; `compaction_count` stays unavailable; no rotation threshold exists
(WS199 collects facts only).

## Benchmarking without spending quota

- Use structural metrics (command + capsule bytes/lines vs the pasted prompt
  they replace) for design feedback — labeled structural, never tokens.
- Accumulate real-session exports naturally from future workstreams; compare
  per-workstream aggregates, not single-turn anecdotes.
- Do not run a paid A/B model campaign for WS78.

## Structural before/after (STRUCTURAL, not tokens)

A bespoke pasted prompt carries at minimum the contract plus the full state:

- before: contract 11386 B / 264 lines + state 6428 B / 115 lines
  = 17814 B / 379 lines (policy/evidence/handoffs extra in practice).
- after: `/work` 451 B / 12 lines + capsule ~2745 B / 30 lines
  = ~3196 B / ~45 lines — about 82% fewer structural bytes for the
  launch prompt. Full state/contract remain one `--full` / file-read away.

## Regression protection

`tests/unit/test_ws78_token_economy.py` (22 tests, hermetic) locks the
capsule (happy path, determinism, `--full`, env default, no leakage,
six fail-closed cases), the `/work` shape and size, the config defaults and
permission/model/provider/instruction invariants, the policy layers, and the
launcher bundle passthrough/rejection.

## TUI prompt form (WS198; pinned CLI 1.18.30, DIRECTLY_VERIFIED)

`/work` is the TUI path. Headless reruns pass a bare message
(`opencode run --auto <message>`), but TUI prompt injection must use
`--prompt "<task>"` (launcher spelling: `-- --prompt "<task>"`): TUI syntax
is `opencode [project]`, so bare positional text is bound to the project path
and fails (`Failed to change directory`, yet child exit 0). Canonical
semantics: `docs/foundry-execution/AUTONOMY.md` §9; enforcement:
`launcher.canonicalize_tui_extras`.
