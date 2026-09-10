# Commander Simulator Next — Repository Agent Policy

Durable instructions for every OpenCode/Muse session on `moeendres-png/commander-playtest-lab`.
Stable rules only. Never place volatile data here: no SHAs, run IDs, PASS counts, failure
diagnoses, pricing, or rate limits. Session-specific facts live in the Workstream Contract
and `.foundry/WORKSTREAM_STATE.yaml`.

## 1. Mission and scope

Build and qualify the best realistically achievable full-rules Magic: The Gathering
Commander simulator. Rules Correctness outranks performance and convenience.
Governing mission policy is `docs/PROJECT_MISSION.md` (established on the PR #173
line): outcome-first, player-count neutral. Its player-count and architecture
direction governs over any summary here, so merging this file must never reintroduce
a fixed 4-player architecture restriction.

- Four players (one own deck, three opponents) is the primary benchmark and decision
  mode. It is not an architecture anchor, a fixed-size data-model requirement, or a
  reason to exclude otherwise better candidates or research.
- Technical Rules-Core conformance for 2–5 players is mandatory. Record evidence for
  each count; a 4P result does not establish another count's correctness.
- Prefer 6+ or generally variable-player solutions when they improve Rules Correctness,
  simplicity, reuse, testability, or research/implementation. This preference must not
  weaken Rules Correctness or the required 2–5P conformance.
- A target player-count capability is not runtime evidence. Unsupported paths remain
  fail closed until qualified.
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

Technical autonomy within those tiers is defined in §8.

## 7. Reasoning effort

Allowed project efforts: `high`, `xhigh`. `high` is the normal default for
implementation, edits, builds, tests, debugging, CI remediation, qualification, evidence,
and build-test-fix loops. `xhigh` is escalation for difficult nonlocal reasoning,
unclear engine-vs-provider-vs-harness-vs-fixture causality, complex multi-subsystem
remediation, deep debugging chains, identity/state/lifecycle problems, and
architecture-adjacent implementation. Never use `medium`, `low`, `minimal`, `none`, or
`off` for active project work. Do not use XHIGH merely because a task is large; do not
restart valid work solely to change effort. Preserve Source Lock and durable state
across escalation. HIGH→XHIGH escalation is not failure.

## 8. Technical decision authority

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`

OpenCode/Muse workers do not stop or ask the Coordinator for routine technical
decisions that can be resolved from authoritative repository source, tests,
artifacts, logs, contracts, or bounded experimentation. They must not stop or
escalate merely because a difficult technical decision exists when those sources
can resolve it.

Routing distinction:

- Muse HIGH: autonomous bounded engineering execution + ordinary local technical
  decisions.
- Muse XHIGH: autonomous difficult engineering + technical root-cause, evidence,
  qualification, and repair adjudication within already-defined project policy.
- Sol High: Rules, evidence-policy, qualification-policy, shared-architecture,
  cross-workstream authority, Provider Selection, Architecture Freeze.

Muse HIGH owns autonomous bounded engineering execution, including ordinary local
technical decisions inside the authorized workstream contract. Muse XHIGH owns
difficult technical reasoning and adjudication within already-defined project
policy (root cause, failure-class, evidence-provenance, repair-DAG decisions).
The model is: Muse investigates → reasons → decides technically → implements when
authorized → tests → diagnoses → repairs → validates → records evidence →
continues. Sol High is an authority and gate tier, not a routine engineering
micro-manager; the full delegation is recorded in
`docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md`.

For in-scope technical ambiguity, Muse must:

1. inspect authoritative evidence;
2. form one or more hypotheses;
3. search for contradictory evidence;
4. perform the smallest permitted validation when required;
5. adjudicate technically when existing project policy determines the allowed semantics;
6. persist the decision and evidence;
7. continue the workstream.

Only a real Rules, Evidence-Policy, Architecture, Scope, Provider, or Freeze
authority question becomes an `AUTHORITY_GATE` for Sol High. A technical decision
is never an authority decision: reaching and persisting a root cause within policy
is the job, not an escalation.

## 9. Workstream contract

One session owns exactly one workstream ↔ one branch ↔ one worktree ↔ one mutation
surface. Every substantial assignment needs Objective, Source Lock, In/Out of Scope,
Ownership, Dependencies, Hard Gates, Forbidden Shortcuts, Evidence Requirements,
Persistence, and Stop Conditions. One primary objective; do not silently broaden scope.

## 10. Git, worktree, ownership

Do not modify another active workstream's branch or worktree. Do not modify `main`
directly. Local commits for resumability are encouraged. Push, merge, rebase,
history rewriting, remote repository creation, paid services, process killing, and
worktree deletion require explicit user approval. Before material work, verify branch,
HEAD, tree, `git status`, contract, and state file; resume from the newest verified
state without redoing valid evidence.

## 11. Privacy

Muse may use project-relevant technical data: repository source, tests, contracts,
qualification artifacts, build output, logs, Git metadata, branches/worktrees, engine
sources, Maven/Gradle/package caches, project configuration, and explicitly allowed
MTG deck/card/collection/ownership/gameplay data. Do not intentionally expose unrelated
personal/private data. Raw credentials, keys, and tokens are `LOCAL_ONLY`: tools may
consume them locally, but values must never appear in prompts, logs, evidence, commits,
or handoffs. Deny explicit secret-extraction operations. Automatic session sharing is
disabled.

## 12. Semantic Completion Rule

Do not stop at a remediable in-scope failure (failed test, lint, config syntax, broken
helper, incompatible design). Inspect → classify → repair → retest → continue. Stop only
for: scope COMPLETE; irreconcilable Source Lock violation; another active owner's
mutation surface; Sol/Human authority requirement (`AUTHORITY_GATE`, see §8);
destructive/external consent
requirement; genuinely unobtainable upstream information; or proceeding would weaken
Rules/Evidence/Privacy invariants. Blocked means fail closed.

## 13. Persistence and handoff

Treat every session as interruptible. After each validated milestone: coherent tree,
scoped validation, state-file update, focused local commit, recorded HEAD/evidence.
Every workstream ends with a self-contained handoff: Source Lock; Work Completed; New
Findings; Changes; Tests/Evidence (with classifications); PASS/FAIL/UNKNOWN;
Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.
