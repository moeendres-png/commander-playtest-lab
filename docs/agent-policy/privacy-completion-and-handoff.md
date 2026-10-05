# Agent Policy — Privacy, Completion and Handoff

Routed from repository-root AGENTS.md. Read this document whenever privacy/secrets, stop conditions, semantic completion, persistence, checkpoints or terminal handoff are material.

Migration source: AGENTS.md at 84edf0eaadb6d62cfa56d8b4056998b4ffa6b69f. The detailed policy below is preserved from that source lock.

## 12. Privacy

The selected OpenCode Foundry executor may use project-relevant technical data: repository source, tests, contracts,
qualification artifacts, build output, logs, Git metadata, branches/worktrees, engine
sources, Maven/Gradle/package caches, project configuration, and explicitly allowed
MTG deck/card/collection/ownership/gameplay data. Do not intentionally expose unrelated
personal/private data. Raw credentials, keys, and tokens are `LOCAL_ONLY`: tools may
consume them locally, but values must never appear in prompts, logs, evidence, commits,
or handoffs. Deny explicit secret-extraction operations. Automatic session sharing is
disabled.

## 13. Semantic Completion Rule

Do not stop at a remediable in-scope failure (failed test, lint, config syntax, broken
helper, incompatible design). Inspect → classify → repair → retest → continue. Stop only
for: scope COMPLETE; irreconcilable Source Lock violation; another active owner's
mutation surface; Sol/Human authority requirement (`AUTHORITY_GATE`, see §8);
destructive/external consent
requirement; genuinely unobtainable upstream information; or proceeding would weaken
Rules/Evidence/Privacy invariants. Blocked means fail closed.

## 14. Persistence and handoff

Treat every session as interruptible. After each validated milestone: coherent tree,
scoped validation, state-file update, focused local commit, recorded HEAD/evidence.
Every workstream ends with a self-contained handoff: Source Lock; Work Completed; New
Findings; Changes; Tests/Evidence (with classifications); PASS/FAIL/UNKNOWN;
Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.
