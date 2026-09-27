# Commander Simulator Next — Repository Agent Policy

Durable instructions for every OpenCode execution session on `moeendres-png/commander-playtest-lab`.
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

Current execution-model authority is `docs/foundry-execution/EXECUTION_MODEL_ROUTING.md`.
Every worker must use that file together with this `AGENTS.md`; historical workstream
documents retain their original model names as provenance and are not routing authority.

- GPT-5.6 Sol High (normal ChatGPT): Coordinator and final adjudication tier —
  architecture, Source Truth, MTG Rules adjudication, evidence-policy decisions,
  cross-workstream integration, Production Provider selection and Architecture Freeze.
- OpenCode Go + `opencode-go/space-bunny-free` at `max`: preferred execution lane for
  new implementation, repository edits, builds, tests, debugging, CI, qualification,
  evidence generation and long autonomous workstreams.
- OpenCode Go + `opencode-go/muse-spark-1.3-contributor` at `xhigh`: fully supported
  alternate execution lane for continuation of Muse-owned work, independent comparison,
  second-pass engineering, difficult remediation, or operator-selected execution.
- ChatGPT Work / Astra: exceptional only after `WORK_NECESSITY = PASS`; it is not a
  routine replacement for Sol or either OpenCode lane.

Model choice never changes Rules authority, evidence semantics, branch ownership or
workstream scope.

## 7. Reasoning effort and model discipline

Active project engineering uses exactly the lane-native maximum configured effort:

- Space Bunny Free: `max` only.
- Muse Spark 1.3 Contributor: `xhigh` only.

Do not silently downgrade effort, substitute another model/provider, or fall back after
quota/auth/model-resolution failure. Fail closed and report the exact execution-model
gate instead. Token cost is not an optimization objective; spend context/reasoning when
it materially improves correctness, contradictory-evidence search, debugging or
validation. Free tokens do not justify irrelevant repository scans or rerunning valid
evidence without an impact reason.

An already-running workstream keeps its verified model identity until a deliberate
checkpointed handoff. Do not restart valid work solely to switch models.

## 8. Technical decision authority

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`

Both Space Bunny MAX and Muse XHIGH own autonomous technical execution inside the
authorized workstream contract: inspect, reason, decide technically, implement when
authorized, test, diagnose, repair, validate, persist evidence and continue.

OpenCode workers do not stop or ask the Coordinator for routine technical decisions
that can be resolved from the workstream contract, source, tests, logs or bounded runtime evidence.

Sol High retains authority for ambiguous MTG Rules interpretation, project-wide
evidence/qualification policy, shared architecture, cross-workstream ownership conflict,
material scope expansion, Production Provider selection and Architecture Freeze.

For in-scope technical ambiguity, either OpenCode lane must:

1. inspect authoritative evidence;
2. form one or more hypotheses;
3. actively search for contradictory evidence;
4. perform the smallest permitted validation required to distinguish them;
5. adjudicate technically when current project policy determines the semantics;
6. persist the decision and evidence;
7. continue the workstream.

Sequential use of both models on one workstream is allowed only after a persisted
checkpoint and handoff of the same branch/worktree ownership; never run two writers
against one mutation surface. Parallel use is allowed only for independent branches /
worktrees / mutation surfaces, or bounded read-only review. A technical decision is not
an authority gate merely because the two models disagree.

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

## 12. Privacy

OpenCode workers may use project-relevant technical data: repository source, tests, contracts,
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
