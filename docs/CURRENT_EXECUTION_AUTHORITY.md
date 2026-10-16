# Commander Simulator Next — Current Execution Authority

Status: **CANONICAL / CURRENT**. Effective 2026-10-16 (Owner instruction: models are
selected manually; previous revision 2026-10-12).

## Executors

The Owner selects the tool and model for each session manually. The rules for every
executor are in `AGENTS.md` §6–§8; this file adds only the technical pointers.

- OpenCode Foundry: the launcher and review gate admit only the profiles defined in
  `tools/foundry/executor_profiles.py` (runtime ids and native variants) and
  `.foundry/executor-profiles.json` (status), with `opencode.json`. Code and configuration,
  not prose, decide which profile can run; a change touches all of them and their tests
  (`tests/foundry/test_executor_profiles.py`). Calls outside the launcher name the
  Owner-selected model explicitly (`-m`), never a tool default. Prompting guidance:
  `docs/foundry-execution/EXECUTOR_PROMPTING.md`; lanes and routing:
  `docs/foundry-execution/ROUTING_AND_EFFORT.md`.
- There is no automatic fallback: a quota, auth, catalog or tool failure ends the run
  (`BLOCKED_SERVICE`); it never re-resolves to another executor.
- Historical executor names in dated records are provenance only and create no migration
  or governance work by themselves. Do not rewrite old evidence to pretend the current
  executor produced it.

## Cross-executor review gate (Foundry tooling)

`tools/foundry/review_gate.py` certifies a `PR_READY` or `COMPLETE` claim for a MATERIAL
Foundry workstream only with a fresh-context read-only `/ro-review` PASS on the exact
validated SHA and TREE, backed by independently verifiable GitHub evidence of that run
(trusted trigger, expected job, workflow pin, structurally read-only `foundry-reviewer`
agent file at the run's `head_sha`, the bot's parseable receipt). Self-declared record
fields cannot fabricate a review; `REVIEWER_MODEL`, `REVIEWER_VARIANT` and `READ_ONLY` in
the receipt are self-reported text checked for equality only (the run pin and agent file
are the observed facts). A missing, blocked, unknown, partial, failed or stale review
blocks the claim; self-review is admitted only while a single profile is ACTIVE; any
MATERIAL change after review needs re-review. The
verifiers are `tools/foundry/review_gate.py`, `tools/foundry/review_evidence.py`,
`tools/foundry/safe_push.py` and `tools/foundry/remote_checkpoint.py`. A pushed WIP is
never qualification PASS. This gate changes no Rules, evidence or qualification semantics.

## Authority boundaries

Executor choice never changes Rules authority, evidence semantics, hidden-information
rules, fail-closed requirements, Source Truth, provider-selection or Freeze authority.
Production Provider selection and Architecture Freeze remain separate Owner gates, with the other Owner-only items in `AGENTS.md` §8.

The Claude Opus Coordinator delegation (effective 2026-10-05) is defined in `AGENTS.md`
§8, "Claude Opus 5.5 Coordinator authority".

`PRODUCTION_PROVIDER = XMAGE` (D5 runtime switch done, `provider_decision = XMAGE_SELECTED`).
`ARCHITECTURE_FREEZE = CLAIMED` (2026-10-10, Owner-signed:
`docs/architecture_freeze_20261010/ARCHITECTURE_FREEZE_ADR.md`).
