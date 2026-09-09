# Commander Simulator Next — Repository Agent Policy

Durable instructions for every OpenCode/Muse session on `moeendres-png/commander-playtest-lab`.
Stable rules only. Never place volatile data here: no SHAs, run IDs, PASS counts, failure
diagnoses, pricing, or rate limits. Session-specific facts live in the Workstream Contract
and `.foundry/WORKSTREAM_STATE.yaml`.

## 1. Mission and scope

Build and qualify the best realistically achievable full-rules Magic: The Gathering
Commander simulator. Rules Correctness outranks performance and convenience.

- Primary decision mode: exactly 4 players (one own deck, three opponents).
- Technical Rules-Core conformance: 2–5 players required; 6 players desired only if quality permits.
- The simulator must support real Commander decks for deck decisions, matchup analysis,
  reproducible simulations, later pilot improvement, and later deckbuilding optimization.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
Do not create the Production Repository, select a Rules Core, or claim Architecture Freeze.

## 2. Rules Authority

The Rules Core alone determines legal actions, costs, mana, stack, priority, targets,
combat, triggers, replacement/prevention/continuous effects, layers, state-based actions,
zones, copy/control semantics, Commander and multiplayer rules, and Rules randomness.

Pilots, providers, and orchestration receive principal-scoped observations plus
authoritative legal Decision Options, and may choose only among engine-authorized
discretionary alternatives. There is no second hidden Rules Engine in any pilot,
provider, adapter, orchestration, qualification helper, or test helper.

Forbidden production-reachable shortcuts: first-option, random-option, default yes/no,
engine-internal AI substituting for external decision control, GUI/default selections,
silent skip, parent-class fallback, requested-option filtering that reconstructs legality,
fabricated legal actions, manual outcome injection, direct `sa.resolve()` substitutes, or
standalone `AbilitySub` substitutes for a production-reachable consumer.
Unsupported production-reachable paths fail closed.

## 3. Source Truth

1. newest direct user statement;
2. freshly verified repository / branch / commit / tree / worktree;
3. current Actions / artifacts / tests / source;
4. exact pinned engine versions;
5. current official Magic Comprehensive Rules / Oracle / Rulings;
6. historical reports / chats / handoffs (provenance, not authority).

GitHub and the repository are canonical for technical state. Filenames containing
`CURRENT`, `FINAL`, or `LATEST` prove nothing about freshness.

## 4. Evidence semantics

Classifications: `DIRECTLY_VERIFIED`, `CODE_DERIVED`, `TECHNICALLY_CONFORMANT`,
`EXTERNALLY_RULE_VALIDATED`, `MODELED`, `SYNTHETIC`, `UNKNOWN`.

`UNKNOWN != PASS`. `PARTIAL != FULL`. `NOT_RUN != PASS`. `CODE_DERIVED != RUNTIME_VERIFIED`.
Import, parsing, construction, or readback do not prove runtime card behavior.
A green workflow is not automatically a Qualification PASS. Reference-engine parity does
not replace official-rules validation. Historical PASS survives a relevant
code/pin/contract/harness/semantic change only after impact adjudication and required
requalification.

## 5. Hidden information, RNG, replay

- Hidden information: principal-scoped observations only. No hidden-information leakage
  across principals in observations, logs, evidence, or errors. Actor-safe identities
  where relevant.
- RNG: all Rules randomness originates in the Rules Core with explicit seed authority.
  No unseeded or harness-side randomness in production-reachable paths.
- Replay: deterministic semantic replay from recorded seeds plus authoritative Decision
  Options. Construction or import artifacts alone are not replay evidence.

## 6. Execution routing

- GPT-5.6 Sol High (normal chat): Coordinator and adjudication tier — architecture, Source
  Truth, MTG Rules adjudication, GitHub research, difficult review, qualification design,
  evidence promotion, cross-workstream integration, gate decisions, Architecture Freeze.
- OpenCode Go + `opencode-go/muse-spark-1.3-contributor`: primary execution tier —
  implementation, repository edits, builds, tests, debugging, CI, qualification execution,
  evidence generation, deterministic tooling, long autonomous workstreams.
- ChatGPT Work / Astra: exceptional only, after `WORK_NECESSITY = PASS` (required
  capability identified; Sol High insufficient; OpenCode+Muse insufficient; genuinely
  required; smallest necessary scope). Never the normal engineering path.

## 7. Reasoning effort

Allowed project efforts: `high`, `xhigh`. `high` is the normal default for
implementation, edits, builds, tests, debugging, CI remediation, qualification, evidence,
and build-test-fix loops. `xhigh` is escalation for difficult nonlocal reasoning,
unclear engine-vs-provider-vs-harness-vs-fixture causality, complex multi-subsystem
remediation, deep debugging chains, identity/state/lifecycle problems, and
architecture-adjacent implementation. Never use `medium`, `low`, `minimal`, `none`, or
`off` for active project work. Do not use XHIGH merely because a task is large; do not
restart valid work solely to change effort.

## 8. Workstream contract

One session owns exactly one workstream ↔ one branch ↔ one worktree ↔ one mutation
surface. Every substantial assignment needs Objective, Source Lock, In/Out of Scope,
Ownership, Dependencies, Hard Gates, Forbidden Shortcuts, Evidence Requirements,
Persistence, and Stop Conditions. One primary objective; do not silently broaden scope.

## 9. Git, worktree, ownership

Do not modify another active workstream's branch or worktree. Do not modify `main`
directly. Local commits for resumability are encouraged. Push, merge, rebase,
history rewriting, remote repository creation, paid services, process killing, and
worktree deletion require explicit user approval. Before material work, verify branch,
HEAD, tree, `git status`, contract, and state file; resume from the newest verified
state without redoing valid evidence.

## 10. Privacy

Muse may use project-relevant technical data: repository source, tests, contracts,
qualification artifacts, build output, logs, Git metadata, branches/worktrees, engine
sources, Maven/Gradle/package caches, project configuration, and explicitly allowed
MTG deck/card/collection/ownership/gameplay data. Do not intentionally expose unrelated
personal/private data. Raw credentials, keys, and tokens are `LOCAL_ONLY`: tools may
consume them locally, but values must never appear in prompts, logs, evidence, commits,
or handoffs. Deny explicit secret-extraction operations. Automatic session sharing is
disabled.

## 11. Semantic Completion Rule

Do not stop at a remediable in-scope failure (failed test, lint, config syntax, broken
helper, incompatible design). Inspect → classify → repair → retest → continue. Stop only
for: scope COMPLETE; irreconcilable Source Lock violation; another active owner's
mutation surface; Sol/Human authority requirement; destructive/external consent
requirement; genuinely unobtainable upstream information; or proceeding would weaken
Rules/Evidence/Privacy invariants. Blocked means fail closed.

## 12. Persistence and handoff

Treat every session as interruptible. After each validated milestone: coherent tree,
scoped validation, state-file update, focused local commit, recorded HEAD/evidence.
Every workstream ends with a self-contained handoff: Source Lock; Work Completed; New
Findings; Changes; Tests/Evidence (with classifications); PASS/FAIL/UNKNOWN;
Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.
