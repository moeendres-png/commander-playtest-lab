# WS78 — Foundry Token-Economy Hardening

## Repository

`moeendres-png/commander-playtest-lab`

## Branch / Ownership

- branch: `ws78/foundry-token-economy-20260913`
- owner: WS78 Foundry Token-Economy Hardening
- one writer only

## Source Lock / AUDIT_BASE_SHA

- audit base SHA: `90f95c117b190d6b21704ca7639198e3ac0a2dc2`
- audit base tree: `ed83951226f52f528953e7cdb0dec0b12e6eabcc`
- contract/research seed commit is a Coordinator-authored descendant on this branch

Before implementation, verify current branch/HEAD/tree/cleanliness and that the audit base
is ancestral. Do not rebase onto moving `main` without Coordinator adjudication.

## Objective

Make future OpenCode Go + Muse Spark 1.3 Contributor HIGH/XHIGH workstreams materially
more token/credit efficient **without reducing Rules Correctness, evidence rigor, privacy,
resumability, autonomy, or fail-closed safety**.

The intended operator outcome is that, after the Coordinator has prepared a workstream
contract/state, the human can launch Foundry and type a tiny stable command (target UX:
`/work`) instead of pasting a large bespoke prompt.

Read `research/foundry/ws78-token-economy/RESEARCH_2026-09-13.md` first. Treat its
DIRECTLY_VERIFIED facts and this contract as the bounded starting authority.

## Inputs / Authority

- this contract
- `research/foundry/ws78-token-economy/RESEARCH_2026-09-13.md`
- root `AGENTS.md`
- root `opencode.json`
- `.opencode/agents/foundry-implementer.md`
- existing `.opencode/skills/*`
- `tools/foundry/launcher.py`, `state.py`, `session_stats.py`, `metrics.py`
- exact pinned OpenCode CLI `1.18.30` source/docs

Newest direct Coordinator/user instruction and freshly verified source outrank this seed
if they conflict.

## In Scope

### A. Compact execution capsule

Implement a deterministic read-only Foundry helper that derives a compact execution
capsule from the exact launcher state path and current Git/worktree facts.

Requirements:

- consume `FOUNDRY_STATE_PATH` by default; explicit `--state` override is acceptable;
- fail closed if state is missing/invalid or source-lock identity is contradictory;
- output only execution-critical information by default, not the full state;
- include at least repository/worktree/branch/workstream identity, audit base,
  current HEAD/tree/cleanliness, validated head/status, objective, exact-next-action,
  and only the hard/authority gates needed to avoid unsafe continuation;
- clearly label the capsule as DERIVED/INDEX data, never a replacement source of truth;
- provide a documented opt-in way to inspect full state when needed;
- deterministic ordering/output suitable for tests and prompt injection;
- do not expose secrets or dump environment values.

Prefer extending an existing Foundry helper if that is objectively cleaner than adding a
new file. Avoid duplicate rules engines or duplicate state authority.

### B. Tiny TUI command

Add a project-local OpenCode command (target name `/work`; use another short name only if
an existing command conflicts) that:

- selects the canonical `foundry-implementer` / Muse Spark 1.3 HIGH path;
- injects the compact derived capsule through a deterministic local helper;
- tells Muse to execute/resume the active bounded workstream through Semantic Completion;
- tells Muse to read full state/contract/evidence only when needed;
- does not paste/restate root policy, routing policy, full state, or historical handoff;
- remains useful after an interrupted TUI session.

Verify command-shell interpolation semantics against the pinned OpenCode 1.18.30 source or
qualified docs before relying on it.

### C. Tool-output economy

Evaluate and implement conservative `tool_output.max_lines` / `max_bytes` values in
`opencode.json` if testing supports them.

Hard requirements:

- full oversized output must remain recoverable through OpenCode's managed output path;
- model-visible preview must preserve enough head/tail context for normal diagnostics;
- agent instructions must explicitly prefer reading the saved full output when necessary
  rather than rerunning an expensive command merely because its preview was truncated;
- do not choose thresholds solely to maximize token reduction; quality is the gate.

Use the smallest values that remain robust in representative Foundry test/build/log cases.
If evidence is insufficient, leave the defaults and record `UNKNOWN` rather than guessing.

### D. Compaction/pruning

Enable `compaction.prune: true` only if exact-pin behavior/tests establish that it removes
old tool-output pressure without losing required durable authority.

Do not introduce aggressive `reserved`, `tail_turns`, or
`preserve_recent_tokens` tuning merely to claim savings. Any non-default threshold needs
explicit evidence and a regression test or bounded empirical justification.

### E. Always-on instruction deduplication

Audit the three always-on policy layers:

1. root `AGENTS.md`;
2. `opencode.json` `instructions` files;
3. `.opencode/agents/foundry-implementer.md`.

Remove only **provably redundant** always-on prose where the exact invariant remains
machine-enforced or present in another always-on authoritative layer. Primary candidate:
`docs/foundry-execution/ROUTING_AND_EFFORT.md` being loaded through `instructions` despite
substantial duplication with `AGENTS.md`, model config, and selected agent.

Do **not** aggressively rewrite or shrink root Rules/evidence/privacy/source-truth policy
in WS78. Stable critical policy is cheap when cached and quality outranks token count.
If deduplication cannot be proven safe, keep it.

### F. Session-resume path

Investigate a safe explicit OpenCode-session resume mechanism using the pinned CLI's
`--session` support and existing Foundry run metadata.

