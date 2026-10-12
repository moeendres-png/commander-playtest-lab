# Commander Simulator Next — Current Execution Authority

Status: **CANONICAL / CURRENT**

Effective date: **2026-10-12** (Step 5 Preview only; previous revision 2026-10-10)

This file is the stable current routing authority for OpenCode/Foundry execution and the Claude Opus 5.5 delegation pointer.
It supersedes older model-routing instructions in dated handoffs, research packets,
historical workstream state, donor reports, chats and superseded governance records.

## Authorized OpenCode executors

By direct Owner instructions of **2026-10-12**, whenever this project uses OpenCode it uses
exactly one model: **Step 5 Preview on OpenCode Zen** (provider `opencode`), because its Zen
quota is free. Nothing else. This holds for every lane (`/oc`, `/assure`, `/ro-review`), the
Foundry launcher, Claude-side OpenCode calls and every OpenCode subagent.

1. **Step 5 Preview HIGH** (ACTIVE, default, only executor)
   - profile: `step`
   - model: `opencode/step-5-preview-free`
   - native variant: `high`. The Owner asked for `max`; the live Zen catalog
     (`opencode models opencode --verbose`, 2026-10-12) lists only `low`, `medium` and `high`
     for this model, so `high` is its highest native level and the only one enabled.
   - resolves only after live pinned-CLI catalog inspection (`opencode models opencode`);
     the Zen id absent => fail closed. A Zen refusal (rate limit, quota, auth) is
     `BLOCKED_SERVICE`, never a fallback to another model or provider.
   - Claude sessions start it through the `opencode` CLI
     (`opencode run -m opencode/step-5-preview-free --variant high`). The Zen free tier
     refuses calls that do not come from the OpenCode client itself ("free tier can only be
     used from within OpenCode", observed 2026-10-12 through the opencode-subagent MCP).

2. **DeepSeek v4.1 Flash MAX** (SUSPENDED)
   - profile: `deepseek`
   - model: `opencode-go/deepseek-v4.1-flash`
   - native variant: `max`
   - suspended by Owner directive after the OpenCode Go monthly quota was exhausted. The
     launcher refuses the profile, it is absent from
     `opencode.json`, and no lane pins it. Only a new direct Owner instruction sets it
     back to ACTIVE in `.foundry/executor-profiles.json`; quota recovery alone does not.

Every earlier OpenCode executor is retired and removed from the active configuration
(Owner directive 2026-10-12); its history stays in Git and in dated records only.
No other OpenCode model/profile is currently authorized or a planned migration target.
Prompting guidance for the active model: `docs/foundry-execution/EXECUTOR_PROMPTING.md`.

## Cross-executor review gate (Foundry tooling)

This is a Foundry tooling gate, not a change to Rules, evidence semantics,
qualification credit or provider/freeze authority. `tools/foundry/review_gate.py`
refuses to certify a `PR_READY` or `COMPLETE` claim for a MATERIAL implementation
workstream unless the record carries a fresh-context READ-ONLY Step 5 Preview PASS on
the exact validated implementation SHA and TREE. DeepSeek implementation plus DeepSeek
review does not satisfy the gate. While DeepSeek is SUSPENDED and Step 5 Preview is the only
ACTIVE profile, a Step 5 Preview implementation reviewed by Step 5 Preview is admitted (explicit
Owner approval of 2026-10-10 for the single-executor case; the Coordinator applies it to Step
from 2026-10-12, the same situation): its independence then rests only on the fresh context and the
read-only `/ro-review` lane, not on a second model, and it is recorded as same-model
review. As soon as another profile is ACTIVE again, self-review is refused; a missing, blocked, unknown, partial, failed or stale
review blocks the tooling claim, and any MATERIAL change after the review requires exact
new-SHA/TREE re-review. A PASS record is only admissible with independently verifiable
GitHub evidence of the trusted `/ro-review` run (trusted trigger comment, expected
job, canonical Step 5 Preview workflow pin and structurally read-only
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

Step 5 Preview runs all OpenCode engineering work: implementation, debugging, CI repair,
qualification execution, evidence production, audits and reviews. The lanes differ by
agent and permissions (`foundry-implementer` on `/oc`, `assurance-verifier` on `/assure`,
read-only `foundry-reviewer` on `/ro-review`), not by model.

There is **no automatic fallback**. Runtime, quota, auth, catalog, tool or child failure
ends the selected run; it never re-resolves to DeepSeek or any other executor.

The project-level `--effort high|xhigh` field describes task/authority routing only.
It does not lower the executor's provider-native compute: Step 5 Preview stays pinned to
its highest native level, `high`.

## Historical executor references

Historical files may name earlier executor experiments. Those references are provenance
only. They do not authorize current execution, do not imply future migration work, and
must not by themselves generate a governance/routing issue.

Do **not** open or revive a model-migration issue merely because historical evidence
mentions another executor. Expanding or replacing the active two-profile allowlist
requires a new direct user instruction that explicitly changes this authority.
Re-activating the suspended DeepSeek profile likewise requires a new direct user instruction.

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
