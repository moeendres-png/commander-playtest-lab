# Commander Simulator Next — Repository Agent Policy

Durable instructions for every OpenCode Foundry session on `moeendres-png/commander-playtest-lab`.
Stable rules only. Never place volatile data here: no SHAs, run IDs, PASS counts, failure
diagnoses, pricing, or rate limits. Session-specific facts live in the Workstream Contract
and the workstream's explicit dedicated state file (the exact `--state` path supplied
to the launcher; there is no implicit active repository-root state).

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

### Intended end state

The project is not complete when a harness compiles or a subset of cards passes. The
intended end state is a production-quality Commander simulation system that can execute
real 100-card decks under a qualified full-rules Rules Core, with authoritative legal
Decision Options, externally controlled discretionary decisions, principal-scoped hidden
information, explicit Rules RNG, semantic replay, process-isolated batch execution, and
correct multiplayer/Commander lifecycle semantics. Before Architecture Freeze, Foundry
work should maximize decision-quality and qualification evidence for the candidate Rules
Core/provider. After Freeze, implementation work must preserve that single-source Rules
authority and move toward complete reproducible full games rather than parallel toy rules
implementations.

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
- OpenCode Foundry: primary execution tier for implementation, repository edits, builds,
  tests, debugging, CI, qualification execution, evidence generation, deterministic tooling
  and long autonomous workstreams. For new substantial work, prefer the explicit
  `space-bunny` profile: `opencode-go/space-bunny-free`, pinned by the launcher to
  native `max` reasoning for the main model, small model, and reachable project agents.
  The committed/default `muse` profile remains
  `opencode-go/muse-spark-1.3-contributor` for reproducibility, continuation of
  Muse-owned workstreams, alternate execution, and deliberate cross-model review.
  Executor selection is explicit per run, recorded, never inferred from quota or failure,
  and never falls back silently.
- ChatGPT Work / Astra: exceptional only, after `WORK_NECESSITY = PASS` (required
  capability identified; Sol High insufficient; OpenCode Foundry insufficient; genuinely
  required; smallest necessary scope). Never the normal engineering path.

Technical autonomy within those tiers is defined in §8.

## 7. Reasoning effort

Allowed project efforts: `high`, `xhigh`. `high` is the normal default for
implementation, edits, builds, tests, debugging, CI remediation, qualification, evidence,
and build-test-fix loops. `xhigh` is escalation for difficult nonlocal reasoning,
unclear engine-vs-provider-vs-harness-vs-fixture causality, complex multi-subsystem
remediation, deep debugging chains, identity/state/lifecycle problems, and
architecture-adjacent implementation. Never use `medium`, `low`, `minimal`, `none`, or
`off` as project effort for active work. The `space-bunny` execution profile deliberately
maps either allowed project effort to its verified native `max` variant and records that
mapping; this changes compute allocation, not authority. Do not use XHIGH merely because a
task is large; do not restart valid work solely to change effort. Preserve Source Lock and
durable state across model/profile handoff. HIGH→XHIGH escalation is not failure.

