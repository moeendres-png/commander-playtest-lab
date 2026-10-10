# Commander Simulator Next — Current Execution Authority

Status: **CANONICAL / CURRENT**

Effective date: **2026-10-10** (Space Bunny MAX only; previous revision 2026-10-02)

This file is the stable current routing authority for OpenCode/Foundry execution and the Claude Opus 5.5 delegation pointer.
It supersedes older model-routing instructions in dated handoffs, research packets,
historical workstream state, donor reports, chats and superseded governance records.

## Authorized OpenCode executors

By direct Owner instruction of **2026-10-10** exactly one OpenCode execution profile is
ACTIVE, for every lane: `/oc`, `/bunny`, `/bunny-review`, the Foundry launcher, the
Claude-side `opencode-subagent` MCP and every OpenCode subagent.

1. **Space Bunny MAX** (ACTIVE, default, only executor)
   - profile: `space-bunny`
   - model: `opencode-go/space-bunny`
   - native variant: `max`
   - resolves only after live pinned-CLI catalog inspection; if the canonical id is
     absent, the admitted legacy runtime alias `opencode-go/space-bunny-free`
     (`LEGACY_ALIAS`, the same logical `space-bunny` profile) may be selected. Neither
     present => fail closed. The alias is a runtime identity, never a third executor.

2. **DeepSeek v4.1 Flash MAX** (SUSPENDED)
   - profile: `deepseek`
   - model: `opencode-go/deepseek-v4.1-flash`
   - native variant: `max`
   - suspended by Owner directive after the OpenCode Go monthly quota was exhausted. Note:
     on 2026-10-10 (workflow run 38049493597) `opencode-go/space-bunny` calls were refused by
     the same monthly limit (HTTP 429 `GoUsageLimitError`), so Space Bunny runs stay
     `BLOCKED_SERVICE` until the quota resets or the Owner restores it. The launcher refuses the profile, it is absent from
     `opencode.json`, and no lane pins it. Only a new direct Owner instruction sets it
     back to ACTIVE in `.foundry/executor-profiles.json`; quota recovery alone does not.

No other OpenCode model/profile is currently authorized or a planned migration target.
Prompting guidance for the active model: `docs/foundry-execution/SPACE_BUNNY_PROMPTING.md`.

## Cross-executor review gate (Foundry tooling)

This is a Foundry tooling gate, not a change to Rules, evidence semantics,
qualification credit or provider/freeze authority. `tools/foundry/review_gate.py`
refuses to certify a `PR_READY` or `COMPLETE` claim for a MATERIAL implementation
workstream unless the record carries a fresh-context READ-ONLY Space Bunny MAX PASS on
the exact validated implementation SHA and TREE. DeepSeek implementation plus DeepSeek
review does not satisfy the gate. While DeepSeek is SUSPENDED and Space Bunny is the only
ACTIVE profile, a Space Bunny implementation reviewed by Space Bunny is admitted (explicit
Owner approval, 2026-10-10): its independence then rests only on the fresh context and the
read-only `/bunny-review` lane, not on a second model, and it is recorded as same-model
review. As soon as another profile is ACTIVE again, self-review is refused; a missing, blocked, unknown, partial, failed or stale
review blocks the tooling claim, and any MATERIAL change after the review requires exact
new-SHA/TREE re-review. A PASS record is only admissible with independently verifiable
GitHub evidence of the trusted `/bunny-review` run (trusted trigger comment, expected
job, canonical Space Bunny MAX workflow pin and structurally read-only
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

Space Bunny MAX runs all OpenCode engineering work: implementation, debugging, CI repair,
qualification execution, evidence production, audits and reviews. The lanes differ by
agent and permissions (`foundry-implementer` on `/oc`, `bunny-verifier` on `/bunny`,
read-only `foundry-reviewer` on `/bunny-review`), not by model.

There is **no automatic fallback**. Runtime, quota, auth, catalog, tool or child failure
ends the selected run; it never re-resolves to DeepSeek or any other executor.

The project-level `--effort high|xhigh` field describes task/authority routing only.
It does not lower the executor's provider-native compute: Space Bunny stays pinned to
native `max`.

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
allowlist or the native `max` pinning above.

`PRODUCTION_PROVIDER = NOT_SELECTED`

`ARCHITECTURE_FREEZE = NOT_CLAIMED`
