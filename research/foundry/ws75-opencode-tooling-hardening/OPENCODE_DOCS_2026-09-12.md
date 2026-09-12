# WS75 — Current Official OpenCode Docs Record (2026-09-12)

Primary authority for WS75 remediations 1, 5, 6, 7, 10. Community posts
were not used. All pages fetched 2026-09-12; each page footer states
"Last updated: Sep 10, 2026".

## Sources

- CLI (run syntax, serve/attach/session/export behavior, env vars):
  https://opencode.ai/docs/cli/
- Permissions (`--auto` semantics, `external_directory`, `doom_loop`,
  agent permission merge, wildcard rules, ask outcomes):
  https://opencode.ai/docs/permissions/
- Agents (primary vs subagent, permission keys incl. `doom_loop`,
  JSON vs Markdown configuration, last-match-wins):
  https://opencode.ai/docs/agents/
- Release tag v1.18.30 (published 2026-09-09T03:34:27Z):
  https://api.github.com/repos/sst/opencode/releases/tags/v1.18.30
  (assets served under `github.com/sst/opencode/releases/download/v1.18.30/`;
  the API asset list mirrors the `anomalyco/opencode` fork remote).

## Recorded semantics (direct quotes / close paraphrase)

### Headless run syntax (remediation 1)

- `opencode run [message..]` — "Run opencode in non-interactive mode by
  passing a prompt directly… useful for scripting, automation, or when you
  want a quick answer without launching the full TUI."
- Headless flags include `--auto`: "Auto-approve permissions that are not
  explicitly denied".
- The permissions page gives the exact canonical headless form:
  `opencode run --auto "Refactor this module"`.
- `opencode run --attach http://localhost:4096 "..."` attaches to a
  running `opencode serve` instance.
- Consequence: the pre-WS75 launcher shape `opencode --auto <argv>`
  (binary flag before any subcommand, extras appended) is NOT the
  documented headless form; `run` must come first, `--auto` after `run`.
  The WS67/WS74 `/tmp` wrapper existed only to repair this order.

### TUI mode (remediation 1)

- Bare `opencode` (optionally `opencode [project]`) starts the TUI.
- The TUI flag table lists `--auto` ("Auto-approve permissions that are
  not explicitly denied"), so the preserved TUI form is
  `opencode --auto <extra...>` with no `run` subcommand.

### `--auto` semantics (remediations 1, 5)

- "Start OpenCode with `--auto` to automatically approve permission
  requests that are not explicitly denied."
- 'Explicit `"deny"` rules are still enforced. Auto mode only changes
  requests that would otherwise ask for approval.'
- Ask outcomes in interactive UI: `once` / `always` / `reject`.
- Consequence: any `ask` rule (including `doom_loop: ask`) is
  auto-approved under `--auto`; repetition protection must be `deny`.

### `permissions` / `external_directory` (remediations 4, 5, 9)

- Actions: `"allow"` (run without approval), `"ask"` (prompt), `"deny"`
  (block).
- "Rules are evaluated by pattern match, with the **last matching rule
  winning**. A common pattern is to put the catch-all `"*"` rule first,
  and more specific rules after it."
- Wildcards: `*` matches zero or more of any character; `?` matches
  exactly one; all else literal.
- `external_directory`: "triggered when a tool touches paths outside the
  project working directory"; "allow tool calls that touch paths outside
  the working directory where OpenCode was started. This applies to any
  tool that takes a path as input (for example `read`, `edit`, `glob`,
  `grep`, and many `bash` commands)."
- "Keep the list focused on trusted paths" — supports the WS75 rule:
  never broad `/home/moeen/code/**` write access; exact declared
  reference roots only, read-only by instruction.
- Defaults: 'Most permissions default to `"allow"`. `doom_loop` and
  `external_directory` default to `"ask"`.'

### Agent permissions (remediations 3, 5)

- "Agent permissions are merged with the global config, and agent rules
  take precedence."
- Markdown frontmatter and JSON `agent:` block both supported; permission
  keys accept shorthand or glob→action objects for `read`, `edit`,
  `glob`, `grep`, `list`, `bash`, `task`, `external_directory`, `lsp`,
  `skill`; remaining keys (incl. `doom_loop`) are shorthand-only.
- `doom_loop`: "Recovery prompts when an agent appears stuck"; per the
  permissions page it fires "when the same tool call repeats 3 times with
  identical input".

### serve / attach / session behavior (remediation 10)

- `opencode serve` — "Start a headless OpenCode server for API access";
  basic auth via `OPENCODE_SERVER_PASSWORD` (username defaults
  to `opencode`).
- `opencode attach [url]` — "Attach a terminal to an already running
  OpenCode backend server started via `serve` or `web`".
- `opencode web` — headless server plus web interface.
- `opencode export [sessionID]` — "Export session data as JSON" (with
  `--sanitize` to redact); `opencode import <file>` restores.
- `opencode session list|delete`, `opencode stats`, `opencode models`
  are read/aggregate-only surfaces used by telemetry qualification.
- Env injection actually used by the launcher is documented verbatim:
  `OPENCODE_CONFIG_DIR` ("Path to config directory"),
  `OPENCODE_CONFIG_CONTENT` ("Inline json config content").

## What was NOT taken from docs

- Wildcard `matches()` replication and last-match-wins ordering in
  `tools/foundry/permission_battery.py` remain CODE_DERIVED from the
  pinned CLI resolver output (`opencode debug agent`), not from prose.
- Version/asset trust comes from downloaded bytes + SHA256, never from
  release-page prose.
