# Foundry Execution System — Canonical Index

Single coherent entry point for the OpenCode/Muse execution system on
`moeendres-png/commander-playtest-lab`.

| Surface | Canonical path | Role |
|---|---|---|
| Durable agent rules | `AGENTS.md` (root) | Non-negotiable invariants for every session |
| Machine config | `opencode.json` (root) | Model, HIGH default, permissions, sharing off |
| Routing and effort | `docs/foundry-execution/ROUTING_AND_EFFORT.md` | Canonical routing, effort, Work gate |
| Technical authority | `docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md` | Coordinator autonomy/adjudication model |
| Contract template | `docs/foundry-execution/WORKSTREAM_CONTRACT_TEMPLATE.md` | Task fields incl. decision authority |
| Governance supersession | `docs/foundry-execution/GOVERNANCE_SUPERSESSION.md` | PR #161/#166/#167 dispositions |
| Governance propagation | `docs/foundry-execution/GOVERNANCE_PROPAGATION.md` | Post-PR172 merge procedure; `RETAINED_EVIDENCE_IMPACT = NO_SEMANTIC_IMPACT` when governance-only |
| Implementer agent | `.opencode/agents/foundry-implementer.md` | Primary long-running worker (HIGH) |
| Adjudicator agent | `.opencode/agents/foundry-adjudicator.md` | Read/test-first technical adjudicator (XHIGH) |
| Reviewer agent | `.opencode/agents/foundry-reviewer.md` | Fresh-context read-only review |
| Skills | `.opencode/skills/*/SKILL.md` | workstream-bootstrap, failure-classification, test-impact, evidence-seal, continuation |
| Workstream state | `.foundry/WORKSTREAM_STATE.yaml` + `.foundry/WORKSTREAM_STATE.schema.json` | Resumable index + validator |
| Deterministic tools | `tools/foundry/` | source_lock, worktree_inventory, cluster_failures, evidence, state, metrics |
| Tool tests | `tests/foundry/test_foundry_tools.py` | Deterministic behavior gates |
| Compaction record | `docs/foundry-execution/COMPACTION_AND_RESUMABILITY.md` | `COMPACTION_HOOK = DEFERRED` + reason |
| Metrics | `docs/foundry-execution/METRICS.md` + `tools/foundry/metrics.py` | JSONL session records |
| Benchmark design | `docs/foundry-execution/HIGH_XHIGH_BENCHMARK.md` | Replay schema, no claimed results |
| Next workstream | `handoffs/CROSS_CANDIDATE_DECISION_PLUMBING_ROOT_CAUSE_AUDIT.md` | Source-locked XHIGH task spec |

Historical research, dated reports, and superseded proposals stay where they are and
keep their facts; only their execution-routing instructions are superseded, per
`GOVERNANCE_SUPERSESSION.md`. Do not rewrite historical evidence to look current.

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
`bash: deny` except read-only Git). Generic `gh api*` is ask-gated for all
roles because OpenCode glob semantics cannot reliably distinguish read
(`GET`) from mutation (`POST`/`PATCH`/`PUT`/`DELETE`); no method-sensitive
enforcement is claimed.
