# Commander Simulator Next — Current Execution Authority

Status: **CANONICAL / CURRENT**

Effective date: **2026-10-13** (DeepSeek V4.1 Flash on OpenCode Go only; previous revision 2026-10-12, Step 5 Preview only)

This file is the stable current routing authority for OpenCode/Foundry execution and the Claude Opus 5.5 delegation pointer.
It supersedes older model-routing instructions in dated handoffs, research packets,
historical workstream state, donor reports, chats and superseded governance records.

## Authorized OpenCode executors

By direct Owner instruction of **2026-10-13** ("OpenCode soll wieder OpenCode Go über die
aktuelle API im GitHub laufen"), whenever this project uses OpenCode it uses exactly one
model: **DeepSeek V4.1 Flash on OpenCode Go** (provider `opencode-go`). Nothing else. This
holds for every lane (`/oc`, `/assure`, `/ro-review`), the Foundry launcher, Claude-side
OpenCode calls and every OpenCode subagent. This reverses the Step-only routing of
2026-10-12.

1. **DeepSeek v4.1 Flash MAX** (ACTIVE, default, only executor)
   - profile: `deepseek`
   - model: `opencode-go/deepseek-v4.1-flash`
   - native variant: `max` (its highest catalog level; the only variant enabled).
   - the OpenCode Go monthly quota was exhausted on 2026-10-10 (HTTP 429
     `GoUsageLimitError`). Its recovery is **assumed by the Owner and not verified**; the live
     pinned-CLI catalog (`opencode models opencode-go`) and the first trusted CI lane run are the
     reverification. A Go refusal (quota, auth, catalog) is `BLOCKED_SERVICE`, never a fallback
     to another model or provider.
   - Claude sessions may start it through the `opencode` CLI
     (`opencode run -m opencode-go/deepseek-v4.1-flash --variant max`) or the
     `opencode-subagent` MCP bridge.

2. **Step 5 Preview HIGH** (SUSPENDED)
   - profile: `step`
   - model: `opencode/step-5-preview-free` (OpenCode Zen)
   - native variant: `high`
   - suspended by the Owner directive of 2026-10-13. The launcher refuses the profile, it is
     absent from `opencode.json`, and no lane pins it. Only a new direct Owner instruction sets
     it back to ACTIVE in `.foundry/executor-profiles.json`.

Claude Sonnet 5.5 is an additionally authorized executor/worker tier next to OpenCode (Owner
decision). It is not an OpenCode profile, is not a Foundry launcher profile, and works under the
same ownership, evidence and Git gates.

Every earlier OpenCode executor is retired and removed from the active configuration;
its history stays in Git and in dated records only.
No other OpenCode model/profile is currently authorized or a planned migration target.
Prompting guidance for the active model: `docs/foundry-execution/EXECUTOR_PROMPTING.md`.

## Cross-executor review gate (Foundry tooling)

This is a Foundry tooling gate, not a change to Rules, evidence semantics,
qualification credit or provider/freeze authority. `tools/foundry/review_gate.py`
refuses to certify a `PR_READY` or `COMPLETE` claim for a MATERIAL implementation
workstream unless the record carries a fresh-context READ-ONLY DeepSeek MAX PASS on
the exact validated implementation SHA and TREE. Step 5 Preview implementation or review does
not satisfy the gate (suspended). While Step 5 Preview is SUSPENDED and DeepSeek is the only
ACTIVE profile, a DeepSeek implementation reviewed by DeepSeek is admitted (explicit
Owner approval of 2026-10-10 for the single-executor case; the Coordinator applies it to DeepSeek
from 2026-10-13, the same situation): its independence then rests only on the fresh context and the
read-only `/ro-review` lane, not on a second model, and it is recorded as same-model
review. As soon as another profile is ACTIVE again, self-review is refused; a missing, blocked, unknown, partial, failed or stale
review blocks the tooling claim, and any MATERIAL change after the review requires exact
new-SHA/TREE re-review. A PASS record is only admissible with independently verifiable
GitHub evidence of the trusted `/ro-review` run (trusted trigger comment, expected
job, canonical DeepSeek workflow pin and structurally read-only
`foundry-reviewer` agent file at the run's exact `head_sha`, the OpenCode bot's
machine-parseable receipt, and the comment/run time and footer-link binding);
self-declared record fields can never fabricate a review. `REVIEWER_MODEL`,
`REVIEWER_VARIANT` and `READ_ONLY` inside the receipt are self-reported text checked
for equality only; the run pin and agent file are the independently observed facts, and
the runtime alias is never observed. The canonical structures and verifiers live in
`tools/foundry/review_gate.py` and `tools/foundry/review_evidence.py`; remote milestone
checkpoints are verified through `tools/foundry/safe_push.py` and
`tools/foundry/remote_checkpoint.py`. A pushed WIP is never qualification PASS.

## Routing

DeepSeek MAX runs all OpenCode engineering work: implementation, debugging, CI repair,
qualification execution, evidence production, audits and reviews. The lanes differ by
agent and permissions (`foundry-implementer` on `/oc`, `assurance-verifier` on `/assure`,
read-only `foundry-reviewer` on `/ro-review`), not by model.

There is **no automatic fallback**. Runtime, quota, auth, catalog, tool or child failure
ends the selected run; it never re-resolves to Step 5 Preview or any other executor.

The project-level `--effort high|xhigh` field describes task/authority routing only.
It does not lower the executor's provider-native compute: DeepSeek stays pinned to
its highest native level, `max`.

## Historical executor references

Historical files may name earlier executor experiments. Those references are provenance
only. They do not authorize current execution, do not imply future migration work, and
must not by themselves generate a governance/routing issue.

Do **not** open or revive a model-migration issue merely because historical evidence
mentions another executor. Expanding or replacing the active two-profile allowlist
requires a new direct user instruction that explicitly changes this authority.
Re-activating the suspended Step 5 Preview profile likewise requires a new direct user instruction.

Historical evidence must remain readable; do not rewrite old evidence to pretend it was
generated by the current executor pair.

## Authority boundaries

Executor choice never changes Rules authority, evidence semantics, hidden-information
rules, fail-closed requirements, Source Truth, provider-selection authority or
Architecture Freeze authority.

Production Provider selection and Architecture Freeze remain separate Owner gates, with the other Owner-only items in `AGENTS.md` §8.

## Claude Opus 5.5 delegation

Effective 2026-10-05, by direct Owner instruction, an explicitly launched Claude Opus 5.5
engineering session holds the Coordinator tier's decision authority. The scope, the
Owner-only reservations and the non-relaxable invariants are defined in `AGENTS.md` §8,
"Claude Opus 5.5 Coordinator authority". It does not change the OpenCode executor
allowlist or the native-variant pinning above.

`PRODUCTION_PROVIDER = XMAGE` (selected at the Freeze; the D5 application runtime switch to
the full-game lane is done, `provider_decision = XMAGE_SELECTED`.)

`ARCHITECTURE_FREEZE = CLAIMED` (2026-10-10, Owner-signed:
`docs/architecture_freeze_20261010/ARCHITECTURE_FREEZE_ADR.md`)
