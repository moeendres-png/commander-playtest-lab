# Agent Policy — Execution and Technical Authority

Routed from repository-root AGENTS.md. Read this document for substantial engineering/campaign execution or when agent/model routing, technical autonomy, tool use, or campaign continuation is material.

Migration source: AGENTS.md at 84edf0eaadb6d62cfa56d8b4056998b4ffa6b69f. The detailed policy below is preserved from that source lock.

## 6. Execution routing

- GPT-5.6 Sol High (normal chat): Coordinator and adjudication tier — architecture, Source
  Truth, MTG Rules adjudication, GitHub research, difficult review, qualification design,
  evidence promotion, cross-workstream integration, gate decisions, Architecture Freeze.
- OpenCode Foundry: primary execution tier for implementation, repository edits, builds,
  tests, debugging, CI, qualification execution, evidence generation, deterministic tooling
  and long autonomous workstreams. The committed/default and preferred executor is
  `deepseek`: `opencode-go/deepseek-v4.1-flash` at native `max` for the main model,
  small model, primary implementer, and reachable project agents. Space Bunny is an
  explicit secondary only: `opencode-go/space-bunny-free` at native `max`, for bounded,
  mechanical, token-heavy, bulk and background work. No other OpenCode execution profile is
  authorized or reachable through the canonical launcher/config. Executor selection is explicit
  per run, recorded, never inferred from quota or failure, and never falls back silently.
- Claude Opus 5.5: explicitly authorized direct engineering/campaign executor when the
  session prompt declares the campaign objective and writable ownership surface. Claude
  may execute large autonomous campaigns under the same Rules, evidence, privacy,
  ownership, Git and merge gates defined here; model identity never grants authority to
  cross a reserved Coordinator gate.
- ChatGPT Work / Astra: exceptional only, after `WORK_NECESSITY = PASS` (required
  capability identified; Sol High insufficient; OpenCode Foundry and any available
  authorized Claude campaign insufficient; genuinely required; smallest necessary scope).
  Never the normal engineering path.

Technical autonomy within those tiers is defined in §8.

## 7. Execution effort

Active OpenCode Foundry execution has exactly two allowed launcher identities:

- DeepSeek: native `max` only. This is the default and preferred execution path for
  implementation, debugging, qualification, integration, CI remediation, evidence and
  long-running campaigns.
- Space Bunny: native `max` only. An explicit secondary for bounded, mechanical,
  token-heavy, bulk and background work, and for deliberately authorized cross-model
  checks.

No other OpenCode executor is selectable under current authority. Historical model references
are provenance only, are not migration targets, and must not generate routing/governance work
without a new direct user instruction. There is no active-work `high`, `medium`, `low`,
`minimal`, `none`, or `off` native lane. The project-level
`--effort` field describes task and authority routing only and never lowers either
executor below its native level. Do not relabel DeepSeek MAX or Space Bunny MAX as
XHIGH; record the actual native identity.

