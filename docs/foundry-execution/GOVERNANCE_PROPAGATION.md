# Governance Propagation Contract — After PR #172 Merge

This is the canonical procedure for carrying the PR #172 execution-system
governance line into active branches. It applies only after PR #172 merges to
`main`. Do not anticipate the merge: before merge, `main` does not carry the
canonical execution system.

## Required procedure (in order)

1. Verify the governance delta against the active branch:
   `git diff main...<branch> -- opencode.json .opencode/ AGENTS.md
   docs/foundry-execution/ tools/foundry/ tests/foundry/
   .foundry/WORKSTREAM_STATE.schema.json`. Record exact SHAs/trees.
2. Require only expected governance/tooling paths unless separately
   adjudicated. Any semantic change under `src/`, `engine-bridge/`,
   `qualification/`, `vendor/`, or provider/fixture surfaces stops the
   propagation and needs its own contract.
3. Determine semantic impact: governance-only (config, agents, skills, docs,
   deterministic helpers, tests for those helpers) vs semantic surface
   changed. Be conservative: uncertain impact is semantic impact.
4. If governance-only and no semantic surface changed, record
   `RETAINED_EVIDENCE_IMPACT = NO_SEMANTIC_IMPACT` with the adjudication
   reason. Historical qualification PASS is retained on impact grounds, not
   rerun for reassurance.
5. Integrate governance into that branch (merge `main` or cherry-pick only
   the governance paths, never WS48/WS49 semantics). Resolve conflicts in
   favor of the canonical PR #172 line unless the Coordinator adjudicates
   otherwise.
6. Update Source Lock and state: new audit-base SHA/tree, current HEAD,
   `validated_gates` entry for the propagation, and the exact next action.
   Validate with `tools/foundry/state.py` and `tools/foundry/source_lock.py`.
7. Do not rerun qualification for reassurance after a governance-only
   propagation. Rerun only the smallest surface covering adjudicated impact
   (typically `pytest tests/foundry/ -q`, ruff, state/source-lock self-checks,
   pinned-CLI smoke where required).

## Inheritance and isolation

- All new workstreams created from updated `main` inherit governance
  normally via the workstream-bootstrap gate. No extra propagation step.
- Do not use one governance checkout to write across independent worktrees.
  One workstream ↔ one branch ↔ one worktree. Cross-worktree writes require
  their own owning workstream and approval gate.

## Evidence

Record the delta SHAs, the path allow-list check, the semantic-impact
decision with reason, the `RETAINED_EVIDENCE_IMPACT` value, the new Source
Lock, and the scoped validation output. Missing evidence stays `UNKNOWN`.
