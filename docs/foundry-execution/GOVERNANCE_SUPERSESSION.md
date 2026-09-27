# Governance Supersession — PR #161, #166, #167

> **Currency note (WSR23, 2026-09-27, verified against `origin/main@c5f9418e`).** The
> consolidation branch named below (`project/opencode-execution-system-consolidation-20260910`,
> based on `origin/main@b3f5a9929aaf07d2ae574724bbe198b5ab402df6`) produced this
> record and remains its historical author, but it is **no longer the successor governance
> line**: it is 0 commits ahead of and 420 commits behind current `main`. The live
> governance line is `main` itself, plus open PR #261
> (`ops/dual-executor-governance-hardening-20260927`, head `0699a5f2`), which owns
> `AGENTS.md`, `opencode.json`-adjacent routing docs, `docs/foundry-execution/README.md`
> and `docs/foundry-execution/ROUTING_AND_EFFORT.md`. Read the dispositions below as
> historical Coordinator input, not as the current routing authority.
>
> The three dispositions were re-verified by WSR23 against current `main` and still hold;
> per-PR evidence is in `docs/project_integration_hygiene_20260927/OPEN_PR_CLASSIFICATION.json`
> and `SUPERSESSION_LEDGER.json`. One cross-reference in the PR #166 entry was corrected
> from `AGENTS.md` §11 to §12 (Privacy) in the same change.

Do not merge the PRs below wholesale. Recommended dispositions are
for the Coordinator; no remote PR state was changed by the workstream that wrote this record.

## PR #161 — `chore/foundry-agents-policy` (@ `26409b932d540ba823ccc70e2187227cdae52329`)

Reusable: two-agent topology (implementer primary, reviewer read-only subagent);
skill-shaped operating guidance; workstream-state template concept; harness
portability and continuation discipline; concise-durable `AGENTS.md` structure.

Obsolete or conflicting: stale Muse SKU (`opencode/muse-spark-1.3-contributor-free`,
Zen free routing — the project uses paid `opencode-go/muse-spark-1.3-contributor`);
`opencode.jsonc` uses the invalid `permissions` array key (the pinned CLI schema
accepts only singular `permission`); `compaction.keep.tokens` and `buffer` fields do
not exist in the schema; `subagent` permission action does not exist (it is `task`);
deletes `.github/workflows/opencode.yml`, removing the pinned execution lane;
Codex Terra/Luna/Sol routing predates the final adjudication.

Recommendation: `CLOSE_AFTER_CONSOLIDATION`. Its valid concepts are incorporated here
in schema-correct form; its config and routing are superseded.

## PR #166 — `ops/opencode-muse-primary-privacy-20260908` (@ `22e2a20fe2fab595f0bc01e40cf00dbdd4af856e`)

Reusable: HIGH as the normal Muse effort; project-relevant engineering data broadly
allowed; unrelated personal/private data excluded; raw secrets `LOCAL_ONLY` with
local consumption permitted but model disclosure forbidden; broad local engineering
freedom with destructive/external operations gated; session sharing disabled.

Obsolete or conflicting: based on a WS49 branch, so it carries a large unrelated
WS49 qualification payload that must not enter governance; references
`docs/operations/AI_EXECUTION_AND_PRIVACY_POLICY.md`, which does not exist on `main`;
Work/Work-chat effort prescriptions predate the final routing adjudication.

Recommendation: `REBASE/REWORK` in spirit — extract only the privacy-boundary
concepts (already incorporated into `AGENTS.md` §12 Privacy and the `opencode.json`
`permission` block), then `CLOSE_AFTER_CONSOLIDATION`. Never merge wholesale.

## PR #167 — `project/resource-constrained-execution-policy-20260908` (@ `633f51ae68b4908228afdb4354029163e24b903c`)

Reusable: Sol High as Coordinator/adjudication tier; OpenCode+Muse as execution tier;
Work/Astra exceptional with `WORK_NECESSITY`; Commander scope statements; source and
evidence invariants; `experimental.policies` provider gating; variant-disabling
mechanism for below-HIGH efforts.

Obsolete or conflicting: makes XHIGH the default effort — superseded by the final
adjudication (HIGH default, XHIGH escalation); `variants` entries carry
`reasoningEffort`, which the config schema forbids (only `disabled` is allowed per
variant); missing `share: disabled`; the `AGENTS.md`/policy copy on that branch is
not on `main`.

Recommendation: `SUPERSEDE`. This consolidation branch replaces it as the governance
line; its valid concepts are incorporated here with HIGH as the default.
