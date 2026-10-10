# Native review lane: actual reviewer selection (#654)

Checkpoint, 2026-10-10. Takes over the Codex-owned #654 implementation.

## Cause (pinned CLI 1.18.30)

`opencode github run` never reads `AGENT`. `github.handler.ts`
(blob `fcf44279ce7f2c764ed86771d913f784bf584746`) sends every prompt without an
agent, so the server uses `default_agent` from the resolved config, which
`opencode.json` sets to the writable `foundry-implementer`. Run 37936416385 /
job 113839482326 logged `agent: "foundry-implementer"` while the workflow said
`AGENT=foundry-reviewer`.

## Repair

- **Selection.** The `opencode-bunny-review` job sets
  `OPENCODE_CONFIG_CONTENT='{"default_agent":"foundry-reviewer"}'`. `config.ts`
  merges that variable after every project config file, so it overrides
  `default_agent` without touching the implementation lanes.
- **Preflight** (`tools/foundry/review_runtime_identity.py preflight`, copied
  from `${GITHUB_SHA}`, before the run): asks the pinned CLI for its resolved
  config and reviewer (`opencode debug config`, `opencode debug agent
  foundry-reviewer`) and fails unless the default agent is the reviewer on
  `opencode-go/space-bunny` variant `max`, no write tool is offered, and the
  merged ruleset refuses all 38 write probes (edit, task, push/commit/add,
  `--output`, redirects, gh writes, arbitrary exec).
- **Audit** (after the run): the watchdog copies the output (`--log`); every
  logged model call must be the reviewer on Space Bunny (only the tool-less
  `title` agent may appear, on the small model). No reviewer call recorded is
  UNKNOWN and fails the job. The preflight is repeated on the tree the run
  checked out.
- **Admission** (`review_evidence.py`): a workflow pin is admitted only with
  that exact override, the preflight/log/audit steps in order and unskippable,
  no `OPENCODE_CONFIG*`/`OPENCODE_PERMISSION`/`GITHUB_ENV` bypass and no
  `continue-on-error`; the committed `opencode.json` merged with the reviewer's
  rules (last match wins, as `permission/index.ts`) must refuse every write
  probe. `AGENT` alone is refused.
- **Reviewer surface.** `foundry-reviewer.md` now also denies `*--output*` and
  `*>*`: `git diff/log/show` could write files through them.

## Evidence

PASS (local, real pinned CLI 1.18.30, sha256-verified release asset):

- `opencode debug config` resolves `default_agent` to `foundry-implementer`
  without the override and to `foundry-reviewer` with it;
- preflight with the override: PASS (38 write probes refused, read-only Git
  allowed); env-only `AGENT`: BLOCKED;
- preflight against the previous reviewer file: BLOCKED on the five
  `--output`/redirect probes.

Unit controls: `tests/foundry/test_review_runtime_identity.py` (real
implementer record from job 113839482326 refused) and the #654 section of
`tests/foundry/test_review_evidence.py`.

NOT_RUN: a native `/bunny-review` run on GitHub. It needs a functioning
provider; until then no native review certificate is claimed and #651-style
reviews stay BLOCKED. Residual: the audit trusts the CLI's own log format
(`stream {` blocks); a missing format fails closed.