## 8. Technical decision authority

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`

OpenCode Foundry workers do not stop or ask the Coordinator for routine technical
decisions that can be resolved from authoritative repository source, tests,
artifacts, logs, contracts, or bounded experimentation. They must not stop or
escalate merely because a difficult technical decision exists when those sources
can resolve it.

Routing distinction:

- Space Bunny MAX: preferred execution profile for new substantial engineering work.
  It is autonomous within the workstream contract and remains natively pinned to
  `max` even when the project-level effort field is `high` or `xhigh`.
- Muse HIGH: supported bounded engineering execution + ordinary local technical
  decisions, especially for established Muse-owned workstreams.
- Muse XHIGH: supported difficult engineering + technical root-cause, evidence,
  qualification, and repair adjudication within already-defined project policy.
- Sol High: Rules, evidence-policy, qualification-policy, shared-architecture,
  cross-workstream authority, Provider Selection, Architecture Freeze.

The selected OpenCode Foundry executor owns autonomous technical execution inside the
authorized workstream contract: inspect → reason → use tools → decide technically →
implement when authorized → build/test → diagnose → repair → retest → validate →
persist evidence → continue. It must actively detect adjacent in-scope defects or
inconsistencies exposed by authoritative evidence and repair them systemically when doing
so is necessary to complete the contracted objective. It must not stop merely because the
first plan or implementation failed. Sol High is an authority and gate tier, not a routine
engineering micro-manager; the current delegation is recorded in
`docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`.

### Autonomous tool use

The selected Foundry worker is expected to use its available OpenCode tools proactively,
not merely describe what could be done. Within configured permissions it should use
read/list/glob/grep for source discovery; edit/write/apply-patch for authorized changes;
bash for builds/tests/debugging and allowed Git inspection; websearch/webfetch for current
public technical or Rules authority when required; LSP for code intelligence; skills for
project workflows; and allowed task/subagent calls for bounded exploration, adjudication,
or fresh-context review. An `allow`ed tool does not require a routine user round-trip.
An `ask`/`deny` result is a real permission boundary: never evade it by wrappers,
alternate command spellings, shell indirection, or a different tool.

Tool use remains evidence-driven. Prefer the smallest discriminating command first, but
continue through build-test-debug-fix loops until the semantic completion rule is met.
When tool output exposes an additional defect that is inside the same objective or is a
necessary prerequisite for it, investigate and repair it rather than knowingly leaving a
broken reachable path behind. Record newly discovered out-of-scope defects without
silently broadening the workstream.

For in-scope technical ambiguity, the selected Foundry worker must:

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

## 9. Reuse-first gate

Before substantial new implementation, search for an existing solution in this order:

1. current canonical source on the active lineage;
2. historical project workstreams, donor branches, port ledgers, tests, and sealed evidence;
3. the exact pinned Rules Engine and its tests/APIs;
4. current upstream of that engine when a newer fix may supersede a project patch;
5. alternate qualified candidate engines or external libraries when they can materially
   reduce work without moving Rules authority out of the Rules Core.

Classify each material capability before implementing it as one of:
`REUSE_AS_IS`, `EXTRACT_AND_GENERALIZE`, `WRAP`, `PORT_FROM_DONOR`,
`ENGINE_NATIVE_REUSE`, `REFERENCE_ONLY`, or `NEW_IMPLEMENTATION_REQUIRED`.
`NEW_IMPLEMENTATION_REQUIRED` needs a concrete source-level reason why current source,
historical donors, engine-native APIs/tests, and relevant external donors cannot safely
satisfy the requirement.

Prefer reuse > extract/generalize > wrap > port > new implementation when Rules
Correctness, evidence integrity, licensing, and source-lock compatibility permit it.
Historical code and tests may transfer; historical PASS evidence does not transfer
without impact adjudication. Never wholesale-merge a diverged donor branch merely because
it contains useful code. Prefer the smallest reviewed transplant and retain provenance.

This gate is bounded discovery, not a research stopping point: once a clearly superior,
compatible donor is established, use it and continue implementation/build/test/debug/
qualification. Do not create a second Rules Engine, second observation layer, second replay
system, or parallel decision protocol when a qualified existing mechanism can be reused.

Qualification fixture or obligation names are evidence labels, not architecture requirements. Before adding a new decision class or protocol surface, inspect the engine callback and its authoritative context; an obligation may already be satisfied by a generic existing decision family plus a specific engine-supplied domain.

## 10. Workstream contract

One session owns exactly one workstream ↔ one branch ↔ one worktree ↔ one mutation
surface. Every substantial assignment needs Objective, Source Lock, In/Out of Scope,
Ownership, Dependencies, Hard Gates, Forbidden Shortcuts, Evidence Requirements,
Persistence, and Stop Conditions. One primary objective; do not silently broaden scope.

## 11. Git, worktree, ownership

Do not modify another active workstream's branch or worktree. Do not modify `main`
directly. Local commits for resumability are encouraged. Push, merge, rebase,
history rewriting, remote repository creation, paid services, process killing, and
worktree deletion require explicit user approval. Before material work, verify branch,
HEAD, tree, `git status`, contract, and state file; resume from the newest verified
state without redoing valid evidence.

### Cross-workstream access

Project-wide understanding does not imply project-wide write authority.

The normal Foundry run owns one primary writable worktree. A bounded integration task may
also declare additional verified workspace surfaces:

- `read-only`: exact repository + HEAD/tree, runtime-readable, edit-denied;
- `owned-write`: exact repository + branch + HEAD/tree + state path + matching ownership.

All owned-write surfaces must be locked before the OpenCode child starts and remain locked
for its entire lifetime. Foreign-active, unknown-owner and undeclared sibling worktrees
remain non-writable. Space Bunny MAX and Muse use the same access contract.

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