## 8. Technical decision authority

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`

OpenCode Foundry workers do not stop or ask the Coordinator for routine technical
decisions that can be resolved from authoritative repository source, tests,
artifacts, logs, contracts, or bounded experimentation. They must not stop or
escalate merely because a difficult technical decision exists when those sources
can resolve it.

Routing distinction:

- DeepSeek MAX: committed/default and preferred execution profile for active engineering.
  It is autonomous within the workstream contract and always runs at native `max`.
- Space Bunny MAX: explicit secondary execution profile for bounded, mechanical,
  token-heavy, bulk and background work, and for deliberately authorized cross-model
  checks. It never runs below native `max`.
- Claude Opus 5.5: direct campaign executor when explicitly authorized by the session
  contract. It may own campaign-sized technical execution and continuous task selection
  inside declared ownership, but does not inherit Foundry-specific launcher permissions.
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
`docs/CURRENT_EXECUTION_AUTHORITY.md`.

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


### Autonomous campaign authority

`AUTONOMOUS_CAMPAIGN_AUTHORITY = ENABLED`
`ASSUMPTIONS_ARE_CHALLENGEABLE = TRUE`
`SCOPE_EXPANSION_WITHIN_OBJECTIVE = AUTONOMOUS`

An explicitly authorized project executor may own a campaign-sized workstream rather than
only one ticket or one preselected implementation task. A campaign remains one primary
workstream when its sequential milestones serve one coherent objective, even when it
contains multiple investigations, fixes, qualification steps, PRs and integrations.

Within that campaign the worker is expected to:

1. refresh canonical source truth, ownership, CI and evidence;
2. identify the highest-value currently unowned problem inside the campaign objective;
3. investigate root cause and actively search for contradictory evidence;
4. challenge existing technical assumptions rather than preserving them by inertia;
5. implement or remediate on the correct owned surface when authorized;
6. validate with discriminating tests and negative controls;
7. integrate and persist evidence/checkpoints;
8. reassess the project and choose the next useful unowned milestone;
9. continue until the campaign is COMPLETE or a genuine stop condition exists.

Finishing one ticket, test, bug fix or PR is not by itself a campaign stop condition.

#### Challenge mandate

No engine candidate, bridge, harness, workflow, test, benchmark, architecture hypothesis,
historical technical conclusion, documentation statement or project convention is
technically immune merely because it is old, widely used, previously green, named
`CURRENT`/`FINAL`, expensive to replace, or authored by another model/worker.

For material assumptions ask, as applicable:

- Is this still true on the current source lock?
- Would this test fail if the claimed mechanic were actually broken?
- Can this PASS for the wrong reason?
- Is there an engine-native or simpler systemic solution?
- Is this evidence still valid after later code/pin/contract/harness changes?
- Is this complexity still necessary?
- Is the current bottleneck artificial or duplicated work?
- Is a local patch hiding a more general defect?

Fresher higher-authority evidence outranks project inertia. A worker may overturn an older
technical conclusion when current evidence demonstrates it is wrong, but must preserve
provenance and record why the prior conclusion is superseded rather than rewriting history.

There are no sacred implementations and no candidate receives incumbent protection.
Prefer the strongest currently supportable solution under Rules Correctness, evidence
integrity, simplicity, maintainability and then performance. Sunk cost is not evidence.
This does not authorize Production Provider selection or Architecture Freeze.

#### Bounded autonomous scope expansion

Adjacent technical work that materially advances the SAME campaign objective is not a
material scope expansion merely because it was not visible at campaign start. The worker
may autonomously take such work when it is high-value or necessary and does not:

- cross an active ownership boundary;
- introduce a genuinely new project objective;
- alter reserved Rules/evidence/qualification policy;
- select a provider or claim Architecture Freeze;
- weaken privacy, Rules authority, fail-closed semantics or evidence standards.

Examples include repairing an adjacent systemic defect, fixing a misleading/flaky test,
repairing CI needed to qualify the work, adding a missing regression harness, performing
required impact adjudication, or resolving a newly exposed prerequisite.

A genuinely new project objective, shared-architecture decision, Rules dispute,
evidence-policy change, ownership conflict, Provider Selection or Architecture Freeze
remains an authority gate.

#### Project-wide read, bounded write

Authorized campaign workers should inspect the whole relevant project and candidate-engine
history read-only when that improves technical decisions. Project-wide understanding is
encouraged; project-wide write authority is not implied. Mutation remains limited to
declared owned surfaces.

#### Continuous task selection and stop conditions

After each milestone, refresh canonical HEAD/tree, open PRs/issues, current ownership, CI
and evidence state. If useful unowned work remains inside the campaign objective, select
the next milestone without asking the user to choose routine technical work.

Stop only when:

- the campaign objective is COMPLETE;
- every worthwhile remaining task is owned elsewhere;
- a genuine authority/ownership/source/permission gate blocks all useful continuation;
- an external dependency makes further progress impossible; or
- resource/tool limits require a resumable handoff.

A gate on one subproblem does not terminate the campaign when independent useful work
remains.

#### Claude Opus 5.5 campaign executor

An explicitly launched Claude Opus 5.5 engineering session may receive this same
autonomous technical campaign authority when its prompt declares the campaign objective,
repository context and writable ownership surface or surfaces. Claude is not restricted to
advisory or review work: within its authorized surfaces it may investigate, implement,
test, debug, commit, push, maintain PRs and integrate its own work under the same project
Rules, evidence, privacy, Git and merge gates.

A bounded integration campaign may own multiple disjoint repository/worktree mutation
surfaces when one coherent objective genuinely requires them. Every writable surface must
be freshly verified, explicitly declared, free of another active writer (or transferred by
a persisted handoff), and governed by the same campaign ownership. Undeclared, foreign-
active or unknown-owner surfaces remain read-only. Multi-surface authority never implies
project-wide write authority.

Claude must still re-read current repository authority and fresh ownership before material
mutation. Tool/runtime capabilities are not inferred from model identity: unavailable,
ask-gated or denied operations remain real boundaries. Claude may not use this section to
bypass Foundry-specific sandboxing, another worker's ownership, protected branches,
reserved Coordinator decisions or any hard prohibition in this file.
