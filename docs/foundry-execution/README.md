# Foundry Execution System — Canonical Index

Single coherent entry point for the OpenCode Foundry execution system on
`moeendres-png/commander-playtest-lab`.

| Surface | Canonical path | Role |
|---|---|---|
| Durable agent rules | `AGENTS.md` (root) | Non-negotiable invariants for every session |
| Machine config | `opencode.json` (root) | DeepSeek MAX default; explicit Space Bunny MAX secondary; permissions; sharing off |
| Routing and effort | `docs/foundry-execution/ROUTING_AND_EFFORT.md` | Canonical routing, effort, Work gate |
| Workspace access | `docs/foundry-execution/WORKSTREAM_CONTRACT_TEMPLATE.md` + launcher `--workspace-access` | Unique verified reference snapshots + standalone current-workstream owned-write surfaces + Bubblewrap read-only-root boundary |
| Explicit execution profiles | `docs/foundry-execution/EXECUTION_PROVIDER_OVERRIDE.md` | DeepSeek MAX default, Space Bunny MAX secondary, retired Zen, no fallback |
| Technical authority | `docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md` | Sol / DeepSeek MAX / Space Bunny MAX / Astra authority model |
| Contract template | `docs/foundry-execution/WORKSTREAM_CONTRACT_TEMPLATE.md` | Task fields incl. decision authority |
| Governance supersession | `docs/foundry-execution/GOVERNANCE_SUPERSESSION.md` | PR #161/#166/#167 dispositions |
| Governance propagation | `docs/foundry-execution/GOVERNANCE_PROPAGATION.md` | PR #172 governance-line propagation; `RETAINED_EVIDENCE_IMPACT = NO_SEMANTIC_IMPACT` when governance-only |
| Implementer agent | `.opencode/agents/foundry-implementer.md` | Primary long-running worker (DeepSeek MAX primary executor) |
| Adjudicator agent | `.opencode/agents/foundry-adjudicator.md` | Read/test-first technical adjudicator (native `max`) |
| Reviewer agent | `.opencode/agents/foundry-reviewer.md` | Fresh-context read-only review |
| Skills | `.opencode/skills/*/SKILL.md` | workstream-bootstrap, failure-classification, test-impact, evidence-seal, continuation, component-change-review, rules-authority-escalation |
| Workstream state | Explicit dedicated state path per workstream (`--state`, exposed as `FOUNDRY_STATE_PATH`) + `.foundry/WORKSTREAM_STATE.schema.json` | Resumable index + validator |
| Deterministic tools | `tools/foundry/` (20 modules) | `launcher.py`, `state.py`, `source_lock.py`, `writer_lock.py`, `workspace_access.py`, `evidence.py`, `metrics.py`, `context_capsule.py`, `safe_push.py`, `drift_check.py` |
| Tool tests | `tests/foundry/test_foundry_tools.py` | Deterministic behavior gates |
| Compaction record | `docs/foundry-execution/COMPACTION_AND_RESUMABILITY.md` | `COMPACTION_HOOK = DEFERRED` + reason |
| Metrics | `docs/foundry-execution/METRICS.md` + `tools/foundry/metrics.py` | JSONL session records |
| Benchmark design | `docs/foundry-execution/HIGH_XHIGH_BENCHMARK.md` | Historical harness design, superseded; no claimed results |
| Current workstream | Explicit user assignment + dedicated state/contract | Historical handoffs never select the next task |

Historical research, dated reports, and superseded proposals stay where they are and
keep their facts; only their execution-routing instructions are superseded, per
`GOVERNANCE_SUPERSESSION.md`. Do not rewrite historical evidence to look current.

## Workstream state writes (canonical)

Explicit-state authority (Coordinator decision ROOT_STATE_SEMANTICS,
2026-09-13): every substantive workstream uses an explicit dedicated state
path. `tools/foundry/launcher.py` and `tools/foundry/bootstrap.py` require
`--state` and never silently fall back to an implicit repository-root state.
There is no implicit active repository-root state. Historical state
snapshots under research/evidence paths are evidence, not continuation
state.

- Never hand-concatenate a state file. Free-form scalars (colons,
  `#`, quotes, newlines, Unicode) break naive YAML and have blocked
  checkpoints before.
- Use the canonical writer: `tools/foundry/state.py --patch-file PATCH
  --state FILE` for checkpoints (full replacement via `--write-from INPUT`;
  explicit `--set-validated-head SHA` / `--clear-validated-head` for credit;
  `--stamp-head --workdir DIR` for the descriptive HEAD stamp), or
  `write_state` / `update_state` from Python. Writes are validated before
  replace, identity-locked, and atomic; failures leave the prior file
  byte-identical.
- Validate after every material checkpoint (`state.py --state FILE` for the
  explicit dedicated state path, plus `--workdir` / `--check-validated` ancestry where credit is claimed).
- `validated_head` means actual validation evidence for that commit, never
  merely current HEAD. `null` is the honest default.

## Skill precedence

Repository-local project skills under `.opencode/skills/` take precedence over
similarly named global Foundry skills for Commander Simulator Next semantics.
The project-local `workstream-bootstrap`, `failure-classification`,
`test-impact`, `evidence-seal`, and `continuation` skills are authoritative in
this repository. Do not edit user-global skills from this workstream.

## Permission model (summary)

Root `opencode.json` is the single permission authority; agents inherit it and
must not widen it. `foundry-implementer` carries no agent-local permission
override. `foundry-adjudicator` narrows to `edit: deny`, ask-gated
`pytest`/`python`/`ruff`/`gh api`, and denied destructive/remote/mutation
paths. `foundry-reviewer` stays fully contained (`edit: deny`,
`bash: deny` except read-only Git). Root `gh api*` is allowed for authorized project work; narrower agent-specific
permissions still apply. Configured permission is not ownership or scope authority.
Rebase and destructive worktree/branch deletion remain denied. No method-sensitive
GitHub permission enforcement is claimed.


### Bubblewrap prerequisite for cross-workstream runs

Cross-workstream `--reference` / `--workspace-access` launches require Linux
`bwrap` (Bubblewrap). The launcher fails closed if it is unavailable or cannot create
the mount namespace. There is no Landlock-only or unsandboxed fallback. Installation is an
operator/environment provisioning step; OpenCode workers must not bypass `sudo` policy
or self-install privileged dependencies.