- Never use ambiguous blind `--continue` where another live session could be selected.
- Do not fabricate or guess an OpenCode session ID.
- If exact automatic capture/resume cannot be made reliable within bounded scope, document
  it as a follow-up instead of adding fragile behavior.
- A safe optional explicit-session path is preferable to a clever ambiguous one.

### G. Measurement / regression protection

Use existing `session_stats.py` / `metrics.py` rather than inventing token counts.
Add deterministic project tests/guardrails for the new context capsule, command, config,
and policy-dedup behavior.

Create/update a concise `docs/foundry-execution/TOKEN_ECONOMY.md` describing:

- operator workflow;
- what consumes cached vs dynamic context conceptually;
- authoritative metrics to compare (`tokens_input`, `tokens_output`,
  `tokens_cache_read`, `tokens_cache_write`, `cost_usd`, tool calls/turns);
- how to benchmark without spending quota unnecessarily;
- explicit `TOKEN_ECONOMY_BENCHMARK = NOT_RUN` unless real exported sessions were actually
  measured.

Do not run a broad paid A/B model campaign merely to finish WS78. Build the measurement
path first; future real workstreams can accumulate evidence naturally.

## Out of Scope

- any Rules-Core behavior change;
- XMage or Forge source mutation;
- engine repinning;
- Production Provider selection;
- Architecture Freeze;
- Full107/RQ-C3 behavior execution;
- lowering active Muse effort below HIGH;
- replacing Muse Spark 1.3 Contributor;
- weakening fail-closed permissions, evidence semantics, source truth, privacy, writer
  locks, safe_push, or Semantic Completion;
- speculative prompt-cache hacks unsupported by the pinned CLI/provider docs;
- broad rewriting of all governance documentation.

## Hard Gates

1. `QUALITY_NON_REGRESSION`: Rules/evidence/privacy/source-lock/ownership invariants remain
   at least as strong as at the audit base.
2. `PIN_CONFORMANCE`: implementation uses only behavior supported by OpenCode CLI 1.18.30
   unless the Coordinator explicitly opens a version migration.
3. `PROMPT_MINIMALITY`: `/work` must not embed full AGENTS/state/contract/handoff text.
4. `STATE_AUTHORITY`: derived capsule never becomes a second authoritative state store.
5. `TRUNCATION_RECOVERY`: if tool-output limits are reduced, the full-output recovery path
   is verified and documented.
6. `NO_FAKE_SAVINGS`: no estimated token reduction may be presented as measured savings.
7. `METRICS_PROVENANCE`: measured token/cache/cost claims come only from authoritative
   OpenCode exports/session metrics.
8. `PERMISSIONS`: existing deny/ask safety semantics and safe_push governance must remain
   conformant.
9. `HERMETIC_CI`: tests must not require an ambient unpinned OpenCode executable unless
   explicitly skipped/fail-closed under the established WS75 pattern.
10. `NO_BEHAVIOR_CREDIT`: this workstream grants zero MTG Rules/card behavior credit.

## Forbidden Shortcuts

- delete critical policy merely to reduce characters;
- lower HIGH/XHIGH policy;
- disable safety tools/permissions to save calls;
- replace real validation with prose;
- hide or discard full test/log output with no recovery path;
- rerun commands simply because bounded previews exist when saved output is available;
- claim cache hits without metrics;
- manual outcome injection or second Rules Engine semantics;
- direct `git push`; publication must use canonical `tools/foundry/safe_push.py`.

## Evidence Requirements

At minimum:

- exact source lock and final HEAD/tree;
- tests for compact capsule happy path + malformed/mismatched state fail-closed behavior;
- tests for `/work` command structure and no full-policy/state embedding;
- affected Foundry/bootstrap/config/policy tests;
- permission battery where relevant;
- Ruff/format for changed Python;
- config validation against the pinned CLI/schema or the existing hermetic equivalent;
- before/after deterministic **context-size structural metrics** (bytes/lines are allowed if
  labeled structural, not tokens);
- exported token/cache metrics only if a real session was actually measured;
- final diff review proving no semantic weakening.

## Technical Decision Authority

`AUTONOMOUS_WITHIN_CONTRACT`.

Muse HIGH owns bounded implementation decisions and ordinary root-cause work. Escalate to
XHIGH only for genuinely nonlocal causality or a difficult policy-preservation problem.
Only a real Rules/evidence-policy/shared-architecture/provider/freeze/scope-authority issue
returns to Sol High.

## Persistence

Use the workstream's exact launcher-provided state path. Persist validated milestones and
focused commits. Do not rerun valid evidence after interruption unless relevant source,
contract, harness, or configuration changed.

## Stop Conditions

COMPLETE when the bounded token-economy implementation is validated, state is coherent,
canonical safe_push has published the branch, and the handoff identifies any deferred
session-resume or empirical benchmark work.

Stop fail-closed for a genuine authority gate, source-lock contradiction, ownership
conflict, unsupported pinned-CLI behavior, or a proposed optimization that would weaken
quality/safety.

## Required Handoff

Source Lock
Work Completed
New Findings
Changes
Tests / Evidence
PASS / FAIL / UNKNOWN
Token-Economy Evidence (measured vs structural clearly separated)
validated_head
remote HEAD
Remaining Blockers
Outputs
Dependencies Unblocked
Exact Next Action

Exact Next Action on successful publication:
`Coordinator verifies remote head, reviews PR/CI, and merges only if quality-non-regression and token-economy gates pass.`
