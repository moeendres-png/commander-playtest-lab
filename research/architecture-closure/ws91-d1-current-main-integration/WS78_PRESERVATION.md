# WS91 — WS78 Token-Economy Preservation

`WS78_TOKEN_ECONOMY_PRESERVED = PASS`.

## Byte-identical WS78 files (untouched by WS91)

- `tools/foundry/context_capsule.py`
- `.opencode/commands/work.md`
- `opencode.json` (`tool_output.max_lines`, `tool_output.max_bytes`)
- `docs/foundry-execution/TOKEN_ECONOMY.md`
- `tests/unit/test_ws78_token_economy.py`

Verified by: `git diff` shows no modification to these paths in the WS91
working tree; `tests/unit/test_ws78_token_economy.py` remains green.

## Semantic union files (WS78 hunks preserved verbatim + D1 hunks added disjointly)

- `tools/foundry/launcher.py`
  - Kept: `_validated_tool_output` (pinned 1.18.30 positive-int fail-closed
    validation) and `tool_output` propagation in `build_content_bundle`.
  - Added: mandatory explicit `state_path`, `worktree_states` map plumbing,
    fail-closed `LAUNCH_REFUSED` paths, `--state` (required) and
    `--worktree-state` (repeatable) CLI flags.
  - Proven: `git diff 8d0f6849 -- tools/foundry/launcher.py` shows exactly the
    WS78 block and nothing else.
- `.opencode/agents/foundry-implementer.md`
  - Kept: WS78 truncated-output saved-full-output paragraph (tool-call
    ergonomics) and `xhigh` escalation routing.
  - Applied: all 5 D1 explicit-state wordings.
  - Proven: diff review shows both behaviors present, disjoint ranges.

## Negative control (gate 10)

- `/work` + context capsule still function: covered by
  `tests/unit/test_ws78_token_economy.py` (capsule happy path, fail-closed
  behavior, determinism, no leakage; `/work` structure; launcher bundle
  `tool_output` passthrough), run green on the WS91 tree.
